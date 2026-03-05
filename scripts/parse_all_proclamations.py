#!/usr/bin/env python3
"""
Parse hunt season dates from state proclamation PDFs.
Extracts hunt codes, open/close dates, bag limits for deer and elk.
Outputs CSV per state.
"""

import csv
import os
import re
import sys
from datetime import datetime

import pdfplumber

BASE_DIR = "/Users/openclaw/Documents/GraysonsDrawOdds"
SEASON_YEAR = 2026

MONTH_MAP = {
    'jan': 1, 'january': 1, 'feb': 2, 'february': 2,
    'mar': 3, 'march': 3, 'apr': 4, 'april': 4,
    'may': 5, 'jun': 6, 'june': 6,
    'jul': 7, 'july': 7, 'aug': 8, 'august': 8,
    'sep': 9, 'sept': 9, 'september': 9,
    'oct': 10, 'october': 10, 'nov': 11, 'november': 11,
    'dec': 12, 'december': 12
}


def parse_wy_date(date_str, year=None):
    """Parse WY date like 'Sep. 1' or 'Oct. 15' into YYYY-MM-DD."""
    if not date_str or not date_str.strip():
        return None
    date_str = date_str.strip().rstrip('.')
    m = re.match(r'([A-Za-z]+)\.?\s+(\d+)', date_str)
    if not m:
        return None
    month_str = m.group(1).lower().rstrip('.')
    day = int(m.group(2))
    month = MONTH_MAP.get(month_str)
    if not month:
        return None
    # For WY: archery starts Sep, regular season ends up to Jan 31
    # Determine year based on month
    if year is None:
        year = SEASON_YEAR if month >= 8 else SEASON_YEAR + 1
    return f"{year:04d}-{month:02d}-{day:02d}"


def parse_wy(species='elk'):
    """Parse Wyoming elk or deer hunting seasons PDF."""
    if species == 'elk':
        pdf_path = os.path.join(BASE_DIR, "WY/proclamations/2026/WY_elk_hunting_seasons.pdf")
    else:
        pdf_path = os.path.join(BASE_DIR, "WY/proclamations/2026/WY_deer_hunting_seasons_ch6.pdf")

    if not os.path.exists(pdf_path):
        print(f"  [WY] PDF not found: {pdf_path}")
        return []

    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if not row or len(row) < 7:
                        continue
                    hunt_area = (row[0] or '').strip()
                    # Skip header rows
                    if not hunt_area or hunt_area.startswith('Hunt') or hunt_area == 'Area':
                        continue
                    # Clean up multi-line hunt areas like "1, 2,\n3"
                    hunt_area = re.sub(r'\s+', ' ', hunt_area).strip()
                    hunt_type = (row[1] or '').strip()
                    archery_opens = (row[2] or '').strip()
                    archery_closes = (row[3] or '').strip()
                    regular_opens = (row[4] or '').strip()
                    regular_closes = (row[5] or '').strip()
                    quota = (row[6] or '').strip()
                    limitations = (row[7] or '').strip() if len(row) > 7 else ''
                    limitations = re.sub(r'\s+', ' ', limitations).strip()

                    # Build hunt code: area-type combination
                    species_prefix = 'ELK' if species == 'elk' else 'DEER'

                    # Regular season row
                    if regular_opens and regular_closes:
                        open_d = parse_wy_date(regular_opens)
                        close_d = parse_wy_date(regular_closes)
                        if open_d and close_d:
                            hunt_code = f"{hunt_area}-{hunt_type}"
                            rows.append({
                                'hunt_code': hunt_code,
                                'open_date': open_d,
                                'close_date': close_d,
                                'bag_limit_description': limitations,
                                'notes': f"Regular season; Quota: {quota}" if quota else "Regular season"
                            })

                    # Archery season row (if different dates)
                    if archery_opens and archery_closes:
                        open_d = parse_wy_date(archery_opens)
                        close_d = parse_wy_date(archery_closes)
                        if open_d and close_d:
                            hunt_code = f"{hunt_area}-{hunt_type}-ARCH"
                            rows.append({
                                'hunt_code': hunt_code,
                                'open_date': open_d,
                                'close_date': close_d,
                                'bag_limit_description': limitations,
                                'notes': "Special archery season"
                            })

    print(f"  [WY-{species}] Extracted {len(rows)} hunt season rows")
    return rows


