"""A run, as a page you can open, print, or attach to a report.

Self-contained by requirement: no fonts, no CDN, no scripts fetched. An
engineering record has to open on a machine with no network and still work in
five years, so everything is inline and the charts are hand-drawn SVG.

On the charts. The reflux sweep was already a chart pretending to be a table:
eight rows in which the reader has to find the minimum. Its job is locating an
optimum in a trade-off, so it is a line with that optimum marked. Stages
against k is a SECOND measure on a different scale and gets its OWN chart,
never a second axis on the first: with two arbitrary scalings the crossing
point of the two curves can be put anywhere, and readers reliably read it as a
finding.

Colour does one job here. Each chart carries a single series, so there is no
categorical palette to assign and no legend to draw; the title names the
series. Status (pass/fail, default/decided/open) uses the reserved status
palette and ALWAYS ships with a label, never colour alone, because the
difference between convention and evidence is the distinction this whole
project rests on and it cannot be left to a hue.
"""
import html as _html

# Single categorical slot (blue) plus the reserved status palette. Light and
# dark steps are selected for their own surface rather than flipped.
CSS = """
:root{
  --surface:#fcfcfb; --panel:#ffffff; --ink:#0b0b0b; --ink-2:#52514e;
  --ink-3:#7a7975; --rule:#e4e3df; --series:#2a78d6; --series-soft:#e5eefa;
  --good:#0ca30c; --warning:#fab219; --critical:#d03b3b; --grid:#ebeae6;
}
@media (prefers-color-scheme:dark){:root{
  --surface:#1a1a19; --panel:#232322; --ink:#ffffff; --ink-2:#c3c2b7;
  --ink-3:#8f8e86; --rule:#33332f; --series:#3987e5; --series-soft:#16293a;
  --good:#0ca30c; --warning:#fab219; --critical:#d03b3b; --grid:#2b2b28;
}}
*{box-sizing:border-box}
body{margin:0;padding:0 24px 72px;background:var(--surface);color:var(--ink);
  font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
  -webkit-font-smoothing:antialiased}
.wrap{max-width:960px;margin:0 auto}
header{padding:40px 0 20px;border-bottom:2px solid var(--ink)}
h1{margin:0;font-size:26px;letter-spacing:-.02em}
h2{margin:36px 0 4px;font-size:17px;letter-spacing:-.01em}
h2+.note{margin-top:0}
.note{color:var(--ink-2);font-size:13.5px;margin:4px 0 14px;max-width:68ch}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.verdict{display:inline-block;padding:5px 12px;border-radius:3px;font-weight:600;
  font-size:13px;letter-spacing:.06em}
.v-feasible{background:var(--good);color:#fff}
.v-caution,.v-undetermined{background:var(--warning);color:#241a00}
.v-infeasible,.v-unknown{background:var(--critical);color:#fff}
.meta{display:flex;flex-wrap:wrap;gap:6px 28px;margin-top:14px;
  font-size:12.5px;color:var(--ink-3)}
.meta b{color:var(--ink);font-weight:600}
.panel{background:var(--panel);border:1px solid var(--rule);border-radius:4px;
  padding:16px 18px;margin:14px 0}
.pairs{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px}
.pair{border-left:3px solid var(--series);padding-left:12px}
.pair .k{font-size:11px;letter-spacing:.09em;text-transform:uppercase;color:var(--ink-3)}
.pair .v{font-size:16px;font-weight:600;margin-top:2px}
.pair .w{font-size:12.5px;color:var(--ink-2);margin-top:3px}
.charts{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:20px}
figure{margin:0;background:var(--panel);border:1px solid var(--rule);
  border-radius:4px;padding:14px 14px 8px}
figcaption{font-size:13px;font-weight:600;margin-bottom:2px}
figcaption+.sub{font-size:12px;color:var(--ink-3);margin:0 0 8px}
table{width:100%;border-collapse:collapse;font-size:13.5px;margin-top:8px}
th{text-align:left;font-size:11px;letter-spacing:.08em;text-transform:uppercase;
  color:var(--ink-3);font-weight:600;padding:0 10px 6px 0;border-bottom:1px solid var(--rule)}
td{padding:7px 10px 7px 0;border-bottom:1px solid var(--rule);vertical-align:top}
td.num{text-align:right;font-variant-numeric:tabular-nums;font-family:ui-monospace,Menlo,monospace}
.chip{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11.5px;
  font-weight:600;border:1px solid}
.chip-default{color:var(--ink-2);border-color:var(--rule)}
.chip-decided{color:var(--good);border-color:var(--good)}
.chip-open{color:var(--warning);border-color:var(--warning)}
.check{display:flex;gap:10px;align-items:baseline;padding:6px 0;border-bottom:1px solid var(--rule)}
.check .tag{font-weight:700;font-size:11.5px;letter-spacing:.05em;min-width:52px}
.pass{color:var(--good)} .fail{color:var(--critical)}
.check .nm{min-width:170px;font-size:13px}
.check .dt{color:var(--ink-2);font-size:12.5px}
.rule{padding:9px 0;border-bottom:1px solid var(--rule)}
.rule .id{font-weight:700;font-size:12.5px}
.rule .cond{color:var(--ink-3);font-size:12px}
.rule.silent{opacity:.62}
.req{color:var(--ink-2);font-size:12.5px;margin-top:4px;padding-left:12px;
  border-left:2px solid var(--warning)}
footer{margin-top:44px;padding-top:14px;border-top:1px solid var(--rule);
  font-size:12px;color:var(--ink-3)}
@media print{body{background:#fff}.panel,figure{break-inside:avoid}}
"""


