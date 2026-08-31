"""Equipment choices as design rules. Heuristic steps 22 to 25.

These are discrete choices, not calculations, and each one changes the numbers
that follow. The project's own evidence for why they must be recorded: an
unrecorded condenser type produced a 58% condenser-duty discrepancy between two
calculations that were each individually correct.

They live in their own table, NOT in rules.yaml. A screening rule answers "can
this be separated at all" and feeds overall_verdict, where worst-verdict-wins;
an equipment rule answers "which of these two pieces of kit". Mixing them would
let a preference for packing outrank a feasibility finding.
"""
import pytest

from sepsyn.equipment import (
    DesignContext,
    choose_equipment,
    load_equipment_rules,
)

ATM = 101325.0


def ordinary() -> DesignContext:
    """A well-behaved atmospheric binary: benzene/toluene, wide column."""
    return DesignContext(
        pressure_Pa=ATM, n_supercritical_at_feed=0, min_alpha=2.4,
        bottoms_T_at_column_P=383.0, feed_q=1.0, stages=40.0,
        column_diameter_m=1.15,
    )


def decisions_for(context) -> dict[int, object]:
    return {d.step: d for d in choose_equipment(context)}


def test_every_equipment_step_gets_a_decision():
    """22 to 25 inclusive. A step that produced no decision would be a choice
    left implicit, which is the exact failure these rules exist to prevent."""
    assert set(decisions_for(ordinary())) == {22, 23, 24, 25}


def test_a_non_condensable_in_the_feed_calls_for_a_partial_condenser():
    context = DesignContext(
        pressure_Pa=ATM, n_supercritical_at_feed=1, min_alpha=3.0,
        bottoms_T_at_column_P=350.0, feed_q=1.0, stages=20.0,
        column_diameter_m=1.0,
    )
    d = decisions_for(context)[22]
    assert d.choice == "partial"
    assert d.status == "decided"


def test_an_ordinary_binary_gets_a_total_condenser_MARKED_AS_A_DEFAULT():
    """The status is the point. A total condenser here was not proved by
    evidence, it was assumed by convention, and a reader has to be able to tell
    those apart before comparing this design with anyone else's."""
    d = decisions_for(ordinary())[22]
    assert d.choice == "total"
    assert d.status == "default"


def test_a_vacuum_column_chooses_packing():
    context = DesignContext(
        pressure_Pa=20000.0, n_supercritical_at_feed=0, min_alpha=1.8,
        bottoms_T_at_column_P=400.0, feed_q=1.0, stages=30.0,
        column_diameter_m=2.0,
    )
    d = decisions_for(context)[24]
    assert d.choice == "packing"
    assert d.status == "decided"
    assert "pressure drop" in d.because


def test_a_wide_atmospheric_column_chooses_trays():
    d = decisions_for(ordinary())[24]
    assert d.choice == "trays"


def test_a_narrow_column_chooses_packing():
    context = DesignContext(
        pressure_Pa=ATM, n_supercritical_at_feed=0, min_alpha=2.4,
        bottoms_T_at_column_P=383.0, feed_q=1.0, stages=40.0,
        column_diameter_m=0.4,
    )
    assert decisions_for(context)[24].choice == "packing"


def test_a_column_of_unknown_diameter_does_not_silently_get_trays():
    """None is not 'large'. Before a column is sized the diameter is unknown,
    and a rule keyed on diameter must not fire either way on a missing number."""
    context = DesignContext(
        pressure_Pa=ATM, n_supercritical_at_feed=0, min_alpha=2.4,
        bottoms_T_at_column_P=383.0, feed_q=1.0, stages=None,
        column_diameter_m=None,
    )
    d = decisions_for(context)[24]
    assert d.choice == "trays"
    assert d.status == "default", "an unsized column has not been decided"


def test_a_hot_bottoms_leaves_the_reboiler_type_OPEN():
    """sepsyn has no viscosity or fouling data, so it must decline rather than
    nominate a kettle for a service that may need forced circulation."""
    context = DesignContext(
        pressure_Pa=ATM, n_supercritical_at_feed=0, min_alpha=1.6,
        bottoms_T_at_column_P=520.0, feed_q=1.0, stages=45.0,
        column_diameter_m=1.5,
    )
    d = decisions_for(context)[23]
    assert d.status == "open"
    assert d.choice is None
    assert d.requires, "an open decision must name what would settle it"


def test_reflux_thermal_state_is_an_assumption_and_says_so():
    d = decisions_for(ordinary())[25]
    assert d.choice == "saturated"
    assert d.status == "default"


def test_every_decision_says_what_must_be_recorded():
    """The 58% lesson. A choice with no must_record is a choice that will be
    made, used, and then lost."""
    for d in choose_equipment(ordinary()):
        assert d.must_record.strip(), f"step {d.step} records nothing"


def test_every_decision_cites_something():
    for d in choose_equipment(ordinary()):
        assert d.cite.strip(), f"step {d.step} cites nothing"


def test_an_open_decision_must_name_a_calculation_or_the_table_will_not_load(
        tmp_path):
    """Mirrors the screening engine's rule for 'undetermined': withholding an
    answer while offering no route to one is worse than saying nothing."""
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "- step: 22\n"
        "  decision: condenser_type\n"
        "  question: total or partial\n"
        "  options: [total, partial]\n"
        "  must_record: which one\n"
        "  default: {choice: total, because: convention, cite: somewhere}\n"
        "  rules:\n"
        "    - id: E-22x\n"
        "      priority: 10\n"
        "      when: 'n_supercritical_at_feed > 0'\n"
        "      choice: null\n"
        "      because: cannot tell\n"
        "      cite: somewhere\n"
    )
    with pytest.raises(ValueError, match="requires"):
        load_equipment_rules(str(bad))


def test_a_rule_choosing_an_option_the_decision_does_not_offer_is_rejected(
        tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "- step: 24\n"
        "  decision: internals\n"
        "  question: trays or packing\n"
        "  options: [trays, packing]\n"
        "  must_record: which one\n"
        "  default: {choice: trays, because: convention, cite: somewhere}\n"
        "  rules:\n"
        "    - id: E-24x\n"
        "      priority: 10\n"
        "      when: 'pressure_Pa < 101325'\n"
        "      choice: structured_packing\n"
        "      because: typo\n"
        "      cite: somewhere\n"
    )
    with pytest.raises(ValueError, match="structured_packing"):
        load_equipment_rules(str(bad))


def test_a_rule_naming_a_property_that_does_not_exist_is_rejected(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "- step: 24\n"
        "  decision: internals\n"
        "  question: trays or packing\n"
        "  options: [trays, packing]\n"
        "  must_record: which one\n"
        "  default: {choice: trays, because: convention, cite: somewhere}\n"
        "  rules:\n"
        "    - id: E-24y\n"
        "      priority: 10\n"
        "      when: 'liquid_viscosity > 5'\n"
        "      choice: packing\n"
        "      because: invented a property\n"
        "      cite: somewhere\n"
    )
    with pytest.raises(ValueError, match="liquid_viscosity"):
        load_equipment_rules(str(bad))
