"""Render the landing page as one self-contained HTML string.

Embedded CSS, an inline SVG illustration, a system font stack, no external
requests. Every value that came from a run file passes through `esc`.
"""

from __future__ import annotations

from utils.dashboard.render import esc, fmt_pct, fmt_seconds, fmt_ts

TITLE = "TestVerse"
TAGLINE = "A UI and API automation framework that keeps its own score."

CSS = """
:root{--bg:#f3f1e8;--surface:#fffdf7;--ink:#161616;--muted:#5a5a55;--line:#161616;
--orange:#e8541e;--yellow:#f4b400;--blue:#2b5be0;--green:#1f9d55;--shadow:6px 6px 0 var(--ink);--radius:10px;
--font:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace}
:root:not([data-theme="light"]){color-scheme:light dark}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#141416;--surface:#1e1e22;--ink:#f3f1e8;--muted:#b3b0a6;--line:#f3f1e8}}
:root[data-theme="dark"]{--bg:#141416;--surface:#1e1e22;--ink:#f3f1e8;--muted:#b3b0a6;--line:#f3f1e8}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--font);font-size:17px;line-height:1.55}
a{color:inherit}
.wrap{max-width:1080px;margin:0 auto;padding:0 20px}
header.top{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:18px 0}
.brand{display:flex;align-items:center;gap:10px;font-weight:800;letter-spacing:-.02em;font-size:20px;text-decoration:none}
.brand .mark{width:30px;height:30px;border:2px solid var(--line);border-radius:8px;background:var(--blue);display:grid;place-items:center;font-size:14px;font-weight:900;color:#fff}
nav.links{display:flex;gap:6px;flex-wrap:wrap;align-items:center}
nav.links a,.btn{display:inline-block;padding:9px 14px;border:2px solid var(--line);border-radius:var(--radius);background:var(--surface);text-decoration:none;font-weight:700;font-size:15px;box-shadow:3px 3px 0 var(--ink);transition:transform .08s,box-shadow .08s}
nav.links a:hover,.btn:hover{transform:translate(-1px,-1px);box-shadow:4px 4px 0 var(--ink)}
nav.links a:active,.btn:active{transform:translate(2px,2px);box-shadow:1px 1px 0 var(--ink)}
.btn.primary{background:var(--orange);color:#fff}
.btn.big{padding:14px 22px;font-size:17px;box-shadow:var(--shadow)}
.btn.big:hover{box-shadow:7px 7px 0 var(--ink)}
button.theme{font:inherit;cursor:pointer}
.pill{display:inline-block;padding:3px 10px;border:2px solid var(--line);border-radius:999px;background:var(--yellow);color:#161616;font-size:13px;font-weight:800;letter-spacing:.02em;text-transform:uppercase;transform:rotate(-2deg)}
.pill.blue{background:var(--blue);color:#fff}
.pill.orange{background:var(--orange);color:#fff}
.hero{display:grid;grid-template-columns:1.15fr .85fr;gap:36px;align-items:center;padding:36px 0 28px}
.hero h1{font-size:clamp(40px,6vw,66px);line-height:1.02;letter-spacing:-.035em;margin:14px 0 14px;font-weight:900}
.hero h1 .u{background:linear-gradient(transparent 62%,var(--yellow) 62%)}
.hero p.lead{font-size:20px;max-width:34em;margin:0 0 22px;color:var(--muted)}
.cta{display:flex;gap:14px;flex-wrap:wrap}
.art{border:2px solid var(--line);border-radius:14px;background:var(--surface);box-shadow:var(--shadow);padding:14px}
.art svg{display:block;width:100%;height:auto}
.strip{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px;margin:26px 0 8px}
.stat{border:2px solid var(--line);border-radius:var(--radius);background:var(--surface);padding:14px 16px;box-shadow:4px 4px 0 var(--ink)}
.stat .v{font-size:32px;font-weight:900;letter-spacing:-.03em;line-height:1;font-family:var(--mono)}
.stat .l{font-size:13px;color:var(--muted);margin-top:6px;font-weight:700;text-transform:uppercase;letter-spacing:.04em}
.note{font-size:14px;color:var(--muted);margin:6px 0 0}
section{padding:40px 0 8px}
section h2{font-size:clamp(28px,4vw,40px);letter-spacing:-.03em;line-height:1.1;margin:8px 0 18px;font-weight:900}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:20px}
.card{border:2px solid var(--line);border-radius:14px;background:var(--surface);padding:22px;box-shadow:var(--shadow)}
.card h3{margin:10px 0 8px;font-size:22px;letter-spacing:-.02em}
.card p{margin:0;color:var(--muted)}
code{font-family:var(--mono);font-size:.9em;background:rgba(127,127,127,.14);padding:1px 6px;border-radius:5px}
.steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px;counter-reset:step}
.step{border:2px solid var(--line);border-radius:14px;background:var(--surface);padding:18px;box-shadow:4px 4px 0 var(--ink);position:relative}
.step:before{counter-increment:step;content:counter(step);position:absolute;top:-14px;left:14px;width:30px;height:30px;border:2px solid var(--line);border-radius:999px;background:var(--blue);color:#fff;font-weight:900;display:grid;place-items:center;font-size:14px}
.step h4{margin:8px 0 6px;font-size:18px}
.step p{margin:0;color:var(--muted);font-size:15px}
pre{margin:8px 0 0;padding:10px 12px;border:2px solid var(--line);border-radius:8px;background:var(--bg);font-family:var(--mono);font-size:13.5px;white-space:pre-wrap;word-break:break-word}
.run{border:2px solid var(--line);border-radius:14px;background:var(--surface);box-shadow:var(--shadow);padding:22px 24px}
.run pre{margin-top:0;font-size:14.5px}
footer{margin-top:44px;padding:26px 0 40px;border-top:2px solid var(--line);font-size:15px;color:var(--muted)}
footer .row{display:flex;flex-wrap:wrap;gap:8px 18px;align-items:center;justify-content:space-between}
footer a{font-weight:700}
@media (max-width:820px){.hero{grid-template-columns:1fr;gap:22px}.art{order:-1}}
@media (max-width:480px){body{font-size:16px}.wrap{padding:0 16px}.btn.big{width:100%;text-align:center}.stat .v{font-size:26px}}
"""

