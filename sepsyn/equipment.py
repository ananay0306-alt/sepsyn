"""Equipment choices as design rules. Heuristic steps 22 to 25.

Kept apart from the screening engine on purpose. A screening rule answers
"can this be separated at all" and feeds overall_verdict, where the worst
verdict wins; an equipment rule answers "which of these two pieces of kit".
Putting them in one table would let a preference for packing outrank a
feasibility finding, and would make every equipment rule a candidate for a
verdict it has no business expressing.

The distinction the statuses carry is the point of the module. `decided` means
a rule fired on evidence, `default` means convention applied because nothing
fired, `open` means sepsyn cannot choose and has said what would settle it.
An unrecorded choice made by convention is what produced the 58 percent
condenser-duty discrepancy in this project's own measurements.
"""
import os
from dataclasses import dataclass

import yaml

from sepsyn.engine import safe_eval

EQUIPMENT_RULES_PATH = os.path.join(os.path.dirname(__file__),
                                    "equipment_rules.yaml")

EQUIPMENT_VISIBLE_FIELDS = frozenset({
    "pressure_Pa",
    "n_supercritical_at_feed",
    "min_alpha",
    "bottoms_T_at_column_P",
    "feed_q",
    "stages",
    "column_diameter_m",
})


@dataclass(frozen=True)
class DesignContext:
    """Everything an equipment rule may see.

    Deliberately small, and deliberately full of Nones before a column has been
    sized. `stages` and `column_diameter_m` do not exist until a design has
    run, and a rule keyed on diameter must decline rather than treat a missing
    diameter as a large one.
    """
    pressure_Pa: float
    n_supercritical_at_feed: int
    min_alpha: float | None = None
    bottoms_T_at_column_P: float | None = None
    feed_q: float | None = None
    stages: float | None = None
    column_diameter_m: float | None = None

    def as_namespace(self) -> dict[str, object]:
        return {name: getattr(self, name) for name in EQUIPMENT_VISIBLE_FIELDS}


@dataclass(frozen=True)
class EquipmentRule:
    id: str
    priority: int
    when: str
    choice: str | None
    because: str
    cite: str = ""
    requires: tuple[str, ...] = ()
    limitations: str = ""


@dataclass(frozen=True)
class EquipmentDecision:
    """One choice, its basis, and what must be written down.

    `status` is not decoration. "total condenser, because a rule proved it" and
    "total condenser, because that is the convention" are different claims, and
    a design that cannot tell them apart cannot be compared with anyone else's.
    """
    step: int
    decision: str
    question: str
    options: tuple[str, ...]
    choice: str | None
    status: str
    """decided | default | open"""
    because: str
    cite: str
    must_record: str
    requires: tuple[str, ...] = ()
    limitations: str = ""
    rule_id: str = ""
    """Empty when the default applied, since no rule fired."""


@dataclass(frozen=True)
class DecisionTable:
    step: int
    decision: str
    question: str
    options: tuple[str, ...]
    must_record: str
    default_choice: str
    default_because: str
    default_cite: str
    rules: tuple[EquipmentRule, ...]


def _squash(text: str) -> str:
    return " ".join((text or "").split())


