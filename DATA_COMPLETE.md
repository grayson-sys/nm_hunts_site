# Data Gathering Complete

**Date:** 2026-03-05
**Total files downloaded:** ~178 data files across 11 states
**Total size:** ~282 MB

---

## Successfully Downloaded

### NM — New Mexico (7 files, 2.9 MB)
| File | Description |
|------|-------------|
| `2025OddsSummary.xlsx` | 2025 draw odds summary (all species) |
| `2025CompleteReport.xlsx` | 2025 draw odds by hunt code |
| `2024OddsSummary.xlsx` | 2024 draw odds summary |
| `2024CompleteReport.xlsx` | 2024 draw odds by hunt code |
| `Elk_Harvest_Report_2024_Corrected.pdf` | 2024-25 elk harvest by GMU |
| `2024-2025-deer-harvest-report.pdf` | 2024-25 deer harvest by GMU |
| `2023-2024-deer-harvest-report.pdf` | 2023-24 deer harvest by GMU |

**Format quality:** Excellent — Excel files for draw odds, PDF for harvest. No preference points (random draw).

### AZ — Arizona (24 files, 37 MB)
- **Draw data:** Bonus point reports + draw pass reports for Fall (deer) and Midwinter (elk) cycles, 2024 & 2025
- **Harvest:** 2024 & 2025 deer and elk harvest summaries
- **Bonus:** 2025-26 hunting regulations, 2026 elk regulations

**Format quality:** All PDFs. Draw odds derivable from bonus point + pass reports.

### CO — Colorado (16 files, 92 MB)
- **Draw data:** Primary draw recaps + secondary draw recaps + "drawn out at" reports for deer & elk, 2024 & 2025
- **Harvest:** 2023 & 2024 deer/elk harvest reports

**Format quality:** Large PDFs (~11 MB each for draw recaps). Very comprehensive.

### UT — Utah (12 files, 36 MB)
- **Draw data:** 2024 & 2025 general deer odds, big game (LE/OIAL) odds, youth elk, antlerless, dedicated hunter
- **Harvest:** 2024 general-season buck deer, LE/OIAL, antlerless harvest reports
- **Bonus:** 2024 comprehensive big game annual report (14 MB)

**Format quality:** All PDFs. General elk is OTC (no draw). LE elk included in bg-odds files.

### NV — Nevada (28 files, 28 MB)
- **Draw data:** 16 bonus point PDFs (deer + elk, by weapon/residency), 2025 draw report, public draw list
- **Harvest:** 7 harvest PDFs (deer + elk by unit group, composition, antler data)
- **Bonus:** `2024-Nevada-Big-Game-Hunt-Data.xlsx` — structured Excel with quotas + harvest
- **Population:** 2 Big Game Status Books

**Format quality:** Mix of PDFs + one key Excel file. Draw odds derived from bonus point PDFs.

### MT — Montana (12 files, 30 MB)
- **Draw info:** Bonus point FAQ/statistics PDFs, NR combo preference point data
- **Harvest:** Region 1 elk (2024) + mule deer (2023), Region 4 elk + deer/elk justifications
- **Regulations:** 2024 deer/elk regs with permit quotas

**Format quality:** All PDFs. Partial coverage — see gaps below.

### ID — Idaho (7 CSVs + 8 HTML, 1.9 MB)
- **Harvest:** 6 CSV files with 1,520+ rows — controlled + general harvest for deer & elk (2023-2024)
- **Summary:** Statewide harvest summary 2024

**Format quality:** CSVs extracted from HTML tables — good structured data for harvest.

### WY — Wyoming (24 files, 19 MB)
- **Draw data:** 2024 & 2025 combined odds reports + 18 detailed PDFs by species/residency/draw type
- **Harvest:** 2024 & 2025 deer and elk harvest reports

**Format quality:** All PDFs. Very comprehensive coverage.

