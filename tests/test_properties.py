import pytest
import re
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


def _first_suggestion(message: str) -> str | None:
    """Extract the first name from a "Did you mean: 'a', 'b', ...?" message."""
    m = re.search(r"Did you mean: '([^']+)'", message)
    return m.group(1) if m else None


@pytest.mark.parametrize("misspelling,expected", [
    ("Methanool", "methanol"),
    ("Glycerool", "glycerol"),
])
def test_unknown_chemical_suggests_the_right_name_first(misspelling, expected):
    """The correct match must rank FIRST, not merely appear somewhere.

    Asserting mere presence is not enough: without case normalisation
    'Methanool' still yields 'methanol' in fourth place, so a presence check
    passes against the very bug it is meant to catch.
    """
    with pytest.raises(UnknownChemical) as exc:
        resolve(misspelling)
    message = str(exc.value)
    assert misspelling in message
    assert "Did you mean" in message
    assert _first_suggestion(message) == expected


def test_unknown_chemical_with_no_close_match_says_so():
    with pytest.raises(UnknownChemical) as exc:
        resolve("Zzzqqqxyw")
    assert "Zzzqqqxyw" in str(exc.value)
