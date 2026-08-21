import pytest
from sepsyn.azeotropes import Azeotrope, find_azeotropes


def test_ethanol_water_azeotrope_is_found():
    """Ethanol/water azeotropes near 89 mol% ethanol at 1 atm.

    Source: Seader & Henley, Separation Process Principles. The literature
    value is 95.6 wt% which is ~89.4 mol%.
    """
    found = find_azeotropes(["Ethanol", "Water"], P_Pa=101325.0)
    assert len(found) == 1
    az = found[0]
    ethanol_x = az.x[az.components.index("Ethanol")]
    assert ethanol_x == pytest.approx(0.894, abs=0.04)
    assert az.T_K == pytest.approx(351.3, abs=2.0)


def test_methanol_water_has_no_azeotrope():
    """Methanol/water is a wide-boiling ideal-ish pair with no azeotrope."""
    assert find_azeotropes(["Methanol", "Water"], P_Pa=101325.0) == []


def test_single_component_has_no_azeotrope():
    assert find_azeotropes(["Water"], P_Pa=101325.0) == []
