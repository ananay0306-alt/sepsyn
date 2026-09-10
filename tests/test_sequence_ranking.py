"""Ranking sequences, and being honest about how far the ranking can be trusted.

The spec measured cost and vapour load agreeing on the WINNER at 4, 5 and 6
components but diverging by up to 14 of 42 places further down. So the winner is
reported as a winner and everything past it as an unordered near-optimal set.
An ordered leaderboard would assert precision the evidence does not support.
"""
import pytest

from sepsyn.properties import resolve
from sepsyn.sequencing.evaluate import SequenceOutcome
from sepsyn.sequencing.rank import rank, sweep
from sepsyn.sequencing.train import Node
from sepsyn.simulators.biosteam_adapter import BioSteamSimulator
from sepsyn.types import Component, Feed

ORDER = ("Propane", "Butane", "Pentane", "Hexane")


def alkane_feed():
    return Feed(
        components=tuple(Component(n, resolve(n), f)
                         for n, f in zip(ORDER, (40.0, 30.0, 20.0, 10.0))),
        T_K=330.0, P_Pa=101325.0,
    )


def fake(name, cost, vapour, eliminated=""):
    root = Node(group=(name,))
    return SequenceOutcome(root, (), None if eliminated else cost,
                           None if eliminated else vapour, eliminated)


def test_the_cheapest_feasible_sequence_wins():
    r = rank([fake("a", 300.0, 10.0), fake("b", 200.0, 8.0),
              fake("c", 400.0, 12.0)])
    assert r.winner.total_cost_USD_yr == 200.0


def test_eliminated_sequences_are_kept_and_reported_separately():
    """Kept, not dropped. 'Could not be built' and 'was not tried' are
    different facts and a reader is entitled to tell them apart."""
    r = rank([fake("a", 300.0, 10.0), fake("bad", 0.0, 0.0, "R-03 azeotrope")])
    assert len(r.eliminated) == 1
    assert "R-03" in r.eliminated[0].eliminated_by
    assert r.winner.total_cost_USD_yr == 300.0


def test_the_near_optimal_set_holds_everything_within_tolerance():
    r = rank([fake("a", 100.0, 10.0), fake("b", 104.0, 11.0),
              fake("c", 130.0, 12.0)], tolerance=0.05)
    assert {o.total_cost_USD_yr for o in r.near_optimal} == {100.0, 104.0}


def test_it_reports_whether_the_two_METRICS_AGREE_on_the_winner():
    agree = rank([fake("a", 100.0, 10.0), fake("b", 200.0, 20.0)])
    assert agree.metrics_agree_on_winner is True

    disagree = rank([fake("a", 100.0, 30.0), fake("b", 200.0, 10.0)])
    assert disagree.metrics_agree_on_winner is False


def test_it_reports_HOW_FAR_the_two_orderings_diverge():
    """The number the spec measured at 14 of 42. Reported so a reader knows
    how much of the ordering to trust."""
    r = rank([fake("a", 100.0, 30.0), fake("b", 200.0, 20.0),
              fake("c", 300.0, 10.0)])
    assert r.orderings_identical is False
    assert r.worst_displacement == 2


def test_identical_orderings_report_zero_displacement():
    r = rank([fake("a", 100.0, 10.0), fake("b", 200.0, 20.0),
              fake("c", 300.0, 30.0)])
    assert r.orderings_identical is True
    assert r.worst_displacement == 0


def test_all_sequences_eliminated_gives_no_winner_rather_than_a_crash():
    r = rank([fake("a", 0.0, 0.0, "R-03"), fake("b", 0.0, 0.0, "R-02")])
    assert r.winner is None
    assert r.near_optimal == ()
    assert len(r.eliminated) == 2


def test_sweep_evaluates_every_sequence_for_a_real_feed():
    """Four components: five sequences, fifteen columns. The spec measured
    this at 0.2 s."""
    r = sweep(BioSteamSimulator(), alkane_feed(), ORDER)
    assert r.evaluated == 5
    assert r.winner is not None
    assert r.winner.total_cost_USD_yr > 0


def test_the_INDIRECT_sequence_wins_once_undetermined_columns_block():
    """Corrected 2026-09-10. This previously asserted the DIRECT sequence won.

    Four of the five sequences send light traces into low-pressure condensers,
    R-09 fires, and they are undetermined rather than costable. The survivor
    removes the heaviest component first, keeping the light ends together in
    high-pressure columns.

    The direct sequence was formerly reported as the winner at $462,010/yr on
    this feed, computed from columns the tool had itself flagged.
    """
    r = sweep(BioSteamSimulator(), alkane_feed(), ORDER)
    assert len(r.undetermined) == 4
    assert r.winner.name.startswith("Propane+Butane+Pentane/Hexane")
