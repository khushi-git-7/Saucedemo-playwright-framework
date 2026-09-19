"""Metric computations for the dashboard. Pure functions over merged runs.

Definitions (these are the rules the dashboard shows in its tooltips):

* pass rate      = passed / (passed + failed + error) * 100. Skipped tests are
                   not executed, so they sit outside the denominator.
* p50 / p95      = nearest-rank percentiles of a test's total duration
                   (setup + call + teardown) across the runs it appeared in.
* flaky test     = within the last FLAKY_WINDOW runs it appeared in, the
                   outcome flipped between pass and fail at least FLAKY_MIN_FLIPS
                   times. Skipped runs are ignored (no observation). A single
                   flip is a regression or a fix, not flakiness.
"""

from __future__ import annotations

import math
from statistics import median

FLAKY_WINDOW = 10
FLAKY_MIN_FLIPS = 2
OUTCOMES = ("passed", "failed", "error", "skipped")
FAILING = ("failed", "error")


# ---------------------------------------------------------------------------
# basic statistics
# ---------------------------------------------------------------------------
def percentile(values, p: float):
    """Nearest-rank percentile; returns None for an empty input."""
    data = sorted(v for v in values if v is not None)
    if not data:
        return None
    if p <= 0:
        return data[0]
    if p >= 100:
        return data[-1]
    rank = max(1, math.ceil(p / 100.0 * len(data)))
    return data[rank - 1]


def pass_rate(summary: dict):
    executed = summary.get("passed", 0) + summary.get("failed", 0) + summary.get("error", 0)
    if executed == 0:
        return None
    return round(100.0 * summary.get("passed", 0) / executed, 1)


def _is_pass(outcome: str) -> bool:
    return outcome == "passed"


def _is_fail(outcome: str) -> bool:
    return outcome in FAILING


# ---------------------------------------------------------------------------
# per-run summaries
# ---------------------------------------------------------------------------
def run_stats(run: dict) -> dict:
    tests = run.get("tests", [])
    summary = run.get("summary") or {}
    durations = [float(t.get("duration") or 0.0) for t in tests]
    total_test_time = sum(durations)
    return {
        "run_id": run["run_id"],
        "timestamp": run["timestamp"],
        "total": summary.get("total", len(tests)),
        "passed": summary.get("passed", 0),
        "failed": summary.get("failed", 0),
        "error": summary.get("error", 0),
        "skipped": summary.get("skipped", 0),
        "pass_rate": pass_rate(summary),
        "median_duration": median(durations) if durations else None,
        "p95_duration": percentile(durations, 95),
        "test_time": total_test_time,
        # Wall time is what the run actually took; fall back to the sum of test
        # durations for hand-made or legacy run files without it.
        "wall_seconds": float(run.get("wall_seconds") or total_test_time),
    }


def delta(current, previous):
    """current - previous, or None when either side has no value."""
    if current is None or previous is None:
        return None
    return current - previous


# ---------------------------------------------------------------------------
# per-test history
# ---------------------------------------------------------------------------
def test_histories(runs: list) -> dict:
    """nodeid -> list of {run_index, outcome, duration, ...} in run order."""
    histories: dict = {}
    for index, run in enumerate(runs):
        for test in run.get("tests", []):
            histories.setdefault(test["nodeid"], []).append(
                {
                    "run_index": index,
                    "run_id": run["run_id"],
                    "outcome": test.get("outcome", "error"),
                    "duration": float(test.get("duration") or 0.0),
                    "layer": test.get("layer", "other"),
                    "area": test.get("area", ""),
                    "markers": list(test.get("markers", [])),
                }
            )
    return histories


def count_flips(outcomes: list) -> int:
    """Number of pass<->fail transitions, ignoring skipped/unknown outcomes."""
    observed = [o for o in outcomes if _is_pass(o) or _is_fail(o)]
    flips = 0
    for previous, current in zip(observed, observed[1:]):
        if _is_pass(previous) != _is_pass(current):
            flips += 1
    return flips


