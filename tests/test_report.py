"""The report must not state a REASON the property record cannot support.

`min_alpha is None` has four distinct causes, only one of which is "there is no
vapour-liquid equilibrium here". Printing that one sentence for all four is the
same class of defect the record itself was fixed for in Task 5: a value
asserting knowledge it does not have.
"""
from sepsyn.cli import parse_feed, screen
from sepsyn.report import format_report


def report_for(spec, T_K):
    feed = parse_feed(spec, T_K=T_K, P_Pa=101325.0)
    record, verdicts, overall = screen(feed)
    return record, format_report(feed, record, verdicts, overall)


def test_single_component_feed_is_not_described_as_having_no_equilibrium():
    """Methanol at 25 C is a liquid with a perfectly ordinary bubble point.

    There is no alpha only because relative volatility needs two components.
    Calling that "no vapour-liquid equilibrium" contradicts the same report's
    own 'condensable' state column and its 337.6 K condensing temperature.
    """
    record, text = report_for("Methanol:100", T_K=298.15)

    # Guard the premise: this really is the empty-alphas, fully-condensable case.
    assert record.min_alpha is None
    assert record.n_supercritical_at_feed == 0
    assert record.feed_phase == "liquid"

    assert "no vapour-liquid equilibrium" not in text
    assert "no liquid phase" not in text
    assert "pair" in text


def test_supercritical_feed_is_still_told_it_has_no_liquid_phase():
    """The one case where the strong claim IS true must keep making it."""
    record, text = report_for("Hydrogen:50,Methane:50", T_K=298.15)

    assert record.n_supercritical_at_feed == record.n_components
    assert "no liquid phase" in text


def test_the_two_empty_alpha_cases_do_not_print_the_same_explanation():
    """If these ever collapse to one sentence again, the distinction is gone."""
    _, single = report_for("Methanol:100", T_K=298.15)
    _, supercritical = report_for("Hydrogen:50,Methane:50", T_K=298.15)

    def alpha_line(text):
        return next(ln for ln in text.splitlines() if ln.strip().startswith("alpha:"))

    assert alpha_line(single) != alpha_line(supercritical)


def test_alphas_are_actually_listed_when_the_feed_has_them():
    """The normal case, which the other tests here all skip.

    Every other test in this file uses a feed with NO alphas -- one component,
    or all supercritical -- so all of them pass against a report that never
    prints an alpha line at all. Without this, breaking the alpha branch is
    invisible: the code falls through to "not applicable" and the single-
    component test is perfectly happy. Found by mutation, not by reading.
    """
    record, text = report_for("Methanol:100,Water:80", T_K=330.0)

    assert record.alphas, "premise: this feed must produce alphas"
    assert "alpha Methanol/Water" in text
    assert "3.48" in text                       # measured 3.481 at 345.1 K
    assert "bubble point at column P" in text   # the basis travels with the value
    assert "not computed" not in text
    assert "not applicable" not in text


def test_every_alpha_printed_carries_its_conditions():
    """A bare alpha is meaningless -- Alpha exists to keep T and P attached, so
    the report must not drop them on the way out."""
    record, text = report_for("Methanol:100,Water:80,Glycerol:25", T_K=330.0)

    alpha_lines = [ln for ln in text.splitlines() if ln.strip().startswith("alpha ")]
    assert len(alpha_lines) == len(record.alphas)
    for line in alpha_lines:
        assert " K," in line and "bar" in line, f"conditions missing: {line!r}"


# --- requires / limitations in the output ------------------------------------


def _verdict(**kw):
    from sepsyn.engine import Verdict
    base = dict(rule_id="R-99", rule_name="partial condensation may recover a liquid",
                condition="feed_phase == 'vapor'", values={"feed_phase": "vapor"},
                verdict="undetermined", technologies=("flash",),
                because="cheap cooling may condense enough to matter",
                fired=True, requires=("vapour fraction from a flash at 313.15 K",),
                limitations="worthless when the vapour fraction stays near 1")
    base.update(kw)
    return Verdict(**base)


def test_report_prints_the_calculation_a_fired_rule_still_requires():
    """A named calculation that never reaches the page cannot be acted on, and
    the verdict then looks like an ordinary refusal to decide."""
    feed = parse_feed("Methanol:100", T_K=298.15, P_Pa=101325.0)
    record, _, _ = screen(feed)
    text = format_report(feed, record, [_verdict()], "undetermined")

    assert "vapour fraction from a flash at 313.15 K" in text
    assert "worthless when the vapour fraction stays near 1" in text


def test_report_does_not_print_a_requires_block_for_a_rule_that_did_not_fire():
    """Printing the calculation for every loaded rule would bury the one that
    is actually outstanding."""
    feed = parse_feed("Methanol:100", T_K=298.15, P_Pa=101325.0)
    record, _, _ = screen(feed)
    text = format_report(feed, record, [_verdict(fired=False)], "unknown")

    assert "vapour fraction from a flash at 313.15 K" not in text


def test_the_rule_that_DECIDED_the_verdict_is_named_and_comes_first():
    """Ethanol/water fires R-01 (distillation is viable) and R-03 (an azeotrope
    blocks it). The verdict is INFEASIBLE because the worst verdict wins.

    Printed in rule-id order, the first sentence a reader meets under
    "INFEASIBLE" is R-01 arguing the split IS achievable. Nothing marks which
    rule carried the decision, so the report reads as contradicting itself and
    the reader has to know the ranking to resolve it.

    The reason that MATCHES the overall verdict comes first, and every reason
    carries its rule id.
    """
    from sepsyn.cli import main
    import io
    import contextlib

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        main(["--feed", "Ethanol:50,Water:50", "--T", "298"])
    out = buf.getvalue()
    block = out[out.index("VERDICT"):]
    reasons = [ln for ln in block.splitlines()[1:] if ln.startswith("         ")]

    assert reasons, "the verdict must explain itself"
    assert "R-03" in reasons[0], (
        f"R-03 carried the INFEASIBLE verdict and must be named first, got: "
        f"{reasons[0]!r}")
    assert "azeotrope" in reasons[0]
    # The other fired rule is still reported -- it is evidence, not noise --
    # but it is clearly marked as not being what decided the outcome.
    assert any("R-01" in r for r in reasons[1:])


def test_a_reason_that_did_not_decide_is_marked_as_such():
    """A reader must be able to tell at a glance which sentence is the finding
    and which is merely a rule that also fired."""
    from sepsyn.cli import main
    import io
    import contextlib

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        main(["--feed", "Ethanol:50,Water:50", "--T", "298"])
    out = buf.getvalue()
    block = out[out.index("VERDICT"):]
    assert "also fired" in block.lower() or "not decisive" in block.lower()
