# Overnight Load Results: WY, AZ, CO

## Summary Table

| State | Hunts | GMUs | Draw Results | Harvest Rows | Hunt Dates |
|-------|------:|-----:|-------------:|-------------:|-----------:|
| WY    | 1,008 |  186 |          982 |          767 |        961 |
| AZ    |   664 |  596 |        2,473 |          911 |        253 |
| CO    | 1,222 |  148 |        2,375 |          456 |      1,222 |

## Wyoming (WY)

**Confidence: HIGH for draw data, MEDIUM for harvest**

### Sources Loaded
- 14 demand report PDFs (2025 elk+deer: random, leftover, cowcalf, doefawn for res/NR/NR-special)
- 4 preference point reports (2025 NR + NR-special for elk and deer)
- 4 harvest reports (2024+2025 elk and deer)
- 1 proclamation CSV (WY_hunt_dates_2026.csv, 1,226 entries)

### Draw Results (982 rows)
- 386 unique hunt codes from draw data
- 3 pools: RES, NR, NR_SPEC (nonresident special license pool)
- Draw year: 2025 only (no 2024 individual draw PDFs available)
- Preference point data enriched for NR and NR_SPEC pools (min_pts_drawn, max_pts_held)

### Harvest (767 rows)
- 2024 elk: 217 rows parsed, 2025 elk: 662 rows parsed
- 2024 deer: 673 rows parsed, 2025 deer: 718 rows parsed
- Some harvest hunt codes (e.g., area-GEN) don't match to draw hunt codes exactly
- 2024 deer report uses different format (TABLE III-A, "General" type) vs 2025 (Table 7)

### Hunt Dates (961 rows)
- 1,193 date entries loaded from proclamation CSV
- 950 unique hunt codes matched; some CSV entries are archery/season variants of same hunt

### Notes
- WY hunt codes: "{area}-{type}" format (e.g., "1-1", "35-9", "100-6")
- Proclamation CSV includes -ARCH suffix and Gen type variants not in draw data
- Total 1,008 hunts = 386 from draw data + 622 from proclamation-only entries

---

## Arizona (AZ)

**Confidence: HIGH for draw data, HIGH for harvest**

### Sources Loaded
- 4 draw report PDFs (2024+2025 Elk/Pronghorn and Fall 1-2 Pass)
- 4 bonus point reports (2024+2025 Elk/Pronghorn and Fall)
- 4 harvest summary PDFs (2024+2025 elk and deer)
- 1 proclamation CSV (AZ_hunt_dates_2026.csv, 253 entries for elk hunts)

### Draw Results (2,473 rows)
- 664 unique hunt codes across 2 years
- 2 pools: RES, NR
- Draw years: 2024 and 2025
- Elk/Pronghorn hunts: 2xxx and 3xxx range
- Fall (deer) hunts: 1xxx range (411 hunts from draw data not in proclamation CSV)
- Bonus point data enriched (min_pts_drawn from bonus point reports)

### Harvest (911 rows)
- 2024 elk: 240 rows, 2025 elk: 313 rows
- 2024 deer: 212 rows, 2025 deer: 216 rows (2024 format lacked % symbol)

### Hunt Dates (253 rows)
- All 253 proclamation CSV entries matched to hunts
- Dates only for elk hunts (2xxx, 3xxx); no deer hunt dates in proclamation CSV

### Notes
- AZ hunt codes: 4-digit numbers (1001-3933)
- GMUs created per hunt code (596 GMUs) since AZ unit-to-hunt mapping is complex
- Pronghorn hunts in Elk/Pronghorn draw included but mapped as elk species

---

## Colorado (CO)

**Confidence: HIGH for hunts/dates, MEDIUM for draw data, LOW for harvest**

### Sources Loaded
- 4 draw recap PDFs (2024+2025 elk+deer, ~1000 pages each)
- 4 drawn-out-at PDFs (2024+2025 elk+deer, ~65 pages each)
- 4 harvest PDFs (2023+2024 elk+deer)
- 1 proclamation CSV (CO_hunt_dates_2026.csv, 1,222 entries)

### Draw Results (2,375 rows)
- Parsed from draw recap PDFs (4,319 pages total)
- Hunt code format: compact (EE001E1R) mapped to dashed (E-E-001-E1-R)
- 675 elk + 518 deer = ~1,193 hunts matched per year
- ~30% of draw recap hunt codes didn't match proclamation CSV (different year's hunt list)
- Preference point data from drawn-out-at reports (545 hunts enriched)

### Harvest (456 rows)
- CO harvest data is per-GMU unit, not per-hunt-code
- Mapped to first matching hunt per species+unit
- Heavy deduplication due to ON CONFLICT (one row per hunt_id + year + access_type)
- 2024 elk: 3,116 unit-level rows → ~130 unique unit-hunt matches
- 2024 deer: 2,084 unit-level rows → ~120 unique unit-hunt matches

### Hunt Dates (1,222 rows)
- All 1,222 proclamation entries loaded (1,100 VERIFIED + 122 APPROX)
- No DO_NOT_LOAD entries in this CSV version

### Notes
- CO hunt code format: {species}-{sex}-{unit}-{season}-{weapon}
- 148 unique GMUs (3-digit unit numbers)
- Season labels derived from season codes (O1=Archery, W1=First Rifle, etc.)
- Secondary draw PDFs available but not parsed (lower priority)

---

## What Still Needs Loading

| State | Status | Notes |
|-------|--------|-------|
| UT    | Partial | 768 hunts, 2,159 draw results loaded. Need harvest + dates |
| MT    | Partial | 240 hunts loaded. Need draw results, harvest, dates |
| WA    | Empty   | No data loaded yet |
| CA    | Empty   | No data loaded yet |

## Supervisor completed at 2026-03-05 23:44:40.327372
Total hunts across all states: 6337
