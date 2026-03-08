# Data Load Task: Montana, Wyoming, Idaho
# Agent: build and run loaders for all three states

## ENVIRONMENT
- PostgreSQL: localhost:5432, db=draws, user=draws, pass=drawspass (Docker container grayson-draws)
- Project root: /Users/openclaw/Documents/GraysonsDrawOdds/
- Python 3.14, fitz (PyMuPDF), psycopg2 available
- Scripts dir: /Users/openclaw/Documents/GraysonsDrawOdds/scripts/

## SCHEMA REMINDER
Always run `SELECT column_name FROM information_schema.columns WHERE table_name='X'` before INSERTs.

Key tables:
- hunts: hunt_id, state_id, hunt_code, hunt_code_display, species_id, season_type, tag_type, is_active, unit_description, season_label, weapon_type_id, bag_limit_id
- draw_results_by_pool: result_id, hunt_id, draw_year, pool_id, applications, tags_available, tags_awarded, avg_pts_drawn, min_pts_drawn, max_pts_held
  UNIQUE ON (hunt_id, draw_year, pool_id)
- pools: pool_id, pool_code, pool_name
- states: state_id, state_code

IMPORTANT: ON CONFLICT (hunt_id, draw_year, pool_id) DO UPDATE to handle re-runs.

## TASK 1: MONTANA BY-POINTS LOADER

### Source files (all in /Users/openclaw/Documents/GraysonsDrawOdds/MT/raw_data/):
By-points PDFs (most important — provides min points to draw):
- MT_elk_permit_by_points_2024.pdf
- MT_elk_permit_by_points_2025.pdf
- MT_elk_b_license_by_points_2024.pdf
- MT_elk_b_license_by_points_2025.pdf
- MT_deer_permit_by_points_2024.pdf
- MT_deer_permit_by_points_2025.pdf
- MT_deer_b_license_by_points_2024.pdf  (if exists)
- MT_deer_b_license_by_points_2025.pdf

Summary PDFs (aggregate totals, load after by-points):
- MT_elk_permit_summary_2024.pdf
- MT_elk_permit_summary_2025.pdf
- MT_elk_b_license_summary_2024.pdf
- MT_elk_b_license_summary_2025.pdf
- MT_deer_permit_summary_2024.pdf
- MT_deer_permit_summary_2025.pdf
- MT_deer_b_license_summary_2024.pdf
- MT_deer_b_license_summary_2025.pdf

### By-points PDF format (all PDFs use this structure):
```
Item Description  District   Residency         Number of Points  Num Apps  Num Successes  %
ELK B LICENSE     007-00     RESIDENT           1                 499       398            79.76
ELK B LICENSE     007-00     RESIDENT           2                 89        85             95.51
ELK B LICENSE     007-00     RESIDENT           0                 340       187            55
ELK B LICENSE TOTAL 007-00                                        1278      800            62.6
ELK B LICENSE     007-00     NONRESIDENT        1                 133       19             14.29
...
ELK PERMIT TOTAL  007-00                                          ...       ...
```
Residency types: RESIDENT LANDOWNER, RESIDENT, NONRESIDENT LANDOWNER, NONRESIDENT

Points: integer 0-20+. Point 0 = "random/no points" (zero-point applicants)

### Summary PDF format:
```
District  Quota  QTA  1st  1st  QTA  1st  1st  QTA  1st  2nd  3rd  1st  2nd 3rd  QTA  1st  2nd  3rd  1st  2nd 3rd  Succ  plus
007-00    800    120  15   15   80   2    2    800  964  326  82   706  0   0    80   297  83   9    77   0   0    800   0
```
Columns: District, Quota, then data grouped by: Resident LO, Resident, NonResident LO, NonResident
Each group: QTA (quota for pool), 1st choice apps, 1st drew, ...

### Hunt code mapping:
Montana proclamation hunt codes in DB have species prefix:
- ELK PERMIT / ELK B LICENSE → hunt_code = 'E-{district}' e.g. 'E-007-00', 'E-217-10'
- DEER PERMIT / DEER B LICENSE → hunt_code = 'D-{district}' e.g. 'D-101-50', 'D-004-01'
- Antelope B LICENSE → hunt_code = 'A-{district}'

To find hunt_id: 
  SELECT hunt_id FROM hunts WHERE state_id=%s AND hunt_code = %s
  where hunt_code = 'E-' + district_code (for elk) or 'D-' + district_code (for deer)

### Pool mapping:
Use existing pools table. Check: SELECT pool_id, pool_code, pool_name FROM pools;
Create/upsert pools as needed:
- pool_code='RES_LO' → pool_name='Resident Landowner'
- pool_code='RES' → pool_name='Resident'
- pool_code='NR_LO' → pool_name='Nonresident Landowner'  
- pool_code='NR' → pool_name='Nonresident'
- pool_code='TOTAL' → pool_name='Total'

### Algorithm for by-points → draw_results_by_pool:
For each (district, license_type, year):
  For each residency pool (RESIDENT LANDOWNER, RESIDENT, NONRESIDENT LANDOWNER, NONRESIDENT):
    - applications = sum of all applications across all point levels
    - tags_awarded = sum of successes across all point levels  
    - tags_available = applications for TOTAL row if available, else NULL
    - min_pts_drawn = lowest point level where successes > 0 (excluding point=0 random)
      NOTE: point=0 is random draw, not "0 preference points held"
      If only point=0 had successes, min_pts_drawn = 0
    - avg_pts_drawn = weighted avg of point levels with successes (weight = successes count)
      = sum(point_level * successes) / sum(successes) for levels > 0
    - max_pts_held = highest point level with any applications > 0

    Then upsert into draw_results_by_pool (ON CONFLICT DO UPDATE).

### Year detection:
The PDFs don't have years in their text. Use filename: 
- *_2024.pdf → draw_year = 2024
- *_2025.pdf → draw_year = 2025

### Script to create:
/Users/openclaw/Documents/GraysonsDrawOdds/scripts/load_mt_by_points.py

---

## TASK 2: WYOMING DEMAND REPORT LOADER

### Source files (in /Users/openclaw/Documents/GraysonsDrawOdds/WY/raw_data/):
These are Wyoming Game & Fish "Demand Report" PDFs:
- 2025_elk_prefpoints_nonres.pdf      (NR preference point elk, 32 pages)
- 2025_elk_prefpoints_nonres_special.pdf (NR special preference point elk)
- 2025_elk_random_nonres.pdf          (NR random draw elk, 4 pages)
- 2025_elk_leftover_nonres.pdf        (NR leftover elk, 4 pages)
- 2025_elk_cowcalf_nonres.pdf         (NR cow/calf elk)
- 2025_deer_prefpoints_nonres.pdf     (NR pref point deer, 23 pages)
- 2025_deer_prefpoints_nonres_special.pdf
- 2025_deer_random_nonres.pdf
- 2025_deer_leftover_nonres.pdf
- 2025_deer_doefawn_nonres.pdf        (NR doe/fawn deer)
Also resident versions:
- 2025_elk_cowcalf_res.pdf
- 2025_elk_leftover_res.pdf
- 2025_elk_random_res.pdf
- 2025_deer_doefawn_res.pdf
- 2025_deer_leftover_res.pdf
- 2025_deer_random_res.pdf
(Note: no resident prefpoints file — residents are OTC or random for most WY hunts)

### WY demand report format (NR preference point):
```
Hunt   Hunt                                              Pref     First Choice   First Choice 
Area   Type   Description               Quota   Issued   Points   Applicants     Success Odds 
----   ----   -----------------------   -----   ------   ------   ------------   ------------ 
001    1      ANY ELK                       6        1       18              1        100.00%                                     
                                            5        0     < 18              0        100.00%                                     
                                            5        4       17              4        100.00%                                     
                                            1        0     < 17              0        100.00%                                     
                                            1        1       16              2         50.00%                                     
                                            0              < 16            322          0.00%                                     
001    4      ANTLERLESS ELK                9        1       ...
```

### WY demand report format (random/leftover/cowcalf):
```
Hunt   Hunt                             Total            First Choice    Second Choice   Third Choice  
Area   Type   Description               Quota          Applicants Drew  Applicants Drew  Applicants Drew
----   ----   -----------------------   -----          ---------- ----  ---------- ----  ---------- ----
009    1      ANY ELK                      20              22       20       8        0      10        0
```

