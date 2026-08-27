# sepsyn milestone 2 — DWSIM cross-validation

**Status: draft spec, not yet planned into tasks.**
Written 2026-08-22, immediately after milestone 1 merged. Feasibility probed
before writing; findings in "What the probe established" below.

## Problem

Milestone 1 produced a tool that screens a feed, designs a column, and verifies
it — against exactly one simulator. Two claims are therefore untested:

1. **That the numbers are right.** Every verification check compares BioSTEAM
   against itself. `verify_column` confirms the column delivered the recovery
   that was asked for; nothing confirms that recovery is physically correct.
   A systematic error in the property package or the shortcut method would pass
   all 111 tests.
2. **That the `Simulator` protocol actually abstracts.** `base.py` was written
   so no BioSTEAM type crosses the boundary, on the explicit promise that
   "DWSIM is a second file later rather than a refactor". No second
   implementation exists, so the promise is untested design intent.

The second is the more expensive to be wrong about, because the cost of
discovering the abstraction leaks grows with everything built on top of it.

## Thesis

Two independent simulators agreeing on the same feed is evidence the answer is
about chemistry rather than about one library's conventions. Two disagreeing is
more valuable still, because the disagreement is nearly always a *basis* or
*specification* mismatch rather than thermodynamics — and that class of error
is silent, passes every mass balance, and has already cost this user a 175%
error on an ETJ/SAF comparison.

## Scope — milestone 2

1. **A `DwsimSimulator` implementing the existing `Simulator` protocol**, with
   no changes to `base.py`. If `base.py` must change, that is the headline
   result of the milestone and must be recorded, not quietly accommodated.
2. **A cross-validation harness** comparing DWSIM and BioSTEAM on the same
   feed, same keys, same recoveries, same property package, reporting
   per-component agreement.
3. **Acceptance case: methanol / water / glycerol at 100 / 80 / 25 kmol/hr**,
   the milestone 1 column, at `Lr = 0.989495`, `Hr = 0.987506`, 1.013 bar.
   BioSTEAM's answer is already recorded: distillate 98.949 / 0.999 / 0.000,
   bottoms 1.051 / 79.001 / 25.000 kmol/hr.
4. **A negative case**: a specification given to both simulators on *different*
   bases must produce a detectable disagreement. This is the test that proves
   the harness can see the error it exists to catch — without it the harness is
   the same "test that cannot fail" this project has caught fourteen times.

**Out of scope:** sequencing, rigorous (stage-by-stage) column comparison
beyond one confirmatory case, literature RAG, LLM interface.

## What the probe established (2026-08-22)

Measured, not assumed:

| finding | consequence |
|---|---|
| DWSIM reachable live through `dwsim-mcp`; flowsheet built, compounds added, streams connected | the milestone is feasible |
| `ShortcutColumn` exists — Fenske-Underwood-Gilliland, same method class as BioSTEAM's `BinaryDistillation` | a like-for-like comparison is possible |
| `Modified UNIFAC (Dortmund)` available, which is thermosteam's default for these compounds | **thermo can be matched; it must be, or the comparison measures the property package** |
| `configure_column` accepts **"Component Recovery"** as a spec type | DWSIM takes recoveries natively too — the Task 9 decision generalises past BioSTEAM, and no mole-fraction basis need ever be constructed on either side |
| `dwsim-mcp` is C#/.NET under mono, JSON-RPC over stdio — **not importable from Python** | see Risk 1 |
| `ShortcutColumn`'s key/spec fields are NOT settable via the reflection property setter (`LightKey` rejected) and do not appear in `get_object` | see Risk 2 |

## Risks, in the order they are likely to bite

1. **The adapter's transport is the real work.** `DwsimSimulator` cannot simply
   import DWSIM. Options, to be decided in planning: (a) a Python subprocess
   speaking MCP JSON-RPC to the `dwsim-mcp` binary; (b) recorded reference
   fixtures produced once through the MCP and versioned into the repo, with the
   procedure documented; (c) both — fixtures for a hermetic suite, a live
   adapter behind an opt-in marker. Note that (b) validates the NUMBERS but
   proves nothing about the protocol, and the protocol is claim 2 above.
2. ~~**Configuring `ShortcutColumn` is an open question.**~~ **RESOLVED
   2026-08-27 — see "Risk 2 resolved" below.** The spec fields are public
   FIELDS, not properties, which is why the property setter rejected them and
   `get_object` never showed them. A working configuration path exists. But it
   forces a mole-fraction basis, which changes the plan — read that section
   before planning tasks.
3. **Matching thermo is a precondition, not a detail.** Both sides must run
   Modified UNIFAC (Dortmund). An unmatched package turns every disagreement
   into a property-package artefact and the milestone answers nothing.
