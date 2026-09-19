"""Pytest fixtures for the UI layer.

Fixture scoping (deliberate - see "Design decisions" in the README):

    playwright  -> session : one Playwright driver process per pytest worker
    browser     -> session : launching a browser is the expensive part
    context     -> function: a fresh, isolated cookie/storage jar per test
    page        -> function: one tab per test

Under ``pytest -n auto`` every xdist worker is its own process, so each worker
gets its own browser and no two tests ever share a context. That is what makes
parallel execution safe here.

Failure artifacts (screenshot / trace / video) are controlled by the
SCREENSHOT, TRACE and VIDEO environment variables, each accepting
``on``, ``off`` or ``retain-on-failure`` (the default).
"""

import os
import re
import shutil
from datetime import datetime

import pytest
from playwright.sync_api import sync_playwright

from utils.config import Config

# Where each kind of artifact lands. Directories are created lazily, only when
# an artifact is actually kept.
_ARTIFACT_DIRS = {
    "screenshot": Config.SCREENSHOTS_DIR,
    "trace": Config.TRACES_DIR,
    "video": Config.VIDEOS_DIR,
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _worker_id(config) -> str:
    """Returns the xdist worker id (gw0, gw1, ...) or "master" when serial."""
    return getattr(config, "workerinput", {}).get("workerid", "master")


def _safe_name(node_name: str) -> str:
    """Turns a pytest node name into something every filesystem accepts."""
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", node_name).strip("_")[:120]


def _artifact_path(request, kind: str, extension: str):
    directory = _ARTIFACT_DIRS[kind]
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    worker = _worker_id(request.config)
    return directory / f"{_safe_name(request.node.name)}_{worker}_{stamp}{extension}"


def _test_failed(item) -> bool:
    """True when setup or the test body failed (reports set by the hook below)."""
    for phase in ("setup", "call"):
        report = getattr(item, "rep_" + phase, None)
        if report is not None and report.failed:
            return True
    return False


def _should_keep(mode: str, failed: bool) -> bool:
    if mode == "on":
        return True
    if mode == "off":
        return False
    return failed  # retain-on-failure


def _record(item, path) -> None:
    """Remembers an artifact so the HTML report and the run record can link to it."""
    if not hasattr(item, "_artifacts"):
        item._artifacts = []
    item._artifacts.append(str(path))


# ---------------------------------------------------------------------------
# session scope - the expensive bits, created once per worker
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def playwright():
    Config.validate()
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def browser(playwright):
    browser_type = getattr(playwright, Config.BROWSER)
    instance = browser_type.launch(headless=Config.HEADLESS, slow_mo=Config.SLOW_MO)
    yield instance
    instance.close()


# ---------------------------------------------------------------------------
# function scope - isolation per test
# ---------------------------------------------------------------------------
@pytest.fixture(scope="function")
def context(browser, request):
    context_args = {
        "base_url": Config.BASE_URL,
        "viewport": {
            "width": Config.VIEWPORT_WIDTH,
            "height": Config.VIEWPORT_HEIGHT,
        },
    }

    video_wanted = Config.VIDEO != "off"
    if video_wanted:
        # Playwright decides on recording before the context exists, so we
        # always record and discard the file afterwards when the test passed
        # and the mode is retain-on-failure. One scratch directory per xdist
        # worker keeps parallel workers out of each other's recordings.
        raw_video_dir = Config.VIDEOS_DIR / "_raw" / _worker_id(request.config)
        raw_video_dir.mkdir(parents=True, exist_ok=True)
        context_args["record_video_dir"] = str(raw_video_dir)
        context_args["record_video_size"] = {
            "width": Config.VIEWPORT_WIDTH,
            "height": Config.VIEWPORT_HEIGHT,
        }

    browser_context = browser.new_context(**context_args)
    browser_context.set_default_timeout(Config.TIMEOUT)
    browser_context.set_default_navigation_timeout(Config.NAVIGATION_TIMEOUT)

    tracing_started = False
    if Config.TRACE != "off":
        browser_context.tracing.start(screenshots=True, snapshots=True, sources=True)
        tracing_started = True

    yield browser_context

    failed = _test_failed(request.node)

    if tracing_started:
        if _should_keep(Config.TRACE, failed):
            trace_path = _artifact_path(request, "trace", ".zip")
            browser_context.tracing.stop(path=str(trace_path))
            _record(request.node, trace_path)
        else:
            browser_context.tracing.stop()

    videos = [page_obj.video for page_obj in browser_context.pages if page_obj.video]
    browser_context.close()  # closing flushes the video files to disk

    if video_wanted:
        keep = _should_keep(Config.VIDEO, failed)
        for index, video in enumerate(videos):
            try:
                if keep:
                    suffix = "" if index == 0 else "_" + str(index)
                    target = _artifact_path(request, "video", suffix + ".webm")
                    video.save_as(str(target))
                    _record(request.node, target)
                video.delete()
            except Exception:  # noqa: BLE001 - cleanup must never fail a test
                pass


@pytest.fixture(scope="function")
def page(context, request):
    new_page = context.new_page()
    yield new_page

    if _should_keep(Config.SCREENSHOT, _test_failed(request.node)):
        try:
            screenshot_path = _artifact_path(request, "screenshot", ".png")
            new_page.screenshot(path=str(screenshot_path), full_page=True)
            _record(request.node, screenshot_path)
        except Exception:  # noqa: BLE001 - a dead page must not mask the failure
            pass


@pytest.fixture(scope="function")
def browser_page(page):
    """Original fixture name, kept so the existing tests need no changes.

    Opens the application under test and hands back a ready page.
    """
    page.goto(Config.BASE_URL, wait_until="domcontentloaded")
    return page


# ---------------------------------------------------------------------------
# session cleanup and hooks
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def _cleanup_raw_video_dir(request):
    """Removes this worker's scratch directory for raw Playwright videos."""
    yield
    shutil.rmtree(
        Config.VIDEOS_DIR / "_raw" / _worker_id(request.config), ignore_errors=True
    )
    try:
        (Config.VIDEOS_DIR / "_raw").rmdir()  # only succeeds once it is empty
    except OSError:
        pass


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Exposes each phase report to fixtures as item.rep_setup / item.rep_call.

    Also links any captured artifact into the pytest-html report.
    """
    outcome = yield
    rep = outcome.get_result()

    setattr(item, "rep_" + rep.when, rep)

    if rep.when != "teardown":
        return

    artifacts = getattr(item, "_artifacts", [])
    if not artifacts:
        return

    try:
        html_plugin = item.config.pluginmanager.getplugin("html")
        if html_plugin is None:
            return
        extras = list(getattr(rep, "extras", []))
        for artifact in artifacts:
            relative = os.path.relpath(artifact, Config.REPORTS_DIR).replace("\\", "/")
            extras.append(
                html_plugin.extras.url(relative, name=os.path.basename(artifact))
            )
        rep.extras = extras
    except Exception:  # noqa: BLE001 - reporting must never break a run
        pass