def parse_nv():
    """Parse Nevada big game seasons PDF."""
    pdf_path = os.path.join(BASE_DIR, "NV/proclamations/2026/NV_big_game_seasons_2026.pdf")
    if not os.path.exists(pdf_path):
        print("  [NV] PDF not found")
        return []

    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        current_species = None
        for page in pdf.pages:
            text = page.extract_text() or ''
            # Detect species sections
            if re.search(r'MULE DEER', text, re.IGNORECASE):
                current_species = 'DEER'
            elif re.search(r'\bELK\b', text, re.IGNORECASE):
                current_species = 'ELK'

            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if not row or len(row) < 3:
                        continue
                    # Look for hunt unit patterns and dates
                    first = (row[0] or '').strip()
                    if not first or re.match(r'^(Hunt|Unit|Season|Weapon|Bag)', first, re.IGNORECASE):
                        continue

                    # Try to extract date patterns from the row
                    row_text = ' '.join(str(c or '') for c in row)
                    dates = re.findall(r'(\w+\.?\s+\d+)\s*[-–]\s*(\w+\.?\s+\d+)', row_text)
                    if dates:
                        for open_str, close_str in dates:
                            open_d = parse_wy_date(open_str)
                            close_d = parse_wy_date(close_str)
                            if open_d and close_d:
                                rows.append({
                                    'hunt_code': first,
                                    'open_date': open_d,
                                    'close_date': close_d,
                                    'bag_limit_description': current_species or '',
                                    'notes': row_text[:200]
                                })

    # Also try text-based extraction
    if len(rows) < 10:
        rows = parse_nv_text_fallback()

    print(f"  [NV] Extracted {len(rows)} hunt season rows")
    return rows


def parse_nv_text_fallback():
    """Fallback text parser for NV."""
    pdf_path = os.path.join(BASE_DIR, "NV/proclamations/2026/NV_big_game_seasons_2026.pdf")
    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ''
            # NV format: hunt unit groups, weapon type, dates
            # Look for date ranges like "Oct. 10 - Oct. 25"
            for line in text.split('\n'):
                date_match = re.findall(
                    r'(\w+\.?\s+\d{1,2})\s*[-–through]+\s*(\w+\.?\s+\d{1,2})',
                    line
                )
                unit_match = re.match(r'^(\d{3}[A-Za-z]?(?:\s*,\s*\d{3}[A-Za-z]?)*)', line)
                if date_match and unit_match:
                    unit = unit_match.group(1).strip()
                    for open_str, close_str in date_match:
                        open_d = parse_wy_date(open_str)
                        close_d = parse_wy_date(close_str)
                        if open_d and close_d:
                            rows.append({
                                'hunt_code': unit,
                                'open_date': open_d,
                                'close_date': close_d,
                                'bag_limit_description': '',
                                'notes': line.strip()[:200]
                            })
    return rows


def parse_az():
    """Parse Arizona pronghorn and elk regulations PDF (elk only)."""
    pdf_path = os.path.join(BASE_DIR, "AZ/proclamations/2026/AZ_pronghorn_elk_2026.pdf")
    if not os.path.exists(pdf_path):
        print("  [AZ] PDF not found")
        return []

    rows = []
    in_elk = False
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ''
            if 'ELK' in text.upper():
                in_elk = True

            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if not row or len(row) < 4:
                        continue
                    first = (row[0] or '').strip()
                    # AZ hunt numbers are typically 4-digit
                    if re.match(r'^\d{3,5}$', first):
                        # Try to find dates in the row
                        row_text = ' '.join(str(c or '') for c in row)
                        dates = re.findall(
                            r'(\w+\.?\s+\d{1,2})\s*[-–]\s*(\w+\.?\s+\d{1,2})',
                            row_text
                        )
                        bag = ''
                        for cell in row:
                            cell_str = (cell or '').strip()
                            if any(w in cell_str.lower() for w in ['bull', 'cow', 'antlerless', 'either']):
                                bag = cell_str

                        if dates:
                            for open_str, close_str in dates:
                                open_d = parse_wy_date(open_str)
                                close_d = parse_wy_date(close_str)
                                if open_d and close_d:
                                    rows.append({
                                        'hunt_code': first,
                                        'open_date': open_d,
                                        'close_date': close_d,
                                        'bag_limit_description': bag,
                                        'notes': ''
                                    })

    print(f"  [AZ] Extracted {len(rows)} hunt season rows")
    return rows


