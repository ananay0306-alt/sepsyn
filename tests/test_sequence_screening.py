"""Screening applies to every column, not just the original feed.

A sub-mixture can behave differently from the feed it came from. Ethanol and
water are separable on paper until you notice the azeotrope; a sequence that
creates that pair partway down the train must be eliminated there, citing the
rule, rather than costed as though it worked.
"""
import pytest

from sepsyn.properties import resolve
from sepsyn.sequencing.evaluate import evaluate_sequence
from sepsyn.sequencing.train import Node
from sepsyn.simulators.biosteam_adapter import BioSteamSimulator
from sepsyn.types import Component, Feed


def feed_of(pairs, T_K=330.0):
    return Feed(
        components=tuple(Component(n, resolve(n), f) for n, f in pairs),
        T_K=T_K, P_Pa=101325.0,
    )


def acetone_train():
    """Split acetone off first, leaving ethanol/water in one column."""
    order = ("Acetone", "Ethanol", "Water")
    return order, Node(group=order, k=1,
                       light=Node(group=("Acetone",)),
                       heavy=Node(group=("Ethanol", "Water"), k=1,
                                  light=Node(group=("Ethanol",)),
                                  heavy=Node(group=("Water",))))


def test_every_column_records_its_screening_verdict():
    order = ("Propane", "Butane", "Pentane")
    root = Node(group=order, k=1,
                light=Node(group=("Propane",)),
                heavy=Node(group=("Butane", "Pentane"), k=1,
                           light=Node(group=("Butane",)),
                           heavy=Node(group=("Pentane",))))
    out = evaluate_sequence(BioSteamSimulator(),
                            feed_of([("Propane", 40.0), ("Butane", 30.0),
                                     ("Pentane", 20.0)]), root)
    assert len(out.columns) == 2
    for c in out.columns:
        assert c.screening in ("feasible", "caution", "undetermined",
                               "infeasible", "unknown")


def test_a_sub_mixture_azeotrope_eliminates_the_sequence_CITING_THE_RULE():
    """Acetone, ethanol and water. Splitting acetone off first leaves the
    ethanol/water pair in one column, which is azeotropic. The sequence must be
    eliminated at that column and must name R-03."""
    _, root = acetone_train()
    out = evaluate_sequence(BioSteamSimulator(),
                            feed_of([("Acetone", 30.0), ("Ethanol", 40.0),
                                     ("Water", 30.0)]), root)
    assert not out.feasible
    assert "R-03" in out.eliminated_by
    # Named precisely. An earlier version asserted only that "Ethanol" appeared,
    # which passed while the FIRST column was being eliminated for the ethanol/
    # water azeotrope between two of its non-keys. That is a different bug
    # wearing the same message.
    assert "Ethanol/Water" in out.eliminated_by
    assert out.columns[0].split.light_key == "Acetone"
    assert out.columns[0].screening == "feasible", (
        "the acetone split is clean and must survive; only the ethanol/water "
        "column is blocked")
    assert out.columns[1].screening == "infeasible"


def test_screening_stops_the_train_before_the_expensive_design_runs():
    """A column that screens infeasible is not designed. Designing it anyway
    would waste the solve and, worse, produce a cost for a column that should
    never be built."""
    _, root = acetone_train()
    out = evaluate_sequence(BioSteamSimulator(),
                            feed_of([("Acetone", 30.0), ("Ethanol", 40.0),
                                     ("Water", 30.0)]), root)
    eliminated = [c for c in out.columns if c.eliminated_by]
    assert len(eliminated) == 1
    assert eliminated[0].result is None


def test_a_clean_alkane_train_is_not_eliminated():
    order = ("Propane", "Butane", "Pentane")
    root = Node(group=order, k=2,
                light=Node(group=("Propane", "Butane"), k=1,
                           light=Node(group=("Propane",)),
                           heavy=Node(group=("Butane",))),
                heavy=Node(group=("Pentane",)))
    out = evaluate_sequence(BioSteamSimulator(),
                            feed_of([("Propane", 40.0), ("Butane", 30.0),
                                     ("Pentane", 20.0)]), root)
    assert out.feasible, out.eliminated_by
