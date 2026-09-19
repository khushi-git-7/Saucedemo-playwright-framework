"""Command line entry point: python -m utils.dashboard."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from utils.config import Config
from utils.dashboard.loader import load_runs
from utils.dashboard.render import render_dashboard

DEFAULT_REPO_URL = "https://github.com/khushi-git-7/Saucedemo-playwright-framework"


def default_repo_url() -> str:
    """The repository URL from the CI environment, else the project's."""
    repo = os.getenv("GITHUB_REPOSITORY", "").strip()
    if repo:
        server = os.getenv("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
        return f"{server}/{repo}"
    return DEFAULT_REPO_URL


def _default_artifact_base(out: Path) -> str:
    """Relative path from the dashboard's folder back to the repo root.

    Artifact paths in the run files are repo-relative (screenshots/x.png), so
    reports/dashboard.html needs a "../" prefix to reach them.
    """
    try:
        rel = os.path.relpath(Config.ROOT_DIR, out.parent)
    except ValueError:  # different drive on Windows
        return ""
    return "" if rel == "." else rel.replace("\\", "/")


def _artifact_root(out: Path, base: str):
    """Folder the artifact links resolve against, or None for a remote base."""
    if "://" in base:
        return None
    return out.parent / base if base else out.parent


def parse_links(values: list, out: Path) -> list:
    """``--link`` values (``LABEL=HREF`` or a bare HREF) as (label, href) pairs.

    Without any, the HTML report next to the dashboard is linked when present.
    """
    links = []
    for value in values or []:
        label, _, href = value.partition("=")
        if not href:
            href, label = label, Path(label).name
        links.append((label.strip(), href.strip()))
    if not links:
        default_report = out.parent / "report.html"
        if default_report.exists():
            links.append(("Latest HTML report", "report.html"))
    return links


def build(history: Path, out: Path, max_runs: int = 0, repo_url: str = "", links: list = None, artifact_base: str = None, home: str = "") -> dict:
    """Renders the history folder to *out* and returns a small summary dict.

    *artifact_base* is the href prefix for failure artifacts, relative to the
    page; None means "the repo root, relative to out" and "." means "next to
    the page". Files that are not found under that base are not linked.
    *home* is the href of a page to link back to from the sidebar, if any.
    """
    runs = load_runs(history, max_runs=max_runs)
    base = _default_artifact_base(out) if artifact_base is None else artifact_base
    base = "" if base in (".", "./") else base
    html_text = render_dashboard(runs, repo_url=repo_url or default_repo_url(), links=links or [], artifact_base=base, artifact_root=_artifact_root(out, base), home=home)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_text, encoding="utf-8")
    return {"runs": len(runs), "bytes": len(html_text.encode("utf-8")), "out": str(out)}


def main(argv: list = None) -> int:
    """Command line entry point; returns the process exit code."""
    parser = argparse.ArgumentParser(prog="python -m utils.dashboard", description="Build the TestVerse results dashboard from recorded runs.")
    parser.add_argument("--history", default=str(Config.REPORTS_DIR / "history"), help="folder with run JSON files (default: reports/history)")
    parser.add_argument("--out", default=str(Config.REPORTS_DIR / "dashboard.html"), help="output HTML file (default: reports/dashboard.html)")
    parser.add_argument("--max-runs", type=int, default=200, help="keep only the newest N runs (default: 200, 0 = all)")
    parser.add_argument("--repo-url", default="", help="repository URL used for commit links (default: from GITHUB_REPOSITORY or the project repo)")
    parser.add_argument("--link", action="append", default=[], metavar="LABEL=HREF", help="extra sidebar link, e.g. 'UI report=report.html' (repeatable)")
    parser.add_argument("--artifact-base", default=None, help="prefix for artifact links, '.' for files next to the page (default: relative path from --out to the repo root)")
    parser.add_argument("--home", default="", metavar="HREF", help="page to link back to from the sidebar, e.g. index.html (default: none)")
    args = parser.parse_args(argv)

    history = Path(args.history)
    out = Path(args.out)
    result = build(history, out, max_runs=args.max_runs, repo_url=args.repo_url, links=parse_links(args.link, out), artifact_base=args.artifact_base, home=args.home)
    print(f"Dashboard written to {result['out']} ({result['runs']} runs, {result['bytes'] / 1024:.0f} KB)")
    if not history.exists():
        print(f"note: history folder {history} does not exist yet; run pytest first", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
