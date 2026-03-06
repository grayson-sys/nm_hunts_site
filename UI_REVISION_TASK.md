# UI Revision Task — GraysonsDrawOdds

Make all changes below to /Users/openclaw/Documents/GraysonsDrawOdds/app/static/index.html
Do NOT stop to ask questions. Make all changes in one pass and commit at the end.

---

## 1. Header / Masthead

Replace the current header with:

```
GRAYSON'S DRAW ODDS
A personal research project by Grayson Schaffer — reporter, writer, and obsessive hunter.
[graysonchaffer.com]                           Western big game draw data, 11 states.
```

Styling:
- "GRAYSON'S DRAW ODDS" — bold, 13px uppercase with letter-spacing
- Attribution line below it in 13px regular weight, color #666
- "graysonchaffer.com" — linked to https://graysonchaffer.com, target="_blank", NYT blue (#326891)
- Thin 1px #e2e2e2 rule below header
- Keep it minimal — no hero, no banner, no padding excess

---

## 2. State Selector — Alphabetical Order

Reorder the state pills left to right alphabetically:
AZ | CA | CO | ID | MT | NM | NV | OR | UT | WA | WY

Update both the DOM order AND any JS arrays/objects that reference state order.
Default state on load should still be NM (or whatever is in the URL hash).

---

## 3. Page Layout — Data First

Current order: Editorial content → Odds Explorer
NEW order: Odds Explorer → Editorial content

Specifically the new order within the state panel should be:

1. **Odds Explorer** (filter bar + results table) — FIRST, immediately after the state selector
2. **Build Your Application** — second
3. **Top Hunts** — third
4. **Draw System** (how the draw works) — fourth, below the fold
5. **Strategy Guide** — fifth

Move the filter bar + odds table to the very top of the state content area.
The editorial/strategy content slides below. Users can scroll down to read it.

---

## 4. Draw System Text — Lean and Efficient

The current state draw explanations are too wordy. Rewrite all 11 state draw system
explanations to be tight, information-dense prose. Target: half the current word count.
No throat-clearing. No "It's worth noting that..." No redundant sentences.
Every sentence must carry new information. Write like The Economist, not a blog post.

Example of the new style for NM:
"Pure random lottery, no points. Three pools: resident (84%), nonresident (6%),
outfitter (10%). List up to 3 hunt codes in preference order — one random number
per applicant determines which choice (if any) is awarded. A first-year applicant
has identical odds to a 30-year veteran."

Do the same compression for all 11 states.

Strategy sections: same treatment — 2-3 tight sentences max per point. No bullet soup.

---

## 5. Fix Duplicate Hunt Codes in Dropdown

The hunt code dropdown is showing duplicates. Root cause is likely one of:
a) The SQL query in /api/hunts joining hunt_gmus and returning one row per GMU
b) The JS rendering loop not deduplicating

Fix:
- Check the /api/hunts endpoint SQL — if there's a JOIN on hunt_gmus, add DISTINCT
  or GROUP BY h.hunt_id to collapse duplicates
- In the JS rendering, also deduplicate by hunt_code before rendering the table
- The server.py file is at: /Users/openclaw/Documents/GraysonsDrawOdds/app/server.py

After fixing, test: curl 'http://localhost:5001/api/hunts?state_code=NM&species_code=ELK&pool_code=RES'
Count unique hunt codes vs total rows — should be equal.

---

## 6. Add Hunt Dates Column (framework, no data yet)

