# Proclamation Research + Parse Task

Find, download, and parse the 2026 big game hunting proclamation (or regulations booklet)
for all 11 states. Extract hunt season dates and bag limits for every deer and elk hunt.
Load results into the PostgreSQL database.

DB: host=localhost port=5432 dbname=draws user=draws password=drawspass

Do NOT stop to ask questions. Make best judgment and keep going.

---

## Phase 1: Find and Download All 11 Proclamations

For each state below, search for the 2026 big game hunting proclamation or regulations PDF.
It may also be called: "Big Game Proclamation", "Hunting Regulations", "Draw Application Guide",
"Deer and Elk Seasons", "Big Game Seasons and Bag Limits", etc.
Released Jan–March each year by the state wildlife agency.

Save each PDF to: /Users/openclaw/Documents/GraysonsDrawOdds/{STATE}/proclamations/2026/
Create the directory if it doesn't exist.

Use curl or wget to download. If a PDF is behind a form or JavaScript wall, save
the direct URL to a file called MANUAL_DOWNLOAD.txt in that state's proclamations folder.

### State agencies and starting URLs:

**NM — New Mexico Department of Game and Fish**
Start: https://www.wildlife.state.nm.us/hunting/big-game/
Look for: "Big Game Proclamation 2025-2026" or "2026 Deer and Elk Proclamation"
Target: /Users/openclaw/Documents/GraysonsDrawOdds/NM/proclamations/2026/

**AZ — Arizona Game and Fish Department**
Start: https://www.azgfd.com/hunting/draw/biggame/
Look for: "2026 Hunt Regulations" or "Deer and Elk Application Booklet"
Also check: https://www.azgfd.com/hunting/regulations/
Target: /Users/openclaw/Documents/GraysonsDrawOdds/AZ/proclamations/2026/

**CO — Colorado Parks and Wildlife**
Start: https://cpw.state.co.us/thingstodo/Pages/BigGameDraws.aspx
Look for: "2026 Deer and Elk Season Dates" or "Big Game Hunting Regulations"
Also check: https://cpw.state.co.us/thingstodo/Pages/Regulations.aspx
Target: /Users/openclaw/Documents/GraysonsDrawOdds/CO/proclamations/2026/

**UT — Utah Division of Wildlife Resources**
Start: https://wildlife.utah.gov/hunting/big-game.html
Look for: "2026 Big Game Proclamation" or "Deer/Elk Proclamation"
Also check: https://wildlife.utah.gov/proclamations-and-regulations.html
Target: /Users/openclaw/Documents/GraysonsDrawOdds/UT/proclamations/2026/

**NV — Nevada Department of Wildlife**
Start: https://www.ndow.org/hunt/big-game/
Look for: "2026 Big Game Seasons and Bag Limits" or hunting regulations
Also check: https://www.ndow.org/regulations/
Target: /Users/openclaw/Documents/GraysonsDrawOdds/NV/proclamations/2026/

**MT — Montana Fish, Wildlife and Parks**
Start: https://fwp.mt.gov/hunting/regulations
Look for: "2026 Deer and Elk Regulations" or "Montana Hunting Regulations"
Also check: https://myfwp.mt.gov/fwpPub/drawingStatistics
Target: /Users/openclaw/Documents/GraysonsDrawOdds/MT/proclamations/2026/

**ID — Idaho Department of Fish and Game**
Start: https://idfg.idaho.gov/hunt/draw
Look for: "2026 Big Game Season Dates" or "Deer and Elk Proclamation"
Also check: https://idfg.idaho.gov/rules/big-game
Target: /Users/openclaw/Documents/GraysonsDrawOdds/ID/proclamations/2026/

**WY — Wyoming Game and Fish Department**
Start: https://wgfd.wyo.gov/Hunting/Apply-for-Hunts
Look for: "2026 Deer and Elk Regulations" or "Wyoming Hunting Regulations"
Also check: https://wgfd.wyo.gov/Regulations
Target: /Users/openclaw/Documents/GraysonsDrawOdds/WY/proclamations/2026/

**OR — Oregon Department of Fish and Wildlife**
Start: https://myodfw.com/hunting/species/elk-deer
Look for: "2026 Oregon Big Game Regulations" or similar
Also check: https://myodfw.com/hunting/regulations
Target: /Users/openclaw/Documents/GraysonsDrawOdds/OR/proclamations/2026/

