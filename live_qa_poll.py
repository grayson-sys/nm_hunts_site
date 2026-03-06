#!/usr/bin/env python3
"""Live Load QA — Poll DB and validate OR, NV, ID as data appears."""

import psycopg2
import re
import time
import json
from datetime import datetime

DB = dict(host='localhost', port=5432, dbname='draws', user='draws', password='drawspass')
STATES = ['ID', 'NV', 'OR']
START = datetime.now()
MAX_MINUTES = 90

report = {}  # state -> {check_name: {status, detail}}


def conn():
    return psycopg2.connect(**DB)


def get_counts():
    c = conn()
    cur = c.cursor()
    cur.execute('''
        SELECT s.state_code,
          COUNT(DISTINCT h.hunt_id) as hunts,
          COUNT(DISTINCT dr.result_id) as draw_results,
          COUNT(DISTINCT hs.harvest_id) as harvest_stats,
          COUNT(DISTINCT hd.hunt_date_id) as hunt_dates
        FROM states s
        LEFT JOIN hunts h ON h.state_id = s.state_id
        LEFT JOIN draw_results_by_pool dr ON dr.hunt_id = h.hunt_id
        LEFT JOIN harvest_stats hs ON hs.hunt_id = h.hunt_id
        LEFT JOIN hunt_dates hd ON hd.hunt_id = h.hunt_id
        WHERE s.state_code IN ('OR','NV','ID')
        GROUP BY s.state_code ORDER BY s.state_code
    ''')
    rows = cur.fetchall()
    cur.close(); c.close()
    return {r[0]: {'hunts': r[1], 'draw': r[2], 'harvest': r[3], 'dates': r[4]} for r in rows}


