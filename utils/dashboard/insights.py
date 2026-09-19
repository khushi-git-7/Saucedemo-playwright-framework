"""Plain-English insights computed from run history.

Every insight carries the rule that produced it, and the dashboard shows that
rule in a tooltip, so a reader can always tell a signal from a heuristic. Each
insight is a dict: {kind, severity, text, rule}. Severity is one of
"good", "info", "warning", "critical".
"""

from __future__ import annotations

from utils.dashboard import metrics

PASS_RATE_POINTS = 5.0          # points of pass-rate movement worth a sentence
DURATION_CHANGE_RATIO = 0.25    # suite time change worth a sentence
LAYER_P95_RATIO = 0.30          # per-layer p95 change worth a sentence
LAYER_P95_MIN_DELTA = 0.1       # ... and at least this many seconds
SLOW_TEST_SHARE = 0.25          # one test taking this share of test time ...
SLOW_TEST_RATIO = 3.0           # ... and at least this many times the median test
PERSISTENT_FAILURE_RUNS = 3     # consecutive failing runs


def _short(nodeid: str) -> str:
    return nodeid.rsplit("::", 1)[-1]


def _fmt_seconds(value: float) -> str:
    if value is None:
        return "n/a"
    if value < 1:
        return f"{value * 1000:.0f} ms"
    if value < 60:
        return f"{value:.1f} s"
    minutes, seconds = divmod(value, 60)
    return f"{int(minutes)} min {seconds:.0f} s"


def _join(names: list, limit: int = 3) -> str:
    shown = [_short(n) for n in names[:limit]]
    rest = len(names) - len(shown)
    text = ", ".join(shown)
    return f"{text} and {rest} more" if rest > 0 else text


