# The multicomponent gap is NOT a feed-stage convention mismatch

**Date:** 2026-09-09
**Status:** negative result, cause still unattributed
**Relates to:** M2 plan task 3; spec §5 convention 2; and it bears on M3

## What was measured

The first column of M3's winning sequence: propane/n-butane/n-pentane/n-hexane
at 10/20/60/10 kmol/hr, 330 K, 13.694 bar, keys propane/n-butane, 99 %
recoveries. BioSTEAM `ShortcutColumn` gives 20 theoretical stages, theoretical
feed stage 6, reflux 0.6407 against Rmin 0.5339, condenser 71.2 kW, reboiler
439.9 kW.

A rigorous DWSIM column was built at 20 stages, Peng-Robinson,
Napthali-Sandholm, at every even feed stage from 2 to 18, each on a freshly
created flowsheet, through `LiveTransport`.

| feed stage | converged | condenser kW | vs 71.2 | reboiler kW | vs 439.9 |
|---|---|---|---|---|---|
| 2 | no | — | — | — | — |
| 4 | yes | 374.0 | −81.0 % | 728.8 | −39.6 % |
| 6 | no | — | — | — | — |
| **8** | yes | **258.2** | **−72.4 %** | **613.0** | **−28.2 %** |
| 10 | yes | 317.1 | −77.5 % | 672.0 | −34.5 % |
| 12 | yes | 458.6 | −84.5 % | 813.4 | −45.9 % |
| 14 | yes | 810.2 | −91.2 % | 1165.0 | −62.2 % |
| 16 | yes | 2005.6 | −96.4 % | 2360.4 | −81.4 % |
| 18 | yes | 8889.0 | −99.2 % | 9243.9 | −95.2 % |

## The finding

**No feed stage reproduces BioSTEAM's duty.** The best placement, stage 8, is
still 3.6 × too high on the condenser. The M2 plan set a 25 % threshold for
accepting a placement as the convention; the closest is 72 % away.

So the feed-stage convention is **ruled out** as the explanation for the 11 ×
gap seen on 09-09. That gap is something else.

The sweep is not useless: the duty curve has a clear minimum at stage 8 and
rises steeply on both sides, reaching 125 × BioSTEAM's value by stage 18. DWSIM
is behaving sensibly. It simply needs far more reflux than the shortcut
predicts.

## What the numbers imply

BioSTEAM's 71.2 kW is internally consistent: with a distillate of 2.8056 mol/s
and reflux 0.6407, (R+1)·D·λ with propane's latent heat near 15 kJ/mol gives
about 69 kW.

DWSIM's best case, 258.2 kW on the same distillate, implies a reflux near 5.1.
That is roughly eight times the reflux BioSTEAM's Underwood/Gilliland pair
calls for, at the same stage count and the same recoveries.

## Candidate causes, none of them established

1. **The shortcut is genuinely much less accurate on this case.** A 10 %
   distillate cut taking the lightest of four components is a very different
   problem from benzene/toluene's 60 % binary cut, where the same comparison
   agreed within 6 %.
2. **Underwood's minimum reflux for a multicomponent feed.** The 08-27 findings
   already record "Rmin, 24 % (binary) — unexplained" as the one gap never
   accounted for. This may be the same defect, larger.
3. **The theoretical stage count may not be the right equivalent.** Whether
   BioSTEAM's 20 includes the condenser and reboiler is spec convention 3 and
   is still unpinned; it is confounded with this.
4. **Property package.** Deferred by the spec and named in every gap, but
   unlikely to produce 3.6 × on alkanes.

## What this means for M3, stated plainly

M3 ranks sequences on `ShortcutColumn` duties and costs. If the shortcut is
off by a factor of three on a column of this shape, the **absolute** costs M3
reports are not trustworthy.

The **ranking** may still be sound, because a systematic error affects all
sequences alike and the M3 result was corroborated by a second metric: cost and
total vapour load selected the same winner at 4, 5 and 6 components. But that is
an argument, not a measurement, and it is now the thing M2 must test.

The 5.1 % margin by which `easiest_first` beat `most_plentiful_first` should be
treated as provisional until this is resolved.

## What must NOT happen

No constant is invented. `FEED_STAGE_ORIGIN` stays unset, because the sweep
ruled the convention out rather than determining it. Setting it to "the value
that makes stage 8 work" would encode a coincidence and hide the real gap.

## Next

1. Compare Underwood's Rmin directly against the rigorous column's converged
   reflux, on both the binary and the multicomponent case. That isolates cause 2
   from cause 1.
2. Resolve convention 3 by running the same column at 20 and 22 stages.
3. Re-check whether the M3 ranking survives, since only the ranking is claimed.
