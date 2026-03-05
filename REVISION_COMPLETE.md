# UI Revision Complete

## Changes Made

### 1. Header / Masthead
- Replaced with minimal masthead: "GRAYSON'S DRAW ODDS" (bold 13px uppercase), attribution line with link to graysonchaffer.com, thin 1px rule below.

### 2. State Selector — Alphabetical
- Reordered pills: AZ | CA | CO | ID | MT | NM | NV | OR | UT | WA | WY
- Updated `STATE_ORDER` JS array. Default state still NM (or URL hash).

### 3. Page Layout — Data First
- Odds Explorer is now the first (active) tab, immediately visible after state selection.
- Tab order: Odds Explorer → Build Your Application → Top Hunts → Draw System → Strategy Guide

### 4. Draw System Text — Lean
- All 11 state draw explanations rewritten to ~50% of original word count.
- Strategy sections compressed to 2-3 tight sentences per point.

### 5. Duplicate Hunt Codes Fixed
- Server: `DISTINCT` keyword added to hunts query SELECT.
- Client: JS deduplicates by `hunt_code|draw_year` before rendering.
- Client: App plan dropdown deduplicates by `hunt_code`.

### 6. Season Dates Column
- Added `latest_dates` LEFT JOIN LATERAL on `hunt_dates` in `/api/hunts`.
- `open_date`, `close_date`, `dates_season_year` returned in API response.
- New "Season" column in odds table with `fmtSeasonDate()` formatter (abbreviated month, en-dash).

### 7. Season Type Labels
- `season_label` column added to hunts table via migration (`ALTER TABLE hunts ADD COLUMN IF NOT EXISTS season_label TEXT`).
- `season_label` included in `/api/hunts` and `/api/hunt_detail` responses.
- New "Season Type" column in odds table. Shows em-dash when null.

### 8. Bag Limits + Proclamation Links
- Expanded row detail now shows bag limit disclaimer with link to official state proclamation.
- All 11 state proclamation URLs stored in `PROCLAMATION_URLS` JS object.

### 9. Proclamation Data Comment
- HTML comment block added noting the proclamation PDF pipeline plan.

## Testing
- `curl http://localhost:5001/` → 200
- `curl /api/hunts?state_code=NM&species_code=ELK&pool_code=RES` → 322 rows, 322 unique hunt codes, `open_date`/`close_date`/`season_label` fields present.
