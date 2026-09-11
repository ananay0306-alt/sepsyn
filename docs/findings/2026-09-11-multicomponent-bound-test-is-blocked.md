# The multicomponent bound test cannot settle the BioSTEAM disagreement

**Date:** 2026-09-11
**Status:** NEGATIVE RESULT. The experiment was run, and it does not work.
**Bears on:** the open 2x disagreement from
`2026-09-10-the-falling-rmin-is-the-feed-condition.md`

## What was attempted

The binary bound test succeeded: a rigorous DWSIM benzene/toluene column at 20,
30 and 45 stages came down 222 to 146 to 129 kmol/hr onto our computed 124.88,
approaching from above and never crossing. See
`2026-09-10-vmin-is-a-real-bound.md`.

The obvious next step was the same test on the four-component alkane column,
because that is where our V_min and BioSTEAM's disagree:

| | V_min, kmol/hr | Rmin |
|---|---|---|
| ours | 20.357 | 1.0357 |
| BioSTEAM `ShortcutColumn` | 15.493 | 0.5339 |

Propane 10, n-butane 20, n-pentane 60, n-hexane 10 kmol/hr at 330 K, propane
from n-butane at 13.694 bar, 99 % recoveries, Peng-Robinson,
Napthali-Sandholm, feed at 0.7 of the stage count.

## The measurement

| theoretical stages | converged | V, kmol/hr | R | x ours | x theirs |
|---|---|---|---|---|---|
| 20 | yes | 214.26 | 20.21 | 10.5 | 13.8 |
| 30 | yes | 95.96 | 8.50 | 4.7 | 6.2 |
| 35 | no, max iterations | | | | |
| 40 | no, max iterations | | | | |
| 45 | no, 283 s timeout | | | | |
| 50 | no, max iterations | | | | |
| 60 | no, max iterations | | | | |

## Why it fails, and it is not the convergence

The convergence failures are the smaller problem. The real one is that the
experiment was under-powered by an order of magnitude, and that was knowable
before it was run.

**The effect being measured is 1.3x.** Our V_min against BioSTEAM's, 20.357
against 15.493.

**The unexplained gap on this column is 10x.** At 20 stages the rigorous solve
wants 214 kmol/hr where the shortcut chain predicts about 20.

A measurement cannot resolve a 1.3x difference while sitting inside a 10x
unattributed error. Even a converged point at 40 stages would have landed
several times above both candidates and discriminated between neither.

The binary test worked precisely BECAUSE there was no unexplained gap there:
DWSIM landed at 1.032x our number at 45 stages, so the bound could be checked
against it directly.

## What the run did establish

**The 810 kW condenser duty is reproducible.** The diagnostic at 20 stages
returned Qc = 810.158 kW, matching the figure recorded on 2026-09-09 to the
watt, from a flowsheet built fresh by a different code path. That measurement
is therefore real and repeatable rather than a one-off setup error.

**The configuration is not the cause.** Checked explicitly on the converged
20-stage run:

- mass balance 100.00 kmol/hr in, 100.00 kmol/hr out, exactly
- condenser spec: component recovery, Propane, 99 %, as requested
- reboiler spec: component recovery, N-butane, 99 %, as requested
- propane to distillate 2.75 of 2.778 mol/s, which is 99.0 %
- n-butane to bottoms 5.500 of 5.556 mol/s, which is 99.0 %
- distillate at 313.77 K, which is propane saturation at 13.694 bar
- latent heat 13.613 kJ/mol against a distillate 98 % propane

So DWSIM is performing the requested separation, and the duty-to-vapour
conversion `V = Q / lambda` is sound. The 10x gap is somewhere else.

## What is NOT concluded

**Nothing about which V_min is correct.** The two converged points extrapolate
toward the low twenties, which would favour ours, and that is explicitly NOT
reported as a result. Two points and an assumed trend is the kind of claim this
project exists to avoid. The question stays open exactly as it was.

**Nothing new about the 810 kW gap** beyond its reproducibility. The three M2
conventions remain unpinned: feed stage numbering, whether a stage count
includes the condenser and reboiler, and the property package mismatch against
BioSTEAM's defaults. Any of them could carry a factor of this size.

## What would actually work

Not another bound test on this column. The order is the other way round:

1. **Explain the 810 kW first.** That is M2's unfinished business and it now
   blocks M6 as well. Pin the feed-stage convention and the stage-inclusion
   convention by an empirical sweep, and match the property packages.
2. **Then** repeat the bound test, once the residual gap is small enough that a
   1.3x difference is visible inside it.

A cheaper intermediate: find a THREE component feed with only a trace of heavy
non-key, where the disagreement still appears but the rigorous solve converges
as readily as the binary did. The heavy non-key fraction is the variable that
matters, so it should be swept rather than jumped.

## The process lesson

The resolving power of a comparison should be checked against the known
uncertainty BEFORE the comparison is run. The 9.3x gap on this exact column was
already recorded in `2026-09-09-underwood-rmin-falls-with-non-keys.md`. Reading
it first would have predicted this outcome without spending the solver time.
