#!/usr/bin/env python3
"""
Nevada data loader: hunts, GMUs, draw results, harvest stats, hunt dates.

Source: NV/raw_data/2024-Nevada-Big-Game-Hunt-Data.xlsx (Sheet: '2024 Hunt Summary')
        NV/proclamations/2026/NV_hunt_dates_2026.csv
"""

import os
import re
import csv
import openpyxl
import psycopg2

BASE_DIR = "/Users/openclaw/Documents/GraysonsDrawOdds"
DB_CONFIG = {
    'host': 'localhost', 'port': 5432,
    'dbname': 'draws', 'user': 'draws', 'password': 'drawspass'
}

# NV weapon code mapping
WEAPON_MAP = {
    'ALW': 1,   # ANY
    'AR': 3,    # ARCHERY
    'M': 4,     # MUZZ
    'WR': 2,    # RIFLE (weapon restricted = centerfire rifle)
    'SWR': 5,   # SRW (short-range weapon, Idaho-specific but reuse)
    'SWR-Prmtve': 4,  # Muzzleloader (primitive SRW)
}

# NV weapon code short labels for hunt_code construction
WEAPON_LABEL = {
    'ALW': 'ALW',
    'AR': 'AR',
    'M': 'MZ',
    'WR': 'WR',
    'SWR': 'SWR',
    'SWR-Prmtve': 'SWRP',
}

# Species mapping
SPECIES_MAP = {
    'Mule Deer': 'MDR',
    'Elk': 'ELK',
}

# Infer sex restriction from hunt name
def parse_sex(hunt_name, species_code):
    name = hunt_name.lower()
    if 'antlerless' in name:
        return 15 if species_code == 'ELK' else 18  # COW / DOE
    if 'spike' in name:
        return 14  # SPIKE
    if 'antlered' in name:
        return 13 if species_code == 'ELK' else 16  # BULL / BUCK
    if 'either sex' in name:
        return 5  # ES
    if 'junior' in name:
        return 5  # ES (junior hunts are typically either sex)
    return 5  # default either sex


def gmu_sort_key(unit_group):
    """Zero-pad first numeric segment to 5 chars."""
    m = re.match(r'(\d+)', str(unit_group))
    if m:
        return m.group(1).zfill(5) + str(unit_group)[m.end():]
    return str(unit_group).zfill(5)


