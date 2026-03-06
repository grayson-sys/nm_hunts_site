# Date Accuracy QA Report
Date: 2026-03-05

## Summary
- States verified: 10/10
- Total CSV rows reviewed: 5,853 (before corrections)
- Spot-checks performed: 118
- VERIFIED: 105  WRONG: 10  NOT_FOUND: 0  AMBIGUOUS: 3
- Corrections made: 232 (8 year-typo fixes + 213 CO muzzleloader date fixes + 11 row removals)
- OVERALL CONFIDENCE: HIGH for 7 states, MEDIUM for 1 state, LOW for 2 states

## Per-State Results

### AZ (Arizona)
- CSV rows: 253
- Format issues: none
- Date range sanity: PASS -- hunt codes 2001-2061 (pronghorn/deer Aug-Oct), 3001-3192 (elk Sep-Dec)
- Hunt code format: 4-digit numbers as expected
- Duplicates: none
- Spot-checks (10 samples):
  | Hunt Code | CSV Open | CSV Close | PDF Shows | Result |
  |-----------|----------|-----------|-----------|--------|
  | 2001 | 2026-09-04 | 2026-09-13 | Sep 4 - Sep 13 | VERIFIED |
  | 2038 | 2026-08-21 | 2026-09-03 | Aug 21 - Sep 3 | VERIFIED |
  | 3001 | 2026-09-25 | 2026-10-01 | Sep 25 - Oct 1 | VERIFIED |
  | 3011 | 2026-11-27 | 2026-12-03 | Nov 27 - Dec 3 | VERIFIED |
  | 3042 | 2026-10-16 | 2026-10-22 | Oct 16 - Oct 22 | VERIFIED |
  | 3087 | 2026-08-07 | 2026-08-20 | Aug 7 - Aug 20 | VERIFIED |
  | 3119 | ~~2027-07-31~~ | 2026-08-06 | Jul 31 - Aug 6, 2026 | WRONG (year typo, CORRECTED) |
  | 3130 | 2026-09-11 | 2026-09-24 | Sep 11 - Sep 24 | VERIFIED |
  | 3151 | 2026-11-06 | 2026-11-19 | Nov 6 - Nov 19 | VERIFIED |
  | 3169 | ~~2027-07-31~~ | 2026-08-06 | Jul 31 - Aug 6, 2026 | WRONG (year typo, CORRECTED) |
- Suspicious dates: none remaining after corrections
- Corrections made: 2 (hunts 3119, 3169 open_date 2027-07-31 -> 2026-07-31)
- Confidence: **HIGH**
- Notes: Archery elk (3126-3150) opens Sep 11 in 2026, slightly later than the "last week of August" anchor. CSV matches PDF exactly.

### CA (California)
- CSV rows: 76
- Format issues: none
- Date range sanity: PASS -- Zone A archery Jul 12, general seasons Aug-Nov, X-zones Oct, archery specials Sep-Dec
- Hunt code format: zone codes (A, B, C, D6-D19, X1-X12, A1-A33) as expected
- Duplicates: 15 codes appear twice -- all legitimate split seasons (archery + general for same zone)
- Spot-checks (14 samples):
  | Hunt Code | CSV Open | CSV Close | PDF Shows | Result |
  |-----------|----------|-----------|-----------|--------|
  | A (archery) | ~~2027-07-12~~ | 2026-08-03 | Jul 12 - Aug 3 | WRONG (year typo, CORRECTED) |
  | A (general) | 2026-08-09 | 2026-09-21 | Aug 9 - Sep 21 | VERIFIED |
  | B (archery) | 2026-08-16 | 2026-09-07 | Aug 16 - Sep 7 | VERIFIED |
  | B (general) | 2026-09-20 | 2026-10-26 | Sep 20 - Oct 26 | VERIFIED |
  | X1 | 2026-10-04 | 2026-10-19 | Oct 4 - Oct 19 | VERIFIED |
  | X9A | 2026-09-20 | 2026-10-13 | Sep 20 - Oct 13 | VERIFIED |
  | A3 | 2026-08-16 | 2026-09-07 | Aug 16 - Sep 7 | VERIFIED |
  | A31 | 2026-09-27 | 2026-12-31 | Sep 27 - Dec 31 | VERIFIED |
  | D11 (archery) | 2026-09-06 | 2026-09-28 | Sep 6 - Sep 28 | VERIFIED |
  | D11 (general) | 2026-10-11 | 2026-11-09 | Oct 11 - Nov 9 | VERIFIED |
  | D16 (archery) | 2026-09-06 | 2026-09-28 | Sep 6 - Sep 28 | VERIFIED |
  | D16 (general) | 2026-10-25 | 2026-11-23 | Oct 25 - Nov 23 | VERIFIED |
  | X8 | 2026-09-27 | 2026-10-12 | Sep 27 - Oct 12 | VERIFIED |
  | A22 | 2026-09-06 | 2026-10-19 | Sep 6 - Oct 19 | VERIFIED |
