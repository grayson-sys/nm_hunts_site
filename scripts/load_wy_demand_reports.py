#!/usr/bin/env python3
"""
Wyoming Game & Fish Demand Report Loader
Parses WY G&F draw demand PDFs (NR preference point, random, leftover, etc.)
Maps to existing WY hunt codes: Area "001" + Type "1" → hunt_code "1-1"

Files in WY/raw_data/:
  2025_elk_prefpoints_nonres.pdf, 2025_elk_prefpoints_nonres_special.pdf
  2025_elk_random_nonres.pdf, 2025_elk_leftover_nonres.pdf
  2025_elk_cowcalf_nonres.pdf
  2025_deer_prefpoints_nonres.pdf, 2025_deer_prefpoints_nonres_special.pdf
  2025_deer_random_nonres.pdf, 2025_deer_leftover_nonres.pdf
  2025_deer_doefawn_nonres.pdf
  Resident versions: 2025_elk_cowcalf_res.pdf, 2025_elk_leftover_res.pdf,
  2025_elk_random_res.pdf, 2025_deer_doefawn_res.pdf, 2025_deer_leftover_res.pdf,
  2025_deer_random_res.pdf
"""

import os, re
from collections import defaultdict
import fitz
import psycopg2

BASE_DIR = "/Users/openclaw/Documents/GraysonsDrawOdds"
WY_DIR   = f"{BASE_DIR}/WY/raw_data"
DB = dict(host='localhost', port=5432, dbname='draws', user='draws', password='drawspass')
DRAW_YEAR = 2025

# (filename, pool_code, description)
PREF_POINT_FILES = [
    ('2025_elk_prefpoints_nonres.pdf',         'NR_PREF',         'NR Preference Point'),
    ('2025_elk_prefpoints_nonres_special.pdf', 'NR_PREF_SPECIAL', 'NR Special Preference Point'),
    ('2025_deer_prefpoints_nonres.pdf',        'NR_PREF',         'NR Preference Point'),
    ('2025_deer_prefpoints_nonres_special.pdf','NR_PREF_SPECIAL', 'NR Special Preference Point'),
]
RANDOM_FILES = [
    ('2025_elk_random_nonres.pdf',    'NR_RANDOM',      'NR Random Draw'),
    ('2025_elk_leftover_nonres.pdf',  'NR_LEFTOVER',    'NR Leftover Draw'),
    ('2025_elk_cowcalf_nonres.pdf',   'NR_ANTLERLESS',  'NR Antlerless/Cow-Calf'),
    ('2025_deer_random_nonres.pdf',   'NR_RANDOM',      'NR Random Draw'),
    ('2025_deer_leftover_nonres.pdf', 'NR_LEFTOVER',    'NR Leftover Draw'),
    ('2025_deer_doefawn_nonres.pdf',  'NR_ANTLERLESS',  'NR Antlerless/Doe-Fawn'),
    ('2025_elk_random_res.pdf',       'RES_RANDOM',     'Resident Random Draw'),
    ('2025_elk_leftover_res.pdf',     'RES_LEFTOVER',   'Resident Leftover Draw'),
    ('2025_elk_cowcalf_res.pdf',      'RES_ANTLERLESS', 'Resident Antlerless/Cow-Calf'),
    ('2025_deer_random_res.pdf',      'RES_RANDOM',     'Resident Random Draw'),
    ('2025_deer_leftover_res.pdf',    'RES_LEFTOVER',   'Resident Leftover Draw'),
    ('2025_deer_doefawn_res.pdf',     'RES_ANTLERLESS', 'Resident Antlerless/Doe-Fawn'),
]


def area_type_to_hunt_code(area_str, type_str):
    """'001', '1' → '1-1';  '010', '4' → '10-4'"""
    try:
        return f"{int(area_str)}-{int(type_str)}"
    except ValueError:
        return None


