"""The four classic sequencing heuristics, as proxies.

A proxy is a cheap ESTIMATOR of the objective, not a competitor to it. The spec
argues that "easiest split first", "hardest last", "most plentiful first" and
"favour equimolar splits" are four estimators of one quantity, invented before
anyone could evaluate 42 sequences in two seconds. They exist here to be
SCORED against the evaluated ranking, not trusted.

Each textbook rule states which split to perform first, so each proxy chooses a
split point for a group and recurses. One proxy yields one sequence per feed,
and designs nothing on the way. If a proxy needed a design, scoring it against
the designed answer would be circular.
"""
from dataclasses import dataclass

from sepsyn.sequencing.train import Node


@dataclass(frozen=True)
class AdjacentAlphas:
    """Relative volatility for each adjacent pair, WITH its conditions.

    Same discipline as sepsyn.types.Alpha. A proxy is cheap, not exempt: an
    alpha quoted without its temperature and pressure is meaningless whoever is
    holding it.
    """
    values: dict[tuple[str, str], float]
    T_K: float
    P_Pa: float
    basis: str


def adjacent_alphas(feed, order: tuple[str, ...], P_Pa: float) -> AdjacentAlphas:
    """Alphas for the adjacent pairs of the ordered list, at one condition.

    ONE condition for the whole train, deliberately. Each column in a real
    sequence settles its own pressure, but a proxy that had to resolve pressures
    would be doing the expensive part of the work it exists to avoid. The single
    reference condition is an approximation, and it is recorded here so that the
    approximation travels with the number.
    """
    from sepsyn.properties import relative_volatilities

    alphas = relative_volatilities(feed, P_Pa)
    by_pair = {a.pair: a.value for a in alphas}
    values: dict[tuple[str, str], float] = {}
    for a, b in zip(order, order[1:]):
        if (a, b) in by_pair:
            values[(a, b)] = by_pair[(a, b)]
        elif (b, a) in by_pair and by_pair[(b, a)] > 0:
            values[(a, b)] = 1.0 / by_pair[(b, a)]
    T = alphas[0].T_K if alphas else 0.0
    return AdjacentAlphas(
        values=values, T_K=T, P_Pa=P_Pa,
        basis=(f"bubble point of the whole feed at {P_Pa/1e5:.3f} bar, one "
               f"reference condition for the entire train"),
    )


def _build(order: tuple[str, ...], choose) -> Node:
    """Apply a split-point rule recursively to make one sequence."""
    if len(order) == 1:
        return Node(group=order)
    k = choose(order)
    return Node(group=order, k=k,
                light=_build(order[:k], choose),
                heavy=_build(order[k:], choose))


def _easiest_first(order, flows, alphas):
    """Split where the volatility gap is widest."""
    def choose(group):
        return max(range(1, len(group)),
                   key=lambda k: alphas.values.get((group[k - 1], group[k]), 1.0))
    return _build(order, choose)


def _hardest_last(order, flows, alphas):
    """Defer the narrowest volatility gap.

    On a first cut this agrees with easiest_first, because avoiding the hardest
    pair and taking the easiest one are the same instruction when there is one
    cut to make. They diverge further down, which is why both are scored.
    """
    def choose(group):
        if len(group) == 2:
            return 1
        hardest = min(range(1, len(group)),
                      key=lambda k: alphas.values.get((group[k - 1], group[k]), 1.0))
        options = [k for k in range(1, len(group)) if k != hardest]
        return max(options or [hardest],
                   key=lambda k: alphas.values.get((group[k - 1], group[k]), 1.0))
    return _build(order, choose)


def _most_plentiful_first(order, flows, alphas):
    """Isolate the largest flow as early as possible.

    The cut is made on whichever side of the most plentiful component is
    nearer, so that it is removed in the fewest cuts. When it sits in the middle
    this does NOT cut at an end, which is exactly where this proxy parts company
    with the volatility ones.
    """
    def choose(group):
        biggest = max(group, key=lambda n: flows.get(n, 0.0))
        i = group.index(biggest)
        return i if i > 0 else 1
    return _build(order, choose)


def _equimolar(order, flows, alphas):
    """Split the molar flow as evenly as the cut points allow."""
    def choose(group):
        total = sum(flows.get(n, 0.0) for n in group)
        def imbalance(k):
            light = sum(flows.get(n, 0.0) for n in group[:k])
            return abs(light - (total - light))
        return min(range(1, len(group)), key=imbalance)
    return _build(order, choose)


PROXIES = {
    "easiest_first": _easiest_first,
    "hardest_last": _hardest_last,
    "most_plentiful_first": _most_plentiful_first,
    "equimolar": _equimolar,
}
