#!/usr/bin/env python3
"""
Utah data loader: hunts, GMUs, draw results, harvest stats.

Sources:
  - 2024/2025 draw odds PDFs (general deer, LE/OIAL, antlerless, dedicated hunter, youth elk)
  - 2024 harvest PDFs (general deer, LE/OIAL, antlerless)
  - UT/proclamations/2026/UT_hunt_dates_2026.csv (all DO_NOT_LOAD — skipped)
"""

import os
import re
import pdfplumber
import psycopg2

BASE_DIR = "/Users/openclaw/Documents/GraysonsDrawOdds"
DB_CONFIG = {
    'host': 'localhost', 'port': 5432,
    'dbname': 'draws', 'user': 'draws', 'password': 'drawspass'
}

# UT hunt code prefixes → (species_code, bag_code)
HUNT_PREFIX_MAP = {
    'DB': ('MDR', 'BUCK'),
    'DA': ('MDR', 'DOE'),
    'EB': ('ELK', 'BULL'),
    'EA': ('ELK', 'COW'),
    'BI': (None, None),   # Bison — skip
    'MO': (None, None),   # Moose — skip
    'MG': (None, None),   # Mountain Goat — skip
    'RS': (None, None),   # Rocky Mtn Bighorn Sheep — skip
    'DS': (None, None),   # Desert Bighorn Sheep — skip
    'PB': (None, None),   # Pronghorn — skip (not in species table)
}


def parse_weapon(name):
    """Infer weapon_type_id from hunt name."""
    name_l = (name or '').lower()
    if 'archery' in name_l or 'bow' in name_l:
        return 3  # ARCHERY
    if 'muzzleloader' in name_l or 'mzldr' in name_l:
        return 4  # MUZZ
    if 'any legal weapon' in name_l or 'rifle' in name_l or 'alw' in name_l:
        return 1  # ANY
    if 'shotgun' in name_l or 'shotgn' in name_l:
        return 6  # SHOTGUN
    return 1  # default ANY


def extract_gmu_name(hunt_name):
    """Extract unit/GMU name from UT hunt name.
    E.g., 'Premium Le Archery Buck Deer - Henry Mtns - Archery' → 'Henry Mtns'
    Or 'Box Elder - Archery' → 'Box Elder'
    Or 'Antlerless Deer - Box Elder, West Bear River - Archery, Mzldr, Shotgn Only' → 'Box Elder, West Bear River'
    """
    if not hunt_name:
        return None
    # Strip species prefix patterns
    name = re.sub(
        r'^(?:Premium\s+)?(?:Le\s+)?(?:Alw\s+\([^)]*\)\s+)?'
        r'(?:Limited Entry(?:\s+on\s+General\s+Season)?\s+)?'
        r'(?:Cactus\s+)?'
        r'(?:Buck\s+Deer|Antlerless\s+(?:Deer|Elk)|Bull\s+Elk|Cow\s+Elk|Draw-only\s+Youth\s+(?:Elk|Any\s+Bull[^-]*))\s*-\s*',
        '', hunt_name, flags=re.IGNORECASE
    ).strip()
    # Split on ' - ' to separate unit from weapon
    parts = [p.strip() for p in name.split(' - ')]
    if len(parts) >= 2:
        return parts[0]
    return parts[0] if parts[0] else hunt_name


def parse_season_label(hunt_name, hunt_code, source_label=None):
    """Derive season label from source file context and hunt name."""
    name_l = (hunt_name or '').lower()
    if source_label:
        # Refine within source category
        if 'premium' in name_l:
            return 'Premium LE'
        if 'limited entry on general season' in name_l:
            return 'LE on GS'
        if 'cactus' in name_l:
            return 'Cactus Buck'
        return source_label
    # Fallback: infer from hunt name
    if 'premium' in name_l:
        return 'Premium LE'
    if 'limited entry' in name_l:
        return 'Limited Entry'
    if 'youth' in name_l:
        return 'Youth'
    if 'antlerless' in name_l:
        return 'Antlerless'
    return 'General Season'


