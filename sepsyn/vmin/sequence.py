"""The optimal separation sequence, by dynamic programming.

A sequence is a binary tree over CONTIGUOUS groups, and the cheapest way to
separate a group does not depend on how that group was produced. That optimal
substructure is what makes the problem polynomial:

    Best(g) = 0                                  if |g| = 1
    Best(g) = min over k of  V_min(g, k) + Best(g[:k]) + Best(g[k:])

At ten components that is 165 split evaluations returning the provable optimum,
against 4,862 sequences and 43,758 column designs by enumeration.

The optimal substructure holds only under the SHARP-SPLIT idealisation. With
real splits impurities propagate and a group's sub-problem depends on its path,
which breaks the decomposition. That is why this module selects and does not
verify: the chosen sequence goes to M3's evaluator, which propagates real
products and screens every column.
"""
from dataclasses import dataclass
from functools import lru_cache

from sepsyn.sequencing.train import Node
from sepsyn.vmin.underwood import NoUnderwoodRoot
from sepsyn.vmin.vapour import SplitVapour, minimum_vapour


class NoFeasibleSequence(ValueError):
    """No complete sequence exists, because some adjacent pair cannot be
    split and every sequence needs that split."""


@dataclass(frozen=True)
class OptimalSequence:
    root: Node
    total_V_min_kmol_hr: float
    splits: tuple[SplitVapour, ...]
    evaluated: int
    """How many (group, split) pairs were evaluated. Reported so the
    polynomial claim is visible rather than asserted."""


def best_sequence(order: tuple[str, ...], alpha: dict[str, float],
                  flows: dict[str, float], q: float,
                  alpha_basis: str = "") -> OptimalSequence:
    """The minimum-total-vapour sequence for separating `order` completely."""
    counter = {"n": 0}

    @lru_cache(maxsize=None)
    def best(group: tuple[str, ...]):
        """(total V_min, Node, splits) for separating this group completely.

        Memoised on the group alone, which is the whole point: the same
        sub-group appears in many sequences and is solved once.
        """
        if len(group) == 1:
            return 0.0, Node(group=group), ()
        options = []
        refusals = []
        for k in range(1, len(group)):
            counter["n"] += 1
            sub = {c: flows[c] for c in group}
            try:
                split = minimum_vapour(group, alpha, sub, q, k, alpha_basis)
                light_total, light_node, light_splits = best(group[:k])
                heavy_total, heavy_node, heavy_splits = best(group[k:])
            except (NoUnderwoodRoot, NoFeasibleSequence) as exc:
                # This cut is unavailable, either because its own keys cannot
                # be separated or because one of its subtrees cannot be. Try
                # the others rather than abandoning the group.
                refusals.append(f"{group[k - 1]}/{group[k]}: {exc}")
                continue
            options.append((
                split.V_min_kmol_hr + light_total + heavy_total,
                Node(group=group, k=k, light=light_node, heavy=heavy_node),
                (split,) + light_splits + heavy_splits,
            ))
        if not options:
            raise NoFeasibleSequence(
                f"no split of {'+'.join(group)} leads to a complete "
                f"separation. " + " ".join(refusals)
            )
        return min(options, key=lambda o: o[0])

    total, root, splits = best(tuple(order))
    return OptimalSequence(root, total, splits, counter["n"])
