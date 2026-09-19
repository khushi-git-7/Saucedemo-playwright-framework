"""The HTML renderer and CLI (utils/dashboard/render.py, cli.py).

These tests parse the generated page with the standard library and assert on
what it says, so a regression in escaping, linking or wording fails here
rather than in a browser.
"""

import json
import re

from tests_framework.helpers import check_html, make_record, run_sequence, shard
from utils.dashboard import cli, render
from utils.dashboard.demo import write_history


def embedded_run_data(page: str) -> list:
    match = re.search(r'<script id="run-data" type="application/json">(.*?)</script>', page, re.S)
    return json.loads(match.group(1))


# ---------------------------------------------------------------------------
# shapes of history
# ---------------------------------------------------------------------------
def test_no_runs_renders_the_empty_page():
    page = render.render_dashboard([], repo_url="https://example.test/repo")

    assert check_html(page).problems == []
    assert "No run history found" in page
    assert embedded_run_data(page) == []


def test_a_single_run_renders_every_section_and_says_first_run():
    page = render.render_dashboard([shard("r1", [make_record("tests/test_a.py::test_x")])])

    assert check_html(page).problems == []
    for key, _ in render.NAV:
        assert f'<section id="{key}">' in page
    assert page.count("first run") == 5  # one per tile that has a delta
    assert "1</b> run in history" in page


def test_a_run_without_tests_renders_without_dividing_by_zero():
    page = render.render_dashboard([shard("empty", [])])

    assert check_html(page).problems == []
    assert "n/a" in page


def test_previous_run_without_a_pass_rate_is_not_called_the_first_run():
    only_skips = shard("r1", [make_record("tests/test_a.py::test_x", "skipped", phase="setup")], index=0)
    latest = shard("r2", [make_record("tests/test_a.py::test_x", "passed")], index=1)

    page = render.render_dashboard([only_skips, latest])

    assert "first run" not in page
    assert "no previous value" in page


def test_demo_history_renders_a_well_formed_page(tmp_path):
    write_history(tmp_path, runs=6)
    out = tmp_path / "site" / "index.html"

    result = cli.build(tmp_path, out, artifact_base="")

    page = out.read_text(encoding="utf-8")
    assert result["runs"] == 6
    assert check_html(page).problems == []
    assert len(embedded_run_data(page)) == 6


# ---------------------------------------------------------------------------
# escaping
# ---------------------------------------------------------------------------
HOSTILE = '<b>"x"</b> & <img src=x onerror=alert(1)>'


def test_every_string_from_the_results_is_escaped():
    nodeid = f"tests/test_{HOSTILE}.py::test_{HOSTILE}"
    test = make_record(nodeid, "failed", message=f"AssertionError: {HOSTILE}", details=f"E {HOSTILE}", artifacts=[f"screenshots/{HOSTILE}.png"], markers=["ui", HOSTILE])
    run = shard("r1", [test], suite=HOSTILE, browser=HOSTILE, git={"sha": HOSTILE, "branch": HOSTILE}, ci={"provider": "github", "url": f"https://ci.test/{HOSTILE}", "run_number": HOSTILE})

    page = render.render_dashboard([run], repo_url="https://example.test/repo", links=[(HOSTILE, HOSTILE)])

    parsed = check_html(page)
    assert parsed.problems == []
    assert "img" not in parsed.tags
    assert "onerror" not in parsed.attributes
    assert "&lt;img src=x onerror=alert(1)&gt;" in page
    assert "<img" not in page


def test_embedded_json_cannot_close_the_script_element():
    nodeid = "tests/test_a.py::test_x[</script><!--<script>]"
    page = render.render_dashboard([shard("r1", [make_record(nodeid, "failed", message="</script>")])])

    script = re.search(r'<script id="run-data" type="application/json">(.*?)</script>', page, re.S).group(1)
    assert "<" not in script
    assert embedded_run_data(page)[0]["tests"][0]["n"] == nodeid


# ---------------------------------------------------------------------------
# artifact links
# ---------------------------------------------------------------------------
def test_artifact_links_are_relative_to_the_page_when_the_files_exist(tmp_path):
    (tmp_path / "screenshots").mkdir()
    (tmp_path / "screenshots" / "shot.png").write_bytes(b"png")
    test = make_record("tests/test_a.py::test_x", "failed", artifacts=["screenshots/shot.png", "traces/trace.zip"])
    run = shard("r1", [test], ci={"provider": "github", "url": "https://ci.test/runs/1"})

    page = render.render_dashboard([run], artifact_base="..", artifact_root=tmp_path)

    assert '<a class="alink" href="../screenshots/shot.png">screenshot</a>' in page
    assert "traces/trace.zip" not in page  # missing file: no dead link
    assert 'href="https://ci.test/runs/1"' in page  # ... but a way to get it
    assert "trace" in page


