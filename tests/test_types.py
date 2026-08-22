import pytest
from sepsyn.types import Component, Feed


def test_feed_totals_and_mole_fractions():
    feed = Feed(
        components=(
            Component("Methanol", "67-56-1", 100.0),
            Component("Water", "7732-18-5", 80.0),
            Component("Glycerol", "56-81-5", 20.0),
        ),
        T_K=330.0,
        P_Pa=101325.0,
    )
    assert feed.total_kmol_hr == 200.0
    assert feed.mole_fractions["Methanol"] == pytest.approx(0.5)
    assert feed.mole_fractions["Water"] == pytest.approx(0.4)
    assert feed.mole_fractions["Glycerol"] == pytest.approx(0.1)


def test_feed_rejects_zero_total_flow():
    with pytest.raises(ValueError, match="total flow must be positive"):
        Feed(components=(Component("Water", "7732-18-5", 0.0),),
             T_K=298.15, P_Pa=101325.0)
