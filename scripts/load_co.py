#!/usr/bin/env python3
"""
Colorado data loader: hunts, GMUs, draw results, harvest stats, hunt dates.

Sources:
  - CO/proclamations/2026/CO_hunt_dates_2026.csv (1,222 hunt codes)
  - 2024/2025 draw recap PDFs (elk + deer)
  - 2024/2025 drawn-out-at PDFs (elk + deer)
  - 2024 elk/deer harvest reports
"""

import os
import re
import csv
import pdfplumber
import psycopg2
from collections import defaultdict

BASE_DIR = "/Users/openclaw/Documents/GraysonsDrawOdds"
DB_CONFIG = {
    'host': 'localhost', 'port': 5432,
    'dbname': 'draws', 'user': 'draws', 'password': 'drawspass'
}


def dashed_to_compact(hunt_code):
    """Convert CO dashed hunt code to compact form: D-E-003-O1-A -> DE003O1A"""
    return hunt_code.replace('-', '')


def compact_to_dashed(compact):
    """Convert CO compact hunt code to dashed form: DE003O1A -> D-E-003-O1-A"""
    if len(compact) < 8:
        return compact
    return f"{compact[0]}-{compact[1]}-{compact[2:5]}-{compact[5:7]}-{compact[7]}"


def parse_co_draw_recap(filepath):
    """Parse CO draw recap PDF to extract per-hunt: total apps, drawn, quota.
    Scans for hunt code patterns and 'Total Choice 1' lines.
    Returns dict: compact_code -> {quota, choice1_apps, total_drawn, res_drawn, nr_drawn}
    """
    hunts = {}
    current_hunt = None
    hunt_code_re = re.compile(r'^([DE][EMF]\d{3}[A-Z0-9]{2}[ARMSP])\b')

    with pdfplumber.open(filepath) as pdf:
        total_pages = len(pdf.pages)
        for page_num, page in enumerate(pdf.pages):
            if page_num % 200 == 0:
                print(f"    Processing page {page_num}/{total_pages}...")
            text = page.extract_text()
            if not text:
                continue

            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Detect hunt code (compact form like EE001E1R)
                m = hunt_code_re.match(line)
                if m:
                    code = m.group(1)
                    current_hunt = code
                    if code not in hunts:
                        hunts[code] = {
                            'quota': 0, 'choice1_apps': 0,
                            'total_drawn': 0, 'res_drawn': 0, 'nr_drawn': 0,
                        }
                    continue

                if not current_hunt:
                    continue

                # Total Quota line
                if 'Total Quota' in line and current_hunt in hunts:
                    # Look for the quota number in this section
                    pass

                # "Total Choice 1 NNN NNN" line
                if 'Total Choice 1' in line:
                    nums = re.findall(r'\d+', line.replace(',', ''))
                    if len(nums) >= 2:
                        # First num after "Choice 1" = total apps, second = total drawn
                        hunts[current_hunt]['choice1_apps'] = int(nums[1]) if len(nums) > 1 else 0

                # Look for quota in format "11 LPP" or just the number after Total Quota
                # Try to get the # Drawn line with Res NonRes breakdown
                if line.startswith('# Drawn') and 'Hunt Code' not in line:
                    # Could be "# Drawn Hunt Code List Total Choice 1 365 11 11 0 8 1 0 0 1 1"
                    pass

                # Lines with "Total Choice 1 XXX YY" where XXX=apps, YY=drawn+quota
                # Actual format: "Total Choice 1 365 11 11 0 8 1 0 0 1 1"
                # The numbers after hunt code: apps, quota, drawn_total, balance, res, nr, youth_res, youth_nr, lo_u, lo_r
                if '# Drawn Hunt Code' in line and current_hunt:
                    # Next part has the draw data
                    pass

                # Simple quota extraction: look for standalone small number before "LPP"
                if current_hunt in hunts and hunts[current_hunt]['quota'] == 0:
                    q_match = re.match(r'^(\d{1,5})\s+LPP', line)
                    if q_match:
                        hunts[current_hunt]['quota'] = int(q_match.group(1))

    return hunts


