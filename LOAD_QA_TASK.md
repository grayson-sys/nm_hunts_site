# Live Load QA — Follow Along and Validate

You are a QA validator watching the database as data gets loaded for OR, NV, and ID.
Poll the database every 2 minutes and validate each new state as data appears.

DB: host=localhost port=5432 dbname=draws user=draws password=drawspass
Do NOT stop to ask questions. Be the skeptic. Catch problems the loader might miss.

---

## Your job

Run validation loops. Every 2 minutes, check which states now have data.
When a new state appears (hunt count goes from 0 to >0), run full validation for it.

```python
import psycopg2, time

def get_counts():
    conn = psycopg2.connect(host='localhost', port=5432,
                            dbname='draws', user='draws', password='drawspass')
    cur = conn.cursor()
    cur.execute("""
        SELECT s.state_code,
          COUNT(DISTINCT h.id) as hunts,
          COUNT(DISTINCT dr.id) as draw_results,
          COUNT(DISTINCT hs.id) as harvest_stats,
          COUNT(DISTINCT hd.id) as hunt_dates
        FROM states s
        LEFT JOIN hunts h ON h.state_id = s.id
        LEFT JOIN draw_results_by_pool dr ON dr.hunt_id = h.id
        LEFT JOIN harvest_stats hs ON hs.hunt_id = h.id
        LEFT JOIN hunt_dates hd ON hd.hunt_id = h.id
        WHERE s.state_code != 'NM'
        GROUP BY s.state_code ORDER BY s.state_code
    """)
    rows = cur.fetchall()
    cur.close(); conn.close()
    return {r[0]: {'hunts': r[1], 'draw': r[2], 'harvest': r[3], 'dates': r[4]} for r in rows}

seen = {}
for poll in range(60):  # poll up to 2 hours
    counts = get_counts()
    for state, c in counts.items():
        if c['hunts'] > 0 and seen.get(state, {}).get('hunts', 0) == 0:
            print(f"\n[NEW DATA] {state}: {c}")
            validate_state(state)  # see below
        elif c != seen.get(state, {}):
            print(f"[UPDATE] {state}: {c}")
    seen = counts
    time.sleep(120)
```

---

## validate_state(state_code) — Run these checks

### Check 1: Duplicate hunt codes
```sql
SELECT hunt_code, COUNT(*) as n
FROM hunts h JOIN states s ON s.id = h.state_id
WHERE s.state_code = %s
GROUP BY hunt_code HAVING COUNT(*) > 1
```
Expected: 0 rows. FAIL if any duplicates.

### Check 2: Hunt codes match expected format
- OR: should match r'^\d{3}[A-Z]?$' (3 digits + optional letter)
- NV: should match r'^\d{3}(-\d{3})?-[A-Z]+$' (unit-weapon)
- ID: should match r'^\d{4}$' (4 digits)
Find any outliers. Print them. Don't fail, just flag.

