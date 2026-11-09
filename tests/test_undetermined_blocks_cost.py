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


ETHANE_ORDER = ("Ethane", "Propane", "Butane", "Pentane")


@pytest.fixture(scope="module")
def adversarial():
    """A column whose R-09 doubt CANNOT be answered: ethane's critical point is
    305 K, so its overhead does not condense against cooling water at any
    pressure. The guard is tested here, where it must hold.

    Corrected 2026-11-08. R-09 is now answered by designing the column: the condenser temperature of the designed distillate, raising the pressure in small steps when the traces pull it just below cooling water. DWSIM converges the raised column and agrees on its condenser temperature to 0.1 K, so the September non-convergence these tests were built on does not reproduce. The alkane feed that used to sit here is now costable; see
    test_the_adversarial_alkane_feed_is_now_fully_costable."""
    feed = Feed(components=tuple(Component(n, resolve(n), f) for n, f in
                                 zip(ETHANE_ORDER, (10., 20., 60., 10.))),
                T_K=330.0, P_Pa=101325.0)
    root = next(iter(enumerate_sequences(ETHANE_ORDER)))
    return evaluate_sequence(BioSteamSimulator(), feed, root)


def test_an_undetermined_column_is_recorded_on_the_sequence(adversarial):
    assert adversarial.undetermined_by
    assert "R-09" in adversarial.undetermined_by


def test_an_unanswerable_R09_says_what_was_measured(adversarial):
    """Not just that it is undetermined: the designed condenser temperature,
    and that the pressure cap was reached."""
    assert "even at the 30 bar cap" in adversarial.undetermined_by
    assert " K, below cooling water" in adversarial.undetermined_by


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


def test_the_adversarial_alkane_feed_is_now_fully_costable():
    """Corrected 2026-11-08. R-09 is now answered by designing the column: the condenser temperature of the designed distillate, raising the pressure in small steps when the traces pull it just below cooling water. DWSIM converges the raised column and agrees on its condenser temperature to 0.1 K, so the September non-convergence these tests were built on does not reproduce.

    Measured 11-08: all five sequences cost, and the direct sequence wins at
    about $505,000/yr, close to the $513,461 M3 first reported. September's
    "only the indirect sequence survives, at 55 % more" rested on the doubt
    this change answers."""
    r = sweep(BioSteamSimulator(), feed_of((10., 20., 60., 10.)), ORDER)
    assert len(r.undetermined) == 0
    assert len(r.all_feasible) == 5
    assert r.winner.name.startswith("Propane/Butane+Pentane+Hexane |"
                                    " Butane/Pentane+Hexane")
    assert r.winner.total_cost_USD_yr == pytest.approx(505171.0, rel=0.02)


def test_the_direct_sequence_records_HOW_its_R09_doubts_were_answered():
    """Costable is not the same as unflagged. Each column R-09 doubted carries
    the measured answer. Measured 11-08: Butane/Pentane+Hexane condenses at
    313.4 K as designed; Pentane/Hexane needed 1.157 to 1.180 bar."""
    root = next(iter(enumerate_sequences(ORDER)))
    o = evaluate_sequence(BioSteamSimulator(), feed_of((10., 20., 60., 10.)),
                          root)
    by_lk = {c.split.light_key: c for c in o.columns}
    assert by_lk["Propane"].resolved == ""
    assert "R-09 answered" in by_lk["Butane"].resolved
    assert "raising" not in by_lk["Butane"].resolved
    raised = by_lk["Pentane"]
    assert "from 1.157 to 1.180 bar" in raised.resolved
    assert "raised to 1.180 bar" in raised.pressure_basis


def test_a_clean_feed_still_costs_and_ranks():
    """The guard must not swallow the ordinary case. Benzene/toluene style:
    a feed whose columns all screen cleanly."""
    r = sweep(BioSteamSimulator(), feed_of((40., 30., 20., 10.)), ORDER)
    assert r.evaluated == 5
    costable = [o for o in r.all_feasible]
    assert costable, "a clean alkane feed must still produce costable sequences"
    assert r.winner is not None
    assert r.winner.total_cost_USD_yr > 0
