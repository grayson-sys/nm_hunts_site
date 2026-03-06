# Overnight Data Load — WY, AZ, CO

Load Wyoming, Arizona, and Colorado draw odds and harvest data into PostgreSQL.
Work through all three states sequentially. Do NOT stop to ask questions.
Take as long as you need. Write all scripts to /scripts/.

DB: host=localhost port=5432 dbname=draws user=draws password=drawspass
Project root: /Users/openclaw/Documents/GraysonsDrawOdds/

SCHEMA NOTES (learned from existing data):
- Primary keys: states.state_id, hunts.hunt_id, gmus.gmu_id, draw_results_by_pool.result_id
- harvest_stats PK: harvest_id; columns: hunt_id, harvest_year, access_type, success_rate
- hunt_dates columns: hunt_date_id, hunt_id, season_year, start_date, end_date
- draw_results_by_pool columns: result_id, hunt_id, draw_year, pool_id, applications
  (pool_id is a foreign key — check pools table for pool_id values)
- gmus has NO species_context column — check actual schema before using it
- Always check column names against information_schema before writing INSERT statements

ALWAYS CHECK SCHEMA FIRST:
```python
cur.execute("""SELECT column_name FROM information_schema.columns 
               WHERE table_name=%s ORDER BY ordinal_position""", (table_name,))
```

---

## STATE 1: WYOMING

### Source PDFs:
WY/raw_data/2024_draw_odds_report.pdf    ← main odds report
WY/raw_data/2025_draw_odds_report.pdf    ← main odds report  
WY/raw_data/2025_elk_prefpoints_res.pdf  ← elk preference points, resident
WY/raw_data/2025_elk_prefpoints_nonres.pdf
WY/raw_data/2025_elk_random_res.pdf      ← elk random draw results, resident
WY/raw_data/2025_elk_random_nonres.pdf
WY/raw_data/2025_elk_leftover_res.pdf
WY/raw_data/2025_elk_leftover_nonres.pdf
WY/raw_data/2025_deer_prefpoints_res.pdf
WY/raw_data/2025_deer_prefpoints_nonres.pdf
WY/raw_data/2025_deer_random_res.pdf
WY/raw_data/2025_deer_random_nonres.pdf
WY/raw_data/2025_deer_leftover_res.pdf
WY/raw_data/2025_deer_leftover_nonres.pdf
WY/raw_data/2025_elk_cowcalf_res.pdf
WY/raw_data/2025_elk_cowcalf_nonres.pdf
WY/raw_data/2024_elk_harvest_report.pdf
WY/raw_data/2025_elk_harvest_report.pdf
WY/raw_data/2024_deer_harvest_report.pdf
WY/raw_data/2025_deer_harvest_report.pdf
WY/proclamations/2026/WY_hunt_dates_2026.csv

### Step 1: Inspect the PDFs with pdfplumber
```python
import pdfplumber

# Start with main odds report to understand column structure
with pdfplumber.open('WY/raw_data/2025_draw_odds_report.pdf') as pdf:
    for i, page in enumerate(pdf.pages[:5]):
        tables = page.extract_tables()
        if tables:
            print(f"Page {i+1} tables:", len(tables))
            for t in tables:
                print("  Headers:", t[0] if t else "empty")
                if len(t) > 1: print("  Sample:", t[1])
        text = page.extract_text()
        if text: print(f"Page {i+1} text[:200]:", text[:200])
```

Typical WY draw odds report columns:
  Hunt Area | Type | Quota | Applications | Successful | Odds | Points Required
OR sometimes split by residency in separate tables.

### Step 2: Parse each PDF and extract hunt data
For each PDF, extract:
- Hunt Area (the hunt code — e.g., "1", "2", "6", "84", "117", "123")
- Type (license type — e.g., "1", "Gen", "6", "7", "8")
- Combined hunt code: "{area}-{type}" e.g., "1-1", "6-Gen", "84-1", "117-8"
- Quota (tags available)
- Applications (applicants)
- Successful (tags drawn)
- Odds (drawn/apps, or compute it)
- Pool: infer from filename (prefpoints_res=RES_PREF, prefpoints_nonres=NR_PREF,
  random_res=RES_RAND, random_nonres=NR_RAND, leftover_res=RES_LEFT, etc.)
  For the combined draw odds report: check if residency is a column

Species: infer from filename (elk_ or deer_)

### Step 3: Get WY state_id and pool IDs
```python
cur.execute("SELECT state_id FROM states WHERE state_code='WY'")
wy_state_id = cur.fetchone()[0]

# Get pools table structure
cur.execute("SELECT * FROM pools LIMIT 5")  # or check schema
# WY pools: RES (resident), NR (nonresident)
# May need to look up pool_id by pool_code
```

