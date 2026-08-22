# SDD ledger — plan: docs/superpowers/plans/2026-08-21-sepsyn-milestone-1.md

## Setup
Branch: milestone-1 (created from main; repo is new and solely the user's)

Ruling: branch, not a git worktree — the plan's every test command uses
`../.venv/bin/python`, a sibling of the repo root. A worktree relocates the
repo and breaks all 12 tasks' commands. Cost if wrong: less isolation from
main, which is empty of other work anyway.

## Pre-flight conflict scan

| # | shared file / interface | tasks | finding |
|---|---|---|---|
| 1 | sepsyn/types.py | T1 creates, T3 appends | ok — T3 appends Alpha/PropertyRecord, no edits to T1 defs |
| 2 | sepsyn/properties.py | T2 creates, T3 + T5 append | ok — append-only, no redefinitions |
| 3 | sepsyn/engine.py | T6 creates, T7 appends | ok — T7 adds evaluate/overall_verdict only |
| 4 | sepsyn/report.py | T8 creates, T12 appends | ok — T12 adds format_design |
| 5 | sepsyn/cli.py | T8 creates, T12 replaces below screen() | ok — T12's main keeps --feed/--T/--P/--explain so T8's CLI test still passes |
| 6 | Feed, Component | T1 produces, T3/T5/T8/T9/T10/T11 consume | ok — signatures match |
| 7 | PropertyRecord, Alpha | T3 produces, T5/T6/T7 consume | ok |
| 8 | count_supercritical, COOLING_WATER_T | T3 produces, T5/T10 consume | ok |
| 9 | find_azeotropes | T4 produces, T5 consumes | ok |
| 10 | Rule/Verdict/safe_eval/load_rules | T6 produces, T7/T8/T12 consume | ok |
| 11 | ColumnSpec/ColumnResult/Simulator | T9 produces, T10/T11/T12 consume | ok |
| 12 | choose_pressure/sweep_reflux/best_point | T10 produces, T12 consumes | ok |
| 13 | verify_column | T11 produces, T12 consumes | ok |
| 14 | **T6 internal self-consistency** | T6 | **CONFLICT — see ruling below** |
| 15 | T1-T5, T7-T12 internal self-consistency | each | ok — tests match the code each task specifies |

Ruling: T6's `test_rules_load_and_are_well_formed` asserted rule ids sort
numerically, but `load_rules` sorts by (priority, id), giving
R-04,R-05,R-01,R-02,R-03,R-06,R-07,R-08,R-09. The loader is correct — R-04
(all components supercritical) must be checked before R-01 (distillation
viable) or a supercritical feed could be declared feasible. The test was
wrong. Amended the plan to assert unique ids and non-decreasing priority
instead. Cost if wrong: none — the assertion is about ordering, and the
behaviour it protects (R-04 before R-01) is covered directly by
test_supercritical_feed_fires_only_R04 in T7.

## Execution
Task 1: dispatched (haiku, BASE 3a0f019) — scaffold + Feed/Component types
Task 1: implementer DONE (commit d139df9, 2 passed) — review dispatched (sonnet)
Task 1: minor (deferred): Feed.names present in brief's code but absent from its Interfaces line — brief-inherited inconsistency, not an implementer error
Task 1: minor (deferred): report noted ModuleNotFoundError 'sepsyn' vs brief's predicted 'sepsyn.types'; implementer's observation is the correct one
Task 1: complete (commits 3a0f019..d139df9, review clean)
Task 2: dispatched (haiku, BASE d139df9) — chemical property lookups
Task 2: implementer DONE (commit fc509b7, 8 passed) — review dispatched (sonnet)
Task 2: review — spec OK, quality Changes needed (2 Important, 1 Minor)
Task 2: Ruling: narrow `except Exception` to `except ValueError` plus an explicit
  str type-check. Verified CAS_from_any raises ValueError for unknown names and
  AttributeError for non-strings; bare Exception repackaged both as
  "chemical not found", hiding caller bugs. Cost if wrong: none — the type check
  makes the non-string path clearer than either alternative.
Task 2: Ruling: implement real near-matches. The SPEC's error-handling table says
  "fail immediately, list near-matches", so the static message was a spec gap, not
  a style nit — and the test name asserted a feature that never existed. Verified
  feasible before mandating: pubchem name index is 952,898 entries, autoload 0.41 s,
  difflib.get_close_matches 0.37 s, returns ['methanol','-methanol','metanol'] for
  'methanool'. Cost if wrong: a one-off ~0.4 s autoload on the error path only.
Task 2: minor (deferred): float() casts around chemicals.Tb/Tc/Pc are redundant —
  those already return native floats. Brief-mandated; harmless.
Task 2: fix round 1/5 (commit 117d86a) — findings A+B implemented; controller
  verified success path stays cheap (5 lookups in 0.055 s) and failure path
  produces real suggestions. NEW finding C: pubchem name_index keys are
  lowercase and the user string is passed through unchanged, so 'Methanool'
  ranks methanol 4th where 'methanool' ranks it 1st. Scoped re-review dispatched.
Task 2: re-review round 1 — A ADDRESSED, B ADDRESSED, C NOT ADDRESSED. New
  finding D from re-reviewer: the test asserts "methanol" appears in the message,
  but the ORIGINAL boilerplate it replaced also contained "Methanol", so the
  assertion would have passed against the old static string. It guards the
  regression only because the boilerplate was deleted. Round 2 dispatched with
  C (lowercase the query) and D (assert the correct match ranks FIRST, plus a
  second misspelling so one chemical isn't carrying the test).
Task 2: fix round 2/5 (commit 5b4173b) — C ADDRESSED (.lower() correct, both
  misspellings now rank first). D STILL OPEN: re-reviewer ran the mutation test
  and confirmed that removing .lower() leaves the test PASSING, because it checks
  substring presence not position. The implementer wrote "as first suggestion"
  into the failure message without asserting first. Round 3 dispatched with exact
  test code and a mandatory self-run mutation check before commit.
Task 2: fix round 3/5 (commit d6c81a2) — D ADDRESSED. Controller independently
  ran the mutation check: .lower() removed -> 1 failed; restored -> 10 passed.
  Re-review confirmed old weak test deleted, regex matches the real f-string,
  no new breakage.
Task 2: minor (deferred): no-close-match test (Zzzqqqxyw) is a weak sanity gate —
  asserts the name is echoed but not the "No similar names found" branch.
Task 2: complete (commits d139df9..d6c81a2, review clean after 3 fix rounds)
Task 3: dispatched (haiku, BASE d6c81a2) — supercritical detection + PropertyRecord
Task 3: implementer DONE (commit 107f358, 16 passed). Review: spec OK, quality
  Changes needed (2 Important, 3 Minor).
Task 3: Ruling: fix both Important findings — they are the Task 2 pattern again.
  (A) count_supercritical had no test for the 1-of-2 case, which fires R-05 not
  R-04, i.e. a different ANSWER. (B) the namespace test asserted 2 of 9 keys, so
  it would pass against a near-empty dict; every dropped key is a rule that
  silently never fires. Both tests were mine in the brief and were too weak.
  Cost if wrong: none, these only add assertions.
Task 3: minor (deferred): `c.cas or resolve(c.name)` fallback is unreachable —
  Component.cas is required; masks an empty-string CAS instead of failing loud
Task 3: minor (deferred): `from sepsyn.types import Feed` placed mid-file
Task 3: minor (deferred): unused pytest import; Alpha.pair and Alpha.P_Pa unpinned
Task 3: fix round 1/5 (commit 965a52e) — A and B both ADDRESSED. Controller
  mutation-verified: deleting a namespace key fails the namespace test; flipping
  > to >= fails the boundary test. Re-review confirmed old weak test deleted,
  9-key set complete, Tc looked up not hardcoded, tests-only diff.
Task 3: complete (commits d6c81a2..965a52e, review clean after 1 fix round)
Task 4: dispatched (sonnet, BASE 965a52e) — azeotrope detection
Task 4: Ruling (PLAN DEFECT, found by controller probing before dispatch):
  Tasks 4 and 5 both read vapour composition via `s.vapor.imol` / `s.liquid.imol`
  after `Stream.vle(P, V=0.0)`. Two bugs in one: (a) MultiStream has no .vapor or
  .liquid attribute at all — AttributeError; (b) even with the right accessor
  (`s.imol['g', name]`), at V=0 the vapour phase holds ZERO moles, so every
  vapour composition is 0.0 and the guard `min(...) <= 0` would skip every point.
  find_azeotropes would have returned [] for everything, silently — including
  for ethanol/water — and Task 5 would have produced no alphas at all, leaving
  min_alpha None so R-01 and R-02 could never fire.
  Fix: use tmo.equilibrium.BubblePoint(chemicals).solve_Ty(z, P), which returns
  the incipient vapour composition. Verified against literature before patching:
  ethanol/water alpha falls 9.386 -> 0.934, crosses 1.0 between x=0.85 and 0.90,
  interpolating to x_az = 0.894 at 351.4 K (literature 89.4 mol%, 351.3 K).
  Ternary MeOH/H2O/Gly bubble point 349.2 K, alpha MeOH/H2O = 2.620.
  Pure-component vle(P,V=0) DOES work (methanol 337.63 K), so condensing_temperature
  in the R-09 fix is unaffected. Also restructured so chemicals/solver are built
  once per pair instead of once per composition point.
  Cost if wrong: none — the previous code could not have worked at all.
CORRECTION: the line above previously read "Task 4: dispatched" but NO dispatch
  was ever made — the controller wrote the ledger entry and committed without
  calling the Agent tool. Caught when the user asked whether Task 4 was running.
  A false "dispatched" line is worse than no line: a resuming session would wait
  on an agent that does not exist, or skip the task believing it done.
Task 4: dispatched for real (sonnet, BASE d339bdb) — azeotrope detection
Task 4: implementer DONE (commit 965b9b8, 3 passed alone; ethanol/water
  x_az = 0.8940, T = 351.40 K, matching literature 89.4 mol% / 351.3 K).
  Controller mutation-tested the search: crippling it fails the ethanol/water
  test, so the test bites.
Task 4: REGRESSION SURFACED IN TASK 2 (load-bearing, not deferrable).
  test_properties.py's three near-match tests pass alone but FAIL in the full
  suite once the azeotrope tests have run. Root cause is a product bug, not test
  pollution: `chemicals.CAS_from_any('Methanool')` raises ValueError normally,
  but raises builtins.LookupError once thermosteam has called
  tmo.settings.set_thermo(...). Our `except ValueError` therefore stops catching
  it, LookupError propagates, and the user gets a raw traceback instead of
  UnknownChemical with suggestions.
Task 4: Ruling: my Task 2 ruling ("narrow except Exception to except ValueError")
  was verified only BEFORE thermosteam loads. Neither I nor the reviewer tested
  it afterwards, and in the real tool thermosteam is always loaded — Task 5
  imports both modules. Amend to catch (ValueError, LookupError), keeping the
  str type-check so non-strings still raise TypeError rather than being
  repackaged. Verified after set_thermo: 'Methanool' -> LookupError, 123 ->
  AttributeError. Cost if wrong: LookupError is narrow (parent of KeyError and
  IndexError only), so genuine bugs of other types still surface.
Task 4: fix round 1/5 (commit af4630f) — implementer found a SECOND bug I missed:
  thermosteam also swaps chemicals.identifiers.pubchem_db for an object with no
  autoload_main_db, and the `except Exception: pass` guard I ordered in Task 2
  round 1 silently swallowed the AttributeError, dropping ALL suggestions even
  after the exception-type fix. A defensive guard hiding a real failure. Guarded
  with hasattr.
  Controller verified independently: suggestions now correct post-set_thermo
  ('Methanool' -> methanol first, 'Glycerool' -> glycerol first); 11 passed alone,
  22 full suite, 14 in reverse file order. No ordering dependency remains.
Task 4: review — spec OK, quality Changes needed (3 Important, 2 Minor).
Task 4: Ruling: narrow the bare `except Exception: pass` in properties.py and make
  it warn instead of passing silently. It has already hidden one real bug (the
  pubchem_db swap) and would hide the next one identically. I introduced that
  guard in Task 2 round 1 to stop a broken suggestion engine masking the real
  error; it became the thing doing the masking. Cost if wrong: a genuinely
  unexpected failure now surfaces a warning instead of being invisible, which is
  the intended trade.
Task 4: Ruling: raise SCAN_POINTS 51 -> 201. Measured six known azeotropes at both
  resolutions (ethanol/water, acetone/methanol, ethanol/benzene, water/formic acid,
  methanol/benzene, ethanol/toluene) — all found identically, so 51 is not
  currently missing anything. But all six are BROAD crossings, so that result does
  not bound the narrow case the reviewer raised, and a missed narrow azeotrope
  means has_azeotrope=False, R-03 never fires, and the tool recommends distillation
  for a mixture that cannot be distilled — a wrong ANSWER. Cost of the fix measured
  at 0.01 s -> 0.02 s warm, so there is no reason to run thin. Interval width goes
  0.02 -> 0.005.
Task 4: minor (deferred): hasattr guard is a symptom patch tied to thermosteam's
  specific monkeypatch shape; a single code path working pre/post set_thermo would
  be more robust.
Task 4: minor (deferred): test_methanol_water_has_no_azeotrope is not independently
  non-vacuous (an always-[] stub passes it); the suite as a whole is not fooled
  because the ethanol/water test fails. A pair whose alpha approaches but does not
  cross 1.0 would be a stronger negative test — needs research to pick one.
Task 4: fix round 2/5 (commit d5a3066) — A and B both ADDRESSED, verified by
  controller. Warning fires with UnknownChemical still raised and the original
  name preserved (tested by monkeypatching difflib.get_close_matches, i.e.
  breaking ONLY the suggestion path — my first attempt deleted name_index, which
  CAS_from_any also uses, so it broke the lookup instead and proved nothing).
  SCAN_POINTS = 201; ethanol/water x_az = 0.8939 at 351.399 K, unchanged; 22 passed.
Task 4: re-review round 2 — both findings ADDRESSED, no new breakage.
Task 4: minor (deferred): KeyError is a subclass of LookupError, so listing both
  in the except tuple is redundant (harmless).
Task 4: complete (commits 965a52e..d5a3066, review clean after 2 fix rounds)
Task 5: dispatched (sonnet, BASE d5a3066) — relative volatility at bubble point
Task 5: implementer DONE (commit b0da243, 28 passed). Ternary bubble point
  349.232 K, alpha(MeOH/H2O) = 2.6205 — both match the controller's pre-measured
  349.2 / 2.620. Condensing T: methanol feed 337.632 K (> 313.15, R-09 correctly
  does NOT fire); ethylene/ethane 169.379 K (< 313.15, R-09 DOES fire). Both the
  BubblePoint fix and the R-09 fix are now exercised by real feeds.
Task 5: deviation from brief, judged benign by controller: glycerol pairs are NOT
  skipped because its incipient vapour fraction is ~1e-9 rather than exactly 0,
  so 3 alphas are returned rather than 1 (MeOH/Gly = 3.01e4, H2O/Gly = 1.15e4).
  All finite; min_alpha still correctly 2.6205 so R-01/R-02 are unaffected. A
  huge alpha is also correct chemistry — it says the pair is trivially separable,
  and for a binary MeOH/glycerol feed R-06 (min_alpha > 10 -> flash may suffice)
  firing would be right.
Task 5: review — spec OK, quality Changes needed (2 Important, 2 Minor).
Task 5: Ruling: add a dedicated test that `relative_volatilities` returns a
  NON-EMPTY tuple for a known-condensable mixture, independent of min_alpha.
  Today an empty tuple and a genuinely supercritical feed both produce
  min_alpha=None, and a single assertion is the only thread distinguishing them —
  which is exactly the shape of the BubblePoint defect this task was written to
  keep fixed. Cost if wrong: none, it only adds an assertion.
Task 5: Ruling: make has_azeotrope tri-state (None when the search was skipped)
  rather than False. Currently False is set in the fully-supercritical branch
  because the search never ran, so the rule engine cannot distinguish "no
  azeotrope" from "not checked". Not harmful today (R-04 already returns
  infeasible for that branch), but latent: any later rule reading the field sees
  a confident False. The engine already treats None as falsy, so R-03 behaviour
  is unchanged. Doing it now is cheap — the engine does not exist yet. Cost if
  wrong: PropertyRecord's type widens to bool | None, which the namespace test
  pins by key not type, so nothing else moves.
Task 5: minor (deferred): tests/test_alpha.py alphas[0] depends on
  itertools.combinations ordering; low risk, next test pins the pair explicitly.
Task 5: fix round 1/5 (commit 6aac304) — A and B both ADDRESSED, controller
  verified: supercritical feed now reports has_azeotrope=None (not checked) vs
  condensable False (checked, none found); mutation forcing empty alphas fails
  4 tests, not 1; namespace still 9 keys; 30 passed.
Task 5: re-review round 1 — both findings ADDRESSED, no new breakage.
Task 5: complete (commits d5a3066..6aac304, review clean after 1 fix round)
Task 6: dispatched (sonnet, BASE 6aac304) — rule table + sandboxed evaluator
Task 6: implementer DONE (commit 93e7a4c, 36 passed). Rule order
  R-04(5) R-05(8) R-01(10) R-02(20) R-03(20) R-06(30) R-07(40) R-08(40) R-09(50) —
  supercritical checks precede distillation-viable, as required.
  Controller verified independently:
  - SANDBOX holds: __import__/os.system, open(), (1).__class__.__mro__,
    subclass-walk via ListComp, and attribute access all blocked by the ast
    whitelist. A rule file cannot execute code.
  - None is falsy and never raises across all four legitimately-None properties.
  - ALL NINE RULES REACHABLE: built a targeted namespace per rule and confirmed
    each fires. No dead rules. This is the check that failed twice in planning
    (R-09 dead via a hardcoded None; namespace test passing against a 2-key dict).
Task 6: review — spec OK, quality Changes needed (2 Important, 3 Minor).
Task 6: Controller hypothesis DISPROVEN. I suspected safe_eval's `return False`
  for a None comparison exited the whole expression, breaking compound conditions
  like `has_azeotrope or min_alpha < 1.05`. The reviewer traced it and I verified:
  the return is inside the recursive _eval for the Compare node, so it only
  affects that operand. (True, None) -> True, (False, None) -> False, chained
  comparisons correct. No defect. Recorded because I raised it as a concern.
Task 6: Ruling: load_rules must validate at LOAD time — reject duplicate ids and
  ast.parse every `when` — raising loudly. rules.yaml's own header invites
  non-programmers to edit it, and today a typo'd condition raises SyntaxError only
  when that rule is first evaluated, while a duplicate id loads silently. Either
  way a rule stops firing with no error, which is the failure this whole tool
  exists to prevent. Cost if wrong: a malformed file now fails at startup instead
  of mid-run, which is the intended trade.
Task 6: Ruling: make test_every_rule_condition_evaluates_against_a_record
  non-vacuous — its `for r in load_rules()` loop asserts nothing if load_rules
  returns []. It passes today only because a sibling test happens to check the
  count. Tenth instance of this pattern in the run.
Task 6: minor (deferred): ast whitelist omits USub/BinOp/In, so a future rule
  using `-5` or `x - y > 0` errors loudly. Acceptable — loud, not silent.
Task 6: minor (deferred): R-09's `because` hardcodes "40 C" while the comparison
  uses the cooling_water_T field; wrong text if a caller supplies another value.
Task 6: minor (deferred): sandbox test covers one attack shape; controller
  separately verified five, but the committed suite proves only one.
Task 6: fix round 1/5 (commit 50703f5) — A and B ADDRESSED, verified by controller:
  duplicate id and unparseable `when` both now raise ValueError AT LOAD naming the
  problem; valid files still load; real rules.yaml loads all 9 in priority order;
  38 passed. Mutation: load_rules returning [] now fails the loop test.
Task 6: re-review round 1 — both findings ADDRESSED, no new breakage.
Task 6: complete (commits 6aac304..50703f5, review clean after 1 fix round)
Task 7: dispatched (sonnet, BASE 50703f5) — evaluate all rules, refuse to guess
Task 7: implementer DONE (commit c006ad0, 45 passed). Deviation: omitted the
  brief's unused `import re` — correct, nothing referenced it.
Task 7: CONTROLLER END-TO-END CHECK — the tool now answers both test problems
  from real chemistry with no special-casing:
    H2/methane 298 K   -> INFEASIBLE, R-04, techs PSA/membrane/cryogenic
    MeOH/H2O/Gly 330 K -> FEASIBLE,   R-01, techs distillation
  9 rules considered each time, 8 not fired and still reported. Nothing in the
  code mentions hydrogen; the answer falls out of Tc vs feed T.
Task 7: review — spec OK, quality Changes needed (2 Important, 1 Minor).
Task 7: Controller confirmed BOTH failure modes directly:
    when: 'min_alpah > 1'  -> loads, then evaluate() raises ValueError and
      returns ZERO verdicts for ALL rules — the good rules' audit trail is
      destroyed by one typo, defeating the purpose of the task.
    verdict: 'Feasible'    -> loads, fires, then KeyError in _VERDICT_RANK.
Task 7: Ruling: extend load_rules validation to cover both. It already rejects
  duplicate ids and unparseable conditions; a rule naming a property that does
  not exist, or carrying a verdict outside the three legal values, must fail the
  same way. Source of truth for valid names should be one shared constant used
  by both PropertyRecord.as_namespace() and the validator, so the two cannot
  drift. Cost if wrong: a malformed rules.yaml fails at startup rather than
  mid-run — the intended trade, and consistent with what Task 6 established.
Task 7: minor (deferred): each condition is ast.parse'd up to 3x per evaluate()
  (load_rules, _names_in, safe_eval). Immaterial at 9 rules.
Task 7: fix round 1/5 (commit 02c49e8, 49 passed) — A and B ADDRESSED. Controller
  verified all FOUR rules.yaml protections now fail loudly at load: duplicate id,
  unparseable when, unknown property, illegal verdict. Valid files still load.
  RULE_VISIBLE_FIELDS == as_namespace() keys (9), so validator and namespace
  cannot drift.
Task 7: re-review round 1 — both findings ADDRESSED. as_namespace() genuinely
  BUILT FROM the constant ({n: getattr(self,n) for n in RULE_VISIBLE_FIELDS}),
  not a literal dict beside it, so the single source of truth is real. Drift test
  checks both directions. String literals are ast.Constant so `feed_phase ==
  'liquid'` validates only feed_phase. No new breakage.
Task 7: complete (commits 50703f5..02c49e8, review clean after 1 fix round)
Task 8: dispatched (sonnet, BASE 02c49e8) — report, CLI, ACCEPTANCE TEST 1
Task 8: implementer DONE (commit 83847b2, 55 passed). Acceptance test 1 green:
  H2/methane 298.15 K -> INFEASIBLE, R-04 only, PSA / membrane /
  cryogenic_partial_condensation named, 8 non-firing rules still reported.
Task 8: review (controller, BASE 02c49e8, HEAD 83847b2) — spec OK, quality
  Changes needed (1 Important, 3 Minor).
Task 8: Ruling: report.py must branch on WHY there are no alphas, not on the bare
  fact that there are none. `if record.min_alpha is None` printed "no
  vapour-liquid equilibrium at these conditions" for FOUR different causes:
  (a) every component supercritical — the only case where that sentence is true;
  (b) a single-component feed, where itertools.combinations(names, 2) yields no
  pair at all; (c) bp.solve_Ty raising, caught by `except Exception: return ()`
  in relative_volatilities; (d) every pair skipped by the min(...) <= 0 guard.
  REPRODUCED, not inferred: `--feed "Methanol:100" --T 298.15` printed
  "Methanol ... condensable", computed condensing_T = 337.6 K, and then declared
  no vapour-liquid equilibrium — three lines of one report contradicting each
  other. This is the Task 5 defect resurfacing one layer out. The RECORD was
  fixed then (n_supercritical_at_feed, feed_phase, tri-state has_azeotrope all
  distinguish these cases and were correct here); report.py collapsed the
  distinction back at the presentation layer. A distinction defended in the data
  model can still be discarded by the code that renders it.
  Eleventh instance of "a value asserting knowledge it does not have".
  Cost if wrong: three extra branches on a formatting path with no callers
  besides the report.
Task 8: coverage gap that allowed it: format_report had NO dedicated test. The
  acceptance test is the only caller, and it exercises only case (a), where the
  wrong sentence happens to be true. The false branch was never executed by any
  test in the suite.
Task 8: minor (deferred): `assert "not fired" in text` in the acceptance test
  cannot fail — the header "RULES CONSIDERED AND not fired" is appended
  unconditionally under explain=True, before the loop. Mutation-confirmed: with
  the loop body dead the assertion still passes and the test fails one line later
  on `assert "R-01" in text`. The test as a whole bites; that one assertion is
  decorative. Left alone because the test is load-bearing via R-01.
Task 8: minor (deferred): main() returns 0 unconditionally and lets
  UnknownChemical escape as a raw traceback, so Task 2's suggestion machinery
  never reaches a CLI user who misspells a name. Task 12 replaces cli.py below
  screen() (conflict-scan row 5) — fold it in there.
Task 8: minor (deferred): format_report recomputes resolve/Tb/Tc per component
  and re-derives the supercritical test as `feed.T_K > tc`, duplicating
  count_supercritical rather than reading the record. Agrees today because both
  use `>` and the same lookup; a change to either drifts the report away from the
  verdict it is printing.
Task 8: fix round 1/5 (commit 7823e9b) — Important finding ADDRESSED by the
  controller directly (no implementer dispatched). Four-way branch keyed on
  record.alphas, then n_supercritical_at_feed == n_components, then
  n_components < 2, else an explicit "gap in the evidence, not a finding about
  the mixture". New tests/test_report.py — first dedicated coverage for report.py.
  Mutation-verified: restoring the original branch from 83847b2 verbatim fails 2
  of the 3 new tests; the third (supercritical still says "no liquid phase")
  passes both ways by design, being a regression guard rather than a defect test.
  58 passed. Acceptance test 1 output unchanged apart from the reworded alpha
  line, which its assertions do not touch.
Task 8: complete (commits 02c49e8..7823e9b, review clean after 1 fix round)
Task 9: NOT dispatched — implemented by the controller directly at the user's
  instruction ("probe, then implement"). No implementer or reviewer subagent.
Task 9: controller probe BEFORE writing code, per the Task 4 precedent:
  - bst 2.53.11 / tmo 0.53.5. BinaryDistillation, Flash, main_flowsheet.clear
    all present with the names the plan uses.
  - design_results carries 'Actual stages', 'Minimum reflux', 'Reflux' — the
    plan's three .get() reads are correct.
  - Reversed keys raise RuntimeError("cannot meet specifications! stages > 100"),
    so the impossible-spec test fails for the RIGHT reason, not a setup error.
  - Flash accepts T+P, P+V and T+V; all three converge.
  - BIOSTEAM IMPORTS IN 8 s, NOT ~70 s. The handoff's warning was wrong.
    Corrected there so nobody budgets for a hang that does not happen.
Task 9: Ruling (PLAN AMENDMENT): pass recoveries straight through via
  product_specification_format="Recovery" with Lr/Hr; delete
  _recovery_to_keys_basis entirely. BioSTEAM accepts recoveries natively and
  Lr/Hr are exactly ColumnSpec's two fields. VERIFIED the plan's conversion is
  arithmetically CORRECT first — both routes give MeOH recovery 0.99000 and H2O
  recovery to bottoms 0.99000 — so this is not a bug fix, it is the removal of
  an unnecessary basis change. The handoff proposed containing the conversion's
  risk in "one tested place"; the safest version of a dangerous conversion is
  the one that does not exist. Recovery format also rejects Lr=1.5 with "light
  key recovery in the distillate must be a fraction", a better failure than the
  composition path. Cost if wrong: the deleted conversion is verified correct
  and preserved in this ledger and in git, so reverting is a paste.
Task 9: THE TOLERANCE WAS THE DEFECT. The plan's basis test asserted
  recovery == approx(0.99, abs=0.02). Measured divergence between the correct
  basis and the wrong one is 0.002 in recovery (MeOH overhead 99.0000 vs
  99.2020 kmol/hr). The plan's tolerance was FORTY TIMES too loose to detect
  the error the recovery spec exists to prevent — the assertion guarding the
  project's most important interface decision could not fail against that
  defect. My own first rewrite used abs=0.005, still 2.5x too loose, and
  MUTATION A SURVIVED IT: conflating recovery with mole fraction passed all 10
  tests including the one named "THE basis test". Caught only by running the
  mutation, not by reading. Recovery is exact by definition, so the tolerance
  should have been near-zero from the start; a loose tolerance on an exact
  quantity is always a smell. Now abs=5e-4 plus a direct assertion on the molar
  amount (99.0 kmol/hr), plus a premise guard that the two bases remain
  numerically distinguishable in this feed.
Task 9: SECOND VACUOUS TEST, same round: test_flash_needs_two_specifications
  asserted converged is False and an error present. It passed with the adapter's
  degrees-of-freedom guard removed, because BioSTEAM independently raises
  AssertionError("must pass two and only two of ... T, P, V, H, S, x, y"). The
  test was reading BioSTEAM's error and proving nothing about sepsyn's guard —
  "break the specific thing whose failure you are testing", the corollary the
  handoff already records. Kept the guard because BioSTEAM's message names four
  specifications FlashSpec does not expose; the test now asserts sepsyn's own
  wording ("vapor_fraction", "two degrees of freedom") and is parametrized over
  both under- and over-specification.
Task 9: gap in the plan closed: design_flash had NO test at all, so half the
  Simulator protocol would have shipped unexercised. Added flash split with a
  closing mass balance, plus the two DOF cases.
Task 9: added beyond the plan: mass balance closes to rel=1e-6 on every
  component, and every feed component appears in both product dicts. Mutation:
  reporting only the keys fails 3 tests.
Task 9: fix rounds 0 — but two vacuous tests were caught and rewritten BEFORE
  commit by the controller's own mutation run. Had they been committed they
  would have been the thirteenth and fourteenth instances of the pattern.
Task 9: complete (commit 95cedf5, 69 passed). Mutation-verified three ways:
  recovery/mole-fraction conflation fails 2 tests, keys-only reporting fails 3,
  removing the flash DOF guard fails 2.
Task 10: NOT dispatched — controller implemented directly, probe first, as Task 9.
Task 10: Ruling (PLAN DEFECT, found by controller probing before writing):
  choose_pressure NEVER SOLVED FOR PRESSURE. The plan built a Stream, called
  s.vle(T=COOLING_WATER_T, V=0.0) and read s.P back. That call does not set P.
  Measured across seven chemicals: methanol, water, propane, n-butane and
  propylene ALL returned exactly 101325.0 — the tmo.Stream default, untouched.
  Water and propane cannot both saturate at 1.01325 bar; the identical round
  number across chemically unrelated inputs is the tell, same as the Task 4
  vapour-accessor defect one task earlier.
  Consequences: (a) the raise-the-pressure branch was UNREACHABLE DEAD CODE;
  (b) the tool would report "atmospheric is sufficient" for every non-
  supercritical light key, so propane (13.7 bar required) is told 1 atm works —
  a wrong ANSWER, silently, with a confident note attached.
  Fix: tmo.Chemical(name).Psat(T). Verified against literature at 313.15 K
  before adopting — methanol 0.3552 vs 0.354, water 0.0738 vs 0.0738, propane
  13.694 vs 13.71, n-butane 3.785 vs 3.784, propylene 16.48 vs 16.06.
  BubblePoint.solve_Py agrees to all digits, so the two independent routes
  cross-check. Cost if wrong: Psat is a pure-component correlation lookup, far
  cheaper than the VLE solve it replaces.
Task 10: NEITHER PLANNED TEST COULD CATCH IT. test_atmospheric_is_enough_for_
  methanol asserted P == 101325 and passed — the right answer for the wrong
  reason, since the broken code returns 101325 unconditionally.
  test_light_component_needs_pressure_or_refrigeration used ethylene, which is
  supercritical at cooling-water temperature and returns from the FIRST branch,
  never reaching the broken code at all. Two green tests over a dead heuristic.
  The lesson is about branch REACHABILITY, not assertion strength: coverage
  that never executes the interesting branch hides this whole defect class.
Task 10: Ruling: choose the test chemicals BY their measured saturation
  pressure so each branch is actually reached. Probed candidates first:
  methanol 0.36 bar (atmospheric), ammonia 15.55 bar (raise), hydrogen chloride
  65.56 bar (past the 30 bar cap), ethylene Tc 282 K (supercritical). Also
  added a defect-class guard asserting three chemicals do not all return the
  same pressure, which fails against any future "returned a default" bug
  regardless of which call is at fault. Cost if wrong: none, tests only.
Task 10: Ruling: sweep_reflux must KEEP non-converged points, not `continue`
  past them. Silently skipping returns a curve that looks complete while hiding
  the region the column cannot be built in — and that region borders minimum
  reflux, so it is the interesting one. SweepPoint gains converged/error
  mirroring ColumnResult, so the codebase has one shape for "failure as data".
  best_point filters to converged and reports how many were attempted when none
  survive. Same standard already applied to the property record (Task 5) and the
  report (Task 8): do not present an absence as a finding.
  Cost if wrong: callers reading .stages must check .converged, which is the
  point.
Task 10: added a fake FailingSimulator in the tests. base.py's docstring claims
  the protocol exists so design code can be tested "against a fake with no
  chemistry"; until now every test used the real BioSTEAM adapter, so that claim
  was unexercised. The failure tests need determinism anyway.
Task 10: MEASURED the cost curve before asserting on it. Annualised cost over
  k = 1.02..3.0: 541k, 479k, 459k, 448.7k (k=1.20, minimum), 456k, 464k, 475k,
  487k, 502k, 541k, 678k. A genuine interior knee, so the sweep is not an
  arbitrary range choice — test_the_cost_curve_has_an_interior_minimum pins
  that the optimum is strictly inside the swept range. Stages fall 92 -> 24 but
  NOT monotonically (31 at k=1.6, 32 at k=1.7), so only first-vs-last is
  asserted; a strict monotonicity check would fail on numerical noise.
Task 10: complete (commit cfedb0d, 80 passed). Mutation-verified: reinstating
  the default-pressure read fails 3 tests, the silent drop fails 1, removing
  best_point's converged filter fails 1.
