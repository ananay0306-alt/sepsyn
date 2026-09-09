"""Are these two columns the same column?

Nothing may report a gap until this says yes. The 09-09 probe measured an 11x
condenser duty gap and it could not be attributed, because three conventions
were unpinned. Naming it as shortcut error would have repeated the 08-27
mistake, where a 58 percent and a 43 percent disagreement both turned out to be
bookkeeping.
"""
import pytest

from sepsyn.simulators.base import ColumnResult, ColumnSpec
from sepsyn.simulators.dwsim_fixtures import DwsimRun
from sepsyn.simulators.equivalence import (
    UNATTRIBUTED, can_report_gap, check_equivalence)

SPEC = ColumnSpec("Benzene", "Toluene", 0.99, 0.99, 101325.0)


def sepsyn_result(**over):
    base = dict(
        distillate={"Benzene": 59.4, "Toluene": 0.4},
        bottoms={"Benzene": 0.6, "Toluene": 39.6},
        stages=28.0, reflux=1.5, minimum_reflux=1.25,
        installed_cost_USD=1e6, utility_cost_USD_hr=10.0, converged=True,
        condenser_duty_kW=1083.4, reboiler_duty_kW=1447.1,
        distillate_T_K=353.4, bottoms_T_K=383.3,
    )
    base.update(over)
    return ColumnResult(**base)


def dwsim_run(**over):
    base = dict(
        feed_mol_s={"Benzene": 16.6667, "Toluene": 11.1111},
        T_K=298.15, P_Pa=101325.0, stages=20, feed_stage=10,
        condenser_spec={"type": "Component Recovery", "compound": "Benzene",
                        "value": 99.0},
        reboiler_spec={"type": "Component Recovery", "compound": "Toluene",
                       "value": 99.0},
        property_package="Peng-Robinson (PR)", solver="NS",
        converged=True, errors=(),
        distillate_mol_s={"Benzene": 16.5, "Toluene": 0.111},
        bottoms_mol_s={"Benzene": 0.1667, "Toluene": 11.0},
        condenser_duty_kW=1090.0, reboiler_duty_kW=1455.0,
        distillate_T_K=353.6, bottoms_T_K=383.5,
    )
    base.update(over)
    return DwsimRun(**base)


def by_name(assertions):
    return {a.name: a for a in assertions}


def test_matching_configuration_passes_every_assertion():
    a = check_equivalence(SPEC, sepsyn_result(), 20, 10, dwsim_run())
    assert all(x.holds for x in a), [x for x in a if not x.holds]
    assert can_report_gap(a) is True


def test_an_ACTUAL_stage_count_reaching_dwsim_is_caught():
    """The trap that produced DCErrorStillHigh in the probe. BioSTEAM reports
    28 actual and 20 theoretical; handing 28 to DWSIM is a different column."""
    a = by_name(check_equivalence(SPEC, sepsyn_result(), 20, 10,
                                  dwsim_run(stages=28)))
    assert a["stage count"].holds is False
    assert "28" in a["stage count"].detail and "20" in a["stage count"].detail


def test_a_feed_stage_mismatch_is_caught():
    """The convention that flipped convergence in the probe: stage 14 solved in
    seconds, stage 6 timed out."""
    a = by_name(check_equivalence(SPEC, sepsyn_result(), 20, 6,
                                  dwsim_run(feed_stage=14)))
    assert a["feed stage"].holds is False


def test_a_pressure_mismatch_is_caught():
    a = by_name(check_equivalence(SPEC, sepsyn_result(), 20, 10,
                                  dwsim_run(P_Pa=5e5)))
    assert a["pressure"].holds is False


def test_a_recovery_spec_mismatch_is_caught():
    a = by_name(check_equivalence(
        SPEC, sepsyn_result(), 20, 10,
        dwsim_run(condenser_spec={"type": "Reflux Ratio", "value": 1.5})))
    assert a["specification basis"].holds is False


def test_the_mass_balance_assertion_catches_a_DOUBLED_feed():
    """Probe finding 4, exactly. A mutated flowsheet produced 55.55 mol/s of
    product from a 27.78 mol/s feed, with plausible compositions and
    temperatures. Only a mass balance caught it."""
    doubled = dwsim_run(
        distillate_mol_s={"Benzene": 33.0, "Toluene": 0.222},
        bottoms_mol_s={"Benzene": 0.333, "Toluene": 22.0})
    a = by_name(check_equivalence(SPEC, sepsyn_result(), 20, 10, doubled))
    assert a["mass balance"].holds is False
    assert "2" in a["mass balance"].detail


def test_a_gap_may_NOT_be_reported_when_an_assertion_fails():
    a = check_equivalence(SPEC, sepsyn_result(), 20, 10, dwsim_run(stages=28))
    assert can_report_gap(a) is False


def test_a_gap_may_NOT_be_reported_when_an_assertion_could_not_be_checked():
    """Unknown is not the same as satisfied. A convention that could not be
    checked leaves the gap unattributable exactly as a failing one does."""
    a = check_equivalence(SPEC, sepsyn_result(), 20, None, dwsim_run())
    assert by_name(a)["feed stage"].holds is None
    assert can_report_gap(a) is False


def test_a_non_converged_dwsim_run_blocks_the_gap():
    a = check_equivalence(SPEC, sepsyn_result(), 20, 10,
                          dwsim_run(converged=False,
                                    errors=("DCErrorStillHigh",)))
    assert can_report_gap(a) is False


def test_the_unattributed_contributors_are_always_named():
    """The property packages differ and that is deferred, not solved. Every
    reported gap must say so rather than implying the difference is all
    shortcut error."""
    assert UNATTRIBUTED
    assert any("property package" in u for u in UNATTRIBUTED)
