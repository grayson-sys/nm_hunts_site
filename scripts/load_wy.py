#!/usr/bin/env python3
"""
Wyoming data loader: hunts, GMUs, draw results, harvest stats, hunt dates.

Sources:
  - 2025 demand reports (elk + deer, random/prefpoints/leftover/cowcalf/doefawn)
  - 2024/2025 harvest reports (elk + deer)
  - WY/proclamations/2026/WY_hunt_dates_2026.csv
"""

import os
import re
import csv
import pdfplumber
import psycopg2

BASE_DIR = "/Users/openclaw/Documents/GraysonsDrawOdds"
DB_CONFIG = {
    'host': 'localhost', 'port': 5432,
    'dbname': 'draws', 'user': 'draws', 'password': 'drawspass'
}

# ── PDF Parsers ──────────────────────────────────────────────────────────────

def parse_demand_report(filepath):
    """Parse WY demand report (random/leftover/cowcalf/doefawn format).
    Fixed-width columns: Area, Type, Description, Quota, 1st Apps, 2nd Apps, 3rd Apps.
    Returns list of dicts with area, type, description, quota, apps_1st, apps_2nd, apps_3rd.
    """
    rows = []
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            for line in text.split('\n'):
                line = line.rstrip()
                if not line or line.startswith('Demand Report') or line.startswith('Resident') or \
                   line.startswith('Nonresident') or line.startswith('Leftover') or \
                   line.startswith('Fiscal') or line.startswith('Hunt') or \
                   line.startswith('Area') or line.startswith('----') or \
                   'Page:' in line or 'Time:' in line or 'Date:' in line or \
                   'Wyoming' in line:
                    continue
                # Match data lines: starts with a number (hunt area)
                m = re.match(r'^\s*(\d{1,3})\s+(\d+)\s+(.+?)\s{2,}([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s*$', line)
                if m:
                    rows.append({
                        'area': m.group(1).lstrip('0') or '0',
                        'type': m.group(2),
                        'description': m.group(3).strip(),
                        'quota': int(m.group(4).replace(',', '')),
                        'apps_1st': int(m.group(5).replace(',', '')),
                        'apps_2nd': int(m.group(6).replace(',', '')),
                        'apps_3rd': int(m.group(7).replace(',', '')),
                    })
    return rows


def parse_prefpoint_report(filepath):
    """Parse WY preference point demand report.
    Multi-row per hunt: first row has area/type/desc, continuation rows only have
    Quota(remaining), Issued, Points, Applicants, Success, Odds.
    Returns per-hunt aggregates: total_apps, total_drawn, min_pts_drawn, max_pts_held.
    """
    hunts = {}
    current_key = None

    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            for line in text.split('\n'):
                line = line.rstrip()
                if not line or 'Demand Report' in line or 'Preference Point' in line or \
                   'Fiscal' in line or 'Page:' in line or 'Time:' in line or \
                   'Date:' in line or 'Wyoming' in line or \
                   line.startswith('Hunt') or line.startswith('Area') or line.startswith('----'):
                    continue

                # Try to match a new hunt line (has area and type)
                m = re.match(
                    r'^\s*(\d{1,3})\s+(\d+)\s+(.+?)\s{2,}([\d,]+)\s+([\d,]+)\s+([\d<,]+)\s+([\d,]+)\s+([\d,.]+%?)\s*$',
                    line
                )
                if m:
                    area = m.group(1).lstrip('0') or '0'
                    htype = m.group(2)
                    current_key = f"{area}-{htype}"
                    if current_key not in hunts:
                        hunts[current_key] = {
                            'area': area, 'type': htype,
                            'description': m.group(3).strip(),
                            'quota': int(m.group(4).replace(',', '')),
                            'total_apps': 0, 'total_drawn': 0,
                            'min_pts_drawn': None, 'max_pts_held': None,
                        }
                    pts_str = m.group(6).strip()
                    pts = int(re.sub(r'[<>=,\s]', '', pts_str)) if re.search(r'\d', pts_str) else 0
                    apps = int(m.group(7).replace(',', ''))
                    # Parse success from odds field
                    odds_str = m.group(8).strip().replace('%', '')
                    try:
                        odds = float(odds_str)
                    except ValueError:
                        odds = 0.0
                    drawn = round(apps * odds / 100) if apps > 0 else 0

                    hunts[current_key]['total_apps'] += apps
                    hunts[current_key]['total_drawn'] += drawn
                    if drawn > 0:
                        if hunts[current_key]['min_pts_drawn'] is None or pts < hunts[current_key]['min_pts_drawn']:
                            hunts[current_key]['min_pts_drawn'] = pts
                    if hunts[current_key]['max_pts_held'] is None or pts > hunts[current_key]['max_pts_held']:
                        hunts[current_key]['max_pts_held'] = pts
                    continue

                # Continuation line (no area/type, just numbers)
                if current_key:
                    m2 = re.match(
                        r'^\s*([\d,]+)\s+([\d,]+)\s+([\d<>=,\s]+?)\s+([\d,]+)\s+([\d,.]+%?)\s*$',
                        line
                    )
                    if m2:
                        pts_str = m2.group(3).strip()
                        pts = int(re.sub(r'[<>=,\s]', '', pts_str)) if re.search(r'\d', pts_str) else 0
                        apps = int(m2.group(4).replace(',', ''))
                        odds_str = m2.group(5).strip().replace('%', '')
                        try:
                            odds = float(odds_str)
                        except ValueError:
                            odds = 0.0
                        drawn = round(apps * odds / 100) if apps > 0 else 0

                        hunts[current_key]['total_apps'] += apps
                        hunts[current_key]['total_drawn'] += drawn
                        if drawn > 0:
                            if hunts[current_key]['min_pts_drawn'] is None or pts < hunts[current_key]['min_pts_drawn']:
                                hunts[current_key]['min_pts_drawn'] = pts
                        if hunts[current_key]['max_pts_held'] is None or pts > hunts[current_key]['max_pts_held']:
                            hunts[current_key]['max_pts_held'] = pts

    return list(hunts.values())


