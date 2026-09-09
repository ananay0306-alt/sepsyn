"""Multicomponent columns via BioSTEAM ShortcutColumn (Fenske-Underwood-Gilliland).

design_column stays on BinaryDistillation. This is a separate method because
swapping the correlation underneath the existing one would change every number
in the 251 tests that depend on it.
"""
import pytest

from sepsyn.properties import resolve
from sepsyn.simulators.base import ColumnSpec
from sepsyn.simulators.biosteam_adapter import BioSteamSimulator
from sepsyn.types import Component, Feed

ORDER = ["Propane", "Butane", "Pentane", "Hexane"]
FLOWS = [40.0, 30.0, 20.0, 10.0]


def alkane_feed(names=None, flows=None):
    names = names or ORDER
    flows = flows or FLOWS
    return Feed(
        components=tuple(Component(n, resolve(n), f) for n, f in zip(names, flows)),
        T_K=330.0, P_Pa=5.0e5,
    )


@pytest.fixture(scope="module")
def result():
    return BioSteamSimulator().design_multicomponent(
        alkane_feed(),
        ColumnSpec("Butane", "Pentane", 0.99, 0.99, 5.0e5),
    )


def test_a_four_component_column_converges(result):
    assert result.converged, result.error


def test_the_split_is_SHARP_at_the_named_keys(result):
    """Everything lighter than the light key goes overhead, everything heavier
    than the heavy key goes to the bottoms. That is what makes the sequence
    tree meaningful: a group either leaves together or it does not."""
    assert result.distillate["Propane"] == pytest.approx(40.0, rel=1e-3)
    assert result.bottoms["Hexane"] == pytest.approx(10.0, rel=1e-3)
    # Negligible RELATIVE to the component's own flow, not exactly zero. A
    # numerical FUG solve leaves a trace of each non-key on the wrong side:
    # measured 1.7e-5 kmol/hr of hexane overhead out of 10, which is 0.0002%.
    # Asserting an exact zero would be asserting a property of the arithmetic
    # rather than of the separation.
    assert result.distillate["Hexane"] / 10.0 < 1e-5
    assert result.bottoms["Propane"] / 40.0 < 1e-5


def test_the_keys_meet_their_recoveries(result):
    assert result.distillate["Butane"] / 30.0 == pytest.approx(0.99, abs=5e-3)
    assert result.bottoms["Pentane"] / 20.0 == pytest.approx(0.99, abs=5e-3)


def test_it_returns_the_numbers_ranking_needs(result):
    """Cost and reflux are what Task 5 aggregates. A design that converged but
    reported no cost would rank as free."""
    assert result.stages > 0
    assert result.reflux > result.minimum_reflux > 0
    assert result.installed_cost_USD > 0
    assert result.utility_cost_USD_hr > 0


def test_every_feed_component_appears_in_both_products(result):
    """Reported, not just the keys. Nothing in a light/heavy-key spec
    constrains the others, so where they went is a result."""
    for name in ORDER:
        assert name in result.distillate
        assert name in result.bottoms


def test_a_failure_is_returned_as_data_not_raised():
    """Sweeping sequences will hit infeasible columns routinely, and an
    infeasible column is an answer about the design rather than a crash."""
    bad = BioSteamSimulator().design_multicomponent(
        alkane_feed(),
        ColumnSpec("Butane", "Pentane", 0.99, 0.99, 5.0e5,
                   condenser_type="thermosiphon"),
    )
    assert not bad.converged
    assert "thermosiphon" in (bad.error or "")


def test_it_works_on_a_binary_group_too():
    """Leaves of a sequence tree are single components, but a two-component
    group is a perfectly ordinary column and the evaluator must not special
    case it."""
    r = BioSteamSimulator().design_multicomponent(
        alkane_feed(["Propane", "Butane"], [40.0, 30.0]),
        ColumnSpec("Propane", "Butane", 0.99, 0.99, 5.0e5),
    )
    assert r.converged, r.error
    assert r.stages > 0
