"""R-03 must fire on the pair the column is SEPARATING, not on any pair present.

Found while building multicomponent sequencing. A column splitting acetone from
ethanol, with water present and leaving in the bottoms alongside the ethanol,
was eliminated by R-03 because ethanol and water form an azeotrope. That pair
is not being separated by that column: both components leave together, and the
column is perfectly buildable.

Left uncorrected, every sequence for such a feed is eliminated at its first
column and the tool reports that no separation is possible, when in truth the
acetone split is clean and only the ethanol/water split is blocked.

This mirrors find_liquid_split, which is already scoped to the key pair for
exactly the same reason. The two checks were inconsistent.
"""
from sepsyn.engine import evaluate, load_rules, overall_verdict
from sepsyn.properties import build_property_record, resolve
from sepsyn.types import Component, Feed


def ternary(T_K=330.0):
    return Feed(
        components=tuple(Component(n, resolve(n), f) for n, f in
                         [("Acetone", 30.0), ("Ethanol", 40.0), ("Water", 30.0)]),
        T_K=T_K, P_Pa=101325.0,
    )


def test_a_NON_KEY_azeotrope_does_not_flag_the_column():
    """Acetone/ethanol are the keys and are not azeotropic. Ethanol and water
    are, but they leave together in the bottoms, so this column does not
    attempt that separation."""
    record = build_property_record(ternary(), light_key="Acetone",
                                   heavy_key="Ethanol")
    assert record.has_azeotrope is False
    fired = {v.rule_id for v in evaluate(load_rules(), record) if v.fired}
    assert "R-03" not in fired


def test_the_KEY_pair_azeotrope_still_flags_the_column():
    """The same feed, with the azeotropic pair as the keys. This column IS
    attempting that separation and cannot perform it."""
    record = build_property_record(ternary(), light_key="Ethanol",
                                   heavy_key="Water")
    assert record.has_azeotrope is True
    verdicts = evaluate(load_rules(), record)
    assert "R-03" in {v.rule_id for v in verdicts if v.fired}
    assert overall_verdict(verdicts) == "infeasible"


def test_without_keys_the_screen_stays_BROAD():
    """Before keys are named the tool does not know which separation is being
    asked about, so it screens every pair. Same precedent as bottoms_T and the
    liquid-liquid check."""
    assert build_property_record(ternary()).has_azeotrope is True


def test_the_azeotrope_and_liquid_liquid_checks_agree_on_scope():
    """They were inconsistent: one scoped to the keys, the other not. Pinned so
    they cannot drift apart again."""
    keyed = build_property_record(ternary(), light_key="Acetone",
                                  heavy_key="Ethanol")
    broad = build_property_record(ternary())
    assert keyed.has_azeotrope is False and keyed.has_two_liquid_phases is False
    assert broad.has_azeotrope is True