def parse_draw_odds_pdf(filepath):
    """Parse a UT draw odds PDF. Returns list of dicts with hunt-level totals.
    Each page (except page 1 summary) is one hunt with point-level breakdown.
    """
    hunts = []
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ''
            # Look for hunt header: "Hunt: XX#### HuntName"
            m = re.search(r'Hunt:\s+(\w+)\s+(.*?)(?:\n|$)', text)
            if not m:
                continue
            hunt_code = m.group(1).strip()
            hunt_name = m.group(2).strip()

            # Sum applicants and permits from the table
            table = page.extract_table()
            if not table:
                continue

            res_apps = 0
            res_permits = 0
            nr_apps = 0
            nr_permits = 0

            for row in table:
                if not row or len(row) < 10:
                    continue
                try:
                    # Resident side: cols 0=pts, 1=applicants, ... 3 or 4=total permits
                    # NR side starts at col 6 or 8 depending on PDF variant
                    r_apps = safe_int(row[1])
                    r_total = safe_int(row[4]) if len(row) > 4 else safe_int(row[3])
                    res_apps += r_apps
                    res_permits += r_total

                    # Find NR columns - they mirror the resident side
                    # In 12-col format: NR at cols 6,7,8,9,10,11
                    # In 16-col format: NR at cols 8,9,10,11,12,13
                    nr_offset = len(row) // 2
                    if nr_offset >= 6:
                        n_apps = safe_int(row[nr_offset + 1])
                        n_total = safe_int(row[nr_offset + 4]) if len(row) > nr_offset + 4 else safe_int(row[nr_offset + 3])
                    else:
                        n_apps = safe_int(row[6]) if len(row) > 6 else 0
                        n_total = safe_int(row[9]) if len(row) > 9 else safe_int(row[8]) if len(row) > 8 else 0
                    nr_apps += n_apps
                    nr_permits += n_total
                except (ValueError, IndexError):
                    continue

            hunts.append({
                'hunt_code': hunt_code,
                'hunt_name': hunt_name,
                'res_apps': res_apps,
                'res_permits': res_permits,
                'nr_apps': nr_apps,
                'nr_permits': nr_permits,
            })
    return hunts


def safe_int(val):
    if val is None:
        return 0
    s = str(val).strip().replace(',', '')
    if s in ('', 'N/A', '-'):
        return 0
    try:
        return int(s)
    except ValueError:
        return 0


def parse_harvest_pdf(filepath):
    """Parse a UT harvest report PDF. Returns list of dicts."""
    records = []
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ''
            lines = text.split('\n')

            for line in lines:
                # Match lines starting with a hunt code like DB1500, EA1030, etc.
                m = re.match(
                    r'^(?:[\w\s]+?\s+)?'  # optional species prefix (e.g., "Antlerless Deer ")
                    r'([A-Z]{2}\d{4})\s+'  # hunt code
                    r'(.+?)\s+'            # hunt name
                    r'(General Season|Premium Limited Entry|Limited Entry(?:\s+on\s+General\s+Season)?|OIAL|Cactus Buck)\s+'  # hunt type
                    r'(Any Legal Weapon|Archery|Muzzleloader|Rifle|Shotgun)\s+'  # weapon
                    r'(\d+)\s+'            # permits
                    r'(\d+)\s+'            # hunters afield
                    r'(\d+)\s+'            # harvest
                    r'([\d.]+)\s+'         # avg days
                    r'([\d.]+)\s+'         # percent success
                    r'([\d.]+)',           # satisfaction
                    line
                )
                if m:
                    records.append({
                        'hunt_code': m.group(1),
                        'hunt_name': m.group(2).strip(),
                        'hunt_type': m.group(3).strip(),
                        'weapon': m.group(4).strip(),
                        'permits': int(m.group(5)),
                        'hunters_afield': int(m.group(6)),
                        'harvest': int(m.group(7)),
                        'avg_days': float(m.group(8)),
                        'success_pct': float(m.group(9)),
                        'satisfaction': float(m.group(10)),
                    })
    return records


