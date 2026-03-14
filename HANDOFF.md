# Handoff Script — State Audit Session
*Written 2026-03-13 22:29 MDT — context at 87%, stopping before wall*

## What Was Completed This Session

### Scale Fixes (DB updated, NOT yet committed)
- ✅ NV: 312 harvest rows × 100 (was 0-1 decimal)
- ✅ UT: 312 harvest rows × 100 (was 0-1 decimal)
- ✅ CA: 132 harvest rows × 100 (was 0-1 decimal)
- ✅ WY 2024: 7 rows nulled (>100 bad metric), 65 rows × 100
- ✅ WY 2025: 446 rows × 100

### MT Draw Odds Fix (DB updated, NOT yet committed)
- Problem: MT numeric hunts (1001-1999) had 2nd-draw data in RES/NR pools (near-0% odds)
- Fix: ran `/Users/openclaw/Documents/GraysonsDrawOdds/MT/scripts/fix_mt_first_draw.py`
- Result: 1243 rows updated, 183 inserted. Hunt 1001 now shows 4.6% RES (was 0.5%)
- Script handles: elk 2024+2025, deer 2024+2025 first-draw CSVs

### Proclamation Status Confirmed
- ✅ MT: Published Jan 28, 2026 — valid March 1, 2026 through Feb 28, 2027
  - PDF: /Users/openclaw/Documents/GraysonsDrawOdds/MT/raw_data/2026-mt-deer-elk-antelope-regs.pdf (26MB, 141 pages)
  - Extracted text: /tmp/mt_dea_regs_2026.txt (~108k tokens — DO NOT load all at once)
  - Key draw info read: bonus pts squared (pts²+1 chances), 1st+2nd choice (some are 1st-only)
  - Application deadlines: LE permits = April 1, B-License/Antelope = June 1
- ❌ WY: Commission meeting April 21-22, 2026 — NOT published yet. Add warning banner.
- ✅ ID: Already has warning banner
- CO, NM: Already live and correct

### Downloads on Disk (not yet imported)
- /Users/openclaw/Documents/GraysonsDrawOdds/AZ/raw_data/az_hunting_regs_2025-26.pdf
- /Users/openclaw/Documents/GraysonsDrawOdds/UT/raw_data/ut_biggame_app_guidebook_2025.pdf
- /Users/openclaw/Documents/GraysonsDrawOdds/NV/raw_data/nv_hunt_stats_2025.xlsx (2025 harvest stats)
- /Users/openclaw/Documents/GraysonsDrawOdds/NV/raw_data/nv_seasons_2025-26_2026-27.pdf
- /Users/openclaw/Documents/GraysonsDrawOdds/OR/raw_data/or_hunting_regs_2026.pdf (29MB)

## What Needs To Be Done Next

### 1. COMMIT FIRST (all DB changes are uncommitted)
```bash
cd /Users/openclaw/sleeperunits
python3 scripts/pull_production_feedback.py
git add draws.db
git commit -m "Fix harvest scale: NV/UT/CA/WY decimal→percentage; fix MT draw odds (1st vs 2nd draw)"
git push origin main
```

### 2. MT Sidebar — Update index.html
Read the EXISTING MT STATE_CONTENT at line ~1447 of static/index.html.
The existing content is good but needs:
- Add `'Choices per app': '2 (1st + 2nd; some LE permits are 1st-only)'` to facts
- Add ⚠️ note to systemHtml: "2026 regs published Jan 28, 2026. Data is current." (GREEN, not warning)
- Update strategy bullets (see below):
  - Add: residents can list 1st + 2nd choice for most B-License hunts
  - Add: NR must draw NR Combo (preference pts) BEFORE competing for LE permits
  - Add: bonus pts are SQUARED not just added (exponential advantage after 5+ pts)
  - Add: harvest success edit — high-point LE units don't always have the best harvest rates
  - Application deadline: April 1 for LE permits, June 1 for B-Licenses

### 3. WY Sidebar — Add warning banner + improve
Add to beginning of WY systemHtml:
```html
<div style="background:#2a1a00;border-left:3px solid #f0a500;padding:10px 14px;margin-bottom:14px;border-radius:0 6px 6px 0;font-size:13px;color:#f5d080;">
  <strong>⚠️ 2026 season dates not yet set.</strong> Wyoming G&F presents 2026 regulations to the Commission April 21–22, 2026. Season dates shown are from 2025. Draw odds are from the 2025 draw. Check <a href="https://wgfd.wyo.gov/regulations" target="_blank" rel="noopener" style="color:#f5d080;text-decoration:underline;">wgfd.wyo.gov/regulations</a> for updates after the April meeting.
</div>
```
Also improve WY strategy (it's thin — only 4 bullets):
- Add: WY draw deadline already passed (Jan 31) — plan for 2027
- Add: NR special vs regular license pools — check both in the data
- Add: resident general season units are largely OTC — huge opportunity
- Add: high-point LE units editorial (same as CO editorial about YouTube hunting)

### 4. NV — Import 2025 Hunt Stats Excel
File: /Users/openclaw/Documents/GraysonsDrawOdds/NV/raw_data/nv_hunt_stats_2025.xlsx
- Open with openpyxl, check column headers
- Match hunt codes to existing NV hunts in DB
- Update harvest_stats with 2025 data (success_rate already fixed to 0-100 scale)
- Also check nv_seasons_2025-26_2026-27.pdf for season dates

### 5. OR — Import Harvest Data
Harvest PDFs on disk in /Users/openclaw/Documents/GraysonsDrawOdds/OR/raw_data/:
- 2024_buck_deer_ALW_harvest_summary.pdf
- 2024_elk_ALW_harvest_summary.pdf
- 2024_elk_archery_harvest_summary.pdf
- 2024_buck_deer_archery_harvest_summary.pdf
- etc.
These are the structured PDFs. Use pdftotext, then parse for hunt code + success rate.

### 6. AZ + UT — Season Dates
AZ: Check existing 253/664 date coverage. AZ regs PDF has season dates.
UT: Check existing 174/768 date coverage. UT guidebook has season dates.

## Key DB Facts
- DB: /Users/openclaw/sleeperunits/draws.db
- MT state_id: check with `SELECT state_id FROM states WHERE state_code='MT'`
- WY state_id: 8
- NV state_id: check DB
- OR state_id: check DB
- sleeperunits repo: /Users/openclaw/sleeperunits/

## Protocol Reference
Full audit protocol: /Users/openclaw/Documents/GraysonsDrawOdds/STATE_AUDIT_PROTOCOL.md
