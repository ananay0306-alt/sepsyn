# sepsyn milestone 2 (revised) — rigorous cross-validation

**Status: draft spec, not yet planned into tasks. Supersedes the SCOPE of
`2026-08-22-milestone-2-dwsim-crossvalidation.md`.** That document stands
unchanged as the record of what was believed on 2026-08-22 and as the evidence
log for why it changed — its probe findings and its three appendices are still
the source material and are not repeated here.

**A ruling is requested before this is planned into tasks.** See "The ruling"
below. Everything else follows from it.

## Why the 08-22 scope was replaced

Probing on 2026-08-27 established three things that between them invalidate the
original plan. All are recorded with their evidence in the 08-22 appendices.

1. **The acceptance criterion could not fail.** Both simulators are given the
   same recoveries, and the products come back equal to their specs to six
   decimals. Per-component product agreement is imposed by construction. The
   acceptance case contains exactly one unimposed number — where glycerol goes
   — and its relative volatility against the keys is ~1e4.
2. **"Like-for-like FUG" was not available.** DWSIM's `ShortcutColumn` and
   BioSTEAM's `BinaryDistillation` disagree by 24 % on minimum reflux for a
   plain binary and handle a heavy non-key on different principles (removing
   glycerol moves DWSIM's Rmin by -34 %, BioSTEAM's by +0.1 %). Two
   implementations that differ that way cannot isolate thermodynamics.
3. **`ShortcutColumn` has no recovery spec at all** — only mole fractions,
   which reintroduces the basis conversion Task 9 chose recoveries to avoid.

## Revised thesis

The 08-22 thesis was that two simulators agreeing is evidence the answer is
about chemistry. That framing does not survive finding 1: agreement on an
imposed quantity is evidence of nothing.