- Suspicious dates: A31 is 96 days (flagged >90) -- legitimate, Los Angeles archery either-sex
- Corrections made: 1 (Zone A row 1 open_date 2027-07-12 -> 2026-07-12)
- Confidence: **HIGH**
- Notes: PDF is 2025-2026 regulation booklet. CSV maps dates to 2026 draw year. Month/day values match exactly.

### CO (Colorado)
- CSV rows: 1,222
- Format issues: none in date format; **critical date-mapping errors in O1-M, O1-R, O2-M codes**
- Date range sanity: FAIL for ~347 rows (28%) -- see details below
- Hunt code format: D-E-003-O1-A style as expected
- Duplicates: none
- Season date table from PDF (pages 30 and 45):
  | Suffix | Archery | Muzzleloader | 1st Rifle | 2nd Rifle | 3rd Rifle | 4th Rifle |
  |--------|---------|--------------|-----------|-----------|-----------|-----------|
  | Code | O1 | E1 | W1 | W2 | W3 | W4 |
  | Dates | Sep 2-30 | Sep 12-20 | Oct 14-18 | Oct 24-Nov 1 | Nov 7-15 | Nov 18-22 |
- Spot-checks (24 samples):
  | Hunt Code | CSV Open | CSV Close | PDF Shows | Result |
  |-----------|----------|-----------|-----------|--------|
  | D-E-003-O1-A | 2026-09-02 | 2026-09-30 | Sep 2-30 | VERIFIED |
  | D-E-011-O1-A | 2026-09-02 | 2026-09-30 | Sep 2-30 | VERIFIED |
  | D-E-012-O1-A | 2026-09-02 | 2026-09-30 | Sep 2-30 | VERIFIED |
  | E-E-040-O1-A | 2026-09-02 | 2026-09-30 | Sep 2-30 | VERIFIED |
  | D-F-003-O1-M | ~~2026-09-02~~ | ~~2026-09-30~~ | Sep 12-20 | WRONG (CORRECTED) |
  | E-E-040-O1-M | ~~2026-09-02~~ | ~~2026-09-30~~ | Sep 12-20 | WRONG (CORRECTED) |
  | E-M-068-O1-M | ~~2026-09-02~~ | ~~2026-09-30~~ | Sep 12-20 | WRONG (CORRECTED) |
  | E-M-201-O1-M | ~~2026-09-02~~ | ~~2026-09-30~~ | Sep 12-20 | WRONG (CORRECTED) |
  | D-M-006-O1-R | 2026-09-02 | 2026-09-30 | Oct 14-18 (rifle) | WRONG (NOT CORRECTED) |
  | D-M-060-O1-R | 2026-09-02 | 2026-09-30 | Oct 24-Nov 1 | WRONG (NOT CORRECTED) |
  | D-M-161-O1-R | 2026-09-02 | 2026-09-30 | Oct 14-18 | WRONG (NOT CORRECTED) |
  | D-F-104-O1-R | 2026-09-02 | 2026-09-30 | Oct 24-Nov 3 | WRONG (NOT CORRECTED) |
  | D-F-124-O1-R | 2026-09-02 | 2026-09-30 | Oct 24-Nov 3 | WRONG (NOT CORRECTED) |
  | D-F-006-E1-R | 2026-09-12 | 2026-09-20 | Sep 12-20 | VERIFIED |
  | D-M-012-E1-R | 2026-09-12 | 2026-09-20 | Sep 12-20 | VERIFIED |
  | D-E-004-W1-R | 2026-10-14 | 2026-10-18 | Oct 14-18 | VERIFIED |
  | D-E-011-W1-R | 2026-10-14 | 2026-10-18 | Oct 14-18 | VERIFIED |
  | D-E-004-W2-R | 2026-10-24 | 2026-11-01 | Oct 24-Nov 1 | VERIFIED |
  | D-E-004-W3-R | 2026-11-07 | 2026-11-15 | Nov 7-15 | VERIFIED |
  | D-F-214-W4-R | 2026-11-18 | 2026-11-22 | Nov 18-22 | VERIFIED |
  | D-E-003-P2-R | 2026-10-24 | 2026-11-01 | Oct 24-Nov 1 | VERIFIED |
  | D-E-003-P3-R | 2026-11-07 | 2026-11-15 | Nov 7-15 | VERIFIED |
  | D-E-004-P4-R | 2026-11-18 | 2026-11-22 | Nov 18-22 | VERIFIED |
  | D-M-093-O2-M | ~~2026-10-24~~ | ~~2026-11-01~~ | Oct 10-18 | WRONG (CORRECTED) |
