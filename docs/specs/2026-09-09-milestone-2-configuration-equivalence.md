# sepsyn milestone 2 (second revision) — configuration equivalence, then cross-validation

**Status:** draft spec, not yet planned into tasks.
**Supersedes the SCOPE of** `2026-08-27-milestone-2-revised.md`. That document's
thesis is carried forward unchanged and its evidence is not repeated here.
**Ruled 2026-09-09:** staged bring-up, both transports, multicomponent as the
target.

## 1. Why the 08-27 scope needed revising

Two things happened after it was written.

**M3 landed.** The 08-27 spec was written when sepsyn was binary-only, so
"cross-validate against DWSIM" meant `BinaryDistillation`. That is no longer
where the risk lives. Every column in every sequence M3 ranks goes through
`ShortcutColumn`, whose error against a rigorous solution is entirely
unmeasured. The M3 result — that `easiest_first` beat `most_plentiful_first` by
5.1 % on the adversarial feed — rests on it completely.

**A probe on 2026-09-08 found that the hard part is not the comparison.** It is
establishing that the two columns being compared are the same column. Section 3
records what happened.

## 2. Thesis, carried forward

Unchanged from 08-27 and restated for multicomponent:

> How far is sepsyn's shortcut design from a rigorous stage-by-stage answer,
> and is that distance small enough to rank sequences on?

DWSIM's rigorous `DistillationColumn` is the REFERENCE, not a peer. The method
asymmetry is the point: a rigorous MESH solve is closer to truth than
Fenske-Underwood-Gilliland, so the gap measures shortcut error.

The 08-27 finding that reframes everything still stands: **agreement on an
imposed quantity is evidence of nothing.** Recovery specs impose the products,
so product agreement proves nothing and only the unimposed numbers — reflux,
duties, temperatures — can carry information.

## 3. What the 2026-09-09 probe established

A rigorous 4-component column was built live through `dwsim-mcp` against the
first column of M3's winning sequence: propane/n-butane/n-pentane/n-hexane at
10/20/60/10 kmol/hr, 330 K, 13.694 bar, 99 % recoveries, Peng-Robinson,
Napthali-Sandholm.

**Finding 1. Risk 5 does not recur on the multicomponent case.** The rigorous
column converges. This was the blocking unknown and it is answered: M2 is
viable on the target case.

**Finding 2. The stage basis is a hard trap, and it produces non-convergence
rather than a wrong number.** The column was first configured with 28 stages,
which is BioSTEAM's ACTUAL stage count — theoretical stages divided by an
O'Connell efficiency. DWSIM's rigorous column takes THEORETICAL stages, of
which there are 20. At 28 the solver returned `DCErrorStillHigh`. Correcting
the basis alone made it converge. This is the 43 % stage discrepancy from the
08-27 findings, reproduced live within minutes of reading the warning about it.

**Finding 3. Feed stage placement dominates the duties, and its convention is
unresolved.** With the feed at stage 14 of 20 the column converged in seconds
and reported 810 kW condenser duty against sepsyn's 71.2 kW. With the feed at
stage 6 — BioSTEAM's reported theoretical feed stage — the solver timed out
after 300 s. Since 20 − 14 = 6, the most economical explanation is that
BioSTEAM numbers the feed stage from the bottom and DWSIM from the top, in
which case stage 14 was the correct match. That is a hypothesis, not a result.

**Finding 4. The flowsheet cannot be safely mutated.** `disconnect_objects`
reported success and left the feed attached. The next solve ran with both the
old and the new feed stream connected, producing 55.55 mol/s of product from a
27.78 mol/s feed — exactly double — with entirely plausible-looking
compositions and temperatures. Nothing in the result flagged it; only a mass
balance caught it.

**Finding 5, and the reason this spec exists.** The 11 × duty gap in finding 3
CANNOT currently be attributed. It may be shortcut error, or a feed-stage
convention mismatch, or a stage-inclusion mismatch. Reporting it as shortcut
error would repeat exactly the 08-27 mistake, where a 58 % and a 43 %
disagreement both turned out to be bookkeeping.

## 4. The revised scope

**The first deliverable is a configuration-equivalence harness, not a
comparison.** The comparison is nearly trivial once the conventions are pinned,
and meaningless before.

The harness asserts that two columns are the same column before it will report
any gap between them. If an assertion cannot be made, it reports that it cannot
be made rather than reporting a number.

That is the same discipline the rest of the tool already applies: a rule that
cannot be evaluated says so instead of guessing.

## 5. The three conventions to pin

Each gets a test that fails loudly if the convention changes underneath.