4. **Agreement tolerance must be measured, not chosen.** This project has now
   been bitten four times by a tolerance too loose to detect its own defect
   (Tasks 9, 11, 12, and the mass-balance constant). Run both simulators first,
   measure the spread on a case believed correct, and set the threshold from
   that spread — then verify by deliberately mis-specifying one side.

## Testing

1. **Protocol conformance** — `DwsimSimulator` satisfies `Simulator` with
   `base.py` unmodified, exercised through the same fake-driven tests that
   already cover `sweep_reflux`.
2. **The acceptance case** — per-component agreement on the milestone 1 column.
3. **The negative case** — a deliberate basis mismatch is detected.
4. **Every new test mutation-checked** with `__pycache__` cleared, per the
   milestone 1 handoff.

## Success criteria

Milestone 2 is complete when:

- `DwsimSimulator` implements `Simulator` with `base.py` unchanged, or the
  required change is documented with its reason.
- DWSIM and BioSTEAM agree per component on the methanol/water/glycerol column,
  within a tolerance derived from measurement and recorded with the number it
  was derived from.
- A deliberate basis mismatch between the two is caught by the harness.
- Matched property packages are asserted by the harness, not assumed by the
  operator.


## Risk 2 resolved (2026-08-27)

Probed live through `dwsim-mcp`. The server itself was not modified.

### Why the property setter failed

`ShortcutColumn`'s specification inputs are **public fields, not properties**.
`set_object_property` reflects over properties and `get_object` dumps public
scalar properties, so both were looking in the wrong place. A full reflection
dump over `BindingFlags.Public|NonPublic|Instance` found them immediately.

| field | type | role |
|---|---|---|
| `m_lightkey`, `m_heavykey` | String | key selection, by compound name |
| `m_lightkeymolarfrac` | Double | **light key mole fraction in the BOTTOMS** |
| `m_heavykeymolarfrac` | Double | **heavy key mole fraction in the DISTILLATE** |
| `m_refluxratio` | Double | reflux ratio |
| `m_condenserpressure`, `m_boilerpressure` | Double | Pa |
| `condtype` | CondenserType | `TotalCond` by default |
| `m_N`, `m_Nmin`, `m_Rmin`, `m_Qc`, `m_Qb` | Double | **outputs**, populated after solve |

Ports are ordinary, so `connect_objects` works and `connect_column_stream` is
not needed: inlet 0 = feed, inlet 1 = reboiler duty, outlet 0 = distillate,
outlet 1 = bottoms, plus a separate condenser-duty energy port.

Both fraction bases were **confirmed empirically**, not assumed: values were
back-computed from BioSTEAM's recorded answer, and the solve reproduced it.

### The finding that changes the plan

**`ShortcutColumn` has no recovery spec.** The reflection dump is exhaustive
and contains no recovery field of any kind — only the two mole fractions. The
probe finding recorded above, that `configure_column` accepts "Component
Recovery", applies to the **rigorous** `DistillationColumn`, not to
`ShortcutColumn`.

That collides with two decisions already made:

- Task 9 chose recoveries specifically so no mole-fraction basis is ever
  constructed. `ShortcutColumn` cannot honour that choice.
- Comparing like-for-like shortcut methods requires `ShortcutColumn`.

So the milestone must pick one, and the choice is now explicit rather than
implicit:

| option | keeps like-for-like FUG | avoids the basis conversion |
|---|---|---|
| `ShortcutColumn` | yes | **no** — forces a mole-fraction basis |
| rigorous `DistillationColumn` + Component Recovery | no | yes |

The mole-fraction basis is the exact error class that produced a 175 %
discrepancy on the ETJ/SAF comparison, so choosing `ShortcutColumn` means
deliberately re-entering it with a conversion that must itself be tested.

### What the acceptance case actually proved, and what it did not

Methanol / water / glycerol at 100 / 80 / 25 kmol/hr, 320 K, 1.013 bar,
Modified UNIFAC (Dortmund) on both sides, R = 0.827.

Per-component agreement, kmol/hr:

| component | DWSIM dist | BioSTEAM dist | DWSIM btms | BioSTEAM btms |
|---|---|---|---|---|
| Methanol | 98.948 | 98.949 | 1.051 | 1.051 |
| Water | 0.999 | 0.999 | 79.001 | 79.001 |
| Glycerol | 0.000 | 0.000 | 25.000 | 25.000 |

**This agreement must not be read as thermodynamic agreement.** The water mole
fraction in the distillate comes back as 0.009995 and the methanol fraction in
the bottoms as 0.010005 — each equal to its specification to six decimals.
Both products are therefore IMPOSED by the specs, not predicted. What the match
confirms is that the BASIS was read correctly; nothing more.

