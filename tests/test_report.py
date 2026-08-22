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
