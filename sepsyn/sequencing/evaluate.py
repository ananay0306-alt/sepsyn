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
from dataclasses import dataclass, field

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
    resolved: str = ""
    """How an R-09 doubt was answered by calculation, when it was: the
    designed condenser temperature, and the pressure raise if one was needed.
    Empty when R-09 did not fire or could not be answered."""


@dataclass(frozen=True)
class SequenceOutcome:
    root: Node
    columns: tuple[ColumnOutcome, ...]
    total_cost_USD_yr: float | None
    total_vapour_kmol_hr: float | None
    eliminated_by: str
    undetermined_by: str = ""
    """Non-empty when a column screened `undetermined`. Such a sequence is NOT
    eliminated, but it carries no cost.

    An undetermined verdict means a rule fired and cannot be acted on until a
    calculation is done. Costing the train anyway is a confident answer about
    something unverified, and that is the failure this project exists to
    prevent. It was committed here: two of three columns in the reported
    winning sequence were flagged and it was ranked at $513,461/yr regardless,
    on columns a rigorous solve could not converge."""
    exposure: dict[str, float] = field(default_factory=dict)
    """Tagged component -> kmol/hr of it summed over every column it enters.

    FLOW WEIGHTED, not a column count, and the difference matters. A plain
    count cannot tell 10 kmol/hr through three columns from a 0.1 kmol/hr trace
    through three: sharp splits are imperfect, so a trace of every component
    propagates almost everywhere and every count saturates. Measured on the
    alkane train, tagging hexane gives a count of 3 for BOTH the direct
    sequence, which carries it at full flow the whole way, and the indirect
    one, which removes it at the first column. A metric that cannot separate
    those two is useless for the trade-off it exists to show.

    Weighting by flow separates them without inventing a threshold, which is
    the whole reason exposure is counted rather than enforced."""
    exposure_columns: dict[str, int] = field(default_factory=dict)
    """Tagged component -> how many columns it appears in at all, trace
    included. Reported alongside the flow-weighted figure for readability, and
    never on its own."""

    @property
    def feasible(self) -> bool:
        """Not ruled out. Undetermined sequences are still feasible: they may
        be perfectly good once a partial condenser or a light-ends vent is
        confirmed, and eliminating them would hide a viable route."""
        return not self.eliminated_by

    @property
    def costable(self) -> bool:
        """Feasible AND fully determined. Only these may carry a cost or enter
        a ranking."""
        return self.feasible and not self.undetermined_by

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


# Pressure step for answering R-09. Small, because the measured shortfalls are
# fractions of a kelvin: the column pressure is chosen so the PURE light key
# condenses exactly at the cooling-water limit, and the traces carried down a
# train pull the real distillate just below it.
R09_PRESSURE_STEP = 1.02


def _undetermined_ids(verdicts) -> list[str]:
    return [v.rule_id for v in verdicts
            if v.fired and v.verdict == "undetermined"]


def _answer_r09(sim, group_feed, node, pressure, lk_recovery, hk_recovery,
                screen):
    """Answer R-09 for one column by designing it, the calculation R-09's
    own `requires` names.

    R-09 screens on the lightest component present, at any amount. Down a
    train that is a 1 % trace of propane, so it doubts condensers that the
    designed column runs 28 to 156 K above cooling water (11-08, ten
    n-alkanes). The designed distillate's temperature is the real answer. When
    it falls short, by fractions of a kelvin where the pure light key sits at
    the limit, the pressure is raised in small steps up to the same 30 bar cap
    design.py uses, re-screening each time so no other rule is stepped past.

    Returns ((pressure, verdicts, result), note) when answered, or
    (None, note) when not. A note of "" means R-09 was not the question.
    """
    from sepsyn.design import MAX_PRESSURE_Pa
    from sepsyn.properties import COOLING_WATER_T

    P = pressure
    while True:
        verdicts, verdict = screen(P)
        if verdict == "infeasible" or _undetermined_ids(verdicts) != ["R-09"]:
            return None, ""
        result = sim.design_multicomponent(group_feed, ColumnSpec(
            node.light_key, node.heavy_key, lk_recovery, hk_recovery, P))
        T = result.distillate_T_K if result.converged else None
        if T is None:
            return None, (f"R-09 could not be answered: the column did not "
                          f"design at {P / 1e5:.3f} bar")
        if T >= COOLING_WATER_T:
            note = (f"R-09 answered: designed condenser at {T:.1f} K, at or "
                    f"above cooling water at {COOLING_WATER_T:.2f} K")
            if P > pressure:
                note += (f", after raising the pressure from "
                         f"{pressure / 1e5:.3f} to {P / 1e5:.3f} bar")
            return (P, verdicts, result), note
        if P >= MAX_PRESSURE_Pa:
            return None, (f"R-09 stands: the designed condenser is at {T:.1f} "
                          f"K, below cooling water at {COOLING_WATER_T:.2f} K, "
                          f"even at the {MAX_PRESSURE_Pa / 1e5:.0f} bar cap")
        P = min(P * R09_PRESSURE_STEP, MAX_PRESSURE_Pa)


