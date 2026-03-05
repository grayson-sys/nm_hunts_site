"""
Migrate NM data from nm_hunts.db (SQLite) into PostgreSQL draws database.
Run from repo root or app/scripts/ — it finds nm_hunts.db relative to the repo root.
"""

import os
import re
import sqlite3
import psycopg2

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SQLITE_PATH = os.path.join(REPO_ROOT, "nm_hunts.db")

PG_HOST = os.environ.get("DRAWS_DB_HOST", "localhost")
PG_PORT = os.environ.get("DRAWS_DB_PORT", "5432")
PG_DB = os.environ.get("DRAWS_DB_NAME", "draws")
PG_USER = os.environ.get("DRAWS_DB_USER", "draws")
PG_PASS = os.environ.get("DRAWS_DB_PASS", "drawspass")

# NM species_code mapping: SQLite code -> PG code
# NM uses 'DER' for all deer — PG uses 'MDR' (mule deer).
# NM deer are mule deer (NM has separate WTD species).
NM_SPECIES_MAP = {
    "ELK": "ELK",
    "DER": "MDR",  # NM "Deer" = mule deer in the multi-state schema
    "ANT": "ANT",
    "ORX": "ORX",
    "IBX": "IBX",
    "BHS": "BHS",
    "BBY": "BBY",
}


def gmu_sort_key(code: str) -> str:
    """Generate sort key: left-pad numeric portion to 5 chars, keep suffix."""
    m = re.match(r"^(\d+)(.*)", code)
    if m:
        return m.group(1).zfill(5) + m.group(2)
    return code


