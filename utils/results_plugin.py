"""Pytest plugin that records every run as a JSON file under reports/history/.

The dashboard (``python -m utils.dashboard``) is built from these files, so
this module is deliberately small and dependency free: it only uses pytest's
public hook API, the standard library and ``utils.config``.

How it works
------------
* ``pytest_runtest_makereport`` (runs in every process, including xdist
  workers) attaches the test's markers and any failure artifacts recorded by
  ``tests/conftest.py`` (``item._artifacts``) to the report's
  ``user_properties``. That list is part of the report that xdist serialises
  back to the controller, so nothing is lost across processes.
* Outcomes: ``passed``, ``failed`` (the test body raised), ``error`` (setup or
  teardown raised) and ``skipped``. An expected failure (``xfail``) is
  recorded as skipped and an unexpected pass as passed, which is how pytest
  itself reports them. When several phases fail, the first one is kept: it is
  the root cause, and a teardown error after a setup error adds nothing.
* ``ResultsRecorder`` is registered only in the controlling process (the one
  without ``workerinput``). Under ``pytest -n``, xdist forwards every worker's
  ``pytest_runtest_logreport`` call to the controller, so the controller sees
  every phase of every test and can write a single, complete run file at
  session end. Workers write nothing, which is what makes the plugin xdist safe
  without any shard merging.
* One JSON file per pytest invocation. Separate invocations that belong to the
  same logical run (for example the UI and API jobs of one CI workflow) share a
  ``run_group`` and are merged by the dashboard generator, not here.

Switches
--------
``TESTVERSE_RESULTS=0``      disable recording for this run.
``TESTVERSE_HISTORY_DIR``    where to write (default ``reports/history``).
``TESTVERSE_RUN_GROUP``      group id for merging (default ``GITHUB_RUN_ID``
                             when set, otherwise the run id of this file).
``TESTVERSE_SUITE``          label for this invocation (default derived from
                             the paths given on the command line: ui, api, full).

Nothing is written for ``--collect-only``, for a session that ran no tests, or
for a session that was interrupted (Ctrl-C): a partial run is not a result.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from utils.config import Config

SCHEMA_VERSION = 1

# A conftest can set this to keep a run out of the history, e.g. the framework's
# own unit tests under tests_framework/ (they are not application results).
DISABLED_KEY = pytest.StashKey[bool]()
RUN_FILE_KEY = pytest.StashKey[str]()

_TRUTHY = {"1", "true", "yes", "on", "y"}

# pytest's own marks carry no suite semantics; only user markers such as
# smoke / regression / ui / api are worth grouping by in the dashboard.
_BUILTIN_MARKS = {"parametrize", "usefixtures", "filterwarnings", "skip", "skipif", "xfail"}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _is_worker(config) -> bool:
    return hasattr(config, "workerinput")


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    return default if value is None or not value.strip() else value.strip()


def history_dir() -> Path:
    custom = _env("TESTVERSE_HISTORY_DIR")
    return Path(custom) if custom else Config.REPORTS_DIR / "history"


def _git(*args: str) -> str:
    try:
        out = subprocess.run(
            ["git", *args],
            cwd=str(Config.ROOT_DIR),
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def git_info() -> dict:
    """Commit and branch, preferring what CI tells us over a local git call."""
    sha = _env("GITHUB_SHA") or _git("rev-parse", "HEAD")
    branch = (
        _env("GITHUB_HEAD_REF")
        or _env("GITHUB_REF_NAME")
        or _git("rev-parse", "--abbrev-ref", "HEAD")
    )
    return {"sha": sha, "branch": branch}


def ci_info() -> dict:
    if not _env("GITHUB_ACTIONS"):
        return {"provider": None}
    server = _env("GITHUB_SERVER_URL", "https://github.com")
    repo = _env("GITHUB_REPOSITORY")
    run_id = _env("GITHUB_RUN_ID")
    return {
        "provider": "github",
        "run_id": run_id,
        "run_number": _env("GITHUB_RUN_NUMBER"),
        "run_attempt": _env("GITHUB_RUN_ATTEMPT"),
        "event": _env("GITHUB_EVENT_NAME"),
        "url": f"{server}/{repo}/actions/runs/{run_id}" if repo and run_id else "",
    }


def relative_to_root(path: str) -> str:
    """Artifact paths are stored relative to the repo so they survive a move."""
    try:
        rel = Path(path).resolve().relative_to(Config.ROOT_DIR)
    except (ValueError, OSError):
        return str(path).replace("\\", "/")
    return rel.as_posix()


def _marker_names(item) -> list:
    """The item's user markers (closest first), without pytest's built-ins."""
    names = []
    for marker in item.iter_markers():
        if marker.name not in names and marker.name not in _BUILTIN_MARKS:
            names.append(marker.name)
    return names


def failure_message(report) -> str:
    """One-line summary of why a phase failed, kept short for the dashboard."""
    longrepr = getattr(report, "longrepr", None)
    if longrepr is None:
        return ""
    crash = getattr(longrepr, "reprcrash", None)
    message = getattr(crash, "message", None)
    if not message:
        if isinstance(longrepr, tuple) and len(longrepr) == 3:  # skip reports
            message = str(longrepr[2])
        else:
            message = str(longrepr)
    message = message.strip()
    first_line = message.splitlines()[0] if message else ""
    return first_line[:300]


def failure_details(report, limit: int = 3000) -> str:
    text = getattr(report, "longreprtext", "") or ""
    if len(text) > limit:
        text = text[: limit - 1] + "..."
    return text


def classify_layer(nodeid: str, markers: list) -> str:
    if "api" in markers:
        return "api"
    if "ui" in markers:
        return "ui"
    head = nodeid.split("/", 1)[0].split("::", 1)[0]
    return {"api": "api", "tests": "ui"}.get(head, "other")


def classify_area(nodeid: str) -> str:
    """tests/test_checkout.py::test_x -> checkout ; api/test_posts_api.py -> posts."""
    module = nodeid.split("::", 1)[0]
    stem = Path(module).stem
    if stem.startswith("test_"):
        stem = stem[5:]
    for suffix in ("_api", "_tests", "_test"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
    return stem or module


def suite_label(config) -> str:
    custom = _env("TESTVERSE_SUITE")
    if custom:
        return custom
    heads = set()
    for arg in config.args:
        rel = str(arg).replace("\\", "/")
        try:
            rel = Path(arg).resolve().relative_to(Config.ROOT_DIR).as_posix()
        except (ValueError, OSError):
            pass
        heads.add(rel.split("/", 1)[0].split("::", 1)[0])
    if heads == {"api"}:
        return "api"
    if heads == {"tests"}:
        return "ui"
    return "full"


def _worker_count(config, seen_workers: set) -> int:
    count = getattr(config.option, "numprocesses", None)
    if isinstance(count, int) and count > 0:
        return count
    return len(seen_workers) or 1


# ---------------------------------------------------------------------------
# hooks that run in every process (controller and workers)
# ---------------------------------------------------------------------------
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    try:
        report.user_properties.append(("testverse_markers", _marker_names(item)))
        if report.when == "teardown":
            artifacts = [relative_to_root(p) for p in getattr(item, "_artifacts", [])]
            report.user_properties.append(("testverse_artifacts", artifacts))
    except Exception:  # noqa: BLE001 - recording must never break a test
        pass


def pytest_configure(config):
    if _is_worker(config):
        return
    if config.pluginmanager.hasplugin("testverse-results-recorder"):
        return
    config.pluginmanager.register(ResultsRecorder(config), "testverse-results-recorder")


# ---------------------------------------------------------------------------
# the recorder - controller only
# ---------------------------------------------------------------------------
class ResultsRecorder:
    def __init__(self, config):
        self.config = config
        self.started = time.time()
        self.started_at = datetime.now(timezone.utc)
        self.run_id = f"{self.started_at.strftime('%Y%m%dT%H%M%S')}Z-{os.getpid()}"
        self.records: dict = {}
        self.order: list = []
        self.seen_workers: set = set()

    # -- collecting -------------------------------------------------------
    def pytest_runtest_logreport(self, report):
        props = dict(getattr(report, "user_properties", []) or [])
        record = self.records.get(report.nodeid)
        if record is None:
            markers = list(props.get("testverse_markers", []))
            location = getattr(report, "location", None) or ("", None, "")
            record = {
                "nodeid": report.nodeid,
                "name": report.nodeid.rsplit("::", 1)[-1],
                "module": str(location[0] or "").replace("\\", "/"),
                "area": classify_area(report.nodeid),
                "layer": classify_layer(report.nodeid, markers),
                "markers": markers,
                "outcome": "passed",
                "phase": None,
                "duration": 0.0,
                "call_duration": None,
                "message": "",
                "details": "",
                "artifacts": [],
                "worker": None,
            }
            self.records[report.nodeid] = record
            self.order.append(report.nodeid)

        node = getattr(report, "node", None)  # set by xdist on the controller
        if node is not None:
            worker = getattr(getattr(node, "gateway", None), "id", None)
            if worker:
                record["worker"] = worker
                self.seen_workers.add(worker)

        record["duration"] += float(getattr(report, "duration", 0.0) or 0.0)
        if report.when == "call":
            record["call_duration"] = float(report.duration)

        if report.failed:
            # Phases arrive in order (setup, call, teardown), so the first
            # failure seen is the root cause; later ones are consequences.
            if record["outcome"] not in ("failed", "error"):
                record["outcome"] = "failed" if report.when == "call" else "error"
                record["phase"] = report.when
                record["message"] = failure_message(report)
                record["details"] = failure_details(report)
        elif report.skipped and record["outcome"] == "passed":
            record["outcome"] = "skipped"
            record["phase"] = report.when
            record["message"] = failure_message(report)

        for artifact in props.get("testverse_artifacts", []):
            if artifact not in record["artifacts"]:
                record["artifacts"].append(artifact)

    # -- writing ----------------------------------------------------------
    def enabled(self) -> bool:
        if self.config.stash.get(DISABLED_KEY, False):
            return False
        if _env("TESTVERSE_RESULTS", "1").lower() not in _TRUTHY:
            return False
        if self.config.getoption("collectonly", False):
            return False
        return bool(self.records)

    def build_run(self, exitstatus: int) -> dict:
        tests = [self.records[nodeid] for nodeid in self.order]
        summary = {"total": len(tests), "passed": 0, "failed": 0, "error": 0, "skipped": 0}
        for record in tests:
            summary[record["outcome"]] += 1
        group = _env("TESTVERSE_RUN_GROUP") or _env("GITHUB_RUN_ID") or self.run_id
        return {
            "schema": SCHEMA_VERSION,
            "run_id": self.run_id,
            "run_group": group,
            "suite": suite_label(self.config),
            "timestamp": self.started_at.isoformat(timespec="seconds"),
            "wall_seconds": round(time.time() - self.started, 3),
            "exit_status": int(exitstatus),
            "git": git_info(),
            "ci": ci_info(),
            "browser": Config.BROWSER,
            "headless": Config.HEADLESS,
            "workers": _worker_count(self.config, self.seen_workers),
            "python": platform.python_version(),
            "platform": platform.system().lower(),
            "pytest": pytest.__version__,
            "config": Config.as_dict(),
            "summary": summary,
            "tests": tests,
        }

    def pytest_sessionfinish(self, session, exitstatus):
        if not self.enabled() or exitstatus == pytest.ExitCode.INTERRUPTED:
            return
        try:
            directory = history_dir()
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / f"{self.run_id}.json"
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(self.build_run(int(exitstatus)), handle, indent=1)
            self.config.stash[RUN_FILE_KEY] = str(path)
        except Exception as exc:  # noqa: BLE001 - never fail the run over a report
            sys.stderr.write(f"results_plugin: could not write run file: {exc}\n")

    def pytest_terminal_summary(self, terminalreporter):
        path = self.config.stash.get(RUN_FILE_KEY, None)
        if path:
            terminalreporter.write_sep("-", f"Run recorded: {path}")
