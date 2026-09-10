"""The sequencing report, end to end from the command line."""
import pytest

from sepsyn.cli import main

ALKANES = ["--feed", "Propane:40,Butane:30,Pentane:20,Hexane:10",
           "--T", "330", "--sequence",
           "--order", "Propane,Butane,Pentane,Hexane"]


def test_it_runs_and_returns_zero(capsys):
    assert main(ALKANES) == 0
    assert "SEQUENCES" in capsys.readouterr().out


def test_it_reports_how_many_sequences_it_evaluated(capsys):
    """Wording changed 2026-09-10: the header now separates costable from
    undetermined, because on an alkane feed four of five sequences are
    designed but not costable and a single count hid that."""
    main(ALKANES)
    out = capsys.readouterr().out
    assert "5 enumerated" in out
    assert "costable" in out and "undetermined" in out


def test_it_names_the_winner_with_its_cost(capsys):
    main(ALKANES)
    out = capsys.readouterr().out
    assert "BEST SEQUENCE" in out
    assert "$" in out
    assert "Propane/Butane+Pentane+Hexane" in out


def test_it_shows_the_near_optimal_set_as_a_SET_not_a_ranked_list(capsys):
    """The wording matters. Numbering these 1, 2, 3 would reintroduce exactly
    the false precision the ranking module exists to avoid."""
    main(ALKANES)
    out = capsys.readouterr().out
    assert "WITHIN 5%" in out.upper()
    assert "not ranked" in out.lower()


def test_it_states_whether_the_two_metrics_agreed(capsys):
    main(ALKANES)
    out = capsys.readouterr().out
    assert "vapour" in out.lower()
    assert "agree" in out.lower()


def test_sequence_requires_order(capsys):
    code = main(["--feed", "Propane:40,Butane:30", "--T", "330", "--sequence"])
    assert code == 2
    assert "--order" in capsys.readouterr().out


def test_an_order_naming_an_absent_component_is_refused(capsys):
    code = main(["--feed", "Propane:40,Butane:30", "--T", "330", "--sequence",
                 "--order", "Propane,Heptane"])
    assert code == 2
    assert "Heptane" in capsys.readouterr().out


def test_eliminated_sequences_are_listed_with_their_reason(capsys):
    """Acetone/ethanol/water: every sequence eventually needs the azeotropic
    ethanol/water split, so all of them are eliminated, each citing R-03."""
    main(["--feed", "Acetone:30,Ethanol:40,Water:30", "--T", "330",
          "--sequence", "--order", "Acetone,Ethanol,Water"])
    out = capsys.readouterr().out
    assert "ELIMINATED" in out
    assert "R-03" in out
