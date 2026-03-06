#!/usr/bin/env python3
"""
Wyoming data loader: hunts, GMUs, draw results, harvest stats, hunt dates.

Sources:
  - 2025 draw PDFs (pref points, random, leftover, cow/calf, doe/fawn)
  - 2024/2025 elk/deer harvest reports
  - WY/proclamations/2026/WY_hunt_dates_2026.csv
"""

import os
import re
import csv
import psycopg2
import pdfplumber

BASE_DIR = "/Users/openclaw/Documents/GraysonsDrawOdds"
RAW_DIR = os.path.join(BASE_DIR, "WY", "raw_data")
PROC_DIR = os.path.join(BASE_DIR, "WY", "proclamations", "2026")

DB_CONFIG = {
    'host': 'localhost', 'port': 5432,
    'dbname': 'draws', 'user': 'draws', 'password': 'drawspass'
}


def connect():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    return conn


def safe_int(val):
    if val is None:
        return 0
    s = str(val).replace(',', '').strip()
    if not s or s == '-':
        return 0
    try:
        return int(float(s))
    except ValueError:
        return 0


def safe_float(val):
    if val is None:
        return None
    s = str(val).replace('%', '').replace(',', '').strip()
    if not s or s == '-':
        return None
    try:
        return float(s)
    except ValueError:
        return None


def hunt_code_from(area, typ):
    area = str(area).strip().lstrip('0') or '0'
    typ = str(typ).strip()
    return f"{area}-{typ}"


def species_id_from_desc(desc, filename):
    desc_lower = (desc or '').lower()
    fn_lower = filename.lower()
    if 'white-tailed' in desc_lower or 'white-tail' in desc_lower or 'whitetail' in desc_lower:
        return 3  # WTD
    if 'elk' in fn_lower or 'elk' in desc_lower:
        return 1  # ELK
    if 'deer' in fn_lower or 'deer' in desc_lower or 'mule' in desc_lower:
        return 2  # MDR
    return 1


def weapon_type_for_wy(desc):
    d = (desc or '').lower()
    if 'archery' in d:
        return 3  # ARCHERY
    return 1  # ANY


def parse_prefpoints_pdf(filepath):
    """Parse NR preference point demand reports."""
    results = {}
    current_area = None
    current_type = None

    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text = page.extract_text(layout=True)
            if not text:
                continue
            for line in text.split('\n'):
                stripped = line.strip()
                if not stripped or stripped.startswith('Demand Report') or \
                   stripped.startswith('Nonresident') or stripped.startswith('Fiscal') or \
                   stripped.startswith('Hunt ') or stripped.startswith('Area ') or \
                   stripped.startswith('----') or 'Page:' in stripped:
                    continue

                # Full line: "  001   1     ANY ELK                 6       1     18            1      100.00%"
                m = re.match(r'^\s*(\d{3})\s+(\S+)\s+(.+?)\s{2,}(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)', line)
                if m:
                    current_area = m.group(1)
                    current_type = m.group(2)
                    desc = m.group(3).strip()
                    quota = safe_int(m.group(4))
                    issued = safe_int(m.group(5))
                    pts_val = safe_int(m.group(6))
                    apps = safe_int(m.group(7))

                    key = (current_area, current_type)
                    if key not in results:
                        results[key] = {
                            'quota': quota, 'total_apps': 0,
                            'total_issued': 0, 'description': desc,
                            'max_pts': 0
                        }
                    results[key]['total_apps'] += apps
                    results[key]['total_issued'] += issued
                    if pts_val > results[key]['max_pts']:
                        results[key]['max_pts'] = pts_val
                    continue

                # Continuation line: quota_rem issued [<] points apps odds
                m2 = re.match(r'^\s{10,}(\S+)\s+(\S+)\s+[<]?\s*(\S+)\s+(\S+)\s+(\S+)', line)
                if not m2:
                    # Alternate: no issued field (blank)
                    m2 = re.match(r'^\s{10,}(\S+)\s+[<]?\s*(\S+)\s+(\S+)\s+(\S+)', line)
                    if m2 and current_area:
                        pts_val = safe_int(m2.group(2))
                        issued = 0
                        apps = safe_int(m2.group(3))
                        key = (current_area, current_type)
                        if key in results:
                            results[key]['total_apps'] += apps
                            if pts_val > results[key]['max_pts']:
                                results[key]['max_pts'] = pts_val
                        continue

                if m2 and current_area:
                    pts_val = safe_int(m2.group(1))
                    issued = safe_int(m2.group(2))
                    apps = safe_int(m2.group(4))

                    key = (current_area, current_type)
                    if key in results:
                        results[key]['total_apps'] += apps
                        results[key]['total_issued'] += issued
                        if pts_val > results[key]['max_pts']:
                            results[key]['max_pts'] = pts_val
                    continue

    return results


