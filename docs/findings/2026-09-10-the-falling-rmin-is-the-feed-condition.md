# The falling minimum reflux is the feed condition, not the method

**Date:** 2026-09-10
**Status:** measured, controlled, and it CORRECTS a previous finding
**Corrects:** `2026-09-09-underwood-rmin-falls-with-non-keys.md`
**Method:** sepsyn's own Underwood implementation (`sepsyn/vmin/`), written
from the equations specifically so this question could be asked.

## The question it answers

On 2026-09-09 BioSTEAM's `ShortcutColumn` returned a minimum reflux that FELL
by 73 % as inert heavy non-key was added to the same propane/butane split. It
could not be established whether that was a defect in BioSTEAM or a misuse of
it, and nothing was filed pending an independent implementation.

That implementation now exists. The same four feeds, run through our own code:

| feed, kmol/hr | q | ours at the feed's q | ours at q = 1.0 | BioSTEAM 09-09 |
|---|---|---|---|---|
| C3 10, C4 20 | 1.098 | 1.2449 | 1.3493 | 1.1324 |
| C3 10, C4 20, C5 60 | 1.381 | 1.1066 | 2.2715 | 0.6121 |
| C3 10, C4 20, C5 60, C6 10 | 1.402 | 1.0357 | 2.3223 | 0.5339 |
| C3 10, C4 20, C5 180 | 1.558 | 0.7720 | 3.9348 | 0.3006 |

## The finding

**Our own implementation falls too, and only because q is allowed to move.**

Hold q at 1.0 and the series RISES monotonically, 1.35 to 3.93, which is the
direction physical intuition expects: more heavy non-key means more material to
boil past the light key. Release q and the same forty lines produce a falling
series.

The mechanism is visible in the q column and it is not subtle. Every feed in
the series sits at a fixed 330 K. Adding heavy pentane raises the mixture
bubble point at 13.694 bar, so the same 330 K feed is progressively further
below it: q climbs 1.098 to 1.558. A subcooled feed condenses vapour on entry
and supplies part of the reflux for free, which genuinely lowers what the
reboiler must raise. Underwood carries this in the `1 - q` right-hand side.

Nothing but q differs between the two series. Same pressure, same alphas, same
flows, same code. It is a controlled experiment, and it is pinned in
`tests/test_vmin_against_biosteam.py`.

**So the 09-09 measurement was never evidence of a defect in `ShortcutColumn`,
and its framing — "adding heavy non-keys makes the shortcut believe the
separation is easier" — attributes to the method something that belongs to the
feed. Nothing is to be filed against BioSTEAM on this basis.**

## What this does NOT explain, stated plainly

**The magnitude.** Ours falls 38 % across the series; BioSTEAM's falls 73 %.
The direction is now attributed; roughly half the depth of the fall is not.

**The 9.3x rigorous gap.** DWSIM's rigorous column on the four-component case
converged at R = 4.95 against BioSTEAM's Rmin of 0.534. That column was fed the
same 330 K stream and saw the same subcooling, so feed condition cannot account
for it. That gap remains open and is unaffected by this finding.

**Which of the two absolute numbers is right.** At 13.694 bar on the
four-component feed we compute Rmin 1.036 where BioSTEAM computes 0.534. A
sweep of recovery from 99 % to 99.999 % — approaching the sharp split our
equation assumes — does not close it; BioSTEAM plateaus at about 0.79x our
value and is not even monotonic. Two implementations of the same equation
disagree by a factor of two and this finding does not resolve which is
correct.

## What survives from the 09-09 finding

- The 9.3x rigorous-versus-shortcut gap. Measured, unexplained, untouched.
- That cost and total vapour load are NOT independent corroboration. Vapour is
  `D(R+1)` and cost derives from duties derived from R. That correction stands.
- That the M3 ranking was not protected by a "systematic error cancels"
  argument. It is superseded anyway: M6 does not rank on cost.

## What it changed in the code

The investigation exposed a real defect in `best_sequence`, now fixed.

It was charging the FRESH feed's q to every column in the tree. Downstream
columns are fed a bottoms liquid or a condensed overhead, each leaving at its
own bubble point, so they are saturated whatever the fresh feed was. Charging
them the fresh feed's subcooling assumes the entire train runs at cold-storage
temperature.

Not a small effect. On the alkane feed 10/20/60/10 the correction changed the
winning sequence from the direct train to `C3+C4 / C5+C6` first, and cut that
sequence's undetermined columns from two to one.

## Why this was worth the milestone

M6's spec argued that Underwood had to be written rather than borrowed, because
"a bound this whole milestone rests on must be code we can read." The first
thing the readable version did was overturn a finding, attribute a trend that
had been sitting unexplained for a day, and expose a defect in the code written
alongside it. That is the case for the decision, made in retrospect.
