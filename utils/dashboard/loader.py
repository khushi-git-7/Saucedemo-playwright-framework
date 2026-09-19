"""Reads run files written by utils/results_plugin.py and merges shards.

A "shard" is one pytest invocation (one JSON file). Shards that share a
``run_group`` - the UI and API jobs of a single CI workflow run, or several
local invocations started with the same ``TESTVERSE_RUN_GROUP`` - are merged
into one logical run so the dashboard compares whole runs, not half runs.
"""

from __future__ import annotations

import json
from pathlib import Path

from utils.dashboard.metrics import OUTCOMES


def load_shards(history_dir: Path) -> list:
    """All valid run files in *history_dir*, oldest first. Bad files are skipped."""
    shards = []
    for path in sorted(Path(history_dir).glob("*.json")):
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict) or "tests" not in data or "timestamp" not in data:
            continue
        data.setdefault("run_id", path.stem)
        data.setdefault("run_group", data["run_id"])
        data["_file"] = path.name
        shards.append(data)
    shards.sort(key=lambda s: (s["timestamp"], s["run_id"]))
    return shards


def _summary(tests: list) -> dict:
    summary = {"total": len(tests), "passed": 0, "failed": 0, "error": 0, "skipped": 0}
    for test in tests:
        summary[test.get("outcome", "error") if test.get("outcome") in OUTCOMES else "error"] += 1
    return summary


def merge_group(shards: list) -> dict:
    """Merges the shards of one run group into a single run dict.

    Rules (mirrored in tests_framework/test_loader.py):
    * timestamp: the earliest shard; wall_seconds: the longest shard (CI jobs run
      in parallel, so the longest one is the wall time of the whole run).
    * tests: the union. The same nodeid from shards with *different* browsers is
      kept as separate tests, suffixed with the browser; the same nodeid from
      shards with the *same* browser is a re-run and the latest shard wins.
    * browser / suite / workers: joined from all shards.
    """
    shards = sorted(shards, key=lambda s: (s["timestamp"], s["run_id"]))
    first = shards[0]

    by_nodeid: dict = {}
    for shard in shards:
        for test in shard.get("tests", []):
            key = test["nodeid"]
            entry = dict(test)
            entry["browser"] = shard.get("browser", "")
            entry["shard"] = shard.get("run_id", "")
            by_nodeid.setdefault(key, []).append(entry)

    merged_tests = []
    for nodeid, entries in by_nodeid.items():
        browsers = {e["browser"] for e in entries}
        if len(entries) == 1:
            merged_tests.append(entries[0])
        elif len(browsers) > 1:
            latest_per_browser = {}
            for entry in entries:  # shards are time ordered, so last wins
                latest_per_browser[entry["browser"]] = entry
            for browser, entry in latest_per_browser.items():
                entry = dict(entry)
                entry["nodeid"] = f"{nodeid} [{browser}]"
                merged_tests.append(entry)
        else:
            merged_tests.append(entries[-1])

    def joined(field: str) -> str:
        values = []
        for shard in shards:
            value = str(shard.get(field, "") or "")
            if value and value not in values:
                values.append(value)
        return ", ".join(values)

    run = {
        "run_id": first["run_group"] if len(shards) > 1 else first["run_id"],
        "run_group": first["run_group"],
        "shards": [s["run_id"] for s in shards],
        "files": [s.get("_file", "") for s in shards],
        "suite": joined("suite"),
        "timestamp": first["timestamp"],
        "wall_seconds": max(float(s.get("wall_seconds", 0) or 0) for s in shards),
        "exit_status": max(int(s.get("exit_status", 0) or 0) for s in shards),
        "git": first.get("git", {}) or {},
        "ci": next((s.get("ci") for s in shards if (s.get("ci") or {}).get("provider")), first.get("ci", {}) or {}),
        "browser": joined("browser"),
        "headless": all(bool(s.get("headless", True)) for s in shards),
        "workers": sum(int(s.get("workers", 1) or 1) for s in shards),
        "python": joined("python"),
        "platform": joined("platform"),
        "config": first.get("config", {}) or {},
        "tests": merged_tests,
    }
    run["summary"] = _summary(merged_tests)
    return run


def merge_runs(shards: list) -> list:
    """Groups shards by run_group and merges each group; oldest run first."""
    groups: dict = {}
    for shard in shards:
        groups.setdefault(shard["run_group"], []).append(shard)
    runs = [merge_group(group) for group in groups.values()]
    runs.sort(key=lambda r: (r["timestamp"], r["run_id"]))
    return runs


def load_runs(history_dir: Path, max_runs: int = 0) -> list:
    """Merged runs from a history folder, oldest first; the newest *max_runs* when > 0."""
    runs = merge_runs(load_shards(history_dir))
    if max_runs and len(runs) > max_runs:
        runs = runs[-max_runs:]
    return runs
