"""The DWSIM adapter. Fixture transport by default, live behind a marker."""
import pytest

from sepsyn.simulators.base import ColumnSpec
from sepsyn.simulators.dwsim_adapter import DwsimSimulator, FixtureTransport
from sepsyn.types import Component, Feed

SPEC = ColumnSpec("Benzene", "Toluene", 0.99, 0.99, 101325.0)


def bt_feed():
    return Feed(components=(Component("Benzene", "71-43-2", 60.0),
                            Component("Toluene", "108-88-3", 40.0)),
                T_K=298.15, P_Pa=101325.0)


def test_a_recorded_run_is_replayed(tmp_path):
    from sepsyn.simulators.dwsim_fixtures import DwsimRun, save_fixture
    run = DwsimRun(
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
        condenser_duty_kW=1083.4, reboiler_duty_kW=1447.1)
    save_fixture(str(tmp_path / "benzene_toluene_20_10.json"), run)

    sim = DwsimSimulator(FixtureTransport(str(tmp_path)))
    got = sim.design_from_stages(bt_feed(), SPEC, 20, 10)
    assert got.converged
    assert got.condenser_duty_kW == pytest.approx(1083.4)


def test_a_missing_fixture_is_an_explicit_failure_not_a_silent_zero(tmp_path):
    sim = DwsimSimulator(FixtureTransport(str(tmp_path)))
    with pytest.raises(FileNotFoundError, match="benzene_toluene"):
        sim.design_from_stages(bt_feed(), SPEC, 20, 10)


def test_the_adapter_converts_kmol_hr_to_mol_s():
    """sepsyn works in kmol/hr and DWSIM in mol/s. A factor of 3.6 in the wrong
    place is the kind of basis error this project exists to prevent."""
    from sepsyn.simulators.dwsim_adapter import feed_to_mol_s
    got = feed_to_mol_s(bt_feed())
    assert got["Benzene"] == pytest.approx(60.0 / 3.6)
    assert got["Toluene"] == pytest.approx(40.0 / 3.6)


def test_component_names_are_mapped_to_the_dwsim_database():
    """sepsyn says Butane, the DWSIM database says N-butane. An unmapped name
    would silently produce a column missing a component."""
    from sepsyn.simulators.dwsim_adapter import dwsim_name
    assert dwsim_name("Butane") == "N-butane"
    assert dwsim_name("Pentane") == "N-pentane"
    assert dwsim_name("Hexane") == "N-hexane"
    assert dwsim_name("Benzene") == "Benzene"


def test_an_unmappable_name_is_refused_rather_than_passed_through():
    from sepsyn.simulators.dwsim_adapter import UnknownDwsimCompound, dwsim_name
    with pytest.raises(UnknownDwsimCompound, match="Unobtainium"):
        dwsim_name("Unobtainium")


def test_the_adapter_never_mutates_a_flowsheet():
    """Probe finding 4. A mutated flowsheet silently doubled the feed, with
    entirely plausible compositions, and only a mass balance caught it. The
    invariant is enforced by inspecting the source because the failure it
    prevents is invisible in the numbers.

    Parsed with ast rather than searched as text. The first version scanned raw
    source and failed on the module docstring, which names disconnect_objects
    in order to explain why it is forbidden. A guard that cannot tell a
    prohibition from a violation is not a guard.
    """
    import ast

    import sepsyn.simulators.dwsim_adapter as a
    tree = ast.parse(open(a.__file__).read())
    identifiers = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    identifiers |= {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    identifiers |= {n.name for n in ast.walk(tree)
                    if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    for forbidden in ("disconnect_objects", "reconfigure", "reconnect"):
        assert forbidden not in identifiers, (
            f"{forbidden} is CALLED in the adapter; a mutated flowsheet "
            f"produced a silently doubled feed in the 09-09 probe")
