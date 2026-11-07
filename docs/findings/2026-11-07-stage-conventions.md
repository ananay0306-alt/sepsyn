# The stage conventions, measured: BioSTEAM counts the feed from the top

**Date:** 2026-11-07
**Status:** SETTLED for a total condenser, on a binary and on the
four-component alkane column. Pinned in `sepsyn/simulators/conventions.py`.
**Bears on:** M2 Task 3; the 09-09 probe; the 09-11 blocked bound test.

## From the source

- **BioSTEAM.** `Theoretical stages` come from the McCabe-Thiele staircase
  (binary), which starts at the reboiler, or Gilliland (multicomponent), which
  counts the same way. The reboiler is a stage; a total condenser is not.
  `Theoretical feed stage` is written as `N - stripping stages` in both
  `_run_McCabeThiele` and `_run_FenskeUnderwoodGilliland`, so it counts from
  the TOP.
- **DWSIM**, through dwsim-mcp: the stage count includes the condenser (index
  0) and the reboiler (last index), 0-based from the top.

Prediction: DWSIM stages = BioSTEAM stages + 1, and DWSIM feed index =
BioSTEAM feed stage.

## The test

With the stage count fixed, the right feed location is the one that minimises
duty. That is a physical criterion and does not use BioSTEAM's duties, so the
convention is not being fitted to the thing it will later be compared with.

**Benzene/toluene** 60/40 kmol/hr, 298.15 K, 1 atm, 99 % recoveries.
BioSTEAM: N = 24, feed 13. DWSIM at 25 stages, Peng-Robinson,
Napthali-Sandholm:

| feed index | 9 | 10 | 11 | 12 | **13** | 14 | 15 | 16 | 17 | 18 |
|---|---|---|---|---|---|---|---|---|---|---|
| QR, kW | 1509.0 | 1458.6 | 1425.6 | 1405.6 | **1397.1** | 1401.9 | 1424.8 | 1475.7 | 1573.2 | 1752.3 |

Minimum exactly at BioSTEAM's 13. Every run converged and closed its mass
balance to 1e-8.

**Alkanes**, propane/butane/pentane/hexane 10/20/60/10 kmol/hr, 330 K,
propane from butane at 13.694 bar, 99 % recoveries. BioSTEAM ShortcutColumn:
N = 20, feed 6. DWSIM at 21 stages:

| feed index | 4 | 5 | 6 | **7** | 8 | 10 | 12 | 14 |
|---|---|---|---|---|---|---|---|---|
| QR, kW | 708.6 | 623.2 | 589.8 | **580.1** | 584.3 | 625.6 | 723.2 | 942.4 |
| solve, s | 7 | 32 | 35 | 21 | 42 | 8 | 8 | 5 |

Minimum at 7, one below Kirkbride's 6, on a shallow floor (1.7 % between
them). Kirkbride is an empirical correlation and one stage is within its
reach. Index 14, where the 09-09 probe converged, is 62 % worse than the
optimum.

## What this changes

1. **The 09-09 bottom-numbering hypothesis is refuted.** 20 - 14 = 6 was a
   coincidence. The probe also handed DWSIM 20 stages for BioSTEAM's 20, one
   short, because the condenser was not added.
2. **Stage 6 does converge** once the column has its 21st stage: 35 s, where
   the probe timed out at 300 s.
3. **The 09-11 bound test placed the feed at 0.7 of the column**, which on
   this column is the wrong end: the optimum is near 0.33. That is a candidate
   cause of its non-convergence above 30 stages, tested separately.

## The gap, now reportable on the binary

`sepsyn.crossvalidate.compare`, every configuration assertion holding:

| quantity | sepsyn | DWSIM | gap |
|---|---|---|---|
| condenser duty | 1087.4 kW | 1127.6 kW | -3.6 % |
| reboiler duty | 1451.2 kW | 1397.1 kW | +3.9 % |
| distillate T | 353.4 K | 352.9 K | +0.4 K |
| bottoms T | 383.1 K | 383.1 K | -0.1 K |

Unattributed in every number: BioSTEAM's default property model against
DWSIM's Peng-Robinson. Reflux is not compared because the transport does not
read DWSIM's back. This is the tolerance, measured: about 4 % on duties for an
ideal binary, with the signs opposite at the two ends.

## Not settled

A partial condenser is an equilibrium stage and may already be in BioSTEAM's
count. Not measured, so `dwsim_stage_count` refuses it.

## The gap on the alkane column, M2's actual target

Same harness, every assertion holding, DWSIM at 21 stages with the feed at 6:

| quantity | sepsyn | DWSIM | gap |
|---|---|---|---|
| condenser duty | 71.2 kW | 235.0 kW | **-69.7 %** |
| reboiler duty | 439.9 kW | 589.8 kW | **-25.4 %** |
| distillate T | 313.8 K | 313.8 K | 0.0 K |
| bottoms T | 402.6 K | 403.6 K | -1.0 K |

The shortcut UNDER-predicts both duties on the multicomponent column, against
4 % on the binary. This is reportable now in the sense that the configuration
is shown equivalent, but it is not attributed: the property package differs,
and BioSTEAM's ShortcutColumn reflux is built on its Rmin of 0.534, half of
sepsyn's own Underwood value of 1.036. The sign is the sign that disagreement
predicts. See `2026-11-07-the-alkane-bound-test.md` for the direct test.
