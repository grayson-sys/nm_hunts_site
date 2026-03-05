# Research Complete: Western States Big Game Draw Systems

**Completed:** March 4, 2026
**Scope:** Deer and elk draw systems for AZ, CO, UT, NV, MT, ID, WY, OR, WA, CA (plus NM in comparison table)

---

## Files Produced

### Phase 1: Per-State Draw System Files
| State | File | Lines | Status |
|---|---|---|---|
| AZ | `AZ/draw_system.md` | ~401 | Complete |
| CO | `CO/draw_system.md` | ~446 | Complete |
| UT | `UT/draw_system.md` | ~454 | Complete |
| NV | `NV/draw_system.md` | ~384 | Complete |
| MT | `MT/draw_system.md` | ~440 | Complete |
| ID | `ID/draw_system.md` | ~330 | Complete |
| WY | `WY/draw_system.md` | ~385 | Complete |
| OR | `OR/draw_system.md` | ~411 | Complete |
| WA | `WA/draw_system.md` | ~378 | Complete |
| CA | `CA/draw_system.md` | ~352 | Complete |

Each file covers all 8 required sections: draw mechanics, point banking/turn-back, R/NR rules, prices, OTC tags, landowner tags, deadlines, and data sources.

### Phase 2: Comparison Table
- `comparison_table.md` -- 11-state comparison (10 + NM) with all required columns

### Phase 3: Database Architecture
- `database_architecture.md` -- Single unified schema recommendation with draft CREATE TABLE statements, migration strategy from current NM schema, and per-state examples

### Phase 4: Data Source Inventory
- `data_sources.md` -- Exact URLs, formats, years available, and automation feasibility for all 10 states

---

## Key Findings

### Draw System Variety
- **Pure lottery (no points):** NM, ID
- **Bonus points (weighted random):** AZ (hybrid 3-pass), NV (squared), WA (squared)
- **Preference points (ordered queue):** CA (90/10 deer, 75/25 elk)
- **Hybrid (pref + random split):** CO (100% pref, changing to 50/50 in 2028), UT (50/50 LE, pref for general), MT (75/25 NR combo, bonus for LE), WY (75/25), OR (75/25)

### Nonresident Access
- **Most restrictive:** CA (1 NR elk tag/year statewide), OR (5% NR cap), NM (6% NR)
- **Most accessible:** WA (no NR quota at all), CO (20-25% per hunt code)
- **Cost extremes:** WY special elk at $1,950 NR; MT at $1,312 NR combo; CA elk at $1,826 NR

### OTC Availability
- **Best NR OTC elk:** CO (2nd/3rd rifle, unlimited), UT (any-bull/spike), WA (general season unlimited)
- **No OTC deer or elk:** NM, NV
- **Residents-only OTC:** MT, ID, WY (general season tags)

### Data Accessibility
- **Best:** Idaho (REST API, 27 years, CSV/JSON/Excel export)
- **Good:** Nevada (Excel), Oregon (Excel), Montana (CSV harvest export)
- **Worst:** Washington (Power BI only), most others (PDF only)

---

## Gaps and Items Needing Manual Verification

### Prices
- Several states may have updated fees for 2026-2027 license year not yet published
- MT prerequisite fees may change
- CA 2026 fee schedule not yet officially released

### Deadlines
- WA 2026 special permit dates not yet published (likely late April-May)
- Some states' 2026 dates are projected from historical patterns

### Data Sources
- WA draw data may require direct WDFW contact for structured data
- MT draw statistics automation needs testing (web form interaction)
- CO removed 20+ years of historical data; may need third-party sources

### Landowner Programs
- Exact volume of landowner tags vs public draw tags not published for most states
- CA PLM tag counts not publicly available
- MT 454 agreement volumes not consolidated

### Points Data
- Maximum point levels for some states are approximate (derived from third-party sources)
- ID point distribution data: N/A (no points system)

---

## Recommended Next Steps

1. **Start with Idaho data integration** -- REST API makes it the easiest state to add. Build the multi-state schema, populate with ID data, validate the schema works.

2. **Add Nevada next** -- Excel harvest stats provide structured data. PDF bonus point tables need parsing but are well-organized.

3. **Migrate NM schema** -- Add `state_id` to existing tables, normalize draw_results from pivoted to per-pool format.

4. **Build PDF parsing pipeline** -- Most states (AZ, CO, UT, WY, CA) publish only PDFs. A robust tabula/pdfplumber pipeline will be needed for 7+ states.

5. **Oregon Excel integration** -- Point summary reports since 2017 are Excel; good structured data.

6. **Contact WDFW** -- Request structured draw data export from Washington. Power BI is not automatable.

7. **Monitor CO 2028 changes** -- Major draw system change coming; schema should already handle it (hybrid_split config).

8. **Track legislative fee changes** -- NM (2025 session NR increases), UT (Sept 2025 increases), OR (biennial increases through 2030).

9. **Add harvest data integration** -- After draw odds are loaded, harvest data adds the most value for users comparing hunt quality across states.

10. **Build front-end state selector** -- Update Flask app to support state selection, filtering by species (deer/elk), and cross-state comparison views.