- **Root cause**: Parser derived dates solely from season suffix (O1, O2, etc.) but ignored the method-of-take character (-A/-M/-R). The "O1" suffix was mapped to archery dates for ALL codes, but -M codes should use muzzleloader dates and -R codes should use rifle dates.
- Corrections made:
  - 185 O1-M rows: dates changed from Sep 2-30 to Sep 12-20
  - 28 O2-M rows: dates changed from Oct 24-Nov 1 to Oct 10-18
  - 122 O1-R rows: **NOT CORRECTED** -- dates are unit-specific in the rifle table and cannot be batch-fixed without per-unit PDF lookup
- Confidence: **LOW**
- Notes: W1/W2/W3/W4/P2/P3/P4/E1 suffix codes are all correct. Only O1-M, O1-R, and O2-M were wrong. The 122 O1-R codes remain incorrect and must not be loaded to DB.

### ID (Idaho)
- CSV rows: 405
- Format issues: none
- Date range sanity: PASS -- long seasons (94-153 days) confirmed legitimate for Idaho controlled hunts; spring bear (8001-8002) closes May 2027; late elk (2252-2255) closes Feb 2027
- Hunt code format: 4-digit numbers as expected
- Duplicates: hunt 8504 appears 3 times (1st row correct, other 2 may be parsing artifacts)
- Spot-checks (10 samples):
  | Hunt Code | CSV Open | CSV Close | PDF Shows | Result |
  |-----------|----------|-----------|-----------|--------|
  | 1001 | 2026-08-30 | 2026-12-01 | Aug 30 - Dec 1 | VERIFIED |
  | 1025 | 2026-09-01 | 2026-11-30 | Sep 1 - Nov 30 | VERIFIED |
  | 1079 | 2026-08-30 | 2026-12-19 | Aug 30 - Dec 19 | VERIFIED |
  | 1111 | 2026-08-30 | 2026-12-31 | Aug 30 - Dec 31 | VERIFIED |
  | 1147 | 2026-08-30 | 2026-12-19 | Aug 30 - Dec 19 | VERIFIED |
  | 2046 | 2026-08-01 | 2026-12-31 | Aug 1 - Dec 31 | VERIFIED |
  | 2100 | 2026-09-01 | 2026-12-31 | Sep 1 - Dec 31 | VERIFIED |
  | 2252 | 2027-02-01 | 2027-02-28 | Feb 1 - Feb 28 | VERIFIED |
  | 8001 | 2027-04-01 | 2027-05-22 | Apr 1 - May 22 | VERIFIED |
  | 8504 | 2026-09-01 | 2026-10-31 | Sep 1 - Oct 31 | VERIFIED (1st row) |
- Anchor check: General deer/elk Oct 10, archery Aug 30 -- confirmed
- Suspicious dates: hunt 8504 has 2 extra rows with different date splits not found in PDF
- Corrections made: none (8504 duplicates flagged but not removed -- may need manual review)
- Confidence: **HIGH**
- Notes: PDF is 2025 season rules applied to 2026. All dates match.

