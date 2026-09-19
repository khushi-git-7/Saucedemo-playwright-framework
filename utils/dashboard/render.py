"""Renders the merged runs into one self-contained HTML page.

Everything is inline: CSS tokens, SVG charts (see charts.py) and a small
vanilla-JS layer for tooltips, the crosshair, the theme toggle and the run
drill-down. No external scripts, fonts or stylesheets, so the file works when
opened from disk, as a CI artifact and as a GitHub Pages site.
"""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone

from utils.dashboard import charts, metrics
from utils.dashboard.insights import compute_insights

MARKER_ORDER = ["smoke", "regression", "e2e", "ui", "api"]
SPARK_POINTS = 12


# ---------------------------------------------------------------------------
# formatting helpers
# ---------------------------------------------------------------------------
def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def fmt_seconds(value) -> str:
    if value is None:
        return "n/a"
    value = float(value)
    if value < 1:
        return f"{value * 1000:.0f} ms"
    if value < 60:
        return f"{value:.2f} s" if value < 10 else f"{value:.1f} s"
    minutes, seconds = divmod(value, 60)
    return f"{int(minutes)}m {seconds:02.0f}s"


def fmt_pct(value) -> str:
    return "n/a" if value is None else f"{float(value):.1f}%"


def parse_ts(text: str) -> datetime:
    try:
        stamp = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp


def fmt_ts(text: str, style: str = "long") -> str:
    stamp = parse_ts(text).astimezone(timezone.utc)
    if style == "short":
        return stamp.strftime("%d %b %H:%M")
    return stamp.strftime("%Y-%m-%d %H:%M UTC")


def short_name(nodeid: str) -> str:
    return nodeid.rsplit("::", 1)[-1]


def module_of(nodeid: str) -> str:
    return nodeid.split("::", 1)[0]


def signed(value: float, unit: str = "", digits: int = 1) -> str:
    if value is None:
        return ""
    text = f"{value:+.{digits}f}".rstrip("0").rstrip(".") if digits else f"{int(round(value)):+d}"
    if text in ("+0", "-0", "+", "-"):
        text = "0"
    return f"{text}{unit}"


def artifact_kind(path: str) -> str:
    lower = path.lower()
    if lower.endswith((".png", ".jpg", ".jpeg")):
        return "screenshot"
    if lower.endswith(".zip"):
        return "trace"
    if lower.endswith((".webm", ".mp4")):
        return "video"
    return "file"


def chip(text: str, kind: str = "") -> str:
    return f'<span class="chip {esc(kind)}">{esc(text)}</span>'


def outcome_chip(outcome: str) -> str:
    return chip(charts.OUTCOME_LABEL.get(outcome, outcome), f"o-{outcome}")


def info(rule: str) -> str:
    return f'<span class="info" tabindex="0" data-tip="{charts.tip_attr("How this is computed", [["", rule]])}" aria-label="{esc(rule)}">?</span>'


def table_view(headers: list, rows: list, summary: str = "Table view") -> str:
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in row) + "</tr>" for row in rows)
    return f'<details class="tbl"><summary>{esc(summary)}</summary><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></details>'


# ---------------------------------------------------------------------------
# sections
# ---------------------------------------------------------------------------
def kpi_tile(label: str, value: str, delta_text: str, delta_class: str, spark_values: list, rule: str) -> str:
    return (
        '<div class="tile">'
        f'<div class="tile-label">{esc(label)} {info(rule)}</div>'
        f'<div class="tile-row"><div class="tile-value">{esc(value)}</div>{charts.sparkline(spark_values[-SPARK_POINTS:])}</div>'
        f'<div class="tile-delta {delta_class}">{esc(delta_text) if delta_text else "&nbsp;"}</div>'
        "</div>"
    )


def render_overview(runs: list, flaky_rows: list) -> str:
    stats = [metrics.run_stats(r) for r in runs]
    latest = stats[-1]
    previous = stats[-2] if len(stats) > 1 else None

    def delta_of(key):
        return metrics.delta(latest[key], previous[key]) if previous else None

    def delta_class(change, up_is_good):
        if change is None or abs(change) < 1e-9 or up_is_good is None:
            return "neutral"
        return "good" if (change > 0) == up_is_good else "bad"

    flaky_count = sum(1 for r in flaky_rows if r["flaky"])
    failed_now = latest["failed"] + latest["error"]
    failed_series = [s["failed"] + s["error"] for s in stats]
    failed_delta = (failed_now - (previous["failed"] + previous["error"])) if previous else None

    pr_delta = delta_of("pass_rate")
    med_delta = delta_of("median_duration")
    wall_delta = delta_of("wall_seconds")
    total_delta = delta_of("total")

    def delta_text(change, unit: str = "", digits: int = 1, scale: float = 1.0) -> str:
        if previous is None:
            return "first run"
        if change is None:  # one of the two runs has no value, e.g. every test skipped
            return "no previous value to compare"
        return signed(change * scale, unit, digits) + " vs previous run"

    tiles = [
        kpi_tile("Pass rate", fmt_pct(latest["pass_rate"]), delta_text(pr_delta, " pts"), delta_class(pr_delta, True), [s["pass_rate"] for s in stats], "passed / (passed + failed + error). Skipped tests are excluded from the denominator. Delta is against the previous run."),
        kpi_tile("Total tests", str(latest["total"]), delta_text(total_delta, "", 0), delta_class(total_delta, None), [s["total"] for s in stats], "Number of test cases in the latest run, including skipped ones."),
        kpi_tile("Failed", str(failed_now), delta_text(failed_delta, "", 0), delta_class(failed_delta, False), failed_series, "Tests whose outcome was failed (assertion in the test body) or error (setup / teardown)."),
        kpi_tile("Flaky tests", str(flaky_count), f"{len(flaky_rows)} changed outcome at least once" if flaky_rows else "no outcome changes in window", "neutral", [], f"Tests whose outcome flipped between pass and fail at least {metrics.FLAKY_MIN_FLIPS} times within the last {metrics.FLAKY_WINDOW} runs they appeared in."),
        kpi_tile("Median test duration", fmt_seconds(latest["median_duration"]), delta_text(med_delta, " ms", 0, scale=1000), delta_class(med_delta, False), [s["median_duration"] for s in stats], "Median of setup + call + teardown time per test in the latest run."),
        kpi_tile("Suite time", fmt_seconds(latest["wall_seconds"]), delta_text(wall_delta, " s"), delta_class(wall_delta, False), [s["wall_seconds"] for s in stats], "Wall-clock time of the pytest session. For a run merged from parallel CI jobs it is the longest job."),
    ]
    return '<div class="tiles">' + "".join(tiles) + "</div>"