def parse_co_draw_recap_simple(filepath):
    """Simpler approach: scan for 'Total Choice 1' lines per hunt code.
    The line format near each hunt is:
    'Total Choice 1 <apps> <drawn_or_quota> <drawn> <balance> <res> <nr> ...'
    """
    hunts = {}
    current_hunt = None
    hunt_code_re = re.compile(r'^([DE][EMF]\d{3}[A-Z0-9]{2}[ARMSP])\s*$')

    with pdfplumber.open(filepath) as pdf:
        total_pages = len(pdf.pages)
        for page_num, page in enumerate(pdf.pages):
            if page_num % 200 == 0:
                print(f"    Page {page_num}/{total_pages}...")
            text = page.extract_text()
            if not text:
                continue

            lines = text.split('\n')
            for i, line in enumerate(lines):
                line = line.strip()

                # Detect standalone hunt code line
                m = hunt_code_re.match(line)
                if m:
                    current_hunt = m.group(1)
                    if current_hunt not in hunts:
                        hunts[current_hunt] = {
                            'quota': 0, 'choice1_apps': 0,
                            'total_drawn': 0
                        }
                    continue

                if not current_hunt:
                    continue

                # Find "Total Choice 1 NNN NNN" pattern
                choice1_match = re.search(r'Total Choice 1\s+(\d[\d,]*)\s+(\d[\d,]*)', line)
                if choice1_match:
                    apps = int(choice1_match.group(1).replace(',', ''))
                    drawn_or_quota = int(choice1_match.group(2).replace(',', ''))
                    if hunts[current_hunt]['choice1_apps'] == 0:
                        hunts[current_hunt]['choice1_apps'] = apps
                        hunts[current_hunt]['total_drawn'] = drawn_or_quota

                # Extract quota: line starting with number followed by "LPP"
                q_match = re.match(r'^(\d{1,5})\s+LPP', line)
                if q_match and hunts[current_hunt]['quota'] == 0:
                    hunts[current_hunt]['quota'] = int(q_match.group(1))

    return hunts


def parse_co_drawn_out_at(filepath):
    """Parse CO drawn-out-at PDF for preference point info.
    Returns dict: compact_code -> {res_pts, nr_pts}
    """
    hunts = {}
    current_hunt = None
    hunt_code_re = re.compile(r'^([DE][EMF]\d{3}[A-Z0-9]{2}[ARMSP])\b')

    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            for line in text.split('\n'):
                line = line.strip()
                if not line:
                    continue

                m = hunt_code_re.match(line)
                if m:
                    current_hunt = m.group(1)
                    if current_hunt not in hunts:
                        hunts[current_hunt] = {'res_pts': None, 'nr_pts': None}

                if not current_hunt:
                    continue

                # "Drawn Out At X Pref Y Pref" or "Drawn Out At X Pref Points Y Pref Points"
                if 'Drawn Out At' in line:
                    pts_matches = re.findall(r'(\d+)\s+Pref', line)
                    if pts_matches:
                        # First is Res, second is NR
                        hunts[current_hunt]['res_pts'] = int(pts_matches[0])
                        if len(pts_matches) > 1:
                            hunts[current_hunt]['nr_pts'] = int(pts_matches[1])

    return hunts


