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
            ast.parse(r.when, mode="eval")
        except SyntaxError as exc:
            raise ValueError(
                f"rule {r.id} has an unparseable condition {r.when!r}: {exc}. "
                f"A rule that cannot be parsed never fires."
            ) from exc

    return sorted(rules, key=lambda r: (r.priority, r.id))