def parse_harvest_report(filepath, species):
    """Parse WY harvest report Table 3 (elk) or Table 7/8 (deer).
    Returns list of dicts: area, type, active_hunters, total_harvest, success_rate, days_hunted.
    """
    rows = []
    in_table = False
    current_area = None

    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            # Look for Table 3 (elk) or Table 7/8 (deer)
            if species == 'ELK' and 'Table3' in text.replace(' ', ''):
                in_table = True
            elif species == 'MDR' and ('Table7' in text.replace(' ', '') or 'Table8' in text.replace(' ', '')):
                in_table = True
            # Also continue if we see the continuation header
            if 'HarvestStatisticsbyHuntArea' in text.replace(' ', ''):
                in_table = True

            if not in_table:
                continue

            for line in text.split('\n'):
                line = line.rstrip()
                if not line:
                    continue
                # Skip header lines
                if 'Table' in line and ('Continued' in line or 'Harvest' in line):
                    continue
                if 'Active' in line or 'HuntArea' in line or 'Lics/Htrs' in line:
                    continue
                if 'Summary' in line or 'Hunter' in line or 'Licenses' in line:
                    continue
                if line.startswith('in') or line.startswith('excludes') or line.startswith('"'):
                    continue

                # Detect hunt area header: starts with a number followed by name
                area_match = re.match(r'^(\d{1,3})\s*([A-Z][a-zA-Z].*)', line)
                if area_match:
                    current_area = area_match.group(1).lstrip('0') or '0'
                    continue

                if not current_area:
                    continue

                # Match type data row: Type ActiveLics Bull Spike Cow Calf Total Days Success Days/Harvest [LicsSold]
                # For elk: Type ActiveLics Bull Spike Cow Calf Total Days Success Days/Harvest
                # For deer: Type ActiveLics Buck Doe Fawn Total Days Success Days/Harvest
                # Type can be: 1, 2, 4, 6, 7, 8, 9, GEN, Total, Resident, Nonresident
                type_match = re.match(
                    r'^\s*(?:\([^)]+\)\s+)?(\d+|GEN)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d.]+)\s+([\d.]+)',
                    line
                )
                if type_match:
                    htype = type_match.group(1)
                    active = int(type_match.group(2).replace(',', ''))
                    total_harvest = int(type_match.group(6).replace(',', ''))
                    days = int(type_match.group(7).replace(',', ''))
                    try:
                        success = float(type_match.group(8))
                    except ValueError:
                        success = 0.0
                    rows.append({
                        'area': current_area,
                        'type': htype,
                        'active_hunters': active,
                        'total_harvest': total_harvest,
                        'success_rate': success,
                        'days_hunted': days,
                    })
                    continue

                # Check if line starts with Total/Resident/Nonresident (summary rows - skip)
                if line.strip().startswith('Total') or line.strip().startswith('Resident') or \
                   line.strip().startswith('Nonresident'):
                    continue

    return rows


