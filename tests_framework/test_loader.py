"""Merging shards into runs (utils/dashboard/loader.py)."""

import json

from tests_framework.helpers import shard, make_record
from utils.dashboard import loader


def test_load_shards_skips_invalid_files_and_sorts_by_timestamp(tmp_path):
    older = shard("b-older", [make_record("tests/test_a.py::test_x")], index=0)
    newer = shard("a-newer", [make_record("tests/test_a.py::test_x")], index=1)
    (tmp_path / "a-newer.json").write_text(json.dumps(newer), encoding="utf-8")
    (tmp_path / "b-older.json").write_text(json.dumps(older), encoding="utf-8")
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")
    (tmp_path / "unrelated.json").write_text(json.dumps({"hello": "world"}), encoding="utf-8")

    shards = loader.load_shards(tmp_path)

    assert [s["run_id"] for s in shards] == ["b-older", "a-newer"]
    assert shards[0]["_file"] == "b-older.json"


def test_shards_with_the_same_group_merge_into_one_run():
    ui = shard("ui-shard", [make_record("tests/test_login.py::test_login", duration=3.0)], group="ci-42", index=0, suite="ui", wall=40.0)
    api = shard("api-shard", [make_record("api/test_posts_api.py::test_get", "failed", duration=0.3)], group="ci-42", index=0, suite="api", wall=5.0)

    runs = loader.merge_runs([ui, api])

    assert len(runs) == 1
    run = runs[0]
    assert run["run_id"] == "ci-42"
    assert sorted(run["shards"]) == ["api-shard", "ui-shard"]
    assert run["summary"] == {"total": 2, "passed": 1, "failed": 1, "error": 0, "skipped": 0}
    assert run["wall_seconds"] == 40.0  # parallel jobs: the longest one is the wall time
    assert run["suite"] == "api, ui"  # shards join in timestamp/run_id order
    assert run["exit_status"] == 1
    assert {t["nodeid"] for t in run["tests"]} == {"tests/test_login.py::test_login", "api/test_posts_api.py::test_get"}


def test_different_groups_stay_separate_and_are_ordered_oldest_first():
    second = shard("r2", [make_record("tests/test_a.py::test_x")], index=5)
    first = shard("r1", [make_record("tests/test_a.py::test_x")], index=1)

    runs = loader.merge_runs([second, first])

    assert [r["run_id"] for r in runs] == ["r1", "r2"]
    assert runs[0]["shards"] == ["r1"]


def test_same_test_from_different_browsers_is_kept_per_browser():
    chromium = shard("s-chromium", [make_record("tests/test_a.py::test_x", "passed")], group="g", index=0, browser="chromium")
    firefox = shard("s-firefox", [make_record("tests/test_a.py::test_x", "failed")], group="g", index=0, browser="firefox")

    run = loader.merge_runs([chromium, firefox])[0]

    nodeids = sorted(t["nodeid"] for t in run["tests"])
    assert nodeids == ["tests/test_a.py::test_x [chromium]", "tests/test_a.py::test_x [firefox]"]
    assert run["browser"] == "chromium, firefox"
    assert run["summary"]["passed"] == 1 and run["summary"]["failed"] == 1


def test_rerun_with_the_same_browser_keeps_the_latest_result():
    first = shard("s1", [make_record("tests/test_a.py::test_x", "failed")], group="g", index=0)
    rerun = shard("s2", [make_record("tests/test_a.py::test_x", "passed")], group="g", index=1)

    run = loader.merge_runs([rerun, first])[0]

    assert len(run["tests"]) == 1
    assert run["tests"][0]["outcome"] == "passed"
    assert run["timestamp"] == first["timestamp"]  # earliest shard dates the run


def test_load_runs_honours_max_runs(tmp_path):
    for index in range(5):
        data = shard(f"r{index}", [make_record("tests/test_a.py::test_x")], index=index)
        (tmp_path / f"r{index}.json").write_text(json.dumps(data), encoding="utf-8")

    runs = loader.load_runs(tmp_path, max_runs=2)

    assert [r["run_id"] for r in runs] == ["r3", "r4"]
