# Minimum-vapour sequencing (M6) — design

**Date:** 2026-09-10
**Status:** design, not yet planned into tasks
**Replaces:** cost-ranked enumeration as the basis for CHOOSING a sequence.
It does not replace M3's machinery; it replaces M3's objective and its search.

## 1. The question

Stated by the review: *"Suppose we have 10 components. How will we separate
them, and how will we separate them efficiently? Not cost-efficient — we have
no cost. What other metric?"*

Two things are being asked and they have different answers.

**Which sequence?** A search problem, and at ten components the current
architecture cannot answer it.

**Efficient by what measure, without cost?** A metric problem, and cost is not
merely unavailable — today's measurements showed it is not trustworthy even
when computed.

## 2. Why cost cannot be the metric, on this project's own evidence

Three findings from 2026-09-09 and 09-10, all recorded in `docs/findings/`:

- A rigorous DWSIM column needed **9x** the reflux BioSTEAM's shortcut chain
  predicted on a four-component case.
- Fixing a single defect **flipped the recommended sequence** from direct to
  indirect and moved cost by 50 %. The ranking sat inside the method's own
  error band.
- Cost and total vapour load were offered as independent corroboration and are
  **not independent**: vapour load is `D(R+1)` and cost derives from the duties,
  which derive from `R`. Both inherit the same reflux.

A ranking whose order changes by more than the margin it reports is not a
ranking. Cost is disqualified as the selection criterion until M2 produces
error bars, and possibly after.

## 3. The metric: minimum vapour flow

For a sharp split of a contiguous group, with components ordered by decreasing
volatility and the split placed between components `r` and `r+1`:

**Phase 1, the Underwood root.** Solve for the θ lying between α(r+1) and α(r):

    sum_i [ alpha_i * z_i ] / [ alpha_i - theta ]  =  1 - q

**Phase 2, the minimum vapour requirement:**

    V_min  =  sum_{i <= r} [ alpha_i * F * z_i ] / [ alpha_i - theta ]

with α relative to the heavy key, `z` the group's feed composition, `F` its
molar flow and `q` its thermal condition. The train's figure of merit is
`sum V_min` over its columns.

### Why this and not cost

**It is a requirement, not an estimate.** V_min is the least vapour that must
be boiled to achieve the split at infinite stages. It is a thermodynamic lower
bound. A bound is a far weaker and safer claim than a design, and it is the
kind of claim that survives the errors measured in M2.

**It needs no cost data**, which is the stated constraint.

**It tracks cost anyway.** Energy is the dominant term in a distillation
train's annual cost, and both reboiler duty and column diameter scale with
vapour flow. When cost data exists it becomes a second objective over the same
machinery, not a replacement.

**It is the established answer.** Underwood's V_min underlies the V_min
diagrams of Halvorsen and Skogestad, which exist for exactly this comparison.
This is not an invented criterion.

**Decisively for this project: it avoids every layer that failed.** No
Gilliland, no theoretical-to-actual stage conversion, no tray efficiency, no
condenser type, no diameter correlation, no cost model. Every defect found on
09-09 and 09-10 lives downstream of Underwood. V_min stops there.

## 4. The algorithm: dynamic programming, not enumeration

Enumeration is the wrong architecture for the question asked, and this is the
core of the redesign.

A sequence is a binary tree over **contiguous** groups. The optimal way to
separate a group does not depend on how that group was produced, only on what
it contains. That is optimal substructure, so the problem decomposes:

    Best(g) = 0                                        if |g| = 1
    Best(g) = min over split k of
                  V_min(g, k) + Best(g_light) + Best(g_heavy)

| n | sequences (Catalan) | columns if enumerated | sub-groups | (group, split) pairs |
|---|---|---|---|---|
| 4 | 5 | 15 | 10 | 10 |
| 6 | 42 | 210 | 21 | 35 |
| 8 | 429 | 3 003 | 36 | 84 |
| **10** | **4 862** | **43 758** | **55** | **165** |
| 12 | 58 786 | 646 646 | 78 | 286 |

The last column is `sum over k of (n-k+1)(k-1)`: there are `n-k+1` contiguous
groups of size `k`, each with `k-1` places to cut. Computed, not estimated —
three entries of this table were wrong when written by hand.

At ten components this is **165 Underwood solves instead of 43 758 column
designs**, and it returns the provable optimum rather than a ranked list.
Complexity is O(n³), not Catalan.

Every sub-result is reusable: `Best(("C5","C6","C7"))` is computed once and
serves every sequence containing that group. Enumeration recomputes it for each.

## 5. What DP costs, and the two-stage design it forces

DP's optimal substructure requires that a group's sub-problem depend only on
its contents. **That holds only under the sharp-split idealisation.** With real
splits, impurities propagate — M3 measured 0.4 kmol/hr of propane carried into
a downstream column — and the sub-problem then depends on the path, which
breaks the decomposition.

