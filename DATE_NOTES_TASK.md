# Date Notes + CO Fix Task

Two things to do. Do NOT stop to ask questions.

---

## Task 1: Fix CO O1-R codes from the PDF

The CO date parser got 122 hunt codes wrong — codes ending in O1-R (rifle hunts
incorrectly got archery dates Sep 2-30). The correct dates depend on which rifle
season each unit falls into. Open the brochure and look up the rifle date table.

Source PDF: /Users/openclaw/Documents/GraysonsDrawOdds/CO/proclamations/2026/CO_big_game_brochure_2026.pdf
Target CSV: /Users/openclaw/Documents/GraysonsDrawOdds/CO/proclamations/2026/CO_hunt_dates_2026.csv

The known statewide CO rifle seasons for 2026 (from QA report, confirmed from PDF):
  1st Rifle (W1): Oct 14-18
  2nd Rifle (W2): Oct 24-Nov 1
  3rd Rifle (W3): Nov 7-15
  4th Rifle (W4): Nov 18-22

O1-R codes are units that have a "first rifle" season. In CO, O1-R typically means
the unit's first rifle season opening, which maps to 1st Rifle dates (Oct 14-18)
UNLESS the unit has plains/mesa seasons (Oct 24-Nov 3).

Step 1: Use pdfplumber to search the CO brochure for any table that lists unit-specific
rifle season dates. Look for pages with columns like "Hunt Code | Season | Dates" or
any table where O1-R, O2-R codes appear alongside actual dates.

```python
import pdfplumber
with pdfplumber.open('CO/proclamations/2026/CO_big_game_brochure_2026.pdf') as pdf:
    for i, page in enumerate(pdf.pages):
        tables = page.extract_tables()
        for t in tables:
            if t and any('O1-R' in str(row) or 'rifle' in str(row).lower() for row in t):
                print(f"Page {i+1}:", t[:5])
        text = page.extract_text() or ''
        if 'O1-R' in text or ('rifle' in text.lower() and 'Oct' in text):
            print(f"Page {i+1} has rifle+date text")
```

Step 2: If you find a table mapping O1-R codes to specific dates, apply those dates
to the CSV. If not, use the default 1st Rifle dates (Oct 14-18) for all O1-R codes
as the best available approximation, and add a note column value:
"APPROX: 1st rifle season dates used; verify unit-specific dates in CO brochure"

Update the 122 O1-R rows in CO_hunt_dates_2026.csv accordingly.

Also fix the ~12 O3-M codes if you find them — these are likely 3rd muzzleloader
season codes. CO doesn't have a standard 3rd muzzleloader, so O3-M may actually
mean 3rd Rifle season for muzzleloader-only units (Nov 7-15). Check the PDF.

---

## Task 2: Add publication timeline notes to the UI

Edit /Users/openclaw/Documents/GraysonsDrawOdds/app/static/index.html

For each state, in the Odds Explorer section, when there is NO hunt data available
(API returns empty results), the empty state message should include:

1. Why there's no data ("Hunt data not yet loaded for [State]")
2. When the proclamation/draw data is typically published
3. The application deadline for reference

Find the existing empty state handler in the JS and update it to show a structured
notice like this HTML (adapt to match existing CSS class names):

```html
<div class="empty-state">
  <h3>No draw data loaded yet for [STATE]</h3>
  <p class="empty-body">
    We're working on it. In the meantime, here's what you need to know for [STATE]:
  </p>
  <table class="timeline-table">
    <tr><td>Application opens:</td><td>[MONTH YEAR]</td></tr>
    <tr><td>Application deadline:</td><td>[DATE]</td></tr>
    <tr><td>Draw results:</td><td>[MONTH]</td></tr>
    <tr><td>Regulations published:</td><td>[MONTH]</td></tr>
    <tr><td>Official portal:</td><td><a href="[URL]">[AGENCY NAME]</a></td></tr>
  </table>
</div>
```

Use these per-state values (fill in the JS STATE_INFO object or equivalent):

AZ:
  app_opens: "January (elk/pronghorn) | April (deer)"
  app_deadline: "February 11, 2026 (elk/pronghorn) | June 11, 2026 (deer)"
  draw_results: "March (elk) | July (deer)"
  regs_published: "January (elk booklet, already available) | Current (2025-26 annual regs)"
  portal: "https://www.azgfd.com/hunting/draw/biggame/"
  agency: "AZ Game & Fish"