def validate_state(state_code):
    print(f"\n{'='*60}")
    print(f"  VALIDATING {state_code}")
    print(f"{'='*60}")
    results = {}
    c = conn()
    cur = c.cursor()

    # Check 1: Duplicate hunt codes
    cur.execute('''
        SELECT hunt_code, COUNT(*) as n
        FROM hunts h JOIN states s ON s.state_id = h.state_id
        WHERE s.state_code = %s
        GROUP BY hunt_code HAVING COUNT(*) > 1
    ''', (state_code,))
    dupes = cur.fetchall()
    if dupes:
        results['1_duplicate_hunt_codes'] = {
            'status': 'FAIL',
            'severity': 'CRITICAL',
            'detail': f'{len(dupes)} duplicate hunt codes: {dupes[:10]}'
        }
        print(f"  [FAIL] Check 1: {len(dupes)} duplicate hunt codes!")
        for d in dupes[:10]:
            print(f"    {d[0]} appears {d[1]} times")
    else:
        results['1_duplicate_hunt_codes'] = {'status': 'PASS', 'severity': 'OK', 'detail': 'No duplicates'}
        print(f"  [PASS] Check 1: No duplicate hunt codes")

    # Check 2: Hunt code format
    patterns = {
        'OR': r'^\d{3}[A-Z]?\d?$',
        'NV': r'^\d{3}(-\d{3})?-[A-Z]+$',
        'ID': r'^\d{1,5}$'
    }
    cur.execute('''
        SELECT hunt_code FROM hunts h
        JOIN states s ON s.state_id = h.state_id
        WHERE s.state_code = %s
    ''', (state_code,))
    codes = [r[0] for r in cur.fetchall()]
    pat = patterns.get(state_code, r'.*')
    outliers = [c for c in codes if not re.match(pat, c)]
    if outliers:
        results['2_hunt_code_format'] = {
            'status': 'WARNING',
            'severity': 'WARNING',
            'detail': f'{len(outliers)} outliers of {len(codes)} total: {outliers[:20]}'
        }
        print(f"  [WARN] Check 2: {len(outliers)}/{len(codes)} hunt codes don't match pattern {pat}")
        for o in outliers[:20]:
            print(f"    Outlier: {o}")
    else:
        results['2_hunt_code_format'] = {'status': 'PASS', 'severity': 'OK',
                                          'detail': f'All {len(codes)} codes match {pat}'}
        print(f"  [PASS] Check 2: All {len(codes)} hunt codes match expected format")

    # Check 3: Draw results integrity
    cur.execute('''
        SELECT COUNT(*) as total,
          COUNT(CASE WHEN applications IS NULL THEN 1 END) as null_apps,
          COUNT(CASE WHEN tags_awarded IS NULL THEN 1 END) as null_tags,
          COUNT(CASE WHEN applications > 0 AND CAST(tags_awarded AS float)/applications > 1 THEN 1 END) as tags_gt_apps,
          MIN(CASE WHEN applications > 0 THEN CAST(tags_awarded AS float)/applications END) as min_odds,
          MAX(CASE WHEN applications > 0 THEN CAST(tags_awarded AS float)/applications END) as max_odds,
          MIN(applications) as min_apps, MAX(applications) as max_apps,
          MIN(tags_awarded) as min_tags, MAX(tags_awarded) as max_tags
        FROM draw_results_by_pool dr
        JOIN hunts h ON h.hunt_id = dr.hunt_id
        JOIN states s ON s.state_id = h.state_id
        WHERE s.state_code = %s
    ''', (state_code,))
    r = cur.fetchone()
    total, null_apps, null_tags, tags_gt_apps = r[0], r[1], r[2], r[3]
    min_odds, max_odds, min_apps, max_apps, min_tags, max_tags = r[4], r[5], r[6], r[7], r[8], r[9]

    issues = []
    if tags_gt_apps > 0:
        issues.append(f'{tags_gt_apps} rows where tags_awarded > applications')
    if null_apps > 0:
        issues.append(f'{null_apps} null applications')

    detail = (f'total={total}, null_apps={null_apps}, null_tags={null_tags}, '
              f'tags>apps={tags_gt_apps}, odds_range=[{min_odds},{max_odds}], '
              f'apps_range=[{min_apps},{max_apps}], tags_range=[{min_tags},{max_tags}]')

    if tags_gt_apps > 0:
        results['3_draw_results'] = {'status': 'FAIL', 'severity': 'CRITICAL', 'detail': detail}
        print(f"  [FAIL] Check 3: {'; '.join(issues)}")
    elif total == 0:
        results['3_draw_results'] = {'status': 'INFO', 'severity': 'INFO', 'detail': 'No draw results loaded'}
        print(f"  [INFO] Check 3: No draw results loaded yet")
    else:
        results['3_draw_results'] = {'status': 'PASS', 'severity': 'OK', 'detail': detail}
        print(f"  [PASS] Check 3: Draw results OK ({total} rows, odds [{min_odds:.3f}-{max_odds:.3f}])" if min_odds else f"  [PASS] Check 3: Draw results OK ({total} rows)")

    # Check 4: Harvest stats integrity
    cur.execute('''
        SELECT COUNT(*) as total,
          COUNT(CASE WHEN success_rate > 1 THEN 1 END) as rate_over_100pct,
          COUNT(CASE WHEN success_rate < 0 THEN 1 END) as rate_negative,
          MIN(success_rate) as min_rate, MAX(success_rate) as max_rate,
          MIN(licenses_sold) as min_hunters, MAX(licenses_sold) as max_hunters,
          MIN(harvest_count) as min_harvest, MAX(harvest_count) as max_harvest
        FROM harvest_stats hs
        JOIN hunts h ON h.hunt_id = hs.hunt_id
        JOIN states s ON s.state_id = h.state_id
        WHERE s.state_code = %s
    ''', (state_code,))
    r = cur.fetchone()
    total_h, over100, negative = r[0], r[1], r[2]
    min_rate, max_rate = r[3], r[4]

    detail = f'total={total_h}, rate_over_100%={over100}, rate_negative={negative}, rate_range=[{min_rate},{max_rate}]'

    if over100 > 0 or negative > 0:
        results['4_harvest_stats'] = {'status': 'FAIL', 'severity': 'CRITICAL', 'detail': detail}
        print(f"  [FAIL] Check 4: harvest rate issues — over100={over100}, negative={negative}")
    elif total_h == 0:
        results['4_harvest_stats'] = {'status': 'INFO', 'severity': 'INFO', 'detail': 'No harvest stats loaded'}
        print(f"  [INFO] Check 4: No harvest stats loaded yet")
    else:
        results['4_harvest_stats'] = {'status': 'PASS', 'severity': 'OK', 'detail': detail}
        print(f"  [PASS] Check 4: Harvest stats OK ({total_h} rows, rate [{min_rate:.3f}-{max_rate:.3f}])")

    # Check 5: Hunt dates sanity
    cur.execute('''
        SELECT COUNT(*) as total,
          COUNT(CASE WHEN start_date > end_date THEN 1 END) as inverted_dates,
          COUNT(CASE WHEN end_date - start_date > 180 THEN 1 END) as very_long,
          COUNT(CASE WHEN EXTRACT(YEAR FROM start_date) NOT IN (2025,2026,2027) THEN 1 END) as wrong_year,
          MIN(start_date) as earliest, MAX(end_date) as latest
        FROM hunt_dates hd
        JOIN hunts h ON h.hunt_id = hd.hunt_id
        JOIN states s ON s.state_id = h.state_id
        WHERE s.state_code = %s
    ''', (state_code,))
    r = cur.fetchone()
    total_d, inverted, very_long, wrong_yr = r[0], r[1], r[2], r[3]
    earliest, latest = r[4], r[5]

    detail = f'total={total_d}, inverted={inverted}, very_long={very_long}, wrong_year={wrong_yr}, range=[{earliest},{latest}]'
    issues = []
    if inverted > 0: issues.append(f'{inverted} inverted dates')
    if wrong_yr > 0: issues.append(f'{wrong_yr} wrong year dates')

    if issues:
        results['5_hunt_dates'] = {'status': 'FAIL', 'severity': 'CRITICAL', 'detail': detail}
        print(f"  [FAIL] Check 5: {'; '.join(issues)}")
    elif total_d == 0:
        results['5_hunt_dates'] = {'status': 'INFO', 'severity': 'INFO', 'detail': 'No hunt dates loaded'}
        print(f"  [INFO] Check 5: No hunt dates loaded yet")
    else:
        sev = 'WARNING' if very_long > 0 else 'OK'
        status = 'WARNING' if very_long > 0 else 'PASS'
        results['5_hunt_dates'] = {'status': status, 'severity': sev, 'detail': detail}
        extra = f" ({very_long} very long seasons)" if very_long > 0 else ""
        print(f"  [{status}] Check 5: Hunt dates OK ({total_d} rows, {earliest} to {latest}){extra}")

    # Check 6: GMU linkage
    cur.execute('''
        SELECT COUNT(*) as hunts_without_gmu
        FROM hunts h
        LEFT JOIN hunt_gmus hg ON hg.hunt_id = h.hunt_id
        JOIN states s ON s.state_id = h.state_id
        WHERE s.state_code = %s AND hg.hunt_gmu_id IS NULL
    ''', (state_code,))
    no_gmu = cur.fetchone()[0]
    total_hunts_q = cur.execute('''
        SELECT COUNT(*) FROM hunts h JOIN states s ON s.state_id = h.state_id WHERE s.state_code = %s
    ''', (state_code,))
    total_hunts = cur.fetchone()[0]

    if no_gmu > 0:
        results['6_gmu_linkage'] = {
            'status': 'WARNING',
            'severity': 'WARNING',
            'detail': f'{no_gmu}/{total_hunts} hunts have no GMU linkage'
        }
        print(f"  [WARN] Check 6: {no_gmu}/{total_hunts} hunts have no GMU linkage")
    else:
        results['6_gmu_linkage'] = {'status': 'PASS', 'severity': 'OK',
                                     'detail': f'All {total_hunts} hunts linked to GMUs'}
        print(f"  [PASS] Check 6: All {total_hunts} hunts linked to GMUs")

    # Check 7: Spot-check random hunts
    cur.execute('''
        SELECT h.hunt_code, wt.weapon_code, h.season_type,
          p.pool_code, dr.draw_year, dr.applications, dr.tags_awarded,
          CASE WHEN dr.applications > 0 THEN ROUND(CAST(dr.tags_awarded AS numeric)/dr.applications, 3) ELSE NULL END as odds,
          hd.start_date, hd.end_date,
          sp.common_name
        FROM hunts h
        JOIN states s ON s.state_id = h.state_id
        LEFT JOIN weapon_types wt ON wt.weapon_type_id = h.weapon_type_id
        LEFT JOIN species sp ON sp.species_id = h.species_id
        LEFT JOIN draw_results_by_pool dr ON dr.hunt_id = h.hunt_id
        LEFT JOIN pools p ON p.pool_id = dr.pool_id
        LEFT JOIN hunt_dates hd ON hd.hunt_id = h.hunt_id
        WHERE s.state_code = %s
        ORDER BY RANDOM() LIMIT 10
    ''', (state_code,))
    samples = cur.fetchall()
    cols = ['hunt_code', 'weapon', 'season', 'pool', 'draw_yr', 'apps', 'tags', 'odds', 'start', 'end', 'species']
    print(f"\n  Spot-check samples ({state_code}):")
    for s in samples:
        row = dict(zip(cols, s))
        print(f"    {row}")
    results['7_spot_check'] = {'status': 'INFO', 'severity': 'INFO',
                                'detail': f'{len(samples)} random rows sampled', 'samples': [dict(zip(cols, s)) for s in samples]}

    cur.close(); c.close()
    report[state_code] = results
    return results


