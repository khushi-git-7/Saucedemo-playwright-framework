"""Inline SVG charts, generated in Python with no external libraries.

Every mark is coloured through a CSS class (``.c-pass``, ``.c-line`` ...) that
resolves to a token in the page's stylesheet, so the same SVG follows the
light / dark theme. Hover data travels in ``data-tip`` attributes holding a
small JSON payload that the page's vanilla JavaScript turns into a tooltip;
the tooltip never gates a value - every chart also has a table view.
"""

from __future__ import annotations

import html
import json

OUTCOME_CLASS = {"passed": "c-pass", "failed": "c-fail", "error": "c-error", "skipped": "c-skip"}
OUTCOME_LABEL = {"passed": "Passed", "failed": "Failed", "error": "Error", "skipped": "Skipped"}


def _n(value: float) -> str:
    """Compact float for SVG attributes."""
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return text if text not in ("", "-0") else "0"


def tip_attr(title: str, rows: list) -> str:
    """rows: list of (label, value) or (label, value, css_class)."""
    payload = {"t": title, "r": [list(r) for r in rows]}
    return html.escape(json.dumps(payload, separators=(",", ":")), quote=True)


def _nice_max(value: float) -> float:
    if value <= 0:
        return 1.0
    magnitude = 10 ** (len(str(int(value))) - 1)
    for step in (1, 2, 2.5, 5, 10):
        candidate = step * magnitude
        if candidate >= value:
            return float(candidate)
    return float(10 * magnitude)


def _ticks(y_min: float, y_max: float, count: int = 4) -> list:
    step = (y_max - y_min) / count
    return [y_min + i * step for i in range(count + 1)]


def _x_positions(count: int, left: float, right: float) -> list:
    if count <= 1:
        return [(left + right) / 2]
    span = right - left
    return [left + i * span / (count - 1) for i in range(count)]


# ---------------------------------------------------------------------------
# sparkline (stat tiles)
# ---------------------------------------------------------------------------
def sparkline(values: list, width: int = 120, height: int = 30) -> str:
    points = [(i, float(v)) for i, v in enumerate(values) if v is not None]
    if len(points) < 2:
        return f'<svg class="spark" viewBox="0 0 {width} {height}" width="{width}" height="{height}" aria-hidden="true"></svg>'
    lo = min(v for _, v in points)
    hi = max(v for _, v in points)
    span = (hi - lo) or 1.0
    xs = _x_positions(len(values), 3, width - 3)
    coords = []
    for i, v in points:
        y = height - 4 - (v - lo) / span * (height - 8)
        coords.append((xs[i], y))
    path = " ".join(f"{_n(x)},{_n(y)}" for x, y in coords)
    last_x, last_y = coords[-1]
    return (
        f'<svg class="spark" viewBox="0 0 {width} {height}" width="{width}" height="{height}" aria-hidden="true">'
        f'<polyline class="spark-line" points="{path}"/>'
        f'<circle class="spark-dot" cx="{_n(last_x)}" cy="{_n(last_y)}" r="3.5"/>'
        "</svg>"
    )