CO:
  app_opens: "February"
  app_deadline: "April 7, 2026"
  draw_results: "May–June"
  regs_published: "January (brochure already published)"
  portal: "https://cpw.state.co.us/thingstodo/Pages/BigGameDraws.aspx"
  agency: "Colorado Parks & Wildlife"

UT:
  app_opens: "January"
  app_deadline: "March 31, 2026"
  draw_results: "May"
  regs_published: "January (guidebook already published)"
  portal: "https://wildlife.utah.gov/hunting/big-game.html"
  agency: "Utah DWR"

NV:
  app_opens: "March"
  app_deadline: "May 6, 2026"
  draw_results: "Late May"
  regs_published: "February (already published)"
  portal: "https://www.ndow.org/hunt/big-game/"
  agency: "Nevada Department of Wildlife"

MT:
  app_opens: "February (limited-entry permits) | March (combo license)"
  app_deadline: "April 1, 2026"
  draw_results: "Mid-April"
  regs_published: "January (already published)"
  portal: "https://myfwp.mt.gov/fwpPub/drawingStatistics"
  agency: "Montana FWP"

ID:
  app_opens: "April (controlled hunts)"
  app_deadline: "June 5, 2026 (controlled) | December 15 (NR general)"
  draw_results: "July (controlled) | January (NR general)"
  regs_published: "April (2026-27 season rules)"
  portal: "https://idfg.idaho.gov/hunt/draw"
  agency: "Idaho Fish & Game"

WY:
  app_opens: "January (NR elk) | April (deer, resident elk)"
  app_deadline: "February 2, 2026 (NR elk) | June 1, 2026 (deer/resident elk)"
  draw_results: "May (NR elk) | June (deer)"
  regs_published: "February (elk, already available) | April (deer, pending Commission)"
  portal: "https://wgfd.wyo.gov/Hunting/Apply-for-Hunts"
  agency: "Wyoming Game & Fish"

OR:
  app_opens: "March"
  app_deadline: "May 15, 2026"
  draw_results: "June"
  regs_published: "January (already published)"
  portal: "https://myodfw.com/hunting/species/elk-deer"
  agency: "Oregon DFW"

WA:
  app_opens: "March"
  app_deadline: "Late May 2026"
  draw_results: "Late June"
  regs_published: "April–May (2026-27 pamphlet, not yet published as of March 2026)"
  portal: "https://wdfw.wa.gov/hunting/big-game"
  agency: "Washington DFW"

CA:
  app_opens: "May (elk) | June (deer)"
  app_deadline: "June 2, 2026 (elk) | June 30, 2026 (deer)"
  draw_results: "July–August"
  regs_published: "March (already published)"
  portal: "https://www.wildlife.ca.gov/Hunting/Big-Game"
  agency: "California DFW"

NM:
  app_opens: "January"
  app_deadline: "March 18, 2026"
  draw_results: "April"
  regs_published: "January (already published)"
  portal: "https://www.wildlife.state.nm.us/hunting/big-game/"
  agency: "NM Department of Game & Fish"

Note: NM already has data so its empty state won't show — but include the values
in the JS object for completeness.

Also: In the Odds Explorer, when dates ARE present in a row, display them. When
dates are NULL/missing for a specific hunt (but hunt data exists), show a small
italic note next to the "—" in the Season column:
"dates pending [STATE ABBR] proclamation"

---

## Task 3: Mark CO O1-R codes in CSV
After fixing dates, add a column "load_status" to CO CSV:
- All O1-R codes: "APPROX" (if no unit-specific dates found) or "VERIFIED" (if found)
- All other codes already fixed: "VERIFIED" or "CORRECTED"
- Rows with confirmed wrong dates unfixed: "DO_NOT_LOAD"

Also add load_status to UT CSV: all rows = "DO_NOT_LOAD" (wrong hunt codes)

---

## Task 4: Commit
cd /Users/openclaw/Documents/GraysonsDrawOdds
git add -A
git commit -m "CO O1-R date fix attempt + UI empty-state publication timeline notes"
