#!/usr/bin/env python3
"""
Fetch Montana harvest data for all species from myfwp.mt.gov using Playwright.

HOW IT WORKS (from harvestReports.js, 2026-03-14):
  1. Select species  → call handleSelectSpecies() → loads year dropdown
  2. Select start yr → trigger('change') on #licYearStart → loads end year dropdown
  3. Select end yr   → trigger('change') on #licYearEnd → loads district dropdown
  4. Select district → trigger('change') on #districtId → enables buttons
  5. Call handleViewReport() → sets reportNm='HarvestEstimates', publishes
     'popReportResultsDiv' topic → loads data via POST to reportResultsDiv_input.action

CSV download also possible via handleGenerateReport('CVS') but HTML table is easier
to parse and avoids file download handling.

Columns returned (elk): License Year, Hunting District, Residency, Hunters, Days,
Days per Hunter, Total Harvest, Bow, Rifle, Spike Bull Elk, <6pt, 6+pt

Usage:
    python3 fetch_mt_harvest.py            # all species, all years in YEARS list
    python3 fetch_mt_harvest.py EL 2024   # single species + year

Requirements:
    pip install playwright && playwright install chromium
"""
import asyncio
import csv
import os
import sys

OUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'raw_data')
BASE_URL = "https://myfwp.mt.gov/fwpPub/harvestReports"

SPECIES = [
    ("EL", "elk"),
    ("DE", "deer"),
    ("PA", "antelope"),
    ("MO", "moose"),
    ("BS", "sheep"),
    ("MG", "goat"),
]
# Update this list each year before running
YEARS = ["2023", "2024"]


def log(msg):
    print(msg, flush=True)


async def fetch_one(page, species_cd, species_name, year):
    log(f"\n--- {species_name} {year} ---")

    await page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
    await page.wait_for_selector('#speciesCd', timeout=20000)

    # Step 1: species
    await page.select_option('#speciesCd', species_cd)
    await page.evaluate("handleSelectSpecies()")

    # Step 2: start year
    await page.wait_for_function(
        f"document.querySelector('#licYearStart option[value=\"{year}\"]') !== null",
        timeout=15000
    )
    await page.select_option('#licYearStart', year)
    await page.evaluate("$('#licYearStart').trigger('change')")

    # Step 3: end year
    await page.wait_for_function(
        f"document.querySelector('#licYearEnd option[value=\"{year}\"]') !== null",
        timeout=15000
    )
    await page.select_option('#licYearEnd', year)
    await page.evaluate("$('#licYearEnd').trigger('change')")

    # Step 4: district
    await page.wait_for_function(
        "document.querySelector('#districtId option[value=\"ALL\"]') !== null",
        timeout=15000
    )
    await page.select_option('#districtId', 'ALL')
    await page.evaluate("$('#districtId').trigger('change')")

    # Step 5: trigger view
    await page.evaluate("handleViewReport()")

    # Wait for data to load
    try:
        await page.wait_for_function(
            "document.querySelectorAll('#reportResultsDiv tbody tr td').length > 0",
            timeout=25000
        )
    except Exception:
        log(f"  No data returned for {species_name} {year}")
        return 0

    # Extract table
    result = await page.evaluate("""
        () => {
            const table = document.querySelector('#reportResultsDiv table');
            if (!table) return null;
            const headers = Array.from(table.querySelectorAll('thead th'))
                .map(th => th.innerText.trim()).filter(h => h);
            const rows = Array.from(table.querySelectorAll('tbody tr'))
                .map(tr => Array.from(tr.querySelectorAll('td'))
                    .map(td => td.innerText.trim()));
            return {headers, rows};
        }
    """)

    if not result or not result.get('rows'):
        log(f"  Empty result")
        return 0

    headers = result['headers']
    data_rows = [r for r in result['rows'] if any(c for c in r)]
    log(f"  {len(data_rows)} rows | cols: {headers}")

    out_path = os.path.join(OUT_DIR, f"harvest_{species_name}_{year}.csv")
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(data_rows)
    log(f"  → {out_path}")
    return len(data_rows)


async def main():
    target_cd = sys.argv[1].upper() if len(sys.argv) >= 2 else None
    target_yr = sys.argv[2] if len(sys.argv) >= 3 else None

    runs = [
        (cd, nm, yr)
        for cd, nm in SPECIES
        for yr in YEARS
        if (not target_cd or cd == target_cd)
        and (not target_yr or yr == target_yr)
    ]

    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        total = 0
        for cd, nm, yr in runs:
            try:
                total += await fetch_one(page, cd, nm, yr)
            except Exception as e:
                log(f"  ERROR {nm} {yr}: {e}")

        await browser.close()

    log(f"\n✅ Done. {total} total rows across {len(runs)} fetches.")
    files = sorted(f for f in os.listdir(OUT_DIR) if f.startswith('harvest_') and f.endswith('.csv'))
    log(f"Output files: {files}")


if __name__ == '__main__':
    asyncio.run(main())
