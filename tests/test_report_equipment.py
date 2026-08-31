"""The equipment choices must appear in the printed design. Steps 22 to 25."""
from sepsyn.equipment import DesignContext, choose_equipment
from sepsyn.report import format_design
from sepsyn.simulators.base import ColumnResult, ColumnSpec

ATM = 101325.0


def _rendered(context=None):
    context = context or DesignContext(pressure_Pa=ATM,
                                       n_supercritical_at_feed=0,
                                       bottoms_T_at_column_P=383.0,
                                       column_diameter_m=1.15)
    spec = ColumnSpec("Benzene", "Toluene", 0.99, 0.99, ATM)
    result = ColumnResult(
        distillate={"Benzene": 59.4}, bottoms={"Toluene": 39.6},
        stages=40.0, reflux=1.5, minimum_reflux=1.25,
        installed_cost_USD=1.0e6, utility_cost_USD_hr=10.0,
        converged=True, feed_q=1.0,
    )
    return format_design(spec, [], None, result, [], [],
                         choose_equipment(context))


def test_all_four_equipment_steps_are_printed():
    out = _rendered()
    for step in (22, 23, 24, 25):
        assert f"step {step}" in out


def test_a_default_is_labelled_as_a_default_not_stated_as_a_finding():
    out = _rendered()
    assert "by default" in out


def test_an_open_decision_prints_what_would_settle_it():
    hot = DesignContext(pressure_Pa=ATM, n_supercritical_at_feed=0,
                        bottoms_T_at_column_P=520.0, column_diameter_m=1.5)
    out = _rendered(hot)
    assert "NOT DECIDED" in out
    assert "viscosity" in out


def test_what_must_be_recorded_is_printed_for_every_decision():
    out = _rendered()
    assert "must record" in out.lower()


def test_a_report_without_equipment_still_renders():
    """format_design predates this section and is called with six arguments in
    places. Adding a seventh must not break them."""
    spec = ColumnSpec("Benzene", "Toluene", 0.99, 0.99, ATM)
    result = ColumnResult({}, {}, 0.0, 0.0, 0.0, 0.0, 0.0, False,
                          error="did not converge")
    assert "COLUMN DESIGN" in format_design(spec, [], None, result, [], [])
