# Date Accuracy QA Task

You are a meticulous fact-checker verifying that hunt season dates parsed from
state proclamation PDFs are accurate. Bad dates are a serious problem — a hunter
who shows up in the field on the wrong date could face legal consequences.

Do NOT stop to ask questions. Be thorough and skeptical. Do not give anything a
pass unless you have directly verified it against the source PDF text.

DB: host=localhost port=5432 dbname=draws user=draws password=drawspass

---

## What Was Parsed

These CSVs were produced by an automated pdfplumber parser:
```
AZ/proclamations/2026/AZ_hunt_dates_2026.csv
CA/proclamations/2026/CA_hunt_dates_2026.csv
CO/proclamations/2026/CO_hunt_dates_2026.csv
ID/proclamations/2026/ID_hunt_dates_2026.csv
MT/proclamations/2026/MT_hunt_dates_2026.csv
NV/proclamations/2026/NV_hunt_dates_2026.csv
OR/proclamations/2026/OR_hunt_dates_2026.csv
UT/proclamations/2026/UT_hunt_dates_2026.csv
WA/proclamations/2026/WA_hunt_dates_2026.csv
WY/proclamations/2026/WY_hunt_dates_2026.csv
```

Source PDFs are in the same directory as each CSV.

---

## For Each State: Verification Protocol

### Step 1 — Sanity check the CSV
Load the CSV and check:
a) Are all dates valid ISO format (YYYY-MM-DD)? Any nulls, blanks, "TBD", obviously wrong years?
b) Do the date ranges make biological/seasonal sense?
   - Archery elk: typically Aug–Sep (late summer)
   - Muzzleloader elk: typically Sep–Oct
   - Rifle elk: typically Oct–Nov
   - Archery deer: typically Aug–Sep
   - Rifle deer: typically Oct–Nov
   - No season should open before July or close after January (for big game)
   - open_date must be BEFORE close_date
   - Season length: archery hunts 2–6 weeks, rifle hunts 5–14 days typically
     Flag anything under 2 days or over 90 days as suspicious
c) Are hunt codes in the expected format for that state?
   - AZ: 4-digit numbers (e.g., 1001, 3042)
   - CO: alphanumeric (e.g., DE007R1, EE049O1)
   - UT: alphanumeric (e.g., EM085O1)
   - NV: alphanumeric unit codes
   - MT: HD (Hunting District) numbers
   - ID: 4-digit controlled hunt numbers
   - WY: Hunt Area numbers
   - OR: 3-digit hunt codes
   - WA: alphanumeric
   - CA: zone codes (A, B, D1–D19, X1–X9a, etc.)
d) Are there duplicate hunt codes in the CSV? Flag them.
e) Count total rows. Does it seem reasonable given what you know about each state
   (WY and CO should have the most codes; CA and MT the fewest)?

### Step 2 — Spot-check against source PDF
Pick 10 hunt codes from the CSV at random (or from known high-profile hunts if you
can identify them), open the corresponding source PDF using pdfplumber, and verify
each date directly against the text in the PDF.

```python
import pdfplumber
with pdfplumber.open('path/to/proclamation.pdf') as pdf:
    for page in pdf.pages:
        text = page.extract_text()
        if text and 'HUNT_CODE' in text:
            print(f"Page {page.page_number}:")
            print(text)
```

For each spot-checked hunt code, confirm:
- The hunt code appears in the PDF
- The open_date matches the date shown in the PDF
- The close_date matches the date shown in the PDF
- Mark as: VERIFIED, WRONG, NOT_FOUND, or AMBIGUOUS

### Step 3 — Cross-reference known anchors
These are well-known season structures you can use as anchors:

**AZ:** Elk Unit 1 early archery bull typically opens last week of August.
  Early rifle bull (Unit 1) is typically late October. If the CSV shows rifle
  in August, that's wrong.