def parse_generic_tables(state_code, pdf_filename, hunt_code_pattern=None):
    """Generic table parser for states with tabular data."""
    pdf_path = os.path.join(BASE_DIR, f"{state_code}/proclamations/2026/{pdf_filename}")
    if not os.path.exists(pdf_path):
        print(f"  [{state_code}] PDF not found: {pdf_filename}")
        return []

    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        page_count = len(pdf.pages)
        print(f"  [{state_code}] PDF has {page_count} pages")

        for page_num, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if not row or len(row) < 3:
                        continue
                    first = (row[0] or '').strip()
                    if not first:
                        continue
                    # Skip obvious headers
                    if re.match(r'^(Hunt|Unit|Season|Species|Code|Area|Weapon|Date|Page)', first, re.IGNORECASE):
                        continue

                    # If hunt code pattern specified, check it
                    if hunt_code_pattern and not re.match(hunt_code_pattern, first):
                        continue

                    row_text = ' '.join(str(c or '') for c in row)

                    # Find date patterns
                    dates = re.findall(
                        r'(\d{1,2}/\d{1,2}(?:/\d{2,4})?)\s*[-–]\s*(\d{1,2}/\d{1,2}(?:/\d{2,4})?)',
                        row_text
                    )
                    if not dates:
                        dates = re.findall(
                            r'(\w{3,9}\.?\s+\d{1,2}(?:,?\s+\d{4})?)\s*[-–]\s*(\w{3,9}\.?\s+\d{1,2}(?:,?\s+\d{4})?)',
                            row_text
                        )

                    for open_str, close_str in dates:
                        open_d = parse_wy_date(open_str)
                        close_d = parse_wy_date(close_str)
                        if open_d and close_d:
                            bag = ''
                            for cell in row:
                                cell_str = (cell or '').strip()
                                if any(w in cell_str.lower() for w in ['bull', 'cow', 'antlerless', 'either', 'buck', 'doe', 'spike']):
                                    bag = cell_str
                                    break
                            rows.append({
                                'hunt_code': first,
                                'open_date': open_d,
                                'close_date': close_d,
                                'bag_limit_description': bag,
                                'notes': f"Page {page_num + 1}"
                            })

    print(f"  [{state_code}] Extracted {len(rows)} hunt season rows")
    return rows


def parse_mt():
    """Parse Montana DEA regulations. Focus on deer/elk hunt districts."""
    pdf_path = os.path.join(BASE_DIR, "MT/proclamations/2026/MT_deer_elk_antelope_2026.pdf")
    if not os.path.exists(pdf_path):
        print("  [MT] PDF not found")
        return []

    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        print(f"  [MT] PDF has {len(pdf.pages)} pages")
        # MT regulations are complex with text-based seasons
        # Extract text and look for HD (hunting district) + date patterns
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text() or ''
            # Look for patterns like "HD 101" followed by dates
            for line in text.split('\n'):
                hd_match = re.search(r'HD\s+(\d+)', line)
                date_match = re.findall(
                    r'(\w{3,9}\.?\s+\d{1,2})\s*[-–through]+\s*(\w{3,9}\.?\s+\d{1,2})',
                    line
                )
                if hd_match and date_match:
                    hd = hd_match.group(1)
                    for open_str, close_str in date_match:
                        open_d = parse_wy_date(open_str)
                        close_d = parse_wy_date(close_str)
                        if open_d and close_d:
                            rows.append({
                                'hunt_code': f"HD-{hd}",
                                'open_date': open_d,
                                'close_date': close_d,
                                'bag_limit_description': '',
                                'notes': f"Page {page_num + 1}: {line.strip()[:150]}"
                            })

            # Also try tables
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if not row or len(row) < 3:
                        continue
                    first = (row[0] or '').strip()
                    if re.match(r'^\d{3,4}$', first):
                        row_text = ' '.join(str(c or '') for c in row)
                        dates = re.findall(
                            r'(\w{3,9}\.?\s+\d{1,2})\s*[-–]\s*(\w{3,9}\.?\s+\d{1,2})',
                            row_text
                        )
                        for open_str, close_str in dates:
                            open_d = parse_wy_date(open_str)
                            close_d = parse_wy_date(close_str)
                            if open_d and close_d:
                                rows.append({
                                    'hunt_code': first,
                                    'open_date': open_d,
                                    'close_date': close_d,
                                    'bag_limit_description': '',
                                    'notes': f"Page {page_num + 1}"
                                })

    print(f"  [MT] Extracted {len(rows)} hunt season rows")
    return rows