def main():
    print(f"SQLite: {SQLITE_PATH}")
    lite = sqlite3.connect(SQLITE_PATH)
    lite.row_factory = sqlite3.Row

    pg = psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASS
    )
    pg.autocommit = False
    cur = pg.cursor()

    # Get NM state_id
    cur.execute("SELECT state_id FROM states WHERE state_code = 'NM'")
    nm_state_id = cur.fetchone()[0]
    print(f"NM state_id = {nm_state_id}")

    # -- Species mapping (SQLite species_id -> PG species_id) --
    species_map = {}  # sqlite species_id -> pg species_id
    for row in lite.execute("SELECT species_id, species_code FROM species"):
        sq_id = row["species_id"]
        pg_code = NM_SPECIES_MAP.get(row["species_code"], row["species_code"])
        cur.execute("SELECT species_id FROM species WHERE species_code = %s", (pg_code,))
        r = cur.fetchone()
        if r:
            species_map[sq_id] = r[0]
            print(f"  Species {row['species_code']} -> PG {pg_code} (id={r[0]})")
        else:
            print(f"  WARNING: species {pg_code} not found in PG, skipping")
    print(f"Mapped {len(species_map)} species")

    # -- Bag limits mapping (SQLite bag_limit_id -> PG bag_limit_id) --
    bag_map = {}  # sqlite bag_limit_id -> pg bag_limit_id
    for row in lite.execute("SELECT bag_limit_id, bag_code, label, plain_definition FROM bag_limits"):
        sq_id = row["bag_limit_id"]
        cur.execute(
            """INSERT INTO bag_limits (bag_code, label, plain_definition)
               VALUES (%s, %s, %s)
               ON CONFLICT (bag_code) DO NOTHING
               RETURNING bag_limit_id""",
            (row["bag_code"], row["label"], row["plain_definition"]),
        )
        r = cur.fetchone()
        if r:
            bag_map[sq_id] = r[0]
        else:
            cur.execute("SELECT bag_limit_id FROM bag_limits WHERE bag_code = %s", (row["bag_code"],))
            bag_map[sq_id] = cur.fetchone()[0]
    print(f"Mapped {len(bag_map)} bag limits")

    # -- Pools mapping (pool_code -> pool_id in PG for NM) --
    pool_map = {}  # pool_code -> pg pool_id
    cur.execute("SELECT pool_id, pool_code FROM pools WHERE state_id = %s", (nm_state_id,))
    for r in cur.fetchall():
        pool_map[r[1]] = r[0]
    print(f"NM pools: {pool_map}")

    # -- Hunts (SQLite hunt_id -> PG hunt_id) --
    hunt_map = {}  # sqlite hunt_id -> pg hunt_id
    sqlite_hunts = list(lite.execute(
        "SELECT hunt_id, hunt_code, species_id, bag_limit_id, unit_description, is_active FROM hunts"
    ))
    print(f"Migrating {len(sqlite_hunts)} hunts...")

    for row in sqlite_hunts:
        sq_hid = row["hunt_id"]
        pg_species_id = species_map.get(row["species_id"])
        if pg_species_id is None:
            continue
        pg_bag_id = bag_map.get(row["bag_limit_id"]) if row["bag_limit_id"] else None

        # Determine weapon_type_id from NM hunt_code pattern: X-{digit}-Y
        # digit: 1=rifle, 2=archery, 3=muzzleloader
        weapon_id = None
        parts = row["hunt_code"].split("-")
        if len(parts) >= 2:
            digit = parts[1]
            weapon_map = {"1": 2, "2": 3, "3": 4}  # RIFLE=2, ARCHERY=3, MUZZ=4
            weapon_id = weapon_map.get(digit)

        cur.execute(
            """INSERT INTO hunts (state_id, species_id, hunt_code, weapon_type_id,
                                  bag_limit_id, unit_description, is_active, tag_type)
               VALUES (%s, %s, %s, %s, %s, %s, %s, 'DRAW')
               ON CONFLICT (state_id, hunt_code) DO NOTHING
               RETURNING hunt_id""",
            (nm_state_id, pg_species_id, row["hunt_code"], weapon_id,
             pg_bag_id, row["unit_description"], row["is_active"]),
        )
        r = cur.fetchone()
        if r:
            hunt_map[sq_hid] = r[0]
        else:
            cur.execute(
                "SELECT hunt_id FROM hunts WHERE state_id = %s AND hunt_code = %s",
                (nm_state_id, row["hunt_code"]),
            )
            hunt_map[sq_hid] = cur.fetchone()[0]

    print(f"Mapped {len(hunt_map)} hunts")

    # -- Draw results (legacy NM table) --
    dr_rows = list(lite.execute("SELECT * FROM draw_results"))
    print(f"Migrating {len(dr_rows)} draw_results rows...")

    dr_count = 0
    drp_count = 0
    for row in dr_rows:
        pg_hid = hunt_map.get(row["hunt_id"])
        if pg_hid is None:
            continue

        # Legacy draw_results table
        cur.execute(
            """INSERT INTO draw_results
               (hunt_id, draw_year,
                resident_applications, nonresident_applications, outfitter_applications,
                licenses_total, resident_licenses, nonresident_licenses, outfitter_licenses,
                resident_results, nonresident_results, outfitter_results)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (hunt_id, draw_year) DO NOTHING""",
            (pg_hid, row["draw_year"],
             row["resident_applications"], row["nonresident_applications"], row["outfitter_applications"],
             row["licenses_total"], row["resident_licenses"], row["nonresident_licenses"], row["outfitter_licenses"],
             row["resident_results"], row["nonresident_results"], row["outfitter_results"]),
        )
        dr_count += 1

        # Normalized draw_results_by_pool
        pool_data = [
            ("RES", row["resident_applications"], row["resident_licenses"], row["resident_results"]),
            ("NR", row["nonresident_applications"], row["nonresident_licenses"], row["nonresident_results"]),
            ("OUTF", row["outfitter_applications"], row["outfitter_licenses"], row["outfitter_results"]),
        ]
        for pool_code, apps, tags_avail, tags_awarded in pool_data:
            pid = pool_map.get(pool_code)
            if pid is None:
                continue
            cur.execute(
                """INSERT INTO draw_results_by_pool
                   (hunt_id, draw_year, pool_id, applications, tags_available, tags_awarded)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT (hunt_id, draw_year, pool_id) DO NOTHING""",
                (pg_hid, row["draw_year"], pid, apps, tags_avail, tags_awarded),
            )
            drp_count += 1

    print(f"Inserted {dr_count} legacy draw_results, {drp_count} draw_results_by_pool")

    # -- Harvest stats --
    hs_rows = list(lite.execute("SELECT * FROM harvest_stats"))
    print(f"Migrating {len(hs_rows)} harvest_stats rows...")
    hs_count = 0
    for row in hs_rows:
        pg_hid = hunt_map.get(row["hunt_id"])
        if pg_hid is None:
            continue
        cur.execute(
            """INSERT INTO harvest_stats
               (hunt_id, harvest_year, access_type, success_rate, satisfaction, days_hunted, licenses_sold)
               VALUES (%s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (hunt_id, harvest_year, access_type) DO NOTHING""",
            (pg_hid, row["harvest_year"], row["access_type"],
             row["success_rate"], row["satisfaction"], row["days_hunted"], row["licenses_sold"]),
        )
        hs_count += 1
    print(f"Inserted {hs_count} harvest_stats")

    # -- Hunt dates --
    hd_rows = list(lite.execute("SELECT * FROM hunt_dates"))
    print(f"Migrating {len(hd_rows)} hunt_dates rows...")
    hd_count = 0
    for row in hd_rows:
        pg_hid = hunt_map.get(row["hunt_id"])
        if pg_hid is None:
            continue
        cur.execute(
            """INSERT INTO hunt_dates
               (hunt_id, season_year, start_date, end_date, hunt_name, notes)
               VALUES (%s, %s, %s, %s, %s, %s)
               ON CONFLICT (hunt_id, season_year) DO NOTHING""",
            (pg_hid, row["season_year"], row["start_date"], row["end_date"],
             row["hunt_name"], row["notes"]),
        )
        hd_count += 1
    print(f"Inserted {hd_count} hunt_dates")

    # -- GMUs (NM gmus table is empty, but we can extract from unit_description) --
    # For NM we'll parse GMU numbers from unit_description and insert them
    gmu_set = set()
    for row in lite.execute("SELECT unit_description FROM hunts WHERE unit_description IS NOT NULL"):
        desc = row["unit_description"]
        # Extract numbers like "Unit 51", "Units 2, 7, 9, 10"
        numbers = re.findall(r'\b(\d+[A-Za-z]?)\b', desc)
        for n in numbers:
            # Skip numbers that are clearly not GMUs (like "youth only" ages)
            if n in desc and int(re.match(r'\d+', n).group()) <= 59:
                gmu_set.add(n)

    gmu_map = {}  # gmu_code -> pg gmu_id
    for code in sorted(gmu_set, key=lambda c: gmu_sort_key(c)):
        cur.execute(
            """INSERT INTO gmus (state_id, gmu_code, gmu_sort_key)
               VALUES (%s, %s, %s)
               ON CONFLICT (state_id, gmu_code) DO NOTHING
               RETURNING gmu_id""",
            (nm_state_id, code, gmu_sort_key(code)),
        )
        r = cur.fetchone()
        if r:
            gmu_map[code] = r[0]
        else:
            cur.execute(
                "SELECT gmu_id FROM gmus WHERE state_id = %s AND gmu_code = %s",
                (nm_state_id, code),
            )
            gmu_map[code] = cur.fetchone()[0]
    print(f"Inserted {len(gmu_map)} GMUs for NM")

    # -- Hunt-GMU links (parse from unit_description) --
    hg_count = 0
    for row in lite.execute("SELECT hunt_id, unit_description FROM hunts WHERE unit_description IS NOT NULL"):
        pg_hid = hunt_map.get(row["hunt_id"])
        if pg_hid is None:
            continue
        desc = row["unit_description"]
        numbers = re.findall(r'\b(\d+[A-Za-z]?)\b', desc)
        for n in numbers:
            if n in gmu_map:
                cur.execute(
                    """INSERT INTO hunt_gmus (hunt_id, gmu_id)
                       VALUES (%s, %s)
                       ON CONFLICT (hunt_id, gmu_id) DO NOTHING""",
                    (pg_hid, gmu_map[n]),
                )
                hg_count += 1
    print(f"Inserted {hg_count} hunt_gmu links")

    pg.commit()
    print("\n=== Migration complete ===")

    # Verify counts
    cur.execute("SELECT count(*) FROM hunts WHERE state_id = %s", (nm_state_id,))
    print(f"PG hunts (NM): {cur.fetchone()[0]}  (SQLite: {len(sqlite_hunts)})")
    cur.execute("SELECT count(*) FROM draw_results")
    print(f"PG draw_results: {cur.fetchone()[0]}  (SQLite: {len(dr_rows)})")
    cur.execute("SELECT count(*) FROM draw_results_by_pool")
    print(f"PG draw_results_by_pool: {cur.fetchone()[0]}")
    cur.execute("SELECT count(*) FROM harvest_stats")
    print(f"PG harvest_stats: {cur.fetchone()[0]}  (SQLite: {len(hs_rows)})")
    cur.execute("SELECT count(*) FROM hunt_dates")
    print(f"PG hunt_dates: {cur.fetchone()[0]}  (SQLite: {len(hd_rows)})")
    cur.execute("SELECT count(*) FROM gmus WHERE state_id = %s", (nm_state_id,))
    print(f"PG gmus (NM): {cur.fetchone()[0]}")

    cur.close()
    pg.close()
    lite.close()


if __name__ == "__main__":
    main()
