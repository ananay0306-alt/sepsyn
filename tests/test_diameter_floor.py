"""BioSTEAM's diameter floor, and what it does to rule E-24b.

A CHARACTERISATION test: it pins third-party behaviour that sepsyn's rules
depend on, rather than driving sepsyn code. Its job is to fail loudly the day
BioSTEAM changes, because on that day a rule that is currently unreachable
becomes live and nobody would otherwise notice.
"""
from sepsyn.equipment import DesignContext, choose_equipment
from sepsyn.simulators.base import ColumnSpec
from sepsyn.simulators.biosteam_adapter import BioSteamSimulator
from sepsyn.types import Component, Feed

ATM = 101325.0
BIOSTEAM_DIAMETER_FLOOR_M = 3.0 * 0.3048  # 0.9144 m; distillation.py _bounds


def tiny_column():
    """A hundredth of a kmol/hr. Nothing physical needs a 3 ft column here."""
    return Feed(components=(Component("Benzene", "71-43-2", 0.006),
                            Component("Toluene", "108-88-3", 0.004)),
                T_K=298.15, P_Pa=ATM)


def test_biosteam_never_reports_a_diameter_below_three_feet():
    """Measured across a 500,000-fold range of feed rates: 0.01 and 1 kmol/hr
    both give exactly 3.00 ft, 100 gives 3.78, 5000 gives 26.70. The lower
    bound is a hard clamp; the upper one is not (26.70 exceeds the stated 24)."""
    sim = BioSteamSimulator()
    r = sim.design_column(tiny_column(),
                          ColumnSpec("Benzene", "Toluene", 0.99, 0.99, ATM))
    assert r.converged, r.error
    assert r.column_diameter_m >= BIOSTEAM_DIAMETER_FLOOR_M - 1e-3


def test_E24b_is_therefore_UNREACHABLE_through_the_biosteam_adapter():
    """The consequence, stated as an assertion so it cannot rot silently.

    E-24b chooses packing below 0.6 m, which is correct physics -- a tray
    cannot be installed or maintained through a manway at that size. But
    BioSTEAM floors the diameter at 0.914 m, so no column it designs can ever
    reach the branch.

    The threshold is deliberately NOT tuned up to meet the floor: that would
    replace a physical criterion with an artefact of one simulator, and the
    rule must still be correct when a DWSIM adapter or a hand-built context
    supplies a real small diameter. If this test ever fails, BioSTEAM has
    lowered its bound and the rule has come alive -- which is good news, and
    worth knowing.
    """
    sim = BioSteamSimulator()
    r = sim.design_column(tiny_column(),
                          ColumnSpec("Benzene", "Toluene", 0.99, 0.99, ATM))
    decision = next(d for d in choose_equipment(DesignContext(
        pressure_Pa=ATM, n_supercritical_at_feed=0,
        column_diameter_m=r.column_diameter_m)) if d.step == 24)
    assert decision.choice == "trays"
    assert decision.rule_id != "E-24b"


def test_E24b_still_fires_on_a_genuinely_narrow_column():
    """The rule itself is not broken -- only unreachable through one adapter."""
    decision = next(d for d in choose_equipment(DesignContext(
        pressure_Pa=ATM, n_supercritical_at_feed=0,
        column_diameter_m=0.4)) if d.step == 24)
    assert decision.choice == "packing"
    assert decision.rule_id == "E-24b"