### Step 4: Insert WY GMUs
gmu_code = Hunt Area number as text (e.g., "1", "6", "84", "117")
gmu_name = "Hunt Area {number}" 
gmu_sort_key = zero-pad to 5 chars

### Step 5: Insert WY hunts
hunt_code = "{area}-{type}" format (matching proclamation CSV: "1-1", "6-Gen", etc.)
weapon_type_id: look up from weapon_types table (check schema)
  WY Type 1 = general elk, Type 6/7/8 = special management hunts
  Default weapon type: 'RIFLE' for most WY elk/deer

### Step 6: Insert draw results
```sql
INSERT INTO draw_results_by_pool 
  (hunt_id, draw_year, pool_id, applications, tags_available, tags_drawn, draw_odds)
VALUES (%s, %s, %s, %s, %s, %s, %s)
ON CONFLICT DO NOTHING
```
draw_year = 2024 or 2025 depending on source file

### Step 7: Load WY harvest data from PDFs
Typical WY harvest report columns: Hunt Area | Type | Hunters | Harvest | Success%
Extract and load into harvest_stats.

### Step 8: Load WY hunt dates from proclamation CSV
WY/proclamations/2026/WY_hunt_dates_2026.csv — match hunt_code to hunts table

### WY Script: scripts/load_wy.py

---

## STATE 2: ARIZONA

### Source PDFs:
AZ/raw_data/2024-Elk-Pronghorn-Draw-Report-Bonus-Pass.pdf  ← bonus point pass
AZ/raw_data/2024-Elk-Pronghorn-Draw-Report-1-2-Pass.pdf   ← first+second pass
AZ/raw_data/2024-Elk-Pronghorn-Draw-Report-3-4-5-Pass.pdf ← third+ pass
AZ/raw_data/2024-Elk-Pronghorn-Bonus-Point-Report.pdf      ← bonus points by unit
AZ/raw_data/2024-Fall-Draw-Report-Bonus-Pass.pdf           ← deer/javelina bonus pass
AZ/raw_data/2024-Fall-Draw-Report-1-2-Pass.pdf
AZ/raw_data/2024-Fall-Draw-Report-3-4-5-Pass.pdf
AZ/raw_data/2024-Fall-Bonus-Point-Report.pdf
AZ/raw_data/2024-AZ-Elk-Harvest-Summary.pdf
AZ/raw_data/2024-AZ-Deer-Harvest-Summary.pdf
AZ/proclamations/2026/AZ_hunt_dates_2026.csv   ← already parsed, verified HIGH confidence

### AZ Draw System:
3 passes: Bonus Pass (max point holders, ~20% tags) → Pass 1-2 → Pass 3-4-5
For our purposes, combine all passes into total applicants and total drawn.
The bonus point report shows min/avg/max bonus points required per hunt.

### Step 1: Inspect AZ draw report PDFs
```python
with pdfplumber.open('AZ/raw_data/2024-Elk-Pronghorn-Draw-Report-1-2-Pass.pdf') as pdf:
    for page in pdf.pages[:3]:
        tables = page.extract_tables()
        text = page.extract_text()
        print(text[:300] if text else "no text")
        for t in tables:
            print("table:", t[:2])
```

Typical AZ draw report columns:
  Hunt # | Quota | Applications | Successful Applicants | [by unit/weapon]
AZ hunt codes are 4-digit numbers (e.g., 3001, 3042, 3119)

### Step 2: Combine all passes
For each hunt code, sum across all 3 pass PDFs:
- total_applications = sum of applicants across all passes
- total_drawn = sum of successful across all passes  
- tags_available = Quota (should be consistent across passes)
- draw_odds = total_drawn / total_applications

Separate resident and nonresident if the PDF has that breakdown.
AZ NR allocation is 10% — if no R/NR split in PDF, estimate:
  NR pool: applications*0.10, tags*0.10 (rough)
  RES pool: applications*0.90, tags*0.90

### Step 3: Bonus points data
From the bonus point report, extract:
- Hunt # | Max Points | Average Points (for successful applicants)
Store in draw_results_by_pool as: pref_points_to_draw = min points for successful draw

### Step 4: AZ hunt codes and GMUs
AZ hunt codes: 4-digit numbers
  1xxx-2xxx = deer/javelina (Fall draw)
  3xxx = elk
  
GMU: AZ uses "Unit" system (Unit 1, Unit 10, Unit 36A, etc.)
The hunt code first 2 digits roughly map to Unit, but use the bonus point report
or draw report header to get actual unit names.
If unit not available, use hunt code prefix as gmu_code.