def compute_insights(runs: list, flaky_rows: list = None) -> list:
    if not runs:
        return [
            {
                "kind": "empty",
                "severity": "info",
                "text": "No runs recorded yet. Run the suite once and rebuild the dashboard.",
                "rule": "Shown when reports/history/ contains no run files.",
            }
        ]

    latest = runs[-1]
    previous = runs[-2] if len(runs) > 1 else None
    stats = metrics.run_stats(latest)
    insights = []

    # 1. pass-rate movement vs the previous run, with the tests that drove it
    if previous is not None:
        prev_stats = metrics.run_stats(previous)
        change = metrics.delta(stats["pass_rate"], prev_stats["pass_rate"])
        if change is not None and abs(change) >= PASS_RATE_POINTS:
            moves = metrics.outcome_changes(latest, previous)
            if change < 0:
                driver = moves["newly_failing"]
                text = f"Pass rate dropped {abs(change):.1f} points since the previous run ({prev_stats['pass_rate']:.1f}% to {stats['pass_rate']:.1f}%)"
                if driver:
                    text += f", driven by {len(driver)} newly failing test{'s' if len(driver) != 1 else ''}: {_join(driver)}"
                insights.append({"kind": "pass_rate_drop", "severity": "critical", "text": text + ".", "rule": f"Pass rate moved by at least {PASS_RATE_POINTS:g} points between the last two runs. Drivers are tests that passed in the previous run and fail now."})
            else:
                driver = moves["fixed"]
                text = f"Pass rate recovered {change:.1f} points since the previous run ({prev_stats['pass_rate']:.1f}% to {stats['pass_rate']:.1f}%)"
                if driver:
                    text += f"; fixed: {_join(driver)}"
                insights.append({"kind": "pass_rate_gain", "severity": "good", "text": text + ".", "rule": f"Pass rate moved by at least {PASS_RATE_POINTS:g} points between the last two runs. Fixed tests failed in the previous run and pass now."})
        else:
            moves = metrics.outcome_changes(latest, previous)
            if moves["newly_failing"]:
                insights.append({"kind": "new_failures", "severity": "warning", "text": f"{len(moves['newly_failing'])} test{'s' if len(moves['newly_failing']) != 1 else ''} started failing in the latest run: {_join(moves['newly_failing'])}.", "rule": "Tests that passed in the previous run and fail in the latest one."})
            if moves["fixed"]:
                insights.append({"kind": "fixed", "severity": "good", "text": f"{len(moves['fixed'])} test{'s' if len(moves['fixed']) != 1 else ''} recovered in the latest run: {_join(moves['fixed'])}.", "rule": "Tests that failed in the previous run and pass in the latest one."})

    # 2. flaky tests
    flaky_rows = flaky_rows if flaky_rows is not None else metrics.flakiness(runs)
    for row in [r for r in flaky_rows if r["flaky"]][:3]:
        insights.append({"kind": "flaky", "severity": "warning", "text": f"{_short(row['nodeid'])} has flipped {row['flips']} times in the last {row['runs_seen']} runs it appeared in ({row['fail_count']} failure{'s' if row['fail_count'] != 1 else ''}); treat its result with suspicion.", "rule": f"A test is flaky when its outcome flipped between pass and fail at least {metrics.FLAKY_MIN_FLIPS} times within the last {metrics.FLAKY_WINDOW} runs it appeared in. Skipped runs are ignored."})

    # 3. persistent failures
    for nodeid, streak in metrics.consecutive_failures(runs):
        if streak >= PERSISTENT_FAILURE_RUNS:
            insights.append({"kind": "persistent", "severity": "critical", "text": f"{_short(nodeid)} has failed in the last {streak} consecutive runs; this looks like a real regression, not flakiness.", "rule": f"A test failing in at least {PERSISTENT_FAILURE_RUNS} consecutive runs (skipped runs are ignored)."})
        else:
            break  # streaks are sorted longest first

    # 4. per-layer p95 duration movement
    if previous is not None:
        for layer in ("api", "ui"):
            now, before = metrics.layer_p95(latest, layer), metrics.layer_p95(previous, layer)
            if now is None or before is None or before <= 0:
                continue
            ratio = (now - before) / before
            if abs(ratio) >= LAYER_P95_RATIO and abs(now - before) >= LAYER_P95_MIN_DELTA:
                direction = "rose" if ratio > 0 else "fell"
                severity = "warning" if ratio > 0 else "good"
                insights.append({"kind": "layer_p95", "severity": severity, "text": f"{layer.upper()} layer p95 test duration {direction} from {_fmt_seconds(before)} to {_fmt_seconds(now)} ({ratio:+.0%}) since the previous run.", "rule": f"The p95 of test durations in a layer changed by at least {LAYER_P95_RATIO:.0%} and {_fmt_seconds(LAYER_P95_MIN_DELTA)} between the last two runs."})

    # 5. suite time movement
    if previous is not None:
        prev_wall = metrics.run_stats(previous)["wall_seconds"]
        if prev_wall > 0:
            ratio = (stats["wall_seconds"] - prev_wall) / prev_wall
            if abs(ratio) >= DURATION_CHANGE_RATIO:
                direction = "slower" if ratio > 0 else "faster"
                insights.append({"kind": "suite_time", "severity": "warning" if ratio > 0 else "good", "text": f"The suite ran {abs(ratio):.0%} {direction} than the previous run ({_fmt_seconds(prev_wall)} to {_fmt_seconds(stats['wall_seconds'])}).", "rule": f"Suite wall time changed by at least {DURATION_CHANGE_RATIO:.0%} between the last two runs."})

    # 6. one test dominating the run
    total_test_time = stats["test_time"]
    if total_test_time > 0:
        tests = latest.get("tests", [])
        slowest = max(tests, key=lambda t: float(t.get("duration") or 0.0), default=None)
        if slowest is not None and len(tests) >= 3:
            slowest_duration = float(slowest.get("duration") or 0.0)
            share = slowest_duration / total_test_time
            others = sorted(float(t.get("duration") or 0.0) for t in tests if t is not slowest)
            median_other = others[len(others) // 2]
            # Both conditions: a big share of the run AND an outlier against its
            # peers. Either alone flags ordinary tests in small suites.
            if share >= SLOW_TEST_SHARE and slowest_duration >= SLOW_TEST_RATIO * max(median_other, 1e-9):
                insights.append({"kind": "slow_test", "severity": "info", "text": f"{_short(slowest['nodeid'])} alone accounts for {share:.0%} of total test time in the latest run ({_fmt_seconds(slowest_duration)}), {slowest_duration / max(median_other, 1e-9):.1f}x the median test.", "rule": f"A single test whose duration is at least {SLOW_TEST_SHARE:.0%} of the sum of all test durations in the latest run and at least {SLOW_TEST_RATIO:g}x the median duration of the other tests; needs at least 3 tests."})

    # 7. stability streak
    streak = metrics.green_streak(runs)
    if streak >= 2:
        insights.append({"kind": "streak", "severity": "good", "text": f"All tests have passed in the last {streak} consecutive runs.", "rule": "Counts the latest runs, newest first, with zero failed or errored tests."})
    elif stats["failed"] + stats["error"] == 0 and stats["total"] > 0 and len(runs) == 1:
        insights.append({"kind": "streak", "severity": "good", "text": "The only recorded run passed cleanly.", "rule": "The latest run has zero failed or errored tests."})

    if not insights:
        insights.append({"kind": "quiet", "severity": "info", "text": "No notable change since the previous run: pass rate, durations and outcomes are all within their usual range.", "rule": "None of the insight rules fired for the latest two runs."})

    return insights