def flakiness(runs: list, window: int = FLAKY_WINDOW, min_flips: int = FLAKY_MIN_FLIPS) -> list:
    """Tests whose outcome changed at least once in the window, most flips first.

    Each entry: nodeid, flips, flaky (flips >= min_flips), outcomes (the window,
    oldest first, as (run_index, outcome) pairs), last_outcome, fail_count.
    """
    results = []
    for nodeid, history in test_histories(runs).items():
        recent = history[-window:]
        outcomes = [entry["outcome"] for entry in recent]
        flips = count_flips(outcomes)
        if flips == 0:
            continue
        results.append(
            {
                "nodeid": nodeid,
                "layer": recent[-1]["layer"],
                "flips": flips,
                "flaky": flips >= min_flips,
                "runs_seen": len(recent),
                "fail_count": sum(1 for o in outcomes if _is_fail(o)),
                "outcomes": [(entry["run_index"], entry["outcome"]) for entry in recent],
                "last_outcome": outcomes[-1],
            }
        )
    results.sort(key=lambda r: (-r["flips"], -r["fail_count"], r["nodeid"]))
    return results


def slowest_tests(runs: list, limit: int = 10) -> list:
    """Per-test p50 / p95 / max duration across history, slowest p95 first."""
    rows = []
    for nodeid, history in test_histories(runs).items():
        durations = [entry["duration"] for entry in history]
        rows.append(
            {
                "nodeid": nodeid,
                "layer": history[-1]["layer"],
                "runs": len(durations),
                "p50": percentile(durations, 50),
                "p95": percentile(durations, 95),
                "max": max(durations),
                "last": durations[-1],
            }
        )
    rows.sort(key=lambda r: (-(r["p95"] or 0), r["nodeid"]))
    return rows[:limit] if limit else rows


# ---------------------------------------------------------------------------
# breakdowns of the latest run
# ---------------------------------------------------------------------------
def breakdown(run: dict, by: str, order: list = None) -> list:
    """Pass rate of one run grouped by 'markers', 'area' or 'layer'.

    Returns rows: {name, total, passed, failed, error, skipped, pass_rate}.
    A test with several markers is counted under each of them.
    """
    groups: dict = {}
    for test in run.get("tests", []):
        keys = test.get("markers", []) if by == "markers" else [test.get(by, "") or "unknown"]
        for key in keys:
            group = groups.setdefault(key, {"name": key, "total": 0, "passed": 0, "failed": 0, "error": 0, "skipped": 0})
            group["total"] += 1
            outcome = test.get("outcome", "error")
            group[outcome if outcome in OUTCOMES else "error"] += 1
    rows = list(groups.values())
    for row in rows:
        row["pass_rate"] = pass_rate(row)
    if order:
        rank = {name: i for i, name in enumerate(order)}
        rows.sort(key=lambda r: (rank.get(r["name"], len(rank)), r["name"]))
    else:
        rows.sort(key=lambda r: r["name"])
    return rows


def layer_p95(run: dict, layer: str):
    """p95 of test durations for one layer of a run; None when the layer is absent."""
    durations = [float(t.get("duration") or 0.0) for t in run.get("tests", []) if t.get("layer") == layer]
    return percentile(durations, 95)


def failures(run: dict) -> list:
    """Tests of a run whose outcome is failed or error, in run order."""
    return [t for t in run.get("tests", []) if _is_fail(t.get("outcome", ""))]


def outcome_changes(current: dict, previous: dict) -> dict:
    """Tests that started failing / got fixed between two runs."""
    prev = {t["nodeid"]: t.get("outcome") for t in previous.get("tests", [])}
    newly_failing, fixed = [], []
    for test in current.get("tests", []):
        before = prev.get(test["nodeid"])
        now = test.get("outcome")
        if _is_fail(now) and before is not None and _is_pass(before):
            newly_failing.append(test["nodeid"])
        elif _is_pass(now) and before is not None and _is_fail(before):
            fixed.append(test["nodeid"])
    return {"newly_failing": newly_failing, "fixed": fixed}


def consecutive_failures(runs: list) -> list:
    """(nodeid, streak) for tests failing in the latest N consecutive runs."""
    streaks = []
    for nodeid, history in test_histories(runs).items():
        streak = 0
        for entry in reversed(history):
            if _is_fail(entry["outcome"]):
                streak += 1
            elif entry["outcome"] == "skipped":
                continue
            else:
                break
        if streak:
            streaks.append((nodeid, streak))
    streaks.sort(key=lambda s: (-s[1], s[0]))
    return streaks


def green_streak(runs: list) -> int:
    """How many of the latest runs in a row had zero failures."""
    streak = 0
    for run in reversed(runs):
        stats = run_stats(run)
        if stats["failed"] == 0 and stats["error"] == 0 and stats["total"] > 0:
            streak += 1
        else:
            break
    return streak
