# sepsyn milestone 1 — handoff

**Written 2026-08-22 after Task 8 passed acceptance test 1; updated the same
day after Task 8's review and Tasks 9-11.** Branch `milestone-1`, 92 tests passing.

The full SDD ledger (13 rulings, 15 deferred minors) is copied alongside this
file as `2026-08-22-sdd-ledger.md`. It originally lived in `.superpowers/`,
which is gitignored — copying it here is deliberate, so the decisions survive
the workspace being cleaned.

## Where things stand

| Task | State | Fix rounds |
|---|---|---|
| 1 Types | complete | 0 |
| 2 Property lookups | complete | 3 |
| 3 Supercritical + PropertyRecord | complete | 1 |
| 4 Azeotropes | complete | 2 |
| 5 Alpha at bubble point | complete | 1 |
| 6 Rule table + evaluator | complete | 1 |
| 7 Evaluate all rules | complete | 1 |
| 8 Report + CLI + **acceptance test 1** | complete | 1 |
| 9 Simulator protocol + BioSTEAM adapter | complete | 0 |
| 10 Pressure rule + reflux sweep | complete | 0 |
| 11 Verification | complete | 0 |
| 12 **Acceptance test 2** + ambiguity flag + negative test | not started | |

**Immediate next action:** Task 12 — acceptance test 2, the ambiguity flag and
the negative test — with BASE `89ba49d`. This is the milestone.

## What Task 8 settled

Acceptance test 1 passes. `sepsyn --feed "Hydrogen:50,Methane:50" --T 298.15
--explain` prints Tc 33.1 K and 190.6 K against a 298.15 K feed, fires R-04
only, answers INFEASIBLE, and names PSA / membrane / cryogenic partial
condensation. It then lists the eight rules that did NOT fire with the values
tested.

Two things in that output are load-bearing and were fixed earlier, so do not
"tidy" them:

- **`has_azeotrope = None`** for a supercritical feed means *the search never
  ran*, not *no azeotrope exists*. Task 5 made this tri-state precisely so the
  record stops asserting knowledge it does not have. `False` would be a lie.
- **`min_alpha = None`** for a supercritical feed is why R-01 and R-02 cannot
  fire. `safe_eval` treats any comparison involving `None` as `False`, by
  design, so a missing property never fires a rule and never raises.
  But do NOT read `min_alpha is None` as "there is no equilibrium": it also
  means a one-component feed, a bubble-point solve that raised, or every pair
  skipped by the zero-fraction guard. Task 8's review found `report.py` doing
  exactly that. Branch on `n_supercritical_at_feed == n_components` when you
  need the strong claim.

## Facts established by probing that are NOT obvious from the code

These cost real time to discover. Anyone continuing should not re-derive them.

- **`Stream.vle(P, V=0.0)` cannot be used to read a vapour composition.** At
  V=0 the vapour phase holds zero moles, so every vapour mole fraction is 0.0.
  `MultiStream` also has no `.vapor`/`.liquid` attributes at all. Use
  `tmo.equilibrium.BubblePoint(chemicals).solve_Ty(z, P)`, which returns the
  incipient vapour. Pure-component `vle(P, V=0)` DOES work and is what
  `condensing_temperature` uses.
- **thermosteam changes an exception type at runtime.**
  `chemicals.CAS_from_any('Nonsense')` raises `ValueError` normally but
  `LookupError` once `tmo.settings.set_thermo(...)` has been called. It also
  swaps `chemicals.identifiers.pubchem_db` for an object lacking
  `autoload_main_db`. Both broke `resolve()` and both are now handled.
- **Measured reference values.** Ethanol/water azeotrope x = 0.894 at 351.4 K
  (literature 89.4 mol%, 351.3 K). Ternary methanol/water/glycerol bubble point
  349.2 K, alpha(MeOH/H2O) = 2.620. Methanol condenses at 337.63 K at 1 atm;
  ethylene/ethane at 169.38 K.
- **Glycerol pairs are not skipped.** Its incipient vapour fraction is ~1e-9,
  not 0, so `relative_volatilities` returns 3 alphas for the ternary feed, two
  of them ~1e4. Harmless: `min_alpha` still resolves to 2.6205, and a huge
  alpha correctly means "trivially separable".

## Hazards waiting in Tasks 9–12

- **SETTLED IN TASK 9: `ColumnSpec` takes recoveries, and nothing converts
  them.** BioSTEAM accepts recoveries natively —
  `product_specification_format="Recovery"` with `Lr`/`Hr`, exactly the two
  fields `ColumnSpec` carries — so the keys-only mole-fraction basis is never
  built. The plan's conversion was measured correct before being deleted; both
  routes give 0.99000. A DWSIM adapter must pass recoveries through its own
  native route too, and must NOT reintroduce a mole-fraction basis.
