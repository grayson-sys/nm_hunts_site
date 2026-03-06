# Data Loading Pipeline — OR, NV, ID

Load draw odds, harvest data, and season dates for Oregon, Nevada, and Idaho into
the PostgreSQL database. Do NOT stop to ask questions. Make best judgment and keep going.

DB: host=localhost port=5432 dbname=draws user=draws password=drawspass
Project root: /Users/openclaw/Documents/GraysonsDrawOdds/

Write all loader scripts to: /Users/openclaw/Documents/GraysonsDrawOdds/scripts/

---

## CRITICAL RULES

1. Hunt codes display EXACTLY as the agency publishes them. No state prefixes.
   OR: "200M", "200R", "201A"  NV: "051", "101"  ID: "2001", "1001"
2. gmu_code is always TEXT. Never cast to integer.
3. UNIQUE(state_id, hunt_code) — check for conflicts before inserting.
4. Use ON CONFLICT DO UPDATE to safely re-run loaders.
5. Write each loader as a standalone Python script with clear print output.
6. After loading each state, print row counts for every affected table.

---

## PART 1: OREGON

### Source files:
- OR/raw_data/2024_elk_preference_point_draw_report.xlsx  (row 5 = headers, data from row 6)
- OR/raw_data/2024_elk_applicants_by_hunt_choice.xlsx     (row 2 = headers, data from row 3)
- OR/raw_data/2024_buck_deer_preference_point_draw_report.xlsx
- OR/raw_data/2024_buck_deer_applicants_by_hunt_choice.xlsx
- OR/raw_data/2025_elk_preference_point_draw_report.xlsx
- OR/raw_data/2025_elk_applicants_by_hunt_choice.xlsx
- OR/raw_data/2025_buck_deer_preference_point_draw_report.xlsx
- OR/raw_data/2025_buck_deer_applicants_by_hunt_choice.xlsx
- OR/proclamations/2026/OR_hunt_dates_2026.csv

### Preference Point Draw Report column structure (verified):
Row 5 headers: Hunt Number | Hunt Name | Tags Authorized | Resident Apps |
  Resident Drawn | Non-Resident Apps | Non-Resident Drawn | Total Apps |
  Total Drawn | Total Points-Apps | Total Points Drawn Pref | Total Points Drawn Random
Data starts row 6. Skip blank rows (hunt number is None/empty).

### Step 1 — Get OR state_id and species IDs
```python
cur.execute("SELECT id FROM states WHERE state_code='OR'")
or_state_id = cur.fetchone()[0]
cur.execute("SELECT id, species_code FROM species")
species_map = {r[1]: r[0] for r in cur.fetchall()}
# ELK and MDR (mule deer) should exist
```

### Step 2 — Parse weapon type from Hunt Name and Hunt Number
OR hunt codes use letter suffixes:
- Ends in M or name contains "Muzzleloader" → weapon_type = 'MUZZ'
- Ends in A or name contains "Archery" → weapon_type = 'ARCH'
- Ends in R or general → weapon_type = 'RIFLE'
- "Premium" or "L"/"M"/"N" prefix → weapon_type = 'RIFLE' (premium draws)
- "Youth" → weapon_type = 'RIFLE', add note

### Step 3 — Infer sex from Hunt Name
- "Bull", "Antlered" → sex = 'BULL' (elk) / 'BUCK' (deer)
- "Cow", "Antlerless", "Either Sex" → sex = 'COW' (elk) / 'DOE' (deer)
- "Any" → sex = 'ANY'
- Default: 'ANY'

### Step 4 — Insert GMUs for OR
OR uses 3-digit numeric hunt codes, but the "unit" is encoded in the first 1-3
digits and the letter suffix. The "Hunt Name" field contains the readable unit name
(e.g., "Cascade Muzzleloader" → unit is "Cascade").

Extract unit name: strip weapon-type words from Hunt Name:
  Remove: Muzzleloader, Archery, Rifle, Bull, Cow, Buck, Doe, Youth, Premium,
  Either Sex, Antlered, Antlerless, Any, Legal Weapon, Special, General
  Strip leading/trailing whitespace
  Result is the GMU name (e.g., "Cascade", "Walla Walla", "Desolation")

