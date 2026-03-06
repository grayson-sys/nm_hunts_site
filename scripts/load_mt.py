#!/usr/bin/env python3
"""
Montana data loader: GMUs (Hunting Districts), hunts (B Licenses, Permits),
hunt dates from proclamation, harvest from regional reports.

Sources:
  - MT/proclamations/2026/MT_deer_elk_antelope_2026.pdf (HD regs, pages 48-123)
  - MT/raw_data/elk_hunting_districts_2024.pdf (HD→EMU names, elk counts)
  - MT/raw_data/region1_elk_report_2024.pdf (R1 harvest by HD)
  - MT/raw_data/region4_elk_season_setting.pdf (R4 HD 418 harvest)
  - MT/proclamations/2026/MT_hunt_dates_2026.csv (supplementary dates)

Note: MT draw statistics are only available via interactive portal
(myfwp.mt.gov/fwpPub/drawingStatistics) and cannot be bulk-downloaded.
No draw_results_by_pool rows are loaded.
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
    if s in ('', 'N/A', '-', 'UNL', '–'):
        return 0
    # Handle ranges like "25-300" or "5-600" — take first number
    m = re.match(r'^(\d+)', s)
    return int(m.group(1)) if m else 0


def safe_float(val):
    if val is None:
        return None
    s = str(val).strip().replace(',', '')
    if s in ('', 'N/A', '-'):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def infer_species_code(opportunity, license_type):
    """Infer species_code from opportunity and license type text."""
    opp = (opportunity or '').lower()
    lt = (license_type or '').lower()
    if 'elk' in lt or 'elk' in opp:
        return 'ELK'
    if 'deer' in lt or 'deer' in opp:
        if 'white-tailed' in opp or 'whitetail' in opp:
            return 'WTD'
        if 'mule' in opp:
            return 'MDR'
        return 'MDR'
    if 'antelope' in opp or 'antelope' in lt:
        return 'ANT'
    return None


def infer_bag_code(opportunity):
    """Infer bag_code from opportunity text."""
    opp = (opportunity or '').lower()
    if 'antlerless' in opp:
        if 'elk' in opp:
            return 'COW'
        return 'DOE'
    if 'brow-tined' in opp or 'bull' in opp:
        return 'BULL'
    if 'antlered buck' in opp or 'buck' in opp:
        return 'BUCK'
    if 'either' in opp:
        return 'ES'
    return 'ES'


def infer_season_label(license_type):
    """Derive season_label."""
    lt = (license_type or '').lower()
    if 'b license' in lt:
        return 'B License'
    if 'permit' in lt:
        return 'Permit'
    return 'General'


def parse_proclamation_hunts(filepath):
    """Parse MT proclamation PDF for HD names and B License/Permit entries.
    Returns (hunt_entries, hd_names) where:
      hunt_entries = list of dicts with hunt info
      hd_names = dict of hd_num → name
    """
    hunt_entries = []
    hd_names = {}
    current_hd = None
    current_species_section = None  # 'DEER' or 'ELK'

    with pdfplumber.open(filepath) as pdf:
        # Deer/Elk regs start at page 44 (idx 43) through ~page 119 (idx 118)
        # Multi-district and antelope tables continue through ~page 138
        total_pages = len(pdf.pages)
        start_page = 43  # page 44
        end_page = min(138, total_pages - 1)

        for page_idx in range(start_page, end_page + 1):
            page = pdf.pages[page_idx]
            text = page.extract_text() or ''

            # Find HD headers: "HD 100 - North Kootenai" or "HD 319 S" etc.
            for m in re.finditer(
                r'HD\s+(\d{3}(?:\s*[A-Z](?:\s|$))?)\s*[-–—]\s*([A-Za-z][A-Za-z\s/.\']+?)(?:\s*[-–]\s*Continued|\s*$|\s*NOTE)',
                text
            ):
                hd_num = m.group(1).strip().replace(' ', '')
                hd_name = m.group(2).strip()
                # Remove trailing "Continued" or noise
                hd_name = re.sub(r'\s*Continued.*$', '', hd_name).strip()
                if len(hd_name) > 2 and hd_num not in hd_names:
                    hd_names[hd_num] = hd_name
                current_hd = hd_num

            # Extract tables from page
            tables = page.extract_tables()
            if not tables:
                continue

            for table in tables:
                for row in table:
                    if not row or len(row) < 3:
                        continue

                    cell0 = str(row[0] or '').strip()

                    # Track species section
                    if cell0.upper() in ('DEER', 'ELK', 'ANTELOPE'):
                        current_species_section = cell0.upper()
                        continue

                    # Match B License or Permit entries
                    # Patterns: "Deer B License: 103-00", "Elk Permit: 101-50"
                    m = re.match(
                        r'((?:Deer|Elk|Antelope)\s+(?:B\s+License|Permit))[:\s]+(\d{3}[-–]\d{2})',
                        cell0, re.IGNORECASE
                    )
                    if not m:
                        continue

                    license_type = m.group(1).strip()
                    hunt_code = m.group(2).replace('–', '-').strip()
                    hd_num = hunt_code.split('-')[0]

                    # Opportunity is usually column 1
                    opportunity = str(row[1] or '').strip() if len(row) > 1 else ''

                    # Apply date col 2, Quota col 3, Quota Range col 4
                    apply_date = str(row[2] or '').strip() if len(row) > 2 else ''
                    quota_raw = str(row[3] or '').strip() if len(row) > 3 else ''
                    quota_range = str(row[4] or '').strip() if len(row) > 4 else ''

                    # Parse quota - handle "UNL" and ranges
                    is_otc = 'OTC' in apply_date.upper() or quota_raw.upper() == 'UNL'
                    quota = safe_int(quota_raw) if quota_raw.upper() != 'UNL' else 0

                    # Season dates from remaining columns
                    # Col 5: Early Season, 6: Archery Only, 7: General, 8: Muzzleloader, 9: Late
                    season_dates = {}
                    col_names = ['early_season', 'archery_only', 'general_season',
                                 'muzzleloader', 'late_season']
                    for i, cname in enumerate(col_names):
                        col_idx = 5 + i
                        if col_idx < len(row) and row[col_idx]:
                            val = str(row[col_idx]).strip()
                            if val not in ('-', '', 'None'):
                                season_dates[cname] = val

                    # Prefix hunt_code with species to avoid collisions
                    # Deer B License: 100-00 → D-100-00, Elk B License: 100-00 → E-100-00
                    lt_lower = license_type.lower()
                    if 'elk' in lt_lower:
                        prefixed_code = f"E-{hunt_code}"
                    elif 'deer' in lt_lower:
                        prefixed_code = f"D-{hunt_code}"
                    elif 'antelope' in lt_lower:
                        prefixed_code = f"A-{hunt_code}"
                    else:
                        prefixed_code = hunt_code

                    hunt_entries.append({
                        'hunt_code': prefixed_code,
                        'raw_code': hunt_code,
                        'license_type': license_type,
                        'opportunity': opportunity,
                        'hd': hd_num,
                        'apply_date': apply_date,
                        'quota': quota,
                        'quota_range': quota_range,
                        'is_otc': is_otc,
                        'season_dates': season_dates,
                    })

    return hunt_entries, hd_names


def parse_elk_counts_pdf(filepath):
    """Parse elk_hunting_districts_2024.pdf for HD→EMU mapping and population data."""
    hd_emu = {}  # hd_num → emu_name

    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            if not tables:
                continue
            for table in tables:
                for row in table:
                    if not row or len(row) < 2:
                        continue
                    hd_cell = str(row[0] or '').strip()
                    emu_cell = str(row[1] or '').strip()

                    # Match HD numbers (may be comma-separated like "204, 261, 262")
                    hds = re.findall(r'\d{3}(?:\s*[A-Z])?', hd_cell)
                    if hds and emu_cell and not emu_cell.startswith('Elk Management'):
                        for hd in hds:
                            hd_emu[hd.strip()] = emu_cell

    return hd_emu


def parse_region1_harvest(filepath):
    """Parse Region 1 elk report for 2024 harvest by HD.
    Tables have 3-period layout: Year,(None),Antlered,Antlerless,Total,%≥6pt,None,None repeated.
    """
    harvests = {}

    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            if not tables:
                continue
            for table in tables:
                if not table or len(table) < 3:
                    continue
                header_text = ' '.join(str(c) for c in table[0] if c)
                if 'Harvest' not in header_text:
                    continue
                hd_match = re.search(r'HD\s+(\d{3})', header_text)
                if not hd_match:
                    continue
                hd = hd_match.group(1)

                for row in table:
                    if not row:
                        continue
                    for col_idx, cell in enumerate(row):
                        if str(cell or '').strip() != '2024':
                            continue
                        # Check if next cell is None (period 1 has None gap)
                        offset = 1
                        if col_idx + 1 < len(row) and row[col_idx + 1] is None:
                            offset = 2
                        a_idx = col_idx + offset
                        al_idx = col_idx + offset + 1
                        t_idx = col_idx + offset + 2
                        if t_idx < len(row):
                            antlered = safe_int(row[a_idx])
                            antlerless = safe_int(row[al_idx])
                            total = safe_int(row[t_idx])
                            if total > 0:
                                harvests[hd] = {
                                    'total': total,
                                    'antlered': antlered,
                                    'antlerless': antlerless,
                                }
                        break

    return harvests


def parse_hunt_dates_csv(filepath):
    """Parse MT hunt dates CSV."""
    dates = []
    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            hd_code = row.get('hunt_code', '').strip()
            m = re.match(r'HD-(\d+)', hd_code)
            if not m:
                continue
            dates.append({
                'hd': m.group(1),
                'open_date': row.get('open_date', '').strip(),
                'close_date': row.get('close_date', '').strip(),
                'notes': row.get('notes', '').strip(),
            })
    return dates


def parse_season_date(date_str):
    """Parse a date like 'Sep 05-Oct 18' or 'Oct 24-Nov 29' into (start, end).
    These are partial dates from the proclamation - we add 2026 as the year.
    """
    if not date_str or date_str.strip() in ('-', ''):
        return None, None

    date_str = date_str.strip()
    # Pattern: "Mon DD-Mon DD" or "Mon DD" (single date) or "Aug 15-Oct 23"
    month_map = {
        'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
        'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
        'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
    }

    # Try "Mon DD-Mon DD" pattern
    m = re.match(r'([A-Z][a-z]{2})\s+(\d{1,2})[-–]([A-Z][a-z]{2})\s+(\d{1,2})', date_str)
    if m:
        sm, sd, em, ed = m.group(1), m.group(2), m.group(3), m.group(4)
        if sm in month_map and em in month_map:
            s_month = int(month_map[sm])
            e_month = int(month_map[em])
            s_year = 2026
            e_year = 2027 if e_month < s_month else 2026
            return f"{s_year}-{month_map[sm]}-{int(sd):02d}", f"{e_year}-{month_map[em]}-{int(ed):02d}"

    # Single date "Mon DD"
    m = re.match(r'([A-Z][a-z]{2})\s+(\d{1,2})$', date_str)
    if m:
        sm, sd = m.group(1), m.group(2)
        if sm in month_map:
            s_month = int(month_map[sm])
            year = 2026 if s_month >= 6 else 2027
            d = f"{year}-{month_map[sm]}-{int(sd):02d}"
            return d, d

    return None, None


def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    # Get MT state_id
    cur.execute("SELECT state_id FROM states WHERE state_code='MT'")
    mt_state_id = cur.fetchone()[0]
    print(f"MT state_id: {mt_state_id}")

    # Clean up previous MT data for idempotent re-runs
    print("Cleaning previous MT data...")
    cur.execute("DELETE FROM hunt_dates WHERE hunt_id IN (SELECT hunt_id FROM hunts WHERE state_id=%s)", (mt_state_id,))
    cur.execute("DELETE FROM harvest_stats WHERE hunt_id IN (SELECT hunt_id FROM hunts WHERE state_id=%s)", (mt_state_id,))
    cur.execute("DELETE FROM draw_results_by_pool WHERE hunt_id IN (SELECT hunt_id FROM hunts WHERE state_id=%s)", (mt_state_id,))
    cur.execute("DELETE FROM hunt_gmus WHERE hunt_id IN (SELECT hunt_id FROM hunts WHERE state_id=%s)", (mt_state_id,))
    cur.execute("DELETE FROM hunts WHERE state_id=%s", (mt_state_id,))
    cur.execute("DELETE FROM gmus WHERE state_id=%s", (mt_state_id,))
    cur.execute("DELETE FROM pools WHERE state_id=%s", (mt_state_id,))
    conn.commit()

    # Lookup tables
    cur.execute("SELECT species_id, species_code FROM species")
    species_map = {r[1]: r[0] for r in cur.fetchall()}

    cur.execute("SELECT bag_limit_id, bag_code FROM bag_limits")
    bag_limit_map = {r[1]: r[0] for r in cur.fetchall()}

    # Create MT pools
    for pool_code, desc, pct, note in [
        ('RES', 'Resident pool', 90.0, '~90% of LE permits'),
        ('NR', 'Nonresident pool', 10.0, '~10% of LE permits'),
    ]:
        cur.execute("""
            INSERT INTO pools (state_id, pool_code, description, allocation_pct, allocation_note)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (state_id, pool_code) DO NOTHING
        """, (mt_state_id, pool_code, desc, pct, note))

    cur.execute("SELECT pool_id, pool_code FROM pools WHERE state_id = %s", (mt_state_id,))
    pool_map = {r[1]: r[0] for r in cur.fetchall()}
    conn.commit()
    print(f"MT pools: {pool_map}")

    # ===== PARSE PROCLAMATION =====
    proc_path = os.path.join(BASE_DIR, 'MT/proclamations/2026/MT_deer_elk_antelope_2026.pdf')
    print("Parsing proclamation PDF (this may take a minute)...")
    hunt_entries, hd_names = parse_proclamation_hunts(proc_path)
    print(f"  Found {len(hunt_entries)} B License/Permit entries")
    print(f"  Found {len(hd_names)} HD names from proclamation")

    # ===== PARSE ELK COUNTS for additional HD→EMU names =====
    elk_counts_path = os.path.join(BASE_DIR, 'MT/raw_data/elk_hunting_districts_2024.pdf')
    hd_emu = {}
    if os.path.exists(elk_counts_path):
        print("Parsing elk counts PDF for HD→EMU mapping...")
        hd_emu = parse_elk_counts_pdf(elk_counts_path)
        print(f"  Found {len(hd_emu)} HD→EMU mappings")

    # ===== PARSE HARVEST =====
    r1_harvest = {}
    r1_path = os.path.join(BASE_DIR, 'MT/raw_data/region1_elk_report_2024.pdf')
    if os.path.exists(r1_path):
        print("Parsing Region 1 elk report for harvest data...")
        r1_harvest = parse_region1_harvest(r1_path)
        print(f"  Found harvest data for {len(r1_harvest)} HDs")

    # ===== INSERT GMUs (Hunting Districts) =====
    # Collect all HD numbers from hunt entries + hd_names
    all_hds = set()
    for entry in hunt_entries:
        all_hds.add(entry['hd'])
    for hd in hd_names:
        all_hds.add(hd)

    gmu_cache = {}  # hd_num → gmu_id
    for hd_num in sorted(all_hds):
        name = hd_names.get(hd_num)
        emu = hd_emu.get(hd_num)
        if name:
            gmu_name = f"HD {hd_num} - {name}"
        elif emu:
            gmu_name = f"HD {hd_num} ({emu})"
        else:
            gmu_name = f"HD {hd_num}"

        gmu_code = hd_num
        gmu_sort_key = hd_num.zfill(5)

        # Determine region from HD number
        region = None
        hd_int = int(re.match(r'\d+', hd_num).group())
        if hd_int < 200:
            region = 'Region 1'
        elif hd_int < 300:
            region = 'Region 2'
        elif hd_int < 400:
            region = 'Region 3'
        elif hd_int < 500:
            region = 'Region 4'
        elif hd_int < 600:
            region = 'Region 5'
        elif hd_int < 700:
            region = 'Region 6'
        elif hd_int < 800:
            region = 'Region 7'

        cur.execute("""
            INSERT INTO gmus (state_id, gmu_code, gmu_name, gmu_sort_key, region)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (state_id, gmu_code) DO UPDATE SET
                gmu_name = EXCLUDED.gmu_name,
                gmu_sort_key = EXCLUDED.gmu_sort_key,
                region = EXCLUDED.region
            RETURNING gmu_id
        """, (mt_state_id, gmu_code, gmu_name, gmu_sort_key, region))
        gmu_cache[hd_num] = cur.fetchone()[0]

    conn.commit()
    print(f"Inserted/updated {len(gmu_cache)} GMUs (Hunting Districts)")

    # ===== INSERT HUNTS =====
    hunt_id_map = {}  # hunt_code → hunt_id
    seen_codes = set()
    skipped = 0

    for entry in hunt_entries:
        code = entry['hunt_code']
        if code in seen_codes:
            continue
        seen_codes.add(code)

        species_code = infer_species_code(entry['opportunity'], entry['license_type'])
        if not species_code or species_code not in species_map:
            skipped += 1
            continue

        species_id = species_map[species_code]
        bag_code = infer_bag_code(entry['opportunity'])
        bag_limit_id = bag_limit_map.get(bag_code, 5)  # default ES
        season_label = infer_season_label(entry['license_type'])

        # Weapon type: MT general is ANY weapon
        weapon_type_id = 1  # ANY

        # Tag type
        tag_type = 'B' if 'b license' in entry['license_type'].lower() else 'LE'
        season_type = 'OTC' if entry.get('is_otc') else 'controlled'

        # Display code - use the raw (un-prefixed) code
        raw_code = entry.get('raw_code', code)
        display = f"{entry['license_type']}: {raw_code}"

        # Unit description
        hd_name = hd_names.get(entry['hd'], f"HD {entry['hd']}")
        unit_desc = f"HD {entry['hd']} - {hd_name}" if hd_name != f"HD {entry['hd']}" else hd_name

        # Notes with quota info
        notes = None
        if entry['quota'] > 0:
            notes = f"Quota: {entry['quota']}"
            if entry['quota_range']:
                notes += f", Range: {entry['quota_range']}"

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
                season_type = EXCLUDED.season_type,
                tag_type = EXCLUDED.tag_type,
                unit_description = EXCLUDED.unit_description,
                season_label = EXCLUDED.season_label,
                notes = EXCLUDED.notes
            RETURNING hunt_id
        """, (mt_state_id, species_id, code, display,
              weapon_type_id, bag_limit_id, season_type, tag_type,
              unit_desc, season_label, notes))
        hunt_id = cur.fetchone()[0]
        hunt_id_map[code] = hunt_id

        # Link to GMU
        gmu_id = gmu_cache.get(entry['hd'])
        if gmu_id:
            cur.execute("""
                INSERT INTO hunt_gmus (hunt_id, gmu_id) VALUES (%s, %s)
                ON CONFLICT (hunt_id, gmu_id) DO NOTHING
            """, (hunt_id, gmu_id))

    conn.commit()
    print(f"Inserted {len(hunt_id_map)} hunts (skipped {skipped} non-deer/elk)")

    # ===== INSERT HUNT DATES =====
    # From proclamation season dates
    dates_count = 0
    for entry in hunt_entries:
        hunt_id = hunt_id_map.get(entry['hunt_code'])
        if not hunt_id:
            continue

        sd = entry.get('season_dates', {})
        if not sd:
            continue

        # Find earliest start and latest end across all season types
        earliest_start = None
        latest_end = None
        for season_key in ['early_season', 'archery_only', 'general_season', 'muzzleloader', 'late_season']:
            date_str = sd.get(season_key)
            if not date_str:
                continue
            start, end = parse_season_date(date_str)
            if start and (earliest_start is None or start < earliest_start):
                earliest_start = start
            if end and (latest_end is None or end > latest_end):
                latest_end = end

        if earliest_start and latest_end:
            cur.execute("""
                INSERT INTO hunt_dates (hunt_id, season_year, start_date, end_date,
                    hunt_name)
                VALUES (%s, 2026, %s, %s, %s)
                ON CONFLICT (hunt_id, season_year) DO UPDATE SET
                    start_date = EXCLUDED.start_date,
                    end_date = EXCLUDED.end_date,
                    hunt_name = EXCLUDED.hunt_name
            """, (hunt_id, earliest_start, latest_end,
                  f"{entry['license_type']}: {entry.get('raw_code', entry['hunt_code'])}"))
            dates_count += 1

    conn.commit()
    print(f"Inserted {dates_count} hunt date rows")

    # ===== INSERT HARVEST STATS =====
    # Map harvest data to elk B License hunts by HD (prefixed with E-)
    harvest_count = 0
    for hd_num, data in r1_harvest.items():
        # Find the first Elk B License for this HD: E-{hd}-00
        elk_code = f"E-{hd_num}-00"
        hunt_id = hunt_id_map.get(elk_code)
        if not hunt_id:
            # Try any elk hunt for this HD
            for code, hid in hunt_id_map.items():
                if code.startswith(f"E-{hd_num}-"):
                    hunt_id = hid
                    break
        if not hunt_id:
            continue

        cur.execute("""
            INSERT INTO harvest_stats
                (hunt_id, harvest_year, access_type, harvest_count, notes)
            VALUES (%s, 2024, %s, %s, %s)
            ON CONFLICT (hunt_id, harvest_year, access_type) DO UPDATE SET
                harvest_count = EXCLUDED.harvest_count,
                notes = EXCLUDED.notes
        """, (hunt_id, 'PUBLIC', data['total'],
              f"Antlered: {data['antlered']}, Antlerless: {data['antlerless']}"))
        harvest_count += 1

    conn.commit()
    print(f"Inserted {harvest_count} harvest rows (Region 1 elk)")

    # ===== FINAL COUNTS =====
    print("\n=== MT LOAD SUMMARY ===")
    cur.execute("SELECT COUNT(*) FROM hunts WHERE state_id = %s", (mt_state_id,))
    print(f"  Hunts:          {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(*) FROM gmus WHERE state_id = %s", (mt_state_id,))
    print(f"  GMUs:           {cur.fetchone()[0]}")
    cur.execute("""SELECT COUNT(*) FROM hunt_gmus hg
                   JOIN hunts h ON h.hunt_id=hg.hunt_id WHERE h.state_id=%s""", (mt_state_id,))
    print(f"  Hunt-GMU links: {cur.fetchone()[0]}")
    cur.execute("""SELECT COUNT(*) FROM draw_results_by_pool dr
                   JOIN hunts h ON h.hunt_id = dr.hunt_id WHERE h.state_id = %s""", (mt_state_id,))
    print(f"  Draw results:   {cur.fetchone()[0]}")
    cur.execute("""SELECT COUNT(*) FROM harvest_stats hs
                   JOIN hunts h ON h.hunt_id = hs.hunt_id WHERE h.state_id = %s""", (mt_state_id,))
    print(f"  Harvest rows:   {cur.fetchone()[0]}")
    cur.execute("""SELECT COUNT(*) FROM hunt_dates hd
                   JOIN hunts h ON h.hunt_id = hd.hunt_id WHERE h.state_id = %s""", (mt_state_id,))
    print(f"  Hunt dates:     {cur.fetchone()[0]}")

    conn.close()
    print("\nMT load complete.")


if __name__ == '__main__':
    main()
