"""An undetermined column must block a cost, not be quietly costed.

sepsyn's own screening flagged two of three columns in M3's winning sequence as
UNDETERMINED, and evaluate_sequence designed, costed and ranked the sequence
anyway at $513,461/yr. A rigorous solve then could not converge those columns,
because propane traces reach a condenser at 1.16 bar where they condense at
234 K against cooling water at 313 K.

That is the failure this project exists to prevent, committed by this project:
a rule said it could not confirm the result and the layer above printed a
confident number.
"""
import pytest

from sepsyn.properties import resolve
from sepsyn.sequencing.enumeration import enumerate_sequences
from sepsyn.sequencing.evaluate import evaluate_sequence
from sepsyn.sequencing.rank import rank, sweep
from sepsyn.simulators.biosteam_adapter import BioSteamSimulator
from sepsyn.types import Component, Feed

ORDER = ("Propane", "Butane", "Pentane", "Hexane")


def feed_of(flows, T_K=330.0):
    return Feed(components=tuple(Component(n, resolve(n), f)
                                 for n, f in zip(ORDER, flows)),
                T_K=T_K, P_Pa=101325.0)


@pytest.fixture(scope="module")
def adversarial():
    """The feed whose winning sequence was reported at $513,461/yr while two
    of its three columns were flagged undetermined."""
    root = next(iter(enumerate_sequences(ORDER)))
    return evaluate_sequence(BioSteamSimulator(), feed_of((10., 20., 60., 10.)),
                             root)


def test_an_undetermined_column_is_recorded_on_the_sequence(adversarial):
    assert adversarial.undetermined_by
    assert "R-09" in adversarial.undetermined_by


def test_an_undetermined_sequence_reports_NO_COST(adversarial):
    """The number that was wrong. A cost for a train containing a column the
    tool declined to endorse is a confident answer about something unverified."""
    assert adversarial.total_cost_USD_yr is None
    assert adversarial.total_vapour_kmol_hr is None


def test_it_is_NOT_eliminated_though(adversarial):
    """Undetermined is not infeasible. The sequence may be perfectly good once
    someone confirms a partial condenser or a light-ends vent, and eliminating
    it would hide a viable route."""
    assert adversarial.feasible is True
    assert adversarial.eliminated_by == ""


def test_costable_is_the_distinction_that_matters(adversarial):
    assert adversarial.costable is False


def test_the_columns_still_carry_their_designs(adversarial):
    """Blocked from costing, not from designing. The per-column numbers remain
    for a reader who wants to see what was rejected and why."""
    assert all(c.result is not None for c in adversarial.columns)


def test_ranking_puts_undetermined_sequences_in_their_own_bucket():
    from sepsyn.sequencing.evaluate import SequenceOutcome
    from sepsyn.sequencing.train import Node

    good = SequenceOutcome(Node(group=("a",)), (), 100.0, 10.0, "")
    unk = SequenceOutcome(Node(group=("b",)), (), None, None, "",
                          undetermined_by="R-09 on Pentane/Hexane")
    r = rank([good, unk])
    assert r.winner is good
    assert len(r.undetermined) == 1
    assert r.undetermined[0] is unk
    assert unk not in r.near_optimal


def test_only_the_INDIRECT_sequence_survives_on_the_adversarial_feed():
    """The result that overturns the M3 answer.

    Four of the five sequences put light traces into a low-pressure condenser
    and are undetermined. The one that survives removes the HEAVIEST component
    first, so the light components stay together and every condenser operates
    where its overhead actually condenses.

    The previously reported winner was the direct sequence at $513,461/yr, and
    it is not costable at all. The only sequence the tool can stand behind
    costs 55 percent more.
    """
    r = sweep(BioSteamSimulator(), feed_of((10., 20., 60., 10.)), ORDER)
    assert len(r.undetermined) == 4
    assert len(r.all_feasible) == 1
    assert r.winner is not None
    assert r.winner.name.startswith("Propane+Butane+Pentane/Hexane")
    assert r.winner.total_cost_USD_yr == pytest.approx(794995.0, rel=0.02)


def test_the_previously_reported_winner_is_now_UNCOSTABLE():
    """The direct sequence, reported at $513,461/yr before undetermined
    columns were allowed to block. It is still feasible: it may be fine with a
    partial condenser. It is no longer costable."""
    r = sweep(BioSteamSimulator(), feed_of((10., 20., 60., 10.)), ORDER)
    direct = [o for o in r.undetermined
              if o.name.startswith("Propane/Butane+Pentane+Hexane |"
                                   " Butane/Pentane+Hexane")]
    assert direct, "the direct sequence must be present and undetermined"
    assert direct[0].total_cost_USD_yr is None
    assert direct[0].feasible is True
    assert "R-09" in direct[0].undetermined_by


def test_a_clean_feed_still_costs_and_ranks():
    """The guard must not swallow the ordinary case. Benzene/toluene style:
    a feed whose columns all screen cleanly."""
    r = sweep(BioSteamSimulator(), feed_of((40., 30., 20., 10.)), ORDER)
    assert r.evaluated == 5
    costable = [o for o in r.all_feasible]
    assert costable, "a clean alkane feed must still produce costable sequences"
    assert r.winner is not None
    assert r.winner.total_cost_USD_yr > 0
