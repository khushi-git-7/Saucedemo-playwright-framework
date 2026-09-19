"""Writes a synthetic run history so the dashboard can be previewed or tested.

    python -m utils.dashboard.demo --out reports/history-demo --runs 8
    python -m utils.dashboard --history reports/history-demo --out reports/dashboard-demo.html

The data is deterministic (seeded) and deliberately contains a flaky test, a
persistent failure, a duration spike and a skipped test, so every panel of the
dashboard has something to show. It is also what tests_framework/ builds on.
"""

from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from utils.results_plugin import classify_area, classify_layer

UI_TESTS = [
    ("tests/test_login.py::test_login[valid_credentials]", ["ui", "smoke", "regression"], 2.1),
    ("tests/test_login.py::test_login[locked_out_user]", ["ui", "smoke", "regression"], 1.7),
    ("tests/test_login.py::test_login[empty_username]", ["ui", "smoke", "regression"], 1.4),
    ("tests/test_inventory.py::test_inventory_lists_products", ["ui", "smoke", "regression"], 2.4),
    ("tests/test_inventory.py::test_sort_by_price_low_to_high", ["ui", "regression"], 2.9),
    ("tests/test_cart.py::test_add_to_cart_updates_badge", ["ui", "smoke", "regression"], 2.6),
    ("tests/test_cart.py::test_remove_from_cart", ["ui", "regression"], 2.8),
    ("tests/test_checkout.py::test_checkout_end_to_end", ["ui", "e2e", "regression"], 5.2),
    ("tests/test_checkout.py::test_checkout_requires_first_name", ["ui", "regression"], 3.1),
]
API_TESTS = [
    ("api/test_posts_api.py::test_get_post_returns_200", ["api", "smoke", "regression"], 0.32),
    ("api/test_posts_api.py::test_get_post_matches_schema", ["api", "smoke", "regression"], 0.21),
    ("api/test_posts_api.py::test_get_post_response_time", ["api", "regression"], 0.2),
    ("api/test_posts_api.py::test_create_post", ["api", "regression"], 0.35),
    ("api/test_posts_api.py::test_missing_post_returns_404", ["api", "regression"], 0.19),
    ("api/test_users_api.py::test_users_list_matches_schema", ["api", "smoke", "regression"], 0.27),
    ("api/test_users_api.py::test_every_user_has_a_valid_email[1]", ["api", "regression"], 0.18),
]

FLAKY = "tests/test_cart.py::test_add_to_cart_updates_badge"
REGRESSED = "tests/test_checkout.py::test_checkout_end_to_end"
SKIPPED = "api/test_posts_api.py::test_create_post"
SPIKE = "api/test_posts_api.py::test_get_post_response_time"


def _record(nodeid: str, markers: list, outcome: str, duration: float, index: int) -> dict:
    module = nodeid.split("::", 1)[0]
    layer = classify_layer(nodeid, markers)
    record = {
        "nodeid": nodeid,
        "name": nodeid.rsplit("::", 1)[-1],
        "module": module,
        "area": classify_area(nodeid),
        "layer": layer,
        "markers": markers,
        "outcome": outcome,
        "phase": None,
        "duration": round(duration, 3),
        "call_duration": round(duration * 0.8, 3),
        "message": "",
        "details": "",
        "artifacts": [],
        "worker": f"gw{index % 2}",
    }
    if outcome == "failed":
        record["phase"] = "call"
        record["message"] = "AssertionError: expected 'inventory.html' in page.url, got 'https://www.saucedemo.com/'"
        record["details"] = "def test_x(browser_page):\n>       assert 'inventory.html' in page.url\nE       AssertionError: assert 'inventory.html' in 'https://www.saucedemo.com/'"
        if layer == "ui":
            safe = record["name"].replace("[", "_").replace("]", "")
            record["artifacts"] = [f"screenshots/{safe}_gw0_demo.png", f"traces/{safe}_gw0_demo.zip", f"videos/{safe}_gw0_demo.webm"]
    elif outcome == "error":
        record["phase"] = "setup"
        record["message"] = "playwright._impl._errors.TimeoutError: Timeout 30000ms exceeded while navigating"
    elif outcome == "skipped":
        record["phase"] = "setup"
        record["message"] = "requires a writable API"
    return record


def make_run(index: int, count: int, rng: random.Random, start: datetime) -> list:
    """Returns the shards (UI + API) for run *index* of *count*."""
    stamp = start + timedelta(hours=6 * index)
    group = f"demo-{index + 1:03d}"
    sha = f"{rng.randrange(16 ** 10):010x}{index:030d}"[:40]
    shards = []
    for suite, tests, browser, wall in (("ui", UI_TESTS, "chromium", 40.0), ("api", API_TESTS, "chromium", 3.0)):
        records = []
        for position, (nodeid, markers, base) in enumerate(tests):
            duration = base * rng.uniform(0.85, 1.2)
            outcome = "passed"
            if nodeid == FLAKY and index % 2 == 1:
                outcome = "failed"
            if nodeid == REGRESSED and index >= count - 3:
                outcome = "failed"
            if nodeid == SKIPPED and index == count - 2:
                outcome = "skipped"
            if nodeid == SPIKE and index == count - 1:
                duration = base * 6
            if index == count - 4 and nodeid == "tests/test_inventory.py::test_sort_by_price_low_to_high":
                outcome = "error"
            records.append(_record(nodeid, markers, outcome, duration, position))
        summary = {"total": len(records), "passed": 0, "failed": 0, "error": 0, "skipped": 0}
        for record in records:
            summary[record["outcome"]] += 1
        shards.append(
            {
                "schema": 1,
                "run_id": f"{stamp.strftime('%Y%m%dT%H%M%S')}Z-{suite}",
                "run_group": group,
                "suite": suite,
                "timestamp": stamp.isoformat(timespec="seconds"),
                "wall_seconds": round(wall * rng.uniform(0.9, 1.15) * (1.4 if index == count - 1 else 1.0), 3),
                "exit_status": 1 if summary["failed"] or summary["error"] else 0,
                "git": {"sha": sha, "branch": "main"},
                "ci": {"provider": "github", "run_id": str(1000 + index), "run_number": str(index + 1), "event": "push", "url": f"https://github.com/khushi-git-7/Saucedemo-playwright-framework/actions/runs/{1000 + index}"},
                "browser": browser,
                "headless": True,
                "workers": 2,
                "python": "3.12.3",
                "platform": "linux",
                "pytest": "9.0.3",
                "config": {"base_url": "https://www.saucedemo.com/", "browser": browser, "headless": True},
                "summary": summary,
                "tests": records,
            }
        )
    return shards


def write_history(out: Path, runs: int = 8, seed: int = 7) -> list:
    rng = random.Random(seed)
    out.mkdir(parents=True, exist_ok=True)
    start = datetime(2026, 9, 10, 2, 0, tzinfo=timezone.utc)
    written = []
    for index in range(runs):
        for shard in make_run(index, runs, rng, start):
            path = out / f"{shard['run_id']}.json"
            path.write_text(json.dumps(shard, indent=1), encoding="utf-8")
            written.append(path)
    return written


def main(argv: list = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m utils.dashboard.demo")
    parser.add_argument("--out", default="reports/history-demo")
    parser.add_argument("--runs", type=int, default=8)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args(argv)
    files = write_history(Path(args.out), args.runs, args.seed)
    print(f"Wrote {len(files)} shard files ({args.runs} runs) to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
