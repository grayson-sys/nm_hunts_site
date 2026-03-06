#!/usr/bin/env python3
"""
California data loader: deer and elk draw statistics, harvest stats, hunt dates.

Sources:
  - CA/raw_data/deer_draw_2024_*.pdf (deer draw stats by category & point range)
  - CA/raw_data/elk_draw_2024_*.pdf (elk draw stats by category & point range)
  - CA/raw_data/deer_harvest_2024.pdf (deer harvest by hunt code)
  - CA/raw_data/elk_harvest_2022.pdf (elk harvest by hunt code - latest available)
  - CA/proclamations/2026/CA_hunt_dates_2026.csv (season dates)

CA draw system:
  Deer: 90% pref queue / 10% random. Split by point range PDFs (0-7, 8-14, 15-22).
  Elk: 75% pref / 25% random. Split by point range PDFs (0-10, 11-22).
  Half-point values (e.g., 7.5, 6.5) represent applicants who drew and lost points.
  We aggregate total applicants across all point-range PDFs per hunt code.
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


def safe_int(val):
    if val is None:
        return 0
    s = str(val).strip().replace(',', '').replace('\n', '')
    if s in ('', 'N/A', '-', '–', 'None'):
        return 0
    m = re.match(r'^(\d+)', s)
    return int(m.group(1)) if m else 0


def safe_pct(val):
    if val is None:
        return None
    s = str(val).strip().replace('%', '').replace(',', '')
    if s in ('', 'N/A', '-', '–', 'None'):
        return None
    try:
        return float(s) / 100.0
    except ValueError:
        return None


# ── DEER DRAW PARSING ──

DEER_DRAW_FILES = {
    'apprentice': ['deer_draw_2024_apprentice.pdf'],
    'archery': [
        'deer_draw_2024_archery_0-7pts.pdf',
        'deer_draw_2024_archery_8-14pts.pdf',
        'deer_draw_2024_archery_15-22pts.pdf',
    ],
    'general_late': [
        'deer_draw_2024_general_late_0-7pts.pdf',
        'deer_draw_2024_general_late_8-14pts.pdf',
        'deer_draw_2024_general_late_15-22pts.pdf',
    ],
    'muzzleloader': [
        'deer_draw_2024_muzzleloader_0-7pts.pdf',
        'deer_draw_2024_muzzleloader_8-14pts.pdf',
        'deer_draw_2024_muzzleloader_15-22pts.pdf',
    ],
    'zone': [
        'deer_draw_2024_zone_0-7pts.pdf',
        'deer_draw_2024_zone_8-14pts.pdf',
        'deer_draw_2024_zone_15-22pts.pdf',
    ],
}

ELK_DRAW_FILES = {
    'apprentice': ['elk_draw_2024_apprentice.pdf'],
    'antlerless_eithersex': [
        'elk_draw_2024_antlerless_eithersex_0-10pts.pdf',
        'elk_draw_2024_antlerless_eithersex_11-22pts.pdf',
    ],
    'bull_spikebull': [
        'elk_draw_2024_bull_spikebull_0-10pts.pdf',
        'elk_draw_2024_bull_spikebull_11-22pts.pdf',
    ],
}


def parse_draw_pdf(filepath):
    """Parse a CA draw statistics PDF. Returns list of dicts with hunt_code, description,
    tag_quota, pref_quota, random_quota, total_applicants, and per-point-level applicant counts."""
    results = []
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            if not tables:
                continue
            table = tables[0]  # main data table
            if len(table) < 2:
                continue

            # Header row
            header = [str(h or '').replace('\n', ' ').strip() for h in table[0]]

            for row in table[1:]:
                if not row or len(row) < 6:
                    continue
                hunt_code = str(row[0] or '').strip().replace('\n', ' ')
                if not hunt_code or hunt_code == 'Hunt Code' or hunt_code.startswith('Hunt'):
                    continue
                # Skip preference-point-only rows
                if hunt_code in ('PD', '499'):
                    continue

                desc = str(row[1] or '').strip().replace('\n', ' ')
                tag_quota = safe_int(row[2])
                pref_quota = safe_int(row[3])
                random_quota = safe_int(row[4])
                total_apps = safe_int(row[5])

                # Collect per-point applicant counts (columns 6+)
                point_counts = {}
                for ci in range(6, len(row)):
                    col_name = header[ci] if ci < len(header) else ''
                    val = safe_int(row[ci])
                    # Extract point value from header (e.g., "7 Points", "7 > 6 Points", "0 Point")
                    # Half-points like "7 > 6" represent drawn applicants losing a point
                    m_half = re.match(r'(\d+)\s*>\s*(\d+)', col_name)
                    m_whole = re.match(r'(\d+\.?\d*)\s*Point', col_name)
                    if m_half:
                        pt = float(m_half.group(1)) - 0.5
                        point_counts[pt] = val
                    elif m_whole:
                        pt = float(m_whole.group(1))
                        point_counts[pt] = val

                results.append({
                    'hunt_code': hunt_code,
                    'description': desc,
                    'tag_quota': tag_quota,
                    'pref_quota': pref_quota,
                    'random_quota': random_quota,
                    'total_applicants': total_apps,
                    'point_counts': point_counts,
                })

    return results


def aggregate_draw_data(file_groups, raw_dir):
    """Parse multiple point-range PDFs for a category and aggregate per hunt code.
    Returns dict of hunt_code -> aggregated data."""
    aggregated = {}

    for filepath_name in file_groups:
        filepath = os.path.join(raw_dir, filepath_name)
        if not os.path.exists(filepath):
            print(f"  WARNING: {filepath_name} not found, skipping")
            continue

        rows = parse_draw_pdf(filepath)
        for r in rows:
            code = r['hunt_code']
            if code not in aggregated:
                aggregated[code] = {
                    'hunt_code': code,
                    'description': r['description'],
                    'tag_quota': r['tag_quota'],
                    'pref_quota': r['pref_quota'],
                    'random_quota': r['random_quota'],
                    'total_applicants': 0,
                    'point_counts': {},
                }
            # Sum applicants across point ranges
            aggregated[code]['total_applicants'] += r['total_applicants']
            # Merge point counts
            for pt, count in r['point_counts'].items():
                aggregated[code]['point_counts'][pt] = \
                    aggregated[code]['point_counts'].get(pt, 0) + count
            # Tag quota should be consistent; take max in case of discrepancy
            if r['tag_quota'] > aggregated[code]['tag_quota']:
                aggregated[code]['tag_quota'] = r['tag_quota']
                aggregated[code]['pref_quota'] = r['pref_quota']
                aggregated[code]['random_quota'] = r['random_quota']

    return aggregated


# ── HARVEST PARSING ──

def parse_deer_harvest(filepath):
    """Parse deer harvest PDF. Returns dict of hunt_code -> harvest data."""
    results = {}
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            if not tables:
                continue
            for table in tables:
                for row in table:
                    if not row or len(row) < 10:
                        continue
                    code = str(row[0] or '').strip().replace('\n', ' ')
                    if not code or 'Hunt Code' in code or 'Zone' in code:
                        continue
                    # Skip subtotal/total rows
                    if code.lower() in ('total', 'subtotal', 'statewide'):
                        continue

                    tag_quota = safe_int(row[2])
                    total_estimated = safe_int(row[8])
                    success_str = str(row[9] or '').strip()
                    success_rate = safe_pct(success_str)

                    if code and tag_quota > 0:
                        results[code] = {
                            'tag_quota': tag_quota,
                            'harvest_count': total_estimated,
                            'success_rate': success_rate,
                        }
    return results


def parse_elk_harvest_text(filepath):
    """Parse elk harvest PDF using text extraction (tables have too many None columns).
    Returns dict of hunt_code -> harvest data."""
    results = {}
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            lines = text.strip().split('\n')
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                # Try to match lines that start with a 3-digit hunt code
                m = re.match(r'^(\d{3})\s+(Tule|Rs|Rm|Rocky)\s+(.+?)\s+(\d[\d,]*)\s+(\d[\d,]*)\s+(\d[\d,]*)\s+(\d[\d,]*)\s+(\d[\d,]*)\s+(\d[\d,]*)\s+(\d+%|N/A)', line)
                if m:
                    code = m.group(1)
                    applicants = safe_int(m.group(4))
                    quota = safe_int(m.group(5))
                    tags_issued = safe_int(m.group(7))
                    reported_harvest = safe_int(m.group(9))
                    success_str = m.group(10)
                    success_rate = safe_pct(success_str)

                    results[code] = {
                        'applicants': applicants,
                        'quota': quota,
                        'tags_issued': tags_issued,
                        'harvest_count': reported_harvest,
                        'success_rate': success_rate,
                    }
                    i += 1
                    continue

                # Some lines wrap: hunt code + subspecies on one line, data continues
                # Try matching: code subspecies partial-desc then number fields
                m2 = re.match(r'^(\d{3})\s+(Tule|Rs|Rm|Rocky)\s+', line)
                if m2:
                    code = m2.group(1)
                    # Collect remaining text until we find the number pattern
                    combined = line
                    j = i + 1
                    while j < len(lines) and j < i + 3:
                        combined += ' ' + lines[j].strip()
                        j += 1

                    m3 = re.search(r'(\d[\d,]*)\s+(\d[\d,]*)\s+(\d[\d,]*)\s+(\d[\d,]*)\s+(\d[\d,]*)\s+(\d[\d,]*)\s+(\d+%|N/A)', combined)
                    if m3:
                        applicants = safe_int(m3.group(1))
                        quota = safe_int(m3.group(2))
                        tags_issued = safe_int(m3.group(4))
                        reported_harvest = safe_int(m3.group(6))
                        success_str = m3.group(7)
                        success_rate = safe_pct(success_str)

                        results[code] = {
                            'applicants': applicants,
                            'quota': quota,
                            'tags_issued': tags_issued,
                            'harvest_count': reported_harvest,
                            'success_rate': success_rate,
                        }
                i += 1
    return results


# ── SPECIES & WEAPON INFERENCE ──

def infer_elk_species(description):
    """Infer elk subspecies from hunt description.
    Tule elk, Roosevelt (Rs), Rocky Mountain (Rm)."""
    desc = description.lower()
    if 'tule' in desc or 'grizzly island' in desc or 'cache creek' in desc or \
       'goodale' in desc or 'la panza' in desc or 'independence' in desc or \
       'fort hunter liggett' in desc or 'owens valley' in desc or \
       'bear valley' in desc or 'central coast' in desc or 'san luis' in desc or \
       'lone pine' in desc or 'bass hill' in desc:
        return 'RELT'  # Tule Elk
    if 'marble mountain' in desc or 'northwestern' in desc or 'siskiyou' in desc:
        return 'ROOSE'  # Roosevelt Elk
    if 'northeastern' in desc:
        return 'ELK'  # Rocky Mountain Elk
    return 'ELK'  # default


def infer_weapon_type(description, category):
    """Infer weapon_type_id from description or file category."""
    desc = description.lower()
    cat = category.lower()
    if 'archery' in desc or 'archery' in cat:
        return 3  # ARCHERY
    if 'muzzle' in desc or 'muzzle' in cat or 'muzzloader' in desc:
        return 4  # MUZZ
    return 1  # ANY (General Methods)


def infer_bag_limit(description):
    """Infer bag_limit_id from description."""
    desc = description.lower()
    if 'either-sex' in desc or 'either sex' in desc:
        return 5  # ES
    if 'antlerless' in desc:
        if 'elk' in desc or 'bull' not in desc:
            return 15  # COW
        return 18  # DOE
    if 'spike bull' in desc:
        return 14  # SPIKE
    if 'bull' in desc:
        return 13  # BULL
    if 'buck' in desc:
        return 16  # BUCK
    if 'doe' in desc:
        return 18  # DOE
    return 5  # ES default


def infer_season_label(description, category):
    """Derive season_label from description and category."""
    desc = description.lower()
    cat = category.lower()
    if 'apprentice' in desc or 'apprentice' in cat:
        return 'Apprentice'
    if 'late' in desc or 'late' in cat:
        return 'Late Season'
    if 'archery' in desc or 'archery' in cat:
        return 'Archery'
    if 'muzzle' in desc or 'muzzle' in cat:
        return 'Muzzleloader'
    if 'zone' in cat or 'general' in cat:
        return 'General'
    return 'General'


def derive_gmu_from_hunt(hunt_code, description, species):
    """Derive GMU code and name from CA hunt code and description.
    Deer zones: A, B, C, D6-D19, X1-X12
    Elk: named areas (Bear Valley, Cache Creek, etc.)
    Archery hunts (A1-A33): map to zone from description.
    """
    desc = description

    if species == 'deer':
        # Zone hunts: code IS the zone (A, B, C, D6, X1, etc.)
        # Archery hunts: A1, A3, etc. - description has the zone
        code = hunt_code.upper()

        # General/zone/late hunts
        if re.match(r'^[A-D]\d*$', code) or re.match(r'^X\d+[A-C]?$', code):
            return code, f"Zone {code}"

        # Archery area-specific: description like "Archery Hunt in Zone X1"
        m = re.search(r'(?:Zone|Zones?)\s+([A-Z]\d*[A-Za-z]?)', desc)
        if m:
            zone = m.group(1).upper()
            return zone, f"Zone {zone}"

        # Named hunts: extract area name
        m = re.search(r'^(.+?)(?:\s+Archery|\s+Late|\s+Muzzle|\s+General)', desc)
        if m:
            area = m.group(1).strip()
            return hunt_code, area

        # Apprentice: description has the area
        m = re.search(r'^(.+?)\s+Apprentice', desc)
        if m:
            area = m.group(1).strip()
            return hunt_code, area

        return hunt_code, desc[:50]

    else:
        # Elk: named areas as GMU
        # Extract area name from description
        # "Bear Valley - General Methods - Bull" -> "Bear Valley"
        # "Cache Creek Period 1 - General Methods - Bull" -> "Cache Creek"
        # "Fort Hunter Liggett Archery only - Antlerless" -> "Fort Hunter Liggett"
        desc_clean = desc
        # Remove common suffixes
        for pat in [r'\s*-\s*General Methods.*', r'\s*-\s*Muzzle?loader.*',
                    r'\s*-\s*Archery.*', r'\s*-\s*Bull$', r'\s*-\s*Antlerless$',
                    r'\s*-\s*Either-?sex$', r'\s*-\s*Spike Bull$',
                    r'\s+Archery only.*', r'\s+Apprentice.*',
                    r'\s+Period\s+\d+.*', r'\s+Multiple Zone.*']:
            desc_clean = re.sub(pat, '', desc_clean, flags=re.IGNORECASE).strip()

        if desc_clean:
            # Normalize name for GMU code
            gmu_code = re.sub(r'[^A-Za-z0-9]', '_', desc_clean).upper()
            return gmu_code, desc_clean

        return hunt_code, desc[:50]


def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    ca_state_id = 11
    raw_dir = os.path.join(BASE_DIR, 'CA/raw_data')

    # Clean previous CA data for idempotent re-runs
    print("Cleaning previous CA data...")
    cur.execute("DELETE FROM hunt_dates WHERE hunt_id IN (SELECT hunt_id FROM hunts WHERE state_id=%s)", (ca_state_id,))
    cur.execute("DELETE FROM harvest_stats WHERE hunt_id IN (SELECT hunt_id FROM hunts WHERE state_id=%s)", (ca_state_id,))
    cur.execute("DELETE FROM draw_results_by_pool WHERE hunt_id IN (SELECT hunt_id FROM hunts WHERE state_id=%s)", (ca_state_id,))
    cur.execute("DELETE FROM hunt_gmus WHERE hunt_id IN (SELECT hunt_id FROM hunts WHERE state_id=%s)", (ca_state_id,))
    cur.execute("DELETE FROM hunts WHERE state_id=%s", (ca_state_id,))
    cur.execute("DELETE FROM gmus WHERE state_id=%s", (ca_state_id,))
    conn.commit()

    # Lookup tables
    cur.execute("SELECT species_id, species_code FROM species")
    species_map = {r[1]: r[0] for r in cur.fetchall()}

    # Create CA pools if not exist
    for pool_code, desc, pct, note in [
        ('RES', 'Resident pool', 99.0, 'No NR quota for deer; elk: 1 NR tag/yr statewide'),
        ('NR', 'Nonresident pool', 1.0, 'Elk: 1 NR tag/yr statewide; deer: no separate NR pool'),
    ]:
        cur.execute("""
            INSERT INTO pools (state_id, pool_code, description, allocation_pct, allocation_note)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (state_id, pool_code) DO NOTHING
        """, (ca_state_id, pool_code, desc, pct, note))
    conn.commit()

    cur.execute("SELECT pool_id, pool_code FROM pools WHERE state_id = %s", (ca_state_id,))
    pool_map = {r[1]: r[0] for r in cur.fetchall()}
    print(f"CA pools: {pool_map}")

    # ===== PARSE ALL DRAW PDFs =====
    print("\nParsing deer draw PDFs...")
    all_deer_hunts = {}
    for category, files in DEER_DRAW_FILES.items():
        agg = aggregate_draw_data(files, raw_dir)
        for code, data in agg.items():
            key = (code, category)
            data['category'] = category
            data['species'] = 'deer'
            all_deer_hunts[key] = data

    print(f"  Parsed {len(all_deer_hunts)} deer hunt-category combinations")

    print("Parsing elk draw PDFs...")
    all_elk_hunts = {}
    for category, files in ELK_DRAW_FILES.items():
        agg = aggregate_draw_data(files, raw_dir)
        for code, data in agg.items():
            key = (code, category)
            data['category'] = category
            data['species'] = 'elk'
            all_elk_hunts[key] = data

    print(f"  Parsed {len(all_elk_hunts)} elk hunt-category combinations")

    # Combine into single list, creating unique hunt_codes
    all_hunts = {}  # unique_key -> data

    for (code, category), data in all_deer_hunts.items():
        # Deer hunt codes: use code directly (they're unique per category because
        # archery codes like A1 don't overlap with zone codes like D6)
        # But some codes appear in multiple categories (e.g., zone + general_late)
        # Prefix with category initial for disambiguation
        if category == 'apprentice':
            hunt_key = f"D-{code}"  # J1, J3, etc.
        elif category == 'archery':
            hunt_key = f"D-{code}"  # A1, A3, etc.
        elif category == 'general_late':
            hunt_key = f"D-{code}-GL"
        elif category == 'muzzleloader':
            hunt_key = f"D-{code}-ML"
        elif category == 'zone':
            hunt_key = f"D-{code}"  # C, D6, X1, etc.
        else:
            hunt_key = f"D-{code}"

        # Check for duplicates - zone and archery codes don't overlap
        # but general_late codes like G1 could overlap. Use hunt_key as hunt_code.
        all_hunts[hunt_key] = data

    for (code, category), data in all_elk_hunts.items():
        if category == 'apprentice':
            hunt_key = f"E-{code}"
        elif category == 'antlerless_eithersex':
            hunt_key = f"E-{code}"
        elif category == 'bull_spikebull':
            hunt_key = f"E-{code}"
        else:
            hunt_key = f"E-{code}"

        # Elk codes are numeric (330, 406, etc.) and unique across categories
        # since a given code is either bull or antlerless, not both
        if hunt_key in all_hunts:
            # Same elk hunt code in multiple categories - shouldn't happen normally
            # but if so, keep the one with more applicants
            if data['total_applicants'] > all_hunts[hunt_key]['total_applicants']:
                all_hunts[hunt_key] = data
        else:
            all_hunts[hunt_key] = data

    print(f"\nTotal unique hunt codes: {len(all_hunts)}")

    # ===== INSERT GMUs =====
    gmu_cache = {}  # gmu_code -> gmu_id

    for hunt_key, data in all_hunts.items():
        species = data['species']
        gmu_code, gmu_name = derive_gmu_from_hunt(
            data['hunt_code'], data['description'], species)

        if gmu_code in gmu_cache:
            continue

        gmu_sort_key = gmu_code.ljust(10, '0')[:10]

        cur.execute("""
            INSERT INTO gmus (state_id, gmu_code, gmu_name, gmu_sort_key)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (state_id, gmu_code) DO UPDATE SET
                gmu_name = EXCLUDED.gmu_name,
                gmu_sort_key = EXCLUDED.gmu_sort_key
            RETURNING gmu_id
        """, (ca_state_id, gmu_code, gmu_name, gmu_sort_key))
        gmu_cache[gmu_code] = cur.fetchone()[0]

    conn.commit()
    print(f"Inserted {len(gmu_cache)} GMUs")

    # ===== INSERT HUNTS =====
    hunt_id_map = {}  # hunt_key -> hunt_id

    for hunt_key, data in all_hunts.items():
        species = data['species']
        desc = data['description']
        category = data['category']

        if species == 'elk':
            species_code = infer_elk_species(desc)
        else:
            species_code = 'MDR'  # California deer are mule/blacktail

        species_id = species_map.get(species_code, species_map.get('MDR'))

        weapon_type_id = infer_weapon_type(desc, category)
        bag_limit_id = infer_bag_limit(desc)
        season_label = infer_season_label(desc, category)
        season_type = 'controlled'
        tag_type = 'LE'

        cur.execute("""
            INSERT INTO hunts (state_id, species_id, hunt_code, hunt_code_display,
                weapon_type_id, bag_limit_id, season_type, tag_type, is_active,
                unit_description, season_label, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1, %s, %s, %s)
            ON CONFLICT (state_id, hunt_code) DO UPDATE SET
                species_id = EXCLUDED.species_id,
                hunt_code_display = EXCLUDED.hunt_code_display,
                weapon_type_id = EXCLUDED.weapon_type_id,
                bag_limit_id = EXCLUDED.bag_limit_id,
                season_label = EXCLUDED.season_label,
                notes = EXCLUDED.notes
            RETURNING hunt_id
        """, (ca_state_id, species_id, hunt_key, f"{data['hunt_code']} - {desc[:60]}",
              weapon_type_id, bag_limit_id, season_type, tag_type,
              desc, season_label,
              f"Quota: {data['tag_quota']} (Pref: {data['pref_quota']}, Random: {data['random_quota']})"))
        hunt_id = cur.fetchone()[0]
        hunt_id_map[hunt_key] = hunt_id

        # Link to GMU
        gmu_code, _ = derive_gmu_from_hunt(data['hunt_code'], desc, species)
        gmu_id = gmu_cache.get(gmu_code)
        if gmu_id:
            cur.execute("""
                INSERT INTO hunt_gmus (hunt_id, gmu_id) VALUES (%s, %s)
                ON CONFLICT (hunt_id, gmu_id) DO NOTHING
            """, (hunt_id, gmu_id))

    conn.commit()
    print(f"Inserted {len(hunt_id_map)} hunts")

    # ===== INSERT DRAW RESULTS =====
    # CA has no separate R/NR pool for deer draw stats; use RES pool
    res_pool_id = pool_map['RES']
    draw_count = 0

    for hunt_key, data in all_hunts.items():
        hunt_id = hunt_id_map.get(hunt_key)
        if not hunt_id:
            continue

        total_apps = data['total_applicants']
        tag_quota = data['tag_quota']
        if total_apps == 0 and tag_quota == 0:
            continue

        # Compute max points held from point_counts
        pts = data.get('point_counts', {})
        max_pts = max(pts.keys()) if pts else None
        # Compute min points that drew: find highest point with half-point drawn
        # Half-points (x.5) represent applicants who drew
        drawn_pts = sorted([p for p in pts.keys() if p != int(p) and pts[p] > 0], reverse=True)
        min_pts_drawn = int(drawn_pts[-1] + 0.5) if drawn_pts else None

        cur.execute("""
            INSERT INTO draw_results_by_pool
                (hunt_id, draw_year, pool_id, applications, tags_available,
                 tags_awarded, max_pts_held, min_pts_drawn)
            VALUES (%s, 2024, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (hunt_id, draw_year, pool_id) DO UPDATE SET
                applications = EXCLUDED.applications,
                tags_available = EXCLUDED.tags_available,
                tags_awarded = EXCLUDED.tags_awarded,
                max_pts_held = EXCLUDED.max_pts_held,
                min_pts_drawn = EXCLUDED.min_pts_drawn
        """, (hunt_id, res_pool_id, total_apps, tag_quota, tag_quota,
              max_pts if max_pts else None,
              min_pts_drawn))
        draw_count += 1

    conn.commit()
    print(f"Inserted {draw_count} draw result rows")

    # ===== INSERT HARVEST STATS =====
    # Deer harvest 2024
    print("\nParsing deer harvest 2024...")
    deer_harvest_path = os.path.join(raw_dir, 'deer_harvest_2024.pdf')
    deer_harvest = parse_deer_harvest(deer_harvest_path)
    print(f"  Parsed {len(deer_harvest)} deer harvest rows")

    harvest_count = 0
    for code, hdata in deer_harvest.items():
        # Map harvest hunt code to our hunt_key
        # Try direct mapping: D-{code}
        hunt_id = None
        for suffix in ['', '-GL', '-ML']:
            hk = f"D-{code}{suffix}"
            if hk in hunt_id_map:
                hunt_id = hunt_id_map[hk]
                break

        if not hunt_id:
            continue

        cur.execute("""
            INSERT INTO harvest_stats
                (hunt_id, harvest_year, access_type, success_rate, harvest_count)
            VALUES (%s, 2024, 'PUBLIC', %s, %s)
            ON CONFLICT (hunt_id, harvest_year, access_type) DO UPDATE SET
                success_rate = EXCLUDED.success_rate,
                harvest_count = EXCLUDED.harvest_count
        """, (hunt_id, hdata['success_rate'], hdata['harvest_count']))
        harvest_count += 1

    # Elk harvest 2022 (latest available)
    print("Parsing elk harvest 2022...")
    elk_harvest_path = os.path.join(raw_dir, 'elk_harvest_2022.pdf')
    elk_harvest = parse_elk_harvest_text(elk_harvest_path)
    print(f"  Parsed {len(elk_harvest)} elk harvest rows")

    for code, hdata in elk_harvest.items():
        hunt_id = hunt_id_map.get(f"E-{code}")
        if not hunt_id:
            continue

        cur.execute("""
            INSERT INTO harvest_stats
                (hunt_id, harvest_year, access_type, success_rate, harvest_count)
            VALUES (%s, 2022, 'PUBLIC', %s, %s)
            ON CONFLICT (hunt_id, harvest_year, access_type) DO UPDATE SET
                success_rate = EXCLUDED.success_rate,
                harvest_count = EXCLUDED.harvest_count
        """, (hunt_id, hdata['success_rate'], hdata['harvest_count']))
        harvest_count += 1

    conn.commit()
    print(f"Inserted {harvest_count} harvest rows total")

    # ===== INSERT HUNT DATES =====
    print("\nLoading hunt dates from CSV...")
    dates_csv = os.path.join(BASE_DIR, 'CA/proclamations/2026/CA_hunt_dates_2026.csv')
    dates_count = 0

    with open(dates_csv, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = row.get('hunt_code', '').strip()
            open_date = row.get('open_date', '').strip()
            close_date = row.get('close_date', '').strip()
            bag_desc = row.get('bag_limit_description', '').strip()

            if not code or not open_date:
                continue

            # Map CSV hunt codes to our hunt_keys
            hunt_id = None
            for prefix in ['D-', 'E-']:
                hk = f"{prefix}{code}"
                if hk in hunt_id_map:
                    hunt_id = hunt_id_map[hk]
                    break
            # Also try suffixed versions
            if not hunt_id:
                for suffix in ['-GL', '-ML']:
                    hk = f"D-{code}{suffix}"
                    if hk in hunt_id_map:
                        hunt_id = hunt_id_map[hk]
                        break

            if not hunt_id:
                continue

            cur.execute("""
                INSERT INTO hunt_dates (hunt_id, season_year, start_date, end_date,
                    hunt_name, notes)
                VALUES (%s, 2026, %s, %s, %s, %s)
                ON CONFLICT (hunt_id, season_year) DO UPDATE SET
                    start_date = LEAST(hunt_dates.start_date, EXCLUDED.start_date),
                    end_date = GREATEST(hunt_dates.end_date, EXCLUDED.end_date),
                    hunt_name = EXCLUDED.hunt_name,
                    notes = EXCLUDED.notes
            """, (hunt_id, open_date, close_date, bag_desc, row.get('notes', '').strip()))
            dates_count += 1

    conn.commit()
    print(f"Inserted/updated {dates_count} hunt date rows")

    # ===== FINAL COUNTS =====
    print("\n=== CA LOAD SUMMARY ===")
    cur.execute("SELECT COUNT(*) FROM hunts WHERE state_id = %s", (ca_state_id,))
    print(f"  Hunts:          {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(*) FROM gmus WHERE state_id = %s", (ca_state_id,))
    print(f"  GMUs:           {cur.fetchone()[0]}")
    cur.execute("""SELECT COUNT(*) FROM hunt_gmus hg
                   JOIN hunts h ON h.hunt_id=hg.hunt_id WHERE h.state_id=%s""", (ca_state_id,))
    print(f"  Hunt-GMU links: {cur.fetchone()[0]}")
    cur.execute("""SELECT COUNT(*) FROM draw_results_by_pool dr
                   JOIN hunts h ON h.hunt_id = dr.hunt_id WHERE h.state_id = %s""", (ca_state_id,))
    print(f"  Draw results:   {cur.fetchone()[0]}")
    cur.execute("""SELECT COUNT(*) FROM harvest_stats hs
                   JOIN hunts h ON h.hunt_id = hs.hunt_id WHERE h.state_id = %s""", (ca_state_id,))
    print(f"  Harvest rows:   {cur.fetchone()[0]}")
    cur.execute("""SELECT COUNT(*) FROM hunt_dates hd
                   JOIN hunts h ON h.hunt_id = hd.hunt_id WHERE h.state_id = %s""", (ca_state_id,))
    print(f"  Hunt dates:     {cur.fetchone()[0]}")

    conn.close()
    print("\nCA load complete.")


if __name__ == '__main__':
    main()