# ─── PREFERENCE POINT FORMAT PARSER ───────────────────────────────────────────
# Header row: "001    1      ANY ELK            6    1    18     1    100.00%"
# Cont rows:  "                                 5    0  < 18     0    100.00%"
HUNT_HDR = re.compile(
    r'^(\d{3})\s+(\d+)\s+'          # area, type
    r'(.{2,25?})\s{2,}'             # description (non-greedy)
    r'(\d+)\s+'                     # quota
    r'(\d+)\s+'                     # issued (remaining after this tier)
    r'(<?\s*\d+)\s+'                # pref points (maybe "< N")
    r'(\d+)\s+'                     # applicants
    r'([\d.]+)%'                    # success odds
)
CONT_LINE = re.compile(
    r'^\s{20,}'                     # starts with lots of whitespace
    r'(\d+)\s+'                     # remaining quota
    r'(\d+)\s+'                     # issued at this tier
    r'(<?\s*\d+)\s+'                # pref points
    r'(\d+)\s+'                     # applicants
    r'([\d.]+)%'                    # success odds
)


def _normalize_tokens(tokens):
    """Merge any '< N' pairs into a single '< N' token, drop odds% token."""
    norm = []
    i = 0
    while i < len(tokens):
        if tokens[i] == '<' and i+1 < len(tokens) and re.match(r'^\d+$', tokens[i+1]):
            norm.append(f'< {tokens[i+1]}')
            i += 2
        else:
            norm.append(tokens[i])
            i += 1
    return [t for t in norm if not re.match(r'^[\d.]+%$', t)]


def _parse_hunt_header(tokens):
    """
    From a hunt header token list (includes area, type, desc words, then data),
    parse out: area, hunt_type, quota, issued, pts_str, applicants.
    Returns dict or None.
    """
    # Scan right-to-left on normalized tokens (no odds%)
    norm = _normalize_tokens(tokens)
    try:
        apps = norm[-1]
        pts_raw = norm[-2]
        issued = norm[-3]
        quota = norm[-4]
        area = norm[0]
        htype = norm[1]
        return dict(area=area, hunt_type=htype, quota=int(quota),
                    issued=int(issued), pts_raw=pts_raw, apps=int(apps))
    except (IndexError, ValueError):
        return None


def _parse_cont_line(tokens):
    """
    Parse a continuation line: (remaining, issued, pts, apps) or (remaining, pts, apps).
    Returns dict or None.
    """
    norm = _normalize_tokens(tokens)
    try:
        if len(norm) >= 4:
            remaining, issued, pts_raw, apps = norm[-4], norm[-3], norm[-2], norm[-1]
            return dict(remaining=int(remaining), issued=int(issued),
                        pts_raw=pts_raw, apps=int(apps))
        elif len(norm) == 3:
            remaining, pts_raw, apps = norm[-3], norm[-2], norm[-1]
            return dict(remaining=int(remaining), issued=0,
                        pts_raw=pts_raw, apps=int(apps))
    except (ValueError, IndexError):
        pass
    return None


SKIP_RE = re.compile(
    r'^(Demand Report|Nonresident|Resident|Hunt\s+Hunt|Area\s+Type|'
    r'----|\s*State of Wyoming|Fiscal|Wyoming Game|Date:|Time:|Page:)'
)


def parse_pref_points_pdf(pdf_path, pool_code):
    """
    Parse WY G&F NR preference point demand report.
    Returns list of dicts: {area, hunt_type, points, issued, applicants, quota, pool_code}
    Only includes rows with EXPLICIT (non-< N) point levels.
    """
    doc  = fitz.open(pdf_path)
    records = []
    current = None  # {area, hunt_type, quota}

    for page in doc:
        for raw_line in page.get_text().split('\n'):
            line = raw_line.rstrip()
            tokens = line.split()
            if not tokens:
                continue
            if SKIP_RE.match(line.strip()):
                continue

            # Hunt header: first token is 3-digit area code
            if re.match(r'^\d{3}$', tokens[0]):
                parsed = _parse_hunt_header(tokens)
                if parsed:
                    current = {'area': parsed['area'], 'hunt_type': parsed['hunt_type'],
                               'quota': parsed['quota']}
                    if not parsed['pts_raw'].startswith('<'):
                        records.append({
                            'area': parsed['area'], 'hunt_type': parsed['hunt_type'],
                            'quota': parsed['quota'],
                            'points': int(parsed['pts_raw']),
                            'issued': parsed['issued'],
                            'applicants': parsed['apps'],
                            'pool_code': pool_code,
                        })
                continue

            # Continuation line: starts with whitespace
            if current and line and line[0] == ' ':
                parsed = _parse_cont_line(tokens)
                if parsed and not parsed['pts_raw'].startswith('<'):
                    pts = int(parsed['pts_raw'])
                    records.append({
                        'area': current['area'], 'hunt_type': current['hunt_type'],
                        'quota': current['quota'],
                        'points': pts,
                        'issued': parsed['issued'],
                        'applicants': parsed['apps'],
                        'pool_code': pool_code,
                    })

    return records


