#!/usr/bin/env python3
"""
Idaho data loader: hunts, GMUs, harvest stats, hunt dates.

Sources:
  - ID/raw_data/elk_controlled_harvest_2023.csv
  - ID/raw_data/elk_controlled_harvest_2024.csv
  - ID/raw_data/deer_controlled_harvest_2023.csv
  - ID/raw_data/deer_controlled_harvest_2024.csv
  - ID/proclamations/2026/ID_hunt_dates_2026.csv

Note: ID has no draw odds data yet (pure lottery, no points).
"""

import os
import re
import csv
import psycopg2

BASE_DIR = "/Users/openclaw/Documents/GraysonsDrawOdds"
DB_CONFIG = {
    'host': 'localhost', 'port': 5432,
    'dbname': 'draws', 'user': 'draws', 'password': 'drawspass'
}

# TakeMethod → weapon_type_id
WEAPON_MAP = {
    'Any Weapon': 1,          # ANY
    'Archery': 3,             # ARCHERY
    'Muzzleloader': 4,        # MUZZ
    'Short-Range Weapons': 5, # SRW
    'Archery or Muzzleloader': 3,  # ARCHERY (closest fit)
}


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


def gmu_sort_key(area_code):
    """Zero-pad numeric part, append letter suffix."""
    m = re.match(r'^(\d+)(.*)', str(area_code))
    if m:
        return m.group(1).zfill(5) + m.group(2)
    return str(area_code).zfill(5)