def render_insights(insights: list) -> str:
    items = []
    for item in insights:
        items.append(
            f'<li class="insight {esc(item["severity"])}"><span class="dot"></span>'
            f'<span class="insight-text">{esc(item["text"])}</span>{info(item["rule"])}</li>'
        )
    return '<ul class="insights">' + "".join(items) + "</ul>"


def render_trends(runs: list) -> str:
    stats = [metrics.run_stats(r) for r in runs]
    labels = [fmt_ts(s["timestamp"], "short") for s in stats]

    pr_tips = [
        (f"Run #{i + 1} - {fmt_ts(s['timestamp'])}", [["Pass rate", fmt_pct(s["pass_rate"]), "v"], ["Passed", str(s["passed"]), "c-pass"], ["Failed", str(s["failed"] + s["error"]), "c-fail"], ["Skipped", str(s["skipped"]), "c-skip"]])
        for i, s in enumerate(stats)
    ]
    pass_chart = charts.line_chart("chart-pass", labels, [s["pass_rate"] for s in stats], pr_tips, y_max=100.0, y_min=0.0, y_format=lambda v: f"{v:.0f}%")

    dur_tips = [
        (f"Run #{i + 1} - {fmt_ts(s['timestamp'])}", [["Suite time", fmt_seconds(s["wall_seconds"]), "v"], ["Sum of test durations", fmt_seconds(s["test_time"])], ["Median test", fmt_seconds(s["median_duration"])], ["p95 test", fmt_seconds(s["p95_duration"])]])
        for i, s in enumerate(stats)
    ]
    dur_chart = charts.line_chart("chart-dur", labels, [s["wall_seconds"] for s in stats], dur_tips, y_format=lambda v: fmt_seconds(v) if v < 60 else f"{v / 60:.1f} m")

    stacks = [{"passed": s["passed"], "failed": s["failed"], "error": s["error"], "skipped": s["skipped"]} for s in stats]
    stack_tips = [
        (f"Run #{i + 1} - {fmt_ts(s['timestamp'])}", [["Passed", str(s["passed"]), "c-pass"], ["Failed", str(s["failed"]), "c-fail"], ["Error", str(s["error"]), "c-error"], ["Skipped", str(s["skipped"]), "c-skip"], ["Total", str(s["total"]), "v"]])
        for i, s in enumerate(stats)
    ]
    stack_chart = charts.stacked_bars(labels, stacks, stack_tips)
    legend = (
        '<div class="legend">'
        '<span><i class="sw c-pass"></i>Passed</span><span><i class="sw c-fail"></i>Failed</span>'
        '<span><i class="sw c-error"></i>Error</span><span><i class="sw c-skip"></i>Skipped</span></div>'
    )
    table_rows = [[f"#{i + 1}", fmt_ts(s["timestamp"]), fmt_pct(s["pass_rate"]), s["passed"], s["failed"], s["error"], s["skipped"], fmt_seconds(s["wall_seconds"])] for i, s in enumerate(stats)]
    table = table_view(["Run", "Started", "Pass rate", "Passed", "Failed", "Error", "Skipped", "Suite time"], table_rows)

    return (
        '<div class="grid two">'
        f'<div class="card"><div class="card-head"><h3>Pass rate over runs</h3>{info("Pass rate of each run, oldest to newest. Hover for the outcome counts.")}</div>{pass_chart}{table}</div>'
        f'<div class="card"><div class="card-head"><h3>Suite time over runs</h3>{info("Wall-clock time of each pytest session. Hover for the median and p95 test duration.")}</div>{dur_chart}{table}</div>'
        "</div>"
        f'<div class="card"><div class="card-head"><h3>Outcomes per run</h3>{legend}</div>{stack_chart}{table}</div>'
    )


def _hbar_rows(rows: list) -> list:
    out = []
    for row in rows:
        out.append(
            {
                "name": row["name"],
                "value": row["pass_rate"],
                "tip": (str(row["name"]), [["Pass rate", fmt_pct(row["pass_rate"]), "v"], ["Passed", str(row["passed"]), "c-pass"], ["Failed", str(row["failed"] + row["error"]), "c-fail"], ["Skipped", str(row["skipped"]), "c-skip"], ["Tests", str(row["total"])]]),
            }
        )
    return out