The quantities that are actually predicted disagree:

| quantity | DWSIM | BioSTEAM | gap |
|---|---|---|---|
| minimum reflux | 0.785 | 0.689 | 14 % |
| stages | 25.3 | 44 | 43 % |

**Both gaps were investigated the same day. See "The gaps, explained" below.**
`m_Tc` and `m_Tb` return 0 after a converged solve and may simply not be
populated by this unit; not chased.

This is the real cross-validation surface. A harness that compares only product
flows on an imposed spec would report perfect agreement and detect none of it —
which is the same "test that cannot fail" shape this project has caught before.

Probe flowsheet saved at `sepsyn_m2_shortcut_probe.dwxmz` in the parent
directory, editable in the DWSIM GUI.


## The gaps, explained (2026-08-27)

Each step below was a test, not an inference. The order matters: the first
finding removed most of the apparent disagreement, and only then was the real
one visible.

### 1. The 43 % stage gap was mostly a definition, not a disagreement

`biosteam_adapter.py` line 76 reads `design_results["Actual stages"]`. DWSIM's
`m_N` is THEORETICAL. BioSTEAM reports both:

| | value |
|---|---|
| BioSTEAM actual stages | 43.0 |
| BioSTEAM theoretical stages | 21 |
| DWSIM `m_N` (theoretical) | 25.26 |

Comparing like with like drops the gap from 43 % to **16.9 %**. The implied
tray efficiency, 21/43 = 0.49, is the whole of the rest.

**Consequence for the harness: it must compare theoretical stages to
theoretical stages.** A harness fed `ColumnResult.stages` compares an actual
stage count against a theoretical one and reports a ~40 % disagreement that
does not exist. `ColumnResult` currently carries only `stages`, sourced from
"Actual stages", so it cannot express this comparison at all.

### 2. The remaining stage gap is a consequence of Rmin, not independent

Re-solving DWSIM at R = 1.20 x its OWN Rmin (0.9423) rather than at BioSTEAM's
absolute reflux gives `m_N` = 19.63 against BioSTEAM's 21 — **6.5 %**. Setting
each column the same distance above its own minimum collapses the stage gap, so
stages are not a second independent disagreement. There is one root: Rmin.

### 3. The Rmin disagreement is real, and the acceptance case understates it

Removing glycerol and re-running both sides:

| case | DWSIM | BioSTEAM | DWSIM vs BioSTEAM |
|---|---|---|---|
| ternary (with glycerol) | 0.7853 | 0.6813 | **+15.3 %** |
| binary (no glycerol) | 0.5164 | 0.6822 | **-24.3 %** |

| effect of removing glycerol | |
|---|---|
| DWSIM | 0.7853 -> 0.5164, **-34.2 %** — strongly affected |
| BioSTEAM | 0.6813 -> 0.6822, **+0.1 %** — essentially unaffected |

Two distinct effects, established by differential experiment on both sides:

1. **The two treat a heavy non-key completely differently.** Glycerol moves
   DWSIM's Rmin by a third and BioSTEAM's not at all. BioSTEAM's
   `BinaryDistillation` evidently drops a non-distributing heavy out of the
   Underwood calculation; DWSIM's `ShortcutColumn` keeps it in.
2. **They also disagree by 24 % on the pure binary**, where no third component
   is involved at all. Cause unknown — **this one remains unexplained** and no
   attribution is offered.

**The two effects act in OPPOSITE directions and partially cancel.** The
acceptance case shows a 15.3 % gap; the underlying method disagreement is
larger than that in both components. A tolerance measured only on
methanol/water/glycerol would be calibrated on a coincidence.

This is the direct answer to Risk 4 ("agreement tolerance must be measured, not
chosen"): **measure it on at least the binary case as well**, or the number
will be set from two errors cancelling.

Caveat on method: the DWSIM binary case was produced by setting glycerol's
molar flow to 0 while leaving the compound in the flowsheet, not by removing
the compound. A zero mole fraction should contribute nothing to an Underwood
summation, but this was not separately verified.

### What this means for the route decision

Point 1 under Risk 2 (recoveries vs like-for-like FUG) is now easier to settle.
"Like-for-like shortcut method" was the argument for accepting a mole-fraction
basis with `ShortcutColumn`. But the two shortcut implementations disagree by
24 % on minimum reflux for a plain binary, and handle non-keys on different
principles. They are not like-for-like in any sense that would let a
disagreement be attributed to thermodynamics. The argument for paying the
basis-conversion risk is correspondingly weaker.
