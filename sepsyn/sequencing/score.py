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


@dataclass(frozen=True)
class VminProxyScore:
    """A textbook heuristic, scored against a THERMODYNAMIC bound.

    `score_proxies` above grades proxies against sepsyn's own cost ranking,
    which is circular: an unvalidated ruler measuring itself. Minimum vapour is
    not from the same family. It is an exact requirement derived from
    Underwood, it needs no cost data, and it does not depend on any of the
    layers -- Gilliland, tray efficiency, condenser type, diameter, cost
    correlation -- that the 09-09 and 09-10 measurements found wanting.
    """
    name: str
    sequence_name: str
    total_V_min_kmol_hr: float | None
    excess: float | None
    """Fraction ABOVE the optimum's total vapour. 0.0 means the proxy found the
    optimum. None when its sequence contains a split that cannot be made."""
    note: str = ""


def total_vmin_of(root, order, alpha, flows, q, downstream_q=1.0,
                  alpha_basis=""):
    """Total minimum vapour of an ARBITRARY sequence tree.

    Used to price a heuristic's choice on the same basis the dynamic program
    used for its own, which is the only way the comparison means anything. q
    is charged to the root split alone; every other column is fed a saturated
    product of the column above it.
    """
    from sepsyn.vmin.vapour import minimum_vapour

    root_group = tuple(order)
    total = 0.0
    for node in root.splits():
        sub = {c: flows[c] for c in node.group}
        group_q = q if node.group == root_group else downstream_q
        total += minimum_vapour(node.group, alpha, sub, group_q, node.k,
                                alpha_basis).V_min_kmol_hr
    return total


def score_proxies_against_vmin(feed, order, alpha, flows, q, optimum,
                               P_Pa, downstream_q=1.0):
    """Every proxy, priced in vapour against the provable optimum."""
    from sepsyn.vmin.underwood import NoUnderwoodRoot

    alphas = adjacent_alphas(feed, order, P_Pa)
    best = optimum.total_V_min_kmol_hr
    out = []
    for name, proxy in PROXIES.items():
        root = proxy(tuple(order), flows, alphas)
        try:
            total = total_vmin_of(root, order, alpha, flows, q, downstream_q)
        except NoUnderwoodRoot as exc:
            out.append(VminProxyScore(name, label(root), None, None,
                                      note=f"not computable: {exc}"))
            continue
        out.append(VminProxyScore(name, label(root), total,
                                  total / best - 1.0 if best else None))
    return tuple(out)
