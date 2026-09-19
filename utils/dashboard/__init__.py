"""Test-results analytics dashboard, built from reports/history/*.json.

    python -m utils.dashboard                 # reads reports/history, writes reports/dashboard.html
    python -m utils.dashboard --help

Standard library only. See loader.py (merging), metrics.py (numbers),
insights.py (plain-English rules), charts.py (inline SVG) and render.py (HTML).
"""

from utils.dashboard.cli import build, main  # noqa: F401

__all__ = ["build", "main"]
