"""The sequencing report.

The near-optimal set is printed as a SET and labelled as one. Numbering the
entries would reintroduce the false precision that rank.py exists to avoid: the
measured divergence between the two ranking metrics is up to 14 of 42 places,
so a numbered list past the winner would be an artefact of the metric.
"""
import textwrap

from sepsyn.sequencing.rank import NEAR_OPTIMAL_TOLERANCE, Ranking


def _wrap(prefix: str, text: str) -> list[str]:
    body = textwrap.wrap(" ".join(text.split()), width=78 - len(prefix)) or [""]
    pad = " " * len(prefix)
    return [prefix + body[0]] + [pad + line for line in body[1:]]


def format_sequencing(ranking: Ranking) -> str:
    lines: list[str] = []
    feasible = ranking.evaluated - len(ranking.eliminated)
    lines.append("SEQUENCES")
    lines.append(f"  {ranking.evaluated} sequences enumerated, "
                 f"{feasible} designable, {len(ranking.eliminated)} eliminated")
    lines.append("")

    if ranking.winner is None:
        lines.append("  No sequence could be designed. Reasons below.")
    else:
        w = ranking.winner
        lines.append("BEST SEQUENCE")
        lines.append(f"  {w.name}")
        lines.append(f"  ${w.total_cost_USD_yr:,.0f} per year"
                     f"   |   {w.total_vapour_kmol_hr:,.1f} kmol/hr vapour"
                     f"   |   {len(w.columns)} columns")
        lines.append("")

        others = [o for o in ranking.near_optimal if o is not w]
        pct = int(NEAR_OPTIMAL_TOLERANCE * 100)
        lines.append(f"WITHIN {pct}% OF THE BEST  (a set, not ranked)")
        if not others:
            lines.append("  Nothing else comes close.")
        else:
            n = len(others)
            lines.extend(_wrap(
                "  ",
                f"{'This one is' if n == 1 else f'These {n} are'} not "
                f"meaningfully worse. The shortcut methods underneath carry "
                f"more error than {pct}% between them, so ordering "
                f"{'it' if n == 1 else 'them'} would be reporting noise."))
            for o in others:
                lines.append(f"    {o.name}")
                lines.append(f"      ${o.total_cost_USD_yr:,.0f}/yr")
        lines.append("")

        lines.append("HOW FAR TO TRUST THE ORDER")
        if ranking.metrics_agree_on_winner:
            lines.extend(_wrap(
                "  ",
                "Annualised cost and total vapour load select the same winning "
                "sequence, so the winner does not agree only by accident of "
                "which metric was used."))
        else:
            lines.extend(_wrap(
                "  ",
                "WARNING: cost and vapour load select DIFFERENT winners. The "
                "answer depends on which metric you trust, and neither has been "
                "validated against a rigorous solution."))
        if not ranking.orderings_identical:
            lines.extend(_wrap(
                "  ",
                f"Past the winner the two orderings diverge by up to "
                f"{ranking.worst_displacement} of {feasible} places, which is "
                f"why the set above is unordered."))

    if ranking.eliminated:
        lines.append("")
        lines.append("ELIMINATED")
        for o in ranking.eliminated:
            lines.append(f"  {o.name}")
            lines.extend(_wrap("      ", o.eliminated_by))
    return "\n".join(lines)
