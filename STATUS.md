# sepsyn — status

Updated 2026-08-31. Check this file; it is the tracker.
`cat STATUS.md` beats scrolling a chat log.

## Where we are

| | |
|---|---|
| Milestones done | **1 of 6**, plus the 41-step heuristics fold-in COMPLETE |
| Tests | **230 passing**, 17 s |
| Blocking right now | **Risk 5**, re-tested and confirmed genuine. M2 needs a new acceptance case |
| Waiting on you | **2 decisions** (below). M2 does not move until these are made. |
| Published | **public** at github.com/ananay0306-alt/sepsyn, MIT |

## Environment: FIXED 2026-08-30

The project was on `~/Desktop`, which is iCloud synced, and iCloud was out of
quota. 19,294 of 28,295 `.venv` files were evicted to stubs; `import
thermosteam` hung for over 7 minutes and the suite went from 11 s to a 10 minute
timeout.

**Resolved.** The project now lives at `~/projects/process_simulation`, outside
iCloud, with **zero dataless files**. `.venv` was rebuilt (biosteam 2.53.11,
pytest, pyyaml, mcp 2.0.0) and both MCP servers were re-registered and report
Connected. Suite is back to ~11 s.

Risk 5 was re-tested there and **stands**; see the 08-27 revised spec. The
eviction changed the failure mode, not the outcome.

## Decisions waiting on you

- [x] ~~**Merge `m2-risk2-shortcut-config` into `main`?**~~ **DONE 08-31.**
      It had become the de facto trunk: 21 commits, not 5, and `main` was that
      far behind. Fast-forwarded, so nothing was rewritten, and
      `rule-schema-requires` turned out to be already contained.
- [ ] **1. Switch the M2 bring-up case to benzene/toluene?**
      Methanol/water/glycerol was chosen when both sides were shortcut methods
      and will not solve rigorously. Benzene/toluene solved rigorously in
      seconds. *Recommend: yes*, keep methanol/water as a later stress case.
- [ ] **2. M2 transport — live subprocess, recorded fixtures, or both?**
      Solve times of minutes make a live adapter impractical in the suite.
      *Recommend: both* — fixtures for a hermetic suite, live behind an opt-in
      marker, since fixtures alone prove nothing about the protocol.

## The road

### [x] M1 — screen, design, verify · COMPLETE, MERGED
Feed in, nine screening rules, column design, verification out. One simulator,
binary keys, no flowsheet.
- [x] All 12 tasks
- [x] Five success criteria checked by hand, not inferred from the suite
- [x] Re-verified live 08-27: H2/methane INFEASIBLE citing R-04;
      methanol/water/glycerol designs a column, all five checks pass

### [x] EXTRA — rule schema extension · COMPLETE, MERGED
Unplanned, built 08-27. Rules can now declare the calculation they still need
instead of only a verdict.
- [x] `requires` + `limitations`, both defaulting empty — additive
- [x] Fourth verdict `undetermined`, distinct from `unknown`; rejected at load
      if it names no calculation
- [x] R-09 stops asserting refrigeration before the pressure search that could
      refute it has run
- Done now because it makes M4 a default-valued field instead of a migration

### [ ] M2 — rigorous cross-validation · BLOCKED, NOT PLANNED
How far is sepsyn's shortcut design from a rigorous answer? DWSIM's rigorous
column is the REFERENCE, not a peer, so the gap measures shortcut error.
- [x] Scope A ruled
- [x] Risk 2 resolved — `ShortcutColumn` spec inputs are public *fields*
- [x] Found: the old acceptance criterion could not fail — recoveries impose
      the products, leaving one free number
- [x] Risk 5 **re-tested 08-30 on a healthy machine and CONFIRMED** — genuine
      non-convergence, not a timeout artifact. M2 needs a new acceptance case;
      benzene/toluene is the candidate
- [ ] Risk 1 OPEN — the adapter's transport, and the real work
- [ ] Not planned into tasks

Every gap found on 08-27, and what it turned out to be:

| apparent gap | true cause | corrected |
|---|---|---|
| stages, 43 % | actual vs theoretical stage basis | 16.9 % |
| stages, 16.9 % | absolute reflux vs matched R/Rmin | 6.5 % |
| condenser duty, 58 % | partial vs total condenser | 6.3 % |
| Rmin, 24 % (binary) | **unexplained** | — |

The lesson: every large disagreement but one was a configuration or definition
mismatch, not physics. **The harness must assert configuration equivalence, not
just compare numbers.**

### [x] Workflow steps from the binary heuristics list · COMPLETE
The 41 step design sequence, folded into the rule tables. sepsyn covered about
20 of the 41 to begin with; the gaps named on 08-30 are now closed.
- [x] **Item 1** — reboiler side pressure rule (R-10) and thermal limit (R-11);
      record gains `bottoms_T_at_column_P` and `steam_T`; `safe_eval` now
      permits arithmetic so thresholds can be expressed against another
      property in the rule file. 34 engine tests pass