def render_breakdown(runs: list) -> str:
    latest = runs[-1]
    by_marker = metrics.breakdown(latest, "markers", MARKER_ORDER)
    by_area = metrics.breakdown(latest, "area")
    slow = metrics.slowest_tests(runs, limit=10)

    def bd_table(rows):
        return table_view(["Group", "Pass rate", "Passed", "Failed", "Error", "Skipped", "Tests"], [[r["name"], fmt_pct(r["pass_rate"]), r["passed"], r["failed"], r["error"], r["skipped"], r["total"]] for r in rows])

    slow_rows = "".join(
        f'<tr><td><div class="tname">{esc(short_name(r["nodeid"]))}</div><div class="tmod">{esc(module_of(r["nodeid"]))}</div></td>'
        f'<td>{chip(r["layer"], "layer")}</td><td class="num">{r["runs"]}</td><td class="num">{esc(fmt_seconds(r["p50"]))}</td>'
        f'<td class="num strong">{esc(fmt_seconds(r["p95"]))}</td><td class="num">{esc(fmt_seconds(r["max"]))}</td><td class="num">{esc(fmt_seconds(r["last"]))}</td></tr>'
        for r in slow
    )
    return (
        '<div class="grid two">'
        f'<div class="card"><div class="card-head"><h3>Pass rate by marker</h3>{info("Latest run, grouped by pytest marker. A test with several markers counts under each of them.")}</div>{charts.hbar_chart(_hbar_rows(by_marker))}{bd_table(by_marker)}</div>'
        f'<div class="card"><div class="card-head"><h3>Pass rate by page area</h3>{info("Latest run, grouped by test module: tests/test_checkout.py becomes checkout, api/test_posts_api.py becomes posts.")}</div>{charts.hbar_chart(_hbar_rows(by_area))}{bd_table(by_area)}</div>'
        "</div>"
        f'<div class="card"><div class="card-head"><h3>Slowest tests</h3>{info("Nearest-rank p50 / p95 of each test\'s total duration (setup + call + teardown) across every run it appeared in. Sorted by p95.")}</div>'
        '<table class="data"><thead><tr><th>Test</th><th>Layer</th><th class="num">Runs</th><th class="num">p50</th><th class="num">p95</th><th class="num">Max</th><th class="num">Last</th></tr></thead>'
        f"<tbody>{slow_rows}</tbody></table></div>"
    )


def render_flakiness(runs: list, flaky_rows: list) -> str:
    window_runs = runs[-metrics.FLAKY_WINDOW:]
    first_index = len(runs) - len(window_runs)
    run_labels = [f"Run #{first_index + i + 1} - {fmt_ts(r['timestamp'])}" for i, r in enumerate(window_runs)]

    rows_html = []
    for row in flaky_rows:
        by_index = dict(row["outcomes"])
        cells = [by_index.get(first_index + i) for i in range(len(window_runs))]
        badge = chip("Flaky", "o-failed") if row["flaky"] else chip("Changed once", "o-skipped")
        rows_html.append(
            f'<tr><td><div class="tname">{esc(short_name(row["nodeid"]))}</div><div class="tmod">{esc(module_of(row["nodeid"]))}</div></td>'
            f'<td>{chip(row["layer"], "layer")}</td><td class="num strong">{row["flips"]}</td><td class="num">{row["fail_count"]} / {row["runs_seen"]}</td>'
            f'<td>{charts.outcome_strip(cells, run_labels)}</td><td>{badge}</td></tr>'
        )
    body = "".join(rows_html) or '<tr><td colspan="6" class="empty">No test changed outcome in the last runs.</td></tr>'
    legend = (
        '<div class="legend"><span><i class="sw c-pass"></i>Passed</span><span><i class="sw c-fail"></i>Failed</span>'
        '<span><i class="sw c-error"></i>Error</span><span><i class="sw c-skip"></i>Skipped</span><span><i class="sw c-absent"></i>Not run</span></div>'
    )
    rule = (
        f"A test is flaky when its outcome flipped between pass and fail at least {metrics.FLAKY_MIN_FLIPS} times "
        f"within the last {metrics.FLAKY_WINDOW} runs it appeared in. Skipped runs are ignored. One flip is a "
        "regression or a fix, so it is listed as 'changed once' rather than flaky."
    )
    return (
        f'<div class="card"><div class="card-head"><h3>Outcome timeline (last {len(window_runs)} runs)</h3>{info(rule)}{legend}</div>'
        '<table class="data"><thead><tr><th>Test</th><th>Layer</th><th class="num">Flips</th><th class="num">Failures</th><th>Timeline (oldest to newest)</th><th>Status</th></tr></thead>'
        f"<tbody>{body}</tbody></table></div>"
    )


def render_failures(runs: list, artifact_base: str, artifact_root=None) -> str:
    """Failure cards for the latest run.

    Artifact links are ``artifact_base/<repo-relative path>``. When
    *artifact_root* is given, only files that exist under it are linked; the
    rest are named in plain text with a link to the CI run they were uploaded
    to, so a page published without its artifacts (GitHub Pages) never shows
    a dead link.
    """
    latest = runs[-1]
    failed = metrics.failures(latest)
    if not failed:
        return f'<div class="card"><p class="empty">No failures in the latest run ({fmt_ts(latest["timestamp"])}).</p></div>'
    base = artifact_base.rstrip("/") + "/" if artifact_base else ""
    ci_url = (latest.get("ci") or {}).get("url") or ""
    cards = []
    for test in failed:
        available, missing = [], []
        for path in test.get("artifacts", []):
            if artifact_root is None or (artifact_root / path).is_file():
                available.append(path)
            else:
                missing.append(path)
        parts = [f'<a class="alink" href="{esc(base + path)}">{esc(artifact_kind(path))}</a>' for path in available]
        if missing:
            note = ", ".join(artifact_kind(path) for path in missing) + " not published with this page"
            if ci_url:
                note += f' - <a href="{esc(ci_url)}">download from the CI run</a>'
            parts.append(f'<span class="muted">{note}</span>')
        if parts:
            links_html = '<div class="fail-links">Artifacts: ' + " ".join(parts) + "</div>"
        else:
            links_html = '<div class="fail-links muted">No artifacts captured for this test.</div>'
        details = test.get("details") or ""
        detail_html = f'<details class="trace"><summary>Traceback</summary><pre>{esc(details)}</pre></details>' if details else ""
        cards.append(
            '<div class="fail">'
            f'<div class="fail-head">{outcome_chip(test["outcome"])}<div><div class="tname">{esc(short_name(test["nodeid"]))}</div><div class="tmod">{esc(module_of(test["nodeid"]))}</div></div>'
            f'<div class="fail-meta">{chip("phase: " + str(test.get("phase") or "call"))}{chip(fmt_seconds(test.get("duration")))}{"".join(chip(m, "layer") for m in test.get("markers", []))}</div></div>'
            f'<div class="fail-msg">{esc(test.get("message") or "(no message)")}</div>'
            f"{links_html}{detail_html}</div>"
        )
    return f'<div class="card"><div class="card-head"><h3>{len(failed)} failing in the latest run</h3><span class="muted">{esc(fmt_ts(latest["timestamp"]))}</span></div>' + "".join(cards) + "</div>"


