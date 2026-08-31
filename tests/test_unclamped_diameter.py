"""The true hydraulic diameter, recovered from under BioSTEAM's floor.

compute_tower_diameter() ends with:

    Di = sqrt(4*V_vol / (f*U_f*pi*(1 - A_dn)))
    if Di < 0.914:
        Di = 0.914    # "Make sure diameter is not too small"

That floor is a TRAY costing assumption -- you do not build a tray column at
0.3 m -- and it silently destroyed rule E-24b, which chooses packing below
0.6 m for exactly the reason BioSTEAM refuses to go there. The number the rule
needs is the one discarded on the line above.
"""
import pytest

from sepsyn.equipment import DesignContext, choose_equipment
from sepsyn.simulators.base import ColumnSpec
from sepsyn.simulators.biosteam_adapter import BioSteamSimulator
from sepsyn.types import Component, Feed

ATM = 101325.0
FLOOR_M = 0.914


def benzene_toluene(total_kmol_hr):
    return Feed(components=(Component("Benzene", "71-43-2", 0.6 * total_kmol_hr),
                            Component("Toluene", "108-88-3", 0.4 * total_kmol_hr)),
                T_K=298.15, P_Pa=ATM)


def design(total_kmol_hr):
    return BioSteamSimulator().design_column(
        benzene_toluene(total_kmol_hr),
        ColumnSpec("Benzene", "Toluene", 0.99, 0.99, ATM))


@pytest.fixture(scope="module")
def wide():
    return design(100.0)


@pytest.fixture(scope="module")
def narrow():
    return design(10.0)


def test_above_the_floor_the_recompute_AGREES_with_biosteam(wide):
    """THE correctness proof, and the reason both sections had to be done.

    Where no clamp applies, the recomputed diameter must equal the one BioSTEAM
    reports. Computing only the RECTIFYING section passes every small-column
    test and still fails here: at this feed the stripping section governs
    (1.151 m against the rectifying section's 1.086 m), so a rectifying-only
    version would under-report by 6% and call for packing on columns that want
    trays.
    """
    assert wide.converged, wide.error
    assert wide.column_diameter_m > FLOOR_M, "this column must not be clamped"
    assert wide.column_diameter_m == pytest.approx(
        wide.biosteam_reported_diameter_m, rel=1e-6)


def test_below_the_floor_the_recompute_GOES_BELOW_it(narrow):
    """A 10 kmol/hr benzene/toluene column is about 0.34 m. BioSTEAM reports
    0.914 m for it, and for a column ten thousand times smaller."""
    assert narrow.converged, narrow.error
    assert narrow.column_diameter_m < 0.6
    assert narrow.biosteam_reported_diameter_m == pytest.approx(FLOOR_M, abs=1e-3)


def test_the_floored_value_is_still_reported_separately(narrow):
    """BioSTEAM costs the clamped column, so the clamped number is what the
    cost belongs to. Both travel, and neither is silently substituted for the
    other."""
    assert narrow.biosteam_reported_diameter_m > narrow.column_diameter_m


def test_E24b_now_FIRES_through_the_adapter(narrow):
    """The point of the whole exercise. Before this, no column BioSTEAM
    designed could reach the branch."""
    decision = next(d for d in choose_equipment(DesignContext(
        pressure_Pa=ATM, n_supercritical_at_feed=0,
        column_diameter_m=narrow.column_diameter_m)) if d.step == 24)
    assert decision.choice == "packing"
    assert decision.rule_id == "E-24b"
    assert decision.status == "decided"


def test_a_wide_column_still_gets_trays(wide):
    decision = next(d for d in choose_equipment(DesignContext(
        pressure_Pa=ATM, n_supercritical_at_feed=0,
        column_diameter_m=wide.column_diameter_m)) if d.step == 24)
    assert decision.choice == "trays"


def test_the_recompute_falls_back_rather_than_crashing(monkeypatch):
    """It reads five private BioSTEAM attributes. When a version bump moves
    them the adapter must degrade to the clamped value, not raise -- a design
    is worth more than a diameter."""
    import sepsyn.simulators.biosteam_adapter as adapter

    monkeypatch.setattr(adapter, "_hydraulic_diameter_m",
                        lambda col: (_ for _ in ()).throw(AttributeError("_f")))
    r = design(10.0)
    assert r.converged, r.error
    assert r.column_diameter_m == pytest.approx(FLOOR_M, abs=1e-3)
