# Opens the live demo in a headless browser so Streamlit Community Cloud doesn't put it to sleep.
# Author: Syed Ali Haider
# A plain HTTP request doesn't count as a visit; the app needs a real browser session.
# Run by .github/workflows/keep-awake.yml. Loading the page makes no Azure calls.

import os
import re

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

APP_URL = os.getenv("APP_URL", "https://azure-ai-smart-invoice.streamlit.app/")
APP_HEADING = "Smart Invoice & Receipt Processor"

with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.goto(APP_URL, wait_until="domcontentloaded", timeout=60_000)

    wake_button = page.get_by_role("button", name=re.compile("get this app back up", re.IGNORECASE))
    try:
        wake_button.wait_for(timeout=15_000)
        wake_button.click()
        print("App was asleep; wake-up requested.")
    except PlaywrightTimeout:
        print("App was already awake.")

    page.frame_locator('iframe[title="streamlitApp"]').get_by_text(APP_HEADING).wait_for(timeout=180_000)
    print(f"App is up: {APP_URL}")
    browser.close()
