"""Formatting. The output IS the product -- the whole point is that a reader
can check the reasoning, so rules that did NOT fire are printed too."""
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
    lines.append("PROPERTIES")
    lines.append(f"  {'component':<12}{'Tb (K)':>10}{'Tc (K)':>10}   state at feed")
    for c in feed.components:
        cas = c.cas or resolve(c.name)
        tb, tc = boiling_point(cas), critical_temperature(cas)
        state = "SUPERCRITICAL" if feed.T_K > tc else "condensable"
        lines.append(f"  {c.name:<12}{tb:>10.1f}{tc:>10.1f}   {state}")

    if record.min_alpha is None:
        lines.append("  alpha: undefined -- no vapour-liquid equilibrium at these conditions")
    else:
        for a in record.alphas:
            lines.append(
                f"  alpha {a.pair[0]}/{a.pair[1]} = {a.value:.3f} "
                f"at {a.T_K:.1f} K, {a.P_Pa/1e5:.3f} bar ({a.basis})"
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