### Check 3: Draw results integrity
```sql
SELECT COUNT(*) as total,
  COUNT(CASE WHEN applicants IS NULL THEN 1 END) as null_apps,
  COUNT(CASE WHEN tags_drawn IS NULL THEN 1 END) as null_tags,
  COUNT(CASE WHEN draw_odds < 0 OR draw_odds > 1 THEN 1 END) as bad_odds,
  COUNT(CASE WHEN tags_drawn > applicants THEN 1 END) as tags_gt_apps,
  MIN(draw_odds) as min_odds, MAX(draw_odds) as max_odds,
  MIN(applicants) as min_apps, MAX(applicants) as max_apps
FROM draw_results_by_pool dr
JOIN hunts h ON h.id = dr.hunt_id
JOIN states s ON s.id = h.state_id
WHERE s.state_code = %s
```
Flag: bad_odds > 0 (odds outside 0-1), tags_gt_apps > 0 (can't draw more than applied)
Note: draw_odds = 0 is valid (nobody drew), odds = 1.0 is valid (all applicants drew)

### Check 4: Harvest stats integrity
```sql
SELECT COUNT(*) as total,
  COUNT(CASE WHEN harvest_success_rate > 1 THEN 1 END) as rate_over_100pct,
  COUNT(CASE WHEN harvest_success_rate < 0 THEN 1 END) as rate_negative,
  MIN(harvest_success_rate) as min_rate, MAX(harvest_success_rate) as max_rate,
  MIN(total_hunters) as min_hunters, MAX(total_hunters) as max_hunters
FROM harvest_stats hs
JOIN hunts h ON h.id = hs.hunt_id
JOIN states s ON s.id = h.state_id
WHERE s.state_code = %s
```
Flag: rate_over_100pct > 0 (impossible), rate_negative > 0

### Check 5: Hunt dates sanity
```sql
SELECT COUNT(*) as total,
  COUNT(CASE WHEN open_date > close_date THEN 1 END) as inverted_dates,
  COUNT(CASE WHEN close_date - open_date > 180 THEN 1 END) as very_long,
  COUNT(CASE WHEN EXTRACT(YEAR FROM open_date) NOT IN (2025,2026,2027) THEN 1 END) as wrong_year,
  MIN(open_date) as earliest, MAX(close_date) as latest
FROM hunt_dates hd
JOIN hunts h ON h.id = hd.hunt_id
JOIN states s ON s.id = h.state_id
WHERE s.state_code = %s
```
Flag: inverted_dates > 0, wrong_year > 0

### Check 6: GMU linkage
Are all hunts linked to at least one GMU?
```sql
SELECT COUNT(*) as hunts_without_gmu
FROM hunts h
LEFT JOIN hunt_gmus hg ON hg.hunt_id = h.id
JOIN states s ON s.id = h.state_id
WHERE s.state_code = %s AND hg.id IS NULL
```
Flag if > 0.

### Check 7: Spot-check 5 random hunts per state
```sql
SELECT h.hunt_code, h.weapon_type, h.sex_restriction,
  dr.pool_code, dr.draw_year, dr.applicants, dr.tags_drawn,
  ROUND(dr.draw_odds::numeric, 3) as odds,
  hd.open_date, hd.close_date
FROM hunts h
JOIN states s ON s.id = h.state_id
LEFT JOIN draw_results_by_pool dr ON dr.hunt_id = h.id
LEFT JOIN hunt_dates hd ON hd.hunt_id = h.id
WHERE s.state_code = %s
ORDER BY RANDOM() LIMIT 10
```
Print these rows. Do they look reasonable? Rifle in Oct-Nov, archery Aug-Sep,
odds between 0 and 1, hunt codes in expected format?

### Check 8: Cross-check against source data (one sample per state)
For OR: Open OR/raw_data/2024_elk_preference_point_draw_report.xlsx,
  read hunt 200M: Tags Authorized=?, Resident Drawn=?, NR Drawn=?
  Query DB: SELECT * FROM draw_results_by_pool WHERE hunt_id IN
    (SELECT id FROM hunts h JOIN states s ON s.id=h.state_id WHERE state_code='OR' AND hunt_code='200M')
  Do the numbers match? If not, it's a loading bug.

For NV: Open NV/raw_data/2024-Nevada-Big-Game-Hunt-Data.xlsx,
  find elk unit 051 residency=Res: Unique Apps=?, Draw Rate=?
  Query DB and compare.

For ID: Open ID/raw_data/elk_controlled_harvest_2024.csv,
  find Hunt# 2001: Hunters=37, Harvest=21, Success%=56
  Query DB and compare.

---

## Output: LOAD_QA_REPORT.md

Write /Users/openclaw/Documents/GraysonsDrawOdds/LOAD_QA_REPORT.md with:
- Per-state validation results (PASS/FAIL per check)
- Any issues found and severity (CRITICAL/WARNING/INFO)
- Cross-check results vs source data
- Final row counts when done

Run until all three states (OR, NV, ID) have been validated, or until 90 minutes
have passed, whichever comes first.

Commit when done:
git add -A && git commit -m "Load QA report: OR, NV, ID validation results"
