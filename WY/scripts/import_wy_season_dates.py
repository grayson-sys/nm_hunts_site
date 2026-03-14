#!/usr/bin/env python3
"""
Import WY 2025 season dates for ANT, MOOS, BHS from WGFD regulation PDFs.
ELK and MDR already imported from wy_elk_seasons.txt / wy_deer_seasons.txt.

Hunt code format in DB:  ANT-{area}-{type}  MOOS-{area}-{type}  BHS-{area}-{type}
PDF format: Area | Type | Archery Opens | Closes | Regular Opens | Closes

Season year stored as 2025 (hunt year, not calendar year of end date).
"""
import pdfplumber, re, sqlite3
from datetime import datetime

DB = '/Users/openclaw/sleeperunits/draws.db'

MONTHS = {m[:3]: i+1 for i, m in enumerate([
    'January','February','March','April','May','June',
    'July','August','September','October','November','December'])}

DATE_RE = re.compile(
    r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z.]*\.?\s+(\d{1,2})', re.I)

PDFS = [
    ('/Users/openclaw/Documents/GraysonsDrawOdds/WY/raw_data/wy_antelope_seasons_2025.pdf', 'ANT'),
    ('/Users/openclaw/Documents/GraysonsDrawOdds/WY/raw_data/wy_moose_seasons_2025.pdf',   'MOOS'),
    ('/Users/openclaw/Documents/GraysonsDrawOdds/WY/raw_data/wy_bhs_seasons_2025.pdf',     'BHS'),
]

def mk_date(mon, day, year=2025):
    mn = MONTHS.get(mon.capitalize()[:3])
    if not mn: return None
    try: return datetime(year, mn, int(day)).strftime('%Y-%m-%d')
    except: return None

def parse_pdf(pdf_path, prefix):
    results = {}
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            words = page.extract_words(x_tolerance=4, y_tolerance=3)
            rows = {}
            for w in words:
                y = round(w['top'], 0)
                rows.setdefault(y, []).append((w['x0'], w['text']))
            for row_items in sorted(rows.values(), key=lambda r: r[0][0]):
                texts = [t for _, t in sorted(row_items)]
                row_str = ' '.join(texts)
                # Area number(s) at start, then type, then dates
                m = re.match(r'^(\d+)(?:\s*,\s*\d+)*\s+(\d+)\s+', row_str)
                if not m: continue
                area_raw = m.group(1)   # just the first area (handle multi-area separately)
                typ = m.group(2)
                dates = DATE_RE.findall(row_str)
                if len(dates) >= 4:
                    arch_s = mk_date(*dates[0])
                    arch_e = mk_date(*dates[1])
                    reg_s  = mk_date(*dates[2])
                    reg_e  = mk_date(*dates[3])
                    # If end month < start month, bump end year
                    if reg_e and reg_s and reg_e < reg_s:
                        reg_e = mk_date(*dates[3], year=2026)
                elif len(dates) == 2:
                    arch_s = arch_e = None
                    reg_s = mk_date(*dates[0])
                    reg_e = mk_date(*dates[1])
                    if reg_e and reg_s and reg_e < reg_s:
                        reg_e = mk_date(*dates[1], year=2026)
                else:
                    continue

                # Build code — type 7/8 = archery (use arch dates), else regular
                is_archery = typ in ('7', '8')
                start = arch_s if is_archery and arch_s else reg_s
                end   = arch_e if is_archery and arch_e else reg_e
                if start and end:
                    code = f"{prefix}-{area_raw}-{typ}"
                    if code not in results:
                        results[code] = (start, end)

            # Also handle multi-area rows like "7 8 9  1  Sep. 1 Sep. 30 Oct. 1 Oct. 31"
            # These appear when multiple areas share the same type/dates
            for row_items in sorted(rows.values(), key=lambda r: r[0][0]):
                texts = [t for _, t in sorted(row_items)]
                row_str = ' '.join(texts)
                # Multi-area: starts with multiple numbers before type
                m = re.match(r'^(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+', row_str)
                if not m: continue
                dates = DATE_RE.findall(row_str)
                if not dates: continue
                # Try each leading number as an area, last before dates as type
                nums_before_dates = re.findall(r'\b(\d+)\b', row_str.split(dates[0][0])[0])
                if len(nums_before_dates) >= 2:
                    typ_candidate = nums_before_dates[-1]
                    for area_n in nums_before_dates[:-1]:
                        code = f"{prefix}-{area_n}-{typ_candidate}"
                        if code not in results and len(dates) >= 2:
                            is_archery = typ_candidate in ('7','8')
                            if len(dates) >= 4:
                                s = mk_date(*dates[0]) if is_archery else mk_date(*dates[2])
                                e = mk_date(*dates[1]) if is_archery else mk_date(*dates[3])
                            else:
                                s = mk_date(*dates[0])
                                e = mk_date(*dates[1])
                            if s and e:
                                results[code] = (s, e)
    return results

# --- Main ---
conn = sqlite3.connect(DB)
cur  = conn.cursor()
wy_id = cur.execute("SELECT state_id FROM states WHERE state_code='WY'").fetchone()[0]
wy_hunts = {r[0]: r[1] for r in cur.execute(
    "SELECT hunt_code, hunt_id FROM hunts WHERE state_id=?", (wy_id,))}
already_dated = {r[0] for r in cur.execute("""
    SELECT hd.hunt_id FROM hunt_dates hd JOIN hunts h ON h.hunt_id=hd.hunt_id
    WHERE h.state_id=?""", (wy_id,))}

total_inserted = 0
for pdf_path, prefix in PDFS:
    parsed = parse_pdf(pdf_path, prefix)
    inserted = no_match = already = 0
    for code, (s, e) in parsed.items():
        if code not in wy_hunts: no_match += 1; continue
        hid = wy_hunts[code]
        if hid in already_dated: already += 1; continue
        cur.execute(
            "INSERT OR IGNORE INTO hunt_dates (hunt_id, season_year, start_date, end_date) VALUES (?,2025,?,?)",
            (hid, s, e))
        inserted += 1
        already_dated.add(hid)
    total_inserted += inserted
    print(f"{prefix}: parsed={len(parsed)} inserted={inserted} no_match={no_match} already={already}")

conn.commit()
conn.close()

print(f"\nTotal inserted: {total_inserted}")

# Coverage
conn2 = sqlite3.connect(DB)
rows = conn2.execute("""
    SELECT sp.species_code, COUNT(DISTINCT h.hunt_id) t, COUNT(DISTINCT hd.hunt_id) d
    FROM hunts h JOIN species sp ON sp.species_id=h.species_id
    LEFT JOIN hunt_dates hd ON hd.hunt_id=h.hunt_id
    WHERE h.state_id=(SELECT state_id FROM states WHERE state_code='WY')
    GROUP BY sp.species_code ORDER BY d*1.0/t""").fetchall()
conn2.close()
print("\nWY coverage:")
for sp,t,d in rows:
    print(f"  {sp:5}: {d}/{t} ({100*d//max(t,1)}%)")