def safe_int(val):
    if val is None or val == '' or val == 'N/A':
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def safe_float(val):
    if val is None or val == '' or val == 'N/A':
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    # Get state_id
    cur.execute("SELECT state_id FROM states WHERE state_code='NV'")
    nv_state_id = cur.fetchone()[0]

    # Species map
    cur.execute("SELECT species_id, species_code FROM species")
    species_db = {r[1]: r[0] for r in cur.fetchall()}

    # Ensure pools exist for NV
    for pool_code, desc, pct, note in [
        ('RES', 'Resident pool', 90.0, '~90% of tags'),
        ('NR', 'Nonresident pool', 10.0, '~10% of tags'),
    ]:
        cur.execute("""
            INSERT INTO pools (state_id, pool_code, description, allocation_pct, allocation_note)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (state_id, pool_code) DO NOTHING
        """, (nv_state_id, pool_code, desc, pct, note))

    cur.execute("SELECT pool_id, pool_code FROM pools WHERE state_id = %s", (nv_state_id,))
    pool_map = {r[1]: r[0] for r in cur.fetchall()}
    conn.commit()

    # Load Excel
    xlsx_path = os.path.join(BASE_DIR, 'NV/raw_data/2024-Nevada-Big-Game-Hunt-Data.xlsx')
    wb = openpyxl.load_workbook(xlsx_path, read_only=True)
    ws = wb['2024 Hunt Summary']

    # Read headers
    headers = None
    rows = []
    for i, row in enumerate(ws.iter_rows(values_only=True), 1):
        if i == 1:
            headers = [str(c).strip() if c else '' for c in row]
            continue
        rows.append(row)
    wb.close()

    # Map column indices
    col = {h: i for i, h in enumerate(headers)}

    total_hunts = 0
    total_gmus = 0
    total_draw = 0
    total_harvest = 0

    for row in rows:
        species_raw = row[col['Species']]
        if species_raw not in SPECIES_MAP:
            continue
        sp_code = SPECIES_MAP[species_raw]
        species_id = species_db[sp_code]

        hunt_name = str(row[col['Hunt']]).strip()
        weapon_raw = str(row[col['Weapon']]).strip()
        unit_group = str(row[col['Unit Group']]).strip()
        residency = str(row[col['Residency']]).strip()
        year = safe_int(row[col['year']]) or 2024

        weapon_type_id = WEAPON_MAP.get(weapon_raw, 1)
        weapon_label = WEAPON_LABEL.get(weapon_raw, weapon_raw)
        bag_limit_id = parse_sex(hunt_name, sp_code)

        # Build hunt_code: unit_group + weapon + season_type
        # Include hunt type prefix for special hunts
        hunt_prefix = ''
        name_lower = hunt_name.lower()
        if 'dream' in name_lower:
            hunt_prefix = 'DRM-'
        elif 'silver state' in name_lower:
            hunt_prefix = 'SS-'
        elif 'heritage' in name_lower:
            hunt_prefix = 'WH-'
        elif 'piw' in name_lower:
            hunt_prefix = 'PIW-'
        elif 'guided' in name_lower:
            hunt_prefix = 'GD-'
        elif 'junior' in name_lower:
            hunt_prefix = 'JR-'
        elif 'depredation' in name_lower and 'emergency' in name_lower:
            hunt_prefix = 'EDEP-'
        elif 'depredation' in name_lower:
            hunt_prefix = 'DEP-'
        elif 'incentive' in name_lower:
            hunt_prefix = 'INC-'
        elif 'private lands' in name_lower:
            hunt_prefix = 'PLH-'
        elif 'landowner' in name_lower:
            hunt_prefix = 'LDC-'

        # Sex suffix
        sex_suffix = ''
        if 'antlerless' in name_lower:
            sex_suffix = '-AL'
        elif 'spike' in name_lower:
            sex_suffix = '-SPK'

        hunt_code = f"{hunt_prefix}{unit_group}-{weapon_label}{sex_suffix}"

        # Pool code
        pool_code = 'RES' if residency == 'Res' else 'NR'
        pool_id = pool_map[pool_code]

        # Season type
        season_type = 'controlled'
        tag_type = 'LE'
        if hunt_prefix in ('DRM-', 'SS-', 'WH-', 'PIW-'):
            season_type = 'special'

        # Insert GMU
        cur.execute("""
            INSERT INTO gmus (state_id, gmu_code, gmu_name, gmu_sort_key)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (state_id, gmu_code) DO NOTHING
            RETURNING gmu_id
        """, (nv_state_id, unit_group, unit_group, gmu_sort_key(unit_group)))
        r = cur.fetchone()
        if r:
            gmu_id = r[0]
            total_gmus += 1
        else:
            cur.execute("SELECT gmu_id FROM gmus WHERE state_id=%s AND gmu_code=%s",
                        (nv_state_id, unit_group))
            gmu_id = cur.fetchone()[0]

        # Insert hunt
        cur.execute("""
            INSERT INTO hunts (state_id, species_id, hunt_code, hunt_code_display,
                weapon_type_id, bag_limit_id, season_type, tag_type, is_active,
                unit_description, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1, %s, %s)
            ON CONFLICT (state_id, hunt_code) DO UPDATE SET
                weapon_type_id = EXCLUDED.weapon_type_id,
                bag_limit_id = EXCLUDED.bag_limit_id,
                unit_description = EXCLUDED.unit_description
            RETURNING hunt_id
        """, (nv_state_id, species_id, hunt_code, hunt_code,
              weapon_type_id, bag_limit_id, season_type, tag_type,
              unit_group, hunt_name))
        hunt_id = cur.fetchone()[0]
        total_hunts += 1

        # Link hunt to GMU
        cur.execute("""
            INSERT INTO hunt_gmus (hunt_id, gmu_id) VALUES (%s, %s)
            ON CONFLICT (hunt_id, gmu_id) DO NOTHING
        """, (hunt_id, gmu_id))

        # Draw results
        apps = safe_int(row[col['Unique\nApps']])
        demand = safe_int(row[col['Demand']])
        quota = safe_int(row[col['2024\nQuota']])
        draw_rate = safe_float(row[col['Draw\nRate']])

        if apps is not None and apps > 0:
            cur.execute("""
                INSERT INTO draw_results_by_pool
                    (hunt_id, draw_year, pool_id, applications, tags_available, tags_awarded)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (hunt_id, draw_year, pool_id) DO UPDATE SET
                    applications = EXCLUDED.applications,
                    tags_available = EXCLUDED.tags_available,
                    tags_awarded = EXCLUDED.tags_awarded
            """, (hunt_id, year, pool_id, apps, quota, demand))
            total_draw += 1

        # Harvest stats
        hunters_afield = safe_int(row[col['Hunters\nAfield']])
        successful = safe_int(row[col['Successful\nHunters']])
        hunter_success = safe_float(row[col['Hunter\nSuccess']])
        satisfaction = safe_float(row[col['Hunter\nSatisfaction']])
        hunt_days = safe_float(row[col['Hunt\nDays']])

        if hunters_afield is not None and hunters_afield > 0:
            cur.execute("""
                INSERT INTO harvest_stats
                    (hunt_id, harvest_year, access_type, success_rate, satisfaction,
                     days_hunted, harvest_count)
                VALUES (%s, %s, 'ALL', %s, %s, %s, %s)
                ON CONFLICT (hunt_id, harvest_year, access_type) DO UPDATE SET
                    success_rate = EXCLUDED.success_rate,
                    satisfaction = EXCLUDED.satisfaction,
                    days_hunted = EXCLUDED.days_hunted,
                    harvest_count = EXCLUDED.harvest_count
            """, (hunt_id, year, hunter_success, satisfaction, hunt_days, successful))
            total_harvest += 1

    conn.commit()

    # Load hunt dates
    dates_csv = os.path.join(BASE_DIR, 'NV/proclamations/2026/NV_hunt_dates_2026.csv')
    dates_loaded = 0
    dates_unmatched = 0
    if os.path.exists(dates_csv):
        cur.execute("SELECT hunt_code, hunt_id FROM hunts WHERE state_id = %s", (nv_state_id,))
        hunt_map = {r[0]: r[1] for r in cur.fetchall()}
        # NV proclamation CSV hunt_codes are unit-level, not full hunt_codes
        # We need to match by prefix
        with open(dates_csv) as f:
            reader = csv.DictReader(f)
            for row in reader:
                hc = row['hunt_code'].strip()
                # Try exact match first
                if hc in hunt_map:
                    cur.execute("""
                        INSERT INTO hunt_dates (hunt_id, season_year, start_date, end_date, notes)
                        VALUES (%s, 2026, %s, %s, %s)
                        ON CONFLICT (hunt_id, season_year) DO UPDATE SET
                            start_date = EXCLUDED.start_date, end_date = EXCLUDED.end_date,
                            notes = EXCLUDED.notes
                    """, (hunt_map[hc], row['open_date'], row['close_date'],
                          row.get('notes', '')))
                    dates_loaded += 1
                else:
                    # Try matching all hunts that start with this unit code
                    matched = False
                    for full_code, hunt_id in hunt_map.items():
                        # Match: hunt_code starts with "hc-" (unit group prefix)
                        if full_code.startswith(hc + '-') or full_code.split('-')[0] == hc \
                           or (len(full_code.split('-')) > 1 and full_code.split('-')[-2] == hc):
                            # Check if prefix portion after stripping special prefixes matches
                            parts = full_code.split('-')
                            # Find the unit group in the hunt code
                            unit_in_code = None
                            for p in parts:
                                if re.match(r'^\d', p):
                                    unit_in_code = p
                                    break
                            if unit_in_code == hc:
                                cur.execute("""
                                    INSERT INTO hunt_dates (hunt_id, season_year, start_date, end_date, notes)
                                    VALUES (%s, 2026, %s, %s, %s)
                                    ON CONFLICT (hunt_id, season_year) DO UPDATE SET
                                        start_date = EXCLUDED.start_date, end_date = EXCLUDED.end_date,
                                        notes = EXCLUDED.notes
                                """, (hunt_id, row['open_date'], row['close_date'],
                                      row.get('notes', '')))
                                dates_loaded += 1
                                matched = True
                    if not matched:
                        dates_unmatched += 1
        conn.commit()

    # Print counts
    print("\n=== NV LOAD SUMMARY ===")
    cur.execute("SELECT COUNT(*) FROM hunts WHERE state_id = %s", (nv_state_id,))
    print(f"  Hunts:         {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(*) FROM gmus WHERE state_id = %s", (nv_state_id,))
    print(f"  GMUs:          {cur.fetchone()[0]}")
    cur.execute("""SELECT COUNT(*) FROM draw_results_by_pool dr
                   JOIN hunts h ON h.hunt_id = dr.hunt_id WHERE h.state_id = %s""", (nv_state_id,))
    print(f"  Draw results:  {cur.fetchone()[0]}")
    cur.execute("""SELECT COUNT(*) FROM harvest_stats hs
                   JOIN hunts h ON h.hunt_id = hs.hunt_id WHERE h.state_id = %s""", (nv_state_id,))
    print(f"  Harvest stats: {cur.fetchone()[0]}")
    cur.execute("""SELECT COUNT(*) FROM hunt_dates hd
                   JOIN hunts h ON h.hunt_id = hd.hunt_id WHERE h.state_id = %s""", (nv_state_id,))
    print(f"  Hunt dates:    {cur.fetchone()[0]}")
    print(f"  Dates loaded:  {dates_loaded}, unmatched: {dates_unmatched}")

    conn.close()
    print("\nNV load complete.")


if __name__ == '__main__':
    main()
