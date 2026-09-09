"""Recorded DWSIM runs.

A fixture records the CONFIGURATION as well as the result. A recorded number
whose configuration is unknown cannot be checked for equivalence, and checking
equivalence is what this milestone is for.
"""
import json

import pytest

from sepsyn.simulators.dwsim_fixtures import (
    DwsimRun, FixtureMismatch, load_fixture, save_fixture)


def a_run(**over):
    base = dict(
        feed_mol_s={"Benzene": 16.6667, "Toluene": 11.1111},
        T_K=298.15, P_Pa=101325.0,
        stages=20, feed_stage=10,
        condenser_spec={"type": "Component Recovery", "compound": "Benzene",
                        "value": 99.0},
        reboiler_spec={"type": "Component Recovery", "compound": "Toluene",
                       "value": 99.0},
        property_package="Peng-Robinson (PR)",
        solver="Napthali-Sandholm (Simultaneous Correction)",
        converged=True, errors=(),
        distillate_mol_s={"Benzene": 16.5, "Toluene": 0.111},
        bottoms_mol_s={"Benzene": 0.1667, "Toluene": 11.0},
        condenser_duty_kW=1083.4, reboiler_duty_kW=1447.1,
        distillate_T_K=353.4, bottoms_T_K=383.3,
    )
    base.update(over)
    return DwsimRun(**base)


def test_a_run_round_trips_through_a_file(tmp_path):
    path = tmp_path / "r.json"
    original = a_run()
    save_fixture(str(path), original)
    assert load_fixture(str(path)) == original


def test_the_fixture_records_the_CONFIGURATION_not_only_the_result(tmp_path):
    """The whole point. A recorded duty whose stage count is unknown cannot be
    compared against anything."""
    path = tmp_path / "r.json"
    save_fixture(str(path), a_run())
    data = json.loads(path.read_text())
    for key in ("stages", "feed_stage", "property_package", "solver",
                "condenser_spec", "reboiler_spec", "P_Pa", "T_K"):
        assert key in data, f"{key} must be recorded"


def test_a_non_converged_run_is_recordable(tmp_path):
    """A DWSIM failure is data. The 09-09 probe produced two, and a harness
    that can only record successes cannot record what it learned."""
    path = tmp_path / "r.json"
    run = a_run(converged=False, errors=("DCErrorStillHigh",),
                condenser_duty_kW=None, reboiler_duty_kW=None,
                distillate_mol_s={}, bottoms_mol_s={})
    save_fixture(str(path), run)
    back = load_fixture(str(path))
    assert back.converged is False
    assert back.errors == ("DCErrorStillHigh",)


def test_a_fixture_missing_a_configuration_field_is_refused(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({
        "feed_mol_s": {"Benzene": 1.0}, "T_K": 298.15, "P_Pa": 101325.0,
        "converged": True, "errors": [],
        "distillate_mol_s": {}, "bottoms_mol_s": {},
    }))
    with pytest.raises(FixtureMismatch, match="stages"):
        load_fixture(str(path))


def test_mass_balance_is_checkable_from_a_fixture():
    """Finding 4 of the probe: a mutated flowsheet produced a doubled feed with
    plausible numbers, and only a mass balance caught it. The fixture must
    carry enough to re-check that."""
    run = a_run()
    fed = sum(run.feed_mol_s.values())
    out = sum(run.distillate_mol_s.values()) + sum(run.bottoms_mol_s.values())
    assert out == pytest.approx(fed, rel=1e-3)