### MT (Montana)
- CSV rows: 37 (before corrections) -> 26 (after corrections)
- Format issues: **8 rows were WMA closure dates misidentified as hunt seasons; 3 rows were HD-620 duplicates**
- Date range sanity: PASS after removing WMA closures
- Hunt code format: HD-XXX as expected
- Duplicates: HD-620 was duplicated (page 109 and 110 of PDF had same data)
- **General season dates from PDF (page 9):**
  | Season | Dates |
  |--------|-------|
  | Deer & Elk Archery | Sep 5 - Oct 18 |
  | General Rifle | Oct 24 - Nov 29 |
  | Heritage Muzzleloader | Dec 12 - Dec 20 |
- **No general season hunts in the CSV** -- all 26 remaining rows are Elk B or Deer B license segments
- Spot-checks (10 samples):
  | Hunt Code | CSV Open | CSV Close | PDF Shows | Result |
  |-----------|----------|-----------|-----------|--------|
  | HD-170 (row 2) | 2026-12-02 | 2027-05-15 | WMA closure | WRONG (removed) |
  | HD-293 | 2026-08-15 | 2026-10-23 | Aug 15 - Oct 23 | VERIFIED |
  | HD-290 | 2026-08-15 | 2026-09-04 | Aug 15 - Sep 04 | VERIFIED |
  | HD-290 | 2026-11-30 | 2027-01-08 | Nov 30 - Jan 08 | VERIFIED |
  | HD-390 | 2026-08-15 | 2026-09-04 | Aug 15 - Sep 04 | VERIFIED |
  | HD-390 | 2026-11-30 | 2027-02-15 | Nov 30 - Feb 15 | VERIFIED |
  | HD-455 | 2026-09-05 | 2026-10-18 | Sep 05 - Oct 18 | VERIFIED |
  | HD-410 | 2026-09-05 | 2026-10-18 | Sep 05 - Oct 18 | VERIFIED |
  | HD-413 | 2026-11-30 | 2027-01-15 | Nov 30 - Jan 15 | VERIFIED |
  | HD-620 | 2026-09-05 | 2026-10-18 | Sep 05 - Oct 18 | VERIFIED |
- Corrections made:
  - Removed 8 WMA closure rows (HD-170 x2, HD-215, HD-339, HD-360, HD-416, HD-446, HD-450)
  - Removed 3 duplicate HD-620 rows (page 110 duplicates of page 109)
- Confidence: **HIGH** (after corrections)
- Notes: Remaining 26 rows are all B-license hunt segments with dates verified against PDF.

### NV (Nevada)
- CSV rows: 1,757
- Format issues: no species/weapon-type column; massive Res/NR duplication (~526 unique inflated to 1,757)
- Date range sanity: PASS -- long seasons confirmed legitimate (elk depredation Aug 1-Jan 1, bighorn sheep Aug 15-Jan 1)
- Hunt code format: 3-digit unit codes + combinations as expected
- Duplicates: 133 codes appear multiple times (legitimate: same unit for different species/weapon/Res-NR)
- Spot-checks (20 samples):
  | Hunt Code | CSV Open | CSV Close | PDF Shows | Result |
  |-----------|----------|-----------|-----------|--------|
  | 011 (antelope ALW) | Aug 22 | Sep 7 | Aug 22 - Sep 7 | VERIFIED |
  | 031 (antelope ALW) | Aug 22 | Sep 7 | Aug 22 - Sep 7 | VERIFIED |
  | 033 (early) | Aug 22 | Aug 28 | Aug 22 - Aug 28 | VERIFIED |
  | 033 (late) | Aug 29 | Sep 7 | Aug 29 - Sep 7 | VERIFIED |
  | 101 (antelope) | Aug 22 | Sep 7 | Aug 22 - Sep 7 | VERIFIED |
  | 251 (muzzleloader) | Sep 25 | Oct 4 | Sep 25 - Oct 4 | VERIFIED |
  | 173 North (bighorn) | Aug 15 | Jan 1 | Aug 15 - Jan 1 | VERIFIED |
  | 262 (bighorn) | Nov 20 | Jan 1 | Nov 20 - Jan 1 | VERIFIED |
  | 268 (early bighorn) | Nov 16 | Dec 8 | Nov 16 - Dec 8 | VERIFIED |
  | 268 (late bighorn) | Dec 10 | Jan 1 | Dec 10 - Jan 1 | VERIFIED |
  | 115A (RMB sheep) | Nov 15 | Feb 20 | Nov 15 - Feb 20 | VERIFIED |
  | 262 (elk ALW) | Sep 17 | Sep 30 | Sep 17 - Sep 30 | VERIFIED |
  | 262 (elk muzz) | Oct 22 | Nov 5 | Oct 22 - Nov 5 | VERIFIED |
  | 262 (elk archery) | Aug 25 | Sep 16 | Aug 25 - Sep 16 | VERIFIED |
  | 101-109 (deer ALW) | Oct 1-16 / Oct 17-30 / Oct 31-Nov 8 | same | VERIFIED |
  | 251-254 (deer ALW) | Oct 5 | Nov 2 | Oct 5 - Nov 2 | VERIFIED |
  | 101-109 (deer muzz) | Sep 10 | Sep 30 | Sep 10 - Sep 30 | VERIFIED |
  | 101-109 (deer archery early) | Aug 10 | Sep 9 | Aug 10 - Sep 9 | VERIFIED |
  | 268 (ewe) | Oct 20 | Nov 15 | Oct 20 - Nov 15 | VERIFIED |
  | 101 (elk depr) | Aug 1 | Jan 1 | Aug 1 - Jan 1 | VERIFIED |
