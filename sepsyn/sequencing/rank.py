"""Rank the sequences, and say how far the ranking can be trusted.

The measurement behind this module, recorded in the spec: annualised cost and
total vapour load select the SAME winner at 4, 5 and 6 components, but their
full orderings diverge by up to 14 of 42 places at six components.

So the winner is reported as a winner, and everything past it as an UNORDERED
near-optimal set. An ordered leaderboard past position one would assert a
precision the evidence does not support, and anything downstream consuming a
shortlist would be consuming an artefact of which metric happened to be chosen.
"""
from dataclasses import dataclass

from sepsyn.sequencing.enumeration import enumerate_sequences
from sepsyn.sequencing.evaluate import SequenceOutcome, evaluate_sequence

# Within this fraction of the winner's cost counts as indistinguishable. The
# shortcut methods underneath carry more error than this between them, which is
# what M2 exists to quantify; until it does, a 5% gap is not a real difference.
NEAR_OPTIMAL_TOLERANCE = 0.05


@dataclass(frozen=True)
class Ranking:
    winner: SequenceOutcome | None
    near_optimal: tuple[SequenceOutcome, ...]
    eliminated: tuple[SequenceOutcome, ...]
    metrics_agree_on_winner: bool
    orderings_identical: bool
    worst_displacement: int
    evaluated: int


def rank(outcomes: list[SequenceOutcome],
         tolerance: float = NEAR_OPTIMAL_TOLERANCE) -> Ranking:
    feasible = [o for o in outcomes if o.feasible]
    eliminated = tuple(o for o in outcomes if not o.feasible)
    if not feasible:
        return Ranking(None, (), eliminated, True, True, 0, len(outcomes))

    by_cost = sorted(feasible, key=lambda o: o.total_cost_USD_yr)
    by_vapour = sorted(feasible, key=lambda o: o.total_vapour_kmol_hr)
    winner = by_cost[0]

    position = {id(o): i for i, o in enumerate(by_vapour)}
    displacement = max(abs(i - position[id(o)]) for i, o in enumerate(by_cost))

    cutoff = winner.total_cost_USD_yr * (1.0 + tolerance)
    near = tuple(o for o in feasible if o.total_cost_USD_yr <= cutoff)

    return Ranking(
        winner=winner,
        near_optimal=near,
        eliminated=eliminated,
        metrics_agree_on_winner=(by_cost[0] is by_vapour[0]),
        orderings_identical=(displacement == 0),
        worst_displacement=displacement,
        evaluated=len(outcomes),
    )


def sweep(sim, feed, order: tuple[str, ...], **kw) -> Ranking:
    """Evaluate every sharp-split sequence for this feed and rank them.

    Exhaustive by design. The spec measured 0.01 s per column, so 42 sequences
    of six components take about two seconds and there is nothing to gain from
    pruning at the sizes this tool supports.
    """
    outcomes = [evaluate_sequence(sim, feed, root, **kw)
                for root in enumerate_sequences(order)]
    return rank(outcomes)