def aggregate_pref_records(records):
    """Aggregate by (area, hunt_type, pool_code) → draw_results_by_pool fields."""
    groups = defaultdict(list)
    for r in records:
        groups[(r['area'], r['hunt_type'], r['pool_code'], r.get('quota', 0))].append(r)

    results = []
    for (area, htype, pool_code, quota), rows in groups.items():
        total_apps  = sum(r['applicants'] for r in rows)
        total_issued = sum(r['issued']    for r in rows)

        pts_with_issued = [r['points'] for r in rows if r['issued'] > 0 and r['points'] > 0]
        min_pts = min(pts_with_issued) if pts_with_issued else 0

        weighted = [(r['points'] * r['issued'], r['issued'])
                    for r in rows if r['points'] > 0 and r['issued'] > 0]
        avg_pts = (sum(w for w, _ in weighted) / sum(s for _, s in weighted)
                   if weighted else 0.0)

        pts_with_apps = [r['points'] for r in rows if r['applicants'] > 0 and r['points'] > 0]
        max_pts = max(pts_with_apps) if pts_with_apps else None

        results.append({
            'area': area, 'hunt_type': htype, 'pool_code': pool_code,
            'tags_available': quota,
            'applications': total_apps, 'tags_awarded': total_issued,
            'min_pts_drawn': min_pts, 'avg_pts_drawn': round(avg_pts, 2),
            'max_pts_held': max_pts,
        })
    return results


# ─── RANDOM / LEFTOVER FORMAT PARSER ──────────────────────────────────────────
# "009    1      ANY ELK                      20              22       20       8        0      10        0"
# Columns: Area, Type, Desc, Quota, 1st Apps, 1st Drew, 2nd Apps, 2nd Drew, 3rd Apps, 3rd Drew
def parse_random_pdf(pdf_path, pool_code):
    """
    Parse WY random/leftover/antlerless format.
    Columns: Area, Type, Desc, Quota, 1st-choice apps, 2nd-choice apps, 3rd-choice apps
    (No explicit 'drew' column — assume quota filled if oversubscribed.)
    """
    doc = fitz.open(pdf_path)
    records = []
    for page in doc:
        for raw_line in page.get_text().split('\n'):
            line = raw_line.rstrip()
            tokens = line.split()
            if not tokens:
                continue
            if SKIP_RE.match(line.strip()):
                continue
            # Hunt header: starts with 3-digit area code
            if not re.match(r'^\d{3}$', tokens[0]):
                continue
            # Last 4 tokens: quota, 1st_apps, 2nd_apps, 3rd_apps
            try:
                quota    = int(tokens[-4])
                apps_1st = int(tokens[-3])
                # apps_2nd = int(tokens[-2])
                # apps_3rd = int(tokens[-1])
                area  = tokens[0]
                htype = tokens[1]
                # tags_awarded ≈ min(quota, apps_1st) for oversubscribed draws
                awarded = min(quota, apps_1st)
                records.append({
                    'area': area, 'hunt_type': htype,
                    'quota': quota,
                    'applications': apps_1st,
                    'tags_awarded': awarded,
                    'tags_available': quota,
                    'pool_code': pool_code,
                    'min_pts_drawn': 0, 'avg_pts_drawn': 0.0, 'max_pts_held': None,
                })
            except (ValueError, IndexError):
                continue
    return records