JS = """
(function(){
  var KEY='testverse-site-theme';var root=document.documentElement;var order=['auto','light','dark'];
  function read(){try{return localStorage.getItem(KEY)||'auto'}catch(e){return 'auto'}}
  function apply(v){if(v==='auto'){root.removeAttribute('data-theme')}else{root.setAttribute('data-theme',v)}
    var b=document.getElementById('theme');if(b){b.textContent='Theme: '+v}}
  apply(read());
  var btn=document.getElementById('theme');
  if(btn){btn.addEventListener('click',function(){var cur=read();var next=order[(order.indexOf(cur)+1)%order.length];
    try{localStorage.setItem(KEY,next)}catch(e){}apply(next)})}
})();
"""

ART = """
<svg viewBox="0 0 520 330" role="img" aria-label="A browser window with a passing checkout flow and a trend of green bars">
  <defs>
    <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
      <path d="M20 0H0V20" fill="none" stroke="currentColor" stroke-opacity=".12" stroke-width="1"/>
    </pattern>
  </defs>
  <rect x="0" y="0" width="520" height="330" rx="10" fill="url(#grid)"/>
  <g stroke="currentColor" stroke-width="3">
    <rect x="40" y="34" width="300" height="210" rx="10" fill="#fffdf7"/>
    <line x1="40" y1="68" x2="340" y2="68"/>
    <circle cx="60" cy="51" r="5" fill="#e8541e"/><circle cx="78" cy="51" r="5" fill="#f4b400"/><circle cx="96" cy="51" r="5" fill="#1f9d55"/>
    <rect x="118" y="43" width="190" height="16" rx="8" fill="#f3f1e8"/>
  </g>
  <g stroke="currentColor" stroke-width="3">
    <rect x="62" y="90" width="120" height="18" rx="6" fill="#f3f1e8"/>
    <rect x="62" y="120" width="256" height="18" rx="6" fill="#f3f1e8"/>
    <rect x="62" y="150" width="256" height="18" rx="6" fill="#f3f1e8"/>
    <rect x="62" y="192" width="130" height="34" rx="8" fill="#e8541e"/>
  </g>
  <text x="127" y="215" font-family="ui-sans-serif,system-ui,sans-serif" font-size="15" font-weight="800" text-anchor="middle" fill="#fff">Checkout</text>
  <g transform="translate(300 176)">
    <circle cx="0" cy="0" r="30" fill="#1f9d55" stroke="currentColor" stroke-width="3"/>
    <path d="M-13 1 L-4 10 L14 -10" fill="none" stroke="#fff" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>
  </g>
  <g stroke="currentColor" stroke-width="3">
    <rect x="372" y="200" width="22" height="44" rx="4" fill="#1f9d55"/>
    <rect x="402" y="176" width="22" height="68" rx="4" fill="#1f9d55"/>
    <rect x="432" y="214" width="22" height="30" rx="4" fill="#e8541e"/>
    <rect x="462" y="160" width="22" height="84" rx="4" fill="#1f9d55"/>
    <line x1="364" y1="246" x2="492" y2="246"/>
  </g>
  <g transform="translate(372 70)">
    <rect x="0" y="0" width="118" height="40" rx="8" fill="#f4b400" stroke="currentColor" stroke-width="3"/>
    <text x="59" y="26" font-family="ui-monospace,Menlo,Consolas,monospace" font-size="15" font-weight="800" text-anchor="middle" fill="#161616">-n auto</text>
  </g>
  <g transform="translate(372 122)">
    <rect x="0" y="0" width="118" height="40" rx="8" fill="#2b5be0" stroke="currentColor" stroke-width="3"/>
    <text x="59" y="26" font-family="ui-monospace,Menlo,Consolas,monospace" font-size="14" font-weight="800" text-anchor="middle" fill="#fff">trace.zip</text>
  </g>
  <g font-family="ui-monospace,Menlo,Consolas,monospace" font-size="12" fill="currentColor" text-anchor="middle">
    <text x="60" y="290">login</text><text x="140" y="290">inventory</text><text x="220" y="290">cart</text><text x="300" y="290">checkout</text><text x="428" y="290">runs</text>
  </g>
</svg>
"""