def e(x) -> str:
    return _html.escape(str(x))


def _num(x, dp=3):
    return "n/a" if x is None else f"{x:,.{dp}f}"


def _line_chart(points, xkey, ykey, *, title, sub, yfmt, mark_min=False):
    """One series, one axis. Minimum emphasised when the curve has an optimum.

    Hover is the SVG <title> element rather than a scripted tooltip: this file
    has to work with scripting off and when printed, and a native tooltip
    degrades to nothing rather than to a broken layer.
    """
    pts = [p for p in points if p.get(ykey) is not None]
    if len(pts) < 2:
        return ""
    W, H = 420, 210
    L, R, T, B = 52, 14, 14, 34
    xs = [p[xkey] for p in pts]
    ys = [p[ykey] for p in pts]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    pad = (y1 - y0) * 0.12 or (y1 or 1) * 0.05
    y0, y1 = y0 - pad, y1 + pad

    def px(v):
        return L + (v - x0) / ((x1 - x0) or 1) * (W - L - R)

    def py(v):
        return T + (1 - (v - y0) / ((y1 - y0) or 1)) * (H - T - B)

    best = min(pts, key=lambda p: p[ykey]) if mark_min else None
    grid, ticks = [], []
    for i in range(4):
        v = y0 + (y1 - y0) * i / 3
        y = py(v)
        grid.append(f'<line x1="{L}" y1="{y:.1f}" x2="{W-R}" y2="{y:.1f}" '
                    f'stroke="var(--grid)" stroke-width="1"/>')
        ticks.append(f'<text x="{L-8}" y="{y+4:.1f}" text-anchor="end" '
                     f'font-size="10" fill="var(--ink-3)">{yfmt(v)}</text>')
    # Thin the x labels rather than let them collide. Sweep points bunch at the
    # low-k end, where 1.05 and 1.10 sit a few pixels apart.
    last_x = -1e9
    for p in pts:
        x = px(p[xkey])
        if x - last_x < 26:
            continue
        last_x = x
        ticks.append(f'<text x="{x:.1f}" y="{H-B+16}" text-anchor="middle" '
                     f'font-size="10" fill="var(--ink-3)">{p[xkey]:g}</text>')

    poly = " ".join(f"{px(p[xkey]):.1f},{py(p[ykey]):.1f}" for p in pts)
    marks = []
    for p in pts:
        is_best = best is not None and p is best
        cx, cy = px(p[xkey]), py(p[ykey])
        # A 2px surface ring keeps overlapping marks separable.
        marks.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{5 if is_best else 4}" '
            f'fill="{"var(--series)" if is_best else "var(--panel)"}" '
            f'stroke="var(--series)" stroke-width="2">'
            f'<title>k = {p[xkey]:g}, {yfmt(p[ykey])}</title></circle>')
    label = ""
    if best is not None:
        bx, by = px(best[xkey]), py(best[ykey])
        # BELOW the point, always. This marks a minimum, so the curve lies above
        # it on both sides and the space underneath is the only region
        # guaranteed empty. Placing it beside the point put the text straight
        # through the rising limb.
        y = min(by + 20, H - B - 6)
        anchor, x = "middle", bx
        if bx < L + 46:
            anchor, x = "start", L + 2
        elif bx > W - R - 46:
            anchor, x = "end", W - R - 2
        label = (f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" '
                 f'font-size="11" font-weight="600" fill="var(--ink)">'
                 f'cheapest, k = {best[xkey]:g}</text>')

    return f"""<figure>
<figcaption>{e(title)}</figcaption>
<p class="sub">{e(sub)}</p>
<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="{e(title)}">
{''.join(grid)}
<line x1="{L}" y1="{T}" x2="{L}" y2="{H-B}" stroke="var(--rule)" stroke-width="1"/>
<line x1="{L}" y1="{H-B}" x2="{W-R}" y2="{H-B}" stroke="var(--rule)" stroke-width="1"/>
{''.join(ticks)}
<polyline points="{poly}" fill="none" stroke="var(--series)" stroke-width="2"
  stroke-linejoin="round" stroke-linecap="round"/>
{''.join(marks)}
{label}
<text x="{(L+W-R)/2:.0f}" y="{H-4}" text-anchor="middle" font-size="10.5"
  fill="var(--ink-3)">reflux multiple, k = R / R_min</text>
</svg>
</figure>"""