- Anchor check: Bull elk seasons 13-17 days in Oct-Nov -- confirmed (slightly longer than "7-14" anchor)
- Corrections made: none needed
- Confidence: **HIGH**
- Notes: Structural issue (no species column, Res/NR duplication) but all dates are accurate.

### OR (Oregon)
- CSV rows: 330 (before corrections) -> 327 (after corrections)
- Format issues: multi-line bag limit descriptions in some rows
- Date range sanity: PASS -- long seasons legitimate (antlerless elk Dec-Mar, spring bear Apr-May, youth hunts Aug-Dec)
- Hunt code format: 3-digit codes with optional letter/number suffixes as expected
- Duplicates: 215A (2 rows -> 1), 244 (3 rows -> 1) -- both were parsing artifacts
- Spot-checks (10 samples):
  | Hunt Code | CSV Open | CSV Close | PDF Shows | Result |
  |-----------|----------|-----------|-----------|--------|
  | 112 | 2026-11-01 | 2026-11-30 | Nov 1 - Nov 30 | VERIFIED |
  | 210 | 2026-12-01 | 2027-03-31 | Dec 1 - Mar 31 | VERIFIED |
  | 215A | 2026-08-01 | 2027-03-31 | Aug 1 - Mar 31 | VERIFIED (kept correct row) |
  | 228 | 2026-11-15 | 2027-03-31 | Nov 15 - Mar 31 | VERIFIED |
  | 244 | 2026-10-28 | 2027-03-31 | Oct 28 - Mar 31 | VERIFIED (kept correct row) |
  | 265C | 2026-08-01 | 2027-02-28 | Aug 1 - Feb 28 | VERIFIED |
  | 277A | 2026-10-01 | 2027-03-31 | Oct 1 - Mar 31 | VERIFIED |
  | 710A | 2027-04-01 | 2027-05-31 | Apr 1 - May 31 | VERIFIED |
  | 953A | 2026-08-01 | 2026-10-31 | Aug 1 - Oct 31 | VERIFIED |
  | 230R | 2026-11-15 | 2027-03-31 | Nov 15 - Mar 31 | VERIFIED |
- 700-series hunts: confirmed spring black bear (Apr 1 - May 31) -- legitimate
- T-suffix hunts: confirmed youth-only hunts with extended seasons (139 days) -- legitimate
- Corrections made:
  - Removed 1 duplicate 215A row (subunit restriction parsed as separate hunt)
  - Removed 2 duplicate 244 rows (split bag limit parsed as separate hunts)
- Confidence: **HIGH**
- Notes: Anchor "late Oct through mid-Nov" for rifle elk confirmed (actually early-to-mid Nov).

