"""The minimum-vapour report.

Written so a reader cannot mistake a bound for a duty. V_min is what the
separation requires at INFINITE stages; a real column needs more, and a reader
who read these numbers as reboiler loads would size everything too small.
"""
from math import comb

from sepsyn.sequencing.enumeration import label

WIDTH = 78


def catalan(n_components: int) -> int:
    """How many sharp-split sequences separate this many components.

    Catalan(n-1). Printed beside the number of splits actually evaluated so the
    polynomial claim is visible rather than asserted.
    """
    m = n_components - 1
    return comb(2 * m, m) // (m + 1)


def format_vmin(selection, outcome, proxy_scores=(), order=()) -> str:
    lines: list[str] = []
    n = len(order) or len(selection.root.group)

    lines.append("MINIMUM VAPOUR")
    lines.append("  The least vapour that must be boiled to make these "
                 "splits, at")
    lines.append("  infinite stages. A lower bound, NOT a duty: every real "
                 "column needs")
    lines.append("  more than the number beside it.")
    if selection.splits:
        lines.append(f"  Volatilities {selection.splits[0].alpha_basis}")
    lines.append("")

    lines.append("OPTIMAL SEQUENCE")
    lines.append(f"  {label(selection.root)}")
    lines.append(f"  {selection.total_V_min_kmol_hr:,.1f} kmol/hr total")
    lines.append("")
    for s in selection.splits:
        name = f"{'+'.join(s.light)} / {'+'.join(s.heavy)}"
        lines.append(f"    {name:<44}{s.V_min_kmol_hr:>10,.1f} kmol/hr")
    lines.append("")

    total_seq = catalan(n)
    lines.append(f"  Found by dynamic programming: {selection.evaluated} "
                 f"(group, split) pairs evaluated,")
    lines.append(f"  against {total_seq} sequences and "
                 f"{total_seq * (n - 1)} column designs by enumeration. The "
                 f"answer is the")
    lines.append("  provable optimum, not the best of a ranked list.")
    lines.append("")

    lines.append("VERIFICATION")
    lines.append("  Minimum vapour cannot see whether a column's overhead will "
                 "condense, so")
    lines.append("  the chosen sequence is screened again as a real design.")
    for c in outcome.columns:
        name = (f"{'+'.join(c.split.light_group)} / "
                f"{'+'.join(c.split.heavy_group)}")
        lines.append(f"    {name:<40}{c.pressure_Pa / 1e5:>8.2f} bar   "
                     f"{c.screening}")
    if outcome.eliminated_by:
        lines.append(f"  ELIMINATED: {outcome.eliminated_by}")
    elif outcome.undetermined_by:
        lines.append("")
        lines.append(f"  UNDETERMINED: {outcome.undetermined_by}")
        lines.append("  The sequence is not ruled out, but no cost is reported "
                     "for it. A rule")
        lines.append("  fired that cannot be acted on until a calculation is "
                     "done.")
    else:
        lines.append("  Every column screened feasible.")
    lines.append("")

    if proxy_scores:
        lines.append("HEURISTICS")
        lines.append("  Each textbook rule, scored by how much MORE vapour its "
                     "sequence needs")
        lines.append("  than the optimum. Measured against thermodynamics, not "
                     "against this")
        lines.append("  tool's own cost model.")
        lines.append("")
        for p in proxy_scores:
            if p.excess is None:
                verdict = f"({p.note})"
            elif p.excess <= 0.0:
                verdict = "the optimum"
            else:
                verdict = f"+{p.excess * 100:.1f}% vapour"
            lines.append(f"    {p.name:<22}{verdict}")
            lines.append(f"      {p.sequence_name}")
        lines.append("")
    return "\n".join(lines)
