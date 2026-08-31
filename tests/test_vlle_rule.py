"""Step 6 reaching the rule table, not just the physics module."""
from sepsyn.engine import evaluate, load_rules, overall_verdict
from sepsyn.properties import build_property_record, resolve
from sepsyn.types import Component, Feed

ATM = 101325.0


def feed_of(*pairs, T_K=298.15):
    return Feed(components=tuple(Component(n, resolve(n), f) for n, f in pairs),
                T_K=T_K, P_Pa=ATM)


def fired_ids(feed, **keys):
    record = build_property_record(feed, **keys)
    return record, {v.rule_id for v in evaluate(load_rules(), record) if v.fired}


def test_a_splitting_mixture_is_recorded_as_splitting():
    record, ids = fired_ids(feed_of(("Water", 50.0), ("Butanol", 50.0)))
    assert record.has_two_liquid_phases is True
    assert "R-12" in ids


def test_a_miscible_mixture_is_recorded_as_not_splitting():
    record, ids = fired_ids(feed_of(("Benzene", 60.0), ("Toluene", 40.0)))
    assert record.has_two_liquid_phases is False
    assert "R-12" not in ids


def test_the_split_is_a_CAUTION_and_names_what_would_settle_it():
    """Caution, not undetermined, and the reason is measured rather than
    stylistic.

    Undetermined blocks --design. The detector's activity-coefficient model
    predicts a false miscibility gap for water/glycerol (see lle.py for the
    eight-pair panel), and blocking design on a false alarm at that rate is
    worse calibrated than flagging it and letting the reader dismiss it -- which
    they can, because the rule names the pair and the limitation.

    Not infeasible either: a heterogeneous split is separable, often very
    easily, with a decanter. What is wrong is sepsyn's MODEL, not the
    separation.
    """
    record = build_property_record(feed_of(("Water", 50.0), ("Butanol", 50.0)))
    verdicts = evaluate(load_rules(), record)
    r12 = next(v for v in verdicts if v.rule_id == "R-12")
    assert r12.verdict == "caution"
    assert r12.requires, "the rule must still name the calculation it needs"
    assert "glycerol" in r12.limitations.lower(), (
        "the known false positive must travel with the rule, not sit only in a "
        "source comment where a reader of the report will never see it")


def test_the_check_follows_the_KEYS_when_they_are_known():
    """The milestone feed is the case. Its non-key pair water/glycerol trips
    UNIFAC's false miscibility gap; its actual key pair methanol/water does not.

    Once the keys are named, R-12's claim is about the model underneath THIS
    separation, and that model is the key pair's. The source heuristics are
    explicitly binary and put non-key handling outside their scope.
    """
    ternary = feed_of(("Methanol", 100.0), ("Water", 80.0), ("Glycerol", 25.0),
                      T_K=330.0)
    keyed = build_property_record(ternary, light_key="Methanol",
                                  heavy_key="Water")
    assert keyed.has_two_liquid_phases is False


def test_without_keys_the_screen_is_BROADER_and_flags_the_non_key_pair():
    """Pinned deliberately, including the false positive it contains.

    Before keys are named the tool does not know which separation is being
    asked about, so it screens every pair -- and on this feed that surfaces the
    water/glycerol false positive. Recorded here so the behaviour is a known
    property of the tool rather than a surprise in someone's report.
    """
    ternary = feed_of(("Methanol", 100.0), ("Water", 80.0), ("Glycerol", 25.0),
                      T_K=330.0)
    assert build_property_record(ternary).has_two_liquid_phases is True


def test_not_checked_is_not_the_same_as_checked_and_found_none():
    """Every component supercritical: there is no liquid, so the LLE search
    never ran. None, not False -- False is the claim that it was checked."""
    record = build_property_record(
        feed_of(("Hydrogen", 60.0), ("Methane", 40.0)))
    assert record.has_two_liquid_phases is None
