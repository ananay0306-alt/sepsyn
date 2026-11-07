"""The comparison, and the refusal. Hermetic: both simulators are fakes here,
and the recorded DWSIM run replays the real one measured 11-07."""
import os
from dataclasses import replace

import pytest

from sepsyn.crossvalidate import compare, format_comparison
from sepsyn.properties import resolve
from sepsyn.simulators.base import ColumnSpec
from sepsyn.simulators.dwsim_adapter import DwsimSimulator, FixtureTransport
from sepsyn.types import Component, Feed
from test_configuration_equivalence import dwsim_run, sepsyn_result

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "dwsim")
SPEC = ColumnSpec("Benzene", "Toluene", 0.99, 0.99, 101325.0)
FEED = Feed(components=(Component("Benzene", resolve("Benzene"), 60.0),
                        Component("Toluene", resolve("Toluene"), 40.0)),
            T_K=298.15, P_Pa=101325.0)


class FakeBioSteam:
    def __init__(self, result):
        self.result = result

    def design_column(self, feed, spec):
        return self.result


class FakeDwsim:
    def __init__(self, run):
        self.run, self.asked = run, None

    def design_from_stages(self, feed, spec, stages, feed_stage):
        self.asked = (stages, feed_stage)
        return replace(self.run, stages=stages, feed_stage=feed_stage)


@pytest.fixture
def matched():
    ours = sepsyn_result(theoretical_stages=19, theoretical_feed_stage=10)
    return FEED, SPEC, FakeBioSteam(ours), FakeDwsim(dwsim_run())


@pytest.fixture
def mismatched():
    ours = sepsyn_result(theoretical_stages=19, theoretical_feed_stage=10)
    bad = dwsim_run(condenser_spec={"type": "Reflux Ratio", "value": 1.5})
    return FEED, SPEC, FakeBioSteam(ours), FakeDwsim(bad)


def test_dwsim_is_handed_the_MAPPED_column(matched):
    *_, dwsim = matched
    compare(*matched)
    assert dwsim.asked == (20, 10)


def test_a_matched_pair_reports_gaps_on_the_UNIMPOSED_quantities(matched):
    c = compare(*matched)
    assert c.reportable is True
    assert {g.quantity for g in c.gaps} >= {"condenser duty", "reboiler duty"}


def test_products_are_NOT_reported_as_a_gap(matched):
    c = compare(*matched)
    assert not any("product" in g.quantity or "recovery" in g.quantity
                   for g in c.gaps)


def test_a_mismatched_configuration_reports_NO_gap_at_all(mismatched):
    c = compare(*mismatched)
    assert c.reportable is False
    assert c.gaps == ()


def test_the_refusal_names_which_assertion_failed(mismatched):
    text = format_comparison(compare(*mismatched))
    assert "NO GAP REPORTED" in text
    assert "specification basis" in text


def test_a_reported_gap_always_names_the_unattributed_contributors(matched):
    assert "property package" in format_comparison(compare(*matched))


def test_the_relative_gap_is_signed(matched):
    """Ours 1083.4 against DWSIM 1090.0 is an UNDER-prediction."""
    c = compare(*matched)
    (cond,) = [g for g in c.gaps if g.quantity == "condenser duty"]
    assert cond.relative == pytest.approx((1083.4 - 1090.0) / 1090.0)
    assert cond.relative < 0


def test_temperatures_are_compared_in_kelvin_not_percent(matched):
    c = compare(*matched)
    (td,) = [g for g in c.gaps if g.quantity == "distillate temperature"]
    assert td.relative is None
    assert td.difference == pytest.approx(353.4 - 353.6)


def test_an_imposed_feed_condition_blocks_the_gap(matched):
    feed, _, ours, dwsim = matched
    c = compare(feed, replace(SPEC, feed_q=1.0), ours, dwsim)
    assert c.reportable is False
    assert "feed condition" in format_comparison(c)


def test_a_missing_theoretical_count_is_refused_before_dwsim_runs(matched):
    feed, spec, _, dwsim = matched
    c = compare(feed, spec, FakeBioSteam(sepsyn_result()), dwsim)
    assert c.reportable is False and dwsim.asked is None


def test_the_reflux_omission_is_stated(matched):
    assert "not compared: reflux" in format_comparison(compare(*matched))


def test_the_recorded_benzene_toluene_run_replays_and_reports():
    """The real 11-07 DWSIM solve, 25 stages, feed at 13, replayed against a
    real BioSTEAM design."""
    from sepsyn.simulators.biosteam_adapter import BioSteamSimulator

    c = compare(FEED, SPEC, BioSteamSimulator(),
                DwsimSimulator(FixtureTransport(FIXTURES)))
    assert c.reportable, format_comparison(c)
    assert (c.dwsim_stages, c.dwsim_feed_stage) == (25, 13)
    duties = {g.quantity: g.relative for g in c.gaps if g.unit == "kW"}
    assert abs(duties["reboiler duty"]) < 0.10
    assert abs(duties["condenser duty"]) < 0.10


def test_the_recorded_alkane_run_reports_the_shortcut_UNDER_predicting():
    """The real 11-07 solve, 21 stages, feed at 6: M2's actual target.
    Measured -69.7 % on condenser duty and -25.4 % on reboiler duty. Pinned by
    sign and rough size, so a change in either tool shows up here."""
    from sepsyn.simulators.biosteam_adapter import BioSteamSimulator

    order = ("Propane", "Butane", "Pentane", "Hexane")
    feed = Feed(components=tuple(Component(n, resolve(n), f) for n, f in
                                 zip(order, (10.0, 20.0, 60.0, 10.0))),
                T_K=330.0, P_Pa=101325.0)
    spec = ColumnSpec("Propane", "Butane", 0.99, 0.99, 1369410.0)
    c = compare(feed, spec, BioSteamSimulator(),
                DwsimSimulator(FixtureTransport(FIXTURES)))
    assert c.reportable, format_comparison(c)
    assert (c.dwsim_stages, c.dwsim_feed_stage) == (21, 6)
    duties = {g.quantity: g.relative for g in c.gaps if g.unit == "kW"}
    assert -0.80 < duties["condenser duty"] < -0.60
    assert -0.35 < duties["reboiler duty"] < -0.15