def render_runs(runs: list, repo_url: str) -> str:
    rows = []
    for i, run in enumerate(reversed(runs)):
        index = len(runs) - i
        stats = metrics.run_stats(run)
        sha = (run.get("git") or {}).get("sha", "") or ""
        branch = (run.get("git") or {}).get("branch", "") or ""
        sha_html = f'<a href="{esc(repo_url.rstrip("/") + "/commit/" + sha)}">{esc(sha[:7])}</a>' if sha and repo_url else esc(sha[:7] or "-")
        ci = run.get("ci") or {}
        ci_html = f'<a href="{esc(ci["url"])}">#{esc(ci.get("run_number") or ci.get("run_id"))}</a>' if ci.get("url") else '<span class="muted">local</span>'
        rows.append(
            f'<tr class="run-row" data-run="{index - 1}" tabindex="0" aria-expanded="false">'
            f'<td class="num">{index}</td><td>{esc(fmt_ts(run["timestamp"]))}</td><td>{esc(run.get("suite") or "-")}</td>'
            f'<td>{sha_html}<div class="tmod">{esc(branch)}</div></td><td>{esc(run.get("browser") or "-")}</td><td class="num">{esc(run.get("workers", 1))}</td>'
            f'<td class="num strong">{esc(fmt_pct(stats["pass_rate"]))}</td>'
            f'<td class="num"><span class="c-pass-text">{stats["passed"]}</span> / <span class="c-fail-text">{stats["failed"] + stats["error"]}</span> / <span class="muted">{stats["skipped"]}</span></td>'
            f'<td class="num">{esc(fmt_seconds(stats["wall_seconds"]))}</td><td>{ci_html}</td></tr>'
            f'<tr class="run-detail" hidden><td colspan="10"><div class="detail-host" data-run="{index - 1}"></div></td></tr>'
        )
    return (
        f'<div class="card"><div class="card-head"><h3>All runs</h3>{info("One row per logical run, newest first. Pytest invocations that share a run group (for example the UI and API jobs of one CI workflow) are merged into a single run. Click a row to see every test in that run.")}</div>'
        '<table class="data runs"><thead><tr><th class="num">#</th><th>Started</th><th>Suite</th><th>Commit</th><th>Browser</th><th class="num">Workers</th><th class="num">Pass rate</th><th class="num">Pass / fail / skip</th><th class="num">Suite time</th><th>CI</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
    )


def run_data(runs: list) -> str:
    """Compact per-test outcomes for the run drill-down (rendered client side)."""
    data = []
    for run in runs:
        data.append(
            {
                "id": run["run_id"],
                "ts": run["timestamp"],
                "tests": [
                    {
                        "n": t["nodeid"],
                        "o": t.get("outcome", ""),
                        "d": round(float(t.get("duration") or 0.0), 3),
                        "p": t.get("phase") or "",
                        "m": (t.get("message") or "")[:200],
                        "l": t.get("layer", ""),
                        "w": t.get("worker") or "",
                    }
                    for t in run.get("tests", [])
                ],
            }
        )
    # A "<" inside a script element could start "</script>" or "<!--", so it
    # is written as the JSON escape <, which JSON.parse turns back.
    return json.dumps(data, separators=(",", ":")).replace("<", "\\u003c")