### Hunt code mapping (WY):
Demand report: Hunt Area "001" + Hunt Type "1" → DB hunt_code "1-1"
Demand report: Hunt Area "001" + Hunt Type "4" → DB hunt_code "1-4"  
Demand report: Hunt Area "010" + Hunt Type "1" → DB hunt_code "10-1"
Demand report: Hunt Area "100" + Hunt Type "1" → DB hunt_code "100-1"

Algorithm: hunt_code = str(int(area)) + '-' + str(int(hunt_type))
(strip leading zeros from area, then hyphen-join with type)

Also handle "Gen" type codes in DB: some hunts have "1-Gen" codes.
Description "GENERAL" or type "G" → use type 'Gen'.

### Pool mapping for WY:
- prefpoints_nonres → pool_code='NR_PREF'
- prefpoints_nonres_special → pool_code='NR_PREF_SPECIAL'  
- random_nonres → pool_code='NR_RANDOM'
- leftover_nonres → pool_code='NR_LEFTOVER'
- cowcalf_nonres / doefawn_nonres → pool_code='NR_ANTLERLESS'
- random_res → pool_code='RES_RANDOM'
- leftover_res → pool_code='RES_LEFTOVER'
- cowcalf_res / doefawn_res → pool_code='RES_ANTLERLESS'

### Algorithm for NR preference point format:
The cascading format shows remaining quota at each point tier.
For each hunt (area + type):
  - tags_available = quota (from header row — the first number before Issued column)
  - For each point tier row:
    - pref_pts = the "Pref Points" value (an integer or "< X" format)
    - applicants = First Choice Applicants column
    - issued = Issued column (running remaining quota)
  - tags_awarded = total issued (quota - final remaining, or sum of issues per tier)
  - min_pts_drawn = lowest explicit point level where any were issued (not "< X" rows)
    (The "< X" rows are applicants who fell below the cut — they didn't draw)
  - Actually: issued column shows REMAINING quota after that tier, not how many issued AT that tier
    So issued_at_tier = issued[prev_row] - issued[current_row] if current is "<X" row
    OR: issued_at_tier = issued column for the explicit point tier rows
  
  SIMPLER interpretation:
  - Rows with explicit point number show: at this point level, N applicants applied and M were issued
  - The "< X" rows show applicants below the cut with 0 issued (or remaining random)
  - min_pts_drawn = lowest row with explicit points AND issued > 0
  - max_pts_held = highest explicit point row with applicants > 0

### Script to create:
/Users/openclaw/Documents/GraysonsDrawOdds/scripts/load_wy_demand_reports.py
Year = 2025 (all files are 2025)

---

## TASK 3: IDAHO STATUS
No new Idaho draw odds data received. The 8 inbound CSVs are Montana data (already loaded).
Idaho has 429 hunts + 824 harvest rows + 329 dates in DB.
Idaho draw results = 0. Skip Idaho loader for now.
BUT: write a note file: /Users/openclaw/Documents/GraysonsDrawOdds/ID/DRAW_DATA_NEEDED.md
  explaining: IDFG draw odds CSVs needed from idfg.idaho.gov/ifwis/huntplanner/odds/
  (deer 2024/2025 + elk 2024/2025, 4 CSV files)

---

## EXECUTION ORDER
1. Check existing pools in DB and create missing ones
2. Run MT by-points loader (most valuable data)
3. Run WY demand report loader
4. Commit all scripts to git
5. Print summary stats: how many draw_results_by_pool rows added per state

## QA CHECKS
After loading:
- Verify a known hunt: MT Elk B License 100-00 should have 4 pool rows (RES_LO, RES, NR_LO, NR) for each year
- Verify min_pts_drawn makes sense: E-217-10 (famous MT elk permit) should need many points
- Verify WY hunt 1-1 (ANY ELK, Area 001) has NR pref point data with reasonable min_pts
- Check for any NULL hunt_id lookups (print warnings for districts not found in DB)

## IMPORTANT NOTES
- Always ON CONFLICT DO UPDATE for draw_results_by_pool
- Print warnings (don't crash) for districts not found in DB
- The PDFs may have OCR/formatting issues — use regex to be robust to whitespace
- For MT: hunt_code lookup: 'E-{district}' for elk, 'D-{district}' for deer, 'A-{district}' for antelope
- Year is from filename not PDF content
