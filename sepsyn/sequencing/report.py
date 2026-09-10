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


def format_sequencing(ranking: Ranking, scorecard=None, tags=None) -> str:
    lines: list[str] = []
    costable = len(ranking.all_feasible)
    feasible = costable
    lines.append("SEQUENCES")
    lines.append(f"  {ranking.evaluated} enumerated, {costable} costable, "
                 f"{len(ranking.undetermined)} undetermined, "
                 f"{len(ranking.eliminated)} eliminated")
    if ranking.undetermined and costable <= 1:
        # Say it plainly. A reader seeing "BEST SEQUENCE" naturally assumes it
        # beat the others; here it was the only candidate.
        lines.extend(_wrap(
            "  ",
            f"Only {costable} of {ranking.evaluated} could be costed, so the "
            f"best sequence below was not chosen over the others. It is the "
            f"only one the tool can stand behind."))
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

    if tags and ranking.winner is not None:
        lines.append("")
        lines.append("EXPOSURE  (counted, NOT used to rank)")
        lines.extend(_wrap(
            "  ",
            "Tagged components, weighted by how much of them passes through "
            "each column. This did not change the ranking above and eliminated "
            "nothing: a traversal threshold would be invented and a materials "
            "cost factor has no source. The trade-off is yours to resolve."))
        shown = [ranking.winner] + [o for o in ranking.near_optimal
                                    if o is not ranking.winner]
        for o in shown:
            if not o.exposure:
                continue
            lines.append(f"    {o.name}")
            for name, load in sorted(o.exposure.items()):
                marks = "/".join(sorted(tags.get(name, ())))
                cols = o.exposure_columns.get(name, 0)
                lines.extend(_wrap(
                    "      ",
                    f"{name} ({marks}): {load:,.1f} kmol/hr summed across "
                    f"{cols} of {len(o.columns)} columns"))
            lines.append(f"      ${o.total_cost_USD_yr:,.0f}/yr")

    if scorecard is not None and scorecard.scores:
        lines.append("")
        lines.append("HEURISTICS  (scored against the evaluated ranking)")
        if scorecard.proxies_agree:
            lines.extend(_wrap(
                "  ",
                "Every heuristic picked the same sequence on this feed, so "
                "this scorecard cannot tell them apart. Agreement here is not "
                "evidence that any of them is right."))
        for s in sorted(scorecard.scores, key=lambda x: x.name):
            if s.picked_winner:
                verdict = "picked the winner"
            elif s.sequence_status == "undetermined":
                verdict = "named a sequence the tool cannot endorse"
            elif s.sequence_status == "eliminated":
                verdict = "named a sequence that was eliminated"
            elif s.cost_penalty is None:
                verdict = "named a sequence that could not be costed"
            else:
                verdict = f"{s.cost_penalty:+.1%} worse than the winner"
            lines.append(f"    {s.name:<22} {verdict}")
            lines.extend(_wrap("      ", s.sequence_name))

    if ranking.undetermined:
        lines.append("")
        lines.append("UNDETERMINED  (designed, but NOT costed or ranked)")
        lines.extend(_wrap(
            "  ",
            "A rule fired on one of these columns and cannot be acted on until "
            "a calculation is done, so no cost is reported. These are not ruled "
            "out: each may be perfectly good once the named question is "
            "settled."))
        for o in ranking.undetermined:
            lines.append(f"    {o.name}")
            lines.extend(_wrap("      ", o.undetermined_by))

    if ranking.eliminated:
        lines.append("")
        lines.append("ELIMINATED")
        for o in ranking.eliminated:
            lines.append(f"  {o.name}")
            lines.extend(_wrap("      ", o.eliminated_by))
    return "\n".join(lines)