def load_equipment_rules(path: str | None = None) -> list[DecisionTable]:
    """Load and VALIDATE the equipment table.

    Validated at load time for the same reason the screening rules are: every
    failure mode here is a rule that stops firing with no error. A condition
    naming a property that does not exist, a rule offering an option the
    decision does not list, a duplicate id -- each of those silently removes a
    decision from the design record rather than raising when it is evaluated.
    """
    source = path or EQUIPMENT_RULES_PATH
    with open(source) as fh:
        raw = yaml.safe_load(fh)

    tables: list[DecisionTable] = []
    seen_ids: dict[str, str] = {}
    seen_steps: set[int] = set()

    for entry in raw:
        step = int(entry["step"])
        if step in seen_steps:
            raise ValueError(
                f"duplicate step {step} in {source}. Two tables for one step "
                f"means one of them is silently ignored."
            )
        seen_steps.add(step)

        options = tuple(entry["options"])
        default = entry["default"]
        if default["choice"] not in options:
            raise ValueError(
                f"step {step} defaults to {default['choice']!r}, which is not "
                f"among its options {list(options)}."
            )
        if not _squash(entry.get("must_record", "")):
            raise ValueError(
                f"step {step} records nothing. A choice with no must_record is "
                f"a choice that will be made, used, and then lost -- which is "
                f"the failure these rules exist to prevent."
            )

        rules: list[EquipmentRule] = []
        for r in entry.get("rules", ()) or ():
            rule = EquipmentRule(
                id=r["id"], priority=int(r["priority"]), when=r["when"],
                choice=r["choice"], because=_squash(r["because"]),
                cite=r.get("cite", ""),
                requires=tuple(r.get("requires", ()) or ()),
                limitations=_squash(r.get("limitations", "")),
            )
            if rule.id in seen_ids:
                raise ValueError(
                    f"duplicate equipment rule id {rule.id!r} in {source}: "
                    f"{seen_ids[rule.id]!r} and step {step}. A duplicate id "
                    f"silently shadows a rule."
                )
            seen_ids[rule.id] = rule.because
            if rule.choice is not None and rule.choice not in options:
                raise ValueError(
                    f"equipment rule {rule.id} chooses {rule.choice!r}, which "
                    f"is not among step {step}'s options {list(options)}."
                )
            if rule.choice is None and not rule.requires:
                raise ValueError(
                    f"equipment rule {rule.id} declines to choose but names "
                    f"nothing in requires. Withholding a decision while "
                    f"offering no route to one is worse than saying nothing."
                )
            _validate_condition(rule)
            rules.append(rule)

        tables.append(DecisionTable(
            step=step, decision=entry["decision"], question=entry["question"],
            options=options, must_record=_squash(entry["must_record"]),
            default_choice=default["choice"],
            default_because=_squash(default["because"]),
            default_cite=default.get("cite", ""),
            rules=tuple(sorted(rules, key=lambda r: (r.priority, r.id))),
        ))

    return sorted(tables, key=lambda t: t.step)


def _validate_condition(rule: EquipmentRule) -> None:
    import ast

    try:
        tree = ast.parse(rule.when, mode="eval")
    except SyntaxError as exc:
        raise ValueError(
            f"equipment rule {rule.id} has an unparseable condition "
            f"{rule.when!r}: {exc}. A rule that cannot be parsed never fires."
        ) from exc
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id not in EQUIPMENT_VISIBLE_FIELDS:
            raise ValueError(
                f"equipment rule {rule.id} references unknown property "
                f"{node.id!r} in {rule.when!r}. Valid properties: "
                f"{sorted(EQUIPMENT_VISIBLE_FIELDS)}."
            )


def choose_equipment(context: DesignContext,
                     tables: list[DecisionTable] | None = None
                     ) -> list[EquipmentDecision]:
    """One decision per step, always. Highest-priority firing rule wins.

    Every step yields a decision even when nothing fires, because a step that
    produced no output is a choice left implicit -- and implicit choices are
    what these rules exist to surface.
    """
    namespace = context.as_namespace()
    out: list[EquipmentDecision] = []

    for table in tables if tables is not None else load_equipment_rules():
        fired = next((r for r in table.rules
                      if safe_eval(r.when, namespace)), None)
        if fired is None:
            out.append(EquipmentDecision(
                step=table.step, decision=table.decision,
                question=table.question, options=table.options,
                choice=table.default_choice, status="default",
                because=table.default_because, cite=table.default_cite,
                must_record=table.must_record,
            ))
            continue
        out.append(EquipmentDecision(
            step=table.step, decision=table.decision, question=table.question,
            options=table.options, choice=fired.choice,
            status="open" if fired.choice is None else "decided",
            because=fired.because, cite=fired.cite,
            must_record=table.must_record, requires=fired.requires,
            limitations=fired.limitations, rule_id=fired.id,
        ))
    return out