- **The tolerance on the basis test is load-bearing; do not relax it.** Reading
  a recovery as a keys-only mole fraction moves methanol overhead from 99.0000
  to 99.2020 kmol/hr — 0.002 in recovery. The plan asserted `abs=0.02`, forty
  times too loose to see it, and a first rewrite at `abs=0.005` still let the
  mutation pass. Recovery is exact by definition; `abs=5e-4` is deliberate.
- **`Simulator` leaks no BioSTEAM types.** No `Stream`, no `Unit` crosses
  `base.py`. That is what makes DWSIM a second file rather than a refactor.
- **`choose_pressure` uses `Chemical.Psat`, never a VLE call.** The plan used
  `s.vle(T=..., V=0.0)` then read `s.P`, which does not solve for pressure and
  returned exactly 101325.0 for every chemical — dead-coding the raise-pressure
  branch and telling the user 1 atm suffices for propane. If you touch this,
  re-check that three different chemicals give three different pressures;
  there is a test for exactly that.
- **`sweep_reflux` keeps failed points in the curve.** They carry
  `converged=False` and an error, mirroring `ColumnResult`. Do not "tidy" them
  out — the unbuildable region borders minimum reflux and is the interesting
  part. `best_point` filters them.
- **Clear `__pycache__` before every mutation run.** The harness silently
  reused stale bytecode: `1e-3` and `0.01` are both four characters, so a
  restored file matched the mutant's size and CPython's pyc check (source mtime
  + size, one-second granularity) served the old bytecode. The mutation never
  loaded and reported as *survived* — the same output as a mutation the tests
  caught, so it fails toward false confidence. Use
  `scratchpad/mutate.sh`-style handling: assert the edit changed the file, wipe
  every `__pycache__`, run `python -B`, and flag same-size edits.
- **`verify.py`'s two tolerances are set from measurements. Do not round them
  off.** `RECOVERY_TOL = 1e-3` sits between the 0.002 wrong-basis signature and
  BioSTEAM's 1.1e-16 actual error. `MASS_BALANCE_TOL = 1e-3` is the weaker of
  the two — no known defect signature, just measured 1e-6 closure — and is
  pinned by a 0.3% single-component test.
- **Task 12's ambiguity flag is the point of acceptance test 2**, not a nicety.
  The methanol/water/glycerol problem specifies only methanol purity; water and
  glycerol are never separated from each other. The tool must answer the literal
  question AND print that it did not separate them. Answering silently would be
  the failure the test exists to catch.
- **BioSTEAM imports in ~8 s, not ~70 s.** The earlier figure in this file was
  wrong; measured at 8.4 s on this machine. The full 69-test suite runs in
  about 9 s. If a run hangs, it is a hang, not the import.

## The pattern worth carrying forward

Twelve fix rounds across seven reviewed tasks, plus Task 8's review and two
vacuous tests caught inside Task 9 before commit. **Every single one** was
either a test that could not fail against the defect it named, or a value
asserting knowledge it did not have. Not one was a wrong formula or a chemistry
error. Task 9 added a third face of the same coin: **a tolerance wide enough to
swallow the defect the test was written for.** Whenever a quantity is exact by
construction — a recovery, a mass balance — assert it tightly, and set the
tolerance from a measurement of the wrong answer rather than by habit.

Task 10 added a fourth: **a test that never reaches the branch it names.** Both
of its planned tests passed against a `choose_pressure` that never computed a
pressure — one got the right answer for the wrong reason, the other returned
from an earlier branch. Assertion strength was not the problem; reachability
was. When a function has branches, pick inputs that provably land in each one,
and prefer a real measurement to decide which input does that. A defect that
survives because no test executes the line is invisible to every check aimed at
assertions.

The two plan defects so far (Task 4's vapour accessor, Task 10's pressure read)
share a signature worth naming: **a call that looks like it computes and
silently returns a default instead.** Both showed up as an implausibly uniform
number across unrelated inputs — every azeotrope search returning `[]`, every
chemical saturating at exactly 1.01325 bar. When a sweep of different inputs
gives suspiciously identical output, suspect the accessor before the chemistry.

The check that caught most of them: take the fix out, confirm the test now
fails, put it back. If the test still passes with the fix removed, it is not
testing the fix. Apply it to every new test in Tasks 9–12.

Two corollaries learned the hard way:

- **A verification carries the conditions it was run under.** `CAS_from_any`
  raising `ValueError` was verified — before thermosteam loaded. Six azeotropes
  were found at 51 scan points — all of them broad. Neither result bounded the
  case that actually mattered.
- **Break the specific thing whose failure you are testing.** My first attempt
  to prove a warning fired deleted `name_index`, which `CAS_from_any` also uses;
  the error came from the lookup, not the guarded block, and proved nothing.
