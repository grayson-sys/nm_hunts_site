# QA Report: Grayson's Draw Odds

**Date:** 2026-03-05
**Tester:** Automated QA Agent
**URL tested:** http://192.168.10.20:5001/
**File under test:** `app/static/index.html`

---

## 1. What Was Tested

### HTTP Endpoints
| Endpoint | Status | Result |
|----------|--------|--------|
| `GET /` | 200 | Page loads, 76KB HTML |
| `GET /api/states` | 200 | Returns 11 states (AZ, CA, CO, ID, MT, NV, NM, OR, UT, WA, WY) |
| `GET /api/hunts?state_code=NM&species_code=ELK&pool_code=RES` | 200 | Returns hunt data with odds, apps, tags |
| `GET /api/species?state_code=NM` | 200 | 7 species (Elk, Mule Deer, Pronghorn, Barbary Sheep, Bighorn Sheep, Ibex, Oryx) |
| `GET /api/pools?state_code=NM` | 200 | 3 pools (RES, NR, OUTF) |
| `GET /api/draw_years?state_code=NM` | 200 | [2025] |
| `POST /api/recommend` | 200 | Returns 10 scored recommendations for NM Elk |
| `POST /api/application_plan` | 200 | Returns combined odds + ordering advice for 3 choices |

### Feature Checklist
| Feature | Pass/Fail | Notes |
|---------|-----------|-------|
| Page title | PASS | "Grayson's Draw Odds" |
| State selector (11 pills) | PASS | All 11 states present, ordered NM first |
| Hash routing (#NM, #AZ) | PASS | URL updates, hashchange listener works |
| Filter bar (species/pool/unit/year) | PASS | All dropdowns present, species cascades to units |
| NM hunt code format | PASS | Displays "ELK-1-132" format correctly |
| Odds coloring | PASS | Green >20%, Amber 5-20%, Red <5% |
| Data table sorting | PASS | Click headers to sort, arrow indicators show |
| Row expansion (detail view) | PASS | Click row to expand, shows draw/harvest history |
| Application Plan tool | PASS | 3 choices, combined odds, ordering advice |
| Top Hunts / Recommend | PASS | Returns scored hunts with notes |
| Editorial content | PASS | All 11 states have full draw system explanations |
| Typography (Helvetica) | PASS | Helvetica Neue/Helvetica/Arial stack |
| Official draw portal links | PASS (with fix) | All 11 states have portal URLs |
| Print stylesheet | PASS | @media print exists, hides nav/filters |
| Tab navigation (Odds/Plan/Top) | PASS | Section tabs work correctly |
| JS syntax | PASS | All braces, parens, brackets balanced |

---

## 2. Bugs Found

### Critical

**BUG-1: Application Plan API requires exactly 3 choices, UI said "up to 3"**
- The `/api/application_plan` endpoint returns `{"error": "Exactly three choices are required"}` when given 1 or 2 choices
- The UI previously said "Pick up to 3 hunt codes" and would send `choices.filter(Boolean)` which could be 1-2 items
- **Status: FIXED** - Updated copy to "Pick 3 hunt codes" and added client-side validation requiring all 3 slots filled

### Moderate

**BUG-2: 10 of 11 states have zero draw data**
- AZ, CO, UT, NV, MT, ID, WY, OR, WA, CA all return empty species lists and zero hunts
- Previously, selecting one of these states showed "Loading..." in species dropdown with no further feedback
- **Status: FIXED** - Species dropdown now shows "No species data yet" (disabled), odds panel shows a clear message explaining data is coming, and state pills are dimmed with an asterisk

**BUG-3: California portal URL pointed to wrong page**
- `https://wildlife.ca.gov/hunting/nonlead` is the non-lead ammunition page, not the draw/licensing page
- **Status: FIXED** - Changed to `https://wildlife.ca.gov/Licensing/Hunting`

**BUG-4: Data tables overflowed on mobile**
- The 8-column hunt data table and 6-column recommendations table had no horizontal scroll wrapper
- On phones, columns would compress to unreadable widths or overflow the viewport
- **Status: FIXED** - Added `.table-scroll` wrapper with `overflow-x: auto` and `min-width: 700px` on tables

**BUG-5: Touch targets too small on mobile**
- State pills shrank to `padding: 5px 12px; font-size: 12px;` on mobile - well under 44px minimum
- Buttons and section tabs also below 44px
- **Status: FIXED** - Added `min-height: 44px` to state pills, buttons, and section tabs; increased mobile pill padding

### Minor

**BUG-6: fact-value HTML not escaped**
- Line 928: editorial fact values are injected as raw HTML (`${value}` not `${esc(value)}`)
- Currently safe because values are hardcoded, but would be XSS-vulnerable if values ever came from user input
- **Status: NOT FIXED** - Intentional for now since some values use `&mdash;` entities

**BUG-7: No loading state on initial page render**
- Between page load and API response, state pills area is empty (pills are built after `fetchJSON('/api/states')`)
- On slow connections, user sees blank state bar briefly
- **Status: NOT FIXED** - Minor, fast API response makes this barely noticeable

---

## 3. What Was Fixed

1. **Application Plan validation** - Now requires all 3 choices filled with helpful guidance message
2. **Application Plan copy** - Changed "up to 3" to "3" with strategy guidance
3. **Empty state handling** - States with no data now show clear messaging across all three tabs (Odds, Plan, Top Hunts)
4. **State pill no-data indicator** - Pills dimmed with asterisk + footnote for states without draw data
5. **California portal URL** - Corrected from non-lead ammo page to hunting/licensing page
6. **Mobile table scrolling** - Added horizontal scroll wrapper to data tables
7. **Mobile touch targets** - State pills, buttons, and section tabs now meet 44px minimum height
8. **Mobile state pill sizing** - Increased padding and font size on small screens

---

## 4. What Still Needs Human Attention

### Data Collection (Blocking for launch quality)
- **10 states have zero draw data.** The editorial content is excellent for all 11, but the Odds Explorer, Application Plan, and Top Hunts tabs return nothing for AZ, CO, UT, NV, MT, ID, WY, OR, WA, CA. This is the #1 gap. A user clicking "CO" sees great editorial but a dead data section.

### Backend
- **Application Plan only works with exactly 3 choices.** Some states allow 1-5 choices per application (CO: 4, NV: 5, OR: 5, WY: 1). The backend should accept variable choice counts per state, or the UI should dynamically show the correct number of choice slots per state.
- **Pool dropdown doesn't cascade from species.** If different species have different pools, this could confuse users. Currently pools load at the state level.

### UX Improvements
- **No auto-search.** User must click "Search" after selecting species. Consider auto-loading results when species is selected (the most common user flow is: pick species -> see data).
- **No search on Enter key.** Filter dropdowns don't respond to Enter.
- **Bag code column uses codes not labels.** Table shows "MB", "A", "ES" instead of "Mature bull", "Antlerless", "Either sex". The bag_label field exists in the API but isn't used in the main table.
- **No state name on pills.** Mobile users may not know what "MT" or "NV" stand for. Consider a tooltip or showing full names on desktop.
- **Year selector defaults to "Latest" with no visual indication of what year that is.** Should say "Latest (2025)" or similar.
- **No favicon.** Browser tab shows generic icon.
- **No meta description or OG tags** for social sharing.
- **Consider adding a simple legend** for the odds color coding (green/amber/red) somewhere visible.

### Content
- **WA portal URL** (`https://wdfw.wa.gov/hunting/management/game-harvest`) goes to harvest data, not draw results. WA doesn't publish draw results in a clean URL; consider linking to the main WDFW hunting page instead.
- **OR portal URL** (`https://myodfw.com/hunting/draw-results`) - verify this is still live.

---

## 5. Honest Ratings

### (a) Visual Design Quality: 7/10
The design is clean, professional, and newspaper-inspired. The Helvetica typography, NYT-style masthead, and restrained color palette work well. The flow diagrams for each state's draw system are genuinely excellent and add visual clarity. Deductions: no favicon, no imagery at all (even subtle iconography would help), and the state pills could have more visual hierarchy between data-ready and coming-soon states.

### (b) Usability: 5/10
NM works end-to-end and the flow is logical. But 10 of 11 states show dead data sections (now improved with messaging, but still disappointing). The requirement to click "Search" instead of auto-loading adds friction. The Application Plan requiring exactly 3 choices with no flexibility is rigid. On mobile, tables now scroll but the overall experience needs more attention (the filter bar stacks to full-width selects which works, but the sidebar-main layout shifts could be smoother). The editorial content is legitimately useful and well-written, which saves this from a lower score.

### (c) Content Completeness: 6/10
**Editorial content: 9/10** - Every state has a thorough, accurate draw system explanation with strategy advice. This is genuinely high-quality writing that would be useful to hunters.
**Data completeness: 2/10** - Only NM has actual draw data loaded. 10 of 11 states have zero species, zero hunts, zero years.
**Blended: 6/10** - The editorial carries the experience, but the tool's core value proposition (draw odds data) is only 9% complete.

### Bottom Line
The foundation is solid. The architecture works. The editorial content is publication-quality. The NM data pipeline is proven and the odds/recommendation engine works correctly. But this is a tool that promises "11 western states" and delivers data for 1. The #1 priority before sharing with Grayson should be getting at least 3-4 more states loaded (AZ, CO, UT, WY are the highest-demand states among western hunters).