def parse_co():
    """Parse Colorado big game brochure. Very large PDF (~100+ pages)."""
    pdf_path = os.path.join(BASE_DIR, "CO/proclamations/2026/CO_big_game_brochure_2026.pdf")
    if not os.path.exists(pdf_path):
        print("  [CO] PDF not found")
        return []

    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        print(f"  [CO] PDF has {len(pdf.pages)} pages")
        for page_num, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if not row or len(row) < 3:
                        continue
                    first = (row[0] or '').strip()
                    # CO hunt codes: DE007R1, EE001O1, etc.
                    if re.match(r'^[A-Z]{2}\d{3}[A-Z]\d', first):
                        row_text = ' '.join(str(c or '') for c in row)
                        # CO dates often in format like "Oct 12 - Oct 16" or "10/12 - 10/16"
                        dates = re.findall(
                            r'(\w{3,9}\.?\s+\d{1,2})\s*[-–]\s*(\w{3,9}\.?\s+\d{1,2})',
                            row_text
                        )
                        if not dates:
                            dates = re.findall(
                                r'(\d{1,2}/\d{1,2})\s*[-–]\s*(\d{1,2}/\d{1,2})',
                                row_text
                            )
                        bag = ''
                        for cell in row:
                            cell_str = (cell or '').strip()
                            if any(w in cell_str.lower() for w in ['bull', 'cow', 'antlerless', 'either', 'buck', 'doe']):
                                bag = cell_str
                                break

                        for open_str, close_str in dates:
                            open_d = parse_wy_date(open_str)
                            close_d = parse_wy_date(close_str)
                            if open_d and close_d:
                                rows.append({
                                    'hunt_code': first,
                                    'open_date': open_d,
                                    'close_date': close_d,
                                    'bag_limit_description': bag,
                                    'notes': f"Page {page_num + 1}"
                                })

    print(f"  [CO] Extracted {len(rows)} hunt season rows")
    return rows


def parse_ut():
    """Parse Utah big game application guidebook."""
    pdf_path = os.path.join(BASE_DIR, "UT/proclamations/2026/UT_big_game_app_guidebook_2026.pdf")
    if not os.path.exists(pdf_path):
        print("  [UT] PDF not found")
        return []

    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        print(f"  [UT] PDF has {len(pdf.pages)} pages")
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text() or ''
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if not row or len(row) < 3:
                        continue
                    first = (row[0] or '').strip()
                    if not first:
                        continue
                    if re.match(r'^(Hunt|Unit|Season|Species|Code|Permit)', first, re.IGNORECASE):
                        continue
                    row_text = ' '.join(str(c or '') for c in row)
                    dates = re.findall(
                        r'(\w{3,9}\.?\s+\d{1,2})\s*[-–]\s*(\w{3,9}\.?\s+\d{1,2})',
                        row_text
                    )
                    for open_str, close_str in dates:
                        open_d = parse_wy_date(open_str)
                        close_d = parse_wy_date(close_str)
                        if open_d and close_d:
                            bag = ''
                            for cell in row:
                                cell_str = (cell or '').strip()
                                if any(w in cell_str.lower() for w in ['bull', 'cow', 'antlerless', 'either', 'buck', 'doe', 'spike']):
                                    bag = cell_str
                                    break
                            rows.append({
                                'hunt_code': first,
                                'open_date': open_d,
                                'close_date': close_d,
                                'bag_limit_description': bag,
                                'notes': f"Page {page_num + 1}"
                            })

    print(f"  [UT] Extracted {len(rows)} hunt season rows")
    return rows


