#!/usr/bin/env python3
"""
Import Montana harvest data from fetch_mt_harvest.py CSVs into draws.db.

CSV "Hunting" column = 3-digit hunting district (HD) number.
Hunt codes in DB: E-{HD}-{suffix} (elk), D-{HD}-{suffix} (deer/WTD/MDR), A-{HD}-{suffix} (antelope)

Mapping rules:
  - Skip aggregate rows where Hunting contains 'X' (e.g. '1XX', '2XX')
  - Use Residency='SUM' rows for combined success rate
  - Deer: 'md' rows → MDR species; 'wt' rows → WTD species; 'all_deer' skipped
  - success_rate = round((Total Harvest / Hunters) * 100, 1)
  - Store harvest_year from "License Year" column
  - Apply same rate to ALL hunt codes matching that HD + species prefix

Run AFTER fetch_mt_harvest.py has produced raw_data/harvest_{species}_{year}.csv
"""
import csv
import os
import re
import sqlite3

DB_PATH = os.path.expanduser("~/sleeperunits/draws.db")
RAW_DIR = os.path.join(os.path.dirname(__file__), '..', 'raw_data')


def pad_district(d):
    """'100' → '100', '7' → '007', '15A' → '015A' (preserve alpha suffix)"""
    m = re.match(r'^(\d+)(.*)', d.strip())
    if not m:
        return None
    num, suffix = m.groups()
    return num.zfill(3) + suffix


def load_csv(path, species_filter=None):
    """
    Load a harvest CSV. Returns list of dicts with keys:
      year, district (zero-padded), hunters, harvest, success_rate
    species_filter: 'md', 'wt', or None (for non-deer species)
    """
    rows = []
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            district = row.get('Hunting', '').strip()
            residency = row.get('Residency', '').strip()
            if 'X' in district:        # skip aggregate rows like '1XX'
                continue
            if residency != 'SUM':     # use combined R+NR totals
                continue
            if species_filter:         # deer: filter by 'md' or 'wt'
                sp_val = row.get('Deer Species', '').strip()
                if sp_val != species_filter:
                    continue

            year = row.get('License Year', '').strip()
            hunters = row.get('Hunters', '0').strip().replace(',', '')
            harvest = row.get('Total Harvest', '0').strip().replace(',', '')

            try:
                hunters_n = int(hunters)
                harvest_n = int(harvest)
            except ValueError:
                continue
            if hunters_n <= 0:
                continue

            success = round((harvest_n / hunters_n) * 100, 1)
            district_pad = pad_district(district)
            if not district_pad:
                continue

            rows.append({
                'year': int(year),
                'district': district_pad,
                'hunters': hunters_n,
                'harvest': harvest_n,
                'success_rate': success,
            })
    return rows


def get_hunt_ids(cur, state_id, species_code, hd_prefix):
    """
    Return all hunt_ids for a given state, species, and hunting district prefix.
    e.g. hd_prefix='E-100-' matches E-100-00, E-100-01, E-100-50 etc.
    """
    cur.execute("""
        SELECT h.hunt_id FROM hunts h
        JOIN species sp ON h.species_id = sp.species_id
        WHERE h.state_id = ? AND sp.species_code = ?
          AND h.hunt_code LIKE ?
    """, (state_id, species_code, hd_prefix + '%'))
    return [r[0] for r in cur.fetchall()]


def import_species(cur, state_id, csv_path, species_code, hd_letter, deer_sub=None):
    """
    Import one species+year file into harvest_stats.
    deer_sub: 'md' or 'wt' for deer CSV (filters by Deer Species column)
    """
    rows = load_csv(csv_path, species_filter=deer_sub)
    inserted = updated = skipped = 0

    for row in rows:
        hd_prefix = f"{hd_letter}-{row['district']}-"
        hunt_ids = get_hunt_ids(cur, state_id, species_code, hd_prefix)
        if not hunt_ids:
            skipped += 1
            continue

        for hunt_id in hunt_ids:
            cur.execute("""
                INSERT INTO harvest_stats
                  (hunt_id, harvest_year, access_type, success_rate,
                   harvest_count, licenses_sold)
                VALUES (?, ?, 'all', ?, ?, ?)
                ON CONFLICT(hunt_id, harvest_year, access_type) DO UPDATE SET
                  success_rate  = excluded.success_rate,
                  harvest_count = excluded.harvest_count,
                  licenses_sold = excluded.licenses_sold
            """, (hunt_id, row['year'], row['success_rate'],
                  row['harvest'], row['hunters']))
            if cur.rowcount:
                inserted += 1

    return inserted, skipped


def main():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute("SELECT state_id FROM states WHERE state_code='MT'")
    state_id = cur.fetchone()[0]
    print(f"MT state_id={state_id}", flush=True)

    total_inserted = 0
    total_skipped = 0

    imports = [
        # (csv_glob, species_code, hd_letter, deer_sub)
        ('harvest_elk_*.csv',      'ELK', 'E', None),
        ('harvest_deer_*.csv',     'MDR', 'D', 'md'),
        ('harvest_deer_*.csv',     'WTD', 'D', 'wt'),
        ('harvest_antelope_*.csv', 'ANT', 'A', None),
        ('harvest_moose_*.csv',    'MOOS','M', None),
        ('harvest_sheep_*.csv',    'BHS', 'S', None),
        ('harvest_goat_*.csv',     'MGT', 'G', None),
    ]

    import glob
    for pattern, species_code, hd_letter, deer_sub in imports:
        files = sorted(glob.glob(os.path.join(RAW_DIR, pattern)))
        for csv_path in files:
            fname = os.path.basename(csv_path)
            ins, skip = import_species(cur, state_id, csv_path,
                                       species_code, hd_letter, deer_sub)
            print(f"  {fname} → {species_code}: {ins} rows inserted, {skip} districts not matched", flush=True)
            total_inserted += ins
            total_skipped += skip

    con.commit()
    con.close()

    print(f"\n✅ Done. Total inserted/updated: {total_inserted} | Unmatched districts: {total_skipped}", flush=True)

    # Validation
    print("\nPost-import validation:", flush=True)
    con2 = sqlite3.connect(DB_PATH)
    cur2 = con2.cursor()
    cur2.execute("""
        SELECT sp.species_code, hs.harvest_year, COUNT(*) as rows,
               ROUND(AVG(hs.success_rate),1) as avg_success
        FROM harvest_stats hs
        JOIN hunts h ON hs.hunt_id=h.hunt_id
        JOIN states s ON h.state_id=s.state_id
        JOIN species sp ON h.species_id=sp.species_id
        WHERE s.state_code='MT'
        GROUP BY sp.species_code, hs.harvest_year
        ORDER BY sp.species_code, hs.harvest_year
    """)
    for r in cur2.fetchall():
        print(f"  {r[0]} {r[1]}: {r[2]} rows, avg success {r[3]}%", flush=True)

    cur2.execute("SELECT COUNT(*) FROM harvest_stats hs JOIN hunts h ON hs.hunt_id=h.hunt_id JOIN states s ON h.state_id=s.state_id WHERE s.state_code='MT' AND hs.success_rate > 100")
    bad = cur2.fetchone()[0]
    print(f"  success_rate > 100%: {bad} rows (must be 0)", flush=True)
    con2.close()


if __name__ == '__main__':
    main()
