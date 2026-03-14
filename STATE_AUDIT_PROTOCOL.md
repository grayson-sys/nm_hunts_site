# State Audit Protocol — SleeperUnits
*Reference this before touching any state's data or sidebar.*

---

## PHASE 0 — Snapshot the DB first
```bash
cd /Users/openclaw/sleeperunits
python3 scripts/pull_production_feedback.py   # merge production feedback
git add draws.db && git status                 # confirm clean baseline
```

---

## PHASE 1 — Proclamation / Rules Brochure Check

### 1a. Is it published yet?
```bash
# Try the obvious PDF URL patterns
curl -sI "https://<agency>/big-game-2026.pdf" | head -3
curl -sI "https://<agency>/seasons-rules-big-game-2026.pdf" | head -3
```
- HTTP 200 = published. HTTP 404/500 = not yet.
- If 404: add a **⚠️ banner** to the sidebar `systemHtml` noting that the brochure isn't out yet, what year's data we have, and a link to the agency's rules page.
- Typical timing: most states publish 2–4 weeks before draw application opens.

### 1b. Extract & read it
```bash
ls -lh proclamation.pdf && pdfinfo proclamation.pdf | grep Pages
# Under 10 pages: read directly with Read tool
# 10–50 pages: pdftotext first
pdftotext proclamation.pdf proclamation.txt
wc -c proclamation.txt          # bytes / 4 ≈ token count
# Over 400KB of text: chunk with offset+limit
grep -n "CHAPTER\|SECTION\|^[A-Z0-9]" proclamation.txt | head -40  # find structure
```

### 1c. Extract for each species/hunt type:
- **Draw system type**: preference points / bonus points / pure random / hybrid
- **Number of choices per application** and how ordering works
  - Sequential (one number cycles through ranked choices like NM/CO)?
  - Independent (separate randomization per choice round like ID)?
  - Single choice?
- **Resident vs NR pools**: allocation percentages, separate pools?
- **OTC availability**: which species/seasons, any caps?
- **Application deadline, results date**
- **Season dates by species and weapon type**

---

## PHASE 2 — Draw Odds Data Check

### 2a. Verify scale and completeness
```sql
-- Check draw odds are in reasonable 0–100% range
SELECT st.state_code, sp.species_code,
  COUNT(*) as rows,
  ROUND(MIN(100.0*dr.tags_awarded/dr.applications),1) as min_pct,
  ROUND(MAX(100.0*dr.tags_awarded/dr.applications),1) as max_pct,
  ROUND(AVG(100.0*dr.tags_awarded/dr.applications),1) as avg_pct
FROM draw_results_by_pool dr
JOIN hunts h ON h.hunt_id=dr.hunt_id
JOIN states st ON st.state_id=h.state_id
JOIN species sp ON sp.species_id=h.species_id
WHERE st.state_code='XX' AND dr.applications > 0
GROUP BY sp.species_code;
```
- Expect: min ~0%, max ~100%, avg 15–70% for most states.
- **Red flags**: avg > 95% (all general/OTC hunts, no LE data), avg < 5% (only trophy units imported), any pct > 100.

### 2b. Spot-check 3–5 hunts against source PDF/CSV
```bash
grep "^HUNTCODE," /path/to/source.csv
```
Pick one high-demand unit, one low-demand, one NR-only. Confirm:
- `applications` = source's applicant count for the CORRECT pool (RES vs TOTAL)
- `tags_awarded` = source's draws (not tags_available)
- `draw_year` is correct

### 2c. Check pool structure
```sql
SELECT pool_code, description FROM pools WHERE state_id=X;
```
- Every state needs at minimum: RES and NR pools.
- No `TOTAL` pool exposed in dropdown (filtered in `/api/pools`).
- No `%2ND%` pools in dropdown.
- If state has no resident/NR distinction (pure open draw): one pool named appropriately.

---

## PHASE 3 — Harvest Success Data Check

