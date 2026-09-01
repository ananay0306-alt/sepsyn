# sepsyn

Screening and preliminary design for binary distillation, built so that **every
assumption it makes is written down**.

Two engineers can run the same column, both correctly, and disagree by 58%.
Not because either made a mistake, but because one quietly assumed something
the other didn't and neither recorded it. This tool exists to stop that.

```
COLUMN PRESSURE  derived, atmospheric is sufficient; Benzene condenses against
                 cooling water at 313.1 K (saturation pressure 0.24 bar)

  alpha Benzene/Toluene = 2.519 at 362.5 K, 1.013 bar (bubble point at column P)

RULES FIRED
  R-01  ordinary distillation is viable
        min_alpha = 2.5190775755242276, n_supercritical_at_feed = 0

VERDICT  distillation FEASIBLE
```

Not just a verdict. The rule that produced it, the number it tested, and the
pressure that number was evaluated at.

## Why

Two discrepancies measured while building this, both between calculations that
were individually correct:

| Disagreement | Cause |
|---|---|
| **58%** on condenser duty | One side used a total condenser, one a partial. Neither said so |
| **43%** on stage count | One counted theoretical stages, one actual trays. The efficiency was assumed on both sides and stated on neither |

Once the configurations were matched, the two agreed to within about 6%. The
physics was never in dispute. The bookkeeping was.

## Install

Requires Python 3.11 or newer.

```bash
git clone https://github.com/ananay0306-alt/sepsyn.git
cd sepsyn
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

BioSTEAM pulls a large scientific stack, so the first install takes a few
minutes.

## Use

Screen a mixture:

```bash
.venv/bin/python -m sepsyn.cli --feed "Benzene:60,Toluene:40" --T 298.15 \
  --light-key Benzene --heavy-key Toluene
```

Design the column:

```bash
.venv/bin/python -m sepsyn.cli --feed "Benzene:60,Toluene:40" --T 298.15 \
  --design --light-key Benzene --heavy-key Toluene \
  --distillate-purity 0.99 --bottoms-impurity 0.01
```

Add `--explain` to print the rules that did **not** fire, with the values they
tested. Flows are kmol/hr, temperatures K, pressures Pa.

## Saving a run

```bash
--out results/run.txt     # the readable report
--json results/run.json   # the same run as structured data
```

The JSON is what makes two runs *comparable* rather than merely readable, which
is the argument the whole tool rests on. Three things in it are deliberately
saved as pairs, because saving half of any of them recreates the
unrecorded-assumption failure in a new file format:

| Saved | Why both halves |
|---|---|
| pressure **and its basis** | specified and derived are different claims |
| q **and whether it was imposed** | a q the feed had, and a q it was given, are different designs with the same number |
| an equipment choice **and its status** | convention and evidence are not the same |

Every rule is recorded, fired or not, along with all eight verification checks
and the whole reflux sweep. So two designs line up directly:

```
                     as it arrives       preheated
feed q                       1.301           1.000
imposed?                     False            True
stages                          44              48
annualised USD/yr          329,276         291,331
reboiler kW                 1400.7          1158.4

  difference: $37,946/yr from one assumption
```

There is a guided demo:

```bash
./demo.sh          # pauses between beats
NOPAUSE=1 ./demo.sh
```

## What it will not do

A tool that always returns a column is not trustworthy. Three outcomes matter
as much as the designs:

- **INFEASIBLE.** Ethanol and water form an azeotrope; no column of any size
  separates them. It names the alternatives instead.
- **Two liquid phases.** Water and butanol split into layers, so the
  single-liquid model behind every number is the wrong model. This is the only
  screening check whose failure is *silent*: every other error produces an
  obviously wrong number, while this one produces a perfectly reasonable design
  for a separation that will not happen.
- **UNDETERMINED.** Glycerol boils at 289 °C. Does it decompose first? That is
  in no property database, so the tool declines to design and names the
  measurement it needs.

Equipment choices are tagged `[by default]` or `[decided, E-xx]`. Those are
different claims — convention versus evidence — and collapsing them is how the
58% discrepancy stayed hidden.

## Changing its judgment

The thresholds live in two plain YAML files, not in code:

| File | Contains |
|---|---|
| `sepsyn/rules.yaml` | 12 screening rules |
| `sepsyn/equipment_rules.yaml` | Equipment choices: condenser, reboiler, internals, reflux state |

Both are validated at load: a duplicate id, an unparseable condition, or a rule
naming a property that does not exist is rejected rather than silently never
firing. A rule that cannot fire is the failure mode this project exists to
catch.

A rule may also declare what it still needs:

```yaml
verdict: undetermined
requires:
  - decomposition or polymerisation onset temperature of the bottoms
    component, which is not in the property database
```

## Tests

```bash
.venv/bin/python -m pytest -q
```

240 tests, about 18 seconds. They are worth reading: several encode a measured
finding rather than an expected value, including the ones that pin third-party
behaviour this code depends on.

## Known limits, stated rather than hidden

- **A false positive in the liquid-liquid check.** UNIFAC predicts a
  miscibility gap for water and glycerol, which are miscible in all
  proportions. Across an eight-pair panel, seven were classified correctly and
  this one is indistinguishable from a true split by gap width, point count, or
  composition difference alike. The error is in the activity model, not the
  search, so the rule flags the pair and points at literature data. It carries
  verdict `caution` rather than `undetermined` for that reason.
- **BioSTEAM clamps column diameter at 0.914 m.** The adapter recovers the true
  hydraulic diameter from BioSTEAM's own correlations, both column sections,
  and carries the clamped value separately since the cost belongs to that one.

## Design notes

- `ColumnSpec` is written in **recoveries, not mole fractions**. A recovery
  means the same thing in every simulator; a mole fraction has a denominator
  that differs between tools, and that mismatch produced a 175% error in an
  earlier comparison.
- The rule engine sees only a flat `PropertyRecord`. It cannot reach the
  simulator or the raw chemicals, which is what makes it testable against a
  hand-written record with no chemistry involved.
- Rule conditions are parsed with `ast` and evaluated against a restricted
  namespace. No builtins, no calls: a rule file edited by a student cannot
  execute code.
- Missing properties never fire a rule. Any comparison against `None` is false
  by construction, so absent data produces silence rather than a guess.

`STATUS.md` is the working tracker: what is done, every finding, and what is
open.

## License

MIT. See `LICENSE`.
