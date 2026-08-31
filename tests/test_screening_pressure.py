"""Screening must use the pressure the column will actually run at.

Raised in review: relative volatility is a property of a pair AT a condition,
so it cannot be evaluated before the pressure is settled. Screening therefore
cannot precede the pressure decision -- which is the order both the numbered
list and the dependency graph claimed.

Measured on propane/n-butane, where the condenser forces 13.69 bar:

    alpha screened at feed pressure (1.01 bar)  6.100
    alpha at the real column pressure           3.383   +80.3%

The verdict did not flip there, but the headline number was wrong by more than
the condenser-duty discrepancy this project was built around, and on a
close-boiling pair needing high pressure it would flip.
"""
import pytest

from sepsyn.cli import design_if_feasible, screen
from sepsyn.properties import resolve
from sepsyn.types import Component, Feed

ATM = 101325.0


def propane_butane():
    """Condenses against cooling water only above about 13.7 bar, so the
    column pressure and the feed pressure are far apart."""
    return Feed(components=(Component("Propane", resolve("Propane"), 60.0),
                            Component("Butane", resolve("Butane"), 40.0)),
                T_K=298.15, P_Pa=ATM)


def test_alpha_is_screened_at_the_COLUMN_pressure_not_the_feed_pressure():
    record, _, _ = screen(propane_butane(), "Propane", "Butane")
    assert record.column_P_Pa == pytest.approx(13.69e5, rel=0.02)
    assert record.min_alpha == pytest.approx(3.383, rel=0.02)


def test_the_alpha_carries_that_same_pressure():
    """Alpha already printed the pressure it was computed at. The bug was that
    the printed pressure was not the column's."""
    record, _, _ = screen(propane_butane(), "Propane", "Butane")
    for alpha in record.alphas:
        assert alpha.P_Pa == pytest.approx(record.column_P_Pa)


def test_a_specified_pressure_DISABLES_the_pressure_heuristic():
    """The reviewer's sharpest point. If the user has fixed the pressure, the
    'start at one atmosphere and work upward' rule never runs -- so knowing
    what is already specified has to come before running any heuristic."""
    record, _, _ = screen(propane_butane(), "Propane", "Butane",
                          column_P_Pa=ATM)
    assert record.column_P_Pa == pytest.approx(ATM)
    assert record.min_alpha == pytest.approx(6.100, rel=0.02)
    assert "specified" in record.column_P_basis


def test_the_basis_says_where_the_pressure_came_from():
    given, _, _ = screen(propane_butane(), "Propane", "Butane", column_P_Pa=ATM)
    derived, _, _ = screen(propane_butane(), "Propane", "Butane")
    assert given.column_P_basis != derived.column_P_basis
    assert "cooling water" in derived.column_P_basis


def test_without_keys_it_falls_back_to_the_feed_pressure_and_SAYS_so():
    """The pressure heuristic needs a light key to know what must condense.
    Without one the tool cannot settle the pressure, so it must report the
    fallback rather than present a feed-pressure alpha as a column alpha."""
    record, _, _ = screen(propane_butane())
    assert record.column_P_Pa == pytest.approx(ATM)
    assert "feed pressure" in record.column_P_basis
    assert "not been settled" in record.column_P_basis


def test_screening_and_design_agree_on_the_pressure():
    """The consistency guard. If these ever diverge, the design being built is
    not the one that was screened."""
    feed = propane_butane()
    record, _, _ = screen(feed, "Propane", "Butane")
    spec = design_if_feasible(feed, "Propane", "Butane")[0]
    assert spec.pressure_Pa == pytest.approx(record.column_P_Pa)


def test_a_specified_pressure_is_carried_into_the_design():
    feed = propane_butane()
    spec = design_if_feasible(feed, "Propane", "Butane", column_P_Pa=20.0e5)[0]
    assert spec.pressure_Pa == pytest.approx(20.0e5)
