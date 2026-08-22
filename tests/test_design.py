"""Pressure from the cooling-water rule, reflux from a sweep.

Two branches of choose_pressure are only reachable with the right chemical, so
the feeds here are chosen from measured saturation pressures at 313.15 K:
methanol 0.36 bar (atmospheric is enough), ammonia 15.6 bar (raise the column),
hydrogen chloride 65.6 bar (past the cap, refrigerate), ethylene supercritical.
Without those the interesting branches never execute.
"""
import dataclasses

import pytest

from sepsyn.design import (
    DEFAULT_K_VALUES,
    MAX_PRESSURE_Pa,
    SweepPoint,
    best_point,
    choose_pressure,
    recoveries_for_purity,
    sweep_reflux,
)
from sepsyn.simulators.base import ColumnResult, ColumnSpec
from sepsyn.simulators.biosteam_adapter import BioSteamSimulator
from sepsyn.types import Component, Feed


def methanol_feed():
    return Feed(
        components=(
            Component("Methanol", "67-56-1", 100.0),
            Component("Water", "7732-18-5", 80.0),
            Component("Glycerol", "56-81-5", 25.0),
        ),
        T_K=330.0, P_Pa=101325.0,
    )


def one(name, cas):
    return Feed(components=(Component(name, cas, 50.0),), T_K=300.0, P_Pa=101325.0)


# --------------------------------------------------------------------------
# choose_pressure -- every branch, with the numbers that decide it
# --------------------------------------------------------------------------

def test_atmospheric_is_enough_for_methanol():
    """Methanol saturates at 0.36 bar at cooling-water temperature, so 1 atm
    condenses it and there is no reason to raise pressure."""
    P, note = choose_pressure(methanol_feed(), light_key="Methanol")
    assert P == pytest.approx(101325.0, rel=0.01)
    assert "cooling water" in note.lower()


def test_pressure_is_raised_when_the_overhead_will_not_condense_at_1_atm():
    """THE branch the plan could not reach.

    Ammonia saturates at 15.55 bar at 313.15 K (measured; literature 15.5).
    A column running at 1 atm would have nothing condensing overhead, so the
    heuristic must raise it. The original implementation read the pressure back
    off an untouched Stream and returned exactly 101325.0 for every chemical,
    which made this branch dead code AND told the user atmospheric was fine.
    """
    P, note = choose_pressure(one("Ammonia", "7664-41-7"), light_key="Ammonia")

    assert P > 101325.0, "ammonia cannot condense against cooling water at 1 atm"
    assert P == pytest.approx(15.55e5, rel=0.05)
    assert P < MAX_PRESSURE_Pa
    assert "bar" in note.lower()


def test_pressure_is_capped_and_refrigeration_named_when_the_duty_is_absurd():
    """Hydrogen chloride needs 65.6 bar. Past the cap, say so rather than
    returning a pressure no one would build."""
    P, note = choose_pressure(one("Hydrogen chloride", "7647-01-0"),
                              light_key="Hydrogen chloride")
    assert P == pytest.approx(MAX_PRESSURE_Pa)
    assert "refrigerat" in note.lower()


def test_supercritical_light_key_goes_straight_to_refrigeration():
    """Ethylene's critical temperature is 282 K, below cooling water at 313 K.
    No pressure condenses it; the answer is refrigeration, not a bigger number."""
    feed = Feed(components=(Component("Ethylene", "74-85-1", 50.0),
                            Component("Ethane", "74-84-0", 50.0)),
                T_K=250.0, P_Pa=101325.0)
    P, note = choose_pressure(feed, light_key="Ethylene")
    assert P > 101325.0 or "refrigerat" in note.lower()
    assert "refrigerat" in note.lower()


