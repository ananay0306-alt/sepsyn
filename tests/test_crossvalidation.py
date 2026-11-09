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
        return replace(self.run, stages=stages, feed_stage=feed_stage,
                       stages_read_back=stages,
                       feed_stage_read_back=feed_stage)


@pytest.fixture
def matched():
    ours = sepsyn_result(theoretical_stages=19, theoretical_feed_stage=10,
                         feed_q=1.3)
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


@pytest.mark.parametrize("bad", [0.0, float("nan"), None])
def test_an_unusable_DWSIM_duty_blocks_the_gap_instead_of_vanishing(bad):
    """Review 11-08: a 0.0 duty used to drop out of the gaps silently while
    the comparison stayed reportable, so the reader took it as agreement."""
    ours = sepsyn_result(theoretical_stages=19, theoretical_feed_stage=10)
    c = compare(FEED, SPEC, FakeBioSteam(ours),
                FakeDwsim(dwsim_run(condenser_duty_kW=bad)))
    assert c.reportable is False and c.gaps == ()
    assert "condenser duty" in format_comparison(c)


def test_a_missing_sepsyn_temperature_blocks_the_gap(matched):
    feed, spec, _, dwsim = matched
    ours = sepsyn_result(theoretical_stages=19, theoretical_feed_stage=10,
                         bottoms_T_K=None)
    c = compare(feed, spec, FakeBioSteam(ours), dwsim)
    assert c.reportable is False


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
    assert "feed stage placement" not in format_comparison(c)


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
    assert "feed stage placement" in format_comparison(c)
    assert -0.80 < duties["condenser duty"] < -0.60
    assert -0.35 < duties["reboiler duty"] < -0.15


def gate_column():
    flows = {"Butane": 0.2, "Pentane": 59.4, "Hexane": 9.999978788248363}
    feed = Feed(components=tuple(Component(n, resolve(n), f)
                                 for n, f in flows.items()),
                T_K=330.0, P_Pa=101325.0)
    return feed, ColumnSpec("Pentane", "Hexane", 0.99, 0.99, 117999.0)


def test_the_R09_raised_column_is_buildable_and_condenses_in_DWSIM():
    """The gate for answering R-09 by design (11-08). Pentane/Hexane from the
    alkane train, 0.2 kmol/hr butane trace, raised from 1.157 to 1.180 bar so
    the designed distillate condenses against cooling water. September
    recorded this column as one a rigorous solve could not converge. The real
    solve, replayed: it converges, and DWSIM's condenser is at 313.6 K, above
    cooling water. The duty GAP is not reportable; see the next test."""
    from sepsyn.properties import COOLING_WATER_T

    feed, spec = gate_column()
    run = FixtureTransport(FIXTURES).run(feed, spec, 24, 19)
    assert run.converged
    assert run.distillate_T_K >= COOLING_WATER_T
    assert (run.stages_read_back, run.feed_stage_read_back) == (24, 19)


def test_a_feed_the_two_tools_see_in_DIFFERENT_phases_reports_no_gap():
    """11-08. At 330 K and 1.18 bar this feed is all vapour once flashed, and
    DWSIM flashes it; BioSTEAM keeps the stream it was handed, a liquid,
    q = 0.91. The old check said "both sides take the feed as it arrives",
    which held by construction while the two tools modelled feeds about
    490 kW apart, and the -24 % / +72 % duty gaps it let through were that
    difference, not shortcut error."""
    from sepsyn.simulators.biosteam_adapter import BioSteamSimulator

    feed, spec = gate_column()
    c = compare(feed, spec, BioSteamSimulator(),
                DwsimSimulator(FixtureTransport(FIXTURES)))
    assert c.reportable is False
    (fc,) = [a for a in c.assertions if a.name == "feed condition"]
    assert fc.holds is False
    assert "vapour fraction" in fc.detail


def test_a_DWSIM_feed_state_never_read_back_is_UNKNOWN(matched):
    feed, spec, ours, _ = matched
    c = compare(feed, spec, ours,
                FakeDwsim(dwsim_run(feed_vapour_fraction=None)))
    (fc,) = [a for a in c.assertions if a.name == "feed condition"]
    assert fc.holds is None and c.reportable is False


def test_an_imposed_q_reaching_DWSIM_holds_when_both_feeds_agree(matched):
    """q = 1 imposed on both sides, both feeds at their bubble points."""
    feed, _, _, _ = matched
    spec = replace(SPEC, feed_q=1.0)
    ours = sepsyn_result(theoretical_stages=19, theoretical_feed_stage=10,
                         feed_q=1.0, feed_T_K=353.3)
    theirs = dwsim_run(feed_q=1.0, feed_vapour_fraction=0.0,
                       feed_T_K_read_back=353.6)
    c = compare(feed, spec, FakeBioSteam(ours), FakeDwsim(theirs))
    (fc,) = [a for a in c.assertions if a.name == "feed condition"]
    assert fc.holds is True, fc.detail


def test_vapour_fraction_zero_is_NOT_enough_when_q_is_imposed(matched):
    """A subcooled DWSIM feed also reads vapour fraction 0. The feed
    temperatures must agree too."""
    feed, _, _, _ = matched
    spec = replace(SPEC, feed_q=1.0)
    ours = sepsyn_result(theoretical_stages=19, theoretical_feed_stage=10,
                         feed_q=1.0, feed_T_K=353.3)
    theirs = dwsim_run(feed_q=1.0, feed_vapour_fraction=0.0,
                       feed_T_K_read_back=298.15)
    c = compare(feed, spec, FakeBioSteam(ours), FakeDwsim(theirs))
    (fc,) = [a for a in c.assertions if a.name == "feed condition"]
    assert fc.holds is False and not c.reportable


def test_a_liquid_feed_in_both_tools_holds(matched):
    """sepsyn q = 1.3 (subcooled) and DWSIM vapour fraction 0."""
    c = compare(*matched)
    (fc,) = [a for a in c.assertions if a.name == "feed condition"]
    assert fc.holds is True


def test_a_DOWNSTREAM_column_compares_once_both_tools_see_a_saturated_feed():
    """11-08. The gate column as it really sits in the train: fed a saturated
    liquid (q = 1) at 1.18 bar, imposed in BioSTEAM and, by vapour fraction,
    in DWSIM. Feeds at 316.6 K and 316.7 K. The +72 % reboiler gap of the
    mismatched feeds becomes -10.9 %, and the condenser -15.5 %: the shortcut
    under-predicting, as on the four-alkane column."""
    from dataclasses import replace
    from sepsyn.simulators.biosteam_adapter import BioSteamSimulator

    feed, spec = gate_column()
    c = compare(feed, replace(spec, feed_q=1.0), BioSteamSimulator(),
                DwsimSimulator(FixtureTransport(FIXTURES)))
    assert c.reportable, format_comparison(c)
    duties = {g.quantity: g.relative for g in c.gaps if g.unit == "kW"}
    assert -0.25 < duties["condenser duty"] < -0.05
    assert -0.20 < duties["reboiler duty"] < -0.03