def test_missing_artifacts_without_ci_degrade_to_plain_text(tmp_path):
    test = make_record("tests/test_a.py::test_x", "failed", artifacts=["videos/clip.webm"])

    page = render.render_dashboard([shard("r1", [test])], artifact_base="..", artifact_root=tmp_path)

    assert "videos/clip.webm" not in page
    assert "video" in page
    assert "not published with this page" in page


def test_cli_build_resolves_the_artifact_root_from_the_output_location(tmp_path, monkeypatch):
    monkeypatch.setattr(cli.Config, "ROOT_DIR", tmp_path)
    history = tmp_path / "history"
    history.mkdir()
    (tmp_path / "screenshots").mkdir()
    (tmp_path / "screenshots" / "shot.png").write_bytes(b"png")
    test = make_record("tests/test_a.py::test_x", "failed", artifacts=["screenshots/shot.png"])
    (history / "r1.json").write_text(json.dumps(shard("r1", [test])), encoding="utf-8")

    out = tmp_path / "reports" / "dashboard.html"
    cli.build(history, out)
    assert 'href="../screenshots/shot.png"' in out.read_text(encoding="utf-8")

    site = tmp_path / "site" / "index.html"
    cli.build(history, site, artifact_base=".")
    assert "not published with this page" in site.read_text(encoding="utf-8")


def test_parse_links_accepts_label_equals_href_and_bare_href(tmp_path):
    out = tmp_path / "index.html"
    assert cli.parse_links(["UI report=report.html", "https://x.test/api-report.html"], out) == [("UI report", "report.html"), ("api-report.html", "https://x.test/api-report.html")]
    assert cli.parse_links([], out) == []
    (tmp_path / "report.html").write_text("", encoding="utf-8")
    assert cli.parse_links([], out) == [("Latest HTML report", "report.html")]


# ---------------------------------------------------------------------------
# wording that must stay true
# ---------------------------------------------------------------------------
def test_run_rows_link_the_commit_and_show_local_for_uncommitted_runs():
    with_ci = shard("r1", [make_record("tests/test_a.py::test_x")], index=0, ci={"provider": "github", "url": "https://ci.test/runs/9", "run_number": "9"})
    local = shard("r2", [make_record("tests/test_a.py::test_x")], index=1, git={"sha": "", "branch": ""})

    page = render.render_dashboard([with_ci, local], repo_url="https://example.test/repo")

    assert 'href="https://example.test/repo/commit/abc1234def">abc1234</a>' in page
    assert 'href="https://ci.test/runs/9">#9</a>' in page
    assert '<span class="muted">local</span>' in page


def test_flakiness_timeline_marks_runs_where_the_test_did_not_run():
    runs = run_sequence({"tests/test_a.py::test_x": "P-FP", "tests/test_a.py::test_y": "PPPP"})

    page = render.render_dashboard(runs)

    assert page.count('class="c-absent"') == 1


# ---------------------------------------------------------------------------
# the Home link back to the landing page
# ---------------------------------------------------------------------------
def test_home_link_is_rendered_only_when_asked_for_and_outside_the_nav():
    run = shard("r1", [make_record("tests/test_a.py::test_x")])

    without = render.render_dashboard([run])
    with_home = render.render_dashboard([run], home="index.html")
    empty_with_home = render.render_dashboard([], home="../index.html")

    assert 'class="home"' not in without
    for page in (with_home, empty_with_home):
        assert check_html(page).problems == []
        assert page.count('class="home"') == 1
        # the scroll-spy script queries every .nav href as an in-page anchor
        assert re.search(r'<a class="home" href="[^"]+">.*?</a>\s*<nav class="nav">', page, re.S)
    assert '<a class="home" href="index.html">' in with_home
    assert '<a class="home" href="../index.html">' in empty_with_home


def test_cli_home_option_reaches_the_page(tmp_path):
    write_history(tmp_path, runs=1)
    out = tmp_path / "site" / "dashboard.html"

    assert cli.main(["--history", str(tmp_path), "--out", str(out), "--artifact-base", ".", "--home", "index.html"]) == 0

    assert '<a class="home" href="index.html">' in out.read_text(encoding="utf-8")
