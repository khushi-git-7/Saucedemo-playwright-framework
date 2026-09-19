"""Insight rules (utils/dashboard/insights.py)."""

from tests_framework.helpers import run_sequence, shard, make_record
from utils.dashboard import insights


def kinds(runs):
    return [i["kind"] for i in insights.compute_insights(runs)]


def find(runs, kind):
    return next(i for i in insights.compute_insights(runs) if i["kind"] == kind)


def test_no_history_gives_the_empty_insight():
    result = insights.compute_insights([])
    assert [i["kind"] for i in result] == ["empty"]
    assert result[0]["rule"]


def test_every_insight_carries_text_severity_and_rule():
    runs = run_sequence({"tests/test_a.py::test_x": "PFPF", "tests/test_a.py::test_y": "PPPF"})
    for item in insights.compute_insights(runs):
        assert item["text"] and item["rule"]
        assert item["severity"] in ("good", "info", "warning", "critical")


def test_pass_rate_drop_names_the_driving_tests():
    tests = {f"tests/test_checkout.py::test_{i}": "PP" for i in range(8)}
    tests["tests/test_checkout.py::test_pay"] = "PF"
    tests["tests/test_checkout.py::test_ship"] = "PF"
    runs = run_sequence(tests)

    item = find(runs, "pass_rate_drop")

    assert item["severity"] == "critical"
    assert "dropped 20.0 points" in item["text"]
    assert "2 newly failing tests" in item["text"]
    assert "test_pay" in item["text"] and "test_ship" in item["text"]
    assert "5 points" in item["rule"]


def test_pass_rate_gain_lists_fixed_tests():
    runs = run_sequence({"tests/test_a.py::test_x": "FP", "tests/test_a.py::test_y": "PP"})
    item = find(runs, "pass_rate_gain")
    assert item["severity"] == "good" and "test_x" in item["text"]


def test_small_change_reports_new_failures_instead_of_pass_rate():
    tests = {f"tests/test_a.py::test_{i}": "PP" for i in range(30)}
    tests["tests/test_a.py::test_new"] = "PF"  # ~3 points, below the threshold
    runs = run_sequence(tests)

    result = kinds(runs)

    assert "pass_rate_drop" not in result
    assert "new_failures" in result
    assert "test_new" in find(runs, "new_failures")["text"]


def test_flaky_test_insight_shows_flip_count_and_window():
    runs = run_sequence({"tests/test_cart.py::test_badge": "PFPFP", "tests/test_a.py::test_y": "PPPPP"})
    item = find(runs, "flaky")
    assert "test_badge has flipped 4 times in the last 5 runs" in item["text"]
    assert "2 times" in item["rule"]


def test_persistent_failure_is_called_a_regression():
    runs = run_sequence({"tests/test_checkout.py::test_e2e": "PPFFF", "tests/test_a.py::test_y": "PPPPP"})
    item = find(runs, "persistent")
    assert "failed in the last 3 consecutive runs" in item["text"]
    assert item["severity"] == "critical"
    assert "flaky" not in kinds(runs)  # one flip is not flakiness


def test_layer_p95_rise_is_reported_with_before_and_after():
    api_tests = {f"api/test_posts_api.py::test_{i}": "PP" for i in range(5)}
    durations = {k: [0.2, 0.2] for k in api_tests}
    durations["api/test_posts_api.py::test_4"] = [0.21, 0.48]
    runs = run_sequence(api_tests, durations)

    item = find(runs, "layer_p95")

    assert "API layer p95" in item["text"]
    assert "210 ms to 480 ms" in item["text"]
    assert item["severity"] == "warning"


def test_layer_p95_ignores_small_absolute_changes():
    runs = run_sequence({"api/test_a_api.py::test_x": "PP"}, {"api/test_a_api.py::test_x": [0.010, 0.020]})
    assert "layer_p95" not in kinds(runs)


def test_suite_time_change():
    slow = shard("r2", [make_record("tests/test_a.py::test_x")], index=1, wall=50.0)
    fast = shard("r1", [make_record("tests/test_a.py::test_x")], index=0, wall=20.0)
    item = find([fast, slow], "suite_time")
    assert "150% slower" in item["text"]
    assert "20.0 s to 50.0 s" in item["text"]


def test_dominant_slow_test():
    run = shard("r", [make_record("tests/test_a.py::test_slow", duration=8.0), make_record("tests/test_a.py::test_fast", duration=1.0), make_record("tests/test_a.py::test_ok", duration=1.0)])
    item = find([run], "slow_test")
    assert "test_slow alone accounts for 80%" in item["text"]


def test_green_streak_and_quiet_run():
    runs = run_sequence({"tests/test_a.py::test_x": "PPP"}, {"tests/test_a.py::test_x": [1.0, 1.0, 1.0]})
    result = insights.compute_insights(runs)
    assert [i["kind"] for i in result] == ["streak"]
    assert "last 3 consecutive runs" in result[0]["text"]


def test_quiet_when_nothing_changes_and_not_green():
    runs = run_sequence({"tests/test_a.py::test_x": "FF", "tests/test_a.py::test_y": "PP"})
    assert kinds(runs) == ["quiet"]
