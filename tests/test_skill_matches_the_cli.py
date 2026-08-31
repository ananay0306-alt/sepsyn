"""The skill is a door onto the CLI, so it must not drift from it.

A skill that documents a flag the parser does not accept fails at the moment
someone relies on it, in a session, with no test to catch it. Cheap to pin
here.
"""
import re
from pathlib import Path

import pytest

from sepsyn.cli import main

SKILL = Path(__file__).resolve().parents[1] / "skill" / "SKILL.md"


def documented_flags() -> set[str]:
    return set(re.findall(r"(?<![\w-])--[a-z][a-z-]+", SKILL.read_text()))


def test_the_skill_exists():
    assert SKILL.is_file()


def test_every_flag_the_skill_documents_is_accepted_by_the_parser(capsys):
    """Asserted against argparse's own help text, not against a list copied
    out of it -- a copied list drifts in exactly the same way the skill would.

    Invoking each flag with --help does NOT work: a flag that takes a value
    swallows --help as that value and argparse exits 2, which reads as "unknown
    flag" for every valued flag in the file.
    """
    with pytest.raises(SystemExit):
        main(["--help"])
    help_text = capsys.readouterr().out
    for flag in sorted(documented_flags()):
        assert flag in help_text, f"{flag} is documented but not a sepsyn flag"


def test_the_skill_documents_the_flags_that_change_the_ANSWER():
    """Not every flag needs documenting, but these do: omitting the keys
    silences four rules, and the three specification flags are the ones whose
    bases are easy to confuse."""
    documented = documented_flags()
    for flag in ("--light-key", "--heavy-key", "--feed-q",
                 "--distillate-purity", "--lk-recovery", "--explain"):
        assert flag in documented, f"{flag} changes the answer and is undocumented"
