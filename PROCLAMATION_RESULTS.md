# Proclamation Research & Parse Results

**Date:** 2026-03-05
**Season Year:** 2026

## Phase 1: PDF Downloads

| State | PDF File(s) | Size | Pages | Status |
|-------|------------|------|-------|--------|
| NM | MANUAL_DOWNLOAD.txt | - | - | PDF behind JS download wall; 2026 dates already in DB (891 hunts) |
| AZ | AZ_pronghorn_elk_2026.pdf | 3.3 MB | 40 | Downloaded (elk + pronghorn only; deer in separate booklet published ~Jun) |
| CO | CO_big_game_brochure_2026.pdf | 102 MB | 84 | Downloaded (full brochure, deer + elk + pronghorn + moose + bear) |
| UT | UT_big_game_app_guidebook_2026.pdf | 3.2 MB | 82 | Downloaded (application guidebook with season dates) |
| NV | NV_big_game_seasons_2026.pdf | 2.2 MB | 33 | Downloaded (2025-2026 and 2026-2027 seasons regulation) |
| NV | NV_big_game_quotas_2025_2026.pdf | 1.1 MB | 42 | Downloaded (tag quotas per unit) |
| MT | MT_deer_elk_antelope_2026.pdf | 27 MB | 141 | Downloaded (full DEA regulations with maps) |
| ID | ID_big_game_seasons_rules_2025.pdf | 47 MB | 126 | Downloaded (2025-26 season, covers through spring 2026) |
| ID | ID_NR_supplemental_2026.pdf | 4.9 MB | 25 | Downloaded (nonresident supplemental proclamation) |
| WY | WY_elk_hunting_seasons.pdf | 445 KB | 46 | Downloaded (Chapter 7 elk regulations) |
| WY | WY_deer_hunting_seasons_ch6.pdf | 443 KB | 50 | Downloaded (Chapter 6 deer regulations) |
| WY | WY_hunting_license_guide_2026.pdf | 597 KB | 21 | Downloaded (license guide) |
| OR | OR_big_game_regulations_2026.pdf | 29 MB | 108 | Downloaded (full 2026 regulations from eRegulations) |
| WA | WA_big_game_hunting_2025.pdf | 16 MB | 124 | Downloaded (2025 pamphlet, effective Apr 2025 - Mar 2026) |
| CA | CA_mammal_hunting_regulations_2025_2026.pdf | 4.9 MB | 112 | Downloaded (2025-2026 mammal hunting regulations) |

**Total PDFs downloaded:** 14 files across 10 states (NM requires manual download)

### Notes on Downloads
- **NM:** PDF hosted at `wildlife.dgf.nm.gov/download/2025-2026-new-mexico-hunting-rules-and-info/` requires JavaScript execution. NM 2026 dates already fully loaded in DB from prior data collection.
- **AZ:** Only elk/pronghorn booklet available (published Dec 2025). The main deer regulations booklet publishes ~June 2026.
- **CO:** The 2026 brochure is 102 MB due to embedded high-resolution maps and graphics.
- **WY:** Deer chapter 6 is a draft regulation pending Commission approval at April 2026 meeting. Elk chapter 7 is the current approved regulation.
- **WA:** 2025 pamphlet covers through March 2026. The 2026 pamphlet (Apr 2026 - Mar 2027) publishes ~May 2026.
- **CA:** 2025-2026 mammal regulations cover deer/elk seasons active in fall 2025 through early 2026.

## Phase 2: Parse Results

| State | CSV Rows | Hunt Codes Extracted | Method | Quality |
|-------|----------|---------------------|--------|---------|
| NM | N/A (already in DB) | 891 | Prior load | High - complete |
| AZ | 253 | 253 | pdfplumber tables | Medium - elk only, no bag limits extracted |
| CO | 1,222 | 1,449 codes found | Hunt code regex + standard season dates | High - 1,222 mapped to season dates |
| UT | 257 | 257 | pdfplumber tables | Medium - mixed hunt types |
| NV | 1,757 | 1,757 | pdfplumber tables + text fallback | Medium - broad extraction |
| MT | 37 | 37 | Text regex (HD patterns) | Low - complex text layout, mostly maps |
| ID | 405 | 405 | pdfplumber tables | Medium - 4-digit controlled hunt numbers |
| WY | 1,193 | 1,193 | pdfplumber tables | High - clean tabular data, elk + deer |
| OR | 330 | 330 | pdfplumber tables | Medium - 3-digit hunt codes |
| WA | 355 | 355 | pdfplumber tables | Medium - mixed format |
| CA | 76 | 76 | pdfplumber tables | Medium - zone-based deer codes |

**Total hunt season rows extracted:** 5,885 (excluding NM)

