"""The Phase B report: exposure as a trade-off, and the heuristic scorecard."""
import pytest

from sepsyn.cli import main

BASE = ["--feed", "Propane:10,Butane:20,Pentane:60,Hexane:10", "--T", "330",
        "--sequence", "--order", "Propane,Butane,Pentane,Hexane"]


def test_the_scorecard_is_printed(capsys):
    assert main(BASE) == 0
    out = capsys.readouterr().out
    assert "HEURISTICS" in out
    for name in ("easiest_first", "most_plentiful_first"):
        assert name in out


def test_it_says_which_heuristic_picked_the_winner(capsys):
    main(BASE)
    assert "picked the winner" in capsys.readouterr().out.lower()


def test_a_wrong_heuristic_shows_what_it_cost(capsys):
    main(BASE)
    assert "worse than the winner" in capsys.readouterr().out


def test_exposure_is_reported_when_a_component_is_tagged(capsys):
    assert main(BASE + ["--tag", "Hexane:corrosive"]) == 0
    out = capsys.readouterr().out
    assert "EXPOSURE" in out
    assert "Hexane" in out
    assert "corrosive" in out


def test_the_report_says_exposure_did_not_change_the_ranking(capsys):
    """It is counted, not enforced. A reader must not assume the cheapest
    sequence was chosen with corrosion weighed in."""
    main(BASE + ["--tag", "Hexane:corrosive"])
    out = capsys.readouterr().out
    assert "NOT used to rank" in out


def test_no_exposure_section_without_tags(capsys):
    main(BASE)
    assert "EXPOSURE" not in capsys.readouterr().out


def test_an_unknown_tag_is_refused_before_anything_is_designed(capsys):
    code = main(BASE + ["--tag", "Hexane:corrossive"])
    assert code == 2
    assert "corrossive" in capsys.readouterr().out


def test_the_report_warns_when_the_proxies_all_agree(capsys):
    """On an ordinary feed the heuristics agree, so the scorecard cannot tell
    them apart. Saying so is the difference between a measurement and a
    coincidence presented as one."""
    main(["--feed", "Propane:40,Butane:30,Pentane:20,Hexane:10", "--T", "330",
          "--sequence", "--order", "Propane,Butane,Pentane,Hexane"])
    out = capsys.readouterr().out
    assert "cannot tell them apart" in out
