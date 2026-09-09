# The feed-stage convention cannot be determined on benzene/toluene

**Date:** 2026-09-09
**Status:** measurement complete, convention still UNPINNED
**Relates to:** M2 plan task 3; spec §5 convention 2

## What was measured

Benzene/toluene, 60/40 kmol/hr, 298.15 K, 1 atm, 99 % recoveries both ends.
BioSTEAM `ShortcutColumn` reports 25 theoretical stages and theoretical feed
stage 15. A rigorous DWSIM `DistillationColumn` was built at 25 stages,
Peng-Robinson, Napthali-Sandholm, with the feed at each candidate placement.

If BioSTEAM numbers from the bottom, DWSIM's equivalent is stage 25 − 15 = 10.
If from the top, it is stage 15. Both were run on a freshly built flowsheet.

| feed stage | condenser kW | vs BioSTEAM 1116.7 | reboiler kW | vs BioSTEAM 1482.0 |
|---|---|---|---|---|
| 10 (from bottom) | 1189.05 | **−6.09 %** | 1458.58 | **+1.61 %** |
| 15 (from top) | 1155.28 | **−3.34 %** | 1424.80 | **+4.01 %** |

Products were identical in both runs and equal to their specifications, as
expected: recovery specs impose them. Both runs closed their mass balance
exactly, 27.77778 mol/s in and out.

## The finding

**This case cannot determine the convention.** Stage 15 is closer on the
condenser, stage 10 is closer on the reboiler, and the summed absolute error is
7.4 % against 7.7 %. That is a tie, not a result.

The M2 plan anticipated the opposite failure, where no placement fits. Both fit,
which is worse for a different reason.

## Why benzene/toluene cannot answer it

The separation is easy and 25 stages is far more than it needs, so the column is
insensitive to where the feed enters. That is exactly what makes it a good
bring-up case and a useless discriminating one.

The four-component alkane column IS sensitive: the 09-09 probe measured an 11 ×
condenser duty difference between feed stages 6 and 14, and one of the two
placements failed to converge at all. The convention must be determined there.

## The consequence, and it is the sharper point

**The convention uncertainty is the same size as the quantity being measured.**
Shortcut error on this case is 3 to 6 % on the condenser. The spread introduced
by not knowing the feed-stage convention is 2.75 percentage points on the same
number. So a reported gap of "about 5 %" would be carrying an unattributed
contribution of comparable magnitude, and would mean very little.

This is the concrete justification for the harness built in M2 task 2, and for
why an assertion that cannot be CHECKED blocks a gap exactly as a failing one
does. Here we can see the reason directly rather than argue it: picking a
convention would move the answer by as much as the answer is worth.

## What must happen next

1. Determine the convention on the four-component alkane column, where the
   effect is 11 × rather than 3 percentage points.
2. Only then report a shortcut error for benzene/toluene, with the convention
   named.
3. `FEED_STAGE_ORIGIN` stays unset. No constant is invented from a tie.

## Also confirmed here

- A rigorous DWSIM column converges on benzene/toluene at 25 stages in seconds,
  at both candidate feed placements.
- The fresh-flowsheet discipline works: two independent flowsheets built from
  scratch produced identical products and exact mass balances, with no trace of
  the doubled-feed failure that a mutated flowsheet produced on 09-09.
- The 08-27 measurement of roughly 6 % condenser and 2 % reboiler agreement is
  independently reproduced at feed stage 10, on a different case, through a
  different transport.
