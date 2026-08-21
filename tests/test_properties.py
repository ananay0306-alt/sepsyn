import pytest
from sepsyn.properties import (
    UnknownChemical, resolve, boiling_point,
    critical_temperature, critical_pressure,
)

# literature values; tolerances are loose enough to survive a database update
KNOWN = [
    ("Hydrogen", 20.37, 33.15),
    ("Methane", 111.67, 190.56),
    ("Methanol", 337.63, 513.38),
    ("Water", 373.12, 647.10),
    ("Glycerol", 562.15, 850.00),
    ("Ethanol", 351.57, 514.71),
]


@pytest.mark.parametrize("name,tb,tc", KNOWN)
def test_boiling_and_critical_temperatures(name, tb, tc):
    cas = resolve(name)
    assert boiling_point(cas) == pytest.approx(tb, abs=0.5)
    assert critical_temperature(cas) == pytest.approx(tc, abs=0.5)


def test_critical_pressure_is_positive():
    assert critical_pressure(resolve("Methane")) > 1e6


def test_unknown_chemical_names_near_matches():
    with pytest.raises(UnknownChemical) as exc:
        resolve("Methanool")
    error_msg = str(exc.value)
    assert "Methanool" in error_msg
    assert "methanol" in error_msg.lower()