def test_the_pressure_returned_is_actually_computed_from_the_chemical():
    """Guard against the whole family of 'returned a default' defects.

    Three chemicals with different saturation pressures must not produce the
    same answer. The original code returned 101325.0 for all of them.
    """
    p_meoh, _ = choose_pressure(one("Methanol", "67-56-1"), "Methanol")
    p_nh3, _ = choose_pressure(one("Ammonia", "7664-41-7"), "Ammonia")
    p_hcl, _ = choose_pressure(one("Hydrogen chloride", "7647-01-0"),
                               "Hydrogen chloride")
    assert len({round(p_meoh), round(p_nh3), round(p_hcl)}) == 3


# --------------------------------------------------------------------------
# sweep_reflux -- the curve, including the points that failed
# --------------------------------------------------------------------------

class FailingSimulator:
    """A fake Simulator. The protocol exists precisely so this is possible --
    no chemistry, no BioSTEAM, and a failure exactly where we want one."""

    def __init__(self, fail_at):
        self.fail_at = set(fail_at)

    def design_column(self, feed, spec) -> ColumnResult:
        k = spec.reflux_over_minimum
        if k in self.fail_at:
            return ColumnResult({}, {}, 0.0, 0.0, 0.0, 0.0, 0.0, False,
                                error="RuntimeError: cannot meet specifications")
        return ColumnResult({"Methanol": 99.0}, {"Water": 79.2},
                            stages=100.0 / k, reflux=k, minimum_reflux=1.0,
                            installed_cost_USD=1e6 * k,
                            utility_cost_USD_hr=10.0 * k,
                            converged=True)

    def design_flash(self, feed, spec):
        raise NotImplementedError


def test_a_failed_reflux_point_stays_in_the_curve_and_says_why():
    """A dropped point is a lie of omission.

    Silently skipping non-converged designs hands back a curve that looks
    complete, so the caller cannot tell 'this reflux is uneconomic' from 'this
    reflux could not be designed'. Same standard the report and the property
    record are already held to.
    """
    pts = sweep_reflux(FailingSimulator(fail_at=[1.3, 1.5]), methanol_feed(),
                       ColumnSpec("Methanol", "Water", 0.99, 0.99, 101325.0),
                       k_values=[1.1, 1.3, 1.5, 2.0])

    assert len(pts) == 4, "every requested k must be accounted for"
    failed = [p for p in pts if not p.converged]
    assert [p.k for p in failed] == [1.3, 1.5]
    assert all(p.error for p in failed)
    assert all(p.error is None for p in pts if p.converged)


def test_best_point_ignores_failed_points():
    pts = sweep_reflux(FailingSimulator(fail_at=[1.1]), methanol_feed(),
                       ColumnSpec("Methanol", "Water", 0.99, 0.99, 101325.0),
                       k_values=[1.1, 1.3, 2.0])
    assert best_point(pts).converged
    assert best_point(pts).k != 1.1


def test_best_point_refuses_when_nothing_converged():
    pts = sweep_reflux(FailingSimulator(fail_at=[1.1, 1.3]), methanol_feed(),
                       ColumnSpec("Methanol", "Water", 0.99, 0.99, 101325.0),
                       k_values=[1.1, 1.3])
    with pytest.raises(ValueError, match="no converged"):
        best_point(pts)


# --------------------------------------------------------------------------
# the real trade-off, against BioSTEAM
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def real_sweep():
    return sweep_reflux(BioSteamSimulator(), methanol_feed(),
                        ColumnSpec("Methanol", "Water", 0.99, 0.99, 101325.0),
                        k_values=DEFAULT_K_VALUES)


def test_sweep_returns_a_curve_not_a_point(real_sweep):
    assert len(real_sweep) == len(DEFAULT_K_VALUES)
    assert all(p.converged for p in real_sweep), "expected every default k to design"
    # more reflux buys fewer stages -- the classic trade-off
    assert real_sweep[0].stages > real_sweep[-1].stages


def test_the_cost_curve_has_an_interior_minimum(real_sweep):
    """The knee is the reason to sweep at all.

    If the cheapest design sat at an endpoint the sweep would just be an
    arbitrary choice of range. Measured: cost falls 541k -> 448.7k to k = 1.20,
    then climbs to 678k. The optimum must be strictly inside the range.
    """
    best = best_point(real_sweep)
    assert best.k not in (real_sweep[0].k, real_sweep[-1].k)
    assert best.annualised_cost_USD_yr < real_sweep[0].annualised_cost_USD_yr
    assert best.annualised_cost_USD_yr < real_sweep[-1].annualised_cost_USD_yr


