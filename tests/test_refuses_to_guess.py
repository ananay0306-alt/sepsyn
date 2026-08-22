"""NEGATIVE ACCEPTANCE TEST.

A property combination that no rule covers must return 'unknown'. Without this,
a future rule edit could quietly make the fallthrough permissive and the tool
would start guessing.
"""
from sepsyn.engine import evaluate, load_rules, overall_verdict
from sepsyn.types import PropertyRecord


def record(**overrides):
    base = dict(
        n_components=2, n_supercritical_at_feed=0, min_alpha=None,
        has_azeotrope=False, alphas=(), feed_phase="solid",
        condensing_T_at_column_P=None, cooling_water_T=313.15,
        light_key_mole_fraction=None, heavy_key_mole_fraction=None,
    )
    base.update(overrides)
    return PropertyRecord(**base)


def test_uncovered_properties_return_unknown():
    verdicts = evaluate(load_rules(), record())
    assert [v.rule_id for v in verdicts if v.fired] == []
    assert overall_verdict(verdicts) == "unknown"


def test_unknown_is_never_silently_treated_as_feasible():
    verdicts = evaluate(load_rules(), record(n_components=1, feed_phase="unknown"))
    assert overall_verdict(verdicts) != "feasible"


def test_every_rule_is_still_reported_even_when_none_fire():
    """'Unknown' must mean 'nine rules were considered and none applied', not
    'nothing happened'. The audit trail is the product."""
    verdicts = evaluate(load_rules(), record())
    assert len(verdicts) == len(load_rules()) > 0
    assert all(v.condition for v in verdicts)
