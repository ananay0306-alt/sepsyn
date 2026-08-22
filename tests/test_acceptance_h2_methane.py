"""ACCEPTANCE TEST 1 -- this is the milestone.

Separate equimolar hydrogen and methane, 50 kmol/hr each, at 25 C and 1 atm,
90% hydrogen overhead.

The correct answer is that distillation is INFEASIBLE: both components are
above their critical temperature at feed conditions, so no liquid phase exists
and there is nothing for a column to equilibrate. A tool that confidently
designs a column here has failed.
"""
import pytest
from sepsyn.cli import parse_feed, screen, main
from sepsyn.report import format_report


def h2_methane():
    return parse_feed("Hydrogen:50,Methane:50", T_K=298.15, P_Pa=101325.0)


def test_verdict_is_infeasible():
    _, _, overall = screen(h2_methane())
    assert overall == "infeasible"


def test_R04_is_the_rule_that_fired():
    _, verdicts, _ = screen(h2_methane())
    assert [v.rule_id for v in verdicts if v.fired] == ["R-04"]


def test_alternatives_are_named():
    _, verdicts, _ = screen(h2_methane())
    fired = [v for v in verdicts if v.fired][0]
    assert "PSA" in fired.technologies
    assert "membrane" in fired.technologies


def test_report_shows_the_numbers_that_decided_it():
    feed = h2_methane()
    record, verdicts, overall = screen(feed)
    text = format_report(feed, record, verdicts, overall, explain=True)
    assert "33.1" in text          # hydrogen critical temperature
    assert "190.5" in text or "190.6" in text
    assert "SUPERCRITICAL" in text
    assert "R-04" in text
    assert "INFEASIBLE" in text
    assert "PSA" in text


def test_report_also_shows_rules_that_did_not_fire():
    feed = h2_methane()
    record, verdicts, overall = screen(feed)
    text = format_report(feed, record, verdicts, overall, explain=True)
    assert "not fired" in text
    assert "R-01" in text


def test_cli_runs_and_returns_zero(capsys):
    code = main(["--feed", "Hydrogen:50,Methane:50", "--T", "298.15", "--explain"])
    assert code == 0
    assert "INFEASIBLE" in capsys.readouterr().out