**The revised thesis is narrower and more useful.** sepsyn designs with a
SHORTCUT method (BioSTEAM's `BinaryDistillation`, Fenske-Underwood-Gilliland).
The question worth answering is not "do two simulators agree" but:

> **How far is sepsyn's shortcut design from a rigorous stage-by-stage answer,
> and is that distance small enough to design on?**

That makes DWSIM's rigorous `DistillationColumn` a REFERENCE, not a peer. The
method asymmetry stops being a defect of the comparison and becomes its point:
a rigorous MESH solve is closer to truth than FUG, so the gap is a measurement
of shortcut error, which is design information sepsyn does not currently have.

It also reframes disagreement. A 10 % duty gap does not mean one side is wrong;
it means the shortcut is 10 % off the rigorous answer on that case.

## The ruling

Two scopes are possible. **Recommendation: A.**

**A — minimal (recommended).** Keep the design direction and recoveries. Add
duties as the comparison target and configuration assertions to the harness.
`base.py` changes only ADDITIVELY (two duty fields on `ColumnResult`).

**B — full.** Invert to the simulation direction: specify stages, feed stage
and reflux, and compare the purities each side predicts, using
`MESHDistillation` against DWSIM's rigorous column. Nothing imposed on either
side. This is the better test and roughly twice the milestone: `stages` becomes
an INPUT, which restructures `ColumnSpec`/`ColumnResult` rather than extending
them.

A is recommended because it removes the vacuity for a fraction of the cost, and
because milestone 1 shipped by being scoped tightly. **B should become its own
milestone rather than be folded in.**

## Scope — if A is ruled

1. **A `DwsimSimulator` implementing the existing `Simulator` protocol**, built
   on the **rigorous `DistillationColumn` with a "Component Recovery" spec**,
   NOT `ShortcutColumn`. No mole-fraction basis is constructed anywhere.
2. **Two additive fields on `ColumnResult`**: `condenser_duty_kW`,
   `reboiler_duty_kW`. This is a `base.py` change and therefore, by the
   milestone's own terms, a headline result to be recorded rather than quietly
   accommodated — but an additive one that no existing caller breaks on.
3. **A cross-validation harness** comparing, per case: the two duties, the
   non-key distribution, and the key recoveries as a sanity check (which should
   agree trivially — if they do not, something is wrong upstream of the
   comparison).
4. **Configuration assertions, made by the harness rather than the operator.**
   The property package is already required to be asserted. Add: condenser type
   (BioSTEAM's `BinaryDistillation` defaults to `partial_condenser=True`, which
   alone produced a 57.7 % condenser-duty disagreement), stage basis
   (theoretical vs actual — `design_results` carries both), and reflux basis
   (absolute reflux vs a matched R/Rmin ratio).
5. **Tolerance measured on BOTH a binary and a ternary case.** On the ternary
   case two errors act in opposite directions and partially cancel, so a
   tolerance fitted to it alone is calibrated on a coincidence.
6. **A negative case** — a deliberate configuration mismatch (simplest:
   partial vs total condenser) must be DETECTED by the harness. Without this
   the harness is the "test that cannot fail" shape this project has caught
   repeatedly, including in the 08-22 success criteria.

**Out of scope:** the simulation direction (scope B, its own milestone),
sequencing, literature RAG, LLM interface.

## What is already known to work

Established live on 2026-08-27, so these are not risks:

- DWSIM's rigorous `DistillationColumn` configures and converges through
  `configure_column` — stages, feed stage, top pressure, pressure drop,
  condenser and reboiler specs, solver method — verified on a separate
  benzene/toluene column the same day.
- `configure_column` accepts `"Component Recovery"` as a spec type.
- `ShortcutColumn`'s field-level configuration is documented in the 08-22
  appendix should scope B or a comparison ever need it.

## Risks

1. **The adapter's transport is still the real work, and is unchanged by this
   revision.** `dwsim-mcp` is a C#/mono JSON-RPC server, not importable from
   Python. Options (a) live subprocess speaking MCP, (b) recorded fixtures
   versioned into the repo, (c) both. Note that (b) validates numbers but
   proves nothing about the protocol, which is half the milestone. **This is
   the first thing to decide when planning tasks.**
2. **"Component Recovery" on the rigorous column is configured but not yet
   exercised.** The spec type is accepted; a converged rigorous solve driven by
   recoveries has not been run. Probe this BEFORE planning tasks, as was done
   for `ShortcutColumn`.
3. **The tolerance cannot be inherited from today's numbers.** The 6.3 %
   condenser / 1.9 % reboiler agreement measured on 08-27 was DWSIM's
   `ShortcutColumn` against BioSTEAM's shortcut. Moving DWSIM to a rigorous
   column changes the expected spread — probably widening it, since the
   comparison becomes shortcut-vs-rigorous by design. Treat those figures as an
   order-of-magnitude prior only, and re-measure.
4. **A shortcut-vs-rigorous gap is not automatically an error.** Under the
   revised thesis the gap MEASURES shortcut error. The harness must therefore
   report the gap rather than pass/fail it, and only the configuration
   assertions should be hard failures.

## Testing

1. **Protocol conformance** — `DwsimSimulator` satisfies `Simulator`, exercised
   through the same fake-driven tests that already cover `sweep_reflux`.
2. **The acceptance case** — methanol / water / glycerol at 100 / 80 / 25
   kmol/hr, `Lr = 0.989495`, `Hr = 0.987506`, 1.013 bar, Modified UNIFAC
   (Dortmund) asserted on both sides.
3. **A binary case** — methanol / water alone, so the tolerance is measured
   where no cancellation is possible.
4. **The negative case** — a deliberate condenser-type mismatch is caught.
5. **Every new test mutation-checked** with `__pycache__` cleared, per the
   milestone 1 handoff.

## Success criteria

Milestone 2 (A) is complete when:

- `DwsimSimulator` implements `Simulator` with `base.py` changed only by the
  two additive duty fields, or any further change documented with its reason.
- The harness reports condenser and reboiler duty gaps between the shortcut
  design and the rigorous reference on both the binary and ternary cases, with
  the tolerance derived from those measurements and recorded alongside the
  numbers it came from.
- Property package, condenser type, stage basis and reflux basis are asserted
  by the harness, not assumed by the operator.
- A deliberate configuration mismatch is caught by the harness.
- **No success criterion is satisfied by an imposed quantity.** Key recoveries
  may be checked, but may not be the evidence of agreement.