For gmu_code, use the numeric portion of the hunt code (first 3 digits).
gmu_sort_key = zero-pad to 5 chars.

```sql
INSERT INTO gmus (state_id, species_id, gmu_code, gmu_name, gmu_sort_key)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (state_id, species_id, gmu_code) DO UPDATE SET gmu_name = EXCLUDED.gmu_name
```

### Step 5 — Insert hunts for OR
```sql
INSERT INTO hunts (state_id, species_id, hunt_code, weapon_type, sex_restriction,
  draw_type, notes)
VALUES (%s, %s, %s, %s, %s, 'PREF_RANDOM', %s)
ON CONFLICT (state_id, hunt_code) DO UPDATE SET weapon_type=EXCLUDED.weapon_type,
  sex_restriction=EXCLUDED.sex_restriction
```
OR draw_type = 'PREF_RANDOM' (75% preference, 25% random)

### Step 6 — Insert draw results for OR
Pool codes for OR: 'RES' (resident), 'NR' (nonresident)
Draw year = filename year (2024 or 2025)

For each hunt × year × pool:
```sql
INSERT INTO draw_results_by_pool
  (hunt_id, draw_year, pool_code, applicants, tags_drawn, tags_available,
   draw_odds, pref_points_to_draw)
VALUES (...)
ON CONFLICT (hunt_id, draw_year, pool_code) DO UPDATE
  SET applicants=EXCLUDED.applicants, tags_drawn=EXCLUDED.tags_drawn, ...
```

Derive from report columns:
- RES pool: applicants=Resident Apps, tags_drawn=Resident Drawn
- NR pool: applicants=Non-Resident Apps, tags_drawn=Non-Resident Drawn
- tags_available: Tags Authorized (split proportionally if needed, or use total for both)
- draw_odds: tags_drawn / applicants (if applicants > 0, else 0)
- pref_points_to_draw: Total Points Drawn Pref (last column with data)
  (this is the minimum points needed to draw in the preference round)

### Step 7 — Link hunts to GMUs (hunt_gmus)
```sql
INSERT INTO hunt_gmus (hunt_id, gmu_id)
SELECT h.id, g.id
FROM hunts h
JOIN gmus g ON g.state_id = h.state_id
  AND g.gmu_code = LEFT(h.hunt_code, 3)
WHERE h.state_id = (SELECT id FROM states WHERE state_code='OR')
ON CONFLICT DO NOTHING
```

### Step 8 — Load OR hunt dates from proclamation CSV
OR/proclamations/2026/OR_hunt_dates_2026.csv columns:
hunt_code, open_date, close_date, [other cols]

```sql
INSERT INTO hunt_dates (hunt_id, season_year, open_date, close_date)
SELECT h.id, 2026, %s, %s
FROM hunts h JOIN states s ON s.id = h.state_id
WHERE s.state_code='OR' AND h.hunt_code=%s
ON CONFLICT (hunt_id, season_year) DO UPDATE
  SET open_date=EXCLUDED.open_date, close_date=EXCLUDED.close_date
```

---

## PART 2: NEVADA

### Source file:
- NV/raw_data/2024-Nevada-Big-Game-Hunt-Data.xlsx  (Sheet: "2024 Hunt Summary")
- NV/proclamations/2026/NV_hunt_dates_2026.csv

### Column structure (verified):
year | Hunt | Residency | Species | Weapon | Unit Group | Season |
Demand | Unique Apps | 2024 Quota | Tags Issued | Hunters Afield |
Successful Hunters | Draw Rate | Survey Rate | Hunter Success |
Points or Greater | Length or Greater | Hunt Days | Effort Days | Hunter Satisfaction

- Demand = applicants who were awarded tags (not total applicants — NOTE this carefully)
- Unique Apps = unique applicants in the draw
- Tags Issued = tags actually taken/purchased after draw
- Draw Rate = tags issued / unique apps (odds)
- Hunter Success = harvest success rate among those who hunted

