"""Metric computations (utils/dashboard/metrics.py)."""

import pytest

from tests_framework.helpers import run_sequence, shard, make_record
from utils.dashboard import metrics


# -- percentiles -----------------------------------------------------------
@pytest.mark.parametrize(
    "values, p, expected",
    [
        ([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 50, 5),
        ([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 95, 10),
        ([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20], 95, 19),
        ([5, 1, 3], 0, 1),
        ([5, 1, 3], 100, 5),
        ([7], 95, 7),
        ([3, None, 1], 50, 1),
    ],
)
def test_percentile_is_nearest_rank(values, p, expected):
    assert metrics.percentile(values, p) == expected


def test_percentile_of_nothing_is_none():
    assert metrics.percentile([], 95) is None
    assert metrics.percentile([None], 50) is None


# -- pass rate ---------------------------------------------------------------
def test_pass_rate_excludes_skipped_from_the_denominator():
    assert metrics.pass_rate({"passed": 8, "failed": 1, "error": 1, "skipped": 5}) == 80.0


def test_pass_rate_is_none_when_nothing_executed():
    assert metrics.pass_rate({"passed": 0, "failed": 0, "error": 0, "skipped": 3}) is None


def test_run_stats_reports_counts_durations_and_wall_time():
    run = shard("r", [make_record("tests/test_a.py::test_x", duration=1.0), make_record("tests/test_a.py::test_y", "failed", duration=3.0)], wall=12.5)

    stats = metrics.run_stats(run)

    assert stats["total"] == 2 and stats["passed"] == 1 and stats["failed"] == 1
    assert stats["pass_rate"] == 50.0
    assert stats["median_duration"] == 2.0
    assert stats["test_time"] == 4.0
    assert stats["wall_seconds"] == 12.5


def test_run_stats_falls_back_to_test_time_without_wall_seconds():
    run = shard("r", [make_record("tests/test_a.py::test_x", duration=1.5)])
    del run["wall_seconds"]
    assert metrics.run_stats(run)["wall_seconds"] == 1.5


# -- flakiness ---------------------------------------------------------------
@pytest.mark.parametrize(
    "outcomes, flips",
    [
        (["passed", "passed", "passed"], 0),
        (["passed", "failed"], 1),
        (["passed", "failed", "passed"], 2),
        (["passed", "skipped", "failed", "passed"], 2),   # skipped is ignored
        (["failed", "error", "failed"], 0),               # error counts as failing
        (["passed", "error", "passed", "failed", "passed"], 4),
    ],
)
def test_count_flips(outcomes, flips):
    assert metrics.count_flips(outcomes) == flips


def test_flaky_test_is_detected_and_single_flip_is_not_flaky():
    runs = run_sequence(
        {
            "tests/test_cart.py::test_flaky": "PFPFPP",
            "tests/test_checkout.py::test_regressed": "PPPPFF",
            "tests/test_login.py::test_stable": "PPPPPP",
        }
    )

    rows = metrics.flakiness(runs)

    by_id = {row["nodeid"]: row for row in rows}
    assert "tests/test_login.py::test_stable" not in by_id
    flaky = by_id["tests/test_cart.py::test_flaky"]
    assert flaky["flips"] == 4 and flaky["flaky"] is True
    assert flaky["fail_count"] == 2 and flaky["runs_seen"] == 6
    assert flaky["last_outcome"] == "passed"
    assert [o for _, o in flaky["outcomes"]] == ["passed", "failed", "passed", "failed", "passed", "passed"]
    regressed = by_id["tests/test_checkout.py::test_regressed"]
    assert regressed["flips"] == 1 and regressed["flaky"] is False
    assert rows[0]["nodeid"] == "tests/test_cart.py::test_flaky"  # most flips first


def test_flakiness_only_looks_at_the_window():
    pattern = "PF" * 5 + "PPPPPPPPPP"  # flapped long ago, stable for the last 10 runs
    runs = run_sequence({"tests/test_a.py::test_x": pattern})

    assert metrics.flakiness(runs, window=10) == []
    assert metrics.flakiness(runs, window=20)[0]["flips"] == 10  # 9 inside "PF"*5 plus the final F->P


def test_flakiness_ignores_runs_where_the_test_was_absent():
    runs = run_sequence({"tests/test_a.py::test_x": "P-F-P", "tests/test_a.py::test_y": "PPPPP"})

    row = metrics.flakiness(runs)[0]

    assert row["runs_seen"] == 3
    assert [i for i, _ in row["outcomes"]] == [0, 2, 4]


# -- slowest tests, breakdowns, changes -------------------------------------
def test_slowest_tests_computes_p50_p95_across_history():
    durations = {"tests/test_a.py::test_slow": [1.0, 2.0, 3.0, 4.0, 10.0], "tests/test_a.py::test_fast": [0.1] * 5}
    runs = run_sequence({k: "PPPPP" for k in durations}, durations)

    rows = metrics.slowest_tests(runs, limit=1)

    assert rows[0]["nodeid"] == "tests/test_a.py::test_slow"
    assert rows[0]["p50"] == 3.0 and rows[0]["p95"] == 10.0 and rows[0]["max"] == 10.0
    assert rows[0]["last"] == 10.0 and rows[0]["runs"] == 5


def test_breakdown_by_marker_counts_a_test_under_each_marker():
    run = shard(
        "r",
        [
            make_record("tests/test_a.py::test_x", "passed", markers=["ui", "smoke"]),
            make_record("tests/test_a.py::test_y", "failed", markers=["ui"]),
            make_record("api/test_b_api.py::test_z", "passed", markers=["api", "smoke"]),
        ],
    )

    rows = {r["name"]: r for r in metrics.breakdown(run, "markers", ["smoke", "ui", "api"])}

    assert rows["ui"]["total"] == 2 and rows["ui"]["pass_rate"] == 50.0
    assert rows["smoke"]["total"] == 2 and rows["smoke"]["pass_rate"] == 100.0
    assert list(metrics.breakdown(run, "markers", ["smoke", "ui", "api"])[0].keys())[0] == "name"
    assert [r["name"] for r in metrics.breakdown(run, "markers", ["smoke", "ui", "api"])] == ["smoke", "ui", "api"]


def test_breakdown_by_area_uses_the_module_stem():
    run = shard("r", [make_record("tests/test_checkout.py::test_x"), make_record("tests/test_checkout.py::test_y", "error"), make_record("api/test_posts_api.py::test_z")])

    rows = {r["name"]: r for r in metrics.breakdown(run, "area")}

    assert rows["checkout"]["error"] == 1 and rows["checkout"]["pass_rate"] == 50.0
    assert "posts" in rows


def test_outcome_changes_between_two_runs():
    runs = run_sequence({"tests/test_a.py::test_new_fail": "PF", "tests/test_a.py::test_fixed": "FP", "tests/test_a.py::test_same": "FF", "tests/test_a.py::test_added": "-F"})

    changes = metrics.outcome_changes(runs[1], runs[0])

    assert changes == {"newly_failing": ["tests/test_a.py::test_new_fail"], "fixed": ["tests/test_a.py::test_fixed"]}


def test_consecutive_failures_and_green_streak():
    runs = run_sequence({"tests/test_a.py::test_x": "PFFSF", "tests/test_a.py::test_y": "PPPPP"})

    assert metrics.consecutive_failures(runs) == [("tests/test_a.py::test_x", 3)]  # skipped run is ignored
    assert metrics.green_streak(runs) == 0
    assert metrics.green_streak(run_sequence({"tests/test_a.py::test_x": "FPPP"})) == 3


def test_layer_p95():
    run = shard("r", [make_record(f"api/test_a_api.py::test_{i}", duration=float(i)) for i in range(1, 21)] + [make_record("tests/test_b.py::test_ui", duration=99.0)])
    assert metrics.layer_p95(run, "api") == 19.0
    assert metrics.layer_p95(run, "ui") == 99.0
    assert metrics.layer_p95(run, "other") is None
