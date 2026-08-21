import pytest
from sepsyn.types import Component, Feed, Alpha, PropertyRecord
from sepsyn.properties import count_supercritical


def h2_methane_feed():
    return Feed(
        components=(
            Component("Hydrogen", "1333-74-0", 50.0),
            Component("Methane", "74-82-8", 50.0),
        ),
        T_K=298.15, P_Pa=101325.0,
    )


def methanol_feed():
    return Feed(
        components=(
            Component("Methanol", "67-56-1", 100.0),
            Component("Water", "7732-18-5", 80.0),
        ),
        T_K=330.0, P_Pa=101325.0,
    )


def test_both_components_supercritical_at_ambient():
    # Hydrogen Tc = 33 K, Methane Tc = 191 K, feed at 298 K
    assert count_supercritical(h2_methane_feed()) == 2


def test_nothing_supercritical_for_methanol_water():
    assert count_supercritical(methanol_feed()) == 0


def test_alpha_carries_its_conditions():
    a = Alpha(pair=("Methanol", "Water"), value=2.11,
              T_K=351.2, P_Pa=101325.0, basis="bubble point at column P")
    assert a.value == 2.11
    assert a.T_K == 351.2
    assert a.basis == "bubble point at column P"


def test_namespace_exposes_only_rule_visible_fields():
    rec = PropertyRecord(
        n_components=2, n_supercritical_at_feed=2, min_alpha=None,
        has_azeotrope=False, alphas=(), feed_phase="vapor",
        condensing_T_at_column_P=None, cooling_water_T=313.15,
        light_key_mole_fraction=None, heavy_key_mole_fraction=None,
    )
    ns = rec.as_namespace()
    assert ns["n_supercritical_at_feed"] == 2
    assert ns["n_components"] == 2
    # the raw alpha objects must not leak into rule evaluation
    assert "alphas" not in ns
