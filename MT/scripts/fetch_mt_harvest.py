#!/usr/bin/env python3
"""
Fetch Montana harvest data for all species from myfwp.mt.gov using Playwright.
Outputs CSV files to MT/raw_data/harvest_{species}_{year}.csv
"""
import asyncio
import csv
import os
import sys
from playwright.async_api import async_playwright

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


async def fetch_harvest(page, species_cd, species_name, year):
    print(f"\n--- Fetching {species_name} {year} ---")

    # Navigate fresh each time
    await page.goto(BASE_URL, wait_until="networkidle", timeout=30000)

    # Wait for the form container to load
    await page.wait_for_selector('#speciesCd', timeout=15000)

    # Select species
    await page.select_option('#speciesCd', species_cd)

    # Wait for year dropdowns to populate
    await page.wait_for_function(
        f"document.querySelector('#licYearStart option[value=\"{year}\"]') !== null",
        timeout=15000
    )

    # Select start and end year
    await page.select_option('#licYearStart', year)
    await page.select_option('#licYearEnd', year)

    # Wait for district dropdown to populate
    await page.wait_for_function(
        "document.querySelector('#districtId option[value=\"ALL\"]') !== null",
        timeout=15000
    )

    # Select ALL districts
    await page.select_option('#districtId', 'ALL')

    # Click generate / search button
    await page.click('input[type="submit"], button[type="submit"]')

    # Wait for results table to populate
    try:
        await page.wait_for_function(
            "document.querySelector('#reportResultsDiv tbody tr') !== null",
            timeout=20000
        )
    except Exception:
        print(f"  No data found for {species_name} {year}")
        return 0

    # Extract table data
    rows = await page.evaluate("""
        () => {
            const table = document.querySelector('#reportResultsDiv table');
            if (!table) return [];
            const headers = Array.from(table.querySelectorAll('thead th')).map(th => th.innerText.trim());
            const rows = Array.from(table.querySelectorAll('tbody tr')).map(tr => {
                return Array.from(tr.querySelectorAll('td')).map(td => td.innerText.trim());
            });
            return {headers, rows};
        }
    """)

    if not rows or not rows.get('rows'):
        print(f"  Empty table for {species_name} {year}")
        return 0

    headers = rows['headers']
    data_rows = rows['rows']
    print(f"  Got {len(data_rows)} rows, columns: {headers}")

    out_path = os.path.join(OUT_DIR, f"harvest_{species_name}_{year}.csv")
    with open(out_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(data_rows)

    print(f"  Saved → {out_path}")
    return len(data_rows)


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        total = 0
        for species_cd, species_name in SPECIES:
            for year in YEARS:
                try:
                    n = await fetch_harvest(page, species_cd, species_name, year)
                    total += n
                except Exception as e:
                    print(f"  ERROR {species_name} {year}: {e}")

        await browser.close()
        print(f"\n✅ Done. Total rows fetched: {total}")


if __name__ == '__main__':
    asyncio.run(main())