- [x] **Item 2** — verification checks 39, 40, 41 done. Caught a real defect on
      first run: BioSTEAM defaults to a PARTIAL condenser and the adapter never
      set it, so every design had a vapour distillate. Now stated explicitly.
      Energy tolerance measured at a constant 5.00 % model margin across four
      cases, set to 6 %. **152 tests passing**
- [x] **Item 3** — feed condition q, steps 15 to 17. `sepsyn/feed_condition.py`,
      `ColumnSpec.feed_q` to impose it, `ColumnResult.feed_q` to record it,
      `--feed-q` on the CLI, and the q printed with every design whether or not
      it was imposed. **171 tests**
- [x] **Item 4** — equipment choices, steps 22 to 25, in their OWN table
      (`equipment_rules.yaml` + `equipment.py`). Not in rules.yaml: a screening
      rule feeds overall_verdict where worst-wins, so a preference for packing
      dropped in there could outrank a feasibility finding. This is Section 13's
      "separate screening rules from design rules", built. **197 tests**
- [x] **Item 5** — VLLE check, step 6. `sepsyn/lle.py`, rule R-12,
      `has_two_liquid_phases` on the record. **210 tests**
- [x] **Item 6** — thin skill at `skill/SKILL.md`, symlinked to
      `~/.claude/skills/sepsyn`. Runs the CLI, reimplements nothing.
      **213 tests**

Note: item 5 was the VLLE check in the 08-30 plan, and an earlier revision of
this file dropped it and promoted the skill into its place. That looks like an
omission rather than a decision, so both were built.

#### What items 3 to 6 found

| finding | where | consequence |
|---|---|---|
| thermosteam returns a bubble point ABOVE the critical point without complaint — benzene/toluene at 200 bar gives 673 K against a Tc of 562 K | feed_condition | extrapolation guarded explicitly before and after the solve; the solver will not raise |
| feed enthalpy from a bare `Stream.H` keeps the phase the stream was built with, so a 500 K vapour reads as a liquid | feed_condition | q's SIGN inverts. Feed enthalpy now comes from a TP flash |
| the condenser type was a hardcoded constant in the adapter while the rules recommended one | equipment | moved onto ColumnSpec and decided BEFORE the column is built; the record and the run can no longer disagree |
| BioSTEAM reports Diameter in FEET | equipment | 3.8 read as metres would make the small-diameter branch unreachable for every column ever designed. Converted in the adapter, pinned by a test |
| thermosteam's LLE returns two phases of IDENTICAL composition for a miscible mixture | lle | detecting on phase AMOUNTS reported ethanol/water as splitting. Criterion is composition DIFFERENCE |
| **E-24b (packing below 0.6 m) was UNREACHABLE via BioSTEAM — now FIXED** | equipment | BioSTEAM hard-clamps diameter at 0.914 m inside `compute_tower_diameter`. The adapter now recomputes the true hydraulic diameter from BioSTEAM's own correlations, both sections, and carries the floored value separately as `biosteam_reported_diameter_m` since the COST belongs to that one |
| BioSTEAM converts m to ft with **3.28**, not 3.280839895 | adapter | converting back with 0.3048 does not round-trip and lands 0.026 % low. Small, but it was the whole gap between the recomputed and reported diameters, and would have read as an error in the correlation rather than the unit |
| **UNIFAC predicts a FALSE miscibility gap for water/glycerol** | lle | not fixable by any threshold — it is indistinguishable from a true split by width, point count and dx alike. See below |

#### The water/glycerol false positive, and what was done about it

Panel of eight pairs at 1 atm, 49 compositions each:

| pair | truth | points | width | max dx |
|---|---|---|---|---|
| Water/n-Butanol | SPLITS | 20 | 0.42 | 0.510 |
| Water/Benzene | SPLITS | 48 | 0.94 | 0.995 |
| **Water/Glycerol** | **miscible** | **10** | **0.22** | **0.493** |
| Ethanol/Water | miscible | 0 | 0.00 | 0.000 |
| Methanol/Water | miscible | 0 | 0.00 | 0.000 |
| Methanol/Glycerol | miscible | 0 | 0.00 | 0.000 |
| Benzene/Toluene | miscible | 0 | 0.00 | 0.000 |
| Ethanol/Benzene | miscible | 0 | 0.00 | 0.000 |

Seven of eight correct; the eighth sits inside the true-positive range on every
metric. The error is in the activity model, not the search. Two consequences:

1. **R-12 is `caution`, not `undetermined`.** Undetermined blocks `--design`,
   and blocking on a false alarm at this rate is worse calibrated than flagging
   it with the pair named. The measurement is in the rule's `limitations`, so a
   reader of the REPORT sees it, not only a reader of the source.