**WA — Washington Department of Fish and Wildlife**
Start: https://wdfw.wa.gov/hunting/big-game
Look for: "2026 Washington Big Game Hunting Pamphlet" or regulations
Also check: https://wdfw.wa.gov/licenses/hunting/regulations
Target: /Users/openclaw/Documents/GraysonsDrawOdds/WA/proclamations/2026/

**CA — California Department of Fish and Wildlife**
Start: https://www.wildlife.ca.gov/Hunting/Big-Game
Look for: "2026 California Deer Hunting Regulations" or "Elk Season Dates"
Also check: https://www.wildlife.ca.gov/Regulations
Target: /Users/openclaw/Documents/GraysonsDrawOdds/CA/proclamations/2026/

---

## Phase 2: Install pdfplumber

pip3 install pdfplumber tabula-py pandas openpyxl 2>/dev/null || pip install pdfplumber tabula-py pandas openpyxl

---

## Phase 3: Parse Hunt Dates from Each Proclamation

For each PDF successfully downloaded, write a Python parser script to extract
hunt season dates for deer and elk.

### What to look for in the PDFs:
- Tables or lists with: Hunt Number/Code | Season Dates | Bag Limit
- Date formats: "Oct 1-15", "October 1 through 15", "10/1-10/15"
- Hunt codes that match the format already in the database for that state
  (NM: "ELK-1-197" style; AZ: 4-digit numbers; CO: "DE007R1" style, etc.)

### Output format for each state:
Write a CSV file {STATE}/proclamations/2026/{STATE}_hunt_dates_2026.csv with columns:
  hunt_code, open_date, close_date, bag_limit_description, notes

Dates in ISO format: YYYY-MM-DD

### Parser approach:
1. Use pdfplumber to extract tables: pdf.pages[n].extract_tables()
2. If tables fail, extract text: pdf.pages[n].extract_text() and use regex
3. For each row/line, look for the hunt code pattern for that state, then parse dates
4. If a hunt has multiple seasons (e.g., archery + rifle), create one row per season period

Write the parser as a separate script per state:
/Users/openclaw/Documents/GraysonsDrawOdds/{STATE}/proclamations/parse_{state_lower}_2026.py

---

## Phase 4: Load Dates and Bag Limits into Database

After parsing, load the CSV data into the PostgreSQL database.

### hunt_dates table:
```sql
INSERT INTO hunt_dates (hunt_id, season_year, open_date, close_date, notes)
SELECT h.id, 2026, %s, %s, %s
FROM hunts h
JOIN states s ON s.id = h.state_id
WHERE s.state_code = %s AND h.hunt_code = %s
ON CONFLICT (hunt_id, season_year) DO UPDATE
  SET open_date = EXCLUDED.open_date,
      close_date = EXCLUDED.close_date,
      notes = EXCLUDED.notes;
```

### bag_limits table (add/update):
If the proclamation has bag limit descriptions that differ from what's in the DB,
update bag_limits.bag_description for the matching hunt_id.

Write the loader as:
/Users/openclaw/Documents/GraysonsDrawOdds/scripts/load_proclamation_dates.py

It should accept arguments: --state NM --csv NM/proclamations/2026/NM_hunt_dates_2026.csv

---

## Phase 5: Summary Report

Write /Users/openclaw/Documents/GraysonsDrawOdds/PROCLAMATION_RESULTS.md with:
- Which PDFs were found and downloaded (file size, pages)
- Which PDFs need manual download (URL provided, why it failed)
- Parse results per state: how many hunt codes matched, how many dates extracted
- Load results: rows inserted/updated per state
- Any hunt codes in the proclamation that don't match existing hunt_codes in DB
- Overall data quality notes per state

---

## Phase 6: Commit

cd /Users/openclaw/Documents/GraysonsDrawOdds
git add -A
git commit -m "Proclamation data: 2026 hunt dates and bag limits parsed for available states"

---

## IMPORTANT NOTES

- NM has ~891 hunts in the DB. The proclamation may only list dates for active 2026 hunts
  (some hunt codes may be retired). That's fine — only load what matches.
- Hunt codes must match EXACTLY what's in the database for that state (case-sensitive)
- If you can't find the 2026 proclamation, try the 2025 one — dates shift slightly
  but structure is identical. Note it in the report.
- Some states publish dates in the draw application guide, not the proclamation.
  Check both.
- If a PDF is 100+ pages, focus on the deer and elk sections only.
- WA publishes dates in a "Hunting Pamphlet" separate from draw odds.
- ID publishes dates in the "Big Game Seasons and Rules" booklet.
- Don't spend more than 10 minutes on any one state's PDF if parsing is intractable.
  Note it in the report and move on.
