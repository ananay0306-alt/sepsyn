# BioSTEAM's minimum reflux falls as heavy non-key content rises

**Date:** 2026-09-09
**Status:** measured, reproducible, and it bears directly on M3
**Relates to:** M2 spec §2; the 08-27 "Rmin, 24 % (binary) — unexplained" entry

## The measurement

Same propane/n-butane split, same keys, same 13.694 bar, 99 % recoveries.
Only the heavy non-key content changes. BioSTEAM `ShortcutColumn`:

| feed, kmol/hr | total | Rmin | R | N theoretical |
|---|---|---|---|---|
| C3 10, C4 20 | 30 | **1.1324** | 1.3589 | 19 |
| C3 10, C4 20, C5 60 | 90 | 0.6121 | 0.7345 | 20 |
| C3 10, C4 20, C5 60, C6 10 | 100 | 0.5339 | 0.6407 | 20 |
| C3 10, C4 20, C5 180 | 210 | **0.3006** | 0.3607 | 21 |

Rmin falls by 73 % as the feed grows sevenfold with material that is heavier
than the heavy key and must all leave in the bottoms.

**Adding heavy non-keys makes the shortcut believe the separation is easier.**

## Why that is wrong

A rigorous DWSIM column on the four-component case, 20 theoretical stages,
Peng-Robinson, Napthali-Sandholm, converges at **R = 4.95**, derived from its
condenser duty of 258.2 kW with a distillate of 2.8056 mol/s and a measured
distillate latent heat of 15.48 kJ/mol.

That is **9.3 times** the shortcut's Rmin of 0.534, and 7.7 times its operating
R of 0.641.

## What it explains

- **Benzene/toluene agrees within 6 %.** It has no non-keys at all. Derived
  rigorous reflux 1.26 to 1.33 against BioSTEAM's 1.183, a 6 to 12 % gap, which
  is ordinary shortcut error.
- **The alkane column is off by 3.6 x on duty.** 70 % of its feed is heavy
  non-key.
- **The 08-27 observation.** Removing glycerol moved DWSIM's Rmin by −34 % and
  BioSTEAM's by +0.1 %. That is this defect seen from the other side: BioSTEAM's
  Rmin is not responding to non-keys the way a rigorous solve does.
- **It is not a constant-volatility failure.** Relative volatility varies 1.11 x
  across the alkane column and 1.13 x across benzene/toluene, so Underwood's
  constant-alpha assumption is equally stressed on the case that agrees and the
  case that does not. That hypothesis was tested and refuted.
- **It is not the feed stage.** A nine-point sweep ruled that out; see
  `2026-09-09-alkane-gap-is-not-the-feed-stage.md`.

## What it means for M3, and a correction

M3 ranks sequences on `ShortcutColumn` duties and costs.

An earlier note argued the ranking might survive because a systematic error
affects all sequences alike, and because cost and total vapour load selected the
same winner. **Both halves of that argument are wrong.**

**The two metrics are not independent.** Vapour load is computed as D x (R+1)
and cost derives from the duties, which derive from R. Both inherit the same
reflux from the same shortcut. Their agreement was close to tautological and
should never have been offered as corroboration.

**The error is differential, not systematic.** Sequences differ precisely in how
much non-key material passes through each column: a direct sequence puts the
whole feed through its first column, an indirect one removes the heavy end
first. Since Rmin falls with non-key content, the error is largest exactly where
sequences differ most.

So the M3 ranking is not protected. **The winner may be wrong, not merely
mispriced.** The 5.1 % margin by which easiest_first beat most_plentiful_first
is smaller than this effect by orders of magnitude and cannot be relied on.

## What is NOT claimed

That BioSTEAM is wrong and DWSIM is right in general. DWSIM's rigorous MESH
solve is the better reference for this question, which is the milestone's whole
premise, but three things remain unattributed: the property packages differ
(BioSTEAM defaults against Peng-Robinson), spec convention 3 on whether a stage
count includes the condenser and reboiler is unpinned, and only two cases have
been measured.

What IS established is the direction and the trend: Rmin falls monotonically
with non-key content across four feeds, and a rigorous solve of the same column
needs nine times it.

## Next

1. Re-rank the M3 adversarial feed using rigorous refluxes for every column and
   see whether the winner changes. That is the test that matters.
2. Check whether BioSTEAM's Underwood root selection handles heavy non-keys, or
   whether `ShortcutColumn` is a documented approximation here.
3. Consider whether sepsyn should report a reflux at all for columns carrying
   substantial non-key material, or declare it undetermined.
