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
    assert len(rules) == 12
    assert len({r.id for r in rules}) == 12         # ids are unique
    # load_rules sorts by PRIORITY, not by id -- R-04 (supercritical) must be
    # evaluated before R-01 (distillation viable)
    priorities = [r.priority for r in rules]
    assert priorities == sorted(priorities)
    for r in rules:
        assert r.verdict in {"feasible", "infeasible", "caution", "undetermined"}
        assert r.because.strip()
        assert r.when.strip()


def test_every_rule_condition_evaluates_against_a_record():
    """A rule whose condition cannot be evaluated is a broken rule."""
    ns = record().as_namespace()
    rules = load_rules()
    assert len(rules) == 12  # otherwise this test passes vacuously on []
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


def test_shipped_rules_all_load():
    """Guard against the new validators being too strict and rejecting a
    legitimate rule in the real rules.yaml."""
    rules = load_rules()
    assert len(rules) == 12


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


# --- requires_calculation / limitations schema -------------------------------
#
# A rule may fire on properties it HAS while declaring a calculation it still
# NEEDS. Without this, every rule is terminal: condition -> verdict, with no way
# to express "this option deserves consideration, go compute X before deciding".


def test_rule_carries_required_calculations_and_limitations(tmp_path):
    p = tmp_path / "req.yaml"
    p.write_text(
        "- id: R-99\n"
        "  name: a\n"
        "  priority: 1\n"
        "  when: \"min_alpha > 1\"\n"
        "  verdict: feasible\n"
        "  technologies: [distillation]\n"
        "  because: x\n"
        "  requires: ['vapour fraction from a flash at cooling-water T']\n"
        "  limitations: 'fails when beta approaches 1'\n"
    )
    rule = load_rules(str(p))[0]
    assert rule.requires == ("vapour fraction from a flash at cooling-water T",)
    assert rule.limitations == "fails when beta approaches 1"


def test_rule_without_the_new_fields_defaults_them_empty(tmp_path):
    """The fields are additive -- every rule written before them must still load."""
    p = tmp_path / "old.yaml"
    p.write_text(
        "- {id: R-01, name: a, priority: 1, when: 'min_alpha > 1',\n"
        "   verdict: feasible, technologies: [distillation], because: x}\n"
    )
    rule = load_rules(str(p))[0]
    assert rule.requires == ()
    assert rule.limitations == ""


# --- the undetermined verdict ------------------------------------------------
#
# Distinct from "unknown". `unknown` means NO rule fired -- the tool has nothing
# to say. `undetermined` means a rule DID fire and deliberately declined to
# conclude, because its answer depends on a calculation not yet performed.
# Collapsing the two would report "no applicable rule" for a mixture the tool
# actually has a rule about.


def verdict(v, fired=True, rule_id="R-XX"):
    from sepsyn.engine import Verdict
    return Verdict(rule_id=rule_id, rule_name="n", condition="c", values={},
                   verdict=v, technologies=(), because="b", fired=fired)


def test_undetermined_outranks_feasible():
    """Reporting FEASIBLE while a rule is still awaiting its calculation would
    assert exactly the confidence the field exists to withhold."""
    from sepsyn.engine import overall_verdict
    assert overall_verdict([verdict("feasible"), verdict("undetermined")]) == "undetermined"


def test_undetermined_outranks_caution():
    from sepsyn.engine import overall_verdict
    assert overall_verdict([verdict("caution"), verdict("undetermined")]) == "undetermined"


def test_infeasible_still_beats_undetermined():
    """A hard physical block is knowledge; undetermined is the absence of it.
    Knowledge of a blocker wins -- no calculation can unblock a mixture with no
    liquid phase."""
    from sepsyn.engine import overall_verdict
    assert overall_verdict([verdict("undetermined"), verdict("infeasible")]) == "infeasible"


def test_unfired_undetermined_rule_does_not_change_the_verdict():
    from sepsyn.engine import overall_verdict
    assert overall_verdict([verdict("feasible"),
                            verdict("undetermined", fired=False)]) == "feasible"


def test_undetermined_is_accepted_as_a_rule_verdict(tmp_path):
    p = tmp_path / "u.yaml"
    p.write_text(
        "- {id: R-01, name: a, priority: 1, when: 'min_alpha > 1',\n"
        "   verdict: undetermined, technologies: [flash], because: x,\n"
        "   requires: ['a flash at cooling-water temperature']}\n"
    )
    assert load_rules(str(p))[0].verdict == "undetermined"


def test_undetermined_rule_without_requires_is_rejected_at_load(tmp_path):
    """An undetermined verdict that names no calculation is a dead end: it
    withholds an answer and gives the reader no way to obtain one. The whole
    point of the state is to convert a heuristic into a calculation request, so
    a rule that skips the request is worse than no rule at all -- it suppresses
    a verdict and offers nothing in exchange."""
    p = tmp_path / "deadend.yaml"
    p.write_text(
        "- {id: R-01, name: a, priority: 1, when: 'min_alpha > 1',\n"
        "   verdict: undetermined, technologies: [flash], because: x}\n"
    )
    with pytest.raises(ValueError, match="must declare"):
        load_rules(str(p))


def test_requires_entry_that_is_blank_is_rejected_at_load(tmp_path):
    """An empty string satisfies "declared a calculation" while naming none."""
    p = tmp_path / "blank.yaml"
    p.write_text(
        "- {id: R-01, name: a, priority: 1, when: 'min_alpha > 1',\n"
        "   verdict: undetermined, technologies: [flash], because: x,\n"
        "   requires: ['  ']}\n"
    )
    with pytest.raises(ValueError, match="empty"):
        load_rules(str(p))