# ---------------------------------------------------------------------------
# line chart over runs
# ---------------------------------------------------------------------------
def line_chart(
    chart_id: str,
    labels: list,
    values: list,
    tips: list,
    y_max: float = None,
    y_min: float = 0.0,
    y_format=lambda v: f"{v:g}",
    height: int = 230,
    width: int = 720,
) -> str:
    """One series over runs with crosshair hover. ``tips`` are (title, rows)."""
    left, right, top, bottom = 46, 20, 14, 30
    plot_w, plot_h = width - left - right, height - top - bottom
    valid = [float(v) for v in values if v is not None]
    if not valid:
        return f'<svg class="chart" viewBox="0 0 {width} {height}" role="img"><text class="ax" x="{width / 2}" y="{height / 2}" text-anchor="middle">No data</text></svg>'
    if y_max is None:
        y_max = _nice_max(max(valid))
    if y_max <= y_min:
        y_max = y_min + 1

    xs = _x_positions(len(values), left, left + plot_w)

    def y_of(v: float) -> float:
        return top + plot_h - (v - y_min) / (y_max - y_min) * plot_h

    parts = [f'<svg class="chart" id="{chart_id}" viewBox="0 0 {width} {height}" role="img" data-left="{left}" data-right="{left + plot_w}">']
    # gridlines + y labels
    for tick in _ticks(y_min, y_max):
        y = y_of(tick)
        parts.append(f'<line class="grid" x1="{left}" x2="{left + plot_w}" y1="{_n(y)}" y2="{_n(y)}"/>')
        parts.append(f'<text class="ax" x="{left - 8}" y="{_n(y + 3.5)}" text-anchor="end">{html.escape(y_format(tick))}</text>')
    parts.append(f'<line class="axis" x1="{left}" x2="{left + plot_w}" y1="{_n(top + plot_h)}" y2="{_n(top + plot_h)}"/>')

    # x labels: at most 8, evenly spread
    step = max(1, (len(labels) + 7) // 8)
    last = len(labels) - 1
    last_tick = (last // step) * step
    for i, label in enumerate(labels):
        # the final label is shown only when it is at least half a step away
        # from the last regular tick, otherwise the two overlap
        if i % step == 0 or (i == last and last - last_tick >= max(1, step // 2)):
            parts.append(f'<text class="ax" x="{_n(xs[i])}" y="{height - 10}" text-anchor="middle">{html.escape(str(label))}</text>')

    # area wash + line
    coords = [(xs[i], y_of(float(v))) for i, v in enumerate(values) if v is not None]
    if len(coords) > 1:
        line = " ".join(f"{_n(x)},{_n(y)}" for x, y in coords)
        base = _n(top + plot_h)
        parts.append(f'<polygon class="area" points="{_n(coords[0][0])},{base} {line} {_n(coords[-1][0])},{base}"/>')
        parts.append(f'<polyline class="line" points="{line}"/>')
    # crosshair (moved by JS)
    parts.append(f'<line class="xhair" x1="0" x2="0" y1="{top}" y2="{top + plot_h}" style="display:none"/>')
    # markers
    show_dots = len(values) <= 40
    for i, v in enumerate(values):
        if v is None:
            continue
        x, y = xs[i], y_of(float(v))
        radius = 4 if show_dots else 0
        parts.append(f'<circle class="dot" data-i="{i}" cx="{_n(x)}" cy="{_n(y)}" r="{radius}"/>')
    # end label
    if coords:
        x, y = coords[-1]
        last_value = next(v for v in reversed(values) if v is not None)
        anchor = "end" if x > left + plot_w - 40 else "start"
        dx = -8 if anchor == "end" else 8
        parts.append(f'<text class="endlabel" x="{_n(x + dx)}" y="{_n(max(top + 10, y - 9))}" text-anchor="{anchor}">{html.escape(y_format(float(last_value)))}</text>')
    # hit columns
    parts.append('<g class="hits">')
    for i, x in enumerate(xs):
        half_l = (x - xs[i - 1]) / 2 if i > 0 else max(12, plot_w / max(len(xs), 1) / 2)
        half_r = (xs[i + 1] - x) / 2 if i < len(xs) - 1 else max(12, plot_w / max(len(xs), 1) / 2)
        title, rows = tips[i]
        parts.append(f'<rect class="hit" data-i="{i}" data-x="{_n(x)}" x="{_n(x - half_l)}" y="{top}" width="{_n(half_l + half_r)}" height="{plot_h}" data-tip="{tip_attr(title, rows)}" tabindex="0" aria-label="{html.escape(title)}"/>')
    parts.append("</g></svg>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# stacked outcome bars per run
# ---------------------------------------------------------------------------
def stacked_bars(labels: list, stacks: list, tips: list, height: int = 230, width: int = 720) -> str:
    """stacks: per run, a dict outcome->count. Order passed, failed, error, skipped."""
    left, right, top, bottom = 46, 20, 14, 30
    plot_w, plot_h = width - left - right, height - top - bottom
    totals = [sum(s.values()) for s in stacks] or [0]
    y_max = _nice_max(max(totals)) if max(totals) > 0 else 1.0
    n = len(stacks)
    slot = plot_w / max(n, 1)
    bar_w = min(24.0, max(4.0, slot * 0.6))
    gap = 2.0

    def y_of(v: float) -> float:
        return top + plot_h - v / y_max * plot_h

    parts = [f'<svg class="chart" viewBox="0 0 {width} {height}" role="img">']
    for tick in _ticks(0, y_max):
        y = y_of(tick)
        parts.append(f'<line class="grid" x1="{left}" x2="{left + plot_w}" y1="{_n(y)}" y2="{_n(y)}"/>')
        parts.append(f'<text class="ax" x="{left - 8}" y="{_n(y + 3.5)}" text-anchor="end">{int(tick)}</text>')
    parts.append(f'<line class="axis" x1="{left}" x2="{left + plot_w}" y1="{_n(top + plot_h)}" y2="{_n(top + plot_h)}"/>')
    step = max(1, (n + 7) // 8)
    last_tick = ((n - 1) // step) * step
    for i, stack in enumerate(stacks):
        cx = left + slot * (i + 0.5)
        x = cx - bar_w / 2
        if i % step == 0 or (i == n - 1 and (n - 1) - last_tick >= max(1, step // 2)):
            parts.append(f'<text class="ax" x="{_n(cx)}" y="{height - 10}" text-anchor="middle">{html.escape(str(labels[i]))}</text>')
        running = 0.0
        title, rows = tips[i]
        parts.append(f'<g class="bar" data-tip="{tip_attr(title, rows)}" tabindex="0" aria-label="{html.escape(title)}">')
        parts.append(f'<rect class="hit" x="{_n(cx - slot / 2)}" y="{top}" width="{_n(slot)}" height="{plot_h}"/>')
        segments = [(k, stack.get(k, 0)) for k in ("passed", "failed", "error", "skipped") if stack.get(k, 0) > 0]
        for index, (outcome, count) in enumerate(segments):
            y_top = y_of(running + count)
            y_bottom = y_of(running)
            seg_h = y_bottom - y_top
            if index < len(segments) - 1:
                seg_h = max(0.0, seg_h - gap)  # surface gap between segments
            is_top = index == len(segments) - 1
            radius = ' rx="3"' if is_top else ""
            parts.append(f'<rect class="{OUTCOME_CLASS[outcome]}" x="{_n(x)}" y="{_n(y_top)}" width="{_n(bar_w)}" height="{_n(max(seg_h, 0.5))}"{radius}/>')
            running += count
        parts.append("</g>")
    parts.append("</svg>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# horizontal bars (pass rate by group)
# ---------------------------------------------------------------------------
def hbar_chart(rows: list, width: int = 720, row_h: int = 26, label_w: int = 120) -> str:
    """rows: dicts with name, value (0-100 or None), tip (title, rows)."""
    if not rows:
        return '<svg class="chart" viewBox="0 0 720 40" role="img"><text class="ax" x="360" y="24" text-anchor="middle">No data</text></svg>'
    left, right, top = label_w, 64, 8
    plot_w = width - left - right
    height = top * 2 + row_h * len(rows)
    parts = [f'<svg class="chart" viewBox="0 0 {width} {height}" role="img">']
    for i, row in enumerate(rows):
        y = top + i * row_h
        bar_y = y + (row_h - 14) / 2
        value = row.get("value")
        fill_w = 0 if value is None else plot_w * max(0.0, min(100.0, float(value))) / 100.0
        title, tip_rows = row["tip"]
        parts.append(f'<g class="bar" data-tip="{tip_attr(title, tip_rows)}" tabindex="0" aria-label="{html.escape(title)}">')
        parts.append(f'<rect class="hit" x="0" y="{_n(y)}" width="{width}" height="{row_h}"/>')
        parts.append(f'<text class="lbl" x="{left - 10}" y="{_n(y + row_h / 2 + 4)}" text-anchor="end">{html.escape(str(row["name"]))}</text>')
        parts.append(f'<rect class="track" x="{left}" y="{_n(bar_y)}" width="{plot_w}" height="14" rx="3"/>')
        if fill_w > 0:
            parts.append(f'<rect class="c-line-fill" x="{left}" y="{_n(bar_y)}" width="{_n(fill_w)}" height="14" rx="3"/>')
        text = "n/a" if value is None else f"{float(value):.0f}%"
        parts.append(f'<text class="val" x="{left + plot_w + 8}" y="{_n(y + row_h / 2 + 4)}">{text}</text>')
        parts.append("</g>")
    parts.append("</svg>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# outcome strip (flakiness timeline)
# ---------------------------------------------------------------------------
def outcome_strip(cells: list, run_labels: list, cell_w: int = 12, cell_h: int = 18, gap: int = 2) -> str:
    """cells: list of outcome or None (test absent), one per run in window order."""
    n = len(cells)
    width = n * (cell_w + gap) - gap if n else cell_w
    parts = [f'<svg class="strip" viewBox="0 0 {width} {cell_h}" width="{width}" height="{cell_h}" role="img">']
    for i, outcome in enumerate(cells):
        x = i * (cell_w + gap)
        label = run_labels[i] if i < len(run_labels) else ""
        if outcome is None:
            parts.append(f'<rect class="c-absent" x="{x + 0.5}" y="0.5" width="{cell_w - 1}" height="{cell_h - 1}" rx="2" data-tip="{tip_attr(str(label), [["Outcome", "not run"]])}"/>')
        else:
            cls = OUTCOME_CLASS.get(outcome, "c-error")
            parts.append(f'<rect class="{cls}" x="{x}" y="0" width="{cell_w}" height="{cell_h}" rx="2" data-tip="{tip_attr(str(label), [["Outcome", OUTCOME_LABEL.get(outcome, outcome)]])}"/>')
    parts.append("</svg>")
    return "".join(parts)