### 3a. Critical: verify scale
```sql
SELECT ROUND(MIN(success_rate),2), ROUND(MAX(success_rate),2),
       ROUND(AVG(success_rate),2), COUNT(*)
FROM harvest_stats hs
JOIN hunts h ON h.hunt_id=hs.hunt_id
JOIN states st ON st.state_id=h.state_id
WHERE st.state_code='XX' AND hs.success_rate > 0;
```
**Required scale: 0–100 (percentage), NOT 0–1 (decimal)**
- NM, CO, AZ, MT: 0–100 ✓
- ID was 0–1 (fixed 2026-03-13: `UPDATE ... SET success_rate=success_rate*100 WHERE success_rate<=1.0`)
- **Still needs fix**: CA, NV, UT (all have max ~1.0 → multiply by 100)
- **WY anomaly**: some values > 100 — investigate before enabling WY harvest display

If decimal scale found:
```sql
UPDATE harvest_stats SET success_rate = success_rate * 100
WHERE hunt_id IN (SELECT hunt_id FROM hunts h JOIN states st ON st.state_id=h.state_id WHERE st.state_code='XX')
AND success_rate <= 1.0;
```

### 3b. Check coverage
```sql
SELECT COUNT(DISTINCT h.hunt_id) as total_hunts,
       SUM(CASE WHEN hs.hunt_id IS NOT NULL THEN 1 ELSE 0 END) as with_harvest,
       MAX(hs.harvest_year) as latest_year
FROM hunts h
JOIN states st ON st.state_id=h.state_id
JOIN species sp ON sp.species_id=h.species_id
LEFT JOIN (SELECT DISTINCT hunt_id, MAX(harvest_year) harvest_year
           FROM harvest_stats GROUP BY hunt_id) hs ON hs.hunt_id=h.hunt_id
WHERE st.state_code='XX' AND sp.species_code='ELK' AND h.is_active=1;
```
- Under 50% coverage: note in sidebar that harvest data is partial.
- Harvest year should be within 2 years of current.

### 3c. Spot-check against source
Pick 3 hunt codes. Confirm `success_rate` in DB matches source PDF/CSV.
```bash
grep "HUNTCODE" harvest_source.csv
```

---

## PHASE 4 — Season Dates Check

### 4a. Coverage
```sql
SELECT sp.species_code,
  COUNT(DISTINCT h.hunt_id) as total,
  SUM(CASE WHEN hd.hunt_id IS NOT NULL THEN 1 ELSE 0 END) as with_dates
FROM hunts h
JOIN states st ON st.state_id=h.state_id
JOIN species sp ON sp.species_id=h.species_id
LEFT JOIN (SELECT DISTINCT hunt_id FROM hunt_dates) hd ON hd.hunt_id=h.hunt_id
WHERE st.state_code='XX' AND h.is_active=1
GROUP BY sp.species_code;
```

### 4b. Year sanity
```sql
SELECT season_year, COUNT(*) FROM hunt_dates hd
JOIN hunts h ON h.hunt_id=hd.hunt_id JOIN states st ON st.state_id=h.state_id
WHERE st.state_code='XX' GROUP BY season_year;
```
- All dates should be same season_year (typically current year).
- If proclamation isn't published yet, use prior year and add the ⚠️ banner.

---

## PHASE 5 — Sidebar Content Checklist

Each state in `STATE_CONTENT` needs all of these:

```javascript
{
  drawLabel: 'TYPE',          // e.g. 'PURE RANDOM', 'PREFERENCE', '75/25 HYBRID'
  facts: {
    'Points system': '...',
    'NR allocation': '...',
    'Choices per app': '...',
    'Application deadline': '...',
    'Results announced': '...',
    'OTC available': '...',
  },
  portalUrl: '...',
  portalLabel: '...',
  systemTitle: 'How X\'s Draw Works',
  systemHtml: `...`,          // include flow diagram; ⚠️ banner if brochure unpublished
  strategy: [ ... ],          // 5–7 specific, actionable bullets
  ui: {
    numChoices: N,            // 1–5 choices per app
    hasPrefPoints: bool,      // drives pts-range filter + pt badges
    sleeperDefaultRange: '',  // '' | '0-1' | '2-9' | '10+' (CO: '2-9')
    rutMode: bool,            // NM only
    byaIntro: `...`,          // CO-style HTML intro for BYA tab (if hasPrefPoints)
  },
}
```