def write_report():
    lines = ["# Load QA Report: OR, NV, ID Validation Results\n"]
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Summary
    counts = get_counts()
    lines.append("## Summary Counts\n")
    lines.append("| State | Hunts | Draw Results | Harvest Stats | Hunt Dates |")
    lines.append("|-------|-------|-------------|---------------|------------|")
    for st in STATES:
        c = counts.get(st, {})
        lines.append(f"| {st} | {c.get('hunts',0)} | {c.get('draw',0)} | {c.get('harvest',0)} | {c.get('dates',0)} |")
    lines.append("")

    for st in STATES:
        if st not in report:
            lines.append(f"## {st}: Not yet loaded\n")
            continue
        lines.append(f"## {st}\n")
        lines.append("| Check | Status | Severity | Detail |")
        lines.append("|-------|--------|----------|--------|")
        for check, res in sorted(report[st].items()):
            detail = res['detail'].replace('|', '/').replace('\n', ' ')
            if len(detail) > 120:
                detail = detail[:120] + '...'
            lines.append(f"| {check} | {res['status']} | {res['severity']} | {detail} |")
        lines.append("")

        # Print spot-check samples if available
        if '7_spot_check' in report[st] and 'samples' in report[st]['7_spot_check']:
            lines.append(f"### {st} Spot-Check Samples\n")
            lines.append("```")
            for s in report[st]['7_spot_check']['samples']:
                lines.append(str(s))
            lines.append("```\n")

    # Cross-check section placeholder
    lines.append("## Cross-Check Against Source Data\n")
    lines.append("_See inline notes above per state._\n")

    return '\n'.join(lines)