# ─── MAIN ──────────────────────────────────────────────────────────────────────
def get_or_create_pool(cur, state_id, pool_code, description):
    cur.execute("SELECT pool_id FROM pools WHERE state_id=%s AND pool_code=%s",
                (state_id, pool_code))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute("INSERT INTO pools (state_id, pool_code, description) VALUES (%s,%s,%s) RETURNING pool_id",
                (state_id, pool_code, description))
    return cur.fetchone()[0]


def main():
    conn = psycopg2.connect(**DB)
    cur  = conn.cursor()

    cur.execute("SELECT state_id FROM states WHERE state_code='WY'")
    wy_id = cur.fetchone()[0]
    print(f"WY state_id = {wy_id}")

    # Build all pool codes we'll use
    all_pools = {}
    for fname, pool_code, pool_desc in PREF_POINT_FILES + RANDOM_FILES:
        if pool_code not in all_pools:
            all_pools[pool_code] = pool_desc

    pool_map = {}
    for code, desc in all_pools.items():
        pool_map[code] = get_or_create_pool(cur, wy_id, code, desc)
    conn.commit()
    print(f"WY pools ready: {list(pool_map.keys())}")

    # Hunt lookup: hunt_code → hunt_id
    cur.execute("SELECT hunt_id, hunt_code FROM hunts WHERE state_id=%s", (wy_id,))
    hunt_lookup = {row[1]: row[0] for row in cur.fetchall()}
    print(f"WY hunts in DB: {len(hunt_lookup)}")

    total_loaded = total_skipped = 0
    missing = set()

    def load_rows(rows):
        nonlocal total_loaded, total_skipped
        for row in rows:
            hc = area_type_to_hunt_code(row['area'], row['hunt_type'])
            if not hc:
                total_skipped += 1; continue
            hunt_id = hunt_lookup.get(hc)
            if not hunt_id:
                missing.add(hc)
                total_skipped += 1; continue
            pool_id = pool_map.get(row['pool_code'])
            if not pool_id:
                total_skipped += 1; continue

            cur.execute("""
                INSERT INTO draw_results_by_pool
                    (hunt_id, draw_year, pool_id,
                     applications, tags_available, tags_awarded,
                     avg_pts_drawn, min_pts_drawn, max_pts_held)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (hunt_id, draw_year, pool_id) DO UPDATE SET
                    applications  = EXCLUDED.applications,
                    tags_available= EXCLUDED.tags_available,
                    tags_awarded  = EXCLUDED.tags_awarded,
                    avg_pts_drawn = EXCLUDED.avg_pts_drawn,
                    min_pts_drawn = EXCLUDED.min_pts_drawn,
                    max_pts_held  = EXCLUDED.max_pts_held
            """, (hunt_id, DRAW_YEAR, pool_id,
                  row['applications'], row.get('tags_available'),
                  row['tags_awarded'], row['avg_pts_drawn'],
                  row['min_pts_drawn'], row['max_pts_held']))
            total_loaded += 1

    # Preference point files
    for fname, pool_code, _ in PREF_POINT_FILES:
        fpath = os.path.join(WY_DIR, fname)
        if not os.path.exists(fpath):
            print(f"  SKIP: {fname}"); continue
        print(f"\nParsing pref-pts: {fname}...")
        raw  = parse_pref_points_pdf(fpath, pool_code)
        print(f"  Raw tier records: {len(raw)}")
        agg  = aggregate_pref_records(raw)
        print(f"  Aggregated pool rows: {len(agg)}")
        load_rows(agg)
        conn.commit()

    # Random / leftover / antlerless files
    for fname, pool_code, _ in RANDOM_FILES:
        fpath = os.path.join(WY_DIR, fname)
        if not os.path.exists(fpath):
            print(f"  SKIP: {fname}"); continue
        print(f"\nParsing random: {fname}...")
        rows = parse_random_pdf(fpath, pool_code)
        print(f"  Rows: {len(rows)}")
        load_rows(rows)
        conn.commit()

    conn.close()
    print(f"\n=== WY DEMAND REPORT LOAD COMPLETE ===")
    print(f"  Loaded:  {total_loaded}")
    print(f"  Skipped: {total_skipped}")
    if missing:
        print(f"  Missing hunt codes ({len(missing)}): {sorted(missing)[:20]}")


if __name__ == '__main__':
    main()
