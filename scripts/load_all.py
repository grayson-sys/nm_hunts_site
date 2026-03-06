#!/usr/bin/env python3
"""
Master loader: runs OR, NV, ID loaders in sequence, then verifies.
"""

import subprocess
import sys
import os
import psycopg2

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
DB_CONFIG = {
    'host': 'localhost', 'port': 5432,
    'dbname': 'draws', 'user': 'draws', 'password': 'drawspass'
}


def run_loader(script_name):
    path = os.path.join(SCRIPTS_DIR, script_name)
    print(f"\n{'='*60}")
    print(f"  Running {script_name}")
    print(f"{'='*60}")
    result = subprocess.run([sys.executable, path], capture_output=False)
    if result.returncode != 0:
        print(f"  ERROR: {script_name} exited with code {result.returncode}")
        return False
    return True


def verify():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    print(f"\n{'='*60}")
    print("  VERIFICATION")
    print(f"{'='*60}")

    # Summary by state
    cur.execute("""
        SELECT s.state_code,
            COUNT(DISTINCT h.hunt_id) as hunts,
            COUNT(DISTINCT g.gmu_id) as gmus,
            COUNT(DISTINCT dr.result_id) as draw_results,
            COUNT(DISTINCT hs.harvest_id) as harvest_stats,
            COUNT(DISTINCT hd.hunt_date_id) as hunt_dates
        FROM states s
        LEFT JOIN hunts h ON h.state_id = s.state_id
        LEFT JOIN gmus g ON g.state_id = s.state_id
        LEFT JOIN draw_results_by_pool dr ON dr.hunt_id = h.hunt_id
        LEFT JOIN harvest_stats hs ON hs.hunt_id = h.hunt_id
        LEFT JOIN hunt_dates hd ON hd.hunt_id = h.hunt_id
        WHERE s.state_code IN ('OR', 'NV', 'ID')
        GROUP BY s.state_code ORDER BY s.state_code
    """)
    print(f"\n  {'State':<8} {'Hunts':<8} {'GMUs':<8} {'Draw':<8} {'Harvest':<10} {'Dates':<8}")
    print(f"  {'-'*50}")
    for row in cur.fetchall():
        print(f"  {row[0]:<8} {row[1]:<8} {row[2]:<8} {row[3]:<8} {row[4]:<10} {row[5]:<8}")

    # Check for duplicate hunt codes
    cur.execute("""
        SELECT s.state_code, h.hunt_code, COUNT(*)
        FROM hunts h JOIN states s ON s.state_id = h.state_id
        WHERE s.state_code IN ('OR', 'NV', 'ID')
        GROUP BY s.state_code, h.hunt_code HAVING COUNT(*) > 1
    """)
    dupes = cur.fetchall()
    if dupes:
        print(f"\n  WARNING: Duplicate hunt codes found:")
        for d in dupes:
            print(f"    {d[0]} {d[1]}: {d[2]} rows")
    else:
        print(f"\n  No duplicate hunt codes. All clean.")

    conn.close()


def main():
    ok = True
    for script in ['load_or.py', 'load_nv.py', 'load_id.py']:
        if not run_loader(script):
            ok = False
            print(f"\n  Stopping due to error in {script}")
            break

    verify()

    if ok:
        print("\nAll loaders completed successfully.")
    else:
        print("\nSome loaders failed. Check output above.")
        sys.exit(1)


if __name__ == '__main__':
    main()
