"""Small builders for synthetic run data used across the framework tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from utils.results_plugin import classify_area

START = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)


def make_record(nodeid: str, outcome: str = "passed", duration: float = 1.0, **extra) -> dict:
    layer = "api" if nodeid.startswith("api/") else "ui"
    record = {
        "nodeid": nodeid,
        "name": nodeid.rsplit("::", 1)[-1],
        "module": nodeid.split("::", 1)[0],
        "area": classify_area(nodeid),
        "layer": layer,
        "markers": [layer, "regression"],
        "outcome": outcome,
        "phase": "call" if outcome == "failed" else None,
        "duration": duration,
        "call_duration": duration,
        "message": "AssertionError: boom" if outcome == "failed" else "",
        "details": "",
        "artifacts": [],
        "worker": None,
    }
    record.update(extra)
    return record


def shard(run_id: str, tests: list, *, group: str = None, index: int = 0, browser: str = "chromium", suite: str = "ui", wall: float = 10.0, **extra) -> dict:
    summary = {"total": len(tests), "passed": 0, "failed": 0, "error": 0, "skipped": 0}
    for test in tests:
        summary[test["outcome"]] += 1
    data = {
        "schema": 1,
        "run_id": run_id,
        "run_group": group or run_id,
        "suite": suite,
        "timestamp": (START + timedelta(hours=index)).isoformat(timespec="seconds"),
        "wall_seconds": wall,
        "exit_status": 1 if summary["failed"] or summary["error"] else 0,
        "git": {"sha": "abc1234def", "branch": "main"},
        "ci": {"provider": None},
        "browser": browser,
        "headless": True,
        "workers": 1,
        "config": {},
        "summary": summary,
        "tests": tests,
    }
    data.update(extra)
    return data


def run_sequence(outcomes_by_test: dict, durations: dict = None) -> list:
    """Builds one run per column: {nodeid: "PFPF..."} where P/F/E/S are outcomes."""
    letters = {"P": "passed", "F": "failed", "E": "error", "S": "skipped"}
    length = max(len(v) for v in outcomes_by_test.values())
    runs = []
    for index in range(length):
        tests = []
        for nodeid, pattern in outcomes_by_test.items():
            if index >= len(pattern) or pattern[index] == "-":
                continue  # test absent from this run
            duration = (durations or {}).get(nodeid, [1.0] * length)[index]
            tests.append(make_record(nodeid, letters[pattern[index]], duration))
        runs.append(shard(f"run-{index:02d}", tests, index=index))
    return runs
