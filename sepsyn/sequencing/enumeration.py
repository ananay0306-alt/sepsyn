"""Every sharp-split sequence for an ordered component list.

The count is Catalan(n-1), which is 42 at six components and 429 at eight. The
probes recorded in the spec measured 0.01 s per column, so exhaustive
enumeration is affordable across the whole supported range and no pruning
heuristic is needed.
"""
from typing import Iterator

from sepsyn.sequencing.train import Node


def enumerate_sequences(group: tuple[str, ...]) -> Iterator[Node]:
    """Yield the root Node of every sharp-split sequence.

    A sharp split divides a CONTIGUOUS group into two contiguous subgroups, so
    the recursion only ever chooses where to cut, never which components to
    take. That constraint is what keeps the count at Catalan rather than
    exponential, and it is also what makes each split performable by one
    ordinary column.
    """
    if len(group) == 1:
        yield Node(group=group)
        return
    for k in range(1, len(group)):
        for light in enumerate_sequences(group[:k]):
            for heavy in enumerate_sequences(group[k:]):
                yield Node(group=group, k=k, light=light, heavy=heavy)


def label(node: Node) -> str:
    """A stable one-line name for a sequence, for reports and for de-duping."""
    return " | ".join(
        f"{'+'.join(s.light_group)}/{'+'.join(s.heavy_group)}"
        for s in node.splits()
    )
