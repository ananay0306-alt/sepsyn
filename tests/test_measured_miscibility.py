"""Measured miscibility overrides the activity model's false gap.

Dortmund UNIFAC predicts a miscibility gap for water/glycerol across 10 of 49
compositions with dx up to 0.493, inside the range of real splits on every
metric (see lle.py). No threshold separates it, and swapping the model does
not help: original UNIFAC, measured 11-07 on a fourteen-pair panel, found no
split at all, not even water/benzene.

Water and glycerol are miscible in all proportions, which is handbook data.
Data beats a model, so the measured pair is not scanned, and the report says
so instead of hiding the override.
"""
from sepsyn.cli import main
from sepsyn.engine import evaluate, load_rules
from sepsyn.lle import find_liquid_split, measured_miscible_pairs
from sepsyn.properties import build_property_record, resolve
from sepsyn.types import Component, Feed

ATM = 101325.0


def feed_of(*pairs, T_K=330.0):
    return Feed(components=tuple(Component(n, resolve(n), f) for n, f in pairs),
                T_K=T_K, P_Pa=ATM)


MILESTONE = feed_of(("Methanol", 100.0), ("Water", 80.0), ("Glycerol", 25.0))


def test_water_glycerol_no_longer_reports_a_split():
    assert find_liquid_split(["Water", "Glycerol"], ATM) is None


def test_the_override_is_by_CAS_so_a_synonym_cannot_dodge_it():
    assert find_liquid_split(["H2O", "glycerine"], ATM) is None


def test_real_splits_are_untouched():
    assert find_liquid_split(["Water", "Butanol"], ATM) is not None
    assert find_liquid_split(["Water", "Benzene"], ATM) is not None


def test_a_real_split_beside_the_measured_pair_is_still_found():
    """The override skips ONE pair, not the feed."""
    found = find_liquid_split(["Water", "Glycerol", "Benzene"], ATM)
    assert found is not None
    assert set(found.components) == {"Water", "Benzene"}


def test_the_override_names_its_source():
    (pair,) = measured_miscible_pairs(["Water", "Glycerol"])
    assert set(pair.components) == {"Water", "Glycerol"}
    assert "all proportions" in pair.source
    assert "CRC" in pair.source


def test_the_milestone_feed_screens_without_R12_even_without_keys():
    """Before, the unkeyed screen of this feed fired R-12 on the false gap."""
    record = build_property_record(MILESTONE)
    assert record.has_two_liquid_phases is False
    fired = {v.rule_id for v in evaluate(load_rules(), record) if v.fired}
    assert "R-12" not in fired


def test_the_record_carries_the_override():
    record = build_property_record(MILESTONE)
    assert any(set(p.components) == {"Water", "Glycerol"}
               for p in record.measured_miscible)


def test_the_report_states_the_override(capsys):
    main(["--feed", "Methanol:100,Water:80,Glycerol:25", "--T", "330"])
    out = capsys.readouterr().out
    assert "MEASURED" in out and "Water/Glycerol" in out