| # | Convention | Evidence | How to pin it |
|---|---|---|---|
| 1 | **Stage basis.** Theoretical or actual | Finding 2. 28 vs 20 caused non-convergence | Assert the number handed to DWSIM equals BioSTEAM's `Theoretical stages`, never `Actual stages`. The adapter must not accept an ambiguous "stages" argument |
| 2 | **Feed stage numbering.** From the top or the bottom; 0- or 1-based; condenser counted or not | Finding 3. Flips convergence entirely | Determine empirically: build the same column at every feed stage and find which placement reproduces BioSTEAM's duties. Record the mapping as a tested constant, not a comment |
| 3 | **Stage-count inclusion.** Does a count of 20 include the condenser and the reboiler | Unresolved. BioSTEAM's 20 may be DWSIM's 22 | Determine empirically alongside convention 2, since the two are confounded and must be resolved together |

**Nothing else in M2 may proceed until all three are pinned by tests.** A gap
reported before then is uninterpretable, which is worse than no gap at all.

## 6. Transport

**Both, ruled 2026-09-09.**

Recorded fixtures keep the test suite hermetic and fast. The suite currently
finishes in under a minute and rigorous solves take minutes, so live solves
cannot live in the default run. One 300 s timeout was already observed in the
probe.

A live subprocess path runs behind an opt-in pytest marker. Fixtures alone
prove nothing about whether the adapter still speaks the protocol, which is
Risk 1 and the real work.

**Constraint from finding 4: the adapter builds a fresh flowsheet per run.** It
never reconfigures or reconnects an existing one. This is not a preference; a
mutated flowsheet produced a silently doubled feed.

## 7. Staged bring-up

**Ruled 2026-09-09.** Two stages, and the first is not the goal.

**Stage 1, benzene/toluene.** Binary, converges in seconds, and every number on
both sides is already known from the acceptance case. Its purpose is to get the
transport, the fresh-flowsheet discipline and the three conventions working on
a case where a mismatch is diagnosable.

**Stage 2, the four-component alkane feed.** The measurement that matters,
because it is the path M3 ranks on. Propane/n-butane/n-pentane/n-hexane at
10/20/60/10, the adversarial feed from Phase B.

Binary is a rung. Skipping it means a first disagreement with four candidate
causes and no way to separate them.

## 8. Acceptance criteria

M2 is done when all of the following hold, and not before.

1. The three conventions of section 5 are pinned by tests that fail if they
   change.
2. A fresh flowsheet is built per run, asserted by a mass balance on every
   comparison: total in equals total out. Finding 4 is the reason this is an
   assertion rather than an assumption.
3. Benzene/toluene reproduces the same products from both tools, and the
   unimposed numbers — reflux, condenser duty, reboiler duty, end temperatures
   — are reported as a measured gap with the configuration assertions listed
   beside them.
4. The four-component alkane column does the same.
5. The tolerance is stated as a measurement, not inherited. The 6.3 % condenser
   and 1.9 % reboiler agreement from 08-27 was measured under different
   configuration assumptions and may not survive convention pinning.
6. Where a gap cannot be attributed, the harness says so instead of naming a
   cause.

## 9. Not in scope

- The simulation direction, where the column is specified and purities are
  computed. That remains M-B, deferred by choice.
- Ranking whole sequences against DWSIM. M2 compares single columns; a
  sequence-level comparison needs every column in the train to converge and is
  a separate milestone.
- Any change to sepsyn's own designs. M2 measures; it does not correct.
- Property package matching. The probe used Peng-Robinson against BioSTEAM's
  defaults, and the two are not the same model. This is a fourth potential
  convention mismatch and it is explicitly deferred so it does not confound the
  three above; it must be named in every reported gap as an unattributed
  contributor.

## 10. Risks

1. **Conventions 2 and 3 are confounded** and may not separate cleanly. If the
   empirical sweep cannot find a feed-stage placement and stage-inclusion
   combination reproducing BioSTEAM's duties, the gap may be genuine shortcut
   error and the harness must report exactly that ambiguity.
2. **Property package mismatch is a fourth unattributed variable**, deferred in
   section 9 but present in every number M2 produces.
3. **A 300 s timeout was already observed.** The live path needs a timeout
   policy and must treat a timeout as an outcome, not an error.
4. **Convergence is sensitive to feed placement** in a way not yet understood:
   the badly-placed stage 14 converged in seconds and the nominally-correct
   stage 6 timed out. If that survives investigation it is itself worth
   reporting, because it means the rigorous reference is not uniformly
   available.