def test_best_point_is_the_cheapest_annualised():
    pts = [
        SweepPoint(k=1.1, stages=80, annualised_cost_USD_yr=500_000,
                   installed_cost_USD=2_000_000, utility_cost_USD_hr=10.0),
        SweepPoint(k=1.3, stages=40, annualised_cost_USD_yr=300_000,
                   installed_cost_USD=1_000_000, utility_cost_USD_hr=15.0),
        SweepPoint(k=2.0, stages=25, annualised_cost_USD_yr=400_000,
                   installed_cost_USD=600_000, utility_cost_USD_hr=30.0),
    ]
    assert best_point(pts).k == 1.3


# --------------------------------------------------------------------------
# purity targets -> recoveries
# --------------------------------------------------------------------------

def test_recoveries_for_purity_hits_the_stated_specification():
    """The milestone's spec is written in TOTAL-stream mole fractions, but
    ColumnSpec is written in recoveries -- deliberately, because recovery
    survives a change of simulator and mole fraction does not. Something has to
    convert between them, and it must be this function rather than a loose
    tolerance on the acceptance test.

    Measured: for methanol/water/glycerol at 100/80/25 the answer is
    Lr = 0.989495, Hr = 0.987506, which delivers 0.99000 and 0.01000 exactly.
    Passing 0.99/0.99 as recoveries instead -- what the plan did -- gives
    0.99198 and 0.00951, a different specification that merely looks similar.
    """
    lr, hr = recoveries_for_purity(
        Feed(components=(Component("Methanol", "67-56-1", 100.0),
                         Component("Water", "7732-18-5", 80.0),
                         Component("Glycerol", "56-81-5", 25.0)),
             T_K=330.0, P_Pa=101325.0),
        light_key="Methanol", heavy_key="Water",
        distillate_purity=0.99, bottoms_impurity=0.01,
    )
    assert lr == pytest.approx(0.989495, abs=1e-5)
    assert hr == pytest.approx(0.987506, abs=1e-5)


def test_the_solved_recoveries_beat_the_naive_ones_where_it_counts():
    """The recoveries differ from a naive 0.99 by only 0.0005, which is why
    asserting on them proves little. The difference that matters is downstream:
    run both through the simulator and compare the PURITY actually delivered.
    """
    feed = Feed(components=(Component("Methanol", "67-56-1", 100.0),
                            Component("Water", "7732-18-5", 80.0),
                            Component("Glycerol", "56-81-5", 25.0)),
                T_K=330.0, P_Pa=101325.0)
    sim = BioSteamSimulator()

    def distillate_purity(lr, hr):
        r = sim.design_column(feed, ColumnSpec("Methanol", "Water", lr, hr,
                                               101325.0, 1.2))
        assert r.converged, r.error
        return r.distillate["Methanol"] / sum(r.distillate.values())

    lr, hr = recoveries_for_purity(feed, "Methanol", "Water", 0.99, 0.01)
    assert distillate_purity(lr, hr) == pytest.approx(0.99, abs=1e-5)
    # the naive substitution misses the stated target by ~0.002
    assert distillate_purity(0.99, 0.99) != pytest.approx(0.99, abs=1e-3)


def test_recoveries_for_purity_reports_an_impossible_target_as_data():
    """A purity that no split can reach must be refused, not silently clipped
    into a recovery outside [0, 1] that the simulator would then reject with a
    confusing error."""
    feed = Feed(components=(Component("Methanol", "67-56-1", 1.0),
                            Component("Water", "7732-18-5", 99.0)),
                T_K=330.0, P_Pa=101325.0)
    with pytest.raises(ValueError, match="cannot"):
        recoveries_for_purity(feed, "Methanol", "Water",
                              distillate_purity=0.999999,
                              bottoms_impurity=0.999999)
