#!/usr/bin/env python3
"""
Overnight supervisor — monitors DB progress, restarts failed agents,
keeps Flask server alive. Runs until all target states are loaded.
"""
import subprocess, time, psycopg2, os, sys, json
from datetime import datetime

DB = dict(host='localhost', port=5432, dbname='draws', user='draws', password='drawspass')
LOG = '/tmp/overnight_supervisor.log'
PROJECT = '/Users/openclaw/Documents/GraysonsDrawOdds'

# Target: each state should have at least this many hunts when "done"
TARGETS = {
    'WY': 200,   # ~200+ hunt codes expected
    'AZ': 200,   # 253 from proclamation
    'CO': 800,   # 1,222 from proclamation
    'UT': 100,
    'MT': 20,
    'CA': 50,
}

# Load tasks per state — what to run if that state is empty
LOAD_SCRIPTS = {
    'WY': 'scripts/load_wy.py',
    'AZ': 'scripts/load_az.py',
    'CO': 'scripts/load_co.py',
}

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG, 'a') as f:
        f.write(line + '\n')

def get_counts():
    try:
        conn = psycopg2.connect(**DB)
        cur = conn.cursor()
        cur.execute("""
            SELECT s.state_code,
              COUNT(DISTINCT h.hunt_id) as hunts,
              COUNT(DISTINCT dr.result_id) as draw_results,
              COUNT(DISTINCT hs.harvest_id) as harvest_rows,
              COUNT(DISTINCT hd.hunt_date_id) as dates
            FROM states s
            LEFT JOIN hunts h ON h.state_id = s.state_id
            LEFT JOIN draw_results_by_pool dr ON dr.hunt_id = h.hunt_id
            LEFT JOIN harvest_stats hs ON hs.hunt_id = h.hunt_id
            LEFT JOIN hunt_dates hd ON hd.hunt_id = h.hunt_id
            GROUP BY s.state_code ORDER BY s.state_code
        """)
        rows = cur.fetchall()
        cur.close(); conn.close()
        return {r[0]: {'hunts': r[1], 'draw': r[2], 'harvest': r[3], 'dates': r[4]}
                for r in rows}
    except Exception as e:
        log(f"DB error: {e}")
        return {}

def server_alive():
    try:
        result = subprocess.run(['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}',
                                 'http://localhost:5001/'],
                                capture_output=True, text=True, timeout=5)
        return result.stdout.strip() == '200'
    except:
        return False

def restart_server():
    log("Restarting Flask server...")
    subprocess.run(['pkill', '-f', 'server.py'], capture_output=True)
    time.sleep(2)
    env = os.environ.copy()
    env.update({'DRAWS_DB_HOST': 'localhost', 'DRAWS_DB_PORT': '5432',
                'DRAWS_DB_NAME': 'draws', 'DRAWS_DB_USER': 'draws',
                'DRAWS_DB_PASS': 'drawspass'})
    subprocess.Popen(
        ['python3', 'app/server.py'],
        cwd=PROJECT, env=env,
        stdout=open('/tmp/server.log', 'a'),
        stderr=subprocess.STDOUT
    )
    time.sleep(4)
    if server_alive():
        log("Server back up ✓")
    else:
        log("Server still down — will retry next cycle")

def spawn_loader(state_code, script_path):
    log(f"Spawning loader for {state_code}: {script_path}")
    full_path = os.path.join(PROJECT, script_path)
    if not os.path.exists(full_path):
        log(f"  Script not found: {full_path} — will try overnight task")
        return spawn_claude(state_code)
    
    env = os.environ.copy()
    env.pop('ANTHROPIC_API_KEY', None)
    result = subprocess.run(
        ['python3', full_path],
        cwd=PROJECT, env=env,
        capture_output=True, text=True, timeout=3600
    )
    log(f"  {state_code} loader exit code: {result.returncode}")
    if result.stdout: log(f"  stdout tail: {result.stdout[-500:]}")
    if result.stderr: log(f"  stderr tail: {result.stderr[-200:]}")
    return result.returncode == 0