def _stat(value: str, label: str) -> str:
    return '<div class="stat"><div class="v">' + esc(value) + '</div><div class="l">' + esc(label) + "</div></div>"


def render_stats(numbers, dashboard_href) -> str:
    """The stats strip; an honest empty state when nothing has been recorded."""
    if not numbers:
        return (
            '<div class="strip"><div class="stat"><div class="v">0</div>'
            '<div class="l">runs recorded</div></div></div>'
            '<p class="note">No runs recorded yet. The first push to main fills this in.</p>'
        )
    browsers = ", ".join(numbers["browsers"]) if numbers["browsers"] else "-"
    cells = [
        _stat(str(numbers["tests"]), "tests in the suite"),
        _stat(fmt_pct(numbers["pass_rate"]), "latest pass rate"),
        _stat(str(numbers["failed"]), "failed in latest run"),
        _stat(fmt_seconds(numbers["median_duration"]), "median test"),
        _stat(str(numbers["runs"]), "runs recorded"),
        _stat(str(numbers["green_streak"]), "green runs in a row"),
    ]
    note = "Latest run " + esc(fmt_ts(numbers["timestamp"])) + " on " + esc(browsers) + "."
    if dashboard_href:
        note += ' Same history the <a href="' + esc(dashboard_href) + '">dashboard</a> reads.'
    return '<div class="strip">' + "".join(cells) + '</div><p class="note">' + note + "</p>"