# ── Helper functions ─────────────────────────────────────────────────────────

def infer_bag_limit(description, species):
    """Map WY description to bag_limit_id."""
    desc = (description or '').upper()
    if species == 'ELK':
        if 'COW OR CALF' in desc or 'COW/CALF' in desc:
            return 15  # COW
        if 'ANTLERLESS' in desc:
            return 15  # COW (antlerless elk)
        if 'ANTLERED' in desc:
            return 13  # BULL
        if 'ANY ELK' in desc:
            return 5   # ES (either sex)
        return 5  # default
    else:  # deer
        if 'DOE OR FAWN' in desc or 'DOE/FAWN' in desc:
            return 18  # DOE
        if 'ANTLERLESS' in desc:
            return 18  # DOE
        if 'ANTLERED' in desc:
            return 16  # BUCK
        if 'ANY WHITE-TAILED' in desc:
            return 6   # ESWTD
        if 'ANY MULE' in desc or 'ANY DEER' in desc:
            return 5   # ES
        return 16  # default deer = BUCK


def infer_weapon_type(htype, description):
    """Map WY hunt type and description to weapon_type_id."""
    desc = (description or '').upper()
    if 'ARCHERY' in desc:
        return 3  # ARCHERY
    if htype == '9':
        return 3  # Type 9 = archery only
    return 1  # ANY legal weapon


def infer_species_from_description(description):
    """Determine species from WY description text."""
    desc = (description or '').upper()
    if 'WHITE-TAILED' in desc or 'WHITETAIL' in desc:
        return 'WTD'
    if 'DEER' in desc or 'BUCK' in desc or 'DOE' in desc or 'FAWN' in desc:
        return 'MDR'
    return 'ELK'


def hunt_code_from_area_type(area, htype):
    """Build hunt code from area and type, stripping leading zeros."""
    area_clean = str(int(area))
    return f"{area_clean}-{htype}"


