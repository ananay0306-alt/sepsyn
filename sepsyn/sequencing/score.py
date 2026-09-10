"""Score each proxy against the evaluated ranking.

This is the module that answers the question the whole milestone exists for.
When two textbook heuristics disagree about which split to do first, which one
is right? The answer is not argued from authority: the exhaustive ranking is
the ground truth, each proxy names one sequence, and the scorecard reports
whether it picked the winner and what being wrong cost.
"""
from dataclasses import dataclass

from sepsyn.sequencing.enumeration import label
from sepsyn.sequencing.heuristics import PROXIES, adjacent_alphas
from sepsyn.sequencing.rank import Ranking


@dataclass(frozen=True)
class ProxyScore:
    name: str
    sequence_name: str
    picked_winner: bool
    within_near_optimal: bool
    cost_penalty: float | None
    """Fraction above the winner's cost. None when the proxy named a sequence
    that could not be designed, or when nothing could be."""
    cost_USD_yr: float | None
    sequence_status: str = "unknown"
    """What the ranking made of the sequence this proxy named: winner,
    near-optimal, costable, undetermined, eliminated, or unknown.

    'undetermined' is the case that matters and it did not exist before
    2026-09-10: a heuristic can recommend a route the tool declines to endorse,
    which is a stronger statement than saying the heuristic is wrong. On the
    alkane feeds every classic proxy does exactly that."""


@dataclass(frozen=True)
class Scorecard:
    scores: tuple[ProxyScore, ...]
    winner_name: str
    proxies_agree: bool
    """True when every proxy named the same sequence. On such a feed the
    scorecard cannot discriminate between them, however confident it looks."""


def score_proxies(feed, order: tuple[str, ...], ranking: Ranking,
                  P_Pa: float) -> Scorecard:
    alphas = adjacent_alphas(feed, order, P_Pa)
    flows = {c.name: c.flow_kmol_hr for c in feed.components}

    # EVERY evaluated sequence, not only the near-optimal ones. A proxy that
    # names a feasible but expensive train must still report what it cost;
    # otherwise being badly wrong is indistinguishable from naming something
    # that could not be built, and both show as no penalty at all.
    costs = {o.name: o.total_cost_USD_yr for o in ranking.all_feasible}
    near = {o.name for o in ranking.near_optimal}
    status = {o.name: "undetermined" for o in ranking.undetermined}
    status.update({o.name: "eliminated" for o in ranking.eliminated})
    if ranking.winner is not None:
        costs.setdefault(ranking.winner.name, ranking.winner.total_cost_USD_yr)
        near.add(ranking.winner.name)

    winner_name = ranking.winner.name if ranking.winner else ""
    winner_cost = ranking.winner.total_cost_USD_yr if ranking.winner else None

    scores = []
    chosen: set[str] = set()
    for name, proxy in PROXIES.items():
        picked = label(proxy(order, flows, alphas))
        chosen.add(picked)
        cost = costs.get(picked)
        penalty = (None if (cost is None or not winner_cost)
                   else cost / winner_cost - 1.0)
        if bool(winner_name) and picked == winner_name:
            kind = "winner"
        elif picked in near:
            kind = "near-optimal"
        elif picked in costs:
            kind = "costable"
        else:
            kind = status.get(picked, "unknown")
        scores.append(ProxyScore(
            name=name,
            sequence_name=picked,
            picked_winner=bool(winner_name) and picked == winner_name,
            within_near_optimal=picked in near,
            cost_penalty=penalty,
            cost_USD_yr=cost,
            sequence_status=kind,
        ))
    return Scorecard(tuple(scores), winner_name, len(chosen) == 1)