def render(numbers, dashboard_href, report_href, repo_url: str) -> str:
    """The whole page.

    `dashboard_href` and `report_href` are None when the target does not exist
    next to the page; the buttons then fall back to the repository.
    """
    dash_link = dashboard_href or repo_url
    nav = ['<a href="' + esc(dash_link) + '">Dashboard</a>']
    if report_href:
        nav.append('<a href="' + esc(report_href) + '">Latest report</a>')
    nav.append('<a href="' + esc(repo_url) + '">GitHub</a>')
    nav.append('<button class="theme" id="theme" type="button">Theme: auto</button>')

    p = []
    p.append("<!DOCTYPE html>")
    p.append('<html lang="en"><head><meta charset="utf-8">')
    p.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
    p.append("<title>" + esc(TITLE) + " - " + esc(TAGLINE) + "</title>")
    p.append('<meta name="description" content="' + esc(TITLE + ": a Playwright and Pytest UI and API automation framework with a results dashboard.") + '">')
    p.append("<style>" + CSS + "</style></head><body>")
    p.append('<div class="wrap">')

    p.append('<header class="top"><a class="brand" href="./"><span class="mark">T</span>' + esc(TITLE) + "</a>")
    p.append('<nav class="links">' + "".join(nav) + "</nav></header>")

    p.append('<section class="hero" id="top"><div>')
    p.append('<span class="pill">Playwright + Pytest</span>')
    p.append('<h1>A test suite that<br><span class="u">keeps its own score.</span></h1>')
    p.append(
        '<p class="lead">' + esc(TITLE) + " automates an e-commerce app end to end - UI through page objects, API "
        "through a schema-checked client - and records every run, so the dashboard can tell a flaky test from a "
        "real regression before anyone has to guess.</p>"
    )
    p.append('<div class="cta"><a class="btn primary big" href="' + esc(dash_link) + '">Open the dashboard</a>')
    p.append('<a class="btn big" href="' + esc(repo_url) + '">Source on GitHub</a></div>')
    p.append('</div><div class="art">' + ART + "</div></section>")

    p.append('<section id="numbers"><span class="pill blue">Live numbers</span>')
    p.append("<h2>From the latest run on main</h2>")
    p.append(render_stats(numbers, dashboard_href))
    p.append("</section>")

    p.append('<section id="inside"><span class="pill orange">What is inside</span>')
    p.append("<h2>Three layers, one repository</h2>")
    p.append('<div class="cards">')
    p.append(
        '<div class="card"><span class="pill">01</span><h3>Page-object UI suite</h3>'
        "<p>Sixteen Playwright tests across login, inventory, cart and checkout. Tests call page methods, never "
        "selectors; a session-scoped browser and a fresh context per test make <code>pytest -n auto</code> safe. "
        "Headless by default, <code>HEADED=1</code> to watch.</p></div>"
    )
    p.append(
        '<div class="card"><span class="pill">02</span><h3>API contract layer</h3>'
        "<p>Twelve tests over a reusable <code>requests</code> client: status codes, JSON Schema validation of "
        "every response shape, a response-time SLA, and negative cases. Ten times faster than the UI, and it says "
        "<em>where</em> something broke, not just that it did.</p></div>"
    )
    p.append(
        '<div class="card"><span class="pill">03</span><h3>CI and analytics</h3>'
        "<p>GitHub Actions runs both layers in parallel on every push, nightly on two engines, and uploads reports "
        "and traces. A pytest plugin records each run; the dashboard turns the history into trends, flakiness and "
        "insights, published to this site.</p></div>"
    )
    p.append("</div></section>")

    p.append('<section id="failure"><span class="pill blue">How a failure is handled</span>')
    p.append("<h2>From red test to root cause</h2>")
    p.append('<div class="steps">')
    p.append('<div class="step"><h4>Captured</h4><pre>SCREENSHOT=retain-on-failure\nTRACE=retain-on-failure\nVIDEO=retain-on-failure</pre><p>A failing test keeps its full-page screenshot, Playwright trace and video. A passing one keeps nothing.</p></div>')
    p.append('<div class="step"><h4>Linked</h4><pre>reports/report.html</pre><p>Each artifact is linked into that test\'s row of the HTML report. Open the trace to step through every action, DOM snapshot and network call.</p></div>')
    p.append('<div class="step"><h4>Recorded</h4><pre>reports/history/&lt;run&gt;.json</pre><p>Outcome, the phase that failed, duration, message and artifact paths - written by <code>utils/results_plugin.py</code> for every run.</p></div>')
    p.append('<div class="step"><h4>Explained</h4><pre>flipped 3 times in 10 runs\nvs. failed 3 runs in a row</pre><p>The dashboard reads the history and says which it is: flaky, or a regression. The rule is shown next to every insight.</p></div>')
    p.append("</div></section>")

    p.append('<section id="run"><span class="pill orange">Run it</span>')
    p.append("<h2>Three commands</h2>")
    p.append('<div class="run"><pre>python -m pytest -m smoke          # the critical path, 11 tests\n'
             "python -m pytest -n 4              # the whole suite, four workers\n"
             "docker run --rm testverse -m smoke  # same suite, any machine</pre></div>")
    p.append("</section>")

    p.append('<footer><div class="row"><div>' + esc(TITLE) + " - one self-contained page, generated in Python. No external assets.</div>")
    p.append(
        '<div><a href="' + esc(repo_url + "#readme") + '">README</a> &middot; <a href="'
        + esc(repo_url + "#design-decisions") + '">Design decisions</a> &middot; <a href="'
        + esc(repo_url + "/actions") + '">CI</a></div></div></footer>'
    )
    p.append("</div><script>" + JS + "</script></body></html>")
    return "\n".join(p)
