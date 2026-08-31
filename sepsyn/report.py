"""Formatting. The output IS the product -- the whole point is that a reader
can check the reasoning, so rules that did NOT fire are printed too."""
import textwrap

from sepsyn.properties import boiling_point, critical_temperature, resolve
from sepsyn.types import Feed, PropertyRecord
from sepsyn.engine import Verdict


def format_report(
    feed: Feed,
    record: PropertyRecord,
    verdicts: list[Verdict],
    overall: str,
    explain: bool = False,
) -> str:
    lines: list[str] = []
    spec = ", ".join(f"{c.name} {c.flow_kmol_hr:g} kmol/hr" for c in feed.components)
    lines.append(f"FEED   {spec}  @ {feed.T_K:.2f} K, {feed.P_Pa/1e5:.3f} bar")
    lines.append("")
    if record.column_P_Pa is not None:
        # Printed BEFORE the properties, because every one of them was
        # evaluated at this pressure and none of them means anything without
        # it. Screening once ran at the feed pressure while the column was
        # designed elsewhere; stating the pressure and its origin is what makes
        # that visible rather than merely wrong.
        lines.extend(_wrapped("COLUMN PRESSURE  ", record.column_P_basis))
    lines.append("")
    lines.append("PROPERTIES")
    lines.append(f"  {'component':<12}{'Tb (K)':>10}{'Tc (K)':>10}   state at feed")
    for c in feed.components:
        cas = c.cas or resolve(c.name)
        tb, tc = boiling_point(cas), critical_temperature(cas)
        state = "SUPERCRITICAL" if feed.T_K > tc else "condensable"
        lines.append(f"  {c.name:<12}{tb:>10.1f}{tc:>10.1f}   {state}")

    # Branch on WHY there are no alphas, not merely on the fact that there are
    # none. `min_alpha is None` collapses four different causes into one flag:
    # every component supercritical, a single-component feed with no pair to
    # compare, the bubble-point solve raising, and every pair hitting the
    # zero-fraction guard. Only the first of those means "no vapour-liquid
    # equilibrium". Task 5 made the record able to tell these apart
    # (n_supercritical_at_feed, feed_phase, tri-state has_azeotrope); printing a
    # single sentence for all of them throws that distinction away again at the
    # last step and states a reason the record does not support.
    if record.alphas:
        for a in record.alphas:
            lines.append(
                f"  alpha {a.pair[0]}/{a.pair[1]} = {a.value:.3f} "
                f"at {a.T_K:.1f} K, {a.P_Pa/1e5:.3f} bar ({a.basis})"
            )
    elif record.n_supercritical_at_feed == record.n_components:
        lines.append(
            "  alpha: not computed -- every component is above its critical "
            "temperature at feed conditions, so no liquid phase exists"
        )
    elif record.n_components < 2:
        lines.append(
            "  alpha: not applicable -- relative volatility is a property of a "
            "pair, and this feed has one component"
        )
    else:
        lines.append(
            "  alpha: not computed -- the bubble-point solve returned no usable "
            "pair at these conditions (this is a gap in the evidence, not a "
            "finding about the mixture)"
        )
    lines.append("")

    fired = [v for v in verdicts if v.fired]
    lines.append("RULES FIRED")
    if not fired:
        lines.append("  none -- no rule covers this combination of properties")
    for v in fired:
        lines.append(f"  {v.rule_id}  {v.rule_name}")
        vals = ", ".join(f"{k} = {val}" for k, val in v.values.items())
        lines.append(f"        {vals}")
        # Only for rules that FIRED. Printing the outstanding calculation for
        # every loaded rule would bury the one actually blocking a decision.
        for req in v.requires:
            lines.append(f"        REQUIRES  {req}")
        if v.limitations:
            lines.append(f"        CAVEAT    {v.limitations}")
    lines.append("")

    lines.append(f"VERDICT  distillation {overall.upper()}")
    for v in fired:
        lines.append(f"         {v.because}")
    techs = sorted({t for v in fired for t in v.technologies})
    if techs:
        lines.append(f"CANDIDATES  {', '.join(techs)}")
        lines.append("            (screening only -- sepsyn designs distillation and flash)")

    if explain:
        lines.append("")
        lines.append("RULES CONSIDERED AND not fired")
        for v in verdicts:
            if v.fired:
                continue
            vals = ", ".join(f"{k} = {val}" for k, val in v.values.items())
            lines.append(f"  {v.rule_id}  {v.rule_name:<40} [not fired]")
            lines.append(f"        condition: {v.condition}")
            lines.append(f"        values:    {vals}")
    return "\n".join(lines)


def _feed_condition_line(spec, result) -> str:
    """Heuristic step 17. q printed WITH the design, every time.

    Three distinct things have to stay distinguishable here, and collapsing any
    two of them is the failure the step exists to prevent: a q that was imposed
    on the feed, a q the feed simply had, and a q that could not be measured at
    all. The third is not zero -- zero is a saturated vapour.
    """
    from sepsyn.feed_condition import describe

    if result is None or result.feed_q is None:
        return ("thermal condition q could not be measured at this pressure "
                "(no vapour/liquid region), so this design is not comparable "
                "with one at a stated q")
    origin = "imposed" if spec.feed_q is not None else "as it arrives"
    return f"q = {result.feed_q:.3f} ({describe(result.feed_q)}, {origin})"


