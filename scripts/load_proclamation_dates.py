#!/usr/bin/env python3
"""
Load parsed proclamation hunt dates into PostgreSQL.

Usage:
    python3 load_proclamation_dates.py --state NM --csv NM/proclamations/2026/NM_hunt_dates_2026.csv
    python3 load_proclamation_dates.py --all

Only loads rows where the hunt_code matches an existing hunt in the hunts table for that state.
"""

import argparse
import csv
import os
import sys

import psycopg2

BASE_DIR = "/Users/openclaw/Documents/GraysonsDrawOdds"
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'dbname': 'draws',
    'user': 'draws',
    'password': 'drawspass'
}
SEASON_YEAR = 2026

STATES = ['NM', 'AZ', 'CO', 'UT', 'NV', 'MT', 'ID', 'WY', 'OR', 'WA', 'CA']


def load_state(conn, state_code, csv_path):
    """Load hunt dates from CSV for one state. Returns stats dict."""
    if not os.path.exists(csv_path):
        return {'state': state_code, 'csv_rows': 0, 'matched': 0, 'inserted': 0, 'updated': 0, 'unmatched_codes': []}

    cur = conn.cursor()

    # Get state_id
    cur.execute("SELECT state_id FROM states WHERE state_code = %s", (state_code,))
    row = cur.fetchone()
    if not row:
        print(f"  [{state_code}] State not found in database")
        return {'state': state_code, 'csv_rows': 0, 'matched': 0, 'inserted': 0, 'updated': 0, 'unmatched_codes': []}
    state_id = row[0]

    # Get existing hunt codes for this state
    cur.execute("SELECT hunt_code, hunt_id FROM hunts WHERE state_id = %s", (state_id,))
    hunt_map = {r[0]: r[1] for r in cur.fetchall()}

    # Read CSV
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        csv_rows = list(reader)

    matched = 0
    inserted = 0
    updated = 0
    unmatched_codes = set()

    for row in csv_rows:
        hunt_code = row['hunt_code']
        open_date = row['open_date']
        close_date = row['close_date']
        bag_desc = row.get('bag_limit_description', '')
        notes = row.get('notes', '')

        if hunt_code in hunt_map:
            hunt_id = hunt_map[hunt_code]
            matched += 1

            # Upsert into hunt_dates
            cur.execute("""
                INSERT INTO hunt_dates (hunt_id, season_year, start_date, end_date, notes)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (hunt_id, season_year) DO UPDATE
                    SET start_date = EXCLUDED.start_date,
                        end_date = EXCLUDED.end_date,
                        notes = EXCLUDED.notes
                RETURNING (xmax = 0) AS is_insert
            """, (hunt_id, SEASON_YEAR, open_date, close_date, notes))

            result = cur.fetchone()
            if result and result[0]:
                inserted += 1
            else:
                updated += 1
        else:
            unmatched_codes.add(hunt_code)

    conn.commit()

    stats = {
        'state': state_code,
        'csv_rows': len(csv_rows),
        'matched': matched,
        'inserted': inserted,
        'updated': updated,
        'unmatched_codes': sorted(unmatched_codes)[:50]  # Cap at 50 for report
    }

    print(f"  [{state_code}] CSV rows: {len(csv_rows)}, Matched: {matched}, "
          f"Inserted: {inserted}, Updated: {updated}, Unmatched: {len(unmatched_codes)}")

    return stats


def main():
    parser = argparse.ArgumentParser(description='Load proclamation dates into PostgreSQL')
    parser.add_argument('--state', type=str, help='State code (e.g., NM)')
    parser.add_argument('--csv', type=str, help='Path to CSV file')
    parser.add_argument('--all', action='store_true', help='Load all states')
    args = parser.parse_args()

    conn = psycopg2.connect(**DB_CONFIG)

    all_stats = []

    if args.all:
        for state in STATES:
            csv_path = os.path.join(BASE_DIR, f"{state}/proclamations/2026/{state}_hunt_dates_2026.csv")
            if os.path.exists(csv_path):
                print(f"\nLoading {state}...")
                stats = load_state(conn, state, csv_path)
                all_stats.append(stats)
            else:
                print(f"\n[{state}] No CSV found, skipping")
                all_stats.append({'state': state, 'csv_rows': 0, 'matched': 0,
                                  'inserted': 0, 'updated': 0, 'unmatched_codes': []})
    elif args.state and args.csv:
        csv_path = os.path.join(BASE_DIR, args.csv) if not os.path.isabs(args.csv) else args.csv
        stats = load_state(conn, args.state, csv_path)
        all_stats.append(stats)
    else:
        parser.print_help()
        sys.exit(1)

    conn.close()

    # Print summary
    print("\n" + "=" * 70)
    print("LOAD SUMMARY")
    print("=" * 70)
    print(f"{'State':<8} {'CSV Rows':<12} {'Matched':<10} {'Inserted':<10} {'Updated':<10} {'Unmatched':<10}")
    print("-" * 70)
    for s in all_stats:
        unmatched_count = len(s['unmatched_codes'])
        print(f"{s['state']:<8} {s['csv_rows']:<12} {s['matched']:<10} {s['inserted']:<10} {s['updated']:<10} {unmatched_count:<10}")

    return all_stats


if __name__ == '__main__':
    main()
