---
name: sepsyn
description: Screen a binary or near-binary mixture for separation feasibility and design a distillation column, using the sepsyn rule engine. Use when asked whether a mixture can be distilled, which separation technology suits it, what column a split needs, or to check a stage count, reflux, pressure, feed condition or equipment choice against the binary distillation heuristics. Triggers on distillation, relative volatility, azeotrope, reflux, stages, light key, heavy key, condenser, reboiler, trays, packing, feed q.
---

# sepsyn

A door, not a brain. sepsyn already decides these questions in code; this skill
runs it and reads the output. **Never compute a stage count, minimum reflux,
relative volatility, column pressure or feed q yourself, and never assert a
threshold from memory.** Those numbers are the tool's job, and a number you
produce instead of running it is exactly the failure sepsyn exists to prevent:
a plausible answer nobody can audit.

## Run it

```bash
cd ~/projects/process_simulation/sepsyn
../.venv/bin/python -m sepsyn.cli --feed "Methanol:100,Water:80" --T 330
```

Flows are kmol/hr, `--T` in K, `--P` in Pa. Add `--explain` to print the rules
that did NOT fire with the values they tested — use it whenever the user asks
why, or disagrees with a verdict.

To design the column, name the keys:

```bash
../.venv/bin/python -m sepsyn.cli --feed "Benzene:60,Toluene:40" --T 298.15 \
  --design --light-key Benzene --heavy-key Toluene \
  --distillate-purity 0.99 --bottoms-impurity 0.01
```

`--lk-recovery` / `--hk-recovery` if the user speaks in recoveries instead.
These are different specifications and the tool converts explicitly — do not
substitute one for the other. `--feed-q` imposes the feed thermal condition;
omitting it takes the feed as it arrives, which is **not** the same as 1.0.

**Always pass the keys when the user has named them.** Without them four rules
cannot fire and the liquid-liquid check screens every pair instead of the one
being separated.

## Read the output

The verdict is one of `FEASIBLE`, `CAUTION`, `UNDETERMINED`, `INFEASIBLE`,
`unknown`. Report the rule ids that fired and what they tested — the reasoning
is the product, not the verdict.

Three things must never be flattened when you summarise:

- **`REQUIRES`** means the rule fired but its verdict cannot be acted on until
  that calculation is done. Say so. Do not present it as settled.
- **`CAVEAT`** is a competing effect the reader must check. Carry it across.
- **`NOT DECIDED`** under EQUIPMENT CHOICES means sepsyn declined. Ask the user
  for the missing input; do not choose on its behalf.

Under EQUIPMENT CHOICES, `[by default]` and `[decided, E-xx]` are different
claims — one is convention, the other is evidence. Keep the distinction. An
unrecorded equipment choice is what produced this project's 58 % condenser-duty
discrepancy.

`UNKNOWN` means no rule fired at all. That is a gap in the rule table, not a
finding about the mixture. Say that plainly rather than reaching for a reason.

## Ask, don't guess

Stop and ask the user when the request needs any of these, because sepsyn has
no data for them and neither do you:

- decomposition, polymerisation or fouling behaviour (R-11, E-23a)
- bottoms viscosity or solids (E-23a)
- whether an existing column or utility must be reused
- a design-vs-simulation ambiguity: "design me a column" computes stages from a
  purity, "what will this column do" computes purity from a column. Opposite
  directions, different solver. Ask which one is meant.

## Change the judgment, not the code

The thresholds live in `sepsyn/rules.yaml` (screening) and
`sepsyn/equipment_rules.yaml` (equipment, steps 22–25). Both are validated at
load. Editing them is the supported way to change what the tool concludes — do
not patch Python to alter a verdict.

Run the suite after any edit:

```bash
cd ~/projects/process_simulation/sepsyn && ../.venv/bin/python -m pytest -q
```

## Known limitation, state it when relevant

The liquid-liquid check (R-12) inherits a UNIFAC false positive: it reports
water/glycerol as splitting when they are miscible in all proportions, and that
false positive is indistinguishable from a true one by gap width or composition
difference. If R-12 fires on an aqueous polyol, say so and point the user at
literature solubility data.