def parse_co_harvest(filepath, species):
    """Parse CO harvest PDF (per-GMU format).
    Returns list of dicts: unit, total_harvest, hunters, success, days.
    """
    rows = []
    in_table = False

    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            if 'Harvest, Hunters' in text or 'Manners of Take' in text:
                in_table = True

            if not in_table:
                continue

            for line in text.split('\n'):
                line = line.strip()
                if not line:
                    continue
                if 'Unit' in line and ('Bulls' in line or 'Bucks' in line):
                    continue
                if 'Total' in line and ('Harvest' in line or 'Hunters' in line):
                    continue

                # Format: Unit Bucks/Bulls Does/Cows Fawns/Calves Harvest Hunters Success Days
                parts = line.split()
                if len(parts) < 7:
                    continue

                # First part is unit code (numeric, 1-3 digits)
                if not parts[0].isdigit():
                    continue

                try:
                    unit = parts[0].zfill(3)
                    # Last 4 meaningful columns: Harvest, Hunters, Success%, Days
                    # But format varies. For elk: Bulls Cows Calves Harvest Hunters Success Days
                    # Try to parse: skip harvest columns, find total harvest and hunters
                    nums = []
                    for p in parts[1:]:
                        p_clean = p.replace(',', '').replace('%', '')
                        try:
                            nums.append(float(p_clean))
                        except ValueError:
                            break

                    if len(nums) < 6:
                        continue

                    if species == 'ELK':
                        # bulls, cows, calves, total_harvest, hunters, success, days
                        total_harvest = int(nums[3])
                        hunters = int(nums[4])
                        success = float(nums[5])
                        days = int(nums[6]) if len(nums) > 6 else 0
                    else:  # deer
                        # bucks, does, fawns, total_harvest, hunters, success, days
                        total_harvest = int(nums[3])
                        hunters = int(nums[4])
                        success = float(nums[5])
                        days = int(nums[6]) if len(nums) > 6 else 0

                    rows.append({
                        'unit': unit,
                        'total_harvest': total_harvest,
                        'hunters': hunters,
                        'success_rate': success,
                        'days_hunted': days,
                    })
                except (ValueError, IndexError):
                    continue

    return rows


def parse_co_hunt_code(hunt_code):
    """Parse a CO dashed hunt code into components.
    D-E-003-O1-A → species=D, sex=E, unit=003, season=O1, weapon=A
    """
    parts = hunt_code.split('-')
    if len(parts) != 5:
        return None
    return {
        'species_char': parts[0],  # D=deer, E=elk
        'sex_char': parts[1],      # E=either, M=male, F=female
        'unit': parts[2],          # 3-digit unit
        'season': parts[3],        # O1=archery, E1=either, W1-W4=rifle, P2-P4=pref, L1=late
        'weapon_char': parts[4],   # A=archery, M=muzzleloader, R=rifle
    }