Add a "Season Dates" column to the odds table with these rules:
- If hunt_dates data exists in DB: show as "Oct 1–15, 2025" (abbreviated month, en-dash)
- If no dates in DB yet: show "—" (em-dash, muted gray #999)
- Column header: "Season" in the same style as other column headers

The hunt_dates table in PostgreSQL (db=draws, user=draws, pass=drawspass, port=5432) has:
  hunt_id, season_year, open_date, close_date, notes
Query via the existing /api/hunt_detail endpoint or add a dates field to /api/hunts.

Add dates to the /api/hunts response: include open_date, close_date from the most
recent season_year available for that hunt_id.

SQL addition to the hunts query in server.py:
```sql
LEFT JOIN (
  SELECT DISTINCT ON (hunt_id) hunt_id, open_date, close_date, season_year
  FROM hunt_dates
  ORDER BY hunt_id, season_year DESC
) latest_dates ON latest_dates.hunt_id = h.hunt_id
```
Then include open_date, close_date, season_year in the SELECT.

---

## 7. Hunt Characterization — Weapon + Ordinal Label

Each hunt needs a "Season Type" label like: "First Rifle Bull", "Second Archery Any",
"First Cow", "First Muzzleloader Bull", etc.

### Logic for deriving the label (apply to NM first, framework for other states):

**Step 1 — Determine Sex/Bag Type:**
- If bag_limit description contains: antlerless, cow, doe, any-antlered → use that term
- NM uses "4A" (any antlerless = cow/antlerless)
- Map to display: bull, cow, antlerless, any-bull, any-deer, spike, etc.
- When in doubt, show what's in the bag_limits table

**Step 2 — Determine Weapon Type:**
- Parse hunt_code or weapon field for: archery, bow, muzzleloader, ML, rifle, any-weapon
- Canonical order for assigning ordinals: Archery → Muzzleloader → Rifle
  (Note: some states/units flip muzzleloader and rifle — handle by sort date when dates available)

**Step 3 — Assign Ordinal:**
- Within the same GMU + same weapon type + same sex category:
  rank by hunt open_date (or hunt_code sort order if no dates)
  → First, Second, Third, etc.

**Step 4 — Build Label:**
"[Ordinal] [Weapon] [Sex]" → "First Rifle Bull", "Second Archery Any", "First Cow"

### Implementation:
- Add a `season_type` computed field to the /api/hunts response
- Compute server-side in Python (not in JS) — easier to control and debug
- For NM: use existing bag_limits + hunt_dates data to compute now
- For other states: return None / null (display as "—") until data is loaded
- Store computed label in a column `season_label` on the hunts table so it can be
  manually corrected later if the algorithm gets it wrong

Add migration: ALTER TABLE hunts ADD COLUMN IF NOT EXISTS season_label TEXT;
Then run a one-time compute for NM hunts and UPDATE the column.

Show season_label in the odds table as a new column "Season Type".
If null: show "—"

---

## 8. Bag Limits — Link, Don't Hallucinate

In the hunt detail expanded row (when user clicks a row), show:
- Bag limit from the bag_limits table (what's already in DB): "1 bull", "1 antlerless", etc.
- Below it: a linked disclaimer:

"For legal shooting hours, legal weapon specifications, and definitions of legal animals,
see the official [State] hunting proclamation → [link]"

Use these official proclamation/regulation links per state:
- NM: https://www.wildlife.state.nm.us/hunting/big-game/
- AZ: https://www.azgfd.com/hunting/draw/biggame/
- CO: https://cpw.state.co.us/thingstodo/Pages/BigGameDraws.aspx
- UT: https://wildlife.utah.gov/hunting/big-game.html
- NV: https://www.ndow.org/hunt/big-game/
- MT: https://myfwp.mt.gov/fwpPub/drawingStatistics
- ID: https://idfg.idaho.gov/hunt/draw
- WY: https://wgfd.wyo.gov/Hunting/Apply-for-Hunts
- OR: https://myodfw.com/hunting/species/elk-deer
- WA: https://wdfw.wa.gov/hunting/big-game
- CA: https://www.wildlife.ca.gov/Hunting/Big-Game

Style: small 12px text, color #666, link in NYT blue.
Text: "Always verify bag limits and legal animal definitions in the official proclamation
before applying."

---

## 9. Proclamation Data Note (informational — no code needed)

Add a comment block in the HTML source (<!-- -->) noting:
"Hunt season dates are sourced from each state's annual big game hunting proclamation PDF.
These PDFs are released annually (typically Jan-March) and are the authoritative source for
dates, bag limits, legal weapon specs, and season structure. A separate parsing pipeline
(tabula-py / pdfplumber) will extract dates from proclamation PDFs for each state."

---

## 10. After All Changes

1. Commit everything to git:
   cd /Users/openclaw/Documents/GraysonsDrawOdds
   git add -A
   git commit -m "UI revision: data-first layout, alphabetical states, lean copy, dedup hunt codes, season type labels"

2. Test: curl http://localhost:5001/ → 200
3. Test: curl 'http://localhost:5001/api/hunts?state_code=NM&species_code=ELK&pool_code=RES'
   → confirm no duplicate hunt_codes in response, open_date/close_date fields present,
     season_label field present

4. Write REVISION_COMPLETE.md with a brief summary of what changed
