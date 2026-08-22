"""Verification is the last line of defence, so its tolerances are the product.

Two numbers set them, both measured rather than chosen:
  * BioSTEAM hits a requested recovery to 1.1e-16 across 16 spec/reflux
    combinations, so real solver noise is effectively zero.
  * Reading a recovery as a keys-only mole fraction -- the error the whole
    recovery spec exists to prevent -- shifts it by 0.002 (Task 9).
Anything between those two scales works. The plan proposed 0.03, which is 15x
too loose to see the defect and 3e14 times larger than any real error.
"""
import dataclasses

import pytest

from sepsyn.simulators.base import ColumnResult, ColumnSpec
from sepsyn.types import Component, Feed
from sepsyn.verify import Check, verify_column


def feed():
    return Feed(
        components=(Component("Methanol", "67-56-1", 100.0),
                    Component("Water", "7732-18-5", 80.0)),
        T_K=330.0, P_Pa=101325.0,
    )


def spec():
    return ColumnSpec("Methanol", "Water", 0.99, 0.99, 101325.0)


def good_result():
    return ColumnResult(
        distillate={"Methanol": 99.0, "Water": 0.8},
        bottoms={"Methanol": 1.0, "Water": 79.2},
        stages=40, reflux=1.3, minimum_reflux=1.0,
        installed_cost_USD=500_000, utility_cost_USD_hr=20.0,
        converged=True, error=None,
    )


def names(checks):
    return {c.name: c.passed for c in checks}


def detail(checks, name):
    return next(c.detail for c in checks if c.name == name)


# --------------------------------------------------------------------------
# the plan's checks
# --------------------------------------------------------------------------

def test_good_result_passes_every_check():
    assert all(c.passed for c in verify_column(feed(), spec(), good_result()))


def test_mass_balance_failure_is_caught():
    bad = dataclasses.replace(good_result(),
                              bottoms={"Methanol": 1.0, "Water": 40.0})
    assert names(verify_column(feed(), spec(), bad))["mass balance"] is False


def test_missed_recovery_is_caught():
    bad = dataclasses.replace(good_result(),
                              distillate={"Methanol": 60.0, "Water": 0.8},
                              bottoms={"Methanol": 40.0, "Water": 79.2})
    assert names(verify_column(feed(), spec(), bad))["light key recovery"] is False


def test_non_converged_result_fails_immediately():
    bad = ColumnResult({}, {}, 0, 0, 0, 0, 0, False, "RuntimeError: stages > 100")
    checks = verify_column(feed(), spec(), bad)
    assert names(checks)["converged"] is False
    assert "stages > 100" in detail(checks, "converged")


def test_reflux_below_minimum_is_caught():
    bad = dataclasses.replace(good_result(), reflux=0.9, minimum_reflux=1.0)
    assert names(verify_column(feed(), spec(), bad))["reflux above minimum"] is False


# --------------------------------------------------------------------------
# the checks the plan's tolerances and aggregation would have let through
# --------------------------------------------------------------------------

def test_the_wrong_recovery_basis_is_caught():
    """The defect this project's most important interface decision guards
    against must not survive verification.

    Reading the 0.99 recovery as a keys-only mole fraction puts 99.202 kmol/hr
    of methanol overhead instead of 99.000 -- measured in Task 9, both ways.
    The design balances perfectly and looks entirely reasonable; only the
    recovery tolerance stands between it and a passing report. At the plan's
    0.03 this passed.
    """
    wrong_basis = dataclasses.replace(
        good_result(),
        distillate={"Methanol": 99.202, "Water": 1.002},
        bottoms={"Methanol": 0.798, "Water": 78.998},
    )
    checks = verify_column(feed(), spec(), wrong_basis)

    assert names(checks)["mass balance"] is True, "the deception is that it balances"
    assert names(checks)["light key recovery"] is False
    assert "0.992" in detail(checks, "light key recovery")