def parse_id():
    """Parse Idaho big game seasons. Very large PDF."""
    pdf_path = os.path.join(BASE_DIR, "ID/proclamations/2026/ID_big_game_seasons_rules_2025.pdf")
    if not os.path.exists(pdf_path):
        print("  [ID] PDF not found")
        return []

    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        print(f"  [ID] PDF has {len(pdf.pages)} pages")
        for page_num, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if not row or len(row) < 3:
                        continue
                    first = (row[0] or '').strip()
                    # ID controlled hunt numbers are 4-digit
                    if re.match(r'^\d{3,4}$', first):
                        row_text = ' '.join(str(c or '') for c in row)
                        dates = re.findall(
                            r'(\w{3,9}\.?\s+\d{1,2})\s*[-–]\s*(\w{3,9}\.?\s+\d{1,2})',
                            row_text
                        )
                        if not dates:
                            dates = re.findall(
                                r'(\d{1,2}/\d{1,2})\s*[-–]\s*(\d{1,2}/\d{1,2})',
                                row_text
                            )
                        for open_str, close_str in dates:
                            open_d = parse_wy_date(open_str)
                            close_d = parse_wy_date(close_str)
                            if open_d and close_d:
                                rows.append({
                                    'hunt_code': first,
                                    'open_date': open_d,
                                    'close_date': close_d,
                                    'bag_limit_description': '',
                                    'notes': f"Page {page_num + 1}"
                                })

    print(f"  [ID] Extracted {len(rows)} hunt season rows")
    return rows


def parse_or():
    """Parse Oregon big game regulations."""
    pdf_path = os.path.join(BASE_DIR, "OR/proclamations/2026/OR_big_game_regulations_2026.pdf")
    if not os.path.exists(pdf_path):
        print("  [OR] PDF not found")
        return []

    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        print(f"  [OR] PDF has {len(pdf.pages)} pages")
        for page_num, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if not row or len(row) < 3:
                        continue
                    first = (row[0] or '').strip()
                    # OR hunt codes: 3-digit numbers (100s = deer, 200s = elk, 600s = antlerless deer)
                    if re.match(r'^\d{3}[A-Za-z]?$', first):
                        row_text = ' '.join(str(c or '') for c in row)
                        dates = re.findall(
                            r'(\w{3,9}\.?\s+\d{1,2})\s*[-–]\s*(\w{3,9}\.?\s+\d{1,2})',
                            row_text
                        )
                        for open_str, close_str in dates:
                            open_d = parse_wy_date(open_str)
                            close_d = parse_wy_date(close_str)
                            if open_d and close_d:
                                bag = ''
                                for cell in row:
                                    cell_str = (cell or '').strip()
                                    if any(w in cell_str.lower() for w in ['bull', 'cow', 'antlerless', 'either', 'buck', 'doe']):
                                        bag = cell_str
                                        break
                                rows.append({
                                    'hunt_code': first,
                                    'open_date': open_d,
                                    'close_date': close_d,
                                    'bag_limit_description': bag,
                                    'notes': f"Page {page_num + 1}"
                                })

    print(f"  [OR] Extracted {len(rows)} hunt season rows")
    return rows


def parse_wa():
    """Parse Washington big game hunting pamphlet."""
    pdf_path = os.path.join(BASE_DIR, "WA/proclamations/2026/WA_big_game_hunting_2025.pdf")
    if not os.path.exists(pdf_path):
        print("  [WA] PDF not found")
        return []

    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        print(f"  [WA] PDF has {len(pdf.pages)} pages")
        for page_num, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if not row or len(row) < 3:
                        continue
                    first = (row[0] or '').strip()
                    if not first:
                        continue
                    if re.match(r'^(Hunt|GMU|Season|Species|Permit|Area)', first, re.IGNORECASE):
                        continue
                    row_text = ' '.join(str(c or '') for c in row)
                    dates = re.findall(
                        r'(\w{3,9}\.?\s+\d{1,2})\s*[-–]\s*(\w{3,9}\.?\s+\d{1,2})',
                        row_text
                    )
                    for open_str, close_str in dates:
                        open_d = parse_wy_date(open_str)
                        close_d = parse_wy_date(close_str)
                        if open_d and close_d:
                            rows.append({
                                'hunt_code': first,
                                'open_date': open_d,
                                'close_date': close_d,
                                'bag_limit_description': '',
                                'notes': f"Page {page_num + 1}"
                            })

    print(f"  [WA] Extracted {len(rows)} hunt season rows")
    return rows