def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    # Get state_id
    cur.execute("SELECT state_id FROM states WHERE state_code='ID'")
    id_state_id = cur.fetchone()[0]

    # Species map
    cur.execute("SELECT species_id, species_code FROM species")
    species_db = {r[1]: r[0] for r in cur.fetchall()}

    # Ensure pools exist for ID (even though no draw data yet)
    for pool_code, desc, pct, note in [
        ('RES', 'Resident pool', 90.0, '90% open random'),
        ('NR', 'Nonresident pool', 10.0, '10% NR reserved'),
    ]:
        cur.execute("""
            INSERT INTO pools (state_id, pool_code, description, allocation_pct, allocation_note)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (state_id, pool_code) DO NOTHING
        """, (id_state_id, pool_code, desc, pct, note))
    conn.commit()

    # Source files: (filepath, species_code, species_context)
    sources = [
        ('ID/raw_data/elk_controlled_harvest_2023.csv', 'ELK', 'ELK'),
        ('ID/raw_data/elk_controlled_harvest_2024.csv', 'ELK', 'ELK'),
        ('ID/raw_data/deer_controlled_harvest_2023.csv', 'MDR', 'MDR'),
        ('ID/raw_data/deer_controlled_harvest_2024.csv', 'MDR', 'MDR'),
    ]

    total_hunts = 0
    total_gmus = 0
    total_harvest = 0

    for relpath, sp_code, sp_context in sources:
        filepath = os.path.join(BASE_DIR, relpath)
        if not os.path.exists(filepath):
            print(f"  SKIP (missing): {relpath}")
            continue

        species_id = species_db[sp_code]

        with open(filepath) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        print(f"\n  {relpath}: {len(rows)} rows")

        for row in rows:
            hunt_code = str(row['Hunt#']).strip()
            take_method = row['TakeMethod'].strip()
            area = str(row['Area']).strip()
            year = safe_int(row.get('Year'))

            weapon_type_id = WEAPON_MAP.get(take_method, 1)

            # Infer sex from Antlered/Antlerless columns
            antlered = safe_int(row.get('Antlered'))
            antlerless = safe_int(row.get('Antlerless'))
            harvest = safe_int(row.get('Harvest'))

            if sp_code == 'ELK':
                if antlerless and antlerless > 0 and (antlered is None or antlered == 0):
                    bag_limit_id = 15  # COW
                elif antlered and antlered > 0 and (antlerless is None or antlerless == 0):
                    bag_limit_id = 13  # BULL
                else:
                    bag_limit_id = 5   # ES (either sex or mixed)
            else:
                if antlerless and antlerless > 0 and (antlered is None or antlered == 0):
                    bag_limit_id = 18  # DOE
                elif antlered and antlered > 0 and (antlerless is None or antlerless == 0):
                    bag_limit_id = 16  # BUCK
                else:
                    bag_limit_id = 5   # ES

            # Insert GMU with species_context
            cur.execute("""
                INSERT INTO gmus (state_id, gmu_code, gmu_name, gmu_sort_key, species_context)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (state_id, gmu_code) DO NOTHING
                RETURNING gmu_id
            """, (id_state_id, area, area, gmu_sort_key(area), sp_context))
            r = cur.fetchone()
            if r:
                gmu_id = r[0]
                total_gmus += 1
            else:
                cur.execute("SELECT gmu_id FROM gmus WHERE state_id=%s AND gmu_code=%s",
                            (id_state_id, area))
                gmu_id = cur.fetchone()[0]

            # Notes for special weapon types
            notes = None
            if take_method == 'Archery or Muzzleloader':
                notes = 'Archery or Muzzleloader'

            # Insert hunt
            cur.execute("""
                INSERT INTO hunts (state_id, species_id, hunt_code, hunt_code_display,
                    weapon_type_id, bag_limit_id, season_type, tag_type, is_active,
                    unit_description, notes)
                VALUES (%s, %s, %s, %s, %s, %s, 'controlled', 'LE', 1, %s, %s)
                ON CONFLICT (state_id, hunt_code) DO UPDATE SET
                    weapon_type_id = EXCLUDED.weapon_type_id,
                    bag_limit_id = EXCLUDED.bag_limit_id,
                    unit_description = EXCLUDED.unit_description,
                    notes = EXCLUDED.notes
                RETURNING hunt_id
            """, (id_state_id, species_id, hunt_code, hunt_code,
                  weapon_type_id, bag_limit_id, area, notes))
            hunt_id = cur.fetchone()[0]
            total_hunts += 1

            # Link hunt to GMU
            cur.execute("""
                INSERT INTO hunt_gmus (hunt_id, gmu_id) VALUES (%s, %s)
                ON CONFLICT (hunt_id, gmu_id) DO NOTHING
            """, (hunt_id, gmu_id))

            # Insert harvest stats
            hunters = safe_int(row.get('Hunters'))
            success_pct = safe_float(row.get('Success%'))
            days = safe_float(row.get('Days'))
            success_rate = round(success_pct / 100.0, 4) if success_pct is not None else None

            if hunters is not None and year is not None:
                cur.execute("""
                    INSERT INTO harvest_stats
                        (hunt_id, harvest_year, access_type, success_rate,
                         days_hunted, harvest_count)
                    VALUES (%s, %s, 'ALL', %s, %s, %s)
                    ON CONFLICT (hunt_id, harvest_year, access_type) DO UPDATE SET
                        success_rate = EXCLUDED.success_rate,
                        days_hunted = EXCLUDED.days_hunted,
                        harvest_count = EXCLUDED.harvest_count
                """, (hunt_id, year, success_rate, days, harvest))
                total_harvest += 1

        conn.commit()

    # Load hunt dates
    dates_csv = os.path.join(BASE_DIR, 'ID/proclamations/2026/ID_hunt_dates_2026.csv')
    dates_loaded = 0
    dates_unmatched = 0
    if os.path.exists(dates_csv):
        cur.execute("SELECT hunt_code, hunt_id FROM hunts WHERE state_id = %s", (id_state_id,))
        hunt_map = {r[0]: r[1] for r in cur.fetchall()}
        with open(dates_csv) as f:
            reader = csv.DictReader(f)
            for row in reader:
                hc = row['hunt_code'].strip()
                if hc in hunt_map:
                    cur.execute("""
                        INSERT INTO hunt_dates (hunt_id, season_year, start_date, end_date, notes)
                        VALUES (%s, 2026, %s, %s, %s)
                        ON CONFLICT (hunt_id, season_year) DO UPDATE SET
                            start_date = EXCLUDED.start_date,
                            end_date = EXCLUDED.end_date,
                            notes = EXCLUDED.notes
                    """, (hunt_map[hc], row['open_date'], row['close_date'],
                          row.get('notes', '')))
                    dates_loaded += 1
                else:
                    dates_unmatched += 1
        conn.commit()

    # Print counts
    print("\n=== ID LOAD SUMMARY ===")
    cur.execute("SELECT COUNT(*) FROM hunts WHERE state_id = %s", (id_state_id,))
    print(f"  Hunts:         {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(*) FROM gmus WHERE state_id = %s", (id_state_id,))
    print(f"  GMUs:          {cur.fetchone()[0]}")
    cur.execute("""SELECT COUNT(*) FROM harvest_stats hs
                   JOIN hunts h ON h.hunt_id = hs.hunt_id WHERE h.state_id = %s""", (id_state_id,))
    print(f"  Harvest stats: {cur.fetchone()[0]}")
    cur.execute("""SELECT COUNT(*) FROM hunt_dates hd
                   JOIN hunts h ON h.hunt_id = hd.hunt_id WHERE h.state_id = %s""", (id_state_id,))
    print(f"  Hunt dates:    {cur.fetchone()[0]}")
    print(f"  Dates loaded:  {dates_loaded}, unmatched: {dates_unmatched}")

    conn.close()
    print("\nID load complete.")


if __name__ == '__main__':
    main()
