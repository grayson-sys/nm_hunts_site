#!/usr/bin/env python3
"""
Montana draw statistics loader.

MT FWP uses a different hunt code system in their draw stats
(numeric B-license numbers: 1001, 2001...) vs the proclamation
(E-100-00, D-100-00 style). This loader ingests the draw stat CSV
files as native hunt codes and loads draw_results_by_pool.

CSV columns (after 2-row header):
  Hunt, Area, Drawing, Permits,
  1st Choice Applied, Drew, %,
  2nd Choice Applied, Drew, %,
  Residents Applied, Drew, %,
  NonResidents Applied, Drew, %,
  Total Drew, Year

Pool mapping:
  RES pool → Residents Applied / Drew
  NR  pool → NonResidents Applied / Drew

Files expected in MT/raw_data/:
  MT_elk_2024_1st.csv, MT_elk_2024_2nd.csv
  MT_elk_2025_1st.csv, MT_elk_2025_2nd.csv
  MT_deer_2024_1st.csv, MT_deer_2024_2nd.csv
  MT_deer_2025_1st.csv, MT_deer_2025_2nd.csv
"""
import csv
import os
import psycopg2

BASE_DIR = "/Users/openclaw/Documents/GraysonsDrawOdds"
DB_CONFIG = {
    'host': 'localhost', 'port': 5432,
    'dbname': 'draws', 'user': 'draws', 'password': 'drawspass'
}

FILES = [
    # (filename, species_code)
    ('MT_elk_2024_1st.csv',  'ELK'),
    ('MT_elk_2024_2nd.csv',  'ELK'),
    ('MT_elk_2025_1st.csv',  'ELK'),
    ('MT_elk_2025_2nd.csv',  'ELK'),
    ('MT_deer_2024_1st.csv', 'MDR'),
    ('MT_deer_2024_2nd.csv', 'MDR'),
    ('MT_deer_2025_1st.csv', 'MDR'),
    ('MT_deer_2025_2nd.csv', 'MDR'),
]

def safe_int(v):
    try:
        return int(str(v).strip().replace(',', '').replace('%', ''))
    except:
        return 0


