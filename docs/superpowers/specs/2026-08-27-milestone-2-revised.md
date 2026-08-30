# sepsyn milestone 2 (revised) — rigorous cross-validation

**Status: draft spec, not yet planned into tasks. Supersedes the SCOPE of
`2026-08-22-milestone-2-dwsim-crossvalidation.md`.** That document stands
unchanged as the record of what was believed on 2026-08-22 and as the evidence
log for why it changed — its probe findings and its three appendices are still
the source material and are not repeated here.

**RULED 2026-08-27: scope A.** The user chose the minimal scope. Scope B (the
simulation direction) is deferred to its own milestone and is NOT part of
milestone 2.

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

Two scopes were possible. **Recommendation was A; A was ruled on 2026-08-27.**

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
2. ~~**"Component Recovery" on the rigorous column is not yet exercised.**~~
   **PROBED 2026-08-27 — the risk was mis-stated. See "Risk 5" below, which
   replaces it and is more serious.**
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


## Risk 5 — the rigorous reference does not solve this acceptance case
### (probed 2026-08-27; replaces the old Risk 2)

**Seven configurations were run. None converged.** No numbers from any of them
are reported or used anywhere.

| # | configuration | result |
|---|---|---|
| 1 | ternary, 2x Component Recovery, 21 stages, Napthali-Sandholm | max iterations |
| 2 | ternary, 2x Component Recovery, 30 stages, 300 iter | max iterations |
| 3 | ternary, Reflux 0.8175 + Product Flow, 30 stages, N-S | timeout |
| 4 | binary, Reflux 0.8175 + Product Flow, 30 stages, N-S | timeout |
| 5 | binary, same but **NRTL** instead of UNIFAC-Dortmund | timeout |
| 6 | binary, **Reflux 2.0**, 20 stages, **Wang-Henke**, 200 iter | mass balance 2.57e-4 vs 1e-4 tol |
| 7 | binary, Reflux 2.0, 20 stages, Wang-Henke, 1000 iter | still running past 10 min |

**What this rules OUT, by differential test:**

- **Not the Component Recovery spec type.** Runs 3-7 use Reflux Ratio and
  Product Molar Flow Rate — the two spec types that solved a 15-stage
  benzene/toluene column in SECONDS the same day. They fail here too. The old
  Risk 2 asked the wrong question.
- **Not glycerol.** Run 4 (binary) is no better than run 3 (ternary).
- **Not the property package.** Run 5 swaps Modified UNIFAC (Dortmund) for
  NRTL and is equally slow, so the cost is not group-contribution activity
  coefficients.

**What it points AT:**

- **The reflux derived from a shortcut is too low for the rigorous column.**
  Raising reflux from 0.8175 (a value taken from shortcut Rmin of 0.52-0.68) to
  2.0 changed the failure mode qualitatively — from an uninformative timeout to
  a near-miss, mass balance off by 2.57e-4 against a 1e-4 tolerance. That is
  the single most informative result of the seven.
- **Napthali-Sandholm is dramatically more expensive than Wang-Henke here**
  (~945 s vs ~120 s on comparable settings), which inverts the usual advice in
  `AGENTS.md` for this system.
- Even Wang-Henke at 1000 iterations does not finish inside ~10 minutes.

### Consequences for scope A

1. **The acceptance case may be the wrong case.** Methanol / water / glycerol
   was chosen when BOTH sides were shortcut methods, where it is trivial. As a
   rigorous reference it is a stiff, strongly non-ideal problem. The
   benzene/toluene system solved rigorously in seconds the same day, and is the
   obvious candidate for harness bring-up, with methanol/water kept as a later
   stress case.
2. **Solve times of minutes-to-timeout make a LIVE adapter impractical in a
   test suite.** This pushes Risk 1 (transport) hard toward option (b),
   recorded fixtures, or (c) with the live path behind an opt-in marker. Risk 2
   has effectively decided Risk 1, which is not how the spec expected it to go.
3. **The reference column cannot be driven by shortcut-derived reflux.** If the
   harness compares a shortcut design against a rigorous reference, it must
   solve the reference at a reflux the RIGOROUS column can achieve, and that
   value is not known in advance from FUG.

**None of this is resolved.** It is recorded so that task planning starts from
it rather than rediscovering it.

## Risk 5 re-tested on a healthy machine (2026-08-30)

The 08-27 runs were made while `~/Desktop` was iCloud evicted and `dwsim-mcp`
was 68 % dataless, so four of the seven failures were *timeouts* and had to be
treated as contaminated. The project now lives at
`~/projects/process_simulation`, outside iCloud, with zero dataless files.

Re-run there:

| configuration | 08-27 | 08-30 |
|---|---|---|
| ternary, 2x Component Recovery, 30 stages, Napthali-Sandholm, 300 iter | timeout | **max iterations, returned promptly** |
| ternary, Reflux 2.0 + Product Flow, 20 stages, Wang-Henke, 2000 iter | timeout | **max iterations, returned promptly** |

**Risk 5 stands. It was not an artifact.** What the eviction changed was the
failure *mode*, not the outcome: a genuine non-convergence was being reported as
a timeout, which hid the fact that the solver was reaching its iteration cap
rather than being starved of CPU. The rigorous column does not converge on
methanol / water / glycerol across two spec types, two solvers, two stage
counts and iteration limits up to 2000.

The conclusions drawn from it therefore hold unchanged: the acceptance case is
the wrong case for a rigorous reference, and benzene/toluene remains the
sensible bring-up candidate.

One correction to the 08-27 reasoning. Solve times are NOT the argument for
recorded fixtures that they appeared to be, because the slowness was
environmental. Risk 1 must be decided on the protocol question alone.