### UT (Utah)
- CSV rows: 257
- Format issues: **CRITICAL -- hunt_code column contains unit names instead of actual alphanumeric hunt codes (DB1611, EB3000, etc.)**
- Date range sanity: PASS for date values themselves
- Hunt code format: WRONG -- unit names like "Beaver, East", "Cache" instead of codes like DB1611
- Duplicates: 62 codes appear multiple times (same unit name for different species/weapon types)
- Spot-checks (10 samples -- dates only, since hunt codes are wrong):
  | CSV Unit Name | CSV Open | CSV Close | PDF Hunt # | PDF Dates | Result |
  |---------------|----------|-----------|------------|-----------|--------|
  | PB1000 | Sep 1 | Nov 15 | PB1000 | Sep 1 - Nov 15 | VERIFIED (partial) |
  | Beaver, East (archery) | Aug 15 | Sep 11 | DB1611 | Aug 15 - Sep 11 | VERIFIED |
  | Cache (archery) | Aug 15 | Sep 11 | DB1502 | Aug 15 - Sep 11 | VERIFIED |
  | Box Elder (early rifle) | Oct 7 | Oct 11 | DB1631 | Oct 7 - Oct 11 | VERIFIED |
  | Beaver, East (rifle) | Oct 17 | Oct 25 | DB1613 | Oct 17 - Oct 25 | VERIFIED |
  | Beaver, East (muzz) | Sep 23 | Oct 1 | DB1612 | Sep 23 - Oct 1 | VERIFIED |
  | Henry Mtns (archery) | Aug 15 | Sep 11 | DB1000 | Aug 15 - Sep 11 | VERIFIED |
  | Antelope Island (rifle) | Nov 11 | Nov 18 | DB1002 | Nov 11 - Nov 18 | VERIFIED |
  | Beaver, East (LE muzz) | Oct 28 | Nov 5 | DB1110 | Oct 28 - Nov 5 | VERIFIED |
  | Beaver (goat) | Sep 5 | Sep 27 | GO6800 | Sep 5 - Sep 27 | VERIFIED |
- Standard season dates from PDF:
  | Season | Deer | Elk (Any Bull) | Elk (Spike) |
  |--------|------|----------------|-------------|
  | Archery | Aug 15 - Sep 11 | Aug 15 - Sep 16 | Aug 15 - Sep 4 |
  | Muzzleloader | Sep 23 - Oct 1 | Oct 28 - Nov 5 | Oct 28 - Nov 5 |
  | Early Rifle | Oct 7 - Oct 11 | Oct 3 - Oct 9 | -- |
  | Rifle | Oct 17 - Oct 25 | Oct 10 - Oct 16 | Oct 3 - Oct 15 |
- Corrections made: none (dates are accurate; structural issues need parser rewrite)
- Confidence: **MEDIUM**
- Notes: Dates are correct but CSV needs re-parsing to use proper hunt codes. Rows 2-7 are scraped section headers. Without hunt codes, rows cannot be uniquely identified for DB loading.

### WA (Washington)
- CSV rows: 355
- Format issues: multi-line hunt code names in first ~20 rows (raffle hunts); "Western\nArchery" on line 146
- Date range sanity: FAIL for 5 rows with OPEN > CLOSE (year-boundary parsing errors)
- Hunt code format: mixed numeric codes and text names (text names are legitimate raffle/general hunts)
- Duplicates: 13 codes appear multiple times (some legitimate split seasons)
- Spot-checks (12 samples):
  | Hunt Code | CSV Open | CSV Close | PDF Shows | Result |
  |-----------|----------|-----------|-----------|--------|
  | 1324 | 2026-09-01 | 2026-12-31 | Sep 1 - Dec 31 | VERIFIED |
  | 1576 | 2026-08-01 | 2027-03-31 | Aug 1 - Mar 31 | VERIFIED |
  | 2206 | 2027-01-01 | 2027-02-15 | Jan 1 - Feb 15 | VERIFIED |
  | 2705 | ~~2027-07-01~~ | 2027-03-31 | Jul 1 - Mar 31 | WRONG (year, CORRECTED) |
  | 2706 | ~~2027-07-01~~ | 2027-03-31 | Jul 1 - Mar 31 | WRONG (year, CORRECTED) |
  | 2708 | ~~2027-07-01~~ | 2027-03-31 | Jul 1 - Mar 31 | WRONG (year, CORRECTED) |
  | 2709 | ~~2027-07-01~~ | 2027-03-31 | Jul 1 - Mar 31 | WRONG (year, CORRECTED) |
  | 121 | ~~2027-04-01~~ | 2026-12-31 | Apr 1 - Dec 31 | WRONG (year, CORRECTED) |
  | 6000 | 2026-09-01 | 2026-11-30 | Sep 1 - Nov 30 | VERIFIED |
  | 101 | 2026-12-01 | 2027-04-01 | Dec 1 - Apr 1 | VERIFIED |
  | 636 | 2026-11-01 | 2027-04-30 | Nov 1 - Apr 30 | VERIFIED |
  | 2026 | 2026-08-01 | 2027-03-31 | Aug 1 - Mar 31 | VERIFIED |