def _pairs_panel(run) -> str:
    """The three things a run must never collapse. Front and centre, because
    they are the argument the tool exists to make."""
    p = run["column_pressure"]
    d = run.get("design")
    cells = [(
        "column pressure",
        f'{p["Pa"]/1e5:.3f} bar' if p["Pa"] else "n/a",
        p["basis"],
    )]
    if d:
        q = d["feed_q"]
        cells.append((
            "feed condition q",
            _num(q["value"]) if q["value"] is not None else "n/a",
            f'{q["classification"] or ""}, '
            f'{"imposed" if q["imposed"] else "as the feed arrives"}',
        ))
        decided = sum(1 for x in d["equipment"] if x["status"] == "decided")
        default = sum(1 for x in d["equipment"] if x["status"] == "default")
        openn = sum(1 for x in d["equipment"] if x["status"] == "open")
        cells.append((
            "equipment choices",
            f"{decided} decided, {default} by default",
            (f"{openn} left undecided. " if openn else "")
            + "A default was not proved; it is the convention.",
        ))
    return ('<div class="panel"><div class="pairs">'
            + "".join(f'<div class="pair"><div class="k">{e(k)}</div>'
                      f'<div class="v">{e(v)}</div><div class="w">{e(w)}</div></div>'
                      for k, v, w in cells)
            + "</div></div>")


def _rules(run) -> str:
    rows = []
    for r in run["screening"]["rules"]:
        vals = ", ".join(f"{k} = {v}" for k, v in r["values"].items())
        req = "".join(f'<div class="req">requires: {e(x)}</div>'
                      for x in r["requires"])
        lim = (f'<div class="req">caveat: {e(r["limitations"])}</div>'
               if r["limitations"] else "")
        state = "fired" if r["fired"] else "did not fire"
        rows.append(
            f'<div class="rule{"" if r["fired"] else " silent"}">'
            f'<span class="id mono">{e(r["id"])}</span> {e(r["name"])} '
            f'<span class="cond">[{state}]</span>'
            f'<div class="cond mono">{e(vals) or e(r["condition"])}</div>'
            f'{req if r["fired"] else ""}{lim if r["fired"] else ""}</div>')
    return "".join(rows)