def _format_equipment(decisions) -> list[str]:
    """Steps 22 to 25, with the STATUS of each choice kept visible.

    "total condenser, decided" and "total condenser, by default" are different
    claims about how much is known, and a report that prints them identically
    hands the reader a design they cannot compare with anyone else's. That is
    the failure that produced this project's 58 percent condenser-duty
    discrepancy, so the label is not decoration.
    """
    lines = ["", "EQUIPMENT CHOICES"]
    for d in decisions:
        if d.status == "open":
            headline = f"NOT DECIDED ({' / '.join(d.options)})"
        else:
            suffix = "by default" if d.status == "default" else f"decided, {d.rule_id}"
            headline = f"{d.choice}  [{suffix}]"
        lines.append(f"  step {d.step}  {d.question}")
        lines.append(f"            {headline}")
        lines.extend(_wrapped("            ", d.because))
        for item in d.requires:
            lines.extend(_wrapped("            needs: ", item))
        if d.limitations:
            lines.extend(_wrapped("            but: ", d.limitations))
        lines.extend(_wrapped("            must record: ", d.must_record))
    return lines


def _wrapped(prefix: str, text: str) -> list[str]:
    body = textwrap.wrap(" ".join(text.split()), width=78 - len(prefix)) or [""]
    pad = " " * len(prefix)
    return [prefix + body[0]] + [pad + line for line in body[1:]]


def format_design(spec, points, best, result, checks, unseparated,
                  equipment=None) -> str:
    """The design half of the report. Same contract as the screening half: show
    the numbers that decided it, and say plainly what was not decided."""
    lines: list[str] = []
    lines.append("COLUMN DESIGN")
    lines.append(f"  keys        {spec.light_key} (light) / {spec.heavy_key} (heavy)")
    lines.append(f"  pressure    {spec.pressure_Pa/1e5:.3f} bar")
    lines.append(f"  recovery    {spec.light_key} {spec.lk_recovery_to_distillate:.3%} "
                 f"overhead, {spec.heavy_key} {spec.hk_recovery_to_bottoms:.3%} bottoms")
    lines.append(f"  feed        {_feed_condition_line(spec, result)}")
    lines.append("")
    lines.append("REFLUX SWEEP")
    lines.append(f"  {'k':>6}{'stages':>9}{'annualised $/yr':>19}")
    for p in points:
        if not p.converged:
            lines.append(f"  {p.k:>6.2f}{'--':>9}{'no design':>19}   {p.error or ''}")
            continue
        mark = "  <- cheapest" if best is not None and p is best else ""
        lines.append(f"  {p.k:>6.2f}{p.stages:>9.0f}"
                     f"{p.annualised_cost_USD_yr:>19,.0f}{mark}")
    lines.append("")

    if result.converged:
        lines.append("PRODUCTS (kmol/hr)")
        d_total = sum(result.distillate.values())
        b_total = sum(result.bottoms.values())
        for name in result.distillate:
            d = result.distillate[name]
            b = result.bottoms.get(name, 0.0)
            lines.append(
                f"  {name:<12}{d:>10.3f} overhead ({d/d_total:>7.3%})"
                f"{b:>12.3f} bottoms ({b/b_total:>7.3%})" if d_total and b_total
                else f"  {name:<12}{d:>10.3f} overhead{b:>12.3f} bottoms"
            )
        lines.append("")

    if equipment:
        lines.extend(_format_equipment(equipment))
        lines.append("")

    lines.append("VERIFICATION")
    for c in checks:
        lines.append(f"  [{'PASS' if c.passed else 'FAIL'}]  {c.name:<22}{c.detail}")

    if unseparated:
        lines.append("")
        lines.append("NOT SPECIFIED")
        for n in unseparated:
            d = result.distillate.get(n, 0.0)
            b = result.bottoms.get(n, 0.0)
            total = d + b
            if total <= 0:
                lines.append(f"  {n}: absent from both products.")
                continue
            # Report where it WENT, read off the result. The earlier draft of
            # this note asserted "left together in the bottoms" without looking,
            # which would be wrong for any volatile non-key.
            stream, flow = (("bottoms", result.bottoms) if b >= d
                            else ("overhead", result.distillate))
            stream_total = sum(flow.values()) or 1.0
            companions = sorted(m for m, v in flow.items()
                                if m != n and v / stream_total > 0.01)
            with_whom = ", ".join(companions) if companions else "anything else"
            lines.append(f"  {n}: {100*max(d, b)/total:.1f}% to the {stream}, "
                         f"where it was NOT separated from {with_whom}.")
        lines.append("  No specification distinguishes these components, so the column")
        lines.append("  was never asked to split them. Separate products need a second column.")
    return "\n".join(lines)
