"""Evaluating one sequence end to end.

The property that matters most here is PROPAGATION: the feed to a downstream
column is the actual product of the column above it, carrying its impurities,
not the idealised group flow. The spec's probes used idealised flows and said
so; this is where that simplification is removed.
"""
import pytest

from sepsyn.properties import resolve
from sepsyn.sequencing.enumeration import enumerate_sequences
from sepsyn.sequencing.evaluate import evaluate_sequence
from sepsyn.sequencing.train import Node
from sepsyn.simulators.biosteam_adapter import BioSteamSimulator
from sepsyn.types import Component, Feed

ORDER = ("Propane", "Butane", "Pentane", "Hexane")
FLOWS = (40.0, 30.0, 20.0, 10.0)


def alkane_feed():
    return Feed(
        components=tuple(Component(n, resolve(n), f) for n, f in zip(ORDER, FLOWS)),
        T_K=330.0, P_Pa=101325.0,
    )


def direct_sequence():
    """Remove the lightest component first, one at a time."""
    return Node(
        group=ORDER, k=1,
        light=Node(group=("Propane",)),
        heavy=Node(
            group=("Butane", "Pentane", "Hexane"), k=1,
            light=Node(group=("Butane",)),
            heavy=Node(group=("Pentane", "Hexane"), k=1,
                       light=Node(group=("Pentane",)),
                       heavy=Node(group=("Hexane",))),
        ),
    )


@pytest.fixture(scope="module")
def outcome():
    return evaluate_sequence(BioSteamSimulator(), alkane_feed(), direct_sequence())


def test_a_sequence_of_four_components_has_three_columns(outcome):
    assert len(outcome.columns) == 3


def test_it_reports_a_total_cost_and_a_total_vapour_load(outcome):
    assert outcome.feasible, outcome.eliminated_by
    assert outcome.total_cost_USD_yr > 0
    assert outcome.total_vapour_kmol_hr > 0


def test_the_total_is_the_sum_of_the_columns(outcome):
    """A total that is not the sum of its parts cannot be audited."""
    assert outcome.total_cost_USD_yr == pytest.approx(
        sum(c.annualised_cost_USD_yr for c in outcome.columns))
    assert outcome.total_vapour_kmol_hr == pytest.approx(
        sum(c.vapour_kmol_hr for c in outcome.columns))


def test_PRODUCTS_PROPAGATE_rather_than_ideal_flows_being_reused(outcome):
    """THE test for this task.

    The second column's feed is the first column's bottoms, so it carries the
    1% of propane the first column failed to recover overhead. If idealised
    group flows were reused, the second column would see exactly zero propane.
    """
    second = outcome.columns[1]
    first = outcome.columns[0]
    propane_into_second = first.result.bottoms["Propane"]
    assert propane_into_second > 0.0, "the first column is not perfect"
    total_second = sum(second.result.distillate.values()) + \
        sum(second.result.bottoms.values())
    assert total_second == pytest.approx(
        sum(first.result.bottoms.values()), rel=1e-6)


def test_each_column_settles_its_own_pressure(outcome):
    """A propane overhead needs a far higher pressure than a hexane one, so a
    single train-wide pressure would be wrong for most of the columns."""
    pressures = [c.pressure_Pa for c in outcome.columns]
    assert len(set(round(p) for p in pressures)) > 1
    for c in outcome.columns:
        assert c.pressure_basis


def test_vapour_load_is_distillate_times_reflux_plus_one(outcome):
    """Defined once in the spec; pinned here so it cannot drift."""
    c = outcome.columns[0]
    D = sum(c.result.distillate.values())
    assert c.vapour_kmol_hr == pytest.approx(D * (c.result.reflux + 1.0))


def test_a_column_that_fails_marks_the_SEQUENCE_not_just_the_column():
    """One unbuildable column makes the whole sequence unbuildable. Reporting
    a total cost for a train containing a column that did not converge would
    be reporting the cost of something that cannot be built."""
    class AlwaysFails:
        def design_multicomponent(self, feed, spec):
            from sepsyn.simulators.base import ColumnResult
            return ColumnResult({}, {}, 0.0, 0.0, 0.0, 0.0, 0.0, False,
                                error="ValueError: contrived failure")

    out = evaluate_sequence(AlwaysFails(), alkane_feed(), direct_sequence())
    assert not out.feasible
    assert "contrived failure" in out.eliminated_by
    assert out.total_cost_USD_yr is None


def test_every_enumerated_sequence_can_be_evaluated():
    """Five sequences for four components, all of them designable."""
    sim = BioSteamSimulator()
    feed = alkane_feed()
    outs = [evaluate_sequence(sim, feed, r) for r in enumerate_sequences(ORDER)]
    assert len(outs) == 5
    assert all(o.feasible for o in outs), [o.eliminated_by for o in outs if not o.feasible]
