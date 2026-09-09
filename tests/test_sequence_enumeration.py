"""Sharp-split sequence enumeration. Pure combinatorics, no chemistry."""
import pytest

from sepsyn.sequencing.enumeration import enumerate_sequences, label
from sepsyn.sequencing.train import Node

# Catalan(n-1) is the number of sharp-split sequences for n components.
CATALAN = {1: 1, 2: 1, 3: 2, 4: 5, 5: 14, 6: 42, 7: 132}


@pytest.mark.parametrize("n", sorted(CATALAN))
def test_sequence_count_is_catalan(n):
    group = tuple("ABCDEFG"[:n])
    assert len(list(enumerate_sequences(group))) == CATALAN[n]


@pytest.mark.parametrize("n", [3, 4, 5, 6])
def test_every_sequence_has_exactly_n_minus_one_columns(n):
    group = tuple("ABCDEFG"[:n])
    for root in enumerate_sequences(group):
        assert len(root.splits()) == n - 1


def test_no_duplicate_sequences():
    group = tuple("ABCDE")
    labels = [label(r) for r in enumerate_sequences(group)]
    assert len(labels) == len(set(labels))


def test_a_split_names_the_adjacent_pair_as_its_keys():
    """The light key is the heaviest component going overhead and the heavy key
    is the lightest going to the bottoms. They are adjacent in volatility
    order, which is what makes the split sharp."""
    root = Node(group=("A", "B", "C"), k=2,
                light=Node(group=("A", "B"), k=1,
                           light=Node(group=("A",)), heavy=Node(group=("B",))),
                heavy=Node(group=("C",)))
    assert root.light_group == ("A", "B")
    assert root.heavy_group == ("C",)
    assert root.light_key == "B"
    assert root.heavy_key == "C"


def test_a_leaf_is_a_single_component_and_is_not_a_split():
    leaf = Node(group=("A",))
    assert leaf.is_leaf
    assert leaf.splits() == []


def test_every_group_in_a_tree_is_contiguous_in_volatility_order():
    """A sharp split cannot produce a group with a gap in it. If it did, the
    tree would describe a separation no single column can perform."""
    order = tuple("ABCDE")
    index = {c: i for i, c in enumerate(order)}
    for root in enumerate_sequences(order):
        for node in [root] + root.splits():
            positions = sorted(index[c] for c in node.group)
            assert positions == list(range(positions[0], positions[-1] + 1))


def test_a_single_component_yields_one_empty_sequence():
    roots = list(enumerate_sequences(("A",)))
    assert len(roots) == 1
    assert roots[0].splits() == []
