"""Rule loading and evaluation.

Conditions are parsed with `ast` and evaluated against a restricted namespace
containing only the property record. No builtins, no imports, no calls -- a
rule file edited by a student cannot execute code.
"""
import ast
import os
from dataclasses import dataclass
from typing import Any

import yaml

from sepsyn.types import PropertyRecord, RULE_VISIBLE_FIELDS

RULES_PATH = os.path.join(os.path.dirname(__file__), "rules.yaml")

_ALLOWED_NODES = (
    ast.Expression, ast.BoolOp, ast.UnaryOp, ast.Compare, ast.Name, ast.Load,
    ast.Constant, ast.And, ast.Or, ast.Not, ast.Eq, ast.NotEq, ast.Lt,
    ast.LtE, ast.Gt, ast.GtE, ast.Is, ast.IsNot,
)


@dataclass(frozen=True)
class Rule:
    id: str
    name: str
    priority: int
    when: str
    verdict: str
    technologies: tuple[str, ...]
    because: str
    cite: str = ""
    requires: tuple[str, ...] = ()
    """Calculations that must be performed before this rule's verdict can be
    acted on. A rule may fire on the properties it HAS while naming the ones it
    still NEEDS -- without this field every rule is terminal, and a heuristic
    that merely nominates a candidate becomes indistinguishable from one that
    settles the question."""
    limitations: str = ""
    """Competing effects a reader must check before trusting the verdict."""


@dataclass(frozen=True)
class Verdict:
    rule_id: str
    rule_name: str
    condition: str
    values: dict[str, Any]
    verdict: str
    technologies: tuple[str, ...]
    because: str
    fired: bool
    requires: tuple[str, ...] = ()
    limitations: str = ""


