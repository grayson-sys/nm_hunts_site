#!/usr/bin/env python

import sqlite3
from pathlib import Path

import pandas as pd


DB_PATH = Path(__file__).parent / "nm_hunts.db"
DATA_DIR = Path(__file__).parent / "data"

HUNTS_CSV = DATA_DIR / "hunts_table_2025_units_species.csv"
DRAW_CSV = DATA_DIR / "draw_results_2025_clean.csv"
DATES_CSV = DATA_DIR / "hunt_dates_2024_2026_combined.csv"
HARVEST_CSV = DATA_DIR / "harvest_reports_public_with_licenses_2016_2024_cleaned.csv"


def load_hunts(cur, species_map, bag_map):
    print(f"Loading hunts from {HUNTS_CSV}...")

    df = pd.read_csv(HUNTS_CSV)
    print("Hunts CSV columns:", list(df.columns))

    required = {"hunt_code", "unit_description", "bag", "species"}
    missing_cols = required - set(df.columns)
    if missing_cols:
        raise SystemExit(f"Hunts CSV missing columns: {missing_cols}")

    # Map human readable species names to canonical species codes
    species_name_to_code = {
        "Elk": "ELK",
        "Deer": "DER",
        "Mule deer": "DER",
        "White-tailed deer": "DER",
        "Pronghorn": "ANT",
        "Antelope": "ANT",
        "Oryx": "ORX",
        "Ibex": "IBX",
        "Barbary sheep": "BBY",
        "Bighorn sheep": "BHS",
        "Rocky Mountain bighorn sheep": "BHS",
        "Desert bighorn sheep": "BHS",
    }

    inserted = 0
    missing_species = set()
    missing_bag_codes = set()

    insert_sql = """
        INSERT INTO hunts (hunt_code, species_id, bag_limit_id, unit_description, is_active)
        VALUES (?, ?, ?, ?, 1)
    """

    for _, row in df.iterrows():
        hunt_code = str(row["hunt_code"]).strip()
        if not hunt_code:
            continue

        raw_species = str(row["species"]).strip()

        # If CSV already uses species_code like ELK, use that
        if raw_species in species_map:
            species_code = raw_species
        else:
            species_code = species_name_to_code.get(raw_species)

        species_id = species_map.get(species_code)
        if species_id is None:
            missing_species.add(raw_species)
            continue

        bag_raw = str(row["bag"]).strip() if not pd.isna(row["bag"]) else ""
        bag_limit_id = None
        if bag_raw:
            bag_limit_id = bag_map.get(bag_raw)
            if bag_limit_id is None:
                missing_bag_codes.add(bag_raw)

        unit_description = (
            str(row["unit_description"]).strip()
            if not pd.isna(row["unit_description"])
            else None
        )

        cur.execute(
            insert_sql,
            (hunt_code, species_id, bag_limit_id, unit_description),
        )
        inserted += 1

    print(f"Inserted {inserted} hunts.")
    if missing_species:
        print(
            "WARNING: Missing species mappings for these labels (rows skipped):",
            sorted(missing_species),
        )
    if missing_bag_codes:
        print(
            "WARNING: Bag codes not found in bag_limits (set to NULL):",
            sorted(missing_bag_codes),
        )


def make_hunt_map(cur):
    hunt_map = {}
    for row in cur.execute("SELECT hunt_id, hunt_code FROM hunts;"):
        hunt_map[row["hunt_code"]] = row["hunt_id"]
    print(f"Built hunt_code -> hunt_id map with {len(hunt_map)} entries.")
    return hunt_map


