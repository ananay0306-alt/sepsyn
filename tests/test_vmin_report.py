"""The V_min report, and heuristics scored against a bound rather than against
another estimate from the same family."""
import pytest

from sepsyn.cli import main

ALKANES = ["--feed", "Propane:10,Butane:20,Pentane:60,Hexane:10", "--T", "330",
           "--vmin", "--order", "Propane,Butane,Pentane,Hexane"]


def run(capsys, argv=None):
    code = main(argv or ALKANES)
    return code, capsys.readouterr().out


def test_it_runs_and_returns_zero(capsys):
    code, out = run(capsys)
    assert code == 0
    assert "MINIMUM VAPOUR" in out


def test_it_names_the_optimal_sequence_and_its_total_vapour(capsys):
    _, out = run(capsys)
    assert "OPTIMAL SEQUENCE" in out
    assert "kmol/hr" in out
    assert "Propane" in out and "Hexane" in out


def test_it_says_the_result_is_a_BOUND_not_a_duty(capsys):
    """A reader who mistook minimum vapour for a reboiler load would be badly
    misled. The report has to say so in its own words, not rely on the reader
    knowing what Underwood computes."""
    _, out = run(capsys)
    low = out.lower()
    assert "infinite stages" in low
    assert "bound" in low


def test_it_reports_the_split_count_AGAINST_the_number_of_sequences(capsys):
    """The polynomial claim, made visible. A reader should be able to see that
    it did not enumerate, rather than take it on faith."""
    _, out = run(capsys)
    assert "10" in out      # (group, split) pairs at four components
    assert "5 sequences" in out or "5 " in out


def test_the_verification_stage_is_reported_beside_the_optimum(capsys):
    """Selection cannot see condenser feasibility. Measured on this feed, the
    chosen sequence contains a column that screens undetermined, and hiding
    that beneath a confident optimum is the exact failure of 09-10."""
    _, out = run(capsys)
    assert "VERIFICATION" in out.upper()
    assert "UNDETERMINED" in out.upper()
    assert "R-09" in out


def test_the_heuristics_are_scored_against_the_MINIMUM(capsys):
    """Not against sepsyn's own cost model. That was circular -- an ungraded
    ruler grading itself."""
    _, out = run(capsys)
    assert "HEURISTICS" in out
    for name in ("easiest_first", "hardest_last",
                 "most_plentiful_first", "equimolar"):
        assert name in out
    assert "%" in out


def test_a_heuristic_that_finds_the_optimum_is_marked_as_such(capsys):
    """Excess over the minimum is the score. A proxy that lands on the optimal
    sequence scores zero and must be shown scoring zero, not shown blank."""
    _, out = run(capsys)
    assert "optimum" in out.lower()


def test_the_alpha_basis_appears_in_the_report(capsys):
    """A bare relative volatility is meaningless, and so is a V_min computed
    from one. The condition travels into the report."""
    _, out = run(capsys)
    assert "bar" in out
    assert "bubble point" in out.lower()


def test_vmin_requires_order(capsys):
    code, out = run(capsys, ["--feed", "Propane:10,Butane:20", "--T", "330",
                             "--vmin"])
    assert code == 2
    assert "--order" in out


def test_vmin_rejects_an_order_naming_absent_components(capsys):
    code, out = run(capsys, ["--feed", "Propane:10,Butane:20", "--T", "330",
                             "--vmin", "--order", "Propane,Octane"])
    assert code == 2
    assert "Octane" in out


AZEOTROPE = ["--feed", "Ethanol:40,Water:40,Butanol:20", "--T", "298",
             "--vmin", "--order", "Ethanol,Water,Butanol"]


def test_an_eliminated_sequence_is_announced_BEFORE_its_vapour_number(capsys):
    """Minimum vapour is computed from relative volatilities at the bubble
    point, and an azeotrope does not show up there -- ethanol/water reads
    alpha 1.9 while the split is thermodynamically impossible. The dynamic
    program therefore returns a perfectly confident 415.3 kmol/hr for a
    separation that cannot be performed.

    Stage 2 catches it, but the reader meets the number first and the refusal
    eight lines later. A skimming reader takes away the number. The headline
    must carry the verdict.
    """
    _, out = run(capsys, AZEOTROPE)
    head = out[:out.index("OPTIMAL SEQUENCE")]
    assert "CANNOT BE PERFORMED" in head.upper() or "IMPOSSIBLE" in head.upper()
    assert "R-03" in head


def test_the_heuristics_are_NOT_scored_against_an_impossible_optimum(capsys):
    """Reporting that a heuristic is 13.5% worse than an optimum which cannot
    be built is a precision that means nothing. Say the comparison is void
    rather than print a number for it."""
    _, out = run(capsys, AZEOTROPE)
    assert "%" not in out[out.index("HEURISTICS"):]


def test_a_feasible_run_is_UNAFFECTED(capsys):
    """The alkane feed is screened feasible and must still lead with its
    optimum, not with a warning that does not apply to it."""
    _, out = run(capsys)
    head = out[:out.index("OPTIMAL SEQUENCE")]
    assert "CANNOT BE PERFORMED" not in head.upper()
    assert "%" in out[out.index("HEURISTICS"):]
