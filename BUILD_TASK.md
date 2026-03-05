# Build Task — GraysonsDrawOdds Multi-State Rebuild

Build a new multi-state Flask app from scratch. The existing NM-only app is in
this directory. Keep it intact as reference. Build the new app in a NEW
subfolder: /Users/openclaw/Documents/GraysonsDrawOdds/app/

Do NOT stop to ask questions. Make best judgment on ambiguities and keep going.

---

## Context

### Existing NM App
- `app.py` — Flask/SQLite, 532 lines, NM-only
- `nm_hunts.db` — SQLite database with NM draw results and harvest data
- `static/index.html` — 754-line single-page app frontend
- Key routes: /api/hunts, /api/draw_results, /api/species, /api/pools,
  /api/recommend, /api/application_plan, /api/bag_limits

### New Database (PostgreSQL in Docker)
- Host: localhost:5432
- DB: draws, User: draws, Password: drawspass
- Already has schema (all tables created) and 11 states seeded
- Tables: states, species, weapon_types, bag_limits, gmus, pools, hunts,
  hunt_gmus, draw_results_by_pool, harvest_stats, hunt_dates, app_deadlines,
  draw_results (legacy NM table)

### Key Design Rules
1. State is always the first filter. Every API endpoint takes state_code.
2. hunt_code displays exactly as published by the agency — never prefixed.
   NM: 'ELK-1-197', AZ: '1001', CO: 'DE007R1'. Never 'NM-ELK-1-197'.
3. gmu_code is always TEXT, ordered by gmu_sort_key not gmu_code.
4. draw_results_by_pool has one row per hunt × year × pool (normalized).
   For NM, pools are RES/NR/OUTF. For other states, different pool_codes.
5. Subspecies/sex live in bag_limits, not separate species rows.

---

## Phase 1: Migrate NM Data to PostgreSQL

Read all data from `nm_hunts.db` (SQLite) and load it into the PostgreSQL
`draws` database.

Write script: `app/scripts/migrate_nm.py`

Steps:
1. Read all rows from nm_hunts.db: hunts, draw_results, harvest_stats,
   hunt_dates, gmus, hunt_gmus, species, bag_limits, pools
2. Get NM state_id from PostgreSQL states table
3. Insert species into PG species table (on conflict do nothing)
4. Insert bag_limits (on conflict do nothing)
5. Insert gmus with state_id=NM. For gmu_code, read from existing gmus table.
   Generate gmu_sort_key: left-pad pure numeric codes to 5 chars, keep
   alphanumeric suffixes. E.g. '1' → '00001', '55' → '00055', '55A' → '00055A'
6. Insert hunts with state_id=NM, map species and bag_limit FKs
7. Insert hunt_gmus links
8. Insert draw_results (legacy NM table) from existing draw_results
9. ALSO insert into draw_results_by_pool (normalized):
   - One row per hunt × draw_year × pool (RES, NR, OUTF)
   - Get pool_id from pools table for NM
   - Map: resident_applications → applications for RES pool
          resident_licenses → tags_available for RES pool
          resident_results → tags_awarded for RES pool
          (same for NR and OUTF)
10. Insert harvest_stats
11. Insert hunt_dates

Run the script and verify counts match between SQLite and PostgreSQL.

---

## Phase 2: New Flask App

Build: `app/server.py` — new Flask app connecting to PostgreSQL

### Requirements
- Uses psycopg2 (not sqlite3)
- Reads DB connection from env vars (DRAWS_DB_HOST, DRAWS_DB_PORT,
  DRAWS_DB_NAME, DRAWS_DB_USER, DRAWS_DB_PASS) with defaults matching
  the Docker container
- All routes are state-aware
- Preserves ALL existing NM functionality exactly as before
- NM state works identically to the current app — same hunt codes,
  same pool names, same logic

### Routes to build

**GET /api/states**
Returns list of all states with draw_type, unit_type_label, has_otc_tags etc.
Used to populate the state selector dropdown.

**GET /api/species?state_code=NM**
Returns species available for a given state (join hunts to find which species
have data for that state).

**GET /api/units?state_code=NM&species_code=ELK**
Returns GMUs for the selected state and species, ordered by gmu_sort_key.
Respects species_context (Idaho deer units vs elk zones).
Response includes: gmu_id, gmu_code, gmu_name, gmu_sort_key,
dropdown_label (gmu_code + ' — ' + gmu_name if name exists else just gmu_code),
unit_type_label (from states table).

**GET /api/pools?state_code=NM**
Returns pools for the selected state (pool_code, description, allocation_pct).