def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    # State / lookup IDs
    cur.execute("SELECT state_id FROM states WHERE state_code='MT'")
    mt_id = cur.fetchone()[0]

    cur.execute("SELECT species_id, species_code FROM species")
    species_map = {r[1]: r[0] for r in cur.fetchall()}

    cur.execute("SELECT weapon_type_id FROM weapon_types WHERE weapon_code='ANY' LIMIT 1")
    row = cur.fetchone()
    weapon_any = row[0] if row else 1

    cur.execute("SELECT bag_limit_id FROM bag_limits WHERE bag_code='ES' LIMIT 1")
    row = cur.fetchone()
    bag_es = row[0] if row else 5

    # Ensure MT has RES and NR pools
    for pool_code, desc, pct in [('RES', 'Resident pool', 90.0), ('NR', 'Nonresident pool', 10.0)]:
        cur.execute("""
            INSERT INTO pools (state_id, pool_code, description, allocation_pct)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (state_id, pool_code) DO NOTHING
        """, (mt_id, pool_code, desc, pct))

    cur.execute("SELECT pool_id, pool_code FROM pools WHERE state_id=%s", (mt_id,))
    pool_map = {r[1]: r[0] for r in cur.fetchall()}
    conn.commit()
    print(f"MT pools: {pool_map}")

    # GMU cache: area_code -> gmu_id (for draw-stat areas)
    # We store these with a 'DS-' prefix to distinguish from proclamation HDs
    gmu_cache = {}

    def get_or_create_gmu(area):
        if area in gmu_cache:
            return gmu_cache[area]
        gmu_code = f"DS-{area}"   # "DS" = draw stats district code
        gmu_sort = area.zfill(8)
        gmu_name = f"Draw District {area}"
        cur.execute("""
            INSERT INTO gmus (state_id, gmu_code, gmu_name, gmu_sort_key)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (state_id, gmu_code) DO UPDATE SET gmu_name=EXCLUDED.gmu_name
            RETURNING gmu_id
        """, (mt_id, gmu_code, gmu_name, gmu_sort))
        gmu_id = cur.fetchone()[0]
        gmu_cache[area] = gmu_id
        return gmu_id

    # Hunt cache: hunt_code -> hunt_id
    hunt_cache = {}

    def get_or_create_hunt(hunt_code, area, species_code):
        if hunt_code in hunt_cache:
            return hunt_cache[hunt_code]
        sp_id = species_map.get(species_code, species_map.get('ELK'))
        gmu_id = get_or_create_gmu(area)
        display = f"B License {hunt_code} (Area {area})"
        unit_desc = f"Draw District {area}"
        cur.execute("""
            INSERT INTO hunts (state_id, species_id, hunt_code, hunt_code_display,
                weapon_type_id, bag_limit_id, season_type, tag_type, is_active,
                unit_description, season_label)
            VALUES (%s, %s, %s, %s, %s, %s, 'controlled', 'B', 1, %s, 'B License')
            ON CONFLICT (state_id, hunt_code) DO UPDATE SET
                hunt_code_display=EXCLUDED.hunt_code_display
            RETURNING hunt_id
        """, (mt_id, sp_id, hunt_code, display, weapon_any, bag_es, unit_desc))
        hunt_id = cur.fetchone()[0]
        # Link to GMU
        cur.execute("""
            INSERT INTO hunt_gmus (hunt_id, gmu_id) VALUES (%s, %s)
            ON CONFLICT DO NOTHING
        """, (hunt_id, gmu_id))
        hunt_cache[hunt_code] = hunt_id
        return hunt_id

    total_rows = 0
    total_files = 0

    for filename, species_code in FILES:
        filepath = os.path.join(BASE_DIR, 'MT/raw_data', filename)
        if not os.path.exists(filepath):
            print(f"  MISSING: {filename}")
            continue

        rows_loaded = 0
        with open(filepath, encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            next(reader)  # skip mega-header row 1
            next(reader)  # skip column header row 2
            for row in reader:
                if len(row) < 17:
                    continue
                hunt_code = row[0].strip().strip('"')
                area      = row[1].strip().strip('"')
                # drawing = row[2]  -- "1st" or "2nd" (not stored separately here)
                permits   = safe_int(row[3])
                # 1st choice: cols 4,5,6
                # 2nd choice: cols 7,8,9
                res_apps  = safe_int(row[10])
                res_drew  = safe_int(row[11])
                nr_apps   = safe_int(row[13])
                nr_drew   = safe_int(row[14])
                year      = safe_int(row[17]) if len(row) > 17 else safe_int(row[-1])

                if not hunt_code or not area or year == 0:
                    continue

                hunt_id = get_or_create_hunt(hunt_code, area, species_code)

                # Resident pool
                if res_apps > 0:
                    cur.execute("""
                        INSERT INTO draw_results_by_pool
                            (hunt_id, draw_year, pool_id, applications, tags_awarded, tags_available)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (hunt_id, draw_year, pool_id) DO UPDATE SET
                            applications=EXCLUDED.applications,
                            tags_awarded=EXCLUDED.tags_awarded,
                            tags_available=EXCLUDED.tags_available
                    """, (hunt_id, year, pool_map['RES'], res_apps, res_drew, permits))

                # NR pool
                if nr_apps > 0:
                    cur.execute("""
                        INSERT INTO draw_results_by_pool
                            (hunt_id, draw_year, pool_id, applications, tags_awarded, tags_available)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (hunt_id, draw_year, pool_id) DO UPDATE SET
                            applications=EXCLUDED.applications,
                            tags_awarded=EXCLUDED.tags_awarded,
                            tags_available=EXCLUDED.tags_available
                    """, (hunt_id, year, pool_map['NR'], nr_apps, nr_drew, permits))

                rows_loaded += 1

        conn.commit()
        total_rows += rows_loaded
        total_files += 1
        print(f"  ✓ {filename}: {rows_loaded} hunts loaded")

    # Final summary
    print(f"\n=== MT Draw Stats Load Summary ===")
    print(f"  Files processed: {total_files}")
    print(f"  Hunt rows processed: {total_rows}")

    cur.execute("""
        SELECT COUNT(*) FROM draw_results_by_pool drp
        JOIN hunts h ON drp.hunt_id=h.hunt_id
        WHERE h.state_id=%s
    """, (mt_id,))
    print(f"  Total MT draw results in DB: {cur.fetchone()[0]}")

    cur.execute("""
        SELECT COUNT(*) FROM hunts WHERE state_id=%s AND hunt_code ~ '^[0-9]'
    """, (mt_id,))
    print(f"  New draw-stat hunts created: {cur.fetchone()[0]}")

    cur.execute("""
        SELECT COUNT(*) FROM gmus WHERE state_id=%s AND gmu_code LIKE 'DS-%%'
    """, (mt_id,))
    print(f"  New draw-stat GMUs created: {cur.fetchone()[0]}")

    conn.close()
    print("\nDone.")


if __name__ == '__main__':
    main()
