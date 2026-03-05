# Data Source Inventory: Western States Draw Odds & Harvest Data

*Last updated: March 2026*

---

## NM -- New Mexico

### Draw Odds Data
| Item | Details |
|---|---|
| URL | https://wildlife.dgf.nm.gov/hunting/applications-and-draw-information/ |
| Format | PDF (draw results published as PDF documents) |
| Years Available | Multiple years available on NMDGF website |
| Auto-Download | PDFs can be directly downloaded; no API or CSV |
| Notes | 3-pool system (resident/NR/outfitter); no points data needed |

### Harvest Reports
| Item | Details |
|---|---|
| URL | https://www.wildlife.state.nm.us/hunting/harvest-reporting-information/ |
| Format | PDF and some CSV data |
| Years Available | 2016-2024 in current database |
| Auto-Download | Current app already loads from cleaned CSV files |

---

## AZ -- Arizona

### Draw Odds Data
| Item | Details |
|---|---|
| URL | https://draw.azgfd.com/ (portal); https://www.azgfd.com/hunting/hunt-draw-and-licenses/big-game-draw/bonus-point-process/ |
| Format | **PDF only** (bonus point reports, draw results) |
| Years Available | 2017-2025 (Hunt Arizona books for older years) |
| Example URLs | `s3.amazonaws.com/azgfd-portal-wordpress/...` for archived Hunt Arizona PDFs |
| Auto-Download | No API. PDFs hosted on S3 with semi-predictable URLs. Requires PDF parsing (tabula/pdfplumber). |
| Notes | Bonus point tables broken out by species, weapon type, R/NR, all 3 passes |

### Harvest Reports
| Item | Details |
|---|---|
| URL | https://www.azgfd.com/hunting/hunt-draw-and-licenses/harvest-reporting/ |
| Format | **PDF** documents hosted on AWS S3 |
| Years Available | 2022-2025 (partial). Historical Hunt Arizona books go back to 2017. |
| Auto-Download | Direct PDF downloads possible; no structured data format |

---

## CO -- Colorado

### Draw Odds Data
| Item | Details |
|---|---|
| URL (Deer) | https://cpw.state.co.us/hunting/big-game/deer/statistics |
| URL (Elk) | https://cpw.state.co.us/hunting/big-game/elk/statistics |
| Format | **PDF** (Draw Recap, Drawn Out At, Secondary Draw Recap reports) |
| Years Available | 2020-2025 (6 years; older data removed in 2024 for ADA compliance) |
| Historical Archive | https://cpw.cvlcollections.org/collections/show/9 |
| Auto-Download | PDFs on cpw.widen.net have direct download URLs; no login required. No API or CSV. |
| Notes | Reports show apps by hunt code and preference point level, plus drawn results |

### Harvest Reports
| Item | Details |
|---|---|
| URL | Same statistics pages as draw odds (species-specific) |
| Format | **PDF** |
| Years Available | 2019-2024 |
| Auto-Download | Same as draw odds -- direct PDF download, no structured format |

---

## UT -- Utah

### Draw Odds Data
| Item | Details |
|---|---|
| URL | https://wildlife.utah.gov/bg-odds.html |
| Interactive Tool | https://utahdraws.com |
| Format | **PDF** |
| Years Available | 2010-2025 |
| Example URL Pattern | `wildlife.utah.gov/pdf/bg/YYYY/YY_bg-odds.pdf` |
| Auto-Download | Predictable URL patterns; scriptable. Interactive utahdraws.com may offer export. |

### Harvest Reports
| Item | Details |
|---|---|
| URL | https://wildlife.utah.gov/hunting/main-hunting-page/big-game/big-game-harvest-data.html |
| Annual Reports | https://wildlife.utah.gov/hunting/main-hunting-page/annual-reports.html |
| Format | **PDF only** |
| Years Available | 2010-2024 |
| Auto-Download | PDFs with predictable URL patterns; scriptable |

---

## NV -- Nevada

### Draw Odds Data
| Item | Details |
|---|---|
| Bonus Point Data | https://www.ndow.org/blog/bonus-point-data/ |
| Hunt Statistics | https://www.ndow.org/blog/hunt-statistics/ |
| Interactive Tool | HuntNV at ndow.org |
| Format | **PDF** (bonus point tables) + **Excel** (hunt statistics) |
| Years Available | 2022-2025 on main page; pre-2022 in NDOW library |
| Auto-Download | Excel files directly downloadable. PDFs also direct download. URL pattern: `ndow.org/wp-content/uploads/YYYY/MM/filename.pdf` |
| Notes | Best structured data among draw-only states -- Excel harvest stats are filterable |

