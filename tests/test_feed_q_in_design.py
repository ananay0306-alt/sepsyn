"""q must travel WITH the design. Heuristic steps 15, 16 and 17.

Step 17 is the reason this file exists: "two designs at different q are not
comparable, and this is the most commonly unstated assumption in a column
specification." Before this, sepsyn inherited whatever thermal condition the
feed happened to arrive at, used it, and never wrote it down.
"""
import pytest

from sepsyn.simulators.base import ColumnSpec
from sepsyn.simulators.biosteam_adapter import BioSteamSimulator
from sepsyn.types import Component, Feed

P_ATM = 101325.0


def cold_benzene_toluene():
    """25 C into a column boiling near 90 C -- a markedly subcooled feed."""
    return Feed(
        components=(Component("Benzene", "71-43-2", 60.0),
                    Component("Toluene", "108-88-3", 40.0)),
        T_K=298.15, P_Pa=P_ATM,
    )


def test_spec_defaults_to_taking_the_feed_as_it_arrives():
    """None is not a default q of 1. It means 'whatever the feed already is',
    which is the behaviour every earlier design had -- now stated rather than
    inherited silently."""
    assert ColumnSpec("Benzene", "Toluene", 0.99, 0.99, P_ATM).feed_q is None


@pytest.fixture(scope="module")
def as_arrived():
    sim = BioSteamSimulator()
    return sim.design_column(cold_benzene_toluene(),
                             ColumnSpec("Benzene", "Toluene", 0.99, 0.99, P_ATM))


@pytest.fixture(scope="module")
def preheated_to_bubble_point():
    sim = BioSteamSimulator()
    return sim.design_column(
        cold_benzene_toluene(),
        ColumnSpec("Benzene", "Toluene", 0.99, 0.99, P_ATM, feed_q=1.0))


def test_the_design_records_the_q_it_actually_ran_at(as_arrived):
    """Step 17. The number has to come back attached to the design, not be
    recoverable only by re-deriving it from the feed."""
    assert as_arrived.converged, as_arrived.error
    assert as_arrived.feed_q is not None
    assert as_arrived.feed_q > 1.0, "a 25 C benzene/toluene feed is subcooled"


def test_preheating_to_a_saturated_liquid_is_recorded_as_q_of_one(
        preheated_to_bubble_point):
    r = preheated_to_bubble_point
    assert r.converged, r.error
    assert r.feed_q == pytest.approx(1.0, abs=1e-3)


def test_feed_condition_changes_the_answer(as_arrived, preheated_to_bubble_point):
    """The claim heuristic step 15 makes, asserted rather than repeated.

    Preheating a subcooled feed to its bubble point moves duty out of the
    reboiler and into a feed heater. If these two designs came back identical,
    feed_q would be decorative and step 17 would not be worth enforcing.
    """
    assert as_arrived.converged and preheated_to_bubble_point.converged
    assert as_arrived.reboiler_duty_kW > preheated_to_bubble_point.reboiler_duty_kW
    assert as_arrived.feed_q != pytest.approx(preheated_to_bubble_point.feed_q)


def test_a_vapour_feed_is_a_different_design_again():
    """q = 0 sends the whole feed up the column as vapour, which loads the
    rectifying section instead of the stripping section."""
    sim = BioSteamSimulator()
    vapour = sim.design_column(
        cold_benzene_toluene(),
        ColumnSpec("Benzene", "Toluene", 0.99, 0.99, P_ATM, feed_q=0.0))
    assert vapour.converged, vapour.error
    assert vapour.feed_q == pytest.approx(0.0, abs=1e-3)
