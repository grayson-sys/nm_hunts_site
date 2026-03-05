# Data Gathering Task — GraysonsDrawOdds

Autonomous data collection. Do NOT stop to ask questions. Note failures and keep going.

## Goal
For each of 11 states, find and download raw draw odds and harvest data files
for the LAST 1-2 YEARS ONLY (2023, 2024, 2025 data). Save everything in raw
form — whatever the agency publishes (PDF, CSV, Excel, HTML). No scraping or
parsing yet. Just get the files on disk.

## Output directories (create raw_data/ subfolder per state)
/Users/openclaw/Documents/GraysonsDrawOdds/AZ/raw_data/
/Users/openclaw/Documents/GraysonsDrawOdds/CO/raw_data/
/Users/openclaw/Documents/GraysonsDrawOdds/UT/raw_data/
/Users/openclaw/Documents/GraysonsDrawOdds/NV/raw_data/
/Users/openclaw/Documents/GraysonsDrawOdds/MT/raw_data/
/Users/openclaw/Documents/GraysonsDrawOdds/ID/raw_data/
/Users/openclaw/Documents/GraysonsDrawOdds/WY/raw_data/
/Users/openclaw/Documents/GraysonsDrawOdds/OR/raw_data/
/Users/openclaw/Documents/GraysonsDrawOdds/WA/raw_data/
/Users/openclaw/Documents/GraysonsDrawOdds/CA/raw_data/
/Users/openclaw/Documents/GraysonsDrawOdds/NM/raw_data/

## For each state, try to get TWO things:
1. Draw odds / draw results (how many applied, how many drew, by unit)
2. Harvest reports (success rates, animals taken, by unit)

For DEER and ELK only. Skip other species.

## State-by-state instructions

### NM — New Mexico (existing app, just get fresh data)
Agency: New Mexico Department of Game & Fish (NMDGF)
- Draw results: https://www.wildlife.state.nm.us/hunting/draw-information/draw-results/
- Try: https://www.wildlife.state.nm.us/download/hunting/draw/draw-results/
- Also try searching for "New Mexico big game draw results 2024 2025"
- Harvest reports: https://www.wildlife.state.nm.us/hunting/draw-information/
- Look for CSV or Excel files specifically

### AZ — Arizona
Agency: Arizona Game & Fish Department (AZGFD)
- Draw statistics portal: https://draw.azgfd.com/Statistics
- Try fetching the page and look for PDF/CSV download links
- Direct attempt: https://www.azgfd.com/hunting/hunt-draw-and-licenses/
- Search for "AZGFD draw statistics 2024 2025 deer elk PDF"
- Harvest: https://www.azgfd.com/hunting/harvest-reports/

### CO — Colorado
Agency: Colorado Parks & Wildlife (CPW)
- Draw statistics: https://cpw.state.co.us/hunting/big-game/primary-draw
- Try: https://cpw.state.co.us/Documents/Hunting/BigGame/DrawStatistics/
- Harvest: https://cpw.state.co.us/thingstodo/Pages/Statistics.aspx
- Annual elk harvest stats PDF — search "CPW big game statistics 2024"
- Try direct: https://cpw.state.co.us/Documents/Hunting/BigGame/Statistics/Elk/2024ElkHarvestData.pdf
- Try: https://cpw.state.co.us/Documents/Hunting/BigGame/Statistics/Deer/2024DeerHarvestData.pdf

### UT — Utah
Agency: Utah Division of Wildlife Resources (DWR)
- Draw statistics: https://wildlife.utah.gov/hunting-in-utah/draw-statistics
- Hunt Planner: https://hunt.utah.gov/
- Try fetching hunt.utah.gov and looking for download links
- Search for "Utah DWR draw statistics 2024 2025 deer elk excel CSV"
- Harvest: https://wildlife.utah.gov/hunting-in-utah/big-game

### NV — Nevada
Agency: Nevada Department of Wildlife (NDOW)
- Portal: https://www.ndow.org/hunting/big-game/elk/
- Try: https://www.ndow.org/hunting/draw-odds/
- Search for "Nevada draw statistics 2024 2025 elk deer Excel"
- Harvest reports at NDOW site

### MT — Montana
Agency: Montana FWP
- Hunting portal: https://fwp.mt.gov/hunting/elk
- Try: https://fwp.mt.gov/hunting/apply
- Search "Montana FWP 2024 special permit draw results elk deer"
- Harvest: look for annual Big Game Harvest Report PDF
- Try: https://fwp.mt.gov/conservation/wildlife-management/elk

### ID — Idaho
Agency: Idaho Department of Fish & Game (IDFG)
- Hunt Planner (BEST SOURCE): https://fishandgame.idaho.gov/ifwis/huntplanner/odds/
- Draw statistics: https://idfg.idaho.gov/licenses/controlled/results
- Try fetching that URL and looking for downloads
- Search "Idaho controlled hunt draw results 2024 2025 deer elk CSV"
- Harvest: https://idfg.idaho.gov/reports

### WY — Wyoming
Agency: Wyoming Game & Fish Department (WGFD)
- Draw results: https://wgfd.wyo.gov/Hunting/Draw-Results
- Try: https://wgfd.wyo.gov/hunting/apply-draw/draw-results
- Search "Wyoming draw results 2024 2025 elk deer PDF"
- Harvest: https://wgfd.wyo.gov/Wildlife-Management/Wildlife-Population/Elk

### OR — Oregon
Agency: Oregon Department of Fish & Wildlife (ODFW)
- Draw odds: https://myodfw.com/hunting/applying-oregon-controlled-hunts/deer-elk-controlled-hunt-statistics
- Try: https://www.dfw.state.or.us/resources/hunting/big_game/draw_odds/
- Search "Oregon controlled hunt statistics 2024 2025 deer elk Excel PDF"
- Harvest: https://www.dfw.state.or.us/wildlife/research/

### WA — Washington
Agency: Washington Dept of Fish & Wildlife (WDFW)
- Draw stats: https://wdfw.wa.gov/licenses/hunting/game/elk/draw
- Try: https://wdfw.wa.gov/hunting/reports
- Search "Washington WDFW special permit draw odds 2024 2025 deer elk"
- Data reportedly in Power BI — look for any CSV/Excel links anyway

### CA — California
Agency: California Dept of Fish & Wildlife (CDFW)
- Big Game Drawing: https://wildlife.ca.gov/Licensing/Big-Game
- Try: https://wildlife.ca.gov/Licensing/Big-Game/Draw-Statistics
- Search "California CDFW big game drawing statistics 2024 2025 deer elk PDF"
- Harvest: https://wildlife.ca.gov/Conservation/Hunting/Harvest-Reporting

## Download rules
1. Use curl -L (follow redirects) to download files
2. Verify files are real (not 404 HTML pages) by checking first 4 bytes for %PDF or file size >10KB for CSVs/Excel
3. Name files descriptively: e.g. az_elk_draw_statistics_2024.pdf, co_deer_harvest_2024.csv
4. If a URL returns HTML instead of a data file, save the HTML as a sources file and note the real download requires browser interaction
5. For each state, write a sources.json file listing what was found, what was downloaded, and what needs manual steps

## After all states attempted
Write /Users/openclaw/Documents/GraysonsDrawOdds/DATA_COMPLETE.md listing:
- What was successfully downloaded (with file paths and sizes)
- What was not found (needs manual download or browser access)
- Recommended next steps for gaps

When completely finished, run:
openclaw system event --text "GraysonsDrawOdds data gathering complete — check DATA_COMPLETE.md" --mode now