def parse_antlerless_harvest(filepath):
    """Parse antlerless harvest PDF which has Species column first."""
    records = []
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ''
            for line in text.split('\n'):
                m = re.match(
                    r'^(?:Antlerless\s+(?:Deer|Elk))\s+'
                    r'([A-Z]{2}\d{4})\s+'
                    r'(.+?)\s+'
                    r'(Any Legal Weapon|Archery|Muzzleloader|Rifle|Shotgun|Archery, Mzldr, Shotgn Only)\s+'
                    r'(\d+)\s+'
                    r'(\d+)\s+'
                    r'(\d+)\s+'
                    r'([\d.]+)\s+'
                    r'([\d.]+)',
                    line
                )
                if m:
                    records.append({
                        'hunt_code': m.group(1),
                        'hunt_name': m.group(2).strip(),
                        'weapon': m.group(3).strip(),
                        'permits': int(m.group(4)),
                        'hunters_afield': int(m.group(5)),
                        'harvest': int(m.group(6)),
                        'avg_days': float(m.group(7)),
                        'success_pct': float(m.group(8)),
                    })
    return records


def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    # Get UT state_id
    cur.execute("SELECT state_id FROM states WHERE state_code='UT'")
    ut_state_id = cur.fetchone()[0]
    print(f"UT state_id: {ut_state_id}")

    # Species map
    cur.execute("SELECT species_id, species_code FROM species")
    species_map = {r[1]: r[0] for r in cur.fetchall()}

    # Bag limit map
    cur.execute("SELECT bag_limit_id, bag_code FROM bag_limits")
    bag_limit_map = {r[1]: r[0] for r in cur.fetchall()}

    # Create UT pools
    for pool_code, desc, pct, note in [
        ('RES', 'Resident pool', 90.0, '~90% of tags'),
        ('NR', 'Nonresident pool', 10.0, '~10% of tags'),
    ]:
        cur.execute("""
            INSERT INTO pools (state_id, pool_code, description, allocation_pct, allocation_note)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (state_id, pool_code) DO NOTHING
        """, (ut_state_id, pool_code, desc, pct, note))

    cur.execute("SELECT pool_id, pool_code FROM pools WHERE state_id = %s", (ut_state_id,))
    pool_map = {r[1]: r[0] for r in cur.fetchall()}
    conn.commit()

    # ===== PARSE DRAW ODDS PDFs =====
    # (filepath, year, source_label)
    draw_sources = [
        ('UT/raw_data/25_deer_odds.pdf', 2025, 'General Season'),
        ('UT/raw_data/25_bg-odds.pdf', 2025, 'Limited Entry'),
        ('UT/raw_data/25_antlerless_drawing_odds_report.pdf', 2025, 'Antlerless'),
        ('UT/raw_data/25_dh_odds.pdf', 2025, 'Dedicated Hunter'),
        ('UT/raw_data/25_youth_elk.pdf', 2025, 'Youth'),
        ('UT/raw_data/24_deer_odds.pdf', 2024, 'General Season'),
        ('UT/raw_data/24_bg-odds.pdf', 2024, 'Limited Entry'),
        ('UT/raw_data/24_youth_elk.pdf', 2024, 'Youth'),
    ]

    all_draw_hunts = {}  # hunt_code → {hunt_name, source_label, ...}
    draw_results = []    # (hunt_code, year, res_apps, res_permits, nr_apps, nr_permits)

    for relpath, year, source_label in draw_sources:
        filepath = os.path.join(BASE_DIR, relpath)
        if not os.path.exists(filepath):
            print(f"  SKIP (missing): {relpath}")
            continue
        print(f"Parsing {relpath}...")
        hunts = parse_draw_odds_pdf(filepath)
        print(f"  → {len(hunts)} hunts found")
        for h in hunts:
            code = h['hunt_code']
            h['source_label'] = source_label
            if code not in all_draw_hunts:
                all_draw_hunts[code] = h
            draw_results.append((code, year, h['res_apps'], h['res_permits'],
                                 h['nr_apps'], h['nr_permits']))

    # ===== PARSE HARVEST PDFs =====
    harvest_records = []

    # General season buck deer harvest
    gs_deer_path = os.path.join(BASE_DIR, 'UT/raw_data/2024_gs_buck_deer_hr.pdf')
    if os.path.exists(gs_deer_path):
        print(f"Parsing 2024_gs_buck_deer_hr.pdf...")
        recs = parse_harvest_pdf(gs_deer_path)
        print(f"  → {len(recs)} records")
        harvest_records.extend(recs)

    # LE/OIAL harvest
    le_path = os.path.join(BASE_DIR, 'UT/raw_data/2024_le_oial_all.pdf')
    if os.path.exists(le_path):
        print(f"Parsing 2024_le_oial_all.pdf...")
        recs = parse_harvest_pdf(le_path)
        print(f"  → {len(recs)} records")
        harvest_records.extend(recs)

    # Antlerless harvest
    al_path = os.path.join(BASE_DIR, 'UT/raw_data/2024_antlerless_hr.pdf')
    if os.path.exists(al_path):
        print(f"Parsing 2024_antlerless_hr.pdf...")
        recs = parse_antlerless_harvest(al_path)
        print(f"  → {len(recs)} records")
        harvest_records.extend(recs)

    # Add harvest hunt codes to all_draw_hunts if not already present
    for rec in harvest_records:
        code = rec['hunt_code']
        if code not in all_draw_hunts:
            all_draw_hunts[code] = {
                'hunt_code': code,
                'hunt_name': rec['hunt_name'] + ' - ' + rec['weapon'],
            }

    # ===== INSERT HUNTS, GMUs, DRAW RESULTS, HARVEST =====
    hunt_id_map = {}  # hunt_code → hunt_id
    gmu_cache = {}    # gmu_code → gmu_id
    skipped_species = set()

    for code, info in sorted(all_draw_hunts.items()):
        prefix = code[:2]
        mapping = HUNT_PREFIX_MAP.get(prefix)
        if not mapping or mapping[0] is None:
            skipped_species.add(prefix)
            continue

        species_code, bag_code = mapping
        species_id = species_map.get(species_code)
        if not species_id:
            continue
        bag_limit_id = bag_limit_map.get(bag_code, 5)  # default ES
        hunt_name = info.get('hunt_name', '')
        weapon_type_id = parse_weapon(hunt_name)
        gmu_name = extract_gmu_name(hunt_name)
        source_label = info.get('source_label')
        season_label = parse_season_label(hunt_name, code, source_label)

        # GMU code = unit name (UT uses unit names not numbers)
        gmu_code = gmu_name or code
        # Normalize gmu_code
        gmu_code = gmu_code[:80]
        gmu_sort_key = gmu_code.lower().ljust(20)[:20]

        if gmu_code not in gmu_cache:
            cur.execute("""
                INSERT INTO gmus (state_id, gmu_code, gmu_name, gmu_sort_key)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (state_id, gmu_code) DO UPDATE SET gmu_name = EXCLUDED.gmu_name
                RETURNING gmu_id
            """, (ut_state_id, gmu_code, gmu_name, gmu_sort_key))
            gmu_cache[gmu_code] = cur.fetchone()[0]
        gmu_id = gmu_cache[gmu_code]

        # Insert hunt
        cur.execute("""
            INSERT INTO hunts (state_id, species_id, hunt_code, hunt_code_display,
                weapon_type_id, bag_limit_id, season_type, tag_type, is_active,
                unit_description, season_label)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1, %s, %s)
            ON CONFLICT (state_id, hunt_code) DO UPDATE SET
                weapon_type_id = EXCLUDED.weapon_type_id,
                bag_limit_id = EXCLUDED.bag_limit_id,
                season_label = EXCLUDED.season_label,
                unit_description = EXCLUDED.unit_description
            RETURNING hunt_id
        """, (ut_state_id, species_id, code, code,
              weapon_type_id, bag_limit_id, 'controlled', 'LE',
              gmu_name, season_label))
        hunt_id = cur.fetchone()[0]
        hunt_id_map[code] = hunt_id

        # Link hunt to GMU
        cur.execute("""
            INSERT INTO hunt_gmus (hunt_id, gmu_id) VALUES (%s, %s)
            ON CONFLICT (hunt_id, gmu_id) DO NOTHING
        """, (hunt_id, gmu_id))

    conn.commit()
    print(f"\nInserted {len(hunt_id_map)} hunts, {len(gmu_cache)} GMUs")
    if skipped_species:
        print(f"Skipped species prefixes: {skipped_species}")

    # ===== INSERT DRAW RESULTS =====
    draw_count = 0
    draw_skip = 0
    for code, year, res_apps, res_permits, nr_apps, nr_permits in draw_results:
        hunt_id = hunt_id_map.get(code)
        if not hunt_id:
            draw_skip += 1
            continue

        for pool_code, apps, awarded in [('RES', res_apps, res_permits),
                                          ('NR', nr_apps, nr_permits)]:
            if apps == 0 and awarded == 0:
                continue
            pool_id = pool_map[pool_code]
            cur.execute("""
                INSERT INTO draw_results_by_pool
                    (hunt_id, draw_year, pool_id, applications, tags_awarded)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (hunt_id, draw_year, pool_id) DO UPDATE SET
                    applications = EXCLUDED.applications,
                    tags_awarded = EXCLUDED.tags_awarded
            """, (hunt_id, year, pool_id, apps, awarded))
            draw_count += 1

    conn.commit()
    print(f"Inserted {draw_count} draw result rows (skipped {draw_skip} non-deer/elk)")

    # ===== INSERT HARVEST STATS =====
    harvest_count = 0
    harvest_skip = 0
    for rec in harvest_records:
        hunt_id = hunt_id_map.get(rec['hunt_code'])
        if not hunt_id:
            harvest_skip += 1
            continue

        success_rate = rec['success_pct'] / 100.0 if rec['success_pct'] > 1 else rec['success_pct']

        cur.execute("""
            INSERT INTO harvest_stats
                (hunt_id, harvest_year, access_type, success_rate, licenses_sold,
                 harvest_count, days_hunted)
            VALUES (%s, 2024, %s, %s, %s, %s, %s)
            ON CONFLICT (hunt_id, harvest_year, access_type) DO UPDATE SET
                success_rate = EXCLUDED.success_rate,
                licenses_sold = EXCLUDED.licenses_sold,
                harvest_count = EXCLUDED.harvest_count,
                days_hunted = EXCLUDED.days_hunted
        """, (hunt_id, 'PUBLIC', success_rate,
              rec['permits'], rec['harvest'],
              rec.get('avg_days')))
        harvest_count += 1

    conn.commit()
    print(f"Inserted {harvest_count} harvest rows (skipped {harvest_skip} non-deer/elk)")

    # ===== FINAL COUNTS =====
    print("\n=== UT LOAD SUMMARY ===")
    cur.execute("SELECT COUNT(*) FROM hunts WHERE state_id = %s", (ut_state_id,))
    print(f"  Hunts:          {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(*) FROM gmus WHERE state_id = %s", (ut_state_id,))
    print(f"  GMUs:           {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(*) FROM hunt_gmus hg JOIN hunts h ON h.hunt_id=hg.hunt_id WHERE h.state_id=%s", (ut_state_id,))
    print(f"  Hunt-GMU links: {cur.fetchone()[0]}")
    cur.execute("""SELECT COUNT(*) FROM draw_results_by_pool dr
                   JOIN hunts h ON h.hunt_id = dr.hunt_id WHERE h.state_id = %s""", (ut_state_id,))
    print(f"  Draw results:   {cur.fetchone()[0]}")
    cur.execute("""SELECT COUNT(*) FROM harvest_stats hs
                   JOIN hunts h ON h.hunt_id = hs.hunt_id WHERE h.state_id = %s""", (ut_state_id,))
    print(f"  Harvest rows:   {cur.fetchone()[0]}")
    cur.execute("""SELECT COUNT(*) FROM hunt_dates hd
                   JOIN hunts h ON h.hunt_id = hd.hunt_id WHERE h.state_id = %s""", (ut_state_id,))
    print(f"  Hunt dates:     {cur.fetchone()[0]}")

    conn.close()
    print("\nUT load complete.")


if __name__ == '__main__':
    main()
