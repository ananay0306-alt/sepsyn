"""A misspelled chemical must produce a message, not a stack trace.

properties.resolve() already builds near-match suggestions -- that machinery
cost three fix rounds in Task 2 -- but they were reaching the user wrapped in a
traceback, which is the one presentation that makes them look like a crash
rather than an answer.
"""
import pytest

from sepsyn.cli import main


def test_a_misspelled_chemical_is_reported_as_a_message(capsys):
    code = main(["--feed", "Methnol:100", "--T", "330"])
    err = capsys.readouterr().err

    assert code != 0, "a failed run must not report success"
    assert "Methnol" in err
    assert "methanol" in err          # the suggestion survives to the user
    assert "Traceback" not in err
    assert "UnknownChemical" not in err, "the exception class name is noise"


def test_the_traceback_really_is_gone(capsys):
    """Guard the presentation, not just the exit code. A raw traceback would
    still 'fail' loudly, so exit code alone does not pin this."""
    main(["--feed", "Zzzqqqxyw:100"])
    captured = capsys.readouterr()
    assert "Traceback (most recent call last)" not in captured.err + captured.out
    assert "Zzzqqqxyw" in captured.err


def test_a_malformed_feed_string_is_also_a_message(capsys):
    """'Methanol' with no colon is a typo, not a bug to crash on."""
    code = main(["--feed", "Methanol"])
    err = capsys.readouterr().err
    assert code != 0
    assert "Traceback" not in err
    assert "Methanol" in err


def test_a_good_feed_still_returns_zero_and_prints_nothing_to_stderr(capsys):
    code = main(["--feed", "Methanol:100,Water:80", "--T", "330"])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.err == ""
    assert "VERDICT" in captured.out


# --- keys must reach the property record ------------------------------------
#
# screen() built the record with no keys at all, so light_key_mole_fraction and
# heavy_key_mole_fraction were ALWAYS None in the CLI. Every rule referencing
# them therefore could not fire, whatever the user typed. The same defect would
# have made R-10 and R-11 dead on arrival.


def test_screen_passes_the_keys_into_the_record():
    from sepsyn.cli import parse_feed, screen
    feed = parse_feed("Methanol:100,Glycerol:50", T_K=340.0, P_Pa=101325.0)
    record, _, _ = screen(feed, light_key="Methanol", heavy_key="Glycerol")
    assert record.light_key_mole_fraction is not None
    assert record.heavy_key_mole_fraction is not None
    assert record.bottoms_T_at_column_P is not None


def test_screen_without_keys_still_works_and_leaves_them_none():
    from sepsyn.cli import parse_feed, screen
    feed = parse_feed("Methanol:100,Glycerol:50", T_K=340.0, P_Pa=101325.0)
    record, _, _ = screen(feed)
    assert record.light_key_mole_fraction is None
    assert record.bottoms_T_at_column_P is None


def test_R10_and_R11_fire_end_to_end_when_the_bottoms_is_hot(capsys):
    """Glycerol boils at 562 K, far above 160 C steam. Both thermal rules must
    reach the printed report, not merely evaluate true in a unit test."""
    from sepsyn.cli import main
    code = main(["--feed", "Methanol:100,Glycerol:50", "--T", "340",
                 "--light-key", "Methanol", "--heavy-key", "Glycerol"])
    assert code == 0
    out = capsys.readouterr().out
    assert "R-10" in out
    assert "R-11" in out
    assert "REQUIRES" in out