# ---------------------------------------------------------------------------
# page
# ---------------------------------------------------------------------------
CSS = r"""
:root{color-scheme:light;
--bg:#f9f9f7;--surface:#fcfcfb;--surface-2:#f3f3f0;--surface-3:#ebebe7;--border:rgba(11,11,11,.10);--border-strong:rgba(11,11,11,.18);
--text:#0b0b0b;--text-2:#52514e;--muted:#898781;--grid:#e1e0d9;--axis:#c3c2b7;
--series:#2a78d6;--series-wash:rgba(42,120,214,.10);--track:#cde2fb;--accent:#2a78d6;--accent-wash:rgba(42,120,214,.12);
--ok:#0ca30c;--ok-text:#006300;--warn:#fab219;--serious:#ec835a;--crit:#d03b3b;--crit-text:#b32b2b;--skip:#898781;--absent:#d9d8d2;
--shadow:0 1px 2px rgba(11,11,11,.05);--radius:8px;--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;
--bg:#0d0d0d;--surface:#1a1a19;--surface-2:#232322;--surface-3:#2c2c2a;--border:rgba(255,255,255,.10);--border-strong:rgba(255,255,255,.2);
--text:#ffffff;--text-2:#c3c2b7;--muted:#898781;--grid:#2c2c2a;--axis:#383835;
--series:#3987e5;--series-wash:rgba(57,135,229,.14);--track:#184f95;--accent:#3987e5;--accent-wash:rgba(57,135,229,.18);
--ok-text:#0ca30c;--crit-text:#e66767;--absent:#383835;--shadow:none}}
:root[data-theme="dark"]{color-scheme:dark;
--bg:#0d0d0d;--surface:#1a1a19;--surface-2:#232322;--surface-3:#2c2c2a;--border:rgba(255,255,255,.10);--border-strong:rgba(255,255,255,.2);
--text:#ffffff;--text-2:#c3c2b7;--muted:#898781;--grid:#2c2c2a;--axis:#383835;
--series:#3987e5;--series-wash:rgba(57,135,229,.14);--track:#184f95;--accent:#3987e5;--accent-wash:rgba(57,135,229,.18);
--ok-text:#0ca30c;--crit-text:#e66767;--absent:#383835;--shadow:none}
*{box-sizing:border-box}
html{scroll-behavior:smooth;scroll-padding-top:64px}
body{margin:0;background:var(--bg);color:var(--text);font:13px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
.app{display:grid;grid-template-columns:220px minmax(0,1fr);min-height:100vh}
.sidebar{position:sticky;top:0;height:100vh;background:var(--surface);border-right:1px solid var(--border);display:flex;flex-direction:column;padding:16px 12px}
.brand{display:flex;align-items:center;gap:10px;padding:4px 8px 16px}
.brand .logo{width:28px;height:28px;border-radius:7px;background:var(--accent);color:#fff;display:grid;place-items:center;font-weight:700;font-size:14px}
.brand b{display:block;font-size:14px}.brand span{display:block;color:var(--muted);font-size:11px}
.nav a{display:flex;align-items:center;gap:8px;padding:7px 10px;border-radius:6px;color:var(--text-2);font-weight:500}
.nav a:hover{background:var(--surface-2);text-decoration:none;color:var(--text)}
.nav a.active{background:var(--accent-wash);color:var(--text)}
.nav a .k{width:6px;height:6px;border-radius:50%;background:var(--axis)}.nav a.active .k{background:var(--accent)}
.side-foot{margin-top:auto;padding:8px 10px;font-size:11px;color:var(--muted);display:grid;gap:4px}
.side-foot a{display:block}
main{padding:0 28px 48px;min-width:0}
.topbar{position:sticky;top:0;z-index:5;background:var(--bg);display:flex;align-items:center;gap:16px;padding:14px 0 12px;border-bottom:1px solid var(--border);margin-bottom:20px}
.topbar h1{font-size:18px;margin:0;font-weight:600}
.topbar .meta{color:var(--text-2);font-size:12px;display:flex;flex-wrap:wrap;gap:6px 14px}
.topbar .meta b{color:var(--text);font-weight:500}
.spacer{flex:1}
.btn{background:var(--surface);border:1px solid var(--border-strong);color:var(--text);border-radius:6px;padding:5px 10px;font:inherit;font-size:12px;cursor:pointer}
.btn:hover{background:var(--surface-2)}
section{margin-bottom:36px}
section>h2{font-size:15px;font-weight:600;margin:0 0 12px;display:flex;align-items:center;gap:8px}
section>h2 .sub{font-weight:400;color:var(--muted);font-size:12px}
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow);padding:14px 16px 12px;margin-bottom:16px;min-width:0}
.card-head{display:flex;align-items:center;gap:8px;margin-bottom:8px;flex-wrap:wrap}
.card-head h3{font-size:13px;font-weight:600;margin:0}
.grid.two{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:16px}
.grid.two>.card{margin-bottom:16px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}
.tile{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow);padding:12px 14px 10px;min-width:0}
.tile-label{color:var(--text-2);font-size:12px;display:flex;align-items:center;gap:6px}
.tile-row{display:flex;align-items:flex-end;justify-content:space-between;gap:8px;margin-top:6px}
.tile-value{font-size:26px;font-weight:600;letter-spacing:-.01em;line-height:1.1;white-space:nowrap}
.tile-delta{font-size:11px;color:var(--muted);margin-top:6px}
.tile-delta.good{color:var(--ok-text)}.tile-delta.bad{color:var(--crit-text)}
.spark{flex:0 0 auto}
.spark-line{fill:none;stroke:var(--axis);stroke-width:1.5;stroke-linejoin:round;stroke-linecap:round}
.spark-dot{fill:var(--series);stroke:var(--surface);stroke-width:2}
.chart{width:100%;height:auto;display:block;font-size:11px}
.chart .grid{stroke:var(--grid);stroke-width:1}.chart .axis{stroke:var(--axis);stroke-width:1}
.chart .ax{fill:var(--muted);font-size:11px}.chart .lbl{fill:var(--text-2);font-size:11.5px}.chart .val{fill:var(--text);font-size:11.5px;font-variant-numeric:tabular-nums}
.chart .endlabel{fill:var(--text);font-size:11.5px;font-weight:600}
.chart .line{fill:none;stroke:var(--series);stroke-width:2;stroke-linejoin:round;stroke-linecap:round}
.chart .area{fill:var(--series-wash)}
.chart .dot{fill:var(--series);stroke:var(--surface);stroke-width:2;transition:r .1s}
.chart .dot.on{r:5.5}
.chart .xhair{stroke:var(--axis);stroke-width:1}
.chart .hit{fill:transparent;outline:none;cursor:crosshair}
.chart .bar .hit{cursor:pointer}
.chart .bar:hover rect:not(.hit),.chart .bar:focus rect:not(.hit){filter:brightness(1.12)}
.chart .track{fill:var(--track);opacity:.45}
.c-pass{fill:var(--ok)}.c-fail{fill:var(--crit)}.c-error{fill:var(--serious)}.c-skip{fill:var(--skip)}
.c-absent{fill:none;stroke:var(--absent);stroke-width:1}
.c-line-fill{fill:var(--series)}
.c-pass-text{color:var(--ok-text);font-weight:600}.c-fail-text{color:var(--crit-text);font-weight:600}
.strip{display:block}.strip rect{cursor:default}
.legend{display:flex;gap:12px;flex-wrap:wrap;font-size:11.5px;color:var(--text-2);margin-left:auto}
.legend span{display:inline-flex;align-items:center;gap:5px}
.sw{display:inline-block;width:10px;height:10px;border-radius:2px;background:currentColor}
.sw.c-pass{background:var(--ok)}.sw.c-fail{background:var(--crit)}.sw.c-error{background:var(--serious)}.sw.c-skip{background:var(--skip)}.sw.c-absent{background:none;border:1px solid var(--absent)}
table.data{width:100%;border-collapse:collapse;font-size:12.5px}
table.data th{text-align:left;color:var(--muted);font-weight:500;font-size:11.5px;padding:6px 8px;border-bottom:1px solid var(--border);white-space:nowrap}
table.data td{padding:7px 8px;border-bottom:1px solid var(--border);vertical-align:middle}
table.data tr:last-child td{border-bottom:none}
table.data .num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
table.data .strong{font-weight:600}
.tname{font-weight:500}.tmod{color:var(--muted);font-size:11px;font-family:var(--mono)}
.chip{display:inline-block;padding:1px 7px;border-radius:999px;font-size:11px;background:var(--surface-3);color:var(--text-2);margin-right:4px;white-space:nowrap}
.chip.layer{background:var(--accent-wash);color:var(--text)}
.chip.o-passed{background:rgba(12,163,12,.14);color:var(--ok-text)}.chip.o-failed{background:rgba(208,59,59,.14);color:var(--crit-text)}
.chip.o-error{background:rgba(236,131,90,.18);color:var(--text)}.chip.o-skipped{background:var(--surface-3);color:var(--text-2)}
.muted{color:var(--muted)}.empty{color:var(--muted);text-align:center;padding:14px}
.info{display:inline-grid;place-items:center;width:15px;height:15px;border-radius:50%;border:1px solid var(--border-strong);color:var(--muted);font-size:10px;font-weight:600;cursor:help;flex:0 0 auto;line-height:1}
.info:focus{outline:2px solid var(--accent);outline-offset:1px}
.insights{list-style:none;margin:0;padding:0;display:grid;gap:8px}
.insight{display:flex;align-items:flex-start;gap:10px;padding:10px 12px;border:1px solid var(--border);border-radius:var(--radius);background:var(--surface)}
.insight .dot{width:8px;height:8px;border-radius:50%;margin-top:5px;flex:0 0 auto;background:var(--axis)}
.insight.good .dot{background:var(--ok)}.insight.warning .dot{background:var(--warn)}.insight.critical .dot{background:var(--crit)}.insight.info .dot{background:var(--series)}
.insight-text{flex:1}
.fail{border-top:1px solid var(--border);padding:12px 0}
.fail-head{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.fail-meta{margin-left:auto}
.fail-msg{font-family:var(--mono);font-size:12px;background:var(--surface-2);border-radius:6px;padding:8px 10px;margin-top:8px;white-space:pre-wrap;word-break:break-word}
.fail-links{margin-top:6px;font-size:12px}.alink{margin-right:10px}
details.trace{margin-top:6px}details.trace summary,details.tbl summary{cursor:pointer;color:var(--muted);font-size:11.5px}
details.trace pre{font-family:var(--mono);font-size:11.5px;background:var(--surface-2);padding:10px;border-radius:6px;overflow:auto;max-height:360px;margin:6px 0 0}
details.tbl{margin-top:6px}details.tbl table{width:100%;border-collapse:collapse;font-size:12px;margin-top:6px}
details.tbl th,details.tbl td{text-align:left;padding:4px 8px;border-bottom:1px solid var(--border);font-variant-numeric:tabular-nums}
tr.run-row{cursor:pointer}tr.run-row:hover td{background:var(--surface-2)}tr.run-row:focus{outline:2px solid var(--accent);outline-offset:-2px}
tr.run-row[aria-expanded="true"] td{background:var(--accent-wash)}
.detail-host{padding:6px 0 4px}
.detail-host .sum{display:flex;gap:14px;font-size:12px;color:var(--text-2);margin:0 0 6px 8px;flex-wrap:wrap}
.detail-host table{width:100%;border-collapse:collapse;font-size:12px}
.detail-host th{text-align:left;color:var(--muted);font-weight:500;padding:4px 8px;border-bottom:1px solid var(--border)}
.detail-host td{padding:4px 8px;border-bottom:1px solid var(--border)}
.detail-host .mono{font-family:var(--mono);font-size:11.5px}
#tip{position:fixed;z-index:50;pointer-events:none;display:none;background:var(--surface);color:var(--text);border:1px solid var(--border-strong);border-radius:6px;padding:8px 10px;font-size:12px;box-shadow:0 4px 16px rgba(0,0,0,.18);max-width:320px}
#tip .tt{font-weight:600;margin-bottom:4px;color:var(--text)}
#tip .tr{display:flex;gap:10px;justify-content:space-between;align-items:baseline}
#tip .tr .tl{color:var(--text-2);display:inline-flex;align-items:center;gap:6px}
#tip .tr .tv{font-weight:600;font-variant-numeric:tabular-nums;white-space:nowrap}
#tip .tr .tv.v{font-size:13px}
#tip .key{display:inline-block;width:10px;height:3px;border-radius:2px;background:var(--axis)}
#tip .key.c-pass{background:var(--ok)}#tip .key.c-fail{background:var(--crit)}#tip .key.c-error{background:var(--serious)}#tip .key.c-skip{background:var(--skip)}
#tip .rule{white-space:normal;color:var(--text-2);font-weight:400}
.table-wrap{overflow-x:auto}
@media (max-width:900px){
.app{grid-template-columns:1fr}
.sidebar{position:static;height:auto;border-right:none;border-bottom:1px solid var(--border);padding:10px 16px}
.nav{display:flex;flex-wrap:wrap;gap:2px}.nav a{padding:5px 8px}.side-foot{display:none}
main{padding:0 16px 32px}.topbar{position:static}
.grid.two{grid-template-columns:1fr}
}
"""