def evaluate_sequence(sim, feed: Feed, root: Node, *,
                      lk_recovery: float = 0.99,
                      hk_recovery: float = 0.99,
                      tags: dict[str, frozenset[str]] | None = None
                      ) -> SequenceOutcome:
    """Walk the tree, designing each column with the products of its parent."""
    from sepsyn.cli import resolve_column_pressure
    from sepsyn.engine import evaluate as evaluate_rules
    from sepsyn.engine import load_rules, overall_verdict
    from sepsyn.properties import build_property_record

    rules = load_rules()
    cas = {c.name: c.cas for c in feed.components}
    order = feed.names          # master volatility order, lightest first
    columns: list[ColumnOutcome] = []
    undetermined: list[str] = []
    exposure: dict[str, float] = {}
    exposure_columns: dict[str, int] = {}
    failure = ""

    def walk(node: Node, flows: dict[str, float]) -> None:
        nonlocal failure
        if node.is_leaf or failure:
            return
        group_feed = _feed_from(flows, order, feed.T_K, feed.P_Pa, cas)

        # Exposure is COUNTED, never enforced. A threshold for how many columns
        # a corrosive component may traverse would be invented, and a materials
        # cost multiplier needs a factor the tool has no source for. Both bury
        # an invented number inside a verdict. The count travels beside the cost
        # and the reader resolves the trade-off.
        #
        # Counted from the ACTUAL stream, so a trace carried forward counts:
        # propane nominally leaves at column one, but the 1% in its bottoms
        # still reaches the metal downstream.
        for tagged in (tags or {}):
            entering = flows.get(tagged, 0.0)
            if entering > 0.0:
                exposure[tagged] = exposure.get(tagged, 0.0) + entering
                exposure_columns[tagged] = exposure_columns.get(tagged, 0) + 1
        pressure, basis = resolve_column_pressure(group_feed, node.group[0], None)
        # Screen THIS column, not just the original feed. A pair that is well
        # behaved in the full mixture can be azeotropic once a component is
        # removed, and a sequence that creates such a pair partway down the
        # train has to be eliminated there rather than costed as if it worked.
        def screen(P):
            record = build_property_record(
                group_feed, column_P_Pa=P,
                light_key=node.light_key, heavy_key=node.heavy_key,
                column_P_basis=basis)
            vs = evaluate_rules(rules, record)
            return vs, overall_verdict(vs)

        verdicts, verdict = screen(pressure)
        designed, resolved, unanswered = None, "", ""
        if verdict == "undetermined":
            answer, note = _answer_r09(sim, group_feed, node, pressure,
                                       lk_recovery, hk_recovery, screen)
            if answer is not None:
                P, verdicts, designed = answer
                if P != pressure:
                    basis = (f"{basis}; raised to {P / 1e5:.3f} bar so the "
                             f"designed distillate condenses against cooling "
                             f"water (R-09)")
                pressure, resolved = P, note
                # R-09 has been answered by the design; the verdict is what
                # the other rules say.
                verdict = overall_verdict(
                    [v for v in verdicts if v.rule_id != "R-09"])
            else:
                unanswered = note
        if verdict == "undetermined":
            # Recorded and ALLOWED TO BLOCK. Previously this was stored on the
            # ColumnOutcome and ignored, so a sequence containing a column the
            # tool declined to endorse was costed and ranked anyway.
            fired = ", ".join(_undetermined_ids(verdicts))
            undetermined.append(
                f"column {node.light_key}/{node.heavy_key} is UNDETERMINED "
                f"({fired})" + (f": {unanswered}" if unanswered else ""))
        if verdict == "infeasible":
            fired = ", ".join(v.rule_id for v in verdicts
                              if v.fired and v.verdict == "infeasible")
            failure = (f"column {node.light_key}/{node.heavy_key} screens "
                       f"INFEASIBLE ({fired})")
            columns.append(ColumnOutcome(node, pressure, basis, None,
                                         None, None, screening=verdict,
                                         eliminated_by=failure))
            return

        if designed is not None:
            result = designed
        else:
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
            resolved=resolved,
        ))
        walk(node.light, dict(result.distillate))
        walk(node.heavy, dict(result.bottoms))

    walk(root, {c.name: c.flow_kmol_hr for c in feed.components})

    if failure:
        return SequenceOutcome(root, tuple(columns), None, None, failure, "",
                               exposure, exposure_columns)
    if undetermined:
        # Designed, but not costed. The per-column results stay so a reader can
        # see what was rejected and why.
        return SequenceOutcome(root, tuple(columns), None, None, "",
                               "; ".join(undetermined),
                               exposure, exposure_columns)
    return SequenceOutcome(
        root, tuple(columns),
        sum(c.annualised_cost_USD_yr for c in columns),
        sum(c.vapour_kmol_hr for c in columns),
        "",
        "",
        exposure,
        exposure_columns,
    )