**Strategy bullets must be specific**, not generic. Include:
- The mechanic most hunters get wrong
- How to use 1st/2nd choices optimally for THIS state
- OTC backstop if available
- A honest editorial note (e.g. "high-point units often have low harvest success")
- Any upcoming rule changes

---

## PHASE 6 — Final Verification

```bash
# Run Sleeper Units locally for the state
python3 -c "
from server import app
with app.test_client() as c:
    import json
    resp = c.post('/api/recommend',
        data=json.dumps({'state_code':'XX','species_code':'ELK','pool_code':'RES'}),
        content_type='application/json')
    data = json.loads(resp.data)
    print('Total:', len(data['results']))
    for r in data['results'][:5]:
        print(r['hunt_label'], 'odds=', r['draw_odds'], 'sr=', r['success_rate'])
"
```
Sanity checks:
- Top results have draw_odds ≥ 0.3 (30%) for most states
- success_rate values are 0–1.0 decimal **in the API response** (server divides by 100 for display)

Wait — actually server does NOT divide. The `fmtPct` in frontend receives raw value.
Check: if harvest_stats stores 56.0, then `r['success_rate'] = 56.0` in API and `fmtPct(56.0)` → "56%". ✓

```bash
# Commit
git add draws.db static/index.html
git commit -m "STATE: audit complete — draw odds/harvest/dates verified"
git push origin main
```

---

## QUICK STATE STATUS TABLE
*Last updated: 2026-03-14*

| State | Draw Odds | Harvest | Dates | Scale OK | Brochure | Sidebar | Live |
|-------|-----------|---------|-------|----------|----------|---------|------|
| NM    | ✅ 2025   | ✅ 2024 | ✅    | ✅ 0-100 | ✅ published | ✅ full | ✅ |
| CO    | ✅ 2025   | ✅ 2025 | ✅    | ✅ 0-100 | ✅ published | ✅ full | ✅ |
| ID    | ✅ 2025   | ✅ 2024 | ✅ 2025 | ✅ fixed 3/13 | ⚠️ mid-Apr 2026 | ✅ full + ⚠️ banner | ✅ |
| MT    | ✅ 2025 fixed | ⚠️ 292/722 | ✅ | ✅ 0-100 | ✅ Jan 28 2026 | ✅ full + ✅ banner | ⚠️ harvest gap |
| WY    | ✅ 2025   | ✅ fixed 3/14 | ✅ | ✅ fixed 3/14 | ❌ Apr 21-22 Commission | ✅ full + ⚠️ banner | ⚠️ dates TBD |
| AZ    | ✅ 2025   | ✅ partial | ⚠️ MDR/ANT=0 | ✅ 0-100 | ✅ published | ⚠️ basic | ⚠️ dates gap |
| UT    | ✅ 2025   | ⚠️ partial | ⚠️ sparse | ✅ fixed 3/14 | ❓ | ⚠️ basic | ❌ |
| NV    | ✅ partial | ✅ 2024+2025 | ⚠️ 222/412 | ✅ fixed 3/14 | ❓ | ⚠️ basic | ❌ |
| OR    | ✅ 2025   | ✅ 278 rows 3/14 | ⚠️ partial | ✅ 0-100 | ✅ published | ⚠️ basic | ❌ |
| CA    | ✅ partial | ✅ partial | ⚠️ sparse | ✅ fixed 3/14 | ✅ published | ⚠️ basic | ❌ |
| AK    | ❌ none   | ❌ none  | ❌ none | N/A | ❓ | ❌ none | ❌ |

---

## HARD-WON LESSONS (from Grayson's direction, 2026-03-13/14)