# ---- MAIN POLLING LOOP ----
print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting QA polling loop...")
print(f"Will poll every 2 minutes for up to {MAX_MINUTES} minutes.\n")

seen = {}
validated = set()

for poll in range(60):
    elapsed = (datetime.now() - START).total_seconds() / 60
    if elapsed > MAX_MINUTES:
        print(f"\n[TIMEOUT] {MAX_MINUTES} minutes elapsed. Stopping.")
        break

    try:
        counts = get_counts()
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] DB error: {e}")
        time.sleep(120)
        continue

    for state, c in counts.items():
        if state not in STATES:
            continue
        prev = seen.get(state, {'hunts': 0, 'draw': 0, 'harvest': 0, 'dates': 0})
        if c['hunts'] > 0 and prev['hunts'] == 0:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] [NEW DATA] {state}: {c}")
            try:
                validate_state(state)
                validated.add(state)
            except Exception as e:
                print(f"  [ERROR] Validation failed for {state}: {e}")
                import traceback; traceback.print_exc()
        elif c != prev:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [UPDATE] {state}: {c}")
            # Re-validate if significantly changed
            if state in validated and (c['draw'] != prev['draw'] or c['harvest'] != prev['harvest']):
                print(f"  Re-validating {state} due to data changes...")
                try:
                    validate_state(state)
                except Exception as e:
                    print(f"  [ERROR] Re-validation failed: {e}")

    seen = counts

    if validated >= set(STATES):
        print(f"\n[DONE] All three states validated!")
        break

    if poll == 0:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Initial state: {counts}")
    else:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Poll #{poll+1} — validated: {validated or 'none yet'} — waiting 2 min...")

    time.sleep(120)

# Write final report
print("\nWriting LOAD_QA_REPORT.md...")
with open('/Users/openclaw/Documents/GraysonsDrawOdds/LOAD_QA_REPORT.md', 'w') as f:
    f.write(write_report())
print("Done.")