def test_evaluate_carries_requires_and_limitations_onto_the_verdict(tmp_path):
    """A calculation named on the Rule but dropped by evaluate() can never
    reach the report, which is the only place it does any good."""
    from sepsyn.engine import evaluate
    p = tmp_path / "carry.yaml"
    p.write_text(
        "- {id: R-01, name: a, priority: 1, when: 'min_alpha > 1',\n"
        "   verdict: undetermined, technologies: [flash], because: x,\n"
        "   requires: ['a flash at cooling-water temperature'],\n"
        "   limitations: 'useless when beta approaches 1'}\n"
    )
    v = evaluate(load_rules(str(p)), record())[0]
    assert v.fired is True
    assert v.requires == ("a flash at cooling-water temperature",)
    assert v.limitations == "useless when beta approaches 1"


# --- the shipped rules use the new schema ------------------------------------


def test_R09_does_not_assert_refrigeration_before_checking_pressure():
    """R-09 fired on `condensing_T_at_column_P < cooling_water_T` and concluded
    "refrigeration is required". That conclusion is premature: raising the
    column pressure raises the condensing temperature, and design.py already
    does exactly that before giving up. The rule was asserting a design outcome
    it had not computed -- so it must now declare the calculation instead."""
    r = {x.id: x for x in load_rules()}["R-09"]
    assert r.verdict == "undetermined"
    assert r.requires, "R-09 must name the pressure check it depends on"
    assert any("pressure" in item.lower() for item in r.requires)
    assert r.limitations.strip()


def test_R05_declares_the_calculation_that_picks_its_technology():
    """R-05 offers both `flash` and `cryogenic_partial_condensation`. Which one
    applies depends on how much actually condenses under ordinary cooling --
    a number the rule never had. Its verdict stands; its technology choice does
    not, until that fraction is computed."""
    r = {x.id: x for x in load_rules()}["R-05"]
    assert r.requires
    assert any("vapour fraction" in item.lower() for item in r.requires)


# --- reboiler-side pressure rule (step 11) and thermal limit (step 7) --------
#
# R-09 covers only the COLD end: can the overhead condense against cooling
# water. A bottoms that boils ABOVE the available steam is just as much a
# blocker -- it forces a fired heater -- and nothing tested for it.


def test_record_exposes_the_bottoms_temperature_and_steam_temperature():
    ns = record().as_namespace()
    assert "bottoms_T_at_column_P" in ns
    assert "steam_T" in ns


def test_R10_fires_when_the_bottoms_boils_above_the_available_steam():
    from sepsyn.engine import evaluate
    rules = load_rules()
    hot = record(bottoms_T_at_column_P=460.0, steam_T=433.15)
    fired = {v.rule_id for v in evaluate(rules, hot) if v.fired}
    assert "R-10" in fired


def test_R10_does_not_fire_when_steam_can_drive_the_reboiler():
    from sepsyn.engine import evaluate
    rules = load_rules()
    ok = record(bottoms_T_at_column_P=373.0, steam_T=433.15)
    fired = {v.rule_id for v in evaluate(rules, ok) if v.fired}
    assert "R-10" not in fired


def test_R10_respects_the_five_degree_approach():
    """430 K against 433.15 K steam is only a 3.15 K driving force, which is
    below the 5 K allowance, so the rule must still fire."""
    from sepsyn.engine import evaluate
    rules = load_rules()
    marginal = record(bottoms_T_at_column_P=430.0, steam_T=433.15)
    fired = {v.rule_id for v in evaluate(rules, marginal) if v.fired}
    assert "R-10" in fired


def test_R11_asks_for_the_decomposition_temperature_on_a_hot_column():
    """Decomposition temperature is not in the property database. Rather than
    guess it or ignore the risk, the rule declares the calculation it needs."""
    from sepsyn.engine import evaluate
    rules = load_rules()
    hot = record(bottoms_T_at_column_P=500.0)
    v = [x for x in evaluate(rules, hot) if x.rule_id == "R-11"][0]
    assert v.fired
    assert v.verdict == "undetermined"
    assert any("decomposition" in r.lower() for r in v.requires)


def test_R11_stays_quiet_on_an_ordinary_column():
    from sepsyn.engine import evaluate
    rules = load_rules()
    mild = record(bottoms_T_at_column_P=373.0)
    fired = {v.rule_id for v in evaluate(rules, mild) if v.fired}
    assert "R-11" not in fired


# --- arithmetic in rule conditions -------------------------------------------
#
# A threshold expressed against another property ("5 K below the steam") is a
# judgment, and judgments belong in rules.yaml. Without arithmetic the 5 would
# have to be baked into Python, which breaks the promise that the rule file
# alone changes the tool's judgment.


def test_safe_eval_allows_arithmetic_against_another_property():
    assert safe_eval("a > b - 5", {"a": 10.0, "b": 12.0}) is True
    assert safe_eval("a > b - 5", {"a": 6.0, "b": 12.0}) is False


def test_safe_eval_supports_the_four_basic_operators():
    ns = {"a": 10.0}
    assert safe_eval("a + 1 > 10", ns) is True
    assert safe_eval("a - 1 > 10", ns) is False
    assert safe_eval("a * 2 > 19", ns) is True
    assert safe_eval("a / 2 > 4", ns) is True


def test_safe_eval_still_refuses_exponentiation():
    """Allowing arithmetic must not open a cheap way to hang the evaluator:
    9**9**9 is a one-line denial of service."""
    with pytest.raises(ValueError, match="not permitted"):
        safe_eval("a ** 9 > 1", {"a": 9.0})


def test_arithmetic_on_a_missing_property_is_still_false():
    """The None guard must survive the operand being inside an expression."""
    assert safe_eval("a > b - 5", {"a": 10.0, "b": None}) is False
    assert safe_eval("a - 5 > b", {"a": None, "b": 1.0}) is False