def spawn_claude(state_code):
    """Spawn a claude agent to load a specific state."""
    task = f"""
Load {state_code} hunt data into PostgreSQL.
DB: host=localhost port=5432 dbname=draws user=draws password=drawspass
Project root: {PROJECT}

CRITICAL: Always check column names with information_schema before writing SQL.
Schema notes: states.state_id (not id), hunts.hunt_id (not id), gmus.gmu_id (not id)
draw_results_by_pool: result_id, hunt_id, draw_year, pool_id, applications
hunt_dates: hunt_date_id, hunt_id, season_year, start_date, end_date (NOT open_date/close_date)

Read the task file: {PROJECT}/OVERNIGHT_LOAD_TASK.md — find the {state_code} section and execute it.
Then check the scripts/ folder for any existing load_{state_code.lower()}.py and run it if present.
Do NOT stop to ask questions. Write scripts/load_{state_code.lower()}.py and run it.
After loading, print row counts for all tables for {state_code}.
Commit with: git add -A && git commit -m "Load {state_code} data overnight"
"""
    env = os.environ.copy()
    env.pop('ANTHROPIC_API_KEY', None)
    proc = subprocess.Popen(
        ['claude', '--dangerously-skip-permissions', '-p', task],
        cwd=PROJECT, env=env,
        stdout=open(f'/tmp/load_{state_code.lower()}.log', 'w'),
        stderr=subprocess.STDOUT
    )
    log(f"  Claude agent spawned for {state_code}, PID {proc.pid}")
    # Wait up to 90 minutes
    try:
        proc.wait(timeout=5400)
        log(f"  {state_code} agent finished, exit code {proc.returncode}")
        return proc.returncode == 0
    except subprocess.TimeoutExpired:
        log(f"  {state_code} agent timed out — killing and moving on")
        proc.kill()
        return False

def commit_progress():
    try:
        subprocess.run(
            ['git', 'add', '-A'],
            cwd=PROJECT, capture_output=True
        )
        result = subprocess.run(
            ['git', 'commit', '-m', f'Overnight progress checkpoint {datetime.now().strftime("%H:%M")}'],
            cwd=PROJECT, capture_output=True, text=True
        )
        if 'nothing to commit' not in result.stdout:
            log("Git committed ✓")
    except Exception as e:
        log(f"Git error: {e}")

