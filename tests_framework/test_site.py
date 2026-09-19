"""The landing page (utils/site) renders a valid, self-contained page from the history."""

from __future__ import annotations

import html.parser
import re

from helpers import make_record, run_sequence, shard

from utils.site import cli, render, stats

VOID = {"meta", "link", "br", "img", "input", "hr", "path", "rect", "circle", "line"}


class _Balance(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.errors = []

    def handle_starttag(self, tag, attrs):
        if tag not in VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        else:
            self.errors.append(tag)


def _check(page: str) -> None:
    parser = _Balance()
    parser.feed(page)
    assert not parser.errors and not parser.stack, (parser.errors, parser.stack)
    external = [
        url for url in re.findall(r'(?:src|href)="([^"]+)"', page)
        if url.startswith("http") and "github.com/khushi-git-7" not in url
    ]
    assert external == []


def _write(tmp_path, runs):
    import json
    history = tmp_path / "history"
    history.mkdir()
    for index, run in enumerate(runs):
        (history / "{:04d}.json".format(index)).write_text(json.dumps(run), encoding="utf-8")
    return history


# -- stats ------------------------------------------------------------------
def test_stats_none_without_runs():
    assert stats.site_stats([]) is None


def test_stats_describe_the_latest_run_and_the_history():
    runs = run_sequence({"tests/test_a.py::test_x": "PFP", "api/test_b.py::test_y": "PPP"})
    runs[-1]["browser"] = "chromium, firefox"
    numbers = stats.site_stats(runs)
    assert numbers["tests"] == 2 and numbers["failed"] == 0 and numbers["runs"] == 3
    assert numbers["pass_rate"] == 100.0
    assert numbers["browsers"] == ["chromium", "firefox"]
    assert numbers["green_streak"] == 1  # only the latest run is clean


# -- page -------------------------------------------------------------------
def test_zero_runs_renders_an_honest_empty_state(tmp_path):
    out = cli.build(tmp_path / "missing", tmp_path / "site" / "index.html")
    page = out.read_text(encoding="utf-8")
    _check(page)
    assert "No runs recorded yet" in page
    assert '<div class="l">tests in the suite</div>' not in page
    assert 'href="dashboard.html"' not in page          # nothing next to the page yet
    assert cli.DEFAULT_REPO in page


def test_one_run_fills_the_strip_and_links_existing_pages(tmp_path):
    history = _write(tmp_path, [shard("r1", [make_record("tests/test_a.py::test_x", duration=2.0)])])
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    (site_dir / "dashboard.html").write_text("<html></html>", encoding="utf-8")
    out = cli.build(history, site_dir / "index.html")
    page = out.read_text(encoding="utf-8")
    _check(page)
    assert ">1<" in page and "100.0%" in page and "2.00 s" in page
    assert 'href="dashboard.html"' in page
    assert 'href="report.html"' not in page               # no report next to the page


def test_three_runs_use_the_latest_for_the_numbers(tmp_path):
    runs = run_sequence({"tests/test_a.py::test_x": "FFP", "tests/test_a.py::test_y": "PPP"})
    history = _write(tmp_path, runs)
    page = cli.build(history, tmp_path / "site" / "index.html").read_text(encoding="utf-8")
    _check(page)
    assert ">3<" in page and "100.0%" in page and "50.0%" not in page


def test_hostile_strings_are_escaped(tmp_path):
    hostile = '<script>alert("x")</script>'
    run = shard("r1", [make_record("tests/test_a.py::test_x")], browser="chromium" + hostile)
    page = cli.build(_write(tmp_path, [run]), tmp_path / "site" / "index.html").read_text(encoding="utf-8")
    assert hostile not in page and "&lt;script&gt;" in page
    _check(page)


def test_absolute_dashboard_url_is_kept(tmp_path):
    page = cli.build(_write(tmp_path, [shard("r1", [make_record("tests/test_a.py::test_x")])]),
                     tmp_path / "site" / "index.html", dashboard="https://example.invalid/d").read_text(encoding="utf-8")
    assert 'href="https://example.invalid/d"' in page


def test_repo_url_prefers_the_explicit_value_then_the_ci_slug(monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "someone/else")
    assert cli.repo_url("https://x.invalid/r") == "https://x.invalid/r"
    assert cli.repo_url() == "https://github.com/someone/else"
    monkeypatch.delenv("GITHUB_REPOSITORY")
    assert cli.repo_url() == cli.DEFAULT_REPO


def test_cli_entry_point(tmp_path, capsys):
    history = _write(tmp_path, [shard("r1", [make_record("tests/test_a.py::test_x")])])
    out = tmp_path / "site" / "index.html"
    assert cli.main(["--history", str(history), "--out", str(out)]) == 0
    assert out.is_file() and "(1 runs)" in capsys.readouterr().out


def test_render_never_emits_the_word_none(tmp_path):
    page = render.render(None, None, None, cli.DEFAULT_REPO)
    assert "None" not in page
