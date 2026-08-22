import pytest
from sepsyn.types import PropertyRecord
from sepsyn.engine import load_rules, evaluate, overall_verdict


def record(**overrides):
    base = dict(
        n_components=2, n_supercritical_at_feed=0, min_alpha=2.0,
        has_azeotrope=False, alphas=(), feed_phase="liquid",
        condensing_T_at_column_P=350.0, cooling_water_T=313.15,
        light_key_mole_fraction=0.5, heavy_key_mole_fraction=0.5,
    )
    base.update(overrides)
    return PropertyRecord(**base)


def fired_ids(verdicts):
    return [v.rule_id for v in verdicts if v.fired]


def test_supercritical_feed_fires_only_R04():
    rec = record(n_supercritical_at_feed=2, min_alpha=None,
                 feed_phase="vapor", condensing_T_at_column_P=None,
                 light_key_mole_fraction=None, heavy_key_mole_fraction=None)
    v = evaluate(load_rules(), rec)
    assert fired_ids(v) == ["R-04"]
    assert overall_verdict(v) == "infeasible"


def test_ordinary_mixture_fires_R01_and_is_feasible():
    v = evaluate(load_rules(), record())
    assert "R-01" in fired_ids(v)
    assert overall_verdict(v) == "feasible"


def test_all_matching_rules_are_reported_not_just_the_first():
    """A mixture can be BOTH low-alpha and azeotropic. Report both."""
    rec = record(min_alpha=1.0, has_azeotrope=True)
    ids = fired_ids(evaluate(load_rules(), rec))
    assert "R-02" in ids
    assert "R-03" in ids


def test_every_rule_appears_in_the_result_even_when_not_fired():
    """Auditability: you must be able to see what was considered."""
    v = evaluate(load_rules(), record())
    assert len(v) == len(load_rules())
    assert any(not x.fired for x in v)


def test_infeasible_beats_caution_beats_feasible():
    rec = record(min_alpha=1.0, condensing_T_at_column_P=200.0)
    v = evaluate(load_rules(), rec)
    assert overall_verdict(v) == "infeasible"


def test_no_rule_fires_returns_unknown_not_a_guess():
    """The tool must never fall through to 'probably distillation'."""
    rec = record(n_components=2, n_supercritical_at_feed=0, min_alpha=None,
                 has_azeotrope=False, feed_phase="solid",
                 condensing_T_at_column_P=None,
                 light_key_mole_fraction=None, heavy_key_mole_fraction=None)
    v = evaluate(load_rules(), rec)
    assert fired_ids(v) == []
    assert overall_verdict(v) == "unknown"


def test_verdict_carries_the_values_that_fired_it():
    rec = record(n_supercritical_at_feed=2, min_alpha=None,
                 feed_phase="vapor", condensing_T_at_column_P=None,
                 light_key_mole_fraction=None, heavy_key_mole_fraction=None)
    v = [x for x in evaluate(load_rules(), rec) if x.rule_id == "R-04"][0]
    assert v.values["n_supercritical_at_feed"] == 2
    assert v.values["n_components"] == 2
    assert "critical temperature" in v.because