### Parse Method Notes
- **WY:** Cleanest data. Tables extracted perfectly via pdfplumber. Hunt Area + Type columns map directly to season dates and quotas.
- **CO:** Hunt codes extracted via regex pattern `[DE]-[MFEB]-\d{3}-[A-Z]\d-[A-Z]` across all pages. Season dates mapped from hunt code suffix (O1=Archery, E1=Muzzleloader, W1=1st Rifle, P2/O2=2nd Rifle, etc.) using CO's standardized 2026 season structure. 227 codes had unmapped season suffixes.
- **NV:** Very broad extraction from the regulation PDF. Many rows may be non-deer/elk species.
- **MT:** The 141-page regulation PDF is mostly graphical maps and narrative text. Only 37 rows extracted where hunting district numbers appear near date patterns. MT general season deer/elk is OTC for residents with fixed statewide dates.
- **AZ:** Only the elk booklet was parsed (deer regulations publish later). Hunt numbers are 4-digit codes.
- **ID:** 2025-26 PDF used (2026 standalone not yet published as of March 2026). Controlled hunt numbers (4-digit) extracted from tables.

## Phase 3: Database Load Results

| State | CSV Rows | Hunts in DB | Matched | Inserted | Updated | Unmatched |
|-------|----------|-------------|---------|----------|---------|-----------|
| NM | N/A | 891 | N/A | N/A | N/A | N/A (already loaded) |
| AZ | 253 | 0 | 0 | 0 | 0 | 253 |
| CO | 1,222 | 0 | 0 | 0 | 0 | 1,222 |
| UT | 257 | 0 | 0 | 0 | 0 | 120 (deduplicated) |
| NV | 1,757 | 0 | 0 | 0 | 0 | 133 (deduplicated) |
| MT | 37 | 0 | 0 | 0 | 0 | 14 (deduplicated) |
| ID | 405 | 0 | 0 | 0 | 0 | 403 |
| WY | 1,193 | 0 | 0 | 0 | 0 | 950 (deduplicated) |
| OR | 330 | 0 | 0 | 0 | 0 | 327 |
| WA | 355 | 0 | 0 | 0 | 0 | 338 |
| CA | 76 | 0 | 0 | 0 | 0 | 61 (deduplicated) |

**Key finding:** Only NM currently has hunts populated in the database (891 hunts with 2026 dates already loaded). All other states have 0 hunts in the `hunts` table, so no CSV rows could be matched. The parsed CSVs are ready to load once hunt data is populated for each state.

## Data Quality Notes

### Per-State Assessment
- **NM:** Complete. 891 hunts with 2026 season dates already in database. No proclamation PDF needed.
- **WY:** Excellent parse quality. Clean tabular PDFs with Hunt Area, Type, Dates, Quota, and Limitations. Both elk (Ch. 7) and deer (Ch. 6) fully parsed. Note: deer regulations are draft pending April 2026 Commission approval.
- **CO:** Good. 1,449 unique hunt codes extracted. Season dates derived from CO's standardized season structure. 227 codes had non-standard season suffixes (late seasons, special hunts). The CO brochure format uses heavy graphics making direct table extraction impossible.
- **AZ:** Partial. Only elk hunts available (253 hunt numbers). Deer regulations publish later (~June 2026). Bag limit descriptions not well extracted from AZ table format.
- **NV:** Large dataset but includes non-deer/elk species. Needs filtering by species when loading.
- **UT:** Good extraction from application guidebook tables.
- **ID:** Reasonable. 405 controlled hunt rows from the 2025-26 season rules.
- **OR:** Good. 330 hunt codes extracted. Note: 2026 introduces new Eastern Oregon deer hunt area structure.
- **WA:** Reasonable. 355 rows from 2025 pamphlet (covers through March 2026).
- **CA:** Smaller dataset (76 rows). Zone-based deer system with fewer distinct hunt codes.
- **MT:** Low extraction. MT regulations are text-heavy with embedded maps. General season has statewide fixed dates. Limited-entry permits are the draw-relevant data and require more targeted parsing.

### Recommendations
1. **Populate hunts table** for non-NM states before re-running the loader
2. **MT** needs manual review or a more sophisticated text parser focused on LE permit tables
3. **AZ deer** regulations should be downloaded when published (~June 2026)
4. **WA 2026** pamphlet should be downloaded when published (~May 2026)
5. **CO** hunt code-to-date mapping covers standard seasons; special/late season hunts (227 codes) need the specific dates from the brochure's hunt code tables

## Files Created

### PDFs (per state)
```
{STATE}/proclamations/2026/*.pdf
```

### Parsed CSVs
```
AZ/proclamations/2026/AZ_hunt_dates_2026.csv (253 rows)
CA/proclamations/2026/CA_hunt_dates_2026.csv (76 rows)
CO/proclamations/2026/CO_hunt_dates_2026.csv (1,222 rows)
ID/proclamations/2026/ID_hunt_dates_2026.csv (405 rows)
MT/proclamations/2026/MT_hunt_dates_2026.csv (37 rows)
NV/proclamations/2026/NV_hunt_dates_2026.csv (1,757 rows)
OR/proclamations/2026/OR_hunt_dates_2026.csv (330 rows)
UT/proclamations/2026/UT_hunt_dates_2026.csv (257 rows)
WA/proclamations/2026/WA_hunt_dates_2026.csv (355 rows)
WY/proclamations/2026/WY_hunt_dates_2026.csv (1,193 rows)
```

### Scripts
```
scripts/parse_all_proclamations.py  - Main parser for all states
scripts/load_proclamation_dates.py  - DB loader (--all or --state XX --csv path)
```