### Harvest Reports
| Item | Details |
|---|---|
| URL | https://www.ndow.org/blog/hunt-statistics/ |
| Format | **Excel** (filterable) + **PDF** |
| Years Available | 2022-present on main page; older in library |
| Auto-Download | **Yes** -- Excel files can be directly downloaded via URL |

---

## MT -- Montana

### Draw Odds Data
| Item | Details |
|---|---|
| URL | https://fwp.mt.gov/buyandapply/hunting-licenses/drawing-statistics |
| Search Tool | https://myfwp.mt.gov/fwpPub/drawingStatistics |
| Format | **PDF** infographics from search tool |
| Years Available | Multiple years via search tool |
| Auto-Download | Search tool outputs PDF; automated download not confirmed. May require form interaction. |
| Notes | Three report types: bonus point stats, drawing stats, NR combo preference point stats |

### Harvest Reports
| Item | Details |
|---|---|
| URL | https://myfwp.mt.gov/fwpPub/harvestReports |
| Format | **CSV and PDF** export available |
| Years Available | 2003+ (confirmed for some species) |
| Auto-Download | **Yes** -- CSV export available through harvest reports search tool |
| Notes | **Best harvest data accessibility among western states** due to CSV export |

---

## ID -- Idaho

### Draw Odds Data
| Item | Details |
|---|---|
| URL (Hunt Planner) | https://fishandgame.idaho.gov/ifwis/huntplanner/odds/ |
| **API Endpoint** | `https://fishandgame.idaho.gov/ifwis/huntplanner/api/1.1/odds/` |
| Format | **JSON, XML, CSV, TXT, Excel** via export button / API |
| Years Available | **1998-2025** (27+ years!) |
| Auto-Download | **YES -- best in the West.** REST API with queryable parameters. Bulk export in multiple formats. |
| Notes | Fields: hunt number, area, permits available, 1st/2nd choice apps, permits drawn, draw %, R/NR breakdown |

### Harvest Reports
| Item | Details |
|---|---|
| URL | https://fishandgame.idaho.gov/ifwis/huntplanner/harvestfinder.aspx |
| Format | Web interface; likely exportable |
| Years Available | Multiple years via Hunt Planner |
| Auto-Download | Likely exportable via the same API infrastructure as draw odds |

---

## WY -- Wyoming

### Draw Odds Data
| Item | Details |
|---|---|
| URL | https://wgfd.wyo.gov/licenses-applications/draw-results-odds |
| Individual Lookup | https://gfdrawresults.wyo.gov/frmSearch.aspx |
| Hunt Planner | https://wgfd.wyo.gov/HuntPlanner |
| Format | **PDF** documents |
| Years Available | 2021-2026 (draw odds); leftover 2021-2025 |
| Open Data Portal | https://wyoming-wgfd.opendata.arcgis.com/ (may have tabular data) |
| Auto-Download | PDFs have direct download URLs; no official API. ArcGIS portal may offer API endpoints for geospatial data. |
| Notes | Categories: R, NR Regular, NR Special, Random, Pref Point, Landowner |

### Harvest Reports
| Item | Details |
|---|---|
| URL | https://wgfd.wyo.gov/hunting-trapping/harvest-reports-surveys |
| Data Request | wgf.inforequest@wyo.gov |
| Format | **PDF** |
| Years Available | 2020/2021-2025 on website; older by email request |
| Auto-Download | Direct PDF downloads; no structured data format |

---

## OR -- Oregon

### Draw Odds Data
| Item | Details |
|---|---|
| Point Summary Reports | https://myodfw.com/articles/point-summary-reports |
| Controlled Hunt Downloads | https://odfw.huntfishoregon.com/reportdownloads |
| Historical Archive (2005-2016) | https://www.dfw.state.or.us/resources/hunting/big_game/controlled_hunts/reports/hunts_summary_archive.asp |
| Format | **Excel (.xlsx)** and PDF |
| Years Available | 2005-2025 (Excel for 2017+; PDF for 2005-2016) |
| Auto-Download | **Yes** -- Excel files hosted at `dfw.state.or.us/resources/hunting/big_game/controlled_hunts/docs/hunt_statistics/` with direct download links |
| Notes | Point summary reports in Excel are well-structured with preference point distributions |