2. **The search follows the KEYS when they are known** — same precedent as
   `bottoms_T_at_column_P`. On the milestone feed the NON-KEY pair
   water/glycerol trips the false gap while the key pair methanol/water does
   not, so the acceptance case still reads FEASIBLE and still designs. The
   broader no-keys behaviour is pinned by its own test, false positive included.

Open question for you: is the water/glycerol false positive worth chasing? A
UNIFAC-LLE parameter set or a switch to NRTL for aqueous polyols would fix it,
but that is a thermodynamics change with reach well beyond R-12.

### [ ] M3 — sequencing multicomponent trains · NOT STARTED, NO SPEC
Today the tool stops at one column and says so. The "NOT SPECIFIED … separate
products need a second column" note is this milestone announcing itself.

### [ ] M4 — heuristic database & retrieval · NOT STARTED, NO SPEC
Store separation heuristics as conditional guidance that triggers a
calculation, never as answers.
- [x] Schema ready ahead of it (see EXTRA)
- [ ] Content being drafted separately
- [ ] Needs its own spec

### [ ] M5 — LLM interface · NOT STARTED, NO SPEC
Wrap the library as an agent or MCP server. The core deliberately has no LLM in
it, so this is a wrapper, not a rewrite.

### [ ] M-B — simulation-direction comparison · DEFERRED BY CHOICE
Specify the column, compare predicted purities. Nothing imposed either side.
- [x] Confirmed available: BioSTEAM `MESHDistillation` takes the same inputs as
      DWSIM's rigorous column
- [ ] Deferred — better test, roughly twice the milestone, so it gets its own

## Where things live

| | |
|---|---|
| `main` | current, and now the trunk. 60 commits |
| Remote | `github.com/ananay0306-alt/sepsyn`, public, MIT |
| Specs | `docs/specs/` (was `docs/superpowers/specs/`). 08-22 M2 spec marked superseded, kept as evidence log; plan from the 08-27 revision |
| Demo | `./demo.sh`, eight beats, pauses between them |
| Skill | `skill/SKILL.md`, symlinked to `~/.claude/skills/sepsyn` |
| Probe flowsheet | `../sepsyn_m2_shortcut_probe.dwxmz`, opens in the DWSIM GUI |
| Written for review | `~/Desktop/dwsim_memo/Binary_Distillation_Given_Required_Derived.pdf`, current. Two earlier versions superseded, see below |

## Published 2026-08-31

Public, MIT, `main` as default. `docs/` was 39 percent of the repository and
larger than the source; the milestone plan, the SDD ledger and the session
handoff were removed as process exhaust that says nothing about distillation.
Removed with `git rm`, not a history rewrite: nothing is sensitive, and the
commit messages carry the measured findings. Proportions are now source 40,
tests 39, docs 13.

Added so a clone can actually run: README, `requirements.txt` pinned to the
versions every finding was measured against, MIT `LICENSE`, and a `demo.sh`
that finds an interpreter instead of assuming `../.venv` (which is outside the
repo root in this working copy).

`STATUS.md` is public. It reads as internal notes, deliberately. If that stops
being wanted, split the findings into `FINDINGS.md` rather than deleting.

## Review 2026-08-31: the ordering was wrong, and so was the code

Raised in review, and it invalidated both written documents plus a live number.

**Relative volatility cannot be screened before the pressure is settled**,
because alpha is a property of a pair AT a condition. Phase one depended on the
output of phase two. The screening code had inherited the same order and
evaluated alpha at the FEED pressure while the column was designed elsewhere:

| propane / n-butane | alpha |
|---|---|
| screened at feed pressure, 1.01 bar | 6.100 |
| at the real column pressure, 13.69 bar | 3.383 |
| error in the reported screening number | **80.3 %** |

Larger than the 58 percent condenser discrepancy this project exists to
prevent. Fixed: `resolve_column_pressure` settles it first and returns three
distinct outcomes, `specified` / `derived` / `fallback`, and both `screen()` and
`design_if_feasible()` call it so they cannot diverge. `--column-P` added.

**A specified value DISABLES its heuristic**, it does not skip it. If the user
gives a pressure, "start at one atmosphere and work upward" never runs at all.
That is the reviewer's second point and it forced the document restructure: the
steps had been classified by what they DO and never by where their values COME
FROM.

**Optimisation is out of the design sequence.** Economic reflux and heat
integration answer a different question (which of the columns that work is
cheapest), need cost data nothing else needs, and can be skipped without
leaving a gap. A step that can be skipped without leaving a gap is not part of
the procedure.

Documents, in order, each superseding the last:

| Document | Status |
|---|---|
| `Binary_Distillation_Heuristics.pdf` | superseded. 41 steps as one numbered sequence |
| `Binary_Distillation_Design_Graph.pdf` | superseded. Gates, triggers, records. Still put screening before pressure |
| `Binary_Distillation_Given_Required_Derived.pdf` | **current.** Classified by provenance; pressure precedes alpha; optimisation removed |

Open from the same review: a point about condenser and reboiler types that
could not be transcribed clearly. Ask before acting on it.
