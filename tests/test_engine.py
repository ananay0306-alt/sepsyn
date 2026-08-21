import pytest
from sepsyn.types import PropertyRecord, RULE_VISIBLE_FIELDS
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
    rules = load_rules()
    assert len(rules) == 9  # otherwise this test passes vacuously on []
    for r in rules:
        result = safe_eval(r.when, ns)
        assert isinstance(result, bool)


def test_duplicate_rule_id_is_rejected_at_load(tmp_path):
    """A duplicate id silently shadows a rule, so it must fail loudly."""
    p = tmp_path / "dup.yaml"
    p.write_text(
        "- {id: R-01, name: a, priority: 1, when: 'min_alpha > 1',\n"
        "   verdict: feasible, technologies: [distillation], because: x}\n"
        "- {id: R-01, name: b, priority: 2, when: 'min_alpha > 2',\n"
        "   verdict: feasible, technologies: [distillation], because: y}\n"
    )
    with pytest.raises(ValueError, match="duplicate rule id"):
        load_rules(str(p))


def test_unparseable_condition_is_rejected_at_load(tmp_path):
    """Today a typo'd condition only raises when that rule is first evaluated,
    which may be never -- so the rule silently stops firing."""
    p = tmp_path / "bad.yaml"
    p.write_text(
        "- {id: R-01, name: a, priority: 1, when: 'min_alpha <',\n"
        "   verdict: feasible, technologies: [distillation], because: x}\n"
    )
    with pytest.raises(ValueError, match="unparseable condition"):
        load_rules(str(p))


def test_unknown_property_in_condition_is_rejected_at_load(tmp_path):
    """A misspelled property name (e.g. 'min_alpah') would otherwise raise
    inside safe_eval at evaluation time -- and evaluate() has no per-rule
    try/except, so ONE typo would abort the whole evaluation loop and
    return zero verdicts for all nine rules, not just the bad one."""
    p = tmp_path / "typo.yaml"
    p.write_text(
        "- {id: R-01, name: a, priority: 1, when: 'min_alpah > 1',\n"
        "   verdict: feasible, technologies: [distillation], because: x}\n"
    )
    with pytest.raises(ValueError, match="unknown property"):
        load_rules(str(p))


def test_invalid_verdict_string_is_rejected_at_load(tmp_path):
    """A verdict like 'Feasible' (wrong case) loads fine and fires fine, then
    crashes _VERDICT_RANK inside overall_verdict -- after the fact, far from
    the typo that caused it."""
    p = tmp_path / "badverdict.yaml"
    p.write_text(
        "- {id: R-01, name: a, priority: 1, when: 'min_alpha > 1',\n"
        "   verdict: Feasible, technologies: [distillation], because: x}\n"
    )
    with pytest.raises(ValueError, match="must be one of"):
        load_rules(str(p))


def test_shipped_rules_still_load_all_nine():
    """Guard against the new validators being too strict and rejecting a
    legitimate rule in the real rules.yaml."""
    rules = load_rules()
    assert len(rules) == 9


def test_as_namespace_and_validator_share_one_source_of_truth():
    """RULE_VISIBLE_FIELDS is the single source of truth for both the
    namespace as_namespace() builds and the set load_rules() validates
    conditions against. If these ever drift, a valid rule starts failing
    validation, or an invalid one slips through."""
    ns = record().as_namespace()
    assert set(ns.keys()) == RULE_VISIBLE_FIELDS
    for name in RULE_VISIBLE_FIELDS:
        assert name in ns
    for name in ns:
        assert name in RULE_VISIBLE_FIELDS
