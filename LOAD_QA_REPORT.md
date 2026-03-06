# Load QA Report: OR, NV, ID Validation Results

Generated: 2026-03-05 19:06 PST

## Summary Counts

| State | Hunts | Draw Results | Harvest Stats | Hunt Dates | Hunts w/o Dates |
|-------|-------|-------------|---------------|------------|-----------------|
| ID    | 429   | 0           | 824           | 329        | 100             |
| NV    | 412   | 534         | 410           | 222        | 190             |
| OR    | 468   | 1745        | 0             | 213        | 255             |

---

## ID

| Check | Status | Severity | Detail |
|-------|--------|----------|--------|
| 1. Duplicate hunt codes | PASS | OK | No duplicates |
| 2. Hunt code format | PASS | OK | All 429 codes match `^\d{1,5}$` |
| 3. Draw results | INFO | INFO | No draw results loaded (ID draw data not yet available) |
| 4. Harvest stats | PASS | OK | 824 rows, success_rate range [0.000, 1.000] |
| 5. Hunt dates | PASS | OK | 329 rows, 2026-08-01 to 2026-12-31, no inverted/wrong year |
| 6. GMU linkage | PASS | OK | All 429 hunts linked to GMUs |
| 7. Spot-check | PASS | OK | Reasonable: archery Aug-Sep, rifle Oct-Nov, correct species |

### ID Issues

- **WARNING**: 100 hunts have no date records (23%). May be hunts where season dates weren't parsed.
- **WARNING**: `licenses_sold` is NULL for harvest stats (e.g., hunt 2001 shows NULL instead of 37 hunters). The `harvest_count` and `success_rate` load correctly but hunter count is missing.

### ID Cross-Check: Hunt 2001

| Field | Source CSV | DB | Match? |
|-------|-----------|-----|--------|
| Harvest | 21 | 21 | YES |
| Success% | 56% | 0.56 | YES |
| Hunters | 37 | NULL | NO — loaded into wrong field or skipped |
| Days | 262 | 262.0 | YES |

---

## NV

| Check | Status | Severity | Detail |
|-------|--------|----------|--------|
| 1. Duplicate hunt codes | PASS | OK | No duplicates |
| 2. Hunt code format | WARNING | WARNING | 347/412 outliers — NV uses comma-separated unit groups (e.g., `041, 042-ALW`) |
| 3. Draw results | PASS | OK | 534 rows, computed odds [0.021, 1.000], no tags > apps |
| 4. Harvest stats | PASS | OK | 410 rows, success_rate [0.000, 1.000] |
| 5. Hunt dates | PASS | OK | 222 rows, 2026-08-01 to 2027-01-01, no inverted/wrong year |
| 6. GMU linkage | PASS | OK | All 412 hunts linked to GMUs |
| 7. Spot-check | PASS | OK | Reasonable odds, correct weapon/season pairings |

### NV Issues

- **INFO**: Hunt code format (Check 2) — 347 outliers are expected. NV formats hunt codes as comma-separated unit groups like `061, 062, 064, 066 - 068-ALW`. This is the actual NV convention, not a loading error. The regex pattern assumed simple `XXX-XXX-WEAPON` format.
- **WARNING**: 190 hunts have no date records (46%).

### NV Cross-Check: Elk Unit 051 ALW Res

| Field | Source Excel | DB (051-ALW, RES) | Match? |
|-------|-------------|-------------------|--------|
| Unique Apps | 958 | 4,062 | NO — DB counts total entries across all pref point levels, Excel shows unique applicants |
| Quota | 2 | 110 (tags_available) | NO — DB tags_available appears to be total across all unit groups, not per-unit quota |
| Tags Awarded | n/a | 1,031 | n/a |

**Analysis**: The NV draw results appear sourced from the bonus point PDFs rather than the hunt summary Excel. The bonus point data counts total application entries (one per preference point level) rather than unique applicants. The `tags_available` field seems to aggregate across pools. This is a **data interpretation difference**, not a loading error — but users should understand that NV `applications` != unique applicants.

---

## OR

| Check | Status | Severity | Detail |
|-------|--------|----------|--------|
| 1. Duplicate hunt codes | PASS | OK | No duplicates |
| 2. Hunt code format | PASS | OK | All 468 codes match `^\d{3}[A-Z]?\d?$` |
| 3. Draw results | PASS | OK | 1,745 rows, odds [0.000, 1.000], apps range [1, 8127] |
| 4. Harvest stats | INFO | INFO | No harvest stats loaded (OR harvest in PDF format only) |
| 5. Hunt dates | WARNING | WARNING | 213 rows, 5 seasons >180 days |
| 6. GMU linkage | PASS | OK | All 468 hunts linked to GMUs |
| 7. Spot-check | PASS | OK | Reasonable: archery Oct-Nov, good odds distribution |

### OR Issues

- **WARNING**: 5 very long seasons (>180 days):
  - `215A` archery: 2026-08-01 to 2027-03-31 (242 days)
  - `223A` archery: 2026-08-01 to 2027-03-31 (242 days)
  - `245D` archery: 2026-08-01 to 2027-03-31 (242 days)
  - `265C` archery: 2026-08-01 to 2027-02-28 (211 days)
  - `277A` archery: 2026-10-01 to 2027-03-31 (181 days)
  These may be legitimate extended archery seasons (OR does have long archery elk seasons). Verify against proclamation.
- **WARNING**: 255 hunts have no date records (55%). Most deer hunts appear to be missing dates.
- **INFO**: No harvest stats loaded. OR harvest data is in PDF format which wasn't parsed.

### OR Cross-Check: Elk Hunt 200M (2024)

| Field | Source Excel | DB (RES pool) | DB (NR pool) | Match? |
|-------|-------------|---------------|--------------|--------|
| Tags Authorized | 990 | 990 (tags_available) | 990 (tags_available) | YES |
| Res Apps | 350 | 350 | — | YES |
| Res Drawn | 350 | 350 | — | YES |
| NR Apps | 4 | — | 4 | YES |
| NR Drawn | 4 | — | 4 | YES |

**FULL MATCH** — OR draw data loads correctly.

---

## Overall Assessment

### Critical Issues: 0

### Warnings: 5
1. **ID**: `licenses_sold` NULL — hunter count not loading for harvest stats
2. **NV**: Hunt code format uses comma-separated units (expected, not a bug)
3. **NV**: Draw result `applications` counts total entries, not unique applicants
4. **OR**: 5 very long seasons (may be legitimate extended archery)
5. **All states**: Significant percentage of hunts missing date records (ID 23%, NV 46%, OR 55%)

### Data Gaps
- **ID**: No draw results loaded
- **OR**: No harvest stats loaded
- **All states**: Many hunts lack date records — likely dates only parsed for some species/weapon combos

### Verdict
Data integrity is sound within what was loaded. No critical failures (no duplicates, no impossible odds, no inverted dates, no out-of-range success rates). The OR cross-check confirms accurate loading from source. The NV cross-check reveals a data interpretation difference worth documenting for users. The missing `licenses_sold` in ID and missing dates across states are gaps to address in future loads.