### Step 5: Elk hunt codes already in proclamation CSV
AZ/proclamations/2026/AZ_hunt_dates_2026.csv has 253 hunt codes with verified dates.
Use these hunt codes to seed the hunts table, then load draw data.

### Step 6: Load AZ harvest
From AZ/raw_data/2024-AZ-Elk-Harvest-Summary.pdf:
Typical columns: Hunt # | Hunters | Harvest | Success Rate | Antlered/Antlerless
Load into harvest_stats for harvest_year=2024.

### AZ Script: scripts/load_az.py

---

## STATE 3: COLORADO

### Source PDFs:
CO/raw_data/ — check what's there
CO/proclamations/2026/CO_big_game_brochure_2026.pdf (102MB)
CO/proclamations/2026/CO_hunt_dates_2026.csv (1,222 rows, mostly verified)

### Step 1: Check what CO raw data files exist
```python
import os
print(os.listdir('CO/raw_data/'))
```

### Step 2: Parse CO brochure for hunt codes
The CO brochure lists every hunt code in tables. CO hunt codes format:
D-E-003-O1-A (species-unit-weapon-method)
E-E-040-W1-R etc.

Use pdfplumber to extract tables from the brochure. Look for tables with
"Hunt Code" or similar column headers.

### Step 3: Load CO from proclamation CSV
The CO_hunt_dates_2026.csv has 1,222 hunt codes with dates (most verified).
Use this as the source of truth for CO hunt codes.
Load hunt codes from the CSV directly into the hunts table.

Parse the hunt code to extract:
- Species: first char D=deer, E=elk
- Sex: second char E=either/any, M=male (buck/bull), F=female (doe/cow)
- Unit: 3-digit number (e.g., 003, 040, 201)
- Season suffix: O1=archery, E1=muzzleloader, W1-W4=1st-4th rifle, P2=2nd pref, etc.
- Method: last char A=archery, M=muzzleloader, R=rifle

Derive:
- weapon_type: from method char (A→ARCH, M→MUZZ, R→RIFLE)
- sex_restriction: from sex char (E→ANY, M→BULL or BUCK, F→COW or DOE)
- season_label: derive from season suffix + ordinal

GMU for CO: 3-digit unit number (e.g., "003", "040", "201")

### Step 4: CO draw odds — check raw_data folder
If CO has draw odds PDFs in raw_data, parse them. If not, skip draw_results for CO.
CO's preference system means odds = (tags/applicants) in preference round, which
requires the annual draw stats PDF. If not available, leave draw_results empty for CO.

### Step 5: Load CO hunt dates from CSV
After inserting hunt codes, match to CO_hunt_dates_2026.csv and load into hunt_dates.
Skip the 122 O1-R codes flagged as DO_NOT_LOAD in the QA report.

### CO Script: scripts/load_co.py

---

## AFTER ALL THREE STATES

### Final verification:
```python
cur.execute("""
    SELECT s.state_code,
      COUNT(DISTINCT h.hunt_id) as hunts,
      COUNT(DISTINCT g.gmu_id) as gmus,
      COUNT(DISTINCT dr.result_id) as draw_results,
      COUNT(DISTINCT hs.harvest_id) as harvest_rows,
      COUNT(DISTINCT hd.hunt_date_id) as dates
    FROM states s
    LEFT JOIN hunts h ON h.state_id = s.state_id
    LEFT JOIN gmus g ON g.state_id = s.state_id
    LEFT JOIN draw_results_by_pool dr ON dr.hunt_id = h.hunt_id
    LEFT JOIN harvest_stats hs ON hs.hunt_id = h.hunt_id
    LEFT JOIN hunt_dates hd ON hd.hunt_id = h.hunt_id
    GROUP BY s.state_code ORDER BY s.state_code
""")
```

### Restart the web server:
The server.py is running in the background. After loading, run:
```bash
pkill -f "server.py"
sleep 2
cd /Users/openclaw/Documents/GraysonsDrawOdds/app
DRAWS_DB_HOST=localhost DRAWS_DB_PORT=5432 DRAWS_DB_NAME=draws \
  DRAWS_DB_USER=draws DRAWS_DB_PASS=drawspass \
  nohup python3 server.py > /tmp/server.log 2>&1 &
sleep 3 && curl -s -o /dev/null -w "Server status: %{http_code}\n" http://localhost:5001/
```

### Commit:
```bash
cd /Users/openclaw/Documents/GraysonsDrawOdds
git add -A
git commit -m "Overnight load: WY, AZ, CO hunt data, draw results, harvest stats"
```

### Write OVERNIGHT_RESULTS.md summarizing:
- Rows loaded per state per table
- Any parse failures or skipped hunts
- Hunt codes that couldn't be matched
- Confidence level for each state's data
- What still needs to be loaded (UT, MT, WA, CA)
