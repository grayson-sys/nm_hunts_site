#!/usr/bin/env python3
"""
Montana By-Points Draw Results Loader
Parses MT FWP ALS30401 by-points PDFs (proclamation code format):
  ELK B LICENSE, ELK PERMIT, DEER B LICENSE, DEER PERMIT
Maps to existing proclamation hunt records (E-XXX-XX, D-XXX-XX).
"""

import os, re, sys
from collections import defaultdict
import fitz  # PyMuPDF
import psycopg2

BASE_DIR = "/Users/openclaw/Documents/GraysonsDrawOdds"
MT_DIR   = f"{BASE_DIR}/MT/raw_data"
DB = dict(host='localhost', port=5432, dbname='draws', user='draws', password='drawspass')

LICENSE_TYPES = {
    'ELK B LICENSE', 'ELK PERMIT',
    'DEER B LICENSE', 'DEER PERMIT',
    'ANTELOPE B LICENSE', 'ANTELOPE PERMIT',
}
SKIP_WORDS = {
    'Item Description', 'District', 'Residency',
    'Number of Points', 'Number of Applications',
    'Number of Successes', '% Successful',
    'Item Description District', 'Residency Number of Points',
}
RESIDENCIES = {
    'RESIDENT LANDOWNER', 'RESIDENT',
    'NONRESIDENT LANDOWNER', 'NONRESIDENT',
}
LIC_TO_PREFIX = {
    'ELK B LICENSE': 'E', 'ELK PERMIT': 'E',
    'DEER B LICENSE': 'D', 'DEER PERMIT': 'D',
    'ANTELOPE B LICENSE': 'A', 'ANTELOPE PERMIT': 'A',
}
RES_TO_POOL = {
    'RESIDENT LANDOWNER': 'RES_LO',
    'RESIDENT': 'RES',
    'NONRESIDENT LANDOWNER': 'NR_LO',
    'NONRESIDENT': 'NR',
}

# PDFs to load: (filename, draw_year)
BY_POINTS_FILES = [
    ('MT_elk_b_license_by_points_2024.pdf', 2024),
    ('MT_elk_b_license_by_points_2025.pdf', 2025),
    ('MT_elk_permit_by_points_2024.pdf',    2024),
    ('MT_elk_permit_by_points_2025.pdf',    2025),
    ('MT_deer_permit_by_points_2024.pdf',   2024),
    ('MT_deer_permit_by_points_2025.pdf',   2025),
    ('MT_deer_b_license_by_points_2024.pdf',2024),
    ('MT_deer_b_license_by_points_2025.pdf',2025),
]


def parse_by_points_pdf(pdf_path):
    """
    Returns list of dicts:
      {license_type, district, residency, points, applications, successes}
    Points=0 means zero-preference-point (random) pool.
    """
    doc = fitz.open(pdf_path)
    lines = []
    for page in doc:
        for ln in page.get_text().split('\n'):
            s = ln.strip()
            if s and not any(s.startswith(w) for w in SKIP_WORDS):
                lines.append(s)

    records = []
    i = 0
    while i < len(lines):
        ln = lines[i]

        # Detect TOTAL rows (skip — we'll aggregate ourselves)
        if re.search(r'\bTOTAL\b', ln):
            i += 1
            continue

        # Detect license type line
        if ln in LICENSE_TYPES:
            lic = ln
            i += 1
            if i >= len(lines): break

            # Next: district code (NNN-NN)
            if not re.match(r'^\d{3}-\d{2}$', lines[i]):
                continue
            district = lines[i]; i += 1
            if i >= len(lines): break

            # Next: residency (may be two words on separate lines)
            res = None
            if lines[i] in RESIDENCIES:
                res = lines[i]; i += 1
            elif i+1 < len(lines) and f"{lines[i]} {lines[i+1]}" in RESIDENCIES:
                res = f"{lines[i]} {lines[i+1]}"; i += 2
            if not res:
                continue
            if i >= len(lines): break

            # Next: points (integer)
            if not re.match(r'^\d+$', lines[i]):
                continue
            pts = int(lines[i]); i += 1
            if i >= len(lines): break

            # Next: applications
            if not re.match(r'^\d+$', lines[i]):
                continue
            apps = int(lines[i]); i += 1
            if i >= len(lines): break

            # Next: successes
            if not re.match(r'^\d+$', lines[i]):
                continue
            succ = int(lines[i]); i += 1

            # Skip % line if present
            if i < len(lines) and re.match(r'^[\d.]+$', lines[i]):
                i += 1

            records.append({
                'license_type': lic,
                'district': district,
                'residency': res,
                'points': pts,
                'applications': apps,
                'successes': succ,
            })
        else:
            i += 1

    return records


