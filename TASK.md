# GraysonsDrawOdds — Autonomous Research Task

You are doing overnight autonomous big game draw system research. Do NOT stop to ask questions. Make your best judgment on all ambiguities and keep going. If you hit a dead end, note it and move on.

## PROJECT CONTEXT
We have an existing Flask/SQLite app combining New Mexico big game draw odds with harvest report data. Expanding to deer and elk draws across all western big game states. Must be equally useful for residents AND nonresidents.

SPECIES: Deer (mule deer + whitetail where applicable) and elk ONLY.

## OUTPUT DIRECTORY: /Users/openclaw/Documents/GraysonsDrawOdds/

---

## PHASE 1: PER-STATE FILES
For each state, write: /Users/openclaw/Documents/GraysonsDrawOdds/<STATE>/draw_system.md

STATES (in order): AZ, CO, UT, NV, MT, ID, WY, OR, WA, CA

For EACH state cover ALL of the following for deer and elk:

### 1. DRAW SYSTEM MECHANICS
- Straight lottery, preference point, bonus point, or hybrid?
- Exact math of how weighted lottery works (e.g. "each bonus point = one additional entry", "points squared", "true preference = ordered queue")
- Separate draws for rifle/archery/muzzleloader?
- Number of choices per application
- What happens if you don't draw any choices?

### 2. POINT BANKING / TAG TURN-BACK
- Can hunters turn in a tag after drawing to keep/gain points?
- Rules and deadlines for tag turn-back
- Effect on points of turning back a tag
- Can you buy a point without applying for a hunt?
- Maximum points currently held (if published)

### 3. RESIDENT VS NONRESIDENT RULES
- % or number of tags allocated to residents vs nonresidents
- Separate draws or combined with quotas?
- Waiting periods between tags for nonresidents?
- Nonresident caps per unit or statewide?
- Residency requirements

### 4. TAG AND LICENSE PRICES
- Resident deer tag/license price
- Nonresident deer tag/license price
- Resident elk tag/license price
- Nonresident elk tag/license price
- Application fees (refundable?)
- Point purchase fees
- Additional fees (habitat stamps, access fees, etc.)
- Price differences by weapon type

### 5. OVER-THE-COUNTER (OTC) TAGS
- OTC deer available? For residents? Nonresidents?
- OTC elk available? For residents? Nonresidents?
- Which units/zones are OTC vs draw?
- Unlimited or quota (FCFS)?
- OTC tag prices

### 6. LANDOWNER TAGS
- Landowner tag program?
- Tags tied to property vs unit-wide?
- Transferable/saleable to nonresidents?
- Volume relative to public draw tags
- Price if different from draw tags

### 7. APPLICATION DEADLINES 2025 AND 2026
- Application period open date
- Application deadline
- Draw results announcement date
- Typical season dates

### 8. DATA SOURCES
- URL for draw odds/results publication
- File format (CSV/Excel/PDF/web tool/API)
- URL for harvest reports
- Format of harvest data
- Years of historical data available
- Can data be auto-downloaded or requires manual steps?

---

## PHASE 2: COMPARISON TABLE
Write: /Users/openclaw/Documents/GraysonsDrawOdds/comparison_table.md

Columns:
- State
- Draw type (lottery/preference/bonus/hybrid)
- Points system summary
- Can buy points without applying? (Y/N)
- Tag turn-back allowed? (Y/N)
- NR tag allocation (% or cap)
- NR waiting period
- Resident deer tag price
- Nonresident deer tag price
- Resident elk tag price
- Nonresident elk tag price
- Application fee
- OTC deer available? (Res/NR/Both/No)
- OTC elk available? (Res/NR/Both/No)
- Landowner tags transferable? (Y/N)
- Application deadline (month)
- Draw results (month)
- Data format (CSV/PDF/Web/Excel)

Include NM in the table (NM uses 3-pool system: resident/nonresident/outfitter, no points).

---

## PHASE 3: DATABASE ARCHITECTURE
Write: /Users/openclaw/Documents/GraysonsDrawOdds/database_architecture.md

Answer: Can all states share a single schema, or do mechanics differ enough to require per-state schemas?

Consider:
- NM has 3-pool system (res/NR/outfitter) with NO points
- Some states: preference points = guaranteed draw-in-order
- Some states: bonus points = weighted random draw
- Some states: hybrid (CO has both preference draw AND weighted bonus in same system)
- Point banking + tag turn-back = additional data fields
- OTC tags fundamentally different from draw tags
- Landowner tag programs vary wildly
- Price structures differ

Recommend ONE schema approach with justification. Show draft CREATE TABLE statements. Current NM tables: hunts, draw_results, harvest_stats, species, bag_limits, pools, hunt_dates, gmus, hunt_gmu.

---

## PHASE 4: DATA SOURCE INVENTORY
Write: /Users/openclaw/Documents/GraysonsDrawOdds/data_sources.md

For each state:
- Exact URLs for draw odds data downloads
- Exact URLs for harvest report downloads
- File format + access notes (e.g., "requires form click", "direct CSV download", "PDF only")
- Years of data available
- Whether automated download script could fetch this

---

## RESEARCH RULES
1. Do NOT stop to ask questions. Ever. Make best judgment and note assumptions.
2. Do NOT summarize or abbreviate. Write complete detailed research for every state.
3. If info not findable, write "NOT FOUND - needs manual verification" and move on.
4. Use web_search and web_fetch extensively. Search "[State] big game draw", "[State] elk draw odds", "[State] deer harvest report", "[State] hunting license fees", etc.
5. Cite all sources with URLs.
6. When ALL phases complete, write: /Users/openclaw/Documents/GraysonsDrawOdds/RESEARCH_COMPLETE.md summarizing what was completed, gaps remaining, and recommended next steps.
7. Do not stop until RESEARCH_COMPLETE.md is written.

When completely finished, run:
openclaw system event --text "GraysonsDrawOdds research complete — check /Users/openclaw/Documents/GraysonsDrawOdds/RESEARCH_COMPLETE.md" --mode now
