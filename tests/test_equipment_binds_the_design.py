"""The recorded equipment choice must be the one that actually ran.

This is the whole lesson of the 58 percent condenser-duty discrepancy: the two
calculations were each correct, and disagreed because one of them used a
partial condenser and neither said so. A rule table that RECOMMENDS a condenser
while the adapter silently hardcodes a different one reproduces that failure
with better documentation.
"""
import pytest

from sepsyn.cli import design_if_feasible
from sepsyn.equipment import DesignContext, choose_equipment
from sepsyn.simulators.base import ColumnSpec
from sepsyn.simulators.biosteam_adapter import BioSteamSimulator
from sepsyn.types import Component, Feed

ATM = 101325.0


def benzene_toluene(T_K=298.15):
    return Feed(
        components=(Component("Benzene", "71-43-2", 60.0),
                    Component("Toluene", "108-88-3", 40.0)),
        T_K=T_K, P_Pa=ATM,
    )


def test_spec_defaults_to_a_total_condenser_and_says_so_in_the_type():
    assert ColumnSpec("Benzene", "Toluene", 0.99, 0.99, ATM).condenser_type == "total"


def test_the_adapter_honours_a_partial_condenser_when_asked():
    """Not a preference the adapter may ignore. A partial condenser does
    roughly R/(R+1) of the duty of a total one, so if the flag were ignored the
    two duties would come back equal."""
    sim = BioSteamSimulator()
    feed = benzene_toluene()
    total = sim.design_column(feed, ColumnSpec("Benzene", "Toluene", 0.99, 0.99,
                                               ATM, condenser_type="total"))
    partial = sim.design_column(feed, ColumnSpec("Benzene", "Toluene", 0.99, 0.99,
                                                 ATM, condenser_type="partial"))
    assert total.converged, total.error
    assert partial.converged, partial.error
    assert partial.condenser_duty_kW < total.condenser_duty_kW


def test_an_unknown_condenser_type_is_refused_rather_than_guessed():
    sim = BioSteamSimulator()
    r = sim.design_column(
        benzene_toluene(),
        ColumnSpec("Benzene", "Toluene", 0.99, 0.99, ATM,
                   condenser_type="thermosiphon"))
    assert not r.converged
    assert "thermosiphon" in (r.error or "")


def test_the_column_diameter_comes_back_in_METRES():
    """BioSTEAM reports Diameter in FEET. The internals rule keys on 0.6 m, so
    handing it 3.8 (feet) as if it were metres would make the small-diameter
    branch unreachable for every column ever designed."""
    sim = BioSteamSimulator()
    r = sim.design_column(benzene_toluene(),
                          ColumnSpec("Benzene", "Toluene", 0.99, 0.99, ATM))
    assert r.converged, r.error
    assert r.column_diameter_m is not None
    assert 0.3 < r.column_diameter_m < 3.0, "looks like feet, not metres"


@pytest.fixture(scope="module")
def designed():
    return design_if_feasible(benzene_toluene(), "Benzene", "Toluene")


def test_the_design_returns_its_equipment_decisions(designed):
    equipment = designed[6]
    assert {d.step for d in equipment} == {22, 23, 24, 25}


def test_the_condenser_that_ran_is_the_condenser_that_was_recorded(designed):
    """The consistency guard. If these ever disagree, the design record is
    describing a column that was not simulated."""
    spec, equipment = designed[0], designed[6]
    recorded = next(d for d in equipment if d.step == 22)
    assert spec.condenser_type == recorded.choice


def test_the_internals_decision_is_made_on_the_SIZED_column(designed):
    """Step 24 keys on diameter, which does not exist until the column has been
    designed. Deciding it on a pre-design context would leave every column
    permanently 'unknown diameter' and quietly default to trays."""
    result, equipment = designed[3], designed[6]
    internals = next(d for d in equipment if d.step == 24)
    context = DesignContext(pressure_Pa=ATM, n_supercritical_at_feed=0,
                            column_diameter_m=result.column_diameter_m)
    expected = next(d for d in choose_equipment(context) if d.step == 24)
    assert internals.choice == expected.choice
