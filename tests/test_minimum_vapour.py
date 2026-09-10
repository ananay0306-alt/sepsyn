"""Minimum vapour for one sharp split.

    V_min = sum over the light group of [ alpha_i F_i / (alpha_i - theta) ]

A BOUND, not a design. No stage count, no efficiency, no condenser type and no
cost enters it, which is the point: every defect measured on 09-09 and 09-10
lives downstream of Underwood.
"""
import pytest

from sepsyn.vmin.underwood import NoUnderwoodRoot
from sepsyn.vmin.vapour import minimum_vapour

ORDER = ("A", "B", "C")
ALPHA = {"A": 4.0, "B": 2.0, "C": 1.0}
FLOWS = {"A": 30.0, "B": 30.0, "C": 40.0}


def test_it_returns_a_positive_vapour_requirement():
    v = minimum_vapour(ORDER, ALPHA, FLOWS, q=1.0, k=1)
    assert v.V_min_kmol_hr > 0


def test_the_vapour_exceeds_the_distillate_it_must_produce():
    """V_min = D(R_min + 1) with R_min >= 0, so the minimum vapour can never be
    less than the distillate flow. A result below it is proof of a wrong
    root."""
    v = minimum_vapour(ORDER, ALPHA, FLOWS, q=1.0, k=1)
    assert v.V_min_kmol_hr > FLOWS["A"]


def test_the_split_point_selects_the_keys_and_the_root():
    v1 = minimum_vapour(ORDER, ALPHA, FLOWS, q=1.0, k=1)
    v2 = minimum_vapour(ORDER, ALPHA, FLOWS, q=1.0, k=2)
    assert v1.light == ("A",) and v1.heavy == ("B", "C")
    assert v2.light == ("A", "B") and v2.heavy == ("C",)
    assert v1.theta != v2.theta


def test_carrying_MORE_overhead_costs_more_vapour():
    """The B/C split must boil A over the top as well as B. A bound that did
    not rise with the light group would not be measuring the separation."""
    v1 = minimum_vapour(ORDER, ALPHA, FLOWS, q=1.0, k=1)
    v2 = minimum_vapour(ORDER, ALPHA, FLOWS, q=1.0, k=2)
    assert v2.V_min_kmol_hr > v1.V_min_kmol_hr


def test_a_binary_split_reduces_to_the_textbook_minimum_reflux():
    """R_min = V_min / D - 1. For a binary sharp split this is the number in
    every textbook, and it is checkable by hand.

    Underwood for a saturated-liquid binary at alpha 3, equimolar:
        3(0.5)/(3 - t) + 1(0.5)/(1 - t) = 1 - q = 0
        1.5(1 - t) + 0.5(3 - t) = 0  ->  3 - 2t = 0  ->  t = 1.5
        V_min = 3(50)/(3 - 1.5) = 100,  R_min = 100/50 - 1 = 1.0
    """
    v = minimum_vapour(("A", "B"), {"A": 3.0, "B": 1.0},
                       {"A": 50.0, "B": 50.0}, q=1.0, k=1)
    assert v.theta == pytest.approx(1.5, abs=1e-6)
    assert v.V_min_kmol_hr == pytest.approx(100.0, rel=1e-6)
    assert v.V_min_kmol_hr / 50.0 - 1.0 == pytest.approx(1.0, rel=1e-6)


def test_the_alpha_basis_travels_with_the_result():
    """A bare relative volatility is meaningless. Same discipline as
    sepsyn.types.Alpha, and a proxy is not exempt."""
    v = minimum_vapour(ORDER, ALPHA, FLOWS, q=1.0, k=1)
    assert v.alpha_basis


def test_an_out_of_range_split_point_is_refused():
    with pytest.raises(ValueError, match="split point"):
        minimum_vapour(ORDER, ALPHA, FLOWS, q=1.0, k=0)
    with pytest.raises(ValueError, match="split point"):
        minimum_vapour(ORDER, ALPHA, FLOWS, q=1.0, k=3)


def test_an_unseparable_pair_propagates_the_refusal():
    with pytest.raises(NoUnderwoodRoot):
        minimum_vapour(("A", "B"), {"A": 1.0, "B": 1.0},
                       {"A": 50.0, "B": 50.0}, q=1.0, k=1)
