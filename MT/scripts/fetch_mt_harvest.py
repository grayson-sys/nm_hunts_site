#!/usr/bin/env python3
"""
Fetch Montana harvest data for all species from myfwp.mt.gov using Playwright.

The FWP harvest search tool is a Struts2 jQuery app. Data is loaded by publishing
a jQuery topic 'popReportResultsDiv' after form fields are filled. No submit button
exists — the trigger is the JS topic system.

Usage:
    python3 fetch_mt_harvest.py            # all species, 2023+2024
    python3 fetch_mt_harvest.py EL 2024   # single species+year

Requirements:
    pip install playwright
    playwright install chromium
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
YEARS = ["2023", "2024"]


def log(msg):
    print(msg, flush=True)


async def fetch_harvest(page, species_cd, species_name, year):
    log(f"\n--- {species_name} {year} ---")

    await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30000)

    # Wait for the Struts2 jQuery plugin to load the inner form div
    try:
        await page.wait_for_selector('#speciesCd', timeout=20000)
    except Exception:
        log(f"  TIMEOUT: #speciesCd never appeared (JS may not have loaded)")
        return 0

    # Select species — triggers year dropdown population via AJAX
    log(f"  Selecting species={species_cd}")
    await page.select_option('#speciesCd', species_cd)

    # Wait for year option to appear
    try:
        await page.wait_for_function(
            f"document.querySelector('#licYearStart option[value=\"{year}\"]') !== null",
            timeout=15000
        )
    except Exception:
        log(f"  TIMEOUT: year {year} never appeared in #licYearStart")
        return 0

    await page.select_option('#licYearStart', year)
    await page.select_option('#licYearEnd', year)
    log(f"  Year={year}")

    # Wait for district dropdown to populate
    try:
        await page.wait_for_function(
            "document.querySelector('#districtId option[value=\"ALL\"]') !== null",
            timeout=15000
        )
    except Exception:
        log(f"  TIMEOUT: district dropdown never populated")
        return 0

    await page.select_option('#districtId', 'ALL')
    log(f"  District=ALL — publishing popReportResultsDiv topic")

    # No submit button exists. Trigger the results by publishing the Struts2 jQuery topic.
    # The reportResultsDiv container listens for 'popReportResultsDiv' and reloads
    # via POST to reportResultsDiv_input.action with harvestEstimatesSearchForm data.
    await page.evaluate("""
        () => {
            // Struts2 jQuery topic publish — triggers the results container reload
            if (typeof jQuery !== 'undefined' && jQuery.publish) {
                jQuery.publish('popReportResultsDiv');
            } else if (typeof jQuery !== 'undefined') {
                // fallback: direct form submit
                var form = document.getElementById('harvestEstimatesSearchForm');
                if (form) jQuery(form).submit();
            }
        }
    """)

    # Wait for table rows to appear in the results div
    try:
        await page.wait_for_function(
            "document.querySelectorAll('#reportResultsDiv tbody tr td').length > 0",
            timeout=25000
        )
    except Exception:
        log(f"  No data rows returned (topic may not have triggered)")
        # Debug: show what's in the results div
        content = await page.inner_html('#reportResultsDiv')
        log(f"  reportResultsDiv content (first 300): {content[:300]}")
        return 0

    # Extract table data
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
    log(f"  Got {len(data_rows)} rows | cols: {headers}")

    out_path = os.path.join(OUT_DIR, f"harvest_{species_name}_{year}.csv")
    with open(out_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(data_rows)
    log(f"  Saved → {out_path}")
    return len(data_rows)


async def main():
    target_species = sys.argv[1].upper() if len(sys.argv) >= 2 else None
    target_year = sys.argv[2] if len(sys.argv) >= 3 else None

    species_list = [(cd, nm) for cd, nm in SPECIES if not target_species or cd == target_species]
    year_list = [y for y in YEARS if not target_year or y == target_year]

    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        total = 0
        for species_cd, species_name in species_list:
            for year in year_list:
                try:
                    n = await fetch_harvest(page, species_cd, species_name, year)
                    total += n
                except Exception as e:
                    log(f"  ERROR {species_name} {year}: {e}")

        await browser.close()
        log(f"\n✅ Done. Total rows fetched: {total}")
        files = [f for f in os.listdir(OUT_DIR) if f.startswith('harvest_') and f.endswith('.csv')]
        log(f"Output files: {sorted(files)}")


if __name__ == '__main__':
    asyncio.run(main())