**GET /api/hunts?state_code=NM&species_code=ELK&gmu_code=1&pool_code=RES&draw_year=2025**
Returns hunts for the given filters with draw odds and latest harvest data.
For AZ: gmu_code filters via hunt_gmus join.
Computes odds = tags_awarded / applications * 100.
Also returns latest harvest success_rate and harvest_year.
Returns: hunt_id, hunt_code, hunt_label (COALESCE(hunt_code_display, hunt_code)),
weapon_code, season_type, bag_code, bag_label, tag_type,
draw_year, applications, tags_available, tags_awarded, draw_odds_pct,
avg_pts_drawn, min_pts_drawn,
latest_harvest_year, latest_success_rate, days_hunted.

**GET /api/draw_years?state_code=NM&species_code=ELK**
Returns available draw years for a state+species (for year selector).

**POST /api/recommend**
Preserved from existing NM app but generalized:
Body: {state_code, species_code, pool_code, gmu_code (optional), draw_year}
Returns top 10 hunts scored by combination of draw odds and harvest success.
For NM: same scoring logic as current app (score = draw_odds * 0.4 + success * 0.6).

**POST /api/application_plan**
Preserved from existing NM app but generalized:
Body: {state_code, species_code, pool_code, choices: [hunt_code1, hunt_code2, hunt_code3]}
Returns odds breakdown for each choice and advice on ordering.
For NM: exact same advice text and logic as existing app.
For other states: generic ordering advice.

**GET /api/bag_limits?state_code=NM**
Returns bag limits used by hunts in this state.

**GET /api/hunt_detail?state_code=NM&hunt_code=ELK-1-197**
Returns full detail for a single hunt: all draw years, all harvest years,
bag limit, weapon type, season dates if available.

---

## Phase 3: Frontend

Build: `app/static/index.html`

Single-page app. Keep the same general aesthetic as the existing index.html
but add state-aware UI.

### UI Flow
1. **State selector** (top of page, required first)
   - Dropdown with all 11 states
   - Shows state name + draw type badge (e.g. "Colorado — Preference Points")
   - Changing state resets all downstream filters

2. **Species selector** (appears after state selected)
   - Elk / Mule Deer / White-tailed Deer (only show species with data for state)

3. **Pool selector** (appears after species selected)
   - Shows pool options for that state (e.g. NM: Resident / Nonresident / Outfitter)
   - For WA: just shows "Open (All Hunters)" since no separate pools

4. **Unit selector** (appears after species selected)
   - Dropdown with search/filter
   - Header text is state's unit_type_label (GMU, Hunting District, etc.)
   - Shows gmu_code + name if available
   - Ordered by gmu_sort_key
   - Optional — leaving blank shows all units

5. **Results table**
   - Hunt code (displayed as agency publishes it)
   - Bag limit (bull/cow/spike/antlerless/either-sex)
   - Weapon type
   - Season type
   - Draw odds % (colored: green >20%, yellow 5-20%, red <5%)
   - Applications / Tags available
   - Latest harvest success rate % (if available)
   - Latest harvest year

6. **Application Plan tab** (same as existing app)
   - Pick 3 hunt codes
   - See combined odds and ordering advice
   - Preserved exactly from NM app, generalized for any state

7. **State info sidebar/panel**
   - Shows draw type, points system, NR allocation, deadlines
   - Sources from states table
   - Links to official draw portal

### Design notes
- Mobile-friendly
- Same color scheme as existing app (reference static/graysons_hunting_data.png for branding)
- No external CSS frameworks needed — keep it clean vanilla or minimal CSS
- Table rows clickable to expand hunt detail

---

## Phase 4: Wire it up

Write: `app/requirements.txt`
```
flask
psycopg2-binary
gunicorn
```

Write: `app/wsgi.py`
```python
from server import app
if __name__ == '__main__':
    app.run()
```

Write: `app/run.sh`
```bash
#!/bin/bash
cd "$(dirname "$0")"
export DRAWS_DB_HOST=localhost
export DRAWS_DB_PORT=5432
export DRAWS_DB_NAME=draws
export DRAWS_DB_USER=draws
export DRAWS_DB_PASS=drawspass
python server.py
```

Write: `app/README.md` explaining:
- How to start the Docker DB: `docker compose up -d` from parent dir
- How to run the app: `bash run.sh`
- How to run the NM migration: `python scripts/migrate_nm.py`
- Database connection details

---

## Completion

When all phases complete:
1. Run migrate_nm.py and confirm NM data is in PostgreSQL
2. Start server.py and confirm / loads
3. Confirm /api/states returns all 11 states
4. Confirm /api/hunts?state_code=NM&species_code=ELK returns NM elk hunts
   matching the existing app's data

Then run:
openclaw system event --text "GraysonsDrawOdds rebuild complete — app/ is ready, NM data migrated to PostgreSQL" --mode now
EOF
echo "Build task written"