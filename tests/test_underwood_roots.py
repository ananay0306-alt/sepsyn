"""Underwood's constant, solved from the equation rather than borrowed.

    sum_i [ alpha_i z_i / (alpha_i - theta) ] = 1 - q

theta lies strictly between the volatilities of the two keys. Volatilities here
are relative to the heavy key, so alpha_HK = 1 by construction and the root is
bracketed by (1, alpha_LK).
"""
import pytest

from sepsyn.vmin.underwood import NoUnderwoodRoot, underwood_theta


def residual(alpha, z, q, theta):
    return sum(alpha[i] * z[i] / (alpha[i] - theta) for i in z) - (1.0 - q)


def test_the_root_satisfies_the_equation():
    alpha = {"A": 4.0, "B": 2.0, "C": 1.0}
    z = {"A": 0.3, "B": 0.3, "C": 0.4}
    theta = underwood_theta(alpha, z, q=1.0, light_key="B", heavy_key="C")
    assert residual(alpha, z, 1.0, theta) == pytest.approx(0.0, abs=1e-9)


def test_the_root_is_bracketed_by_the_KEY_volatilities():
    """The defining property. A root outside the keys' volatilities is a
    different root and gives a different, wrong, minimum vapour."""
    alpha = {"A": 4.0, "B": 2.0, "C": 1.0}
    z = {"A": 0.3, "B": 0.3, "C": 0.4}
    theta = underwood_theta(alpha, z, q=1.0, light_key="B", heavy_key="C")
    assert 1.0 < theta < 2.0


def test_a_different_key_pair_gives_a_different_root():
    """Splitting A from B is a different separation from splitting B from C,
    and must select a root in a different interval."""
    alpha = {"A": 4.0, "B": 2.0, "C": 1.0}
    z = {"A": 0.3, "B": 0.3, "C": 0.4}
    ab = underwood_theta(alpha, z, q=1.0, light_key="A", heavy_key="B")
    bc = underwood_theta(alpha, z, q=1.0, light_key="B", heavy_key="C")
    assert 2.0 < ab < 4.0
    assert 1.0 < bc < 2.0
    assert ab != bc


def test_a_binary_feed_has_an_analytic_root():
    """With two components at q=1 the equation reduces to a quadratic and the
    root can be checked by hand."""
    alpha = {"A": 3.0, "B": 1.0}
    z = {"A": 0.5, "B": 0.5}
    theta = underwood_theta(alpha, z, q=1.0, light_key="A", heavy_key="B")
    assert residual(alpha, z, 1.0, theta) == pytest.approx(0.0, abs=1e-9)
    assert 1.0 < theta < 3.0


@pytest.mark.parametrize("q", [0.0, 0.5, 1.0, 1.3])
def test_feed_condition_moves_the_root(q):
    """q enters the equation directly. A saturated vapour feed and a subcooled
    liquid feed give different roots and therefore different minimum vapour,
    which is why q travels with every design in this project."""
    alpha = {"A": 4.0, "B": 2.0, "C": 1.0}
    z = {"A": 0.3, "B": 0.3, "C": 0.4}
    theta = underwood_theta(alpha, z, q=q, light_key="B", heavy_key="C")
    assert residual(alpha, z, q, theta) == pytest.approx(0.0, abs=1e-9)


def test_components_absent_from_the_group_are_refused():
    alpha = {"A": 4.0, "B": 2.0}
    z = {"A": 0.5, "B": 0.5}
    with pytest.raises(NoUnderwoodRoot, match="C"):
        underwood_theta(alpha, z, q=1.0, light_key="B", heavy_key="C")


def test_keys_with_equal_volatility_are_refused_rather_than_returning_a_root():
    """No interval, no root. Alpha of 1.0 between the keys means they cannot be
    separated by distillation at all, and R-02 should already have said so."""
    alpha = {"A": 2.0, "B": 1.0, "C": 1.0}
    z = {"A": 0.4, "B": 0.3, "C": 0.3}
    with pytest.raises(NoUnderwoodRoot, match="volatilit"):
        underwood_theta(alpha, z, q=1.0, light_key="B", heavy_key="C")