def parse_ca():
    """Parse California mammal hunting regulations."""
    pdf_path = os.path.join(BASE_DIR, "CA/proclamations/2026/CA_mammal_hunting_regulations_2025_2026.pdf")
    if not os.path.exists(pdf_path):
        print("  [CA] PDF not found")
        return []

    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        print(f"  [CA] PDF has {len(pdf.pages)} pages")
        for page_num, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if not row or len(row) < 3:
                        continue
                    first = (row[0] or '').strip()
                    # CA deer zone codes: A, B1-B6, C1-C4, D3-D19, X1-X12
                    if re.match(r'^[A-DXa-dx]\d{0,2}[A-Za-z]?$', first) and len(first) <= 4:
                        row_text = ' '.join(str(c or '') for c in row)
                        dates = re.findall(
                            r'(\w{3,9}\.?\s+\d{1,2})\s*[-–]\s*(\w{3,9}\.?\s+\d{1,2})',
                            row_text
                        )
                        for open_str, close_str in dates:
                            open_d = parse_wy_date(open_str)
                            close_d = parse_wy_date(close_str)
                            if open_d and close_d:
                                bag = ''
                                for cell in row:
                                    cell_str = (cell or '').strip()
                                    if any(w in cell_str.lower() for w in ['buck', 'doe', 'antlerless', 'either']):
                                        bag = cell_str
                                        break
                                rows.append({
                                    'hunt_code': first,
                                    'open_date': open_d,
                                    'close_date': close_d,
                                    'bag_limit_description': bag,
                                    'notes': f"Page {page_num + 1}"
                                })

    print(f"  [CA] Extracted {len(rows)} hunt season rows")
    return rows


def write_csv(state_code, rows):
    """Write rows to CSV file."""
    if not rows:
        print(f"  [{state_code}] No rows to write")
        return None

    csv_dir = os.path.join(BASE_DIR, f"{state_code}/proclamations/2026")
    os.makedirs(csv_dir, exist_ok=True)
    csv_path = os.path.join(csv_dir, f"{state_code}_hunt_dates_2026.csv")

    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['hunt_code', 'open_date', 'close_date', 'bag_limit_description', 'notes'])
        writer.writeheader()
        writer.writerows(rows)

    print(f"  [{state_code}] Wrote {len(rows)} rows to {csv_path}")
    return csv_path


def main():
    results = {}

    # Parse WY elk and deer
    print("\n=== Wyoming ===")
    wy_elk = parse_wy('elk')
    wy_deer = parse_wy('deer')
    wy_all = wy_elk + wy_deer
    results['WY'] = write_csv('WY', wy_all)

    # Parse NV
    print("\n=== Nevada ===")
    nv_rows = parse_nv()
    results['NV'] = write_csv('NV', nv_rows)

    # Parse AZ (elk only from available PDF)
    print("\n=== Arizona ===")
    az_rows = parse_az()
    results['AZ'] = write_csv('AZ', az_rows)

    # Parse MT
    print("\n=== Montana ===")
    mt_rows = parse_mt()
    results['MT'] = write_csv('MT', mt_rows)

    # Parse CO (large PDF)
    print("\n=== Colorado ===")
    co_rows = parse_co()
    results['CO'] = write_csv('CO', co_rows)

    # Parse UT
    print("\n=== Utah ===")
    ut_rows = parse_ut()
    results['UT'] = write_csv('UT', ut_rows)

    # Parse ID
    print("\n=== Idaho ===")
    id_rows = parse_id()
    results['ID'] = write_csv('ID', id_rows)

    # Parse OR
    print("\n=== Oregon ===")
    or_rows = parse_or()
    results['OR'] = write_csv('OR', or_rows)

    # Parse WA
    print("\n=== Washington ===")
    wa_rows = parse_wa()
    results['WA'] = write_csv('WA', wa_rows)

    # Parse CA
    print("\n=== California ===")
    ca_rows = parse_ca()
    results['CA'] = write_csv('CA', ca_rows)

    # NM already has 2026 dates in DB
    print("\n=== New Mexico ===")
    print("  [NM] 2026 hunt dates already loaded in database (891 hunts)")
    results['NM'] = 'already_loaded'

    # Summary
    print("\n" + "=" * 60)
    print("PARSE SUMMARY")
    print("=" * 60)
    for state, result in results.items():
        if result == 'already_loaded':
            print(f"  {state}: Already in database")
        elif result:
            print(f"  {state}: CSV written to {result}")
        else:
            print(f"  {state}: No data extracted")

    return results


if __name__ == '__main__':
    main()