# ── Main loader ──────────────────────────────────────────────────────────────

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    # Get state_id
    cur.execute("SELECT state_id FROM states WHERE state_code='WY'")
    wy_id = cur.fetchone()[0]

    # Species map
    cur.execute("SELECT species_id, species_code FROM species")
    species_map = {r[1]: r[0] for r in cur.fetchall()}

    # Create WY pools
    for pool_code, desc, pct, note in [
        ('RES', 'Resident pool', 90.0, '~90% of tags'),
        ('NR', 'Nonresident pool', 10.0, '~10% of tags (regular license)'),
        ('NR_SPEC', 'Nonresident Special pool', None, 'NR special license pool (separate quota)'),
    ]:
        cur.execute("""
            INSERT INTO pools (state_id, pool_code, description, allocation_pct, allocation_note)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (state_id, pool_code) DO NOTHING
        """, (wy_id, pool_code, desc, pct, note))
    conn.commit()

    cur.execute("SELECT pool_id, pool_code FROM pools WHERE state_id = %s", (wy_id,))
    pool_map = {r[1]: r[0] for r in cur.fetchall()}

    # ── Define source files ─────────────────────────────────────────────────
    # (filepath, draw_year, species_code, pool_code, report_type)
    demand_sources = [
        # Elk random draw
        ('WY/raw_data/2025_elk_random_res.pdf', 2025, 'ELK', 'RES', 'demand'),
        ('WY/raw_data/2025_elk_random_nonres.pdf', 2025, 'ELK', 'NR', 'demand'),
        ('WY/raw_data/2025_elk_random_nonres_special.pdf', 2025, 'ELK', 'NR_SPEC', 'demand'),
        # Elk leftover
        ('WY/raw_data/2025_elk_leftover_res.pdf', 2025, 'ELK', 'RES', 'demand'),
        ('WY/raw_data/2025_elk_leftover_nonres.pdf', 2025, 'ELK', 'NR', 'demand'),
        # Elk cow/calf
        ('WY/raw_data/2025_elk_cowcalf_res.pdf', 2025, 'ELK', 'RES', 'demand'),
        ('WY/raw_data/2025_elk_cowcalf_nonres.pdf', 2025, 'ELK', 'NR', 'demand'),
        # Deer random draw
        ('WY/raw_data/2025_deer_random_res.pdf', 2025, 'MDR', 'RES', 'demand'),
        ('WY/raw_data/2025_deer_random_nonres.pdf', 2025, 'MDR', 'NR', 'demand'),
        ('WY/raw_data/2025_deer_random_nonres_special.pdf', 2025, 'MDR', 'NR_SPEC', 'demand'),
        # Deer leftover
        ('WY/raw_data/2025_deer_leftover_res.pdf', 2025, 'MDR', 'RES', 'demand'),
        ('WY/raw_data/2025_deer_leftover_nonres.pdf', 2025, 'MDR', 'NR', 'demand'),
        # Deer doe/fawn
        ('WY/raw_data/2025_deer_doefawn_res.pdf', 2025, 'MDR', 'RES', 'demand'),
        ('WY/raw_data/2025_deer_doefawn_nonres.pdf', 2025, 'MDR', 'NR', 'demand'),
    ]

    prefpoint_sources = [
        ('WY/raw_data/2025_elk_prefpoints_nonres.pdf', 2025, 'ELK', 'NR'),
        ('WY/raw_data/2025_elk_prefpoints_nonres_special.pdf', 2025, 'ELK', 'NR_SPEC'),
        ('WY/raw_data/2025_deer_prefpoints_nonres.pdf', 2025, 'MDR', 'NR'),
        ('WY/raw_data/2025_deer_prefpoints_nonres_special.pdf', 2025, 'MDR', 'NR_SPEC'),
    ]

    harvest_sources = [
        ('WY/raw_data/2024_elk_harvest_report.pdf', 2024, 'ELK'),
        ('WY/raw_data/2025_elk_harvest_report.pdf', 2025, 'ELK'),
        ('WY/raw_data/2024_deer_harvest_report.pdf', 2024, 'MDR'),
        ('WY/raw_data/2025_deer_harvest_report.pdf', 2025, 'MDR'),
    ]

    # Track all unique hunts and their data
    hunt_data = {}  # key = hunt_code → {species, description, ...}
    draw_results = []  # list of (hunt_code, year, pool, apps, quota, drawn, ...)
    prefpoint_data = {}  # key = (hunt_code, pool) → {min_pts, max_pts, ...}

    # ── Parse demand reports ────────────────────────────────────────────────
    total_demand_rows = 0
    for relpath, year, sp_code, pool_code, rtype in demand_sources:
        filepath = os.path.join(BASE_DIR, relpath)
        if not os.path.exists(filepath):
            print(f"  SKIP (missing): {relpath}")
            continue

        rows = parse_demand_report(filepath)
        print(f"  {os.path.basename(relpath)}: {len(rows)} rows parsed")
        total_demand_rows += len(rows)

        for r in rows:
            hcode = hunt_code_from_area_type(r['area'], r['type'])
            # Determine actual species from description if it's WTD
            actual_sp = sp_code
            if sp_code == 'MDR':
                desc_sp = infer_species_from_description(r['description'])
                if desc_sp == 'WTD':
                    actual_sp = 'WTD'

            if hcode not in hunt_data:
                hunt_data[hcode] = {
                    'area': r['area'],
                    'type': r['type'],
                    'species': actual_sp,
                    'description': r['description'],
                }

            # Only store 1st choice applications (what matters for draw odds)
            if r['apps_1st'] > 0 or r['quota'] > 0:
                draw_results.append({
                    'hunt_code': hcode,
                    'year': year,
                    'pool': pool_code,
                    'applications': r['apps_1st'],
                    'tags_available': r['quota'],
                    'tags_awarded': None,
                })

    # ── Parse preference point reports ──────────────────────────────────────
    for relpath, year, sp_code, pool_code in prefpoint_sources:
        filepath = os.path.join(BASE_DIR, relpath)
        if not os.path.exists(filepath):
            print(f"  SKIP (missing): {relpath}")
            continue

        hunts = parse_prefpoint_report(filepath)
        print(f"  {os.path.basename(relpath)}: {len(hunts)} hunts parsed")

        for h in hunts:
            hcode = hunt_code_from_area_type(h['area'], h['type'])
            actual_sp = sp_code
            if sp_code == 'MDR':
                desc_sp = infer_species_from_description(h['description'])
                if desc_sp == 'WTD':
                    actual_sp = 'WTD'

            if hcode not in hunt_data:
                hunt_data[hcode] = {
                    'area': h['area'],
                    'type': h['type'],
                    'species': actual_sp,
                    'description': h['description'],
                }

            # Store pref point info for later enrichment
            key = (hcode, pool_code)
            prefpoint_data[key] = {
                'total_apps': h['total_apps'],
                'total_drawn': h['total_drawn'],
                'min_pts_drawn': h['min_pts_drawn'],
                'max_pts_held': h['max_pts_held'],
                'quota': h['quota'],
            }

    print(f"\n  Total unique hunts from draw data: {len(hunt_data)}")
    print(f"  Total draw result rows: {len(draw_results)}")
    print(f"  Pref point data entries: {len(prefpoint_data)}")

    # ── Insert GMUs and Hunts ───────────────────────────────────────────────
    gmu_count = 0
    hunt_count = 0
    hunt_id_map = {}  # hunt_code → hunt_id

    # Also load hunt codes from proclamation CSV that aren't in draw data
    proc_csv = os.path.join(BASE_DIR, 'WY/proclamations/2026/WY_hunt_dates_2026.csv')
    proc_hunts = {}
    if os.path.exists(proc_csv):
        with open(proc_csv) as f:
            reader = csv.DictReader(f)
            for row in reader:
                hc = row['hunt_code'].strip()
                proc_hunts[hc] = row

    # Merge: for hunts in draw data, use draw data info; also add proclamation-only hunts
    all_hunt_codes = set(hunt_data.keys()) | set(proc_hunts.keys())
    print(f"  Total unique hunt codes (draw + proclamation): {len(all_hunt_codes)}")

    for hcode in sorted(all_hunt_codes):
        # Determine species, bag limit, weapon type
        if hcode in hunt_data:
            hd = hunt_data[hcode]
            sp_code = hd['species']
            description = hd['description']
            area = hd['area']
            htype = hd['type']
        else:
            # Parse from proclamation hunt code
            parts = hcode.split('-')
            area = parts[0]
            htype = parts[1] if len(parts) > 1 else '1'
            description = ''
            # Infer species from proclamation bag_limit_description
            bag_desc = proc_hunts[hcode].get('bag_limit_description', '') if hcode in proc_hunts else ''
            if 'elk' in bag_desc.lower():
                sp_code = 'ELK'
            elif 'deer' in bag_desc.lower() or 'buck' in bag_desc.lower() or 'doe' in bag_desc.lower():
                sp_code = 'MDR'
            else:
                sp_code = 'ELK'  # default

        species_id = species_map.get(sp_code, species_map.get('ELK'))
        bag_limit_id = infer_bag_limit(description, sp_code)
        weapon_type_id = infer_weapon_type(htype, description)

        # If hunt code ends with -ARCH, it's an archery season variant
        if hcode.endswith('-ARCH'):
            weapon_type_id = 3

        # GMU from area
        gmu_code = area
        gmu_name = f"Hunt Area {area}"
        gmu_sort_key = area.zfill(5)

        cur.execute("""
            INSERT INTO gmus (state_id, gmu_code, gmu_name, gmu_sort_key)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (state_id, gmu_code) DO UPDATE SET gmu_name = EXCLUDED.gmu_name
            RETURNING gmu_id
        """, (wy_id, gmu_code, gmu_name, gmu_sort_key))
        gmu_id = cur.fetchone()[0]
        gmu_count += 1

        # Determine season_type and tag_type
        season_type = 'controlled'
        tag_type = 'LE'
        if htype == 'Gen' or htype == 'GEN':
            season_type = 'general'
            tag_type = 'GEN'

        # Get display info from proclamation if available
        notes = None
        if hcode in proc_hunts:
            bag_desc = proc_hunts[hcode].get('bag_limit_description', '')
            pnotes = proc_hunts[hcode].get('notes', '')
            if bag_desc:
                notes = bag_desc
            if pnotes:
                notes = f"{notes}; {pnotes}" if notes else pnotes

        cur.execute("""
            INSERT INTO hunts (state_id, species_id, hunt_code, hunt_code_display,
                weapon_type_id, bag_limit_id, season_type, tag_type, is_active,
                unit_description, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1, %s, %s)
            ON CONFLICT (state_id, hunt_code) DO UPDATE SET
                weapon_type_id = EXCLUDED.weapon_type_id,
                bag_limit_id = EXCLUDED.bag_limit_id,
                season_type = EXCLUDED.season_type,
                unit_description = EXCLUDED.unit_description,
                notes = EXCLUDED.notes
            RETURNING hunt_id
        """, (wy_id, species_id, hcode, hcode, weapon_type_id, bag_limit_id,
              season_type, tag_type, gmu_name, notes))
        hunt_id = cur.fetchone()[0]
        hunt_id_map[hcode] = hunt_id
        hunt_count += 1

        # Link hunt to GMU
        cur.execute("""
            INSERT INTO hunt_gmus (hunt_id, gmu_id) VALUES (%s, %s)
            ON CONFLICT (hunt_id, gmu_id) DO NOTHING
        """, (hunt_id, gmu_id))

    conn.commit()
    print(f"\n  Inserted {hunt_count} hunts, {gmu_count} GMU upserts")

    # ── Insert draw results ─────────────────────────────────────────────────
    draw_count = 0
    # Aggregate draw results by (hunt_code, year, pool) - sum applications and quota
    from collections import defaultdict
    agg = defaultdict(lambda: {'applications': 0, 'tags_available': 0})
    for dr in draw_results:
        key = (dr['hunt_code'], dr['year'], dr['pool'])
        agg[key]['applications'] += dr['applications']
        agg[key]['tags_available'] = max(agg[key]['tags_available'], dr['tags_available'])

    for (hcode, year, pool_code), vals in agg.items():
        if hcode not in hunt_id_map:
            continue
        hunt_id = hunt_id_map[hcode]
        pool_id = pool_map.get(pool_code)
        if not pool_id:
            continue
        apps = vals['applications']
        quota = vals['tags_available']
        if apps == 0 and quota == 0:
            continue

        # Enrich with pref point data if available
        pp = prefpoint_data.get((hcode, pool_code), {})
        min_pts = pp.get('min_pts_drawn')
        max_pts = pp.get('max_pts_held')
        tags_awarded = pp.get('total_drawn')

        # For NR pools, use pref point total_apps if larger (it includes all NR applicants)
        pp_apps = pp.get('total_apps', 0)
        if pp_apps > apps:
            apps = pp_apps

        cur.execute("""
            INSERT INTO draw_results_by_pool
                (hunt_id, draw_year, pool_id, applications, tags_available,
                 tags_awarded, min_pts_drawn, max_pts_held)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (hunt_id, draw_year, pool_id) DO UPDATE SET
                applications = EXCLUDED.applications,
                tags_available = EXCLUDED.tags_available,
                tags_awarded = COALESCE(EXCLUDED.tags_awarded, draw_results_by_pool.tags_awarded),
                min_pts_drawn = COALESCE(EXCLUDED.min_pts_drawn, draw_results_by_pool.min_pts_drawn),
                max_pts_held = COALESCE(EXCLUDED.max_pts_held, draw_results_by_pool.max_pts_held)
        """, (hunt_id, year, pool_id, apps, quota, tags_awarded, min_pts, max_pts))
        draw_count += 1

    # Also insert pref-point-only entries (hunts that only appear in pref point reports)
    for (hcode, pool_code), pp in prefpoint_data.items():
        key = (hcode, 2025, pool_code)
        if key in agg:
            continue  # already handled
        if hcode not in hunt_id_map:
            continue
        hunt_id = hunt_id_map[hcode]
        pool_id = pool_map.get(pool_code)
        if not pool_id:
            continue

        cur.execute("""
            INSERT INTO draw_results_by_pool
                (hunt_id, draw_year, pool_id, applications, tags_available,
                 tags_awarded, min_pts_drawn, max_pts_held)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (hunt_id, draw_year, pool_id) DO UPDATE SET
                applications = EXCLUDED.applications,
                tags_available = EXCLUDED.tags_available,
                tags_awarded = COALESCE(EXCLUDED.tags_awarded, draw_results_by_pool.tags_awarded),
                min_pts_drawn = COALESCE(EXCLUDED.min_pts_drawn, draw_results_by_pool.min_pts_drawn),
                max_pts_held = COALESCE(EXCLUDED.max_pts_held, draw_results_by_pool.max_pts_held)
        """, (hunt_id, 2025, pool_id, pp['total_apps'], pp['quota'],
              pp['total_drawn'], pp['min_pts_drawn'], pp['max_pts_held']))
        draw_count += 1

    conn.commit()
    print(f"  Inserted {draw_count} draw result rows")

    # ── Load harvest data ───────────────────────────────────────────────────
    harvest_count = 0
    for relpath, year, sp_code in harvest_sources:
        filepath = os.path.join(BASE_DIR, relpath)
        if not os.path.exists(filepath):
            print(f"  SKIP harvest (missing): {relpath}")
            continue

        rows = parse_harvest_report(filepath, sp_code)
        print(f"  {os.path.basename(relpath)}: {len(rows)} harvest rows parsed")

        for r in rows:
            hcode = hunt_code_from_area_type(r['area'], r['type'])
            if hcode not in hunt_id_map:
                # Try with Gen
                if r['type'] == 'GEN':
                    hcode = f"{r['area']}-Gen"
                if hcode not in hunt_id_map:
                    continue

            hunt_id = hunt_id_map[hcode]
            cur.execute("""
                INSERT INTO harvest_stats
                    (hunt_id, harvest_year, success_rate, days_hunted,
                     licenses_sold, harvest_count)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (hunt_id, harvest_year, access_type) DO UPDATE SET
                    success_rate = EXCLUDED.success_rate,
                    days_hunted = EXCLUDED.days_hunted,
                    licenses_sold = EXCLUDED.licenses_sold,
                    harvest_count = EXCLUDED.harvest_count
            """, (hunt_id, year, r['success_rate'], r['days_hunted'],
                  r['active_hunters'], r['total_harvest']))
            harvest_count += 1

    conn.commit()
    print(f"  Inserted {harvest_count} harvest rows")

    # ── Load hunt dates ─────────────────────────────────────────────────────
    dates_loaded = 0
    dates_unmatched = 0
    if os.path.exists(proc_csv):
        with open(proc_csv) as f:
            reader = csv.DictReader(f)
            for row in reader:
                hc = row['hunt_code'].strip()
                if hc in hunt_id_map:
                    hunt_id = hunt_id_map[hc]
                    start = row.get('open_date', '').strip()
                    end = row.get('close_date', '').strip()
                    if not start or not end:
                        continue
                    notes = row.get('notes', '').strip()
                    cur.execute("""
                        INSERT INTO hunt_dates (hunt_id, season_year, start_date, end_date, notes)
                        VALUES (%s, 2026, %s, %s, %s)
                        ON CONFLICT (hunt_id, season_year) DO UPDATE SET
                            start_date = EXCLUDED.start_date,
                            end_date = EXCLUDED.end_date,
                            notes = EXCLUDED.notes
                    """, (hunt_id, start, end, notes))
                    dates_loaded += 1
                else:
                    dates_unmatched += 1
        conn.commit()

    # ── Summary ─────────────────────────────────────────────────────────────
    print("\n=== WY LOAD SUMMARY ===")
    cur.execute("SELECT COUNT(*) FROM hunts WHERE state_id = %s", (wy_id,))
    print(f"  Hunts:        {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(*) FROM gmus WHERE state_id = %s", (wy_id,))
    print(f"  GMUs:         {cur.fetchone()[0]}")
    cur.execute("""SELECT COUNT(*) FROM draw_results_by_pool dr
                   JOIN hunts h ON h.hunt_id = dr.hunt_id WHERE h.state_id = %s""", (wy_id,))
    print(f"  Draw results: {cur.fetchone()[0]}")
    cur.execute("""SELECT COUNT(*) FROM harvest_stats hs
                   JOIN hunts h ON h.hunt_id = hs.hunt_id WHERE h.state_id = %s""", (wy_id,))
    print(f"  Harvest rows: {cur.fetchone()[0]}")
    cur.execute("""SELECT COUNT(*) FROM hunt_dates hd
                   JOIN hunts h ON h.hunt_id = hd.hunt_id WHERE h.state_id = %s""", (wy_id,))
    print(f"  Hunt dates:   {cur.fetchone()[0]}")
    print(f"  Dates loaded: {dates_loaded}, unmatched: {dates_unmatched}")

    conn.close()
    print("\nWY load complete.")


if __name__ == '__main__':
    main()
