#!/usr/bin/env python3
"""
Import UT 2026 season dates from ut_biggame_app_guidebook_2025.pdf
Tables format: Hunt name | Hunt code | Season dates
EA/DA (antlerless) codes NOT in this PDF — need separate UT Antlerless Guidebook.
"""
import pdfplumber, re, sqlite3
from datetime import datetime

DB  = '/Users/openclaw/sleeperunits/draws.db'
PDF = '/Users/openclaw/Documents/GraysonsDrawOdds/UT/raw_data/ut_biggame_app_guidebook_2025.pdf'

MONTHS = {m[:3]: i+1 for i, m in enumerate([
    'January','February','March','April','May','June',
    'July','August','September','October','November','December'])}

HUNT_RE = re.compile(r'^[A-Z]{2}\d{4}$')
# Dates like "Aug. 15–Sept. 16" or "Oct. 3–Oct. 15" or "Sept. 12–22"
DATE_RE = re.compile(
    r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z.]*\.?\s+(\d{1,2})'
    r'\s*[–\-—]+\s*'
    r'(?:(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z.]*\.?\s+)?(\d{1,2})',
    re.I)

def parse_date(text, season_year=2026):
    """Parse a relative date string like 'Oct. 3–Oct. 15' or 'Aug. 15–Sept. 16'"""
    m = DATE_RE.search(text)
    if not m: return None, None
    sm, sd, em, ed = m.groups()
    try:
        sy = int(sd)
        ey = int(ed)
        sm_n = MONTHS[sm.capitalize()[:3]]
        em_n = MONTHS[em.capitalize()[:3]] if em else sm_n
        s_yr = season_year
        e_yr = season_year
        # If end month < start month, end is next year (e.g., Dec–Jan)
        if em_n < sm_n:
            e_yr = season_year + 1
        start = datetime(s_yr, sm_n, sy).strftime('%Y-%m-%d')
        end   = datetime(e_yr, em_n, ey).strftime('%Y-%m-%d')
        return start, end
    except:
        return None, None

# --- Extract from PDF ---
pdf_dates = {}  # hunt_code -> (start, end, page)
with pdfplumber.open(PDF) as pdf:
    for i, page in enumerate(pdf.pages):
        tables = page.extract_tables()
        for t in tables:
            prev_dates = None
            for row in t:
                if not row: continue
                # Find hunt code cell — usually col 1 but sometimes col 0
                code = None
                date_str = None
                for j, cell in enumerate(row):
                    if cell and HUNT_RE.match(str(cell).strip()):
                        code = str(cell).strip()
                        # Date should be in next column
                        if j + 1 < len(row) and row[j+1]:
                            date_str = str(row[j+1]).strip()
                        break

                if code and date_str:
                    s, e = parse_date(date_str)
                    if s and code not in pdf_dates:
                        pdf_dates[code] = (s, e, i+1)
                        prev_dates = (s, e)
                elif code and prev_dates:
                    # Code present but no date — inherit from previous row (same season block)
                    if code not in pdf_dates:
                        pdf_dates[code] = (prev_dates[0], prev_dates[1], i+1)

print(f"Extracted {len(pdf_dates)} hunt codes with dates from PDF")
by_prefix = {}
for k in pdf_dates:
    p = k[:2]
    by_prefix[p] = by_prefix.get(p, 0) + 1
for p, n in sorted(by_prefix.items()):
    print(f"  {p}: {n}")

# --- Insert into DB ---
conn = sqlite3.connect(DB)
cur  = conn.cursor()

ut_id = cur.execute("SELECT state_id FROM states WHERE state_code='UT'").fetchone()[0]
# All UT hunt codes
ut_hunts = {r[0]: r[1] for r in cur.execute(
    "SELECT hunt_code, hunt_id FROM hunts WHERE state_id=?", (ut_id,))}
# Already dated hunts for season 2026
already_dated = {r[0] for r in cur.execute("""
    SELECT hd.hunt_id FROM hunt_dates hd
    JOIN hunts h ON h.hunt_id=hd.hunt_id
    WHERE h.state_id=? AND hd.season_year=2026""", (ut_id,))}

inserted = already = no_match = 0
for code, (s, e, pg) in pdf_dates.items():
    if code not in ut_hunts:
        no_match += 1
        continue
    hid = ut_hunts[code]
    if hid in already_dated:
        already += 1
        continue
    cur.execute(
        "INSERT OR IGNORE INTO hunt_dates (hunt_id, season_year, start_date, end_date) VALUES (?,2026,?,?)",
        (hid, s, e))
    inserted += 1

conn.commit()
conn.close()

print(f"\nInserted: {inserted} | Already dated: {already} | No DB match: {no_match}")

# --- Coverage report ---
conn2 = sqlite3.connect(DB)
rows = conn2.execute("""
    SELECT sp.species_code,
      SUBSTR(h.hunt_code,1,2) as prefix,
      COUNT(DISTINCT h.hunt_id) total,
      COUNT(DISTINCT hd.hunt_id) with_dates
    FROM hunts h
    JOIN species sp ON sp.species_id=h.species_id
    LEFT JOIN hunt_dates hd ON hd.hunt_id=h.hunt_id AND hd.season_year=2026
    WHERE h.state_id=(SELECT state_id FROM states WHERE state_code='UT')
    GROUP BY sp.species_code, prefix
    HAVING total > 2
    ORDER BY sp.species_code, prefix
""").fetchall()
print("\nUT coverage after import:")
for r in rows:
    pct = 100*r[3]//max(r[2],1)
    bar = '█' * (pct//10) + '░' * (10 - pct//10)
    print(f"  {r[0]:4} {r[1]}: {bar} {r[3]}/{r[2]} ({pct}%)")
conn2.close()
