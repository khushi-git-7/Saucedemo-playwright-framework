"""The handful of numbers the landing page shows, taken from merged runs."""

from __future__ import annotations

from utils.dashboard import metrics


def browsers_seen(runs: list) -> list:
    """Distinct browser names across every run, in first-seen order.

    A run merged from several CI jobs carries them joined ("chromium, firefox"),
    so the field is split before counting.
    """
    seen = []
    for run in runs:
        for name in str(run.get("browser") or "").split(","):
            name = name.strip()
            if name and name not in seen:
                seen.append(name)
    return seen


def site_stats(runs: list):
    """Stats for the strip, or None when there is no run to report on.

    * tests / pass_rate / median_duration describe the latest run
      (metrics.run_stats, the same numbers as the dashboard's overview tiles).
    * runs is the number of merged runs in the history.
    * browsers is every engine seen across the history.
    * green_streak is how many of the latest runs in a row had no failure.
    """
    if not runs:
        return None
    latest = metrics.run_stats(runs[-1])
    return {
        "tests": latest["total"],
        "pass_rate": latest["pass_rate"],
        "failed": latest["failed"] + latest["error"],
        "median_duration": latest["median_duration"],
        "runs": len(runs),
        "browsers": browsers_seen(runs),
        "green_streak": metrics.green_streak(runs),
        "timestamp": latest["timestamp"],
    }
