"""The shape of a separation train.

A sequence is a binary TREE, not a flat list of splits. The tree is what makes
product propagation natural: a column's light product is the feed to its light
subtree and its heavy product the feed to its heavy subtree. A flat list would
lose which stream feeds which column and force that structure to be rebuilt.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Node:
    """One column, or a leaf product.

    `group` is the components entering, in volatility order, lightest first.
    `k` is the split point: everything before it goes overhead. `k is None`
    means this is a finished product, not a column.
    """
    group: tuple[str, ...]
    k: int | None = None
    light: "Node | None" = None
    heavy: "Node | None" = None

    @property
    def is_leaf(self) -> bool:
        return self.k is None

    @property
    def light_group(self) -> tuple[str, ...]:
        return self.group[:self.k]

    @property
    def heavy_group(self) -> tuple[str, ...]:
        return self.group[self.k:]

    @property
    def light_key(self) -> str:
        """Heaviest component going overhead. Adjacent to the heavy key, which
        is what makes the split sharp."""
        return self.group[self.k - 1]

    @property
    def heavy_key(self) -> str:
        return self.group[self.k]

    def splits(self) -> list["Node"]:
        """Every column in the tree, in pre-order: this one, then the light
        branch, then the heavy branch. Pre-order matters because it is also a
        valid evaluation order once products propagate."""
        if self.is_leaf:
            return []
        return [self] + self.light.splits() + self.heavy.splits()