def load_draw_results(cur, hunt_map):
    print(f"Loading draw results from {DRAW_CSV}...")
    df = pd.read_csv(DRAW_CSV)
    print("Draw CSV columns:", list(df.columns))

    required = {
        "hunt_code",
        "year",
        "resident_applications",
        "non_resident_applications",
        "outfitter_applications",
        "licenses_total",
        "resident_licenses",
        "non_resident_licenses",
        "outfitter_licenses",
        "resident_results",
        "non_resident_results",
        "outfitter_results",
    }
    missing_cols = required - set(df.columns)
    if missing_cols:
        raise SystemExit(f"Draw CSV missing columns: {missing_cols}")

    insert_sql = """
        INSERT INTO draw_results (
            hunt_id,
            draw_year,
            resident_applications,
            nonresident_applications,
            outfitter_applications,
            licenses_total,
            resident_licenses,
            nonresident_licenses,
            outfitter_licenses,
            resident_results,
            nonresident_results,
            outfitter_results
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    inserted = 0
    missing_codes = set()

    for _, row in df.iterrows():
        hunt_code = str(row["hunt_code"]).strip()
        if not hunt_code:
            continue

        hunt_id = hunt_map.get(hunt_code)
        if hunt_id is None:
            missing_codes.add(hunt_code)
            continue

        year = int(row["year"])

        def as_int(val):
            return int(val) if pd.notna(val) else 0

        vals = (
            hunt_id,
            year,
            as_int(row["resident_applications"]),
            as_int(row["non_resident_applications"]),
            as_int(row["outfitter_applications"]),
            as_int(row["licenses_total"]),
            as_int(row["resident_licenses"]),
            as_int(row["non_resident_licenses"]),
            as_int(row["outfitter_licenses"]),
            as_int(row["resident_results"]),
            as_int(row["non_resident_results"]),
            as_int(row["outfitter_results"]),
        )
        cur.execute(insert_sql, vals)
        inserted += 1

    print(f"Inserted {inserted} draw_results rows.")
    if missing_codes:
        print(
            "WARNING: draw_results had hunt_codes not found in hunts:",
            sorted(missing_codes),
        )


def load_hunt_dates(cur, hunt_map):
    print(f"Loading hunt dates from {DATES_CSV}...")
    df = pd.read_csv(DATES_CSV)
    print("Dates CSV columns:", list(df.columns))

    required = {"year", "hunt_code", "start_date", "end_date", "hunt_name"}
    missing_cols = required - set(df.columns)
    if missing_cols:
        raise SystemExit(f"Hunt dates CSV missing columns: {missing_cols}")

    insert_sql = """
        INSERT INTO hunt_dates (
            hunt_id,
            season_year,
            start_date,
            end_date,
            hunt_name,
            notes
        )
        VALUES (?, ?, ?, ?, ?, NULL)
    """

    inserted = 0
    missing_codes = set()

    for _, row in df.iterrows():
        hunt_code = str(row["hunt_code"]).strip()
        if not hunt_code:
            continue

        hunt_id = hunt_map.get(hunt_code)
        if hunt_id is None:
            missing_codes.add(hunt_code)
            continue

        year = int(row["year"])
        start_date = (
            str(row["start_date"]).strip() if pd.notna(row["start_date"]) else None
        )
        end_date = str(row["end_date"]).strip() if pd.notna(row["end_date"]) else None
        hunt_name = str(row["hunt_name"]).strip() if pd.notna(row["hunt_name"]) else ""

        cur.execute(
            insert_sql,
            (hunt_id, year, start_date, end_date, hunt_name),
        )
        inserted += 1

    print(f"Inserted {inserted} hunt_dates rows.")
    if missing_codes:
        print(
            "WARNING: hunt_dates had hunt_codes not found in hunts:",
            sorted(missing_codes),
        )


def load_harvest_stats(cur, hunt_map):
    print(f"Loading harvest stats from {HARVEST_CSV}...")
    df = pd.read_csv(HARVEST_CSV)
    print("Harvest CSV columns:", list(df.columns))

    required = {"year", "hunt_code", "success_rate", "satisfaction", "days_hunted", "licenses_sold"}
    missing_cols = required - set(df.columns)
    if missing_cols:
        raise SystemExit(f"Harvest CSV missing columns: {missing_cols}")

    # drop rows without a hunt_code
    df = df[df["hunt_code"].notna()].copy()
    df["hunt_code"] = df["hunt_code"].astype(str).str.strip()

    before = len(df)
    df = df.drop_duplicates(subset=["year", "hunt_code"])
    after = len(df)
    if after < before:
        print(f"Deduped harvest rows on (year, hunt_code): {before} -> {after}")

    insert_sql = """
        INSERT INTO harvest_stats (
            hunt_id,
            harvest_year,
            access_type,
            success_rate,
            satisfaction,
            days_hunted,
            licenses_sold
        )
        VALUES (?, ?, 'Public', ?, ?, ?, ?)
    """

    inserted = 0
    missing_codes = set()

    for _, row in df.iterrows():
        hunt_code = str(row["hunt_code"]).strip()
        if not hunt_code:
            continue

        hunt_id = hunt_map.get(hunt_code)
        if hunt_id is None:
            missing_codes.add(hunt_code)
            continue

        year = int(row["year"])

        def as_float(val):
            return float(val) if pd.notna(val) else None

        vals = (
            hunt_id,
            year,
            as_float(row["success_rate"]),
            as_float(row["satisfaction"]),
            as_float(row["days_hunted"]),
            as_float(row["licenses_sold"]),
        )
        cur.execute(insert_sql, vals)
        inserted += 1

    print(f"Inserted {inserted} harvest_stats rows.")
    if missing_codes:
        print(
            "WARNING: harvest_stats had hunt_codes not found in hunts:",
            sorted(missing_codes),
        )


def main():
    print(f"Using database: {DB_PATH}")
    print(f"Using data dir: {DATA_DIR}")

    for p in [HUNTS_CSV, DRAW_CSV, DATES_CSV, HARVEST_CSV]:
        if not p.exists():
            raise SystemExit(f"CSV not found: {p}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys = ON;")

    # load canonical maps
    species_map = {}
    for row in cur.execute("SELECT species_id, species_code FROM species;"):
        species_map[row["species_code"]] = row["species_id"]

    bag_map = {}
    for row in cur.execute("SELECT bag_limit_id, bag_code FROM bag_limits;"):
        bag_map[row["bag_code"]] = row["bag_limit_id"]

    print(f"Loaded {len(species_map)} species codes from DB.")
    print(f"Loaded {len(bag_map)} bag codes from DB.")

    # clear fact tables
    print("Clearing existing data from fact tables...")
    for table in ["harvest_stats", "draw_results", "hunt_dates", "hunt_gmus", "hunts"]:
        cur.execute(f"DELETE FROM {table};")
    conn.commit()

    # load in order
    load_hunts(cur, species_map, bag_map)
    conn.commit()

    hunt_map = make_hunt_map(cur)

    load_draw_results(cur, hunt_map)
    conn.commit()

    load_hunt_dates(cur, hunt_map)
    conn.commit()

    load_harvest_stats(cur, hunt_map)
    conn.commit()

    # simple row count summary
    print("\nRow counts after load:")
    for table in ["hunts", "draw_results", "hunt_dates", "harvest_stats"]:
        cur.execute(f"SELECT COUNT(*) AS c FROM {table};")
        c = cur.fetchone()["c"]
        print(f"  {table}: {c}")

    # optional sanity checks on views, if they exist
    print("\nSample from hunt_summary_view (if present):")
    try:
        for row in cur.execute(
            "SELECT * FROM hunt_summary_view LIMIT 5;"
        ):
            print(dict(row))
    except sqlite3.Error as e:
        print(f"  Could not query hunt_summary_view: {e}")

    print("\nSample from harvest_public_view (if present):")
    try:
        for row in cur.execute(
            "SELECT * FROM harvest_public_view LIMIT 5;"
        ):
            print(dict(row))
    except sqlite3.Error as e:
        print(f"  Could not query harvest_public_view: {e}")

    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