This is a genuine tension with M3's product propagation, which was added
deliberately and is correct.

**The resolution is two stages, and it is better than either alone:**

1. **Select** with DP on V_min under sharp splits. Cheap, exact within its
   idealisation, and scales to ten components.
2. **Verify** the chosen sequence — and only that one — with the existing M3
   machinery: propagate real products, screen every column with the twelve
   rules, honour `undetermined`, count exposure.

Selection is a bound problem; verification is a design problem. Conflating them
is what produced a ranking built on columns that could not be built.

## 6. What is kept, and what is dropped

**Kept, unchanged.** The rule engine and the twelve screening rules; per-column
pressure resolution; `undetermined` blocking a cost; the equipment rules and
their default/decided distinction; exposure counting weighted by flow; the
assumption ledger and the report. All of it caught the defects of the last two
days and none of it is implicated in them.

**Dropped as the basis for CHOOSING a sequence.** Cost ranking; sequence
enumeration; and the Fenske-Underwood-Gilliland design chain. Design a column
once the sequence is chosen, not in order to choose it.

**Written ourselves rather than borrowed.** Underwood's roots and V_min are
implemented directly from the equations in §3. `ShortcutColumn` produced a
result we could not attribute, and a bound this whole milestone rests on must
be code we can read. Roughly forty lines and a root-finder.

## 7. Verification

A bound is easier to check than a design, and this one is checkable directly.

**The primary test.** Run a rigorous DWSIM column at successively higher stage
counts at fixed recoveries. Its converged vapour flow must approach our V_min
from above and never fall below it. A rigorous solve that needs LESS vapour
than the computed minimum is proof the implementation is wrong, and it is an
unambiguous failure signal of the kind M2 lacked.

**The secondary test.** For a binary feed, V_min must reduce to the textbook
`R_min = V_min/D - 1` and agree with a hand calculation.

**The regression test.** The four-feed series from
`2026-09-09-underwood-rmin-falls-with-non-keys.md`, where BioSTEAM's Rmin fell
from 1.13 to 0.30 as inert pentane was added. Our own implementation must be
run on the same series and its behaviour recorded. **Whether it reproduces that
fall or not is a finding either way**, and it is the cheapest available test of
whether that measurement was BioSTEAM's defect or our misuse. Nothing is filed
against BioSTEAM until this runs.

## 8. What this does to the heuristics question

It removes the circularity. The scorecard currently grades textbook heuristics
against sepsyn's own unvalidated cost ranking — an ungraded ruler.

The classic heuristics — easiest split first, most difficult last, most
plentiful first, favour equimolar splits — are all crude approximations of
minimum vapour. With V_min computed exactly and the optimum found by DP, each
heuristic can be scored against a **thermodynamic reference** rather than
against another estimate from the same family.

That is the review's original question, *which rule wins when two conflict*,
answered against something external.

Corrosion and hazard remain what §12 of the M3 spec made them: counted
exposure, reported beside the objective, never folded into it. DP can be run a
second time minimising exposure to expose the trade-off explicitly as two
optimal sequences rather than one compromise.

## 9. Scope

**In.** Sharp splits; simple two-product columns; distillation only; 3 to 12
components; ideal or near-ideal mixtures where Underwood applies.

**Out, and stated so the boundary is declared rather than discovered.**
Non-sharp splits. Thermally coupled, Petlyuk and dividing-wall configurations —
noting that V_min diagrams are the standard tool for exactly those, so this is
the natural extension rather than a permanent exclusion. Azeotropic and
strongly non-ideal mixtures, where constant relative volatility fails and
Underwood does not apply; the existing R-03 and R-12 screening rules must gate
entry to the whole method. Heat integration between columns.

## 10. Assumptions, labelled

| Assumption | Status |
|---|---|
| Constant relative volatility across each column | Underwood's central assumption. Measured 09-09: α varies 1.11x on the alkane column and 1.13x on benzene/toluene, so the error is present and roughly equal on cases that agree and disagree |
| Sharp splits, which DP requires | Idealisation, and the reason for the two-stage design in §5 |
| V_min is a good proxy for cost | Standard, defensible through the energy term, unverified here |
| Underwood applies to the mixture at all | Gated by the existing azeotrope and liquid-liquid rules, not assumed |
| Our own Underwood implementation is correct | The point of §7. Nothing rests on it until the DWSIM approach test passes |

## 11. Why this is the right project

It answers the question that was actually asked, at the size it was asked at.
It is smaller than what exists rather than larger. It discards the layers that
demonstrably failed and keeps the layers that caught the failures. And its
central claim is a bound, which is the only kind of claim this project has
earned the right to make.