### Harvest Scale — Critical Check
**The most common import bug.** Many state agencies publish harvest success as a 0–1 decimal (e.g., 0.56 = 56%). The DB must store 0–100 scale. The frontend `fmtPct(v)` expects raw percentage value.
- Fix: `UPDATE harvest_stats SET success_rate=success_rate*100 WHERE success_rate<=1.0 AND hunt_id IN (...state filter...)`
- States fixed: ID (2026-03-13), NV/UT/CA/WY (2026-03-14)
- WY had additional issue: some rows had values >100 (wrong metric entirely — null those out before multiplying)

### MT Draw Odds — 1st vs 2nd Draw
Montana publishes separate CSV files for 1st draw and 2nd draw. The 2nd draw covers leftover tags (4 permits → 0.5% odds). The 1st draw is what hunters actually compete in (60 permits → 5% odds). **Always import 1st draw data into the main RES/NR pool.** The script `MT/scripts/fix_mt_first_draw.py` corrected 1243 rows.

### AZ Hunt Code Species Mapping
AZ uses sequential numeric hunt codes across ALL species. The draw data PDFs don't always label species. Map ranges carefully:
- 1000–1999 = Deer (MDR/WTD)
- 2000–3999 = Elk
- 4000–4999 = Antelope/Pronghorn
- 5000–5999 = Javelina (NOT elk!)
- 6000–6999 = Desert Bighorn Sheep (NOT elk!)
- 7000–7999 = Bison (NOT elk!)
- 9000–9999 = Sandhill Crane (NOT elk!)
**Watch for misclassification.** Any AZ hunt codes in the 5000–9999 range labeled as ELK in the DB are likely wrong.

### PDF Parsing Strategy
- **pdftotext**: Fast, good for simple text. Merges words in multi-column layouts.
- **pdfplumber with x_tolerance=2**: Use for columnar tables (harvest summaries). Lower x_tolerance prevents word-merging across columns. Oregon harvest PDFs need this.
- **pdfplumber extract_tables()**: Use for CO drawn_out_at PDFs (structured tables). Fails if no table structure detected.
- **Never load a PDF text file > ~120k tokens into context at once.** Extract first, grep for section headers, read in chunks with offset+limit.

### Continuous Journal Protocol (from Grayson, 2026-03-14)
- **Before** any big task: write entry in `memory/YYYY-MM-DD.md` — what you're doing, files involved, expected outcome
- **During** long tasks: update with checkpoints (what's done, what's next)
- **After** any compaction/context reset: read today's memory file + MEMORY.md FIRST before doing anything
- Memory file: `/Users/openclaw/.openclaw/workspace/memory/2026-03-14.md`
- Watcher nudge format: "Read memory/YYYY-MM-DD.md + MEMORY.md, then resume from REMAINING QUEUE section. Last state: [paste checkpoint]."

---

## NEXT STATES QUEUE
1. **AZ** — Add MDR/ANT season dates from regs PDF; deactivate misclassified 5000-9999 "elk" hunts
2. **UT** — Parse season dates from ut_biggame_app_guidebook_2025.pdf (174/768 covered)
3. **NV** — Season dates (unit group format mismatch between PDF and DB — needs fuzzy match)
4. **OR** — Season dates from or_hunting_regs_2026.pdf (29MB — chunk carefully)
5. **MT** — Find harvest gap (292/722 — likely missing weapon-type or species sub-categories)
6. **AK** — Build from scratch: research ADFG draw system, acquire data, create state record

## Draw Deadlines (reference for prioritization)
- NM: Mar 19 ✅ closed
- CO: Apr 7 ✅ live
- UT: Apr 23
- NV: early May
- WY NR elk: Feb 2 ✅ closed; deer/resident elk Jun 1
- MT: Apr 1 (LE) / Jun 1 (B-License)
- ID: Jun 5
- AZ: Jun 9
- CA: Jun 2026
- AK: varies by species, many Dec–Mar
