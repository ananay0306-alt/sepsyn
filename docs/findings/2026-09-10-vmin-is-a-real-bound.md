# The minimum-vapour bound holds against a rigorous solve

**Date:** 2026-09-10
**Status:** VERIFIED against live DWSIM. This is the test M6 was designed around.
**Test:** `tests/test_vmin_bound_live.py` (opt in with `-m dwsim_live`)

## The claim being tested

sepsyn now chooses separation sequences by minimum vapour. If that number is
not a true lower bound, every sequence it picks is picked on a fiction.

A bound is falsifiable in a way a design comparison is not. Give a rigorous
column more and more stages at fixed recoveries and its reflux must fall,
approaching the minimum from ABOVE and never crossing it. One converged solve
underneath the bound disproves the implementation outright.

That is the unambiguous failure signal M2 lacked. Its 11x duty gap and 9.3x
reflux gap could each have been shortcut error, a feed-stage convention, a
stage-inclusion mismatch or a property-package difference, and a day of work
could not separate them.

## The measurement

Benzene/toluene, 60/40 kmol/hr, 353 K, 1.013 bar, 99 % recoveries,
Peng-Robinson, Napthali-Sandholm. A binary ON PURPOSE: it has no non-keys at
all, so nothing about heavy-non-key handling can confound the result.

Our V_min: **124.88 kmol/hr**, from alphas relative to toluene at the 362.5 K
bubble point and q = 1.0467.

| theoretical stages | rigorous vapour, kmol/hr | ratio to our V_min |
|---|---|---|
| 20 | 222.23 | 1.780 |
| 30 | 145.98 | 1.169 |
| 45 | 128.93 | **1.032** |

Rigorous vapour is derived from the converged condenser duty and the
distillate's molar latent heat, `V = Q / lambda`, the same derivation the 09-09
finding used to recover R = 4.95 from 258.2 kW.

**Monotonically decreasing, approaching the bound from above, never crossing
it, and within 3.2 % of it at 45 stages.** Both halves of the test pass.

## What this establishes

**Our Underwood implementation is correct**, at least where it is cleanest to
check. An independent rigorous MESH solve converges asymptotically onto our
number. That is much stronger evidence than agreement between two shortcut
methods, which can share an error.

**M6 rests on something verified.** The spec's assumption table listed "our own
Underwood implementation is correct" as unverified, with the note that nothing
rests on it until this test passes. It has passed.

## What it does NOT establish, stated plainly

**Only the binary case is verified.** The open disagreement with BioSTEAM --
ours 1.036 against their 0.534 on the four-component alkane feed -- involves
heavy non-keys, and this test deliberately has none. The binary is where the
two agree: our R_min of 1.081 sits beside BioSTEAM's operating R of 1.183.

**So the 2x disagreement is now localised rather than resolved.** It appears
only with heavy non-key material present. That is a much narrower question than
the one this milestone started with, and it is the next one worth asking.

**The property packages still differ.** Peng-Robinson against BioSTEAM's
defaults, as noted in the M2 spec.

## The configuration, which was itself a finding

The first run of this test SKIPPED rather than passed, and the distinction
matters: DWSIM sat on the solve for 5.4 minutes and the transport gave up.

Two causes, both fixed:

- **Feed placement.** At `n // 2` the column would not converge. At `0.7 * n`
  it converges in 19 seconds. This reproduces 09-09 finding 3, where feed at
  stage 14 of 20 converged in seconds and stage 6 timed out.
- **Imposed q.** Imposing the subcooled feed condition on the rigorous column
  contributed to the non-convergence. Taking the feed as it arrives is also the
  more honest comparison: our V_min is computed from the q this same stream
  actually has, so both sides describe one stream rather than two.

That the test skipped instead of passing is the behaviour that was wanted. A
verification which quietly reports success when its reference never converged
is worse than no verification.
