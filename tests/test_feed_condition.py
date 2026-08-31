"""Feed thermal condition, q -- heuristic steps 15 to 17.

q is defined the way the McCabe-Thiele feed line defines it: the moles of
liquid added to the stripping section per mole of feed,

    q = (H_saturated_vapour - H_feed) / (H_saturated_vapour - H_saturated_liquid)

all three enthalpies taken at the FEED COMPOSITION and the COLUMN pressure.
So q = 1 is a saturated liquid, q = 0 a saturated vapour, and the sign carries
the rest.
"""
import pytest

from sepsyn.feed_condition import feed_condition
from sepsyn.types import Component, Feed

P_ATM = 101325.0


def bt_feed(T_K: float, P_Pa: float = P_ATM) -> Feed:
    """Benzene/toluene, the well-behaved binary. 60/40, no azeotrope."""
    return Feed(
        components=(Component("Benzene", "71-43-2", 60.0),
                    Component("Toluene", "108-88-3", 40.0)),
        T_K=T_K, P_Pa=P_Pa,
    )


def test_cold_liquid_feed_is_subcooled():
    """A feed at 25 C into a column boiling near 90 C is subcooled, so q > 1.

    This is the case the heuristic list calls out: it is easy to assume the
    common default of a saturated liquid, and a subcooled feed is NOT that.
    """
    fc = feed_condition(bt_feed(298.15), P_ATM)
    assert fc is not None
    assert fc.q > 1.0
    assert fc.classification == "subcooled_liquid"


def test_feed_at_its_own_bubble_point_is_a_saturated_liquid():
    """Round trip: put the feed at the bubble temperature the calculation
    itself reports, and q must come back as 1."""
    first = feed_condition(bt_feed(298.15), P_ATM)
    assert first is not None
    fc = feed_condition(bt_feed(first.bubble_T_K), P_ATM)
    assert fc is not None
    assert fc.q == pytest.approx(1.0, abs=1e-3)
    assert fc.classification == "saturated_liquid"


def test_feed_at_its_own_dew_point_is_a_saturated_vapour():
    first = feed_condition(bt_feed(298.15), P_ATM)
    assert first is not None
    fc = feed_condition(bt_feed(first.dew_T_K), P_ATM)
    assert fc is not None
    assert fc.q == pytest.approx(0.0, abs=1e-3)
    assert fc.classification == "saturated_vapor"


def test_feed_between_bubble_and_dew_is_two_phase():
    first = feed_condition(bt_feed(298.15), P_ATM)
    assert first is not None
    midpoint = 0.5 * (first.bubble_T_K + first.dew_T_K)
    fc = feed_condition(bt_feed(midpoint), P_ATM)
    assert fc is not None
    assert 0.0 < fc.q < 1.0
    assert fc.classification == "two_phase"


def test_hot_feed_is_superheated_vapour():
    fc = feed_condition(bt_feed(500.0), P_ATM)
    assert fc is not None
    assert fc.q < 0.0
    assert fc.classification == "superheated_vapor"


def test_q_is_evaluated_at_the_COLUMN_pressure_not_the_feed_pressure():
    """The whole point of step 15: q is a property of the feed AT THE COLUMN.

    The same physical stream is a subcooled liquid into an atmospheric column
    and something else entirely into a vacuum column, because the bubble point
    moved. A q computed at feed pressure would report the same number for both.
    """
    stream_T = 340.0
    atmospheric = feed_condition(bt_feed(stream_T), P_ATM)
    vacuum = feed_condition(bt_feed(stream_T), 20000.0)
    assert atmospheric is not None and vacuum is not None
    assert atmospheric.q != vacuum.q
    assert atmospheric.classification == "subcooled_liquid"
    assert vacuum.classification != "subcooled_liquid"


def test_no_VLE_at_all_returns_None_rather_than_a_number():
    """Above the critical pressure of every component there is no saturated
    liquid to measure q against. That is a missing number, not a zero --
    returning 0.0 would read as the specific claim "saturated vapour"."""
    assert feed_condition(bt_feed(298.15), 2.0e7) is None


def test_a_feed_far_above_its_cryogenic_bubble_point_is_superheated():
    """H2/methane at 25 C. Both components are supercritical AT FEED
    TEMPERATURE, but the mixture still has a bubble point at 1 atm -- near
    22 K -- so q is computable and the feed is a superheated vapour by a wide
    margin.

    Pinned because it is the boundary between two questions that look alike:
    whether a q exists (thermodynamics, this module) and whether a column can
    be built (screening, rules R-04 and R-05). This module must not answer the
    second one by refusing to answer the first.
    """
    hydrogen = Feed(
        components=(Component("Hydrogen", "1333-74-0", 60.0),
                    Component("Methane", "74-82-8", 40.0)),
        T_K=298.15, P_Pa=P_ATM,
    )
    fc = feed_condition(hydrogen, P_ATM)
    assert fc is not None
    assert fc.classification == "superheated_vapor"
    assert fc.bubble_T_K < 100.0
