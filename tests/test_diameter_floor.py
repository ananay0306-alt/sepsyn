"""BioSTEAM's diameter floor, and the fact that sepsyn now sees through it.

A CHARACTERISATION test of third-party behaviour sepsyn's rules depend on. Its
job is to fail loudly if BioSTEAM changes, because the recompute in the adapter
is written against this exact behaviour.
"""
import pytest

from sepsyn.equipment import DesignContext, choose_equipment
from sepsyn.simulators.base import ColumnSpec
from sepsyn.simulators.biosteam_adapter import BioSteamSimulator
from sepsyn.types import Component, Feed

ATM = 101325.0
BIOSTEAM_DIAMETER_FLOOR_M = 0.914  # hardcoded in compute_tower_diameter


def tiny_column():
    """A hundredth of a kmol/hr. Nothing here needs a 3 ft column."""
    return Feed(components=(Component("Benzene", "71-43-2", 0.006),
                            Component("Toluene", "108-88-3", 0.004)),
                T_K=298.15, P_Pa=ATM)


@pytest.fixture(scope="module")
def result():
    return BioSteamSimulator().design_column(
        tiny_column(), ColumnSpec("Benzene", "Toluene", 0.99, 0.99, ATM))


def test_biosteam_still_floors_the_diameter_it_designs_with(result):
    """Unchanged and still true: compute_tower_diameter ends with
    `if Di < 0.914: Di = 0.914`. The shell, wall thickness and cost all follow
    from the floored value, so it is the number the COST belongs to."""
    assert result.converged, result.error
    assert result.biosteam_reported_diameter_m == pytest.approx(
        BIOSTEAM_DIAMETER_FLOOR_M, abs=1e-3)


def test_sepsyn_recovers_the_diameter_underneath_it(result):
    """0.01 kmol/hr of benzene/toluene is a centimetre-scale column, and the
    rules are entitled to know that even though BioSTEAM will not cost one."""
    assert result.column_diameter_m < 0.1
    assert result.column_diameter_m < result.biosteam_reported_diameter_m


def test_E24b_now_fires_where_it_previously_could_not(result):
    """This assertion is the inverse of the one it replaces.

    E-24b chooses packing below 0.6 m -- correct physics, a tray cannot be
    installed or maintained through a manway at that size. While the adapter
    reported BioSTEAM's floored 0.914 m, no column it designed could reach the
    branch and the rule was dead. It is now reachable.
    """
    decision = next(d for d in choose_equipment(DesignContext(
        pressure_Pa=ATM, n_supercritical_at_feed=0,
        column_diameter_m=result.column_diameter_m)) if d.step == 24)
    assert decision.choice == "packing"
    assert decision.rule_id == "E-24b"


def test_the_threshold_was_never_tuned_to_the_floor():
    """0.6 m is a physical criterion about manway access. Had it been raised to
    meet BioSTEAM's 0.914 m artefact, this column -- comfortably a tray column
    at 0.8 m -- would wrongly be given packing."""
    decision = next(d for d in choose_equipment(DesignContext(
        pressure_Pa=ATM, n_supercritical_at_feed=0,
        column_diameter_m=0.8)) if d.step == 24)
    assert decision.choice == "trays"