def parse_random_pdf(filepath):
    """Parse random/leftover/cow-calf/doe-fawn demand reports."""
    results = []

    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text = page.extract_text(layout=True)
            if not text:
                continue
            for line in text.split('\n'):
                stripped = line.strip()
                if not stripped or stripped.startswith('Demand Report') or \
                   stripped.startswith('Resident') or stripped.startswith('Nonresident') or \
                   stripped.startswith('Leftover') or stripped.startswith('Fiscal') or \
                   stripped.startswith('Hunt ') or stripped.startswith('Area ') or \
                   stripped.startswith('----') or 'Page:' in stripped:
                    continue

                m = re.match(r'^\s*(\d{3})\s+(\S+)\s+(.+?)\s{2,}(\S+)\s+(\S+)\s+(\S+)\s+(\S+)', line)
                if m:
                    results.append({
                        'area': m.group(1),
                        'type': m.group(2),
                        'description': m.group(3).strip(),
                        'quota': safe_int(m.group(4)),
                        'first_choice_apps': safe_int(m.group(5)),
                    })
    return results


def parse_harvest_pdf(filepath, species):
    """Parse WY harvest reports (by Hunt Area tables).
    Handles both 2025 format (Table 3/7/8) and 2024 format (TABLE I-A)."""
    results = []
    current_area = None
    in_table = False

    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            page_nospace = text.replace(' ', '')
            # 2025 format markers
            if 'HarvestStatisticsbyHuntArea' in page_nospace:
                in_table = True
            # 2024 format markers
            if 'TABLEI-A' in page_nospace or 'TABLEI-B' in page_nospace or \
               'TABLEIII-A' in page_nospace or 'TABLEIII-H' in page_nospace:
                in_table = True
            if not in_table:
                continue
            if 'HarvestStatisticsbyHerdUnit' in page_nospace or \
               'HarvestStatisticsbyNonresident' in page_nospace:
                in_table = False
                continue
            # 2024 format end markers
            if 'TABLEII' in page_nospace and 'TABLEI-' not in page_nospace and \
               'TABLEIII-' not in page_nospace:
                in_table = False
                continue
            if 'TABLEV' in page_nospace or 'TABLEIV' in page_nospace:
                in_table = False
                continue

            for line in text.split('\n'):
                stripped = line.strip()
                if not stripped:
                    continue

                # Skip header lines
                skip_keywords = ['Hunter', 'Active', 'HuntArea', 'Table', 'TABLE',
                                 'Summary', 'excludes', 'indicates', 'AREA TYPE',
                                 'LICENSES', 'ELK 20', 'DEER 20', 'MULE DEER',
                                 'WHITE-TAILED', 'column', 'count', '(cross',
                                 'BY HUNT AREA', 'HARVEST,']
                if any(kw in stripped for kw in skip_keywords):
                    continue

                # Hunt area header: "8Boulder Ridge" or "1BlackHills" or "1 Crook"
                m_area = re.match(r'^(\d+)\s*([A-Z][a-zA-Z])', line)
                if m_area:
                    current_area = m_area.group(1)
                    continue

                if current_area is None:
                    continue

                # Skip Resident/Nonresident/Pooled Resident/Pooled Nonresident
                if stripped.startswith('Resident') or stripped.startswith('Nonresident') or \
                   stripped.startswith('Pooled Resident') or stripped.startswith('Pooled Nonresident'):
                    continue

                # Total line (2025: "Total ...", 2024: "Pooled Total ...")
                if stripped.startswith('Total') or stripped.startswith('Pooled Total'):
                    parts = stripped.replace('%', '').split()
                    # Remove "Pooled" prefix if present
                    if parts[0] == 'Pooled':
                        parts = parts[1:]
                    if species == 'elk' and len(parts) >= 10:
                        results.append({
                            'area': current_area, 'type': 'Total',
                            'active_hunters': safe_int(parts[1]),
                            'harvest_total': safe_int(parts[6]),
                            'success_pct': safe_float(parts[8]),
                            'licenses_sold': None,
                        })
                    elif species == 'deer' and len(parts) >= 9:
                        results.append({
                            'area': current_area, 'type': 'Total',
                            'active_hunters': safe_int(parts[1]),
                            'harvest_total': safe_int(parts[5]),
                            'success_pct': safe_float(parts[7]),
                            'licenses_sold': None,
                        })
                    continue

                cleaned = re.sub(r'^\([\d,]+\)\s*', '', stripped)

                # 2024 format: "Full 1 138 27 4 9 0 40 29.0% 31.2 1248 152"
                # or "Reduced 6 211 0 0 24 15 39 18.5% 51.1 1993 250"
                # or "General 1124 117 17 47 11 192 17.1% 39.9 7652"
                # Strip Full/Reduced prefix and extract type
                m_2024 = re.match(r'^(?:Full|Reduced)\s+', cleaned)
                if m_2024:
                    cleaned = cleaned[m_2024.end():]

                if species == 'elk':
                    m_data = re.match(
                        r'^(\S+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d.%]+)\s+([\d.]+)\s*([\d,]*)',
                        cleaned)
                    if m_data:
                        results.append({
                            'area': current_area, 'type': m_data.group(1),
                            'active_hunters': safe_int(m_data.group(2)),
                            'harvest_total': safe_int(m_data.group(7)),
                            'success_pct': safe_float(m_data.group(9)),
                            'licenses_sold': safe_int(m_data.group(11)) if m_data.group(11) else None,
                        })
                else:
                    m_data = re.match(
                        r'^(\S+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d.%]+)\s+([\d.]+)\s*([\d,\-]*)',
                        cleaned)
                    if m_data:
                        results.append({
                            'area': current_area, 'type': m_data.group(1),
                            'active_hunters': safe_int(m_data.group(2)),
                            'harvest_total': safe_int(m_data.group(6)),
                            'success_pct': safe_float(m_data.group(8)),
                            'licenses_sold': safe_int(m_data.group(10)) if m_data.group(10) and m_data.group(10) != '-' else None,
                        })

    return results


