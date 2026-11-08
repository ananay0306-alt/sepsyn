# The alkane bound test, rerun with the feed in the right place

**Date:** 2026-11-07
**Status:** PARTIAL. The 09-11 blocker is explained; the BioSTEAM question is
still open.
**Bears on:** `2026-09-11-multicomponent-bound-test-is-blocked.md`, the open
2x Rmin disagreement.

## What changed since 09-11

The 09-11 run placed the feed at 0.7 of the stage count, near the BOTTOM.
`2026-11-07-stage-conventions.md` measured the optimum for this column at
index 7 of 21, about 0.33. Wrong placement costs a lot here: at 21 stages the
feed at 14 needs 942 kW of reboiler duty against 580 kW at 7.

So most of the "unexplained 10x" was the feed. At 20 stages with the feed at
14, the 09-11 run measured V = 214 kmol/hr. At 21 stages with the feed at 7,
it is 59.6.

## The measurement

Propane/butane/pentane/hexane 10/20/60/10 kmol/hr, 330 K, propane from butane
at 13.694 bar, 99 % recoveries, Peng-Robinson, Napthali-Sandholm, 200
iterations, 300 s budget. V from the condenser duty, V = Q / lambda, as in the
binary test.

| stages | feed | converged | V, kmol/hr | x ours (20.357) | x BioSTEAM (15.493) |
|---|---|---|---|---|---|
| 21 | 6 | yes | 62.13 | 3.05 | 4.01 |
| 21 | 7 | yes | **59.56** | 2.93 | 3.84 |
| 21 | 8 | yes | 60.68 | 2.98 | 3.92 |
| 30 | 9 | no, timeout | | | |
| 30 | 10 | yes | **39.64** | 1.95 | 2.56 |
| 30 | 11 | yes | 39.89 | 1.96 | 2.57 |
| 45 | 14-16 | no, timeouts | | | |
| 60 | 19-21 | no, timeouts and max iterations | | | |
| 80 | 26-28 | no, max iterations | | | |

## What it shows

- **Nothing converged below either candidate**, so neither V_min is falsified.
- **V falls with stages, as a bound requires**: 59.6 to 39.6 from 21 to 30.
- **BioSTEAM's own 20-stage design is not buildable as designed.** It sized
  the column at R = 0.641; a rigorous 21-stage column doing the same split
  needs roughly three times that vapour. That is the -70 % condenser duty in
  the M2 comparison, seen from the other side.

## What is NOT concluded

**Which V_min is right.** At 30 stages the rigorous column is still 1.95x
above ours. The 1.3x difference between the candidates is not resolvable from
two points, and a fitted trend would be exactly the claim 09-11 refused to
make. Above 30 stages DWSIM does not converge within the budget at any of the
three feed placements tried.

## What would

1. Converge the 40 to 80 stage columns: more iterations, a longer budget, or
   initialising each solve from the previous converged profile, which the
   transport cannot do yet because it builds a fresh flowsheet per run.
2. Or the cheaper route 09-11 proposed: a three-component feed with only a
   trace of heavy non-key, swept upward, where the rigorous solve converges as
   readily as the binary did.