JS = r"""
(function(){
var root=document.documentElement;
function readTheme(){try{return localStorage.getItem('tv-theme')||'auto'}catch(e){return 'auto'}}
function applyTheme(t){if(t==='auto'){root.removeAttribute('data-theme')}else{root.setAttribute('data-theme',t)}
var b=document.getElementById('theme');if(b){b.textContent='Theme: '+t}}
applyTheme(readTheme());
var themeBtn=document.getElementById('theme');
if(themeBtn){themeBtn.addEventListener('click',function(){var order=['auto','light','dark'];var next=order[(order.indexOf(readTheme())+1)%3];try{localStorage.setItem('tv-theme',next)}catch(e){}applyTheme(next)})}

var tip=document.getElementById('tip');
function showTip(el,x,y){var data;try{data=JSON.parse(el.getAttribute('data-tip'))}catch(e){return}
while(tip.firstChild){tip.removeChild(tip.firstChild)}
if(data.t){var h=document.createElement('div');h.className='tt';h.textContent=data.t;tip.appendChild(h)}
(data.r||[]).forEach(function(r){var row=document.createElement('div');row.className='tr';
if(r[0]===''){var s=document.createElement('div');s.className='rule';s.textContent=r[1];row.appendChild(s);tip.appendChild(row);return}
var l=document.createElement('span');l.className='tl';if(r[2]&&r[2]!=='v'){var k=document.createElement('i');k.className='key '+r[2];l.appendChild(k)}
l.appendChild(document.createTextNode(r[0]));var v=document.createElement('span');v.className='tv'+(r[2]==='v'?' v':'');v.textContent=r[1];row.appendChild(l);row.appendChild(v);tip.appendChild(row)});
tip.style.display='block';moveTip(x,y)}
function moveTip(x,y){var w=tip.offsetWidth,h=tip.offsetHeight,vw=window.innerWidth,vh=window.innerHeight;var left=x+14,top=y+14;
if(left+w>vw-8){left=x-w-14}if(top+h>vh-8){top=y-h-14}if(left<8){left=8}if(top<8){top=8}tip.style.left=left+'px';tip.style.top=top+'px'}
function hideTip(){tip.style.display='none'}
function crosshair(el,on){var svg=el.closest('svg');if(!svg||!el.classList.contains('hit')||!el.hasAttribute('data-x')){return}
var x=svg.querySelector('.xhair');var i=el.getAttribute('data-i');
if(x){x.style.display=on?'':'none';x.setAttribute('x1',el.getAttribute('data-x'));x.setAttribute('x2',el.getAttribute('data-x'))}
svg.querySelectorAll('.dot.on').forEach(function(d){d.classList.remove('on')});
if(on){var d=svg.querySelector('.dot[data-i="'+i+'"]');if(d){d.classList.add('on')}}}
document.addEventListener('pointerover',function(e){var el=e.target.closest('[data-tip]');if(!el){return}crosshair(el,true);showTip(el,e.clientX,e.clientY)});
document.addEventListener('pointermove',function(e){if(tip.style.display==='block'){moveTip(e.clientX,e.clientY)}});
document.addEventListener('pointerout',function(e){var el=e.target.closest('[data-tip]');if(!el){return}var to=e.relatedTarget;if(to&&el.contains(to)){return}crosshair(el,false);hideTip()});
document.addEventListener('focusin',function(e){var el=e.target.closest('[data-tip]');if(!el){return}var r=el.getBoundingClientRect();crosshair(el,true);showTip(el,r.left+r.width/2,r.top+r.height/2)});
document.addEventListener('focusout',function(e){var el=e.target.closest('[data-tip]');if(el){crosshair(el,false);hideTip()}});
document.addEventListener('keydown',function(e){if(e.key==='Escape'){hideTip()}});

var links=Array.prototype.slice.call(document.querySelectorAll('.nav a'));
var sections=links.map(function(a){return document.querySelector(a.getAttribute('href'))}).filter(Boolean);
if('IntersectionObserver' in window&&sections.length){var current=null;
var obs=new IntersectionObserver(function(entries){entries.forEach(function(en){if(en.isIntersecting){current=en.target.id;links.forEach(function(a){a.classList.toggle('active',a.getAttribute('href')==='#'+current)})}})},{rootMargin:'-64px 0px -70% 0px',threshold:0});
sections.forEach(function(s){obs.observe(s)})}

var runData=[];try{runData=JSON.parse(document.getElementById('run-data').textContent)}catch(e){}
var OUT={passed:'Passed',failed:'Failed',error:'Error',skipped:'Skipped'};
function fmtS(v){if(v<1){return Math.round(v*1000)+' ms'}if(v<60){return v.toFixed(2)+' s'}return Math.floor(v/60)+'m '+Math.round(v%60)+'s'}
function cell(tr,text,cls){var td=document.createElement('td');if(cls){td.className=cls}td.textContent=text;tr.appendChild(td);return td}
function renderDetail(host,run){var counts={passed:0,failed:0,error:0,skipped:0};run.tests.forEach(function(t){counts[t.o]=(counts[t.o]||0)+1});
var sum=document.createElement('div');sum.className='sum';['passed','failed','error','skipped'].forEach(function(k){var s=document.createElement('span');s.textContent=OUT[k]+': '+counts[k];sum.appendChild(s)});host.appendChild(sum);
var table=document.createElement('table');var thead=document.createElement('thead');var hr=document.createElement('tr');['Test','Layer','Outcome','Phase','Duration','Worker','Message'].forEach(function(h){var th=document.createElement('th');th.textContent=h;hr.appendChild(th)});thead.appendChild(hr);table.appendChild(thead);
var tbody=document.createElement('tbody');var order={failed:0,error:1,skipped:2,passed:3};
run.tests.slice().sort(function(a,b){return (order[a.o]-order[b.o])||a.n.localeCompare(b.n)}).forEach(function(t){var tr=document.createElement('tr');cell(tr,t.n,'mono');cell(tr,t.l);
var td=document.createElement('td');var c=document.createElement('span');c.className='chip o-'+t.o;c.textContent=OUT[t.o]||t.o;td.appendChild(c);tr.appendChild(td);
cell(tr,t.p||'');cell(tr,fmtS(t.d));cell(tr,t.w||'');cell(tr,t.m||'','mono');tbody.appendChild(tr)});table.appendChild(tbody);host.appendChild(table)}
function toggleRow(row){var idx=row.getAttribute('data-run');var detail=row.nextElementSibling;var open=row.getAttribute('aria-expanded')==='true';
row.setAttribute('aria-expanded',open?'false':'true');detail.hidden=open;
var host=detail.querySelector('.detail-host');if(!open&&host&&!host.hasChildNodes()&&runData[idx]){renderDetail(host,runData[idx])}}
document.querySelectorAll('tr.run-row').forEach(function(row){row.addEventListener('click',function(e){if(e.target.closest('a')){return}toggleRow(row)});
row.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();toggleRow(row)}})});
})();
"""

