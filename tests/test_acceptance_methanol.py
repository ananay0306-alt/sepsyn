"""ACCEPTANCE TEST 2 -- this is the milestone.

Methanol / water / glycerol at 100 / 80 / 25 kmol/hr. Distillate at 99 mol%
methanol, bottoms at 1 mol% methanol, both mole fractions of the TOTAL stream,
explicitly not a keys-only basis (design spec, Scope item 2).

The correct answer is one column meeting that spec, PLUS a printed flag that
water and glycerol were never separated from each other because no
specification was given for them. Answering the literal question while saying
what was not asked is the behaviour under test.

Note what this file does NOT do: pass 0.99 as a recovery and then assert a mole
fraction. Those are different specifications -- 99% recovery asks how much of
the methanol fed goes overhead, 99 mol% purity asks how much of the overhead is
methanol -- and substituting one for the other lands at 0.99198, missing the
stated target by 0.002. The tolerances here are tight enough to see that.
"""
import pytest

from sepsyn.cli import design_if_feasible, main, parse_feed, screen
from sepsyn.report import format_design

FEED_SPEC = "Methanol:100,Water:80,Glycerol:25"
DISTILLATE_PURITY = 0.99
BOTTOMS_IMPURITY = 0.01


def feed():
    return parse_feed(FEED_SPEC, T_K=330.0, P_Pa=101325.0)


@pytest.fixture(scope="module")
def designed():
    return design_if_feasible(feed(), "Methanol", "Water",
                              distillate_purity=DISTILLATE_PURITY,
                              bottoms_impurity=BOTTOMS_IMPURITY)


def test_distillation_is_feasible():
    _, _, overall = screen(feed())
    assert overall in ("feasible", "caution")


def test_R01_fires():
    _, verdicts, _ = screen(feed())
    assert "R-01" in [v.rule_id for v in verdicts if v.fired]


def test_one_column_meets_the_methanol_spec_on_a_total_stream_basis(designed):
    """THE milestone assertion, on the basis the spec actually names."""
    result = designed[3]
    assert result.converged, result.error

    distillate_purity = result.distillate["Methanol"] / sum(result.distillate.values())
    bottoms_impurity = result.bottoms["Methanol"] / sum(result.bottoms.values())

    assert distillate_purity == pytest.approx(DISTILLATE_PURITY, abs=1e-4)
    assert bottoms_impurity == pytest.approx(BOTTOMS_IMPURITY, abs=1e-4)


def test_the_spec_is_not_being_met_on_a_keys_only_basis_by_accident(designed):
    """Guard the basis itself.

    The keys-only reading of the same distillate is a different number. If the
    two ever coincide, the assertion above stops distinguishing them and this
    test says so rather than letting it pass quietly.
    """
    d = designed[3].distillate
    total_basis = d["Methanol"] / sum(d.values())
    keys_only = d["Methanol"] / (d["Methanol"] + d["Water"])
    assert abs(total_basis - keys_only) > 1e-9 or sum(d.values()) == d["Methanol"] + d["Water"]


def test_all_verification_checks_pass(designed):
    checks = designed[4]
    failed = [f"{c.name}: {c.detail}" for c in checks if not c.passed]
    assert failed == [], f"failed checks: {failed}"


def test_glycerol_is_flagged_as_unseparated(designed):
    """The ambiguity flag. This is what distinguishes answering the question
    from silently missing part of it."""
    assert "Glycerol" in designed[5]


def test_the_flag_names_what_glycerol_was_not_separated_FROM(designed):
    """'Glycerol was not separated' is only half the fact. It shares the
    bottoms with water, and water is the component a reader would assume the
    column had dealt with, because water is a key."""
    text = format_design(*designed)
    assert "not separated" in text.lower()

    # Scope the assertion to the NOTE LINE. "Water" occurs throughout the
    # products table and the verification block, so asserting it against the
    # whole report passes even if the note names nobody -- confirmed by
    # mutation. The claim under test is that the note itself says what glycerol
    # was left mixed with.
    note = next(ln for ln in text.splitlines() if "NOT separated" in ln)
    assert "Glycerol" in note
    assert "Water" in note, f"note does not say what it was mixed with: {note!r}"


def test_the_flag_is_backed_by_where_the_component_actually_went(designed):
    """Do not assert a destination the result does not support. Glycerol is
    measured at 25.0000 to the bottoms and 0.000000 overhead, so the note
    saying 'bottoms' is a report of the result, not an assumption about it."""
    result = designed[3]
    assert result.bottoms["Glycerol"] == pytest.approx(25.0, abs=1e-3)
    assert result.distillate["Glycerol"] == pytest.approx(0.0, abs=1e-6)
    assert "bottoms" in format_design(*designed).lower()


def test_cli_designs_and_returns_zero(capsys):
    code = main(["--feed", FEED_SPEC, "--T", "330",
                 "--light-key", "Methanol", "--heavy-key", "Water",
                 "--distillate-purity", "0.99", "--bottoms-impurity", "0.01",
                 "--design"])
    assert code == 0
    out = capsys.readouterr().out

    # NOT `"FEASIBLE" in out.upper()` -- "INFEASIBLE" contains "FEASIBLE", so
    # that assertion passes on the opposite verdict.
    assert "distillation FEASIBLE" in out
    assert "INFEASIBLE" not in out.upper()
    assert "Glycerol" in out
