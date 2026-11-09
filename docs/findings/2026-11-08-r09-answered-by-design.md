# R-09 answered by design, not by a partial condenser

**Date:** 2026-11-08
**Status:** BUILT in `sequencing/evaluate.py`; DWSIM gate passed.
**Overturns:** the 09-10 result that only the indirect sequence survives on
the propane/butane/pentane/hexane 10/20/60/10 feed.

## The question

On a ten n-alkane feed (C3 to C12, 10 kmol/hr each) `--vmin` verification
left eight of nine columns UNDETERMINED on R-09. R-09 screens a condenser on
the lightest component present, at any amount, and a 1 % propane trace rides
down the whole train.

## The plan that the measurement changed

The approved plan was to design those columns with a partial condenser and
vent the trace. Measured first:

| column | pressure | designed total condenser | vs 313.15 K |
|---|---|---|---|
| Hexane/Heptane to Undecane/Dodecane (6) | 1.013 bar | 341.5 to 468.8 K | +28 to +156 K |
| Butane/Pentane | 3.785 bar | 312.46 K | -0.69 K |
| Pentane/Hexane | 1.157 bar | 312.68 K | -0.47 K |

A partial condenser on Pentane/Hexane (4-alkane train) reached 313.19 K, a
0.04 K margin: luck, not an answer. Six of the doubts were false alarms the
design already answers; two were real shortfalls of under a kelvin, because
the column pressure is set so the PURE light key condenses exactly at the
limit and the traces pull the mixture just below it.

## What was built

For a column undetermined by R-09 alone: design it; if the designed
distillate temperature is at or above cooling water, R-09 is answered and the
report says so with the number. If not, raise the pressure by 2 % steps to the
30 bar cap, re-screening at each step so no other rule is stepped past. An
unanswerable R-09 stays UNDETERMINED with the measured temperature.

Ten alkanes: eight of nine columns verify; Butane/Pentane needs 3.861 bar,
Pentane/Hexane 1.180 bar. Undecane/Dodecane stays UNDETERMINED on R-11
(thermal), which this does not touch.

## The DWSIM gate

Pentane/Hexane of the 4-alkane train (0.2 kmol/hr butane trace), 24 stages,
feed at 19, recovery specs, Peng-Robinson, Napthali-Sandholm:

| pressure | converged | DWSIM condenser | BioSTEAM |
|---|---|---|---|
| 1.157 bar | yes | 313.0 K (below) | 313.0 K |
| 1.180 bar | yes | 313.6 K (above) | 313.6 K |

Every configuration assertion holds at both. September recorded this column as
one a rigorous solve could not converge; it does not reproduce, most likely
because the feed-stage numbering was wrong then (fixed 11-07). Recorded as
`tests/fixtures/dwsim/butane_pentane_hexane_24_19.json`.

## Consequences

- The 4-alkane adversarial feed: all five sequences cost; the direct sequence
  wins at about $505,000/yr. The 09-10 "indirect only, 55 % dearer" is
  withdrawn.
- The undetermined-blocks-cost guard is now tested on ethane as light key,
  which condenses against cooling water at no pressure (Tc 305 K).

## The duty gap on the gate column: explained, and now refused

The first comparison of this column reported condenser -24 %, reboiler +72 %.
Root cause, measured: the two tools were modelling different feeds.

| | BioSTEAM | DWSIM |
|---|---|---|
| feed as modelled | the stream as handed: liquid, 330 K, never flashed (thermosteam's default phase) | PT-flashed at 330 K and column pressure |
| vapour fraction | 0 (q = 0.91 by enthalpy) | 1.00 |
| enthalpy | 107.7 kW | about 600 kW (the same stream flashed in BioSTEAM) |

That is about 490 of the 530 kW by which Qr - Qc differs. The equivalence
check's "feed condition" said "both sides take the feed as it arrives", which
held by construction. It is now measured: sepsyn's q against DWSIM's flashed
vapour fraction, read back after the solve, within 0.05. This column now
reports NO GAP; benzene/toluene and the alkanes, liquid in both tools, still
report theirs unchanged.

A first read-back was taken before the solve and returned 0.0, DWSIM's
default for an unflashed stream. Moved after the solve and pinned in the
transport's docstring.

Open, and a sepsyn question rather than a cross-validation one: downstream
columns in a sequence are fed at the ORIGINAL feed temperature
(`evaluate._feed_from`), not at the state their parent column delivers them
in, and BioSTEAM never flashes a stream it is handed. Here that is a 330 K
"liquid" pentane feed above its bubble point.

## Limits

- Columns keep a total condenser. A partial condenser remains the answer
  only for genuinely non-condensable lights, and is not built here.
- Margins are small by construction (the step stops at the first pressure that
  clears), e.g. 313.2 K against 313.15 K.
- R-09 is answered only when it is the sole undetermined rule; a column also
  undetermined on R-11 keeps both.