def main():
    conn = connect()
    cur = conn.cursor()

    cur.execute("SELECT state_id FROM states WHERE state_code='WY'")
    row = cur.fetchone()
    if not row:
        print("ERROR: WY state not found")
        return
    wy_state_id = row[0]
    print(f"WY state_id = {wy_state_id}")

    # Ensure WY pools exist
    cur.execute("SELECT pool_id, pool_code FROM pools WHERE state_id=%s", (wy_state_id,))
    existing_pools = {r[1]: r[0] for r in cur.fetchall()}
    if 'RES' not in existing_pools:
        cur.execute(
            "INSERT INTO pools (state_id, pool_code, description, allocation_pct, allocation_note) "
            "VALUES (%s, 'RES', 'Resident pool', 84.0, '~84%% of limited-quota tags') RETURNING pool_id",
            (wy_state_id,))
        existing_pools['RES'] = cur.fetchone()[0]
    if 'NR' not in existing_pools:
        cur.execute(
            "INSERT INTO pools (state_id, pool_code, description, allocation_pct, allocation_note) "
            "VALUES (%s, 'NR', 'Nonresident pool', 16.0, '~16%% elk / ~20%% deer NR allocation') RETURNING pool_id",
            (wy_state_id,))
        existing_pools['NR'] = cur.fetchone()[0]
    res_pool_id = existing_pools['RES']
    nr_pool_id = existing_pools['NR']
    print(f"Pools: RES={res_pool_id}, NR={nr_pool_id}")

    # Parse all draw PDFs
    draw_data = {}

    def merge_draw(area, typ, desc, filename, pool, apps, quota, issued=0, max_pts=0):
        hc = hunt_code_from(area, typ)
        if hc not in draw_data:
            draw_data[hc] = {
                'area': area.lstrip('0') or '0',
                'description': desc,
                'species_id': species_id_from_desc(desc, filename),
                'weapon_type_id': weapon_type_for_wy(desc),
                'res_apps': 0, 'res_quota': 0,
                'nr_apps': 0, 'nr_quota': 0, 'nr_issued': 0,
                'max_pts': 0,
            }
        if pool == 'RES':
            draw_data[hc]['res_apps'] += apps
            draw_data[hc]['res_quota'] = max(draw_data[hc]['res_quota'], quota)
        else:
            draw_data[hc]['nr_apps'] += apps
            draw_data[hc]['nr_quota'] = max(draw_data[hc]['nr_quota'], quota)
            draw_data[hc]['nr_issued'] += issued
        draw_data[hc]['max_pts'] = max(draw_data[hc]['max_pts'], max_pts)

    # NR Pref Points
    for fn in ['2025_elk_prefpoints_nonres.pdf', '2025_elk_prefpoints_nonres_special.pdf',
               '2025_deer_prefpoints_nonres.pdf', '2025_deer_prefpoints_nonres_special.pdf']:
        fpath = os.path.join(RAW_DIR, fn)
        if not os.path.exists(fpath):
            print(f"  SKIP: {fn}")
            continue
        print(f"  Parsing {fn}...")
        data = parse_prefpoints_pdf(fpath)
        for (area, typ), info in data.items():
            merge_draw(area, typ, info['description'], fn, 'NR',
                       info['total_apps'], info['quota'], info['total_issued'], info['max_pts'])
        print(f"    {len(data)} hunt codes")

    # Resident random
    for fn in ['2025_elk_random_res.pdf', '2025_deer_random_res.pdf']:
        fpath = os.path.join(RAW_DIR, fn)
        if not os.path.exists(fpath):
            print(f"  SKIP: {fn}")
            continue
        print(f"  Parsing {fn}...")
        data = parse_random_pdf(fpath)
        for row in data:
            merge_draw(row['area'], row['type'], row['description'], fn, 'RES',
                       row['first_choice_apps'], row['quota'])
        print(f"    {len(data)} rows")

    # Resident cow/calf and doe/fawn
    for fn in ['2025_elk_cowcalf_res.pdf', '2025_deer_doefawn_res.pdf']:
        fpath = os.path.join(RAW_DIR, fn)
        if not os.path.exists(fpath):
            continue
        print(f"  Parsing {fn}...")
        data = parse_random_pdf(fpath)
        for row in data:
            merge_draw(row['area'], row['type'], row['description'], fn, 'RES',
                       row['first_choice_apps'], row['quota'])
        print(f"    {len(data)} rows")

    # NR random — fill gaps
    for fn in ['2025_elk_random_nonres.pdf', '2025_elk_random_nonres_special.pdf',
               '2025_deer_random_nonres.pdf', '2025_deer_random_nonres_special.pdf']:
        fpath = os.path.join(RAW_DIR, fn)
        if not os.path.exists(fpath):
            continue
        print(f"  Parsing {fn} (NR random)...")
        data = parse_random_pdf(fpath)
        for row in data:
            hc = hunt_code_from(row['area'], row['type'])
            if hc not in draw_data:
                merge_draw(row['area'], row['type'], row['description'], fn, 'NR',
                           row['first_choice_apps'], row['quota'])
        print(f"    {len(data)} rows")

    # NR cow/calf and doe/fawn
    for fn in ['2025_elk_cowcalf_nonres.pdf', '2025_deer_doefawn_nonres.pdf']:
        fpath = os.path.join(RAW_DIR, fn)
        if not os.path.exists(fpath):
            continue
        print(f"  Parsing {fn}...")
        data = parse_random_pdf(fpath)
        for row in data:
            merge_draw(row['area'], row['type'], row['description'], fn, 'NR',
                       row['first_choice_apps'], row['quota'])
        print(f"    {len(data)} rows")

    # Leftover — just ensure hunt codes exist
    for fn in ['2025_elk_leftover_res.pdf', '2025_elk_leftover_nonres.pdf',
               '2025_deer_leftover_res.pdf', '2025_deer_leftover_nonres.pdf']:
        fpath = os.path.join(RAW_DIR, fn)
        if not os.path.exists(fpath):
            continue
        pool = 'RES' if '_res.' in fn else 'NR'
        data = parse_random_pdf(fpath)
        for row in data:
            hc = hunt_code_from(row['area'], row['type'])
            if hc not in draw_data:
                merge_draw(row['area'], row['type'], row['description'], fn, pool,
                           row['first_choice_apps'], row['quota'])

    print(f"\nTotal unique hunt codes from draw PDFs: {len(draw_data)}")

    # Hunt dates CSV
    csv_path = os.path.join(PROC_DIR, "WY_hunt_dates_2026.csv")
    csv_hunt_codes = set()
    csv_rows = []
    if os.path.exists(csv_path):
        with open(csv_path, newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                hc = row['hunt_code'].strip()
                csv_hunt_codes.add(hc)
                csv_rows.append(row)
        print(f"Hunt codes from CSV: {len(csv_hunt_codes)}")

    all_hunt_codes = set(draw_data.keys()) | csv_hunt_codes
    print(f"Total unique hunt codes (draw + CSV): {len(all_hunt_codes)}")

    # Extract areas for GMUs
    areas = {}
    for hc, info in draw_data.items():
        area = info['area']
        if area not in areas:
            areas[area] = info['description']
    for hc in csv_hunt_codes:
        area = hc.split('-')[0]
        if area not in areas:
            areas[area] = None

    # Insert GMUs
    gmu_map = {}
    cur.execute("SELECT gmu_id, gmu_code FROM gmus WHERE state_id=%s", (wy_state_id,))
    for r in cur.fetchall():
        gmu_map[r[1]] = r[0]

    gmus_new = 0
    for area_code in sorted(areas.keys(), key=lambda x: int(x) if x.isdigit() else 999):
        if area_code in gmu_map:
            continue
        cur.execute(
            "INSERT INTO gmus (state_id, gmu_code, gmu_name, gmu_sort_key) "
            "VALUES (%s, %s, %s, %s) RETURNING gmu_id",
            (wy_state_id, area_code, f"Hunt Area {area_code}", area_code.zfill(5)))
        gmu_map[area_code] = cur.fetchone()[0]
        gmus_new += 1
    print(f"GMUs: {len(gmu_map)} total ({gmus_new} new)")

    # Infer species/weapon for CSV-only hunt codes
    def infer_from_csv(csv_matches):
        for row in csv_matches:
            combined = ((row.get('bag_limit_description') or '') + ' ' +
                        (row.get('notes') or '')).lower()
            if 'elk' in combined:
                sp = 1
            elif 'white-tailed' in combined or 'whitetail' in combined:
                sp = 3
            elif 'deer' in combined:
                sp = 2
            else:
                sp = 1
            wt = 3 if 'archery' in combined else 1
            return sp, wt
        return 1, 1

    # Insert hunts
    hunt_map = {}
    cur.execute("SELECT hunt_id, hunt_code FROM hunts WHERE state_id=%s", (wy_state_id,))
    for r in cur.fetchall():
        hunt_map[r[1]] = r[0]

    hunts_inserted = 0
    for hc in sorted(all_hunt_codes):
        if hc in hunt_map:
            continue

        parts = hc.split('-', 1)
        area = parts[0]
        typ = parts[1] if len(parts) > 1 else ''

        if hc in draw_data:
            info = draw_data[hc]
            sp_id = info['species_id']
            wt_id = info['weapon_type_id']
            desc = info['description']
        else:
            csv_matches = [r for r in csv_rows if r['hunt_code'].strip() == hc]
            sp_id, wt_id = infer_from_csv(csv_matches)
            desc = csv_matches[0].get('bag_limit_description', '') if csv_matches else ''

        if hc.endswith('-ARCH'):
            wt_id = 3

        typ_clean = typ.replace('-ARCH', '')
        season_label = None
        if typ_clean in ('Gen', 'GEN'):
            season_label = 'General'
        elif typ_clean.isdigit():
            season_label = f'Type {typ_clean}'

        cur.execute(
            "INSERT INTO hunts (state_id, species_id, hunt_code, weapon_type_id, season_label, notes) "
            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING hunt_id",
            (wy_state_id, sp_id, hc, wt_id, season_label, desc[:500] if desc else None))
        hunt_map[hc] = cur.fetchone()[0]
        hunts_inserted += 1
    print(f"Hunts: {len(hunt_map)} total ({hunts_inserted} new)")

    # Insert hunt_gmus
    hg_inserted = 0
    cur.execute(
        "SELECT hg.hunt_id, hg.gmu_id FROM hunt_gmus hg "
        "JOIN hunts h ON h.hunt_id = hg.hunt_id WHERE h.state_id=%s", (wy_state_id,))
    existing_hg = set((r[0], r[1]) for r in cur.fetchall())

    for hc, hunt_id in hunt_map.items():
        area = hc.split('-')[0]
        gmu_id = gmu_map.get(area)
        if gmu_id and (hunt_id, gmu_id) not in existing_hg:
            cur.execute("INSERT INTO hunt_gmus (hunt_id, gmu_id) VALUES (%s, %s)", (hunt_id, gmu_id))
            hg_inserted += 1
    print(f"Hunt-GMU links: {hg_inserted} new")

    # Insert draw_results_by_pool
    draw_year = 2025
    dr_inserted = 0
    for hc, info in draw_data.items():
        hunt_id = hunt_map.get(hc)
        if not hunt_id:
            continue

        if info['res_apps'] > 0 or info['res_quota'] > 0:
            cur.execute(
                "INSERT INTO draw_results_by_pool "
                "(hunt_id, draw_year, pool_id, applications, tags_available) "
                "VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                (hunt_id, draw_year, res_pool_id,
                 info['res_apps'], info['res_quota'] if info['res_quota'] > 0 else None))
            dr_inserted += cur.rowcount

        if info['nr_apps'] > 0 or info['nr_quota'] > 0:
            tags_awarded = info['nr_issued'] if info['nr_issued'] > 0 else None
            max_pts = info['max_pts'] if info['max_pts'] > 0 else None
            cur.execute(
                "INSERT INTO draw_results_by_pool "
                "(hunt_id, draw_year, pool_id, applications, tags_available, tags_awarded, max_pts_held) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                (hunt_id, draw_year, nr_pool_id, info['nr_apps'],
                 info['nr_quota'] if info['nr_quota'] > 0 else None,
                 tags_awarded, max_pts))
            dr_inserted += cur.rowcount
    print(f"Draw results: {dr_inserted} new rows")

    # Harvest stats
    hs_inserted = 0
    for fn, species, harvest_year in [
        ('2025_elk_harvest_report.pdf', 'elk', 2025),
        ('2025_deer_harvest_report.pdf', 'deer', 2025),
        ('2024_elk_harvest_report.pdf', 'elk', 2024),
        ('2024_deer_harvest_report.pdf', 'deer', 2024),
    ]:
        fpath = os.path.join(RAW_DIR, fn)
        if not os.path.exists(fpath):
            print(f"  SKIP harvest: {fn}")
            continue
        print(f"  Parsing harvest: {fn}...")
        harvest_rows = parse_harvest_pdf(fpath, species)
        print(f"    {len(harvest_rows)} rows extracted")

        for hr in harvest_rows:
            area = hr['area']
            typ = hr['type']
            if typ == 'Total':
                candidates = [f"{area}-1", f"{area}-Gen", f"{area}-GEN"]
                hunt_id = None
                for c in candidates:
                    if c in hunt_map:
                        hunt_id = hunt_map[c]
                        break
                if not hunt_id:
                    for hc_key in hunt_map:
                        if hc_key.split('-')[0] == area:
                            hunt_id = hunt_map[hc_key]
                            break
            else:
                hc = hunt_code_from(area.zfill(3), typ)
                hunt_id = hunt_map.get(hc)

            if not hunt_id:
                continue

            success = hr['success_pct'] / 100.0 if hr['success_pct'] else None
            cur.execute(
                "INSERT INTO harvest_stats "
                "(hunt_id, harvest_year, success_rate, harvest_count, licenses_sold) "
                "VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                (hunt_id, harvest_year, success, hr['harvest_total'], hr['licenses_sold']))
            hs_inserted += cur.rowcount
    print(f"Harvest stats: {hs_inserted} new rows")

    # Hunt dates from CSV
    hd_inserted = 0
    if csv_rows:
        print(f"  Loading hunt dates ({len(csv_rows)} CSV rows)...")
        for row in csv_rows:
            hc = row['hunt_code'].strip()
            hunt_id = hunt_map.get(hc)
            if not hunt_id:
                continue

            start_date = row.get('open_date', '').strip() or None
            end_date = row.get('close_date', '').strip() or None
            notes = row.get('notes', '').strip() or None
            bag = row.get('bag_limit_description', '').strip() or None

            season_year = 2026
            if start_date:
                try:
                    season_year = int(start_date.split('-')[0])
                except (ValueError, IndexError):
                    pass

            cur.execute(
                "INSERT INTO hunt_dates "
                "(hunt_id, season_year, start_date, end_date, hunt_name, notes) "
                "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                (hunt_id, season_year, start_date, end_date, bag, notes))
            hd_inserted += cur.rowcount
    print(f"Hunt dates: {hd_inserted} new rows")

    conn.commit()
    print("\n── Committed. Final WY counts: ──")

    for table in ['hunts', 'gmus', 'hunt_gmus', 'draw_results_by_pool', 'harvest_stats', 'hunt_dates']:
        if table in ('hunts', 'gmus'):
            cur.execute(f"SELECT COUNT(*) FROM {table} WHERE state_id=%s", (wy_state_id,))
        else:
            cur.execute(
                f"SELECT COUNT(*) FROM {table} WHERE hunt_id IN "
                f"(SELECT hunt_id FROM hunts WHERE state_id=%s)", (wy_state_id,))
        print(f"  {table}: {cur.fetchone()[0]}")

    cur.close()
    conn.close()
    print("\nDone.")


if __name__ == '__main__':
    main()
