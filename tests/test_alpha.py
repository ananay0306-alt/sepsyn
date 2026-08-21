import pytest
from sepsyn.types import Component, Feed
from sepsyn.properties import relative_volatilities, build_property_record


def methanol_water_glycerol():
    return Feed(
        components=(
            Component("Methanol", "67-56-1", 100.0),
            Component("Water", "7732-18-5", 80.0),
            Component("Glycerol", "56-81-5", 25.0),
        ),
        T_K=330.0, P_Pa=101325.0,
    )


def h2_methane():
    return Feed(
        components=(
            Component("Hydrogen", "1333-74-0", 50.0),
            Component("Methane", "74-82-8", 50.0),
        ),
        T_K=298.15, P_Pa=101325.0,
    )


def test_alpha_is_computed_with_conditions_attached():
    alphas = relative_volatilities(methanol_water_glycerol(), P_Pa=101325.0)
    assert len(alphas) >= 1
    a = alphas[0]
    assert a.value > 1.0
    assert a.T_K > 273.0
    assert a.P_Pa == 101325.0
    assert "bubble point" in a.basis


def test_methanol_water_alpha_is_around_two():
    alphas = relative_volatilities(methanol_water_glycerol(), P_Pa=101325.0)
    pair = [a for a in alphas if set(a.pair) == {"Methanol", "Water"}]
    assert len(pair) == 1
    assert 1.5 < pair[0].value < 4.0


def test_record_for_supercritical_feed_has_no_alpha():
    rec = build_property_record(h2_methane())
    assert rec.n_supercritical_at_feed == 2
    assert rec.n_components == 2
    assert rec.min_alpha is None
    assert rec.feed_phase == "vapor"


def test_record_for_condensable_feed_has_alpha():
    rec = build_property_record(methanol_water_glycerol())
    assert rec.n_supercritical_at_feed == 0
    assert rec.min_alpha is not None
    assert rec.min_alpha > 1.0


def test_condensing_temperature_is_populated_so_R09_can_fire():
    """Regression: this field was once hardcoded to None, which made the
    refrigeration caution dead code that only fired in unit tests."""
    rec = build_property_record(methanol_water_glycerol())
    assert rec.condensing_T_at_column_P is not None
    # methanol condenses at ~338 K at 1 atm, above cooling water at 313 K
    assert rec.condensing_T_at_column_P > rec.cooling_water_T


def test_light_hydrocarbon_feed_triggers_the_refrigeration_caution():
    """Ethylene condenses at ~169 K at 1 atm, far below cooling water."""
    feed = Feed(
        components=(Component("Ethylene", "74-85-1", 50.0),
                    Component("Ethane", "74-84-0", 50.0)),
        T_K=250.0, P_Pa=101325.0,
    )
    rec = build_property_record(feed)
    assert rec.condensing_T_at_column_P is not None
    assert rec.condensing_T_at_column_P < rec.cooling_water_T


def test_relative_volatilities_returns_data_for_a_condensable_mixture():
    """Guards the defect this task exists to prevent: an earlier version read
    vapour composition at V=0, where the vapour phase holds zero moles, so this
    returned () for every mixture and min_alpha was permanently None -- which
    silently disables R-01 and R-02."""
    alphas = relative_volatilities(methanol_water_glycerol(), P_Pa=101325.0)
    assert len(alphas) > 0
    meoh_water = [a for a in alphas if set(a.pair) == {"Methanol", "Water"}]
    assert len(meoh_water) == 1
    assert meoh_water[0].value > 1.0
    assert meoh_water[0].basis == "bubble point at column P"


def test_supercritical_feed_reports_azeotrope_as_unknown_not_false():
    """False would claim the search ran and found nothing. It never ran."""
    rec = build_property_record(h2_methane())
    assert rec.has_azeotrope is None
    assert rec.min_alpha is None
    assert rec.feed_phase == "vapor"