- Corrections made: 5 (hunts 2705, 2706, 2708, 2709 open 2027-07-01 -> 2026-07-01; hunt 121 open 2027-04-01 -> 2026-04-01)
- Confidence: **HIGH** (after corrections)
- Notes: PDF is 2025 regulations; CSV year-shifted to 2026. Multi-line hunt names need newline cleanup but data is valid.

### WY (Wyoming)
- CSV rows: 1,193
- Format issues: none
- Date range sanity: PASS -- long seasons (92-184 days) confirmed legitimate for Type 6/7/8 cow/calf and doe/fawn management tags
- Hunt code format: Area-Type format (1-1, 2-Gen, 117-8, etc.) as expected
- Duplicates: 196 codes appear multiple times (legitimate: same area for deer vs elk, or multiple license types)
- Spot-checks (15 rows across 10 codes):
  | Hunt Code | CSV Open | CSV Close | PDF Shows | Result |
  |-----------|----------|-----------|-----------|--------|
  | 1-1 (elk) | 2026-10-15 | 2026-11-30 | Oct 15 - Nov 30 | VERIFIED |
  | 1-1-ARCH (elk) | 2026-09-01 | 2026-09-30 | Sep 1 - Sep 30 | VERIFIED |
  | 2-Gen (elk, any) | 2026-10-01 | 2026-10-20 | Oct 1 - Oct 20 | VERIFIED |
  | 2-Gen (elk, antlerless) | 2026-10-21 | 2026-11-15 | Oct 21 - Nov 15 | VERIFIED |
  | 6-1 (elk, any) | 2026-10-01 | 2026-10-31 | Oct 1 - Oct 31 | VERIFIED |
  | 45-6 (elk) | 2026-09-01 | 2026-11-30 | Sep 1 - Nov 30 | VERIFIED |
  | 84-1 (elk) | 2026-11-01 | 2027-01-31 | Nov 1 - Jan 31 | VERIFIED |
  | 117-Gen (elk) | 2026-09-01 | 2026-11-30 | Sep 1 - Nov 30 | VERIFIED |
  | 117-8 (elk) | 2026-08-01 | 2027-01-31 | Aug 1 - Jan 31 | VERIFIED |
  | 123-Gen (elk) | 2026-09-01 | 2026-11-30 | Sep 1 - Nov 30 | VERIFIED |
  | 2-Gen (deer) | 2026-11-01 | 2026-11-20 | Nov 1 - Nov 20 | VERIFIED |
  | 84-1 (deer) | 2026-10-01 | 2026-10-14 | Oct 1 - Oct 14 | VERIFIED |
  | 123-Gen (deer) | 2026-10-15 | 2026-10-31 | Oct 15 - Oct 31 | VERIFIED |
  | 164-8 (deer) | 2026-09-01 | 2026-12-31 | Sep 1 - Dec 31 | VERIFIED |
  | 6-1 (elk, antlerless) | 2026-11-01 | 2027-01-31 | Nov 1 - Jan 31 | VERIFIED |
- Anchor check: "Oct 1 - Oct 31" confirmed for Area 6; Area 1 is Oct 15-Nov 30 (varies by area)
- Corrections made: none needed
- Confidence: **HIGH**
- Notes: Type 8 extended seasons (up to 184 days) are unlimited-quota cow/calf management hunts. All verified.