NAV = [
    ("overview", "Overview"),
    ("insights", "Insights"),
    ("trends", "Trends"),
    ("breakdown", "Breakdown"),
    ("flakiness", "Flakiness"),
    ("failures", "Failures"),
    ("runs", "Runs"),
]


def render_empty(repo_url: str, links: list) -> str:
    body = (
        '<section id="overview"><h2>Overview</h2><div class="card"><p class="empty">No run history found. '
        "Run <code>python -m pytest</code> once (it writes reports/history/&lt;run&gt;.json) and rebuild with "
        "<code>python -m utils.dashboard</code>.</p></div></section>"
    )
    return page(body, repo_url, links, meta="No runs recorded yet", runs=[])


def page(body: str, repo_url: str, links: list, meta: str, runs: list) -> str:
    nav = "".join(f'<a href="#{key}"><span class="k"></span>{label}</a>' for key, label in NAV)
    link_html = "".join(f'<a href="{esc(href)}">{esc(label)}</a>' for label, href in links)
    built = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>TestVerse Dashboard</title>\n"
        '<meta name="description" content="Test results analytics for the TestVerse Playwright and Pytest framework">\n'
        f"<style>{CSS}</style>\n</head>\n<body>\n"
        '<div class="app">\n<aside class="sidebar">\n'
        '<div class="brand"><div class="logo">T</div><div><b>TestVerse</b><span>Test analytics</span></div></div>\n'
        f'<nav class="nav">{nav}</nav>\n'
        f'<div class="side-foot">{link_html}<a href="{esc(repo_url)}">Source on GitHub</a><span>Built {built}</span></div>\n'
        "</aside>\n<main>\n"
        f'<header class="topbar"><h1>Test results</h1><div class="meta">{meta}</div><div class="spacer"></div>'
        '<button class="btn" id="theme" type="button">Theme: auto</button></header>\n'
        f"{body}\n</main>\n</div>\n"
        '<div id="tip" role="tooltip"></div>\n'
        f'<script id="run-data" type="application/json">{run_data(runs)}</script>\n'
        f"<script>{JS}</script>\n</body>\n</html>\n"
    )