### Harvest Reports
| Item | Details |
|---|---|
| URL | https://myodfw.com/articles/big-game-statistics |
| Format | **PDF** |
| Years Available | Population survey data 2012-present; harvest data available by request |
| Auto-Download | PDFs with direct URLs; email ODFW.WildlifeInfo@odfw.oregon.gov for additional data |

---

## WA -- Washington

### Draw Odds Data
| Item | Details |
|---|---|
| URL | https://wdfw.wa.gov/hunting/special-hunts/results |
| Format | **Power BI interactive reports** (embedded on webpage) |
| Years Available | 2021-2025 noted; older may be available |
| Auto-Download | **Not easily automated.** Power BI embed does not expose standard API. Limited export from within viewer. |
| Contact | wildthing@dfw.wa.gov or 360-902-2515 for raw data requests |
| Notes | Two Power BI views: Overall Results and Species Breakdown |

### Harvest Reports
| Item | Details |
|---|---|
| URL | https://wdfw.wa.gov/hunting/management/game-harvest |
| Format | **HTML tables** on individual pages |
| Years Available | 2013-2024 (12 years) |
| URL Pattern | `wdfw.wa.gov/hunting/management/game-harvest/{YEAR}/deer-general` |
| Auto-Download | HTML tables could be scraped but no API or bulk download offered |

---

## CA -- California

### Draw Odds Data
| Item | Details |
|---|---|
| URL | https://wildlife.ca.gov/Licensing/Statistics/Big-Game-Drawing |
| Format | **PDF** documents via FileHandler |
| URL Pattern | `nrm.dfg.ca.gov/FileHandler.ashx?DocumentID=XXXXX` |
| Years Available | 2017-2024 (8 years) |
| Organization | 2021-2024: broken by hunt type + point ranges; 2017-2020: consolidated by species |
| Auto-Download | PDF links are direct-download. DocumentID values can be scraped from statistics page. |

### Harvest Reports
| Item | Details |
|---|---|
| Example (2023 Deer) | https://nrm.dfg.ca.gov/FileHandler.ashx?DocumentID=222330 |
| Example (2022 Deer) | https://nrm.dfg.ca.gov/FileHandler.ashx?DocumentID=212676 |
| Format | **PDF** (based on hunter license report card submissions) |
| Years Available | Multiple years via FileHandler |
| Auto-Download | Direct PDF download via DocumentID URL pattern |

---

## Automation Feasibility Summary

| State | Draw Odds Format | Harvest Format | Automation Rating | Notes |
|---|---|---|---|---|
| **NM** | PDF | CSV (in app) | Medium | Already integrated; CSV in existing pipeline |
| **AZ** | PDF | PDF | Low | All PDF; requires PDF parsing |
| **CO** | PDF | PDF | Low | All PDF; direct download URLs |
| **UT** | PDF | PDF | Low-Medium | Predictable URL patterns; utahdraws.com interactive |
| **NV** | PDF + Excel | Excel | **High** | Excel harvest stats directly downloadable |
| **MT** | PDF (search tool) | **CSV export** | **Medium-High** | CSV harvest export excellent; draw stats harder |
| **ID** | **CSV/JSON/Excel/API** | Web tool | **Highest** | REST API + multi-format export; 27 years of data |
| **WY** | PDF | PDF | Low-Medium | Direct PDF links; ArcGIS portal may help |
| **OR** | **Excel + PDF** | PDF | **Medium-High** | Excel point summaries since 2017; good structure |
| **WA** | Power BI (web) | HTML tables | **Low** | No easy export; contact WDFW for raw data |
| **CA** | PDF | PDF | Low-Medium | Direct FileHandler URLs; all PDF |

### Priority Order for Data Integration

1. **Idaho** -- REST API, 27 years of data, multiple export formats. Start here.
2. **Nevada** -- Excel harvest stats, PDF bonus point tables. Good structured data.
3. **Oregon** -- Excel point summary reports since 2017. Well-organized.
4. **Montana** -- CSV harvest export. Draw stats require more work.
5. **Colorado** -- Direct PDF downloads, 6 years recent data.
6. **Utah** -- Predictable PDF URLs, 15 years of data.
7. **Arizona** -- PDF only but S3 URLs are stable.
8. **Wyoming** -- PDF with direct links; ArcGIS portal worth exploring.
9. **California** -- PDF via FileHandler; DocumentID scraping needed.
10. **Washington** -- Power BI + HTML; least automatable. Contact WDFW directly.