def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    cur.execute("SELECT state_id FROM states WHERE state_code='CO'")
    co_id = cur.fetchone()[0]

    cur.execute("SELECT species_id, species_code FROM species")
    species_map = {r[1]: r[0] for r in cur.fetchall()}

    # Create CO pools
    for pool_code, desc, pct, note in [
        ('RES', 'Resident pool', 80.0, '~80% of tags (hybrid draw)'),
        ('NR', 'Nonresident pool', 20.0, '~20% NR cap'),
    ]:
        cur.execute("""
            INSERT INTO pools (state_id, pool_code, description, allocation_pct, allocation_note)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (state_id, pool_code) DO NOTHING
        """, (co_id, pool_code, desc, pct, note))
    conn.commit()

    cur.execute("SELECT pool_id, pool_code FROM pools WHERE state_id = %s", (co_id,))
    pool_map = {r[1]: r[0] for r in cur.fetchall()}

    # ── Load hunt codes from proclamation CSV ────────────────────────────────
    proc_csv = os.path.join(BASE_DIR, 'CO/proclamations/2026/CO_hunt_dates_2026.csv')
    proc_rows = []
    if os.path.exists(proc_csv):
        with open(proc_csv) as f:
            reader = csv.DictReader(f)
            proc_rows = list(reader)

    # Filter out APPROX if requested (task says skip 122 O1-R codes flagged as DO_NOT_LOAD)
    # Actually task says skip O1-R codes - let me check
    load_rows = [r for r in proc_rows if r.get('load_status', '') != 'DO_NOT_LOAD']
    print(f"  Proclamation CSV: {len(proc_rows)} total, {len(load_rows)} to load")

    # ── Insert GMUs and Hunts ────────────────────────────────────────────────
    hunt_id_map = {}  # dashed hunt code -> hunt_id
    compact_to_hunt = {}  # compact code -> hunt_id

    weapon_map = {'A': 3, 'M': 4, 'R': 2, 'S': 6, 'P': 1}  # A=archery, M=muzz, R=rifle, S=shotgun, P=any
    sex_bag_map = {
        ('D', 'E'): 5,   # deer either sex
        ('D', 'M'): 16,  # buck
        ('D', 'F'): 18,  # doe
        ('E', 'E'): 5,   # elk either sex
        ('E', 'M'): 13,  # bull
        ('E', 'F'): 15,  # cow
    }

    gmu_count = 0
    for row in load_rows:
        hcode = row['hunt_code'].strip()
        parsed = parse_co_hunt_code(hcode)
        if not parsed:
            continue

        sp_code = 'ELK' if parsed['species_char'] == 'E' else 'MDR'
        species_id = species_map.get(sp_code, species_map['ELK'])
        weapon_type_id = weapon_map.get(parsed['weapon_char'], 1)
        bag_limit_id = sex_bag_map.get((parsed['species_char'], parsed['sex_char']), 5)

        unit = parsed['unit']
        gmu_code = unit
        gmu_name = f"Unit {unit}"
        gmu_sort_key = unit.zfill(5)

        cur.execute("""
            INSERT INTO gmus (state_id, gmu_code, gmu_name, gmu_sort_key)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (state_id, gmu_code) DO UPDATE SET gmu_name = EXCLUDED.gmu_name
            RETURNING gmu_id
        """, (co_id, gmu_code, gmu_name, gmu_sort_key))
        gmu_id = cur.fetchone()[0]
        gmu_count += 1

        # Season label from season code
        season_labels = {
            'O1': 'Archery', 'E1': 'Either Sex', 'W1': 'First Rifle',
            'W2': 'Second Rifle', 'W3': 'Third Rifle', 'W4': 'Fourth Rifle',
            'P2': 'Second Choice', 'P3': 'Third Choice', 'P4': 'Fourth Choice',
            'L1': 'Late', 'M1': 'Muzzleloader',
        }
        season_label = season_labels.get(parsed['season'], parsed['season'])

        bag_desc = row.get('bag_limit_description', '').strip()
        notes = row.get('notes', '').strip()
        hunt_notes = bag_desc
        if notes:
            hunt_notes = f"{hunt_notes}; {notes}" if hunt_notes else notes

        cur.execute("""
            INSERT INTO hunts (state_id, species_id, hunt_code, hunt_code_display,
                weapon_type_id, bag_limit_id, season_type, tag_type, is_active,
                unit_description, notes, season_label)
            VALUES (%s, %s, %s, %s, %s, %s, 'controlled', 'LE', 1, %s, %s, %s)
            ON CONFLICT (state_id, hunt_code) DO UPDATE SET
                weapon_type_id = EXCLUDED.weapon_type_id,
                bag_limit_id = EXCLUDED.bag_limit_id,
                notes = EXCLUDED.notes,
                season_label = EXCLUDED.season_label
            RETURNING hunt_id
        """, (co_id, species_id, hcode, hcode, weapon_type_id, bag_limit_id,
              gmu_name, hunt_notes or None, season_label))
        hunt_id = cur.fetchone()[0]
        hunt_id_map[hcode] = hunt_id
        compact_to_hunt[dashed_to_compact(hcode)] = hunt_id

        cur.execute("""
            INSERT INTO hunt_gmus (hunt_id, gmu_id) VALUES (%s, %s)
            ON CONFLICT (hunt_id, gmu_id) DO NOTHING
        """, (hunt_id, gmu_id))

    conn.commit()
    print(f"  Inserted {len(hunt_id_map)} hunts")

    # ── Parse draw recap PDFs ────────────────────────────────────────────────
    draw_count = 0
    draw_sources = [
        ('CO/raw_data/2024_elk_draw_recap.pdf', 2024),
        ('CO/raw_data/2024_deer_draw_recap.pdf', 2024),
        ('CO/raw_data/2025_elk_draw_recap.pdf', 2025),
        ('CO/raw_data/2025_deer_draw_recap.pdf', 2025),
    ]

    for relpath, year in draw_sources:
        filepath = os.path.join(BASE_DIR, relpath)
        if not os.path.exists(filepath):
            print(f"  SKIP (missing): {relpath}")
            continue

        print(f"  Parsing {os.path.basename(relpath)}...")
        hunts = parse_co_draw_recap_simple(filepath)
        print(f"  {os.path.basename(relpath)}: {len(hunts)} hunts parsed")

        matched = 0
        for compact_code, data in hunts.items():
            if compact_code not in compact_to_hunt:
                continue
            hunt_id = compact_to_hunt[compact_code]
            apps = data['choice1_apps']
            quota = data['quota']
            drawn = data['total_drawn']
            if apps == 0 and quota == 0:
                continue

            # Insert as combined pool (we don't have R/NR split from recap easily)
            cur.execute("""
                INSERT INTO draw_results_by_pool
                    (hunt_id, draw_year, pool_id, applications, tags_available, tags_awarded)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (hunt_id, draw_year, pool_id) DO UPDATE SET
                    applications = EXCLUDED.applications,
                    tags_available = EXCLUDED.tags_available,
                    tags_awarded = EXCLUDED.tags_awarded
            """, (hunt_id, year, pool_map['RES'], apps, quota, drawn))
            draw_count += 1
            matched += 1

        print(f"    Matched to hunts: {matched}")
        conn.commit()

    # ── Parse drawn-out-at for preference points ─────────────────────────────
    pref_count = 0
    pref_sources = [
        ('CO/raw_data/2024_elk_drawn_out_at.pdf', 2024),
        ('CO/raw_data/2024_deer_drawn_out_at.pdf', 2024),
        ('CO/raw_data/2025_elk_drawn_out_at.pdf', 2025),
        ('CO/raw_data/2025_deer_drawn_out_at.pdf', 2025),
    ]

    for relpath, year in pref_sources:
        filepath = os.path.join(BASE_DIR, relpath)
        if not os.path.exists(filepath):
            print(f"  SKIP (missing): {relpath}")
            continue

        hunts = parse_co_drawn_out_at(filepath)
        print(f"  {os.path.basename(relpath)}: {len(hunts)} hunts with pref data")

        for compact_code, data in hunts.items():
            if compact_code not in compact_to_hunt:
                continue
            hunt_id = compact_to_hunt[compact_code]
            res_pts = data.get('res_pts')
            if res_pts is not None:
                cur.execute("""
                    UPDATE draw_results_by_pool
                    SET min_pts_drawn = %s
                    WHERE hunt_id = %s AND draw_year = %s AND pool_id = %s
                      AND (min_pts_drawn IS NULL OR min_pts_drawn < %s)
                """, (res_pts, hunt_id, year, pool_map['RES'], res_pts))
                pref_count += 1

        conn.commit()

    print(f"  Updated {pref_count} draw results with pref point data")

    # ── Parse harvest data ───────────────────────────────────────────────────
    harvest_count = 0
    harvest_sources = [
        ('CO/raw_data/2024_elk_harvest_statelib.pdf', 2024, 'ELK'),
        ('CO/raw_data/2024_deer_harvest_statelib.pdf', 2024, 'MDR'),
        ('CO/raw_data/2023_elk_harvest.pdf', 2023, 'ELK'),
        ('CO/raw_data/2023_deer_harvest.pdf', 2023, 'MDR'),
    ]

    # Build unit -> hunt_ids mapping for harvest data
    unit_to_hunts = defaultdict(list)
    for hcode, hid in hunt_id_map.items():
        parsed = parse_co_hunt_code(hcode)
        if parsed:
            unit_to_hunts[parsed['unit']].append((hcode, hid, parsed))

    for relpath, year, sp_code in harvest_sources:
        filepath = os.path.join(BASE_DIR, relpath)
        if not os.path.exists(filepath):
            print(f"  SKIP harvest (missing): {relpath}")
            continue

        rows = parse_co_harvest(filepath, sp_code)
        print(f"  {os.path.basename(relpath)}: {len(rows)} harvest rows by unit")

        for r in rows:
            unit = r['unit']
            if unit not in unit_to_hunts:
                continue
            # Find the best matching hunt for this species + unit
            # Pick the first hunt of matching species
            sp_char = 'E' if sp_code == 'ELK' else 'D'
            matching = [(hc, hid) for hc, hid, p in unit_to_hunts[unit] if p['species_char'] == sp_char]
            if not matching:
                continue
            # Use first matching hunt as representative
            hunt_id = matching[0][1]
            cur.execute("""
                INSERT INTO harvest_stats
                    (hunt_id, harvest_year, success_rate, days_hunted,
                     licenses_sold, harvest_count)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (hunt_id, harvest_year, access_type) DO UPDATE SET
                    success_rate = EXCLUDED.success_rate,
                    days_hunted = EXCLUDED.days_hunted,
                    licenses_sold = EXCLUDED.licenses_sold,
                    harvest_count = EXCLUDED.harvest_count
            """, (hunt_id, year, r['success_rate'], r['days_hunted'],
                  r['hunters'], r['total_harvest']))
            harvest_count += 1

    conn.commit()
    print(f"  Inserted {harvest_count} harvest rows")

    # ── Load hunt dates ──────────────────────────────────────────────────────
    dates_loaded = 0
    dates_unmatched = 0
    for row in load_rows:
        hc = row['hunt_code'].strip()
        if hc in hunt_id_map:
            hunt_id = hunt_id_map[hc]
            start = row.get('open_date', '').strip()
            end = row.get('close_date', '').strip()
            if not start or not end:
                continue
            notes = row.get('notes', '').strip()
            cur.execute("""
                INSERT INTO hunt_dates (hunt_id, season_year, start_date, end_date, notes)
                VALUES (%s, 2026, %s, %s, %s)
                ON CONFLICT (hunt_id, season_year) DO UPDATE SET
                    start_date = EXCLUDED.start_date,
                    end_date = EXCLUDED.end_date,
                    notes = EXCLUDED.notes
            """, (hunt_id, start, end, notes))
            dates_loaded += 1
        else:
            dates_unmatched += 1

    conn.commit()

    # ── Summary ──────────────────────────────────────────────────────────────
    print("\n=== CO LOAD SUMMARY ===")
    cur.execute("SELECT COUNT(*) FROM hunts WHERE state_id = %s", (co_id,))
    print(f"  Hunts:        {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(*) FROM gmus WHERE state_id = %s", (co_id,))
    print(f"  GMUs:         {cur.fetchone()[0]}")
    cur.execute("""SELECT COUNT(*) FROM draw_results_by_pool dr
                   JOIN hunts h ON h.hunt_id = dr.hunt_id WHERE h.state_id = %s""", (co_id,))
    print(f"  Draw results: {cur.fetchone()[0]}")
    cur.execute("""SELECT COUNT(*) FROM harvest_stats hs
                   JOIN hunts h ON h.hunt_id = hs.hunt_id WHERE h.state_id = %s""", (co_id,))
    print(f"  Harvest rows: {cur.fetchone()[0]}")
    cur.execute("""SELECT COUNT(*) FROM hunt_dates hd
                   JOIN hunts h ON h.hunt_id = hd.hunt_id WHERE h.state_id = %s""", (co_id,))
    print(f"  Hunt dates:   {cur.fetchone()[0]}")
    print(f"  Dates loaded: {dates_loaded}, unmatched: {dates_unmatched}")

    conn.close()
    print("\nCO load complete.")


if __name__ == '__main__':
    main()