def _design_section(d) -> str:
    money = lambda v: f"{v/1000:,.0f}k" if abs(v) >= 1000 else f"{v:,.0f}"
    charts = (
        _line_chart(d["reflux_sweep"], "k", "annualised_cost_USD_yr",
                    title="Annualised cost against reflux",
                    sub="Capital falls and energy rises with reflux; the optimum is the knee.",
                    yfmt=lambda v: f"${money(v)}", mark_min=True)
        + _line_chart(d["reflux_sweep"], "k", "stages",
                      title="Stages against reflux",
                      sub="A second measure on its own scale, deliberately not a second axis.",
                      yfmt=lambda v: f"{v:.0f}")
    )

    prod = "".join(
        f'<tr><td>{e(n)}</td><td class="num">{v:,.3f}</td>'
        f'<td class="num">{d["products"]["bottoms_kmol_hr"].get(n, 0.0):,.3f}</td></tr>'
        for n, v in d["products"]["distillate_kmol_hr"].items())

    equip = "".join(
        f'<tr><td class="mono">step {x["step"]}</td><td>{e(x["question"])}</td>'
        f'<td><b>{e(x["choice"] or "NOT DECIDED")}</b></td>'
        f'<td><span class="chip chip-{x["status"]}">{e(x["status"])}'
        f'{" " + e(x["rule_id"]) if x["rule_id"] else ""}</span></td></tr>'
        for x in d["equipment"])

    checks = "".join(
        f'<div class="check"><span class="tag {"pass" if c["passed"] else "fail"}">'
        f'{"PASS" if c["passed"] else "FAIL"}</span>'
        f'<span class="nm">{e(c["name"])}</span>'
        f'<span class="dt">{e(c["detail"])}</span></div>'
        for c in d["verification"])

    chosen = d["chosen"]
    head = "" if not chosen else (
        f'<div class="meta"><span><b>{chosen["stages"]:.0f}</b> stages</span>'
        f'<span><b>${chosen["annualised_cost_USD_yr"]:,.0f}</b> per year</span>'
        f'<span>reflux <b>{chosen["k"]:g}</b> x minimum</span>'
        f'<span>diameter <b>{_num(d["column"]["diameter_m"], 2)}</b> m</span></div>')

    return f"""
<h2>Column design</h2>
{head}
<div class="charts">{charts}</div>

<h2>Products</h2>
<table><thead><tr><th>Component</th><th style="text-align:right">Distillate kmol/hr</th>
<th style="text-align:right">Bottoms kmol/hr</th></tr></thead><tbody>{prod}</tbody></table>

<h2>Equipment choices</h2>
<p class="note">A choice marked <b>default</b> was not proved, it is the
convention. One marked <b>decided</b> cites the rule that settled it. Collapsing
those two is how an unrecorded condenser type produced a 58% duty discrepancy
between two calculations that were each correct.</p>
<table><thead><tr><th>Step</th><th>Decision</th><th>Choice</th><th>Basis</th></tr></thead>
<tbody>{equip}</tbody></table>

<h2>Verification</h2>
<p class="note">Independent checks on the finished design. Each can fail on a
column every step above produced correctly, which is what makes them worth
running.</p>
{checks}"""


def render(run: dict) -> str:
    feed = ", ".join(f'{c["name"]} {c["flow_kmol_hr"]:g}'
                     for c in run["feed"]["components"])
    verdict = run["screening"]["verdict"]
    d = run.get("design")
    alphas = "".join(
        f'<tr><td>{e(a["pair"][0])} / {e(a["pair"][1])}</td>'
        f'<td class="num">{a["value"]:,.3f}</td>'
        f'<td class="num">{a["T_K"]:,.1f}</td>'
        f'<td class="num">{a["P_Pa"]/1e5:,.3f}</td></tr>'
        for a in run["screening"]["alphas"])

    body_design = _design_section(d) if d and d.get("converged") else (
        '<h2>No column was designed</h2><p class="note">Screening did not clear, '
        'or no design was requested. The reasoning above stands on its own.</p>')

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>sepsyn run</title><style>{CSS}</style></head><body><div class="wrap">
<header>
  <h1>{e(feed)}</h1>
  <div class="meta">
    <span>feed <b>{run["feed"]["T_K"]:.2f} K</b></span>
    <span>column <b>{(run["column_pressure"]["Pa"] or 0)/1e5:.3f} bar</b></span>
    <span>generated {e(run["generated"])}</span>
  </div>
  <p style="margin:16px 0 0">
    <span class="verdict v-{e(verdict)}">{e(verdict).upper()}</span>
  </p>
</header>

<h2>What this run assumed</h2>
<p class="note">Each of these is a pair. The value alone does not describe the
run, because a pressure that was specified and one that was derived are
different claims, and two designs at different q are not comparable.</p>
{_pairs_panel(run)}

<h2>Relative volatility</h2>
<p class="note">Evaluated at the column pressure, not the feed pressure. Alpha
is a property of a pair at a condition, so the condition travels with it.</p>
<table><thead><tr><th>Pair</th><th style="text-align:right">alpha</th>
<th style="text-align:right">T (K)</th><th style="text-align:right">P (bar)</th>
</tr></thead><tbody>{alphas}</tbody></table>

<h2>Rules</h2>
<p class="note">Every rule in the table, whether it fired or not. What was
considered and rejected is part of the reasoning.</p>
{_rules(run)}

{body_design}

<footer>Generated by sepsyn. Every number here is reproducible from the run
recorded alongside it.</footer>
</div></body></html>
"""


def write_html(path: str, run: dict) -> None:
    with open(path, "w") as fh:
        fh.write(render(run))
