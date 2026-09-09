"""Component tags. Corrosivity is in no property database, so it is supplied.

CRC, DIPPR and IUPAC give boiling points and critical constants. None of them
says whether a component is corrosive, and structure does not settle it either:
corrosivity depends on concentration, temperature and the material of
construction. So the tool is told, or it does not know.
"""
import pytest

from sepsyn.sequencing.tags import KNOWN_TAGS, UnknownTag, parse_tags

NAMES = ("Propane", "HCl", "Water")


def test_a_single_tag_is_parsed():
    assert parse_tags(["HCl:corrosive"], NAMES) == {"HCl": frozenset({"corrosive"})}


def test_several_tags_on_one_component():
    tags = parse_tags(["HCl:corrosive", "HCl:hazardous"], NAMES)
    assert tags["HCl"] == frozenset({"corrosive", "hazardous"})


def test_comma_separated_tags_on_one_component():
    tags = parse_tags(["HCl:corrosive,hazardous"], NAMES)
    assert tags["HCl"] == frozenset({"corrosive", "hazardous"})


def test_untagged_components_are_absent_rather_than_marked_benign():
    """Absent, not tagged 'safe'. The tool has not been told propane is
    harmless; it has simply not been told anything."""
    tags = parse_tags(["HCl:corrosive"], NAMES)
    assert "Propane" not in tags


def test_an_unknown_tag_is_refused_with_the_vocabulary():
    """A typo that parses is a tag that silently never matches a rule, which is
    the failure mode this project exists to catch."""
    with pytest.raises(UnknownTag, match="corrossive"):
        parse_tags(["HCl:corrossive"], NAMES)


def test_the_error_names_what_was_allowed():
    with pytest.raises(UnknownTag) as exc:
        parse_tags(["HCl:sticky"], NAMES)
    for known in KNOWN_TAGS:
        assert known in str(exc.value)


def test_a_tag_on_an_absent_component_is_refused():
    with pytest.raises(UnknownTag, match="Benzene"):
        parse_tags(["Benzene:corrosive"], NAMES)


def test_a_malformed_spec_is_refused():
    with pytest.raises(UnknownTag, match="HCl-corrosive"):
        parse_tags(["HCl-corrosive"], NAMES)


def test_no_specs_gives_no_tags():
    assert parse_tags([], NAMES) == {}