def aggregate_to_pools(records, draw_year):
    """Roll up point-level data into per-pool summary for draw_results_by_pool."""
    groups = defaultdict(list)
    for r in records:
        groups[(r['license_type'], r['district'], r['residency'])].append(r)

    results = []
    for (lic, district, residency), rows in groups.items():
        total_apps  = sum(r['applications'] for r in rows)
        total_succ  = sum(r['successes']    for r in rows)

        # min_pts_drawn: lowest non-zero point level with any successes
        pts_with_succ = [r['points'] for r in rows if r['successes'] > 0 and r['points'] > 0]
        min_pts = min(pts_with_succ) if pts_with_succ else 0

        # avg_pts_drawn: weighted avg over non-zero pts with successes
        weighted = [(r['points'] * r['successes'], r['successes'])
                    for r in rows if r['points'] > 0 and r['successes'] > 0]
        avg_pts = (sum(w for w, _ in weighted) / sum(s for _, s in weighted)
                   if weighted else 0.0)

        # max_pts_held: highest point level with any applications
        pts_with_apps = [r['points'] for r in rows if r['applications'] > 0 and r['points'] > 0]
        max_pts = max(pts_with_apps) if pts_with_apps else None

        results.append({
            'license_type': lic, 'district': district, 'residency': residency,
            'draw_year': draw_year,
            'applications': total_apps, 'tags_awarded': total_succ,
            'min_pts_drawn': min_pts, 'avg_pts_drawn': round(avg_pts, 2),
            'max_pts_held': max_pts,
        })
    return results


def get_or_create_pool(cur, state_id, pool_code, description):
    cur.execute("SELECT pool_id FROM pools WHERE state_id=%s AND pool_code=%s",
                (state_id, pool_code))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute("""INSERT INTO pools (state_id, pool_code, description)
                   VALUES (%s, %s, %s) RETURNING pool_id""",
                (state_id, pool_code, description))
    return cur.fetchone()[0]


def main():
    conn = psycopg2.connect(**DB)
    cur  = conn.cursor()

    # State ID
    cur.execute("SELECT state_id FROM states WHERE state_code='MT'")
    mt_id = cur.fetchone()[0]
    print(f"MT state_id = {mt_id}")

    # Ensure MT pools exist
    pool_defs = {
        'RES_LO': 'Resident Landowner',
        'RES':    'Resident',
        'NR_LO':  'Nonresident Landowner',
        'NR':     'Nonresident',
    }
    pool_map = {}
    for code, desc in pool_defs.items():
        pool_map[code] = get_or_create_pool(cur, mt_id, code, desc)
    conn.commit()
    print(f"Pools: {pool_map}")

    # Build hunt lookup: (hunt_code) → hunt_id  for MT
    cur.execute("SELECT hunt_id, hunt_code FROM hunts WHERE state_id=%s", (mt_id,))
    hunt_lookup = {row[1]: row[0] for row in cur.fetchall()}
    print(f"MT hunts in DB: {len(hunt_lookup)}")

    total_loaded = 0
    total_skipped = 0
    missing_hunts = set()

    for fname, draw_year in BY_POINTS_FILES:
        fpath = os.path.join(MT_DIR, fname)
        if not os.path.exists(fpath):
            print(f"  SKIP (not found): {fname}")
            continue

        print(f"\nParsing {fname} (year={draw_year})...")
        raw = parse_by_points_pdf(fpath)
        print(f"  Raw records: {len(raw)}")

        pooled = aggregate_to_pools(raw, draw_year)
        print(f"  Pool records: {len(pooled)}")

        for row in pooled:
            prefix = LIC_TO_PREFIX.get(row['license_type'])
            if not prefix:
                total_skipped += 1
                continue

            hunt_code = f"{prefix}-{row['district']}"
            hunt_id   = hunt_lookup.get(hunt_code)
            if not hunt_id:
                missing_hunts.add(hunt_code)
                total_skipped += 1
                continue

            pool_code = RES_TO_POOL.get(row['residency'])
            pool_id   = pool_map.get(pool_code)
            if not pool_id:
                total_skipped += 1
                continue

            cur.execute("""
                INSERT INTO draw_results_by_pool
                    (hunt_id, draw_year, pool_id,
                     applications, tags_available, tags_awarded,
                     avg_pts_drawn, min_pts_drawn, max_pts_held)
                VALUES (%s, %s, %s, %s, NULL, %s, %s, %s, %s)
                ON CONFLICT (hunt_id, draw_year, pool_id) DO UPDATE SET
                    applications  = EXCLUDED.applications,
                    tags_awarded  = EXCLUDED.tags_awarded,
                    avg_pts_drawn = EXCLUDED.avg_pts_drawn,
                    min_pts_drawn = EXCLUDED.min_pts_drawn,
                    max_pts_held  = EXCLUDED.max_pts_held
            """, (hunt_id, row['draw_year'], pool_id,
                  row['applications'], row['tags_awarded'],
                  row['avg_pts_drawn'], row['min_pts_drawn'], row['max_pts_held']))
            total_loaded += 1

        conn.commit()

    conn.close()
    print(f"\n=== MT BY-POINTS LOAD COMPLETE ===")
    print(f"  Loaded:  {total_loaded}")
    print(f"  Skipped: {total_skipped}")
    if missing_hunts:
        print(f"  Missing hunt codes ({len(missing_hunts)}): {sorted(missing_hunts)[:20]}")


if __name__ == '__main__':
    main()
