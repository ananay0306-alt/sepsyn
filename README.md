# sepsyn

Screening and preliminary design for distillation, from a single column to the
order of columns for a ten-component feed, built so that **every assumption it
makes is written down**.

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

What it does:

- **Screens** a mixture: whether distillation can work, at what column
  pressure, and what to use instead when it cannot (azeotropes, two liquid
  phases, components that will not condense).
- **Designs** the column: stages, reflux, duties, diameter, cost, and the
  equipment choices, each marked as evidence or convention.
- **Sequences** a multicomponent feed: the provably best order of columns by
  minimum vapour, then every column checked as a real design. Ten components
  take about 25 seconds.
- **Scores the textbook heuristics** against that optimum, each with its
  citation.
- **Checks itself against DWSIM**, a rigorous simulator, and reports the gap
  only once both tools are shown to be modelling the same column.
- Runs from the terminal, or **from Claude** as an MCP server.

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

Choose the order of columns for a multicomponent feed:

```bash
.venv/bin/python -m sepsyn.cli --feed "Propane:10,Butane:20,Pentane:60,Hexane:10" \
  --T 330 --vmin --order "Propane,Butane,Pentane,Hexane"
```

`--order` lists the components lightest to heaviest. `--vmin` finds the
sequence that needs the least vapour, by dynamic programming over Underwood's
minimum vapour: at ten components that is 165 splits evaluated instead of 4,862
sequences, and the answer is the optimum rather than the best of a sample. It
needs no cost data. Each column of the chosen sequence is then screened and
designed for real, because minimum vapour cannot see whether an overhead will
condense. `--sequence` instead designs and costs every sequence and ranks them.

An azeotropic pair anywhere in the feed blocks every sequence, so `--vmin`
refuses before computing anything and names what would work instead.

## The heuristics, scored

Textbook rules for ordering columns ("recover the most plentiful component
first", "make the most difficult splits last") are stored in
`sepsyn/heuristics.yaml`, each with its source, and both sequencing reports
score them against the optimum:

```
H-01  Recover the lightest component first          +1.6% vapour
      Douglas (1985), as listed in Separation_heuristics.pdf
H-02  Recover the most plentiful component first    the optimum
H-05  Perform the easiest separation first          +1.6% vapour
      Harbert (1957) ... (citation unverified)
```

A heuristic never changes an answer. It points at a calculation, and a test
holds the report above the heuristics identical with the database emptied. A
citation known only from a secondary source says so.

## Checked against a rigorous simulator

`sepsyn/crossvalidate.py` builds the same column in DWSIM (through
[dwsim-mcp](https://github.com/ananay0306-alt/dwsim-mcp)) and reports the gap,
but only after every configuration assertion holds: the same stage count and
feed stage read back from DWSIM's own column, the same pressure, the same
specification, a closed mass balance, and the same feed state on both sides.
Otherwise it reports no gap and names the assertion that failed. A gap between
two differently configured columns is bookkeeping, not shortcut error.

| Column | Condenser | Reboiler | End temperatures |
|---|---|---|---|
| Benzene/toluene | -3.6 % | +3.9 % | within 0.5 K |
| Pentane/hexane, saturated feed | -15.5 % | -10.9 % | exact |
| Four-alkane, heavy non-keys | -69.7 % | -25.4 % | within 1.1 K |

The shortcut under-predicts multicomponent duties, worst with heavy non-keys.
That is what a preliminary design tool is, and the table is the evidence.

## Use it from Claude (MCP)

```bash
claude mcp add sepsyn -- /path/to/sepsyn/.venv/bin/python -m sepsyn.mcp_server
```

Run that from the repository root so the module is importable. Five tools:
`screen_mixture`, `design_column`, `sequence_by_minimum_vapour`,
`rank_sequences` and `find_azeotropes`. Each one builds the same arguments the
CLI takes and returns the same report, so the server cannot drift from the
tool it wraps. `skill/SKILL.md` covers the shell route instead.

## Saving a run

```bash
--out results/run.txt     # the readable report
--json results/run.json   # the same run as structured data
--html results/run.html   # a page: charts, assumptions, rules, checks
```

`--html` writes a self-contained page. No fonts, no CDN, no scripts fetched, so
it opens on a machine with no network and still works in five years. The reflux
sweep is drawn as a curve with its optimum marked, because locating a minimum
in a trade-off is a chart's job and it had been a table of eight rows the reader
had to scan. Stages against reflux is a second measure on a different scale, so
it gets its own chart rather than a second axis.

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

544 tests, about 90 seconds; six more run against a live DWSIM with
`-m dwsim_live`. They are worth reading: several encode a measured
finding rather than an expected value, including the ones that pin third-party
behaviour this code depends on.

## Known limits, stated rather than hidden

- **The liquid-liquid check can raise a false alarm.** UNIFAC predicts a
  miscibility gap for water and glycerol, which are miscible in all
  proportions, and the false gap looks exactly like a real one by width, point
  count and composition difference. Switching models does not help. That pair
  is now overridden by measured data, keyed by CAS number, and the report says
  so. Other aqueous polyols could fail the same way, which is why the rule
  carries verdict `caution` rather than `undetermined`.
- **Shortcut duties run low on multicomponent columns**, 11 to 16 % on a
  column with traces and up to 70 % on the condenser with heavy non-keys,
  measured against DWSIM (see above).
- **Which minimum vapour is right on the four-alkane feed is unresolved.**
  sepsyn's Underwood and BioSTEAM's differ by about 2x. Both are consistent
  with every rigorous column that converged, and DWSIM does not converge that
  column above 30 stages, so the question is recorded, not answered.
- **Steady state, preliminary design.** No dynamics, no tray hydraulics, no
  reactive distillation.
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

## Acknowledgements

Thanks to Hafi, who I talked through the early direction and design decisions
with. Several of the choices this tool is built on were settled in those
conversations.

## License

MIT. See `LICENSE`.