def test_mass_balance_is_checked_per_component_not_in_aggregate():
    """A total that closes is not a balance.

    Here glycerol is destroyed and ethanol created. The two errors partially
    cancel, so the TOTAL is off by only 0.23% and an aggregate check passes
    while matter is transmuted. Both key recoveries are exactly as asked, so
    nothing else catches it either.
    """
    four = Feed(components=(Component("Methanol", "67-56-1", 100.0),
                            Component("Water", "7732-18-5", 80.0),
                            Component("Glycerol", "56-81-5", 25.0),
                            Component("Ethanol", "64-17-5", 10.0)),
                T_K=330.0, P_Pa=101325.0)
    transmuted = ColumnResult(
        distillate={"Methanol": 99.0, "Water": 0.8, "Glycerol": 0.5, "Ethanol": 0.3},
        bottoms={"Methanol": 1.0, "Water": 79.2, "Glycerol": 24.0, "Ethanol": 10.7},
        stages=40, reflux=1.3, minimum_reflux=1.0,
        installed_cost_USD=500_000, utility_cost_USD_hr=20.0, converged=True,
    )
    checks = verify_column(four, spec(), transmuted)

    assert names(checks)["light key recovery"] is True   # the keys are perfect
    assert names(checks)["heavy key recovery"] is True
    assert names(checks)["mass balance"] is False
    # and it must say WHICH component, or the check is unactionable
    assert "Glycerol" in detail(checks, "mass balance") or \
           "Ethanol" in detail(checks, "mass balance")


def test_a_component_missing_from_the_products_is_caught():
    """Silently dropping a component would otherwise read as a clean balance
    for everything that remains."""
    three = Feed(components=(Component("Methanol", "67-56-1", 100.0),
                             Component("Water", "7732-18-5", 80.0),
                             Component("Glycerol", "56-81-5", 25.0)),
                 T_K=330.0, P_Pa=101325.0)
    dropped = ColumnResult(
        distillate={"Methanol": 99.0, "Water": 0.8},
        bottoms={"Methanol": 1.0, "Water": 79.2},   # no glycerol anywhere
        stages=40, reflux=1.3, minimum_reflux=1.0,
        installed_cost_USD=500_000, utility_cost_USD_hr=20.0, converged=True,
    )
    checks = verify_column(three, spec(), dropped)
    assert names(checks)["mass balance"] is False
    assert "Glycerol" in detail(checks, "mass balance")


def test_every_check_explains_itself_with_numbers():
    """A check that passes silently teaches the reader nothing; the detail is
    what lets someone disagree with the verdict."""
    for c in verify_column(feed(), spec(), good_result()):
        assert isinstance(c, Check)
        assert c.detail.strip(), f"{c.name} has no detail"
        assert any(ch.isdigit() for ch in c.detail), (
            f"{c.name} detail cites no number: {c.detail!r}"
        )


def test_a_small_but_real_imbalance_is_not_tolerated():
    """Pins MASS_BALANCE_TOL itself, which nothing above does.

    Every other imbalance in this file is larger than 1%, so the plan's 0.01
    would have caught those too and the tolerance was doing no work. BioSTEAM
    closes a component balance to better than 1e-6 relative (tests/
    test_simulator.py), so a 0.3% gap is roughly three thousand times worse
    than anything the solver actually produces -- it means something is wrong,
    not that the arithmetic is tired.

    Glycerol is perturbed rather than a key, so ONLY the balance check reacts
    and the failure is unambiguous about what it caught.
    """
    three = Feed(components=(Component("Methanol", "67-56-1", 100.0),
                             Component("Water", "7732-18-5", 80.0),
                             Component("Glycerol", "56-81-5", 25.0)),
                 T_K=330.0, P_Pa=101325.0)
    slightly_off = ColumnResult(
        distillate={"Methanol": 99.0, "Water": 0.8, "Glycerol": 0.0},
        bottoms={"Methanol": 1.0, "Water": 79.2, "Glycerol": 24.925},  # 0.3% lost
        stages=40, reflux=1.3, minimum_reflux=1.0,
        installed_cost_USD=500_000, utility_cost_USD_hr=20.0, converged=True,
    )
    checks = verify_column(three, spec(), slightly_off)

    assert names(checks)["light key recovery"] is True
    assert names(checks)["heavy key recovery"] is True
    assert names(checks)["mass balance"] is False, (
        "a 0.3% component gap must not be waved through"
    )
    assert "Glycerol" in detail(checks, "mass balance")
