"""The Phase B report: exposure as a trade-off, and the heuristic scorecard."""
import pytest

from sepsyn.cli import main

BASE = ["--feed", "Propane:10,Butane:20,Pentane:60,Hexane:10", "--T", "330",
        "--sequence", "--order", "Propane,Butane,Pentane,Hexane"]
# Ethane cannot condense against cooling water at any pressure (Tc 305 K), so
# every sequence keeps an unanswerable R-09. Used where the report's handling
# of undetermined sequences is the thing under test.
ETHANE = ["--feed", "Ethane:10,Propane:20,Butane:60,Pentane:10", "--T", "330",
          "--sequence", "--order", "Ethane,Propane,Butane,Pentane"]


def test_the_scorecard_is_printed(capsys):
    assert main(BASE) == 0
    out = capsys.readouterr().out
    assert "HEURISTICS" in out
    # Statements and citations from the heuristic database (M4), not code
    # names.
    assert "H-05  Perform the easiest separation first" in out
    assert "H-02  Recover the most plentiful component first" in out
    assert "Douglas (1985)" in out and "(citation unverified)" in out


def test_it_says_what_became_of_each_heuristics_choice(capsys):
    """Corrected 2026-11-08: with R-09 answered, three heuristics pick the
    winner and two pick a costed runner-up, priced against it. On the ethane
    feed, where no sequence can be costed, they name routes the tool cannot
    endorse."""
    main(BASE)
    out = capsys.readouterr().out
    assert "picked the winner" in out
    assert "worse than the winner" in out
    main(ETHANE)
    assert "cannot endorse" in capsys.readouterr().out

def test_the_report_names_the_undetermined_sequences(capsys):
    """Asserted against the SEQUENCING section specifically. An earlier version
    checked the whole output and passed on the word 'UNDETERMINED' appearing in
    the feed-level screening report above, while the sequencing section
    mentioned nothing at all. On the ethane feed since 11-08, where R-09
    cannot be answered."""
    main(ETHANE)
    out = capsys.readouterr().out
    seq = out[out.index("SEQUENCES"):]
    assert "UNDETERMINED  (designed, but NOT costed or ranked)" in seq
    assert "R-09" in seq

def test_the_header_does_not_imply_a_winner_when_NONE_can_be_costed(capsys):
    """Corrected 2026-11-08. The header used to say the best sequence below was
    'the only one the tool can stand behind' even when no sequence could be
    costed, and then that none could be DESIGNED, though all were."""
    main(ETHANE)
    seq = capsys.readouterr().out
    seq = seq[seq.index("SEQUENCES"):]
    assert "0 costable" in seq and "5 undetermined" in seq
    assert "None of 5 could be costed" in seq
    assert "only one the tool can stand behind" not in seq
    assert "No sequence can be costed" in seq
    assert "could be designed" not in seq

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