def render_dashboard(runs: list, repo_url: str = "", links: list = None, artifact_base: str = "", artifact_root=None) -> str:
    """The complete page. See render_failures for artifact_base / artifact_root."""
    links = links or []
    if not runs:
        return render_empty(repo_url, links)

    latest = runs[-1]
    flaky_rows = metrics.flakiness(runs)
    insights = compute_insights(runs, flaky_rows)
    git = latest.get("git") or {}
    sha = (git.get("sha") or "")[:7]
    meta = (
        f"<span>Latest run <b>{esc(fmt_ts(latest['timestamp']))}</b></span>"
        f"<span>Commit <b>{esc(sha or 'n/a')}</b>{(' on <b>' + esc(git.get('branch')) + '</b>') if git.get('branch') else ''}</span>"
        f"<span>Browser <b>{esc(latest.get('browser') or 'n/a')}</b></span>"
        f"<span>Suite <b>{esc(latest.get('suite') or 'n/a')}</b></span>"
        f"<span><b>{len(runs)}</b> run{'s' if len(runs) != 1 else ''} in history</span>"
    )

    def section(key: str, title: str, sub: str, content: str) -> str:
        return f'<section id="{key}"><h2>{esc(title)}<span class="sub">{esc(sub)}</span></h2>{content}</section>'

    body = "".join(
        [
            section("overview", "Overview", "latest run vs the one before, sparklines across history", render_overview(runs, flaky_rows)),
            section("insights", "Insights", "generated from the history with the rules shown on hover", render_insights(insights)),
            section("trends", "Trends", "how the suite moves run over run", render_trends(runs)),
            section("breakdown", "Breakdown", "where the latest run passed and where time goes", render_breakdown(runs)),
            section("flakiness", "Flakiness", "tests whose outcome changes without the code changing", render_flakiness(runs, flaky_rows)),
            section("failures", "Failures", "what failed in the latest run and the evidence captured", render_failures(runs, artifact_base, artifact_root)),
            section("runs", "Runs", "every recorded run; click one for its tests", render_runs(runs, repo_url)),
        ]
    )
    return page(body, repo_url, links, meta, runs)