### OR — Oregon (23 files, 3.6 MB)
- **Draw data:** 8 Excel files — applicants by hunt choice + preference point draw reports for deer & elk (2024-2025)
- **Harvest:** 11 PDFs — deer/elk harvest by weapon type, public/private land breakdowns
- **Population:** 4 PDFs with population estimates 2021-2025

**Format quality:** Excellent — Excel for draw data, clean PDFs for harvest. Best structured data alongside NM.

### WA — Washington (14 files, 23 MB)
- **Harvest:** HTML pages with embedded tables for deer/elk (statewide, general, special) 2024
- **Draw proxy:** eRegulations pages with 2024 applications/avg points per hunt code
- **Regulations:** 2025 big game regulations PDF (18 MB)

**Format quality:** Mixed HTML + PDF. Draw odds require Power BI — see gaps below.

### CA — California (25 files, 8.8 MB)
- **Draw data:** 13 deer + 5 elk draw statistics PDFs (2024) broken by weapon type and preference point ranges
- **Harvest:** 2023 & 2024 deer harvest, 2021 & 2022 elk harvest, 2023 & 2024 elk tooth age
- **Bonus:** 2024-2025 Big Game Digest

**Format quality:** All PDFs. Good coverage for deer; elk harvest lags (most recent is 2022).

---

## Gaps Requiring Manual Download

### Critical Gaps (draw odds data missing or incomplete)

| State | What's Missing | Where to Get It | Difficulty |
|-------|---------------|-----------------|------------|
| **MT** | Actual draw statistics (applicants vs successful by permit) | `myfwp.mt.gov/fwpPub/drawingStatistics` — interactive portal | Browser required |
| **ID** | Draw odds data (all years) | `fishandgame.idaho.gov/ifwis/huntplanner/odds/` — has CSV/Excel/JSON export | Browser required (API crashes on direct HTTP) |
| **WA** | Full draw odds/results | Two Power BI dashboards linked from WDFW draw results page | Browser + Power BI export |

### Moderate Gaps (partial data)

| State | What's Missing | Notes |
|-------|---------------|-------|
| **MT** | Harvest reports for Regions 2, 3, 5, 6, 7 | Only Regions 1 & 4 captured; data spread across many regional PDFs |
| **CA** | 2023-2024 elk hunt statistics | Most recent on CDFW site is 2022; may not be published yet |
| **CO** | 2024 harvest from CPW Widen Collective (JS-rendered) | State library alternatives were downloaded instead |

### Minor Gaps

| State | What's Missing | Notes |
|-------|---------------|-------|
| **AZ** | Individual draw results | Requires authenticated AZGFD portal account |
| **WA** | Structured harvest CSVs | HTML tables captured; need parsing |

---

## Recommended Next Steps

1. **Manual browser downloads (highest priority):**
   - **Idaho draw odds:** Open Hunt Planner odds page, filter for deer + elk, export CSV for 2023-2025
   - **Montana draw statistics:** Open myFWP portal, export draw stats for deer + elk permits
   - **Washington draw odds:** Open Power BI dashboards, use built-in export for CSV

2. **Parse raw data into structured format:**
   - OR and NM have Excel files — easiest to start with
   - ID harvest CSVs are ready to use
   - All other states need PDF parsing (tabula-py or similar)

3. **Standardize schema across states:**
   - Draw odds: state, year, species, unit, weapon, residency, applicants, successful, tags_available, draw_pct
   - Harvest: state, year, species, unit, weapon, hunters, harvest, success_rate

4. **Fill Montana regional gaps:**
   - Track down harvest reports for remaining 5 FWP regions
   - Consider contacting FWP directly for consolidated data

---

## File Format Summary

| Format | States | Parsing Difficulty |
|--------|--------|-------------------|
| Excel (.xlsx) | NM, OR, NV (1 file) | Easy |
| CSV | ID | Ready to use |
| PDF | AZ, CO, UT, NV, MT, WY, CA, UT | Medium (tabula-py) |
| HTML tables | WA, ID (source) | Medium (BeautifulSoup) |
| Interactive portal | MT, ID, WA (draw odds) | Manual export needed |