def safe_eval(expr: str, namespace: dict[str, Any]) -> bool:
    """Evaluate a rule condition. Comparisons involving None are False."""
    tree = ast.parse(expr, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise ValueError(
                f"expression element {type(node).__name__} is not permitted "
                f"in a rule condition: {expr!r}"
            )
        if isinstance(node, ast.Name) and node.id not in namespace:
            raise ValueError(f"unknown name {node.id!r} in rule condition {expr!r}")

    def _eval(node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            return namespace[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not _eval(node.operand)
        if isinstance(node, ast.BoolOp):
            vals = [_eval(v) for v in node.values]
            return all(vals) if isinstance(node.op, ast.And) else any(vals)
        if isinstance(node, ast.Compare):
            left = _eval(node.left)
            for op, comp in zip(node.ops, node.comparators):
                right = _eval(comp)
                if isinstance(op, (ast.Is, ast.IsNot)):
                    ok = (left is right) if isinstance(op, ast.Is) else (left is not right)
                else:
                    # a missing property must never fire a rule
                    if left is None or right is None:
                        return False
                    ok = {
                        ast.Eq: lambda a, b: a == b,
                        ast.NotEq: lambda a, b: a != b,
                        ast.Lt: lambda a, b: a < b,
                        ast.LtE: lambda a, b: a <= b,
                        ast.Gt: lambda a, b: a > b,
                        ast.GtE: lambda a, b: a >= b,
                    }[type(op)](left, right)
                if not ok:
                    return False
                left = right
            return True
        raise ValueError(f"unsupported expression: {expr!r}")

    return bool(_eval(tree))


# Worst verdict wins, so this ordering IS the conflict-resolution policy.
#
# `undetermined` sits above `caution` and below `infeasible` deliberately.
# Above caution: a rule that declined to conclude has not been answered by a
# rule that merely counselled care, and reporting CAUTION would imply the tool
# had weighed something it has not yet computed. Below infeasible: a hard
# physical block is knowledge, whereas undetermined is the absence of it -- no
# pending calculation can give a liquid phase to a feed that has none.
_VERDICT_RANK = {"infeasible": 4, "undetermined": 3, "caution": 2, "feasible": 1}


def _names_in(expr: str) -> list[str]:
    """Property names referenced by a condition, for the provenance record."""
    return [
        n.id for n in ast.walk(ast.parse(expr, mode="eval"))
        if isinstance(n, ast.Name)
    ]


def load_rules(path: str | None = None) -> list[Rule]:
    """Load the rule table, sorted by priority then id.

    Validates at load time, not evaluation time: a duplicate id would
    silently shadow a rule, and a malformed condition would only raise
    when that rule happened to be evaluated (which may be never). Both
    failure modes mean a rule stops firing with no error -- exactly what
    this tool exists to expose.
    """
    with open(path or RULES_PATH) as fh:
        raw = yaml.safe_load(fh)
    rules = [
        Rule(
            id=r["id"], name=r["name"], priority=int(r["priority"]),
            when=r["when"], verdict=r["verdict"],
            technologies=tuple(r["technologies"]),
            because=" ".join(r["because"].split()),
            cite=r.get("cite", ""),
            requires=tuple(r.get("requires", ()) or ()),
            limitations=" ".join((r.get("limitations", "") or "").split()),
        )
        for r in raw
    ]

    seen: dict[str, str] = {}
    for r in rules:
        if r.id in seen:
            raise ValueError(
                f"duplicate rule id {r.id!r} in {path or RULES_PATH}: "
                f"{seen[r.id]!r} and {r.name!r}. Ids must be unique -- a "
                f"duplicate silently shadows a rule."
            )
        seen[r.id] = r.name
        try:
            names = _names_in(r.when)
        except SyntaxError as exc:
            raise ValueError(
                f"rule {r.id} has an unparseable condition {r.when!r}: {exc}. "
                f"A rule that cannot be parsed never fires."
            ) from exc
        for name in names:
            if name not in RULE_VISIBLE_FIELDS:
                raise ValueError(
                    f"rule {r.id} references unknown property {name!r} in "
                    f"{r.when!r}. Valid properties: {sorted(RULE_VISIBLE_FIELDS)}. "
                    f"A rule naming a property that does not exist would abort "
                    f"evaluation for every rule, not just this one."
                )
        if r.verdict not in _VERDICT_RANK:
            raise ValueError(
                f"rule {r.id} has verdict {r.verdict!r}; must be one of "
                f"{sorted(_VERDICT_RANK)}. An unrecognised verdict loads and "
                f"fires, then crashes the ranking."
            )
        for item in r.requires:
            if not item.strip():
                raise ValueError(
                    f"rule {r.id} has an empty entry in requires. A blank "
                    f"string satisfies the 'declares a calculation' check "
                    f"while naming no calculation."
                )
        if r.verdict == "undetermined" and not r.requires:
            raise ValueError(
                f"rule {r.id} has verdict 'undetermined' but must declare at "
                f"least one entry in requires. An undetermined verdict that "
                f"names no calculation withholds an answer and gives the "
                f"reader no way to obtain one."
            )

    return sorted(rules, key=lambda r: (r.priority, r.id))


def evaluate(rules: list[Rule], record: PropertyRecord) -> list[Verdict]:
    """Evaluate EVERY rule. Do not stop at the first match.

    A mixture can be both low-alpha and azeotropic, and the report should say
    both. Rules that did not fire are returned too, so a reader can see what
    was considered rather than only what was concluded.
    """
    ns = record.as_namespace()
    out: list[Verdict] = []
    for rule in rules:
        fired = safe_eval(rule.when, ns)
        used = {name: ns[name] for name in _names_in(rule.when) if name in ns}
        out.append(Verdict(
            rule_id=rule.id, rule_name=rule.name, condition=rule.when,
            values=used, verdict=rule.verdict,
            technologies=rule.technologies, because=rule.because, fired=fired,
            requires=rule.requires, limitations=rule.limitations,
        ))
    return out


def overall_verdict(verdicts: list[Verdict]) -> str:
    """Worst verdict wins. Nothing fired means unknown, never a default."""
    fired = [v for v in verdicts if v.fired]
    if not fired:
        return "unknown"
    return max((v.verdict for v in fired), key=lambda v: _VERDICT_RANK[v])
