import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import pytest
from playwright.sync_api import sync_playwright
from datetime import datetime
from utils.config import BASE_URL


@pytest.fixture(scope="function")
def browser_page(request):

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=False, slow_mo=1000)

        context = browser.new_context()

        page = context.new_page()

        page.goto(BASE_URL)

        yield page

        if request.node.rep_call.failed:

            if not os.path.exists("screenshots"):
                os.makedirs("screenshots")

            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

            test_name = request.node.name

            screenshot_path = f"screenshots/{test_name}_{timestamp}.png"

            page.screenshot(path=screenshot_path)

        context.close()
        browser.close()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):

    outcome = yield
    rep = outcome.get_result()

    setattr(item, "rep_" + rep.when, rep)