# sepsyn milestone 1 — handoff

**Written 2026-08-22, after Task 8 passed acceptance test 1.**
Branch `milestone-1`, 19 commits ahead of `main`, 55 tests passing.

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
| 8 Report + CLI + **acceptance test 1** | **implemented, NOT yet reviewed** | — |
| 9 Simulator protocol + BioSTEAM adapter | not started | |
| 10 Pressure rule + reflux sweep | not started | |
| 11 Verification | not started | |
| 12 **Acceptance test 2** + ambiguity flag + negative test | not started | |

**Immediate next action:** review Task 8 (BASE `02c49e8`, HEAD `83847b2`), then
dispatch Task 9 with BASE = the reviewed head.

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

- **Task 9's `ColumnSpec` takes recoveries, not mole fractions.** This is the
  single most important interface decision in the project. Recovery means the
  same thing in every simulator; mole fraction does not — BioSTEAM divides by
  the keys, DWSIM by the total stream, and that mismatch produced a 175% error
  in the earlier ETJ comparison. The adapter converts recovery to BioSTEAM's
  keys-only basis in one tested place.
- **Task 9 must not leak BioSTEAM types across the `Simulator` protocol.** No
  `Stream`, no `Unit`. That is what makes DWSIM a second file later rather than
  a refactor.
- **Task 12's ambiguity flag is the point of acceptance test 2**, not a nicety.
  The methanol/water/glycerol problem specifies only methanol purity; water and
  glycerol are never separated from each other. The tool must answer the literal
  question AND print that it did not separate them. Answering silently would be
  the failure the test exists to catch.
- **BioSTEAM import costs ~70 s** and is not cached between processes. Task 9's
  first test run will be slow. That is expected, not a hang.

## The pattern worth carrying forward

Twelve fix rounds across seven reviewed tasks. **Every single one** was either a
test that could not fail against the defect it named, or a value asserting
knowledge it did not have. Not one was a wrong formula or a chemistry error.

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