**CO:** Archery (O1) season: ~Aug 24 – Sep 21, 2026
  Muzzleloader (E1): ~Sep 12 – Sep 27, 2026
  1st Rifle (W1): ~Oct 10 – Oct 18, 2026
  2nd Rifle (W2): ~Oct 24 – Nov 1, 2026
  3rd Rifle (W3): ~Nov 7 – Nov 15, 2026
  4th Rifle (W4): ~Nov 18 – Nov 22, 2026
  (These are Colorado's standard statewide season dates — every CO hunt with
  "O1" suffix should open around Aug 24. If it doesn't, flag it.)

**WY:** General elk season typically Oct 1 – Oct 31 (Area 1-style)
  Limited quota areas: varies. Antlerless typically Nov.
  
**OR:** General elk: late Oct through mid-Nov for rifle.
  Archery: late Aug–Sep.

**MT:** General deer/elk: starts last Saturday of October (general rifle).
  Archery: early Sep through mid-Oct.
  
**ID:** General deer: Oct 10 – Nov 30 (zones vary)
  General elk: Oct 10 – Nov 30 (zones vary)
  Archery opens late August.

**NV:** Bull elk seasons are extremely limited, typically 7–14 days in Oct–Nov.

**UT:** Archery: typically Aug 19 – Sep 28, 2026
  Early muzzleloader: Sep 5-18 (approx)
  General rifle (any bull): typically Oct 7-21, 2026

**WA:** General elk: Oct 17 – Nov 1 (east of Cascades, rifle)
  Archery: Sep 1-20 (approx)

**CA:** Deer zone A: typically Aug 8 – Sep 27, 2026
  X-zones (archery): typically Jul 11 – Aug 2, 2026

### Step 4 — Flag suspicious data
Create a list of every date that is:
- Clearly wrong (rifle season in August, season ending before it starts, etc.)
- Possibly wrong (plausible but didn't match when spot-checked against PDF)
- Uncertain (hunt code not found in PDF, couldn't verify)
- Format errors (not ISO date, null, placeholder text)

### Step 5 — Correct what you can
If you spot a clear error (wrong month, swapped open/close, year typo 2025 vs 2026),
and you can find the correct date in the PDF, update the CSV directly.
Document every correction made.

Do NOT guess. If you're not sure, leave it as-is and flag it.

### Step 6 — Check CO specifically (highest risk)
Colorado's parser derived dates from season code suffixes (O1, E1, W1, etc.)
rather than reading dates directly from a table. This is an inference, not a direct
read. CO has 1,222 rows — verify the season code → date mapping is actually correct
by checking at least 20 CO hunt codes against the brochure.

Open CO/proclamations/2026/CO_big_game_brochure_2026.pdf and search for the
standard season date table (usually in the front matter). Confirm the O1, E1, W1,
W2, W3, W4 start/end dates match what was used in the CSV.

### Step 7 — MT assessment
MT only had 37 rows extracted. The general deer/elk season has fixed statewide dates.
What are the actual 2026 MT general season dates? Find them in the MT PDF and document
them. Are any of the 37 CSV rows for general season (not LE permits)? If the general
season dates are wrong, that affects every MT general season hunt.

---

## Output: DATE_QA_REPORT.md

Write /Users/openclaw/Documents/GraysonsDrawOdds/DATE_QA_REPORT.md with:

```markdown
# Date Accuracy QA Report
Date: 2026-03-05

## Summary
- States verified: X/10
- Total CSV rows reviewed: X
- Spot-checks performed: X
- VERIFIED: X  WRONG: X  NOT_FOUND: X  AMBIGUOUS: X
- Corrections made: X
- OVERALL CONFIDENCE: HIGH / MEDIUM / LOW per state

## Per-State Results

### [STATE]
- CSV rows: X
- Format issues: [list or "none"]
- Date range sanity: PASS / FAIL — [details]
- Spot-checks (10 samples):
  | Hunt Code | CSV Open | CSV Close | PDF Shows | Result |
  |-----------|----------|-----------|-----------|--------|
- Suspicious dates: [list with reason]
- Corrections made: [list]
- Confidence: HIGH / MEDIUM / LOW
- Notes: [anything else]

## DO NOT LOAD list
Hunt codes/states where dates should NOT be loaded to DB until manually verified:
[list each with reason]

## Corrections Applied to CSVs
[list every change made, old value → new value]

## Recommended Manual Checks
[Anything that needs a human to open the PDF and look]
```

Be specific. "Confidence: HIGH" means you personally spot-checked 10 codes and
they all matched. "LOW" means you found errors or couldn't verify against the PDF.

---

## Final Step: Commit
cd /Users/openclaw/Documents/GraysonsDrawOdds
git add -A
git commit -m "Date QA: accuracy verification and corrections to proclamation CSVs"
