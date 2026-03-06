#!/usr/bin/env python3
"""
Arizona data loader: hunts, GMUs, draw results, harvest stats, hunt dates.

Sources:
  - 2024/2025 Elk/Pronghorn and Fall draw reports (Bonus, 1-2, 3-4-5 passes)
  - 2024/2025 Bonus Point Reports
  - 2024/2025 Elk and Deer Harvest Summaries
  - AZ/proclamations/2026/AZ_hunt_dates_2026.csv
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


def parse_az_draw_report(filepath):
    """Parse AZ draw report (any pass).
    Returns dict: hunt_code -> {authorized, res_apps, nr_apps, res_drawn, nr_drawn, total_issued, ...}
    """
    hunts = {}
    current_hunt = None

    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            for line in text.split('\n'):
                line = line.strip()
                if not line:
                    continue
                # Skip headers
                if 'Arizona' in line or 'Draw Report' in line or 'Authorized' in line or \
                   'Hunt Number' in line or 'Permits' in line and 'Available' in line:
                    continue

                parts = line.split()
                if not parts:
                    continue

                # Hunt number line: just "2001 0 0 0" (hunt_code and 3 zeros)
                if len(parts) <= 4 and parts[0].isdigit() and len(parts[0]) == 4:
                    current_hunt = parts[0]
                    if current_hunt not in hunts:
                        hunts[current_hunt] = {
                            'authorized': 0, 'res_apps_1st': 0, 'nr_apps_1st': 0,
                            'res_drawn': 0, 'nr_drawn': 0, 'total_issued': 0,
                        }
                    continue

                if not current_hunt:
                    continue

                # "All" row: authorized, available, 1st_apps, 2nd_apps, combined, 1st_drawn, 2nd_drawn, ..., grand_total, unissued
                if parts[0] == 'All':
                    try:
                        nums = [int(p) for p in parts[1:] if p.isdigit() or (p.replace(',', '').isdigit())]
                        nums = [int(p.replace(',', '')) for p in parts[1:]]
                    except ValueError:
                        continue
                    if len(nums) >= 8:
                        hunts[current_hunt]['authorized'] = nums[0]
                        hunts[current_hunt]['total_issued'] = nums[-2] if len(nums) >= 2 else 0
                    continue

                # "Res" row
                if parts[0] == 'Res' and not parts[0].startswith('Res%'):
                    try:
                        nums = [int(p.replace(',', '')) for p in parts[1:]]
                    except ValueError:
                        continue
                    if len(nums) >= 5:
                        hunts[current_hunt]['res_apps_1st'] = nums[2]  # 1st choice apps
                        hunts[current_hunt]['res_drawn'] = nums[-2] if len(nums) >= 2 else 0
                    continue

                # "NonRes" row
                if parts[0] == 'NonRes' and not parts[0].startswith('NonRes%'):
                    try:
                        nums = [int(p.replace(',', '')) for p in parts[1:]]
                    except ValueError:
                        continue
                    if len(nums) >= 5:
                        hunts[current_hunt]['nr_apps_1st'] = nums[2]  # 1st choice apps
                        hunts[current_hunt]['nr_drawn'] = nums[-2] if len(nums) >= 2 else 0
                    continue

    return hunts


def parse_az_bonus_point_report(filepath):
    """Parse AZ bonus point report for min_pts_drawn per hunt.
    Returns dict: hunt_code -> {min_pts_drawn, max_pts_held}.
    """
    hunt_pts = defaultdict(lambda: {'min_pts_drawn': None, 'max_pts_held': 0})

    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            for line in text.split('\n'):
                line = line.strip()
                if not line or 'Arizona' in line or 'Bonus Point' in line or \
                   'Hunt' in line or 'Number' in line or 'Group' in line:
                    continue

                parts = line.split()
                if len(parts) < 10:
                    continue

                # Format: hunt_code bonus_pts total res nr total res nr total res nr total res nr total res nr
                if not parts[0].isdigit() or len(parts[0]) != 4:
                    continue
                if not parts[1].isdigit():
                    continue

                hunt_code = parts[0]
                pts = int(parts[1])

                # Track max points held
                if pts > hunt_pts[hunt_code]['max_pts_held']:
                    hunt_pts[hunt_code]['max_pts_held'] = pts

                # Check if any permits were issued at this point level
                # "Permits Issued Bonus Pass" starts around column index 10-12
                # "Permits Issued Bonus + 1-2 Pass" around 13-15
                try:
                    # The last group of 3 numbers = "Permits Issued Bonus + 1-2 Pass" Total, Res, NonRes
                    # Check if total permits issued (at any pass) > 0
                    nums = [int(p) for p in parts[2:] if p.isdigit()]
                    # Last 3 are bonus+1-2 pass issued (total, res, nr)
                    if len(nums) >= 6:
                        issued_total = nums[-3]  # Total issued at bonus+1-2 pass
                        if issued_total > 0:
                            if hunt_pts[hunt_code]['min_pts_drawn'] is None or pts < hunt_pts[hunt_code]['min_pts_drawn']:
                                hunt_pts[hunt_code]['min_pts_drawn'] = pts
                except (ValueError, IndexError):
                    continue

    return dict(hunt_pts)


def parse_az_harvest_summary(filepath, species):
    """Parse AZ harvest summary PDF.
    Returns list of dicts with hunt_code, hunters, total_harvest, success_rate, days.
    """
    rows = []
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            for line in text.split('\n'):
                line = line.strip()
                if not line or 'HARVEST' in line.upper() or 'Unit' in line or \
                   'Permits' in line or 'Hunt No' in line or 'Total,' in line or \
                   'Authorized' in line:
                    continue

                # Each data row starts with Unit name, then hunt number
                # Format: unit_name hunt_no auth 1st_apps issued hunters days [harvest cols] total %success ...
                # Find the 4-digit hunt number in the line
                m = re.search(r'\b(\d{4})\b', line)
                if not m:
                    continue
                hunt_code = m.group(1)
                # Get all numbers after the hunt code
                after_hunt = line[m.end():]
                nums = re.findall(r'[\d.]+%?', after_hunt)
                if len(nums) < 8:
                    continue

                try:
                    authorized = int(nums[0])
                    apps_1st = int(nums[1])
                    issued = int(nums[2])
                    hunters = int(nums[3])
                    days = int(nums[4])

                    # Find total harvest and success rate
                    total_harvest = None
                    success_rate = None

                    # Try with % sign first
                    for i, n in enumerate(nums[5:], 5):
                        if '%' in n:
                            success_str = n.replace('%', '')
                            success_rate = float(success_str)
                            total_harvest = int(nums[i - 1])
                            break

                    # If no % found, use positional approach:
                    # For elk: 5=bull, 6=spike, 7=cow, 8=calf, 9=total, 10=success
                    # For deer: 5+ harvest cols, then total, then success
                    if success_rate is None and len(nums) >= 12:
                        # Find total by looking for a number preceded by harvest columns
                        # Success is 0-100 and follows total
                        for i in range(8, min(14, len(nums))):
                            val = float(nums[i].replace('%', ''))
                            prev = int(nums[i - 1].replace('%', ''))
                            if 0 <= val <= 100 and prev > 0:
                                success_rate = val
                                total_harvest = prev
                                break

                    if total_harvest is not None and success_rate is not None:
                        rows.append({
                            'hunt_code': hunt_code,
                            'authorized': authorized,
                            'hunters': hunters,
                            'total_harvest': total_harvest,
                            'success_rate': success_rate,
                            'days_hunted': days,
                        })
                except (ValueError, IndexError):
                    continue

    return rows


def infer_az_species(hunt_code):
    """Infer species from AZ hunt code number."""
    num = int(hunt_code)
    if 1000 <= num < 2000:
        return 'MDR'  # deer (fall draw)
    elif 2000 <= num < 4000:
        return 'ELK'  # elk (elk/pronghorn draw)
    elif 4000 <= num < 5000:
        return 'ANT'  # pronghorn
    return 'ELK'  # default


def infer_az_bag_limit(hunt_code, description=''):
    """Infer bag_limit_id for AZ hunts."""
    desc = description.upper()
    if 'ANTLERLESS' in desc or 'COW' in desc:
        return 15  # COW (antlerless elk)
    if 'BULL' in desc:
        return 13  # BULL
    # From hunt code patterns (AZ specific)
    num = int(hunt_code)
    if 1000 <= num < 2000:
        return 5   # ES (either sex deer - most AZ deer hunts)
    return 5  # ES default


def infer_az_weapon(hunt_code, notes=''):
    """Infer weapon_type_id for AZ hunts."""
    notes_lower = (notes or '').lower()
    num = int(hunt_code)
    # AZ archery hunts: typically 3126-3199 range, or notes mention archery
    if 'archery' in notes_lower:
        return 3  # ARCHERY
    if 'muzzleloader' in notes_lower:
        return 4  # MUZZ
    return 1  # ANY


def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    cur.execute("SELECT state_id FROM states WHERE state_code='AZ'")
    az_id = cur.fetchone()[0]

    cur.execute("SELECT species_id, species_code FROM species")
    species_map = {r[1]: r[0] for r in cur.fetchall()}

    # Create AZ pools
    for pool_code, desc, pct, note in [
        ('RES', 'Resident pool', 90.0, '~90% of tags'),
        ('NR', 'Nonresident pool', 10.0, '~10% of tags'),
    ]:
        cur.execute("""
            INSERT INTO pools (state_id, pool_code, description, allocation_pct, allocation_note)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (state_id, pool_code) DO NOTHING
        """, (az_id, pool_code, desc, pct, note))
    conn.commit()

    cur.execute("SELECT pool_id, pool_code FROM pools WHERE state_id = %s", (az_id,))
    pool_map = {r[1]: r[0] for r in cur.fetchall()}

    # ── Parse draw reports (use 1-2 Pass as primary for applicant counts) ────
    draw_data = {}  # hunt_code -> {authorized, res_apps, nr_apps, res_drawn, nr_drawn}

    # Parse 2024 and 2025 draw reports
    draw_sources = []
    for year in [2024, 2025]:
        for group in ['Elk-Pronghorn', 'Fall']:
            # Find matching files
            prefix = f'{year}-{group}' if group == 'Elk-Pronghorn' else f'{year}-{group}'
            for pass_name in ['1-2-Pass', 'Bonus-Pass', '3-4-5-Pass']:
                # Match actual filenames
                for fn in os.listdir(os.path.join(BASE_DIR, 'AZ/raw_data')):
                    if str(year) in fn and pass_name.replace('-Pass', '') in fn.replace('-', ' ') and \
                       group.split('-')[0].lower() in fn.lower():
                        draw_sources.append((f'AZ/raw_data/{fn}', year, group, pass_name))

    # Actually let me be more explicit about the files
    draw_file_sets = {
        2024: {
            'elk': [
                'AZ/raw_data/2024-Elk-Pronghorn-Draw-Report-1-2-Pass.pdf',
            ],
            'fall': [
                'AZ/raw_data/2024-Fall-Draw-Report-1-2-Pass.pdf',
            ],
        },
        2025: {
            'elk': [
                'AZ/raw_data/2025-Elk-Pronghorn-Draw-Report-1-2-Pass.pdf',
            ],
            'fall': [
                'AZ/raw_data/2025-Fall-Draw-1-2-Pass.pdf',
            ],
        },
    }

    all_draw = {}  # (hunt_code, year) -> data

    for year, groups in draw_file_sets.items():
        for group, files in groups.items():
            for relpath in files:
                filepath = os.path.join(BASE_DIR, relpath)
                if not os.path.exists(filepath):
                    print(f"  SKIP (missing): {relpath}")
                    continue
                hunts = parse_az_draw_report(filepath)
                print(f"  {os.path.basename(relpath)}: {len(hunts)} hunts parsed")
                for hc, data in hunts.items():
                    if data['authorized'] == 0 and data['res_apps_1st'] == 0 and data['nr_apps_1st'] == 0:
                        continue
                    key = (hc, year)
                    all_draw[key] = data

    print(f"\n  Total draw data entries: {len(all_draw)}")

    # ── Parse bonus point reports ────────────────────────────────────────────
    bp_data = {}
    for fn in ['2024-Elk-Pronghorn-Bonus-Point-Report.pdf', '2025-Elk-Pronghorn-Bonus-Point-Report.pdf',
               '2024-Fall-Bonus-Point-Report.pdf', '2025-Fall-Bonus-Point-Report.pdf']:
        filepath = os.path.join(BASE_DIR, 'AZ/raw_data', fn)
        if not os.path.exists(filepath):
            print(f"  SKIP (missing): {fn}")
            continue
        pts = parse_az_bonus_point_report(filepath)
        print(f"  {fn}: {len(pts)} hunts with bonus point data")
        bp_data.update(pts)

    # ── Collect all unique hunt codes ────────────────────────────────────────
    proc_csv = os.path.join(BASE_DIR, 'AZ/proclamations/2026/AZ_hunt_dates_2026.csv')
    proc_hunts = {}
    if os.path.exists(proc_csv):
        with open(proc_csv) as f:
            reader = csv.DictReader(f)
            for row in reader:
                proc_hunts[row['hunt_code'].strip()] = row

    draw_hunt_codes = set(hc for hc, yr in all_draw.keys())
    all_hunt_codes = draw_hunt_codes | set(proc_hunts.keys())
    print(f"  Total unique AZ hunt codes: {len(all_hunt_codes)}")

    # ── Insert GMUs and Hunts ────────────────────────────────────────────────
    hunt_id_map = {}

    for hcode in sorted(all_hunt_codes):
        sp_code = infer_az_species(hcode)
        species_id = species_map.get(sp_code, species_map.get('ELK'))

        bag_desc = ''
        notes = ''
        if hcode in proc_hunts:
            bag_desc = proc_hunts[hcode].get('bag_limit_description', '')
            notes = proc_hunts[hcode].get('notes', '')

        bag_limit_id = infer_az_bag_limit(hcode, bag_desc)
        weapon_type_id = infer_az_weapon(hcode, notes)

        # GMU: Use hunt code prefix for unit grouping
        # AZ units are in the hunt description from harvest data, but for now use hunt code
        num = int(hcode)
        if 1000 <= num < 2000:
            gmu_code = f"D{num - 1000:03d}"
            gmu_name = f"Deer Hunt {hcode}"
        elif 2000 <= num < 3000:
            gmu_code = f"E{num - 2000:03d}"
            gmu_name = f"Elk Hunt {hcode}"
        elif 3000 <= num < 4000:
            gmu_code = f"E{num - 3000:03d}"
            gmu_name = f"Elk Hunt {hcode}"
        else:
            gmu_code = hcode
            gmu_name = f"Hunt {hcode}"

        gmu_sort_key = hcode.zfill(5)

        cur.execute("""
            INSERT INTO gmus (state_id, gmu_code, gmu_name, gmu_sort_key)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (state_id, gmu_code) DO UPDATE SET gmu_name = EXCLUDED.gmu_name
            RETURNING gmu_id
        """, (az_id, gmu_code, gmu_name, gmu_sort_key))
        gmu_id = cur.fetchone()[0]

        season_type = 'controlled'
        tag_type = 'LE'

        hunt_notes = bag_desc
        if notes:
            hunt_notes = f"{hunt_notes}; {notes}" if hunt_notes else notes

        cur.execute("""
            INSERT INTO hunts (state_id, species_id, hunt_code, hunt_code_display,
                weapon_type_id, bag_limit_id, season_type, tag_type, is_active,
                unit_description, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1, %s, %s)
            ON CONFLICT (state_id, hunt_code) DO UPDATE SET
                weapon_type_id = EXCLUDED.weapon_type_id,
                bag_limit_id = EXCLUDED.bag_limit_id,
                notes = EXCLUDED.notes
            RETURNING hunt_id
        """, (az_id, species_id, hcode, hcode, weapon_type_id, bag_limit_id,
              season_type, tag_type, gmu_name, hunt_notes or None))
        hunt_id = cur.fetchone()[0]
        hunt_id_map[hcode] = hunt_id

        cur.execute("""
            INSERT INTO hunt_gmus (hunt_id, gmu_id) VALUES (%s, %s)
            ON CONFLICT (hunt_id, gmu_id) DO NOTHING
        """, (hunt_id, gmu_id))

    conn.commit()
    print(f"  Inserted {len(hunt_id_map)} hunts")

    # ── Insert draw results ──────────────────────────────────────────────────
    draw_count = 0
    for (hcode, year), data in all_draw.items():
        if hcode not in hunt_id_map:
            continue
        hunt_id = hunt_id_map[hcode]

        bp = bp_data.get(hcode, {})
        min_pts = bp.get('min_pts_drawn')
        max_pts = bp.get('max_pts_held')

        # Resident pool
        if data['res_apps_1st'] > 0 or data['res_drawn'] > 0:
            cur.execute("""
                INSERT INTO draw_results_by_pool
                    (hunt_id, draw_year, pool_id, applications, tags_available,
                     tags_awarded, min_pts_drawn, max_pts_held)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (hunt_id, draw_year, pool_id) DO UPDATE SET
                    applications = EXCLUDED.applications,
                    tags_available = EXCLUDED.tags_available,
                    tags_awarded = EXCLUDED.tags_awarded,
                    min_pts_drawn = COALESCE(EXCLUDED.min_pts_drawn, draw_results_by_pool.min_pts_drawn),
                    max_pts_held = COALESCE(EXCLUDED.max_pts_held, draw_results_by_pool.max_pts_held)
            """, (hunt_id, year, pool_map['RES'], data['res_apps_1st'],
                  data['authorized'], data['res_drawn'], min_pts, max_pts))
            draw_count += 1

        # Nonresident pool
        if data['nr_apps_1st'] > 0 or data['nr_drawn'] > 0:
            cur.execute("""
                INSERT INTO draw_results_by_pool
                    (hunt_id, draw_year, pool_id, applications, tags_available,
                     tags_awarded, min_pts_drawn, max_pts_held)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (hunt_id, draw_year, pool_id) DO UPDATE SET
                    applications = EXCLUDED.applications,
                    tags_available = EXCLUDED.tags_available,
                    tags_awarded = EXCLUDED.tags_awarded,
                    min_pts_drawn = COALESCE(EXCLUDED.min_pts_drawn, draw_results_by_pool.min_pts_drawn),
                    max_pts_held = COALESCE(EXCLUDED.max_pts_held, draw_results_by_pool.max_pts_held)
            """, (hunt_id, year, pool_map['NR'], data['nr_apps_1st'],
                  data['authorized'], data['nr_drawn'], min_pts, max_pts))
            draw_count += 1

    conn.commit()
    print(f"  Inserted {draw_count} draw result rows")

    # ── Load harvest data ────────────────────────────────────────────────────
    harvest_count = 0
    harvest_sources = [
        ('AZ/raw_data/2024-AZ-Elk-Harvest-Summary.pdf', 2024, 'ELK'),
        ('AZ/raw_data/2025-AZ-Elk-Harvest-Summary.pdf', 2025, 'ELK'),
        ('AZ/raw_data/2024-AZ-Deer-Harvest-Summary.pdf', 2024, 'MDR'),
        ('AZ/raw_data/2025-AZ-Deer-Harvest-Summary.pdf', 2025, 'MDR'),
    ]

    for relpath, year, sp_code in harvest_sources:
        filepath = os.path.join(BASE_DIR, relpath)
        if not os.path.exists(filepath):
            print(f"  SKIP harvest (missing): {relpath}")
            continue

        rows = parse_az_harvest_summary(filepath, sp_code)
        print(f"  {os.path.basename(relpath)}: {len(rows)} harvest rows parsed")

        for r in rows:
            if r['hunt_code'] not in hunt_id_map:
                continue
            hunt_id = hunt_id_map[r['hunt_code']]
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
    if os.path.exists(proc_csv):
        with open(proc_csv) as f:
            reader = csv.DictReader(f)
            for row in reader:
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
    print("\n=== AZ LOAD SUMMARY ===")
    cur.execute("SELECT COUNT(*) FROM hunts WHERE state_id = %s", (az_id,))
    print(f"  Hunts:        {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(*) FROM gmus WHERE state_id = %s", (az_id,))
    print(f"  GMUs:         {cur.fetchone()[0]}")
    cur.execute("""SELECT COUNT(*) FROM draw_results_by_pool dr
                   JOIN hunts h ON h.hunt_id = dr.hunt_id WHERE h.state_id = %s""", (az_id,))
    print(f"  Draw results: {cur.fetchone()[0]}")
    cur.execute("""SELECT COUNT(*) FROM harvest_stats hs
                   JOIN hunts h ON h.hunt_id = hs.hunt_id WHERE h.state_id = %s""", (az_id,))
    print(f"  Harvest rows: {cur.fetchone()[0]}")
    cur.execute("""SELECT COUNT(*) FROM hunt_dates hd
                   JOIN hunts h ON h.hunt_id = hd.hunt_id WHERE h.state_id = %s""", (az_id,))
    print(f"  Hunt dates:   {cur.fetchone()[0]}")
    print(f"  Dates loaded: {dates_loaded}, unmatched: {dates_unmatched}")

    conn.close()
    print("\nAZ load complete.")


if __name__ == '__main__':
    main()