### Step 1 — Filter for deer and elk only
```python
df = df[df['Species'].isin(['Deer', 'Elk'])]
```

### Step 2 — Map species to species_code
'Deer' → 'MDR'   'Elk' → 'ELK'

### Step 3 — Map Weapon to weapon_type
'ALW' → 'RIFLE'   'Archery' → 'ARCH'   'Muzzleloader' → 'MUZZ'

### Step 4 — NV hunt code
NV doesn't have traditional hunt codes. Build one from: Unit Group + Weapon + Residency
Example: "051-ELK-ALW-RES"  or just "051" with weapon and pool separate.
Actually: use Unit Group as the hunt_code base. Since NV has separate Res/NR draws,
create ONE hunt per unit+weapon combination (not per residency).
hunt_code = f"{unit_group.strip()}-{weapon_code}"  e.g., "051-ALW", "101-ARCH"
pool_code = Residency (Res→'RES', NR→'NR')

### Step 5 — Insert NV GMUs
gmu_code = Unit Group value (e.g., "051", "101", "012-014")
gmu_name = Unit Group value (NV doesn't have named units consistently)
gmu_sort_key = zero-pad first numeric segment to 5 chars

### Step 6 — Insert NV hunts
```sql
INSERT INTO hunts (state_id, species_id, hunt_code, weapon_type, sex_restriction,
  draw_type, notes)
VALUES (%s, %s, %s, %s, 'ANY', 'BONUS_SQUARED', NULL)
ON CONFLICT (state_id, hunt_code) DO UPDATE SET weapon_type=EXCLUDED.weapon_type
```
NV draw_type = 'BONUS_SQUARED' (pts²+1 entries, weighted random)

### Step 7 — Insert NV draw results
```sql
INSERT INTO draw_results_by_pool
  (hunt_id, draw_year, pool_code, applicants, tags_drawn, tags_available,
   draw_odds, harvest_success_rate)
VALUES (...)
ON CONFLICT (hunt_id, draw_year, pool_code) DO UPDATE SET ...
```
- applicants = 'Unique\nApps'
- tags_drawn = 'Demand' (awarded tags)
- tags_available = '2024\nQuota'
- draw_odds = 'Draw\nRate' (already computed, use directly)
- harvest_success_rate = 'Hunter\nSuccess' (already a rate, store as decimal)

### Step 8 — Insert NV harvest stats
```sql
INSERT INTO harvest_stats
  (hunt_id, season_year, total_hunters, total_harvest, harvest_success_rate)
VALUES (...)
ON CONFLICT (hunt_id, season_year) DO UPDATE SET ...
```
- total_hunters = 'Hunters\nAfield'
- total_harvest = 'Successful\nHunters'
- harvest_success_rate = 'Hunter\nSuccess'

### Step 9 — Load NV hunt dates from proclamation CSV

---

## PART 3: IDAHO

### Source files:
- ID/raw_data/elk_controlled_harvest_2023.csv
- ID/raw_data/elk_controlled_harvest_2024.csv
- ID/raw_data/deer_controlled_harvest_2023.csv
- ID/raw_data/deer_controlled_harvest_2024.csv
- ID/proclamations/2026/ID_hunt_dates_2026.csv

### Column structure (verified):
Hunt# | TakeMethod | Area | Hunters | Harvest | Success% | Days | Antlered

### Step 1 — Map TakeMethod to weapon_type
'Any Weapon' → 'RIFLE'
'Archery' → 'ARCH'
'Muzzleloader' → 'MUZZ'
'Controlled' → 'RIFLE' (default)

### Step 2 — ID hunt codes and GMUs
For controlled hunts, Hunt# is the hunt code (4-digit, e.g., "2001").
The Area column is the GMU/Zone code.

IMPORTANT: Idaho deer uses "Units" (MDR species_context),
elk uses "Zones" (ELK species_context). Same area number = different geography.
When inserting gmus, set species_context appropriately:
  deer hunts → gmu.species_context = 'MDR'
  elk hunts → gmu.species_context = 'ELK'

hunt_code = Hunt# value (4-digit string, no prefix)
gmu_code = Area value (may be alphanumeric like "11", "18", "19A")
gmu_sort_key = zero-pad numeric part to 5 chars + append letter if any

### Step 3 — Insert ID GMUs
```sql
INSERT INTO gmus (state_id, species_id, gmu_code, gmu_name, gmu_sort_key, species_context)
VALUES (%s, %s, %s, %s, %s, %s)
ON CONFLICT (state_id, species_id, gmu_code) DO NOTHING
```

### Step 4 — Insert ID hunts
ID has NO draw system (pure random lottery). But they're still "draw hunts"
(controlled hunts require a draw application).
draw_type = 'LOTTERY' (pure random, no points)

hunt_code = Hunt# string
weapon_type = from TakeMethod mapping
sex_restriction = infer from Antlered column:
  if Antlered column has values → 'BULL'/'BUCK' (antlered only)
  else → look at harvest count — if success rate seems to include antlerless, use 'ANY'
  default: 'ANY'

### Step 5 — Insert ID harvest stats
```sql
INSERT INTO harvest_stats
  (hunt_id, season_year, total_hunters, total_harvest, harvest_success_rate,
   antlered_harvest, total_days)
VALUES (...)
ON CONFLICT (hunt_id, season_year) DO UPDATE SET ...
```
- total_hunters = Hunters
- total_harvest = Harvest
- harvest_success_rate = Success% / 100 (convert to decimal)
- antlered_harvest = Antlered (may be blank — use None)
- total_days = Days

NOTE: ID has no draw_results_by_pool data yet (no odds CSV). Skip that table for now.
A note will be added when the Hunt Planner odds CSV is downloaded manually.

### Step 6 — Load ID hunt dates from proclamation CSV

---

## PART 4: LINK DATES

After loading all three states, run the date loader for each:

```python
# For each state, match proclamation CSV hunt codes to DB hunt codes
for state_code, csv_path in [
    ('OR', 'OR/proclamations/2026/OR_hunt_dates_2026.csv'),
    ('NV', 'NV/proclamations/2026/NV_hunt_dates_2026.csv'),
    ('ID', 'ID/proclamations/2026/ID_hunt_dates_2026.csv'),
]:
    # load CSV, match hunt_code to hunts table, insert into hunt_dates
    # Report: X matched, Y unmatched
```

---

## PART 5: VERIFY + REPORT

After all loads, run this verification query and print results:

```sql
SELECT s.state_code,
  COUNT(DISTINCT h.id) as hunts,
  COUNT(DISTINCT g.id) as gmus,
  COUNT(DISTINCT dr.id) as draw_results,
  COUNT(DISTINCT hs.id) as harvest_stats,
  COUNT(DISTINCT hd.id) as hunt_dates
FROM states s
LEFT JOIN hunts h ON h.state_id = s.id
LEFT JOIN gmus g ON g.state_id = s.id
LEFT JOIN draw_results_by_pool dr ON dr.hunt_id = h.id
LEFT JOIN harvest_stats hs ON hs.hunt_id = h.id
LEFT JOIN hunt_dates hd ON hd.hunt_id = h.id
GROUP BY s.state_code ORDER BY s.state_code;
```

Also verify no duplicate hunt_codes within a state:
```sql
SELECT s.state_code, h.hunt_code, COUNT(*)
FROM hunts h JOIN states s ON s.id = h.state_id
GROUP BY s.state_code, h.hunt_code HAVING COUNT(*) > 1;
```
Should return 0 rows. If any, fix them.

---

## PART 6: COMMIT

```bash
cd /Users/openclaw/Documents/GraysonsDrawOdds
git add -A
git commit -m "Data load: OR, NV, ID hunts + draw results + harvest stats"
```

Write scripts/load_or.py, scripts/load_nv.py, scripts/load_id.py as the
standalone scripts. Also write scripts/load_all.py that runs all three in sequence.
