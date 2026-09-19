"""`python -m utils.site` - build the landing page from recorded runs."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from utils.dashboard import loader
from utils.site import render, stats

DEFAULT_REPO = "https://github.com/khushi-git-7/Saucedemo-playwright-framework"


def repo_url(explicit: str = None) -> str:
    if explicit:
        return explicit
    slug = os.environ.get("GITHUB_REPOSITORY")
    return "https://github.com/" + slug if slug else DEFAULT_REPO


def usable(out: Path, href: str):
    """An href is linked only when it is absolute or exists next to the page."""
    if not href:
        return None
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return href if (out.parent / href).is_file() else None


def build(history: Path, out: Path, dashboard: str = "dashboard.html", report: str = "report.html", repo: str = None) -> Path:
    """Render the page to `out`; returns the path. Zero runs is a valid input."""
    runs = loader.load_runs(history) if history.is_dir() else []
    numbers = stats.site_stats(runs)
    page = render.render(numbers, usable(out, dashboard), usable(out, report), repo_url(repo))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m utils.site", description="Build the TestVerse landing page from recorded runs.")
    parser.add_argument("--history", default="reports/history", help="folder with run JSON files (default: reports/history)")
    parser.add_argument("--out", default="site/index.html", help="output HTML file (default: site/index.html)")
    parser.add_argument("--dashboard", default="dashboard.html", help="href of the dashboard relative to --out (default: dashboard.html)")
    parser.add_argument("--report", default="report.html", help="href of the latest UI report relative to --out (default: report.html)")
    parser.add_argument("--repo-url", default=None, help="repository URL for the source links (default: GITHUB_REPOSITORY or the project repo)")
    args = parser.parse_args(argv)

    history = Path(args.history)
    out = build(history, Path(args.out), args.dashboard, args.report, args.repo_url)
    runs = len(loader.load_runs(history)) if history.is_dir() else 0
    print("Landing page written to " + str(out.resolve()) + " (" + str(runs) + " runs)")
    return 0
