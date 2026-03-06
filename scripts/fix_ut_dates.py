#!/usr/bin/env python3
"""Parse UT big game PDF proclamation and load hunt dates into the database."""

import re
import pdfplumber
import psycopg2
from datetime import date

PDF_PATH = "/Users/openclaw/Documents/GraysonsDrawOdds/UT/proclamations/2026/UT_big_game_app_guidebook_2026.pdf"
DB_PARAMS = dict(host="localhost", port=5432, dbname="draws", user="draws", password="drawspass")
SEASON_YEAR = 2026

HUNT_CODE_RE = re.compile(r'^[DEPMGRSBC][A-Z]\d{4}$')

MONTH_MAP = {
    'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
    'Jul': 7, 'Aug': 8, 'Sep': 9, 'Sept': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12,
}

# Pattern: "Mon. DD" or "Mon DD" with optional ", YYYY"
DATE_RE = re.compile(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+(\d{1,2})(?:,\s*(\d{4}))?')


def parse_date(text, default_year=SEASON_YEAR):
    """Parse a date string like 'Aug. 15' or 'Jan. 15, 2027' into a date object."""
    m = DATE_RE.search(text)
    if not m:
        return None
    month = MONTH_MAP[m.group(1)]
    day = int(m.group(2))
    year = int(m.group(3)) if m.group(3) else default_year
    return date(year, month, day)


def parse_date_range(text):
    """Parse a date range like 'Aug. 15–Sept. 11' or 'Nov. 7, 2026–Jan. 31, 2027'.
    Returns (start_date, end_date) or None."""
    # Normalize dashes
    text = text.replace('–', '-').replace('—', '-')

    # Split on dash that separates dates (not within a date like "2026-Jan")
    # Find the main separator dash between two date expressions
    parts = re.split(r'-(?=[A-Z])', text, maxsplit=1)
    if len(parts) == 2:
        start = parse_date(parts[0])
        end = parse_date(parts[1])
        if start and end:
            # If end month < start month and no explicit year on end, it's next year
            if end < start and not re.search(r'\d{4}', parts[1]):
                end = end.replace(year=end.year + 1)
            return start, end

    # Try: "Mon. DD-DD" (same month range like "Oct. 7-11")
    m = re.match(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+(\d{1,2})-(\d{1,2})(?:,\s*(\d{4}))?', text)
    if m:
        month = MONTH_MAP[m.group(1)]
        day1 = int(m.group(2))
        day2 = int(m.group(3))
        year = int(m.group(4)) if m.group(4) else SEASON_YEAR
        return date(year, month, day1), date(year, month, day2)

    return None


def extract_hunt_dates_from_pdf(pdf_path):
    """Extract all (hunt_code, start_date, end_date) tuples from the PDF."""
    results = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            if not tables:
                continue
            for table in tables:
                for row in table:
                    if not row or len(row) < 2:
                        continue
                    # Find the hunt code - could be in any column
                    hunt_code = None
                    date_col = None
                    for i, cell in enumerate(row):
                        if cell and HUNT_CODE_RE.match(cell.strip()):
                            hunt_code = cell.strip()
                            # Date is typically in the last column that has date-like content
                            # Check remaining columns for dates
                            for j in range(i + 1, len(row)):
                                if row[j] and DATE_RE.search(row[j]):
                                    date_col = row[j]
                            break

                    if not hunt_code or not date_col:
                        continue

                    # Handle multiple seasons per cell (split on newline)
                    date_lines = date_col.split('\n')
                    for line in date_lines:
                        line = line.strip()
                        # Strip leading label like "Archery: " or "Any legal weapon: "
                        line = re.sub(r'^[^:]+:\s*', '', line) if ':' in line else line

                        parsed = parse_date_range(line)
                        if parsed:
                            results.append((hunt_code, parsed[0], parsed[1]))

    return results


def main():
    print(f"Parsing PDF: {PDF_PATH}")
    hunt_dates = extract_hunt_dates_from_pdf(PDF_PATH)

    # Deduplicate: keep last occurrence per hunt_code (in case of dupes)
    seen = {}
    for hunt_code, start, end in hunt_dates:
        seen[hunt_code] = (start, end)

    unique_codes = set(seen.keys())
    print(f"Total hunt codes found in PDF: {len(unique_codes)}")

    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()

    # Look up hunt_ids for all codes
    matched = 0
    inserted = 0
    not_found = []

    for hunt_code, (start_date, end_date) in sorted(seen.items()):
        cur.execute(
            "SELECT h.hunt_id FROM hunts h JOIN states s ON s.state_id = h.state_id "
            "WHERE s.state_code = 'UT' AND h.hunt_code = %s",
            (hunt_code,)
        )
        row = cur.fetchone()
        if not row:
            not_found.append(hunt_code)
            continue

        hunt_id = row[0]
        matched += 1

        cur.execute(
            """INSERT INTO hunt_dates (hunt_id, season_year, start_date, end_date)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (hunt_id, season_year) DO UPDATE
               SET start_date = EXCLUDED.start_date, end_date = EXCLUDED.end_date""",
            (hunt_id, SEASON_YEAR, start_date, end_date)
        )
        inserted += 1

    conn.commit()
    cur.close()
    conn.close()

    print(f"Total matched to DB: {matched}")
    print(f"Total dates inserted/updated: {inserted}")
    if not_found:
        print(f"Hunt codes not found in DB ({len(not_found)}): {', '.join(sorted(not_found)[:20])}{'...' if len(not_found) > 20 else ''}")


if __name__ == "__main__":
    main()