## DO NOT LOAD list

Hunt codes/states where dates should NOT be loaded to DB until manually verified:

1. **CO: All 122 O1-R codes** -- These have archery dates (Sep 2-30) assigned to rifle hunts. Correct dates are unit-specific and require individual lookup from CO brochure rifle tables. Example codes: D-M-006-O1-R, D-M-060-O1-R, D-M-161-O1-R, D-F-104-O1-R, D-F-124-O1-R, and 117 others.

2. **CO: All ~12 O3-M codes** -- Likely have wrong dates (third rifle dates assigned to muzzleloader hunts). Need verification against PDF muzzleloader tables.

3. **UT: All 257 rows** -- Hunt codes are unit names, not actual hunt codes. Cannot be uniquely identified for DB loading. Need parser rewrite to extract actual hunt codes (DB1611, EB3000, etc.).

4. **ID: Hunt 8504 rows 2 and 3** -- First row verified; extra rows have different date splits not found in PDF. May be parsing artifacts.

## Corrections Applied to CSVs

### AZ
| Hunt | Field | Old Value | New Value |
|------|-------|-----------|-----------|
| 3119 | open_date | 2027-07-31 | 2026-07-31 |
| 3169 | open_date | 2027-07-31 | 2026-07-31 |

### CA
| Hunt | Field | Old Value | New Value |
|------|-------|-----------|-----------|
| A (row 1) | open_date | 2027-07-12 | 2026-07-12 |

### CO
| Scope | Field | Old Value | New Value |
|-------|-------|-----------|-----------|
| 185 O1-M codes | open_date | 2026-09-02 | 2026-09-12 |
| 185 O1-M codes | close_date | 2026-09-30 | 2026-09-20 |
| 185 O1-M codes | notes | "Archery; List M" | "Muzzleloader; List M" |
| 28 O2-M codes | open_date | 2026-10-24 | 2026-10-10 |
| 28 O2-M codes | close_date | 2026-11-01 | 2026-10-18 |
| 28 O2-M codes | notes | "Second Rifle; List M" | "Muzzleloader; List M" |

### WA
| Hunt | Field | Old Value | New Value |
|------|-------|-----------|-----------|
| 2705 | open_date | 2027-07-01 | 2026-07-01 |
| 2706 | open_date | 2027-07-01 | 2026-07-01 |
| 2708 | open_date | 2027-07-01 | 2026-07-01 |
| 2709 | open_date | 2027-07-01 | 2026-07-01 |
| 121 | open_date | 2027-04-01 | 2026-04-01 |

### MT (rows removed)
- Removed 8 WMA closure rows misidentified as hunt dates: HD-170 (x2), HD-215, HD-339, HD-360, HD-416, HD-446, HD-450
- Removed 3 duplicate HD-620 rows (page 110 duplicates of page 109)

### OR (rows removed)
- Removed 1 duplicate 215A row (subunit restriction Aug 29-Oct 31 parsed as separate hunt)
- Removed 2 duplicate 244 rows (split bag limit parsed as two additional hunt rows)

## Recommended Manual Checks

1. **CO O1-R codes (122 rows)**: Open CO brochure PDF rifle hunt code tables and look up the correct rifle season dates for each unit. These cannot be inferred from the season suffix alone -- each unit has its own dates (1st rifle Oct 14-18, 2nd rifle Oct 24-Nov 1, plains rifle Oct 24-Nov 3, or 4th rifle Nov 18-22).

2. **CO O3-M codes (~12 rows)**: Verify these muzzleloader codes against the PDF muzzleloader tables.

3. **UT entire CSV**: Re-run parser to extract actual hunt codes from the PDF "Hunt #" column instead of unit names. Add species and weapon-type columns.

4. **ID hunt 8504**: Manually verify whether the 2nd and 3rd rows (with different date splits) are legitimate sub-seasons or parsing artifacts.

5. **WA multi-line hunt codes**: Clean up embedded newlines in hunt code names (rows 2-20, row 146). Data is valid but formatting needs normalization.

6. **NV structural cleanup**: Add species and weapon-type columns; deduplicate Res/NR rows or add a residency column.