def main():
    log("="*50)
    log("OVERNIGHT SUPERVISOR STARTING")
    log("="*50)
    
    prev_counts = {}
    stall_counter = {}
    states_done = set()
    
    # States to process in order
    pipeline = ['WY', 'AZ', 'CO', 'UT', 'MT', 'CA']
    current_idx = 0
    active_proc = None
    
    # Check what's already done
    counts = get_counts()
    for state in pipeline:
        c = counts.get(state, {})
        if c.get('hunts', 0) >= TARGETS.get(state, 50):
            log(f"{state} already done ({c['hunts']} hunts) — skipping")
            states_done.add(state)
    
    loop = 0
    while True:
        loop += 1
        now = datetime.now().strftime('%H:%M:%S')
        counts = get_counts()
        
        # Print progress every 10 loops
        if loop % 10 == 1:
            log("-" * 40)
            for state in ['NM','OR','NV','ID','WY','AZ','CO','UT','MT','CA']:
                c = counts.get(state, {})
                if c.get('hunts', 0) > 0:
                    log(f"  {state}: hunts={c['hunts']} draw={c['draw']} harvest={c['harvest']} dates={c['dates']}")
            log("-" * 40)
        
        # Check server
        if not server_alive():
            log("Server down — restarting")
            restart_server()
        
        # Find next state to work on
        next_state = None
        for state in pipeline:
            if state in states_done:
                continue
            c = counts.get(state, {})
            target = TARGETS.get(state, 50)
            if c.get('hunts', 0) >= target:
                log(f"{state} reached target ({c['hunts']} hunts) ✓")
                states_done.add(state)
                commit_progress()
                continue
            next_state = state
            break
        
        # If no active work, start next state
        if next_state and (active_proc is None or active_proc.poll() is not None):
            if active_proc is not None and active_proc.poll() is not None:
                rc = active_proc.poll()
                log(f"Previous agent exited with code {rc}")
            
            script = LOAD_SCRIPTS.get(next_state)
            script_path = os.path.join(PROJECT, script) if script else None
            
            if script_path and os.path.exists(script_path):
                log(f"Running existing script for {next_state}: {script}")
                env = os.environ.copy()
                env.pop('ANTHROPIC_API_KEY', None)
                active_proc = subprocess.Popen(
                    ['python3', script_path],
                    cwd=PROJECT, env=env,
                    stdout=open(f'/tmp/load_{next_state.lower()}.log', 'w'),
                    stderr=subprocess.STDOUT
                )
                log(f"  Script PID: {active_proc.pid}")
            else:
                log(f"Spawning claude agent for {next_state}")
                task = f"""
Load {next_state} hunt data into PostgreSQL.
DB: host=localhost port=5432 dbname=draws user=draws password=drawspass
Project root: {PROJECT}

CRITICAL SCHEMA — use these exact column names:
- states: state_id (PK), state_code
- hunts: hunt_id (PK), state_id, species_id, hunt_code, weapon_type_id, season_label
- gmus: gmu_id (PK), state_id, gmu_code, gmu_name, gmu_sort_key
- hunt_gmus: hunt_gmu_id (PK), hunt_id, gmu_id
- draw_results_by_pool: result_id (PK), hunt_id, draw_year, pool_id, applications
- harvest_stats: harvest_id (PK), hunt_id, harvest_year, access_type, success_rate
- hunt_dates: hunt_date_id (PK), hunt_id, season_year, start_date, end_date

Always verify columns with: SELECT column_name FROM information_schema.columns WHERE table_name='X'
Look up pool_id from the pools table: SELECT * FROM pools;
Look up weapon_type_id from weapon_types: SELECT * FROM weapon_types;
Look up species_id from species: SELECT * FROM species;

Read {PROJECT}/OVERNIGHT_LOAD_TASK.md and execute the {next_state} section.
Source files in {PROJECT}/{next_state}/raw_data/ and {PROJECT}/{next_state}/proclamations/2026/
Write the loader script to {PROJECT}/scripts/load_{next_state.lower()}.py
Run it. Print row counts when done.
Commit: git add -A && git commit -m "Load {next_state} overnight"
Do NOT stop to ask questions.
"""
                env = os.environ.copy()
                env.pop('ANTHROPIC_API_KEY', None)
                active_proc = subprocess.Popen(
                    ['claude', '--dangerously-skip-permissions', '-p', task],
                    cwd=PROJECT, env=env,
                    stdout=open(f'/tmp/load_{next_state.lower()}.log', 'w'),
                    stderr=subprocess.STDOUT
                )
                log(f"  Claude PID: {active_proc.pid} — log: /tmp/load_{next_state.lower()}.log")
        
        # Check if all done
        if len(states_done) >= len(pipeline):
            log("ALL STATES DONE! 🎉")
            commit_progress()
            restart_server()
            
            # Final counts
            counts = get_counts()
            log("\nFINAL COUNTS:")
            total_hunts = 0
            for state in ['NM','OR','NV','ID','WY','AZ','CO','UT','MT','CA']:
                c = counts.get(state, {})
                log(f"  {state}: hunts={c['hunts']} draw={c['draw']} harvest={c['harvest']} dates={c['dates']}")
                total_hunts += c.get('hunts', 0)
            log(f"  TOTAL HUNTS: {total_hunts}")
            
            with open(f'{PROJECT}/OVERNIGHT_RESULTS.md', 'a') as f:
                f.write(f"\n## Supervisor completed at {datetime.now()}\n")
                f.write(f"Total hunts across all states: {total_hunts}\n")
            break
        
        time.sleep(60)  # Check every minute

if __name__ == '__main__':
    main()
