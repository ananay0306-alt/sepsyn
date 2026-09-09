"""Design every column in one sequence, and add up what it costs.

Products propagate. The feed to a downstream column is the actual product of
the column above it, impurities included, never the idealised group flow. That
matters because a sharp split is not perfect: at 99% recovery the first column
sends 1% of its light key into the bottoms, and the next column has to deal
with it. The idealised version hides that entirely.

Because products propagate, the columns of a sequence must be solved in
dependency order rather than independently. At the measured 0.01 s per column
that costs nothing.
"""
from dataclasses import dataclass

from sepsyn.design import _annualised
from sepsyn.sequencing.train import Node
from sepsyn.simulators.base import ColumnResult, ColumnSpec
from sepsyn.types import Component, Feed


@dataclass(frozen=True)
class ColumnOutcome:
    split: Node
    pressure_Pa: float
    pressure_basis: str
    result: ColumnResult | None
    annualised_cost_USD_yr: float | None
    vapour_kmol_hr: float | None
    screening: str = ""
    eliminated_by: str = ""


@dataclass(frozen=True)
class SequenceOutcome:
    root: Node
    columns: tuple[ColumnOutcome, ...]
    total_cost_USD_yr: float | None
    total_vapour_kmol_hr: float | None
    eliminated_by: str

    @property
    def feasible(self) -> bool:
        return not self.eliminated_by

    @property
    def name(self) -> str:
        from sepsyn.sequencing.enumeration import label
        return label(self.root)


def _feed_from(flows: dict[str, float], order: tuple[str, ...],
               T_K: float, P_Pa: float, cas: dict[str, str]) -> Feed:
    """Everything actually present, in volatility order.

    NOT filtered to the node's nominal group. A sharp split is not perfect: the
    first column of the alkane train sends 0.4 kmol/hr of propane into its
    bottoms, and that propane really does enter the next column. Building the
    downstream feed from the group name instead of from the arriving stream
    discards it, which silently restores the idealisation this module exists to
    remove, and loses 0.4 kmol/hr of mass on the way.
    """
    present = tuple(n for n in order if flows.get(n, 0.0) > 0.0)
    return Feed(
        components=tuple(Component(n, cas[n], flows[n]) for n in present),
        T_K=T_K, P_Pa=P_Pa,
    )


def evaluate_sequence(sim, feed: Feed, root: Node, *,
                      lk_recovery: float = 0.99,
                      hk_recovery: float = 0.99) -> SequenceOutcome:
    """Walk the tree, designing each column with the products of its parent."""
    from sepsyn.cli import resolve_column_pressure
    from sepsyn.engine import evaluate as evaluate_rules
    from sepsyn.engine import load_rules, overall_verdict
    from sepsyn.properties import build_property_record

    rules = load_rules()
    cas = {c.name: c.cas for c in feed.components}
    order = feed.names          # master volatility order, lightest first
    columns: list[ColumnOutcome] = []
    failure = ""

    def walk(node: Node, flows: dict[str, float]) -> None:
        nonlocal failure
        if node.is_leaf or failure:
            return
        group_feed = _feed_from(flows, order, feed.T_K, feed.P_Pa, cas)
        pressure, basis = resolve_column_pressure(group_feed, node.group[0], None)
        # Screen THIS column, not just the original feed. A pair that is well
        # behaved in the full mixture can be azeotropic once a component is
        # removed, and a sequence that creates such a pair partway down the
        # train has to be eliminated there rather than costed as if it worked.
        record = build_property_record(
            group_feed, column_P_Pa=pressure,
            light_key=node.light_key, heavy_key=node.heavy_key,
            column_P_basis=basis)
        verdicts = evaluate_rules(rules, record)
        verdict = overall_verdict(verdicts)
        if verdict == "infeasible":
            fired = ", ".join(v.rule_id for v in verdicts
                              if v.fired and v.verdict == "infeasible")
            failure = (f"column {node.light_key}/{node.heavy_key} screens "
                       f"INFEASIBLE ({fired})")
            columns.append(ColumnOutcome(node, pressure, basis, None,
                                         None, None, screening=verdict,
                                         eliminated_by=failure))
            return

        spec = ColumnSpec(node.light_key, node.heavy_key,
                          lk_recovery, hk_recovery, pressure)
        result = sim.design_multicomponent(group_feed, spec)
        if not result.converged:
            failure = (f"column {'+'.join(node.light_group)}/"
                       f"{'+'.join(node.heavy_group)} did not converge: "
                       f"{result.error}")
            columns.append(ColumnOutcome(node, pressure, basis, result,
                                         None, None, screening=verdict,
                                         eliminated_by=failure))
            return
        D = sum(result.distillate.values())
        columns.append(ColumnOutcome(
            split=node, pressure_Pa=pressure, pressure_basis=basis,
            result=result,
            annualised_cost_USD_yr=_annualised(result.installed_cost_USD,
                                               result.utility_cost_USD_hr),
            # Vapour to the condenser, the spec's cost surrogate. Defined once
            # there and pinned by a test here so the two cannot drift.
            vapour_kmol_hr=D * (result.reflux + 1.0),
            screening=verdict,
        ))
        walk(node.light, dict(result.distillate))
        walk(node.heavy, dict(result.bottoms))

    walk(root, {c.name: c.flow_kmol_hr for c in feed.components})

    if failure:
        return SequenceOutcome(root, tuple(columns), None, None, failure)
    return SequenceOutcome(
        root, tuple(columns),
        sum(c.annualised_cost_USD_yr for c in columns),
        sum(c.vapour_kmol_hr for c in columns),
        "",
    )
