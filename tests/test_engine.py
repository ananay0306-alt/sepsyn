import pytest
from sepsyn.types import PropertyRecord
from sepsyn.engine import safe_eval, load_rules


def record(**overrides):
    base = dict(
        n_components=2, n_supercritical_at_feed=0, min_alpha=2.0,
        has_azeotrope=False, alphas=(), feed_phase="liquid",
        condensing_T_at_column_P=350.0, cooling_water_T=313.15,
        light_key_mole_fraction=0.5, heavy_key_mole_fraction=0.5,
    )
    base.update(overrides)
    return PropertyRecord(**base)


def test_safe_eval_handles_comparisons_and_boolean_logic():
    ns = {"a": 2.0, "b": 5, "flag": True}
    assert safe_eval("a < b", ns) is True
    assert safe_eval("a > b", ns) is False
    assert safe_eval("a < b and flag", ns) is True
    assert safe_eval("a == 2.0", ns) is True


def test_safe_eval_treats_none_comparison_as_false():
    """min_alpha is None when there is no VLE. Rules must not explode."""
    assert safe_eval("min_alpha < 1.05", {"min_alpha": None}) is False


def test_safe_eval_refuses_function_calls():
    with pytest.raises(ValueError, match="not permitted"):
        safe_eval("__import__('os').system('echo hi')", {})


def test_safe_eval_refuses_unknown_names():
    with pytest.raises(ValueError, match="unknown name"):
        safe_eval("mystery_property > 1", {"a": 1})


def test_rules_load_and_are_well_formed():
    rules = load_rules()
    assert len(rules) == 9
    assert len({r.id for r in rules}) == 9          # ids are unique
    # load_rules sorts by PRIORITY, not by id -- R-04 (supercritical) must be
    # evaluated before R-01 (distillation viable)
    priorities = [r.priority for r in rules]
    assert priorities == sorted(priorities)
    for r in rules:
        assert r.verdict in {"feasible", "infeasible", "caution"}
        assert r.because.strip()
        assert r.when.strip()


def test_every_rule_condition_evaluates_against_a_record():
    """A rule whose condition cannot be evaluated is a broken rule."""
    ns = record().as_namespace()
    for r in load_rules():
        result = safe_eval(r.when, ns)
        assert isinstance(result, bool)
