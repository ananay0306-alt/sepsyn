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
