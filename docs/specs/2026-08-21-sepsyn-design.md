# sepsyn — auditable separation synthesis

**Date:** 2026-08-21
**Status:** design approved, ready for implementation planning

## Problem

Designing a separation requires deciding three things: which technology, in what
order, and at what conditions. Reaction conditions are published; separation
conditions largely are not, so engineers find them by trial and error in a
simulator. That is slow, depends on experience, and is the part students find
hardest.

LLMs can do this quickly but produce answers whose reasoning leaves no trace.
The model states a scheme with the same confidence whether it derived it or
pattern-matched it, so the output is least trustworthy exactly where the user
is least able to check it. Evidence from this project: during a DWSIM/BioSTEAM
comparison a discrepancy was confidently attributed to a difference in property
packages and written into a summary; the real cause was a column specification
basis mismatch. Plausible, and wrong.

## Thesis

Most separation decisions do not require reasoning. Whether distillation is
feasible is a calculation. Which split goes first is covered by published
heuristics. The reflux/stages optimum is a parameter sweep. Move those out of
the model and into code, and every decision becomes printable.

**Governing principle:** every decision is either computed from physics, or a
named rule that gets printed, or a cited source. The LLM never silently decides.

## Scope — milestone 1

Answer two test problems correctly, as a demonstration that rules-first works.

1. **H2 / methane**, 50 kmol/hr each, 298.15 K, 1 atm, 90% H2 overhead.
   Correct answer: distillation is infeasible, both components are supercritical
   at feed, candidates are PSA / membrane / cryogenic.
2. **Methanol / water / glycerol**, 100 / 80 / 25 kmol/hr. Target: distillate
   at 99 mol% methanol; bottoms at 1 mol% methanol. Both are mole fractions of
   the **total** stream, not a keys-only basis. Correct answer: one column meeting the spec, plus a
   printed flag that water and glycerol were not separated because no spec was
   given for them.

**In scope:** the nine screening rules enumerated below; design of distillation
and flash only; BioSTEAM as the only simulator behind an abstract interface.

**Out of scope for milestone 1:** sequencing multicomponent trains, DWSIM
cross-validation, literature RAG, any LLM interface. Each becomes its own
milestone with its own spec.

## Deliverable

A Python library with a CLI. No LLM anywhere in milestone 1. The library is the
unit under test and is later wrappable as an MCP server or agent without
changing the core.

## Architecture

```
sepsyn/
├── properties.py     lookups (Tb, Tc, Pc) + relative volatility
├── azeotropes.py     VLE search; separate module, own tests
├── rules.yaml        the decision table -- readable, editable, printable
├── engine.py         evaluates rules against properties
├── simulators/
│   ├── base.py       Simulator protocol
│   └── biosteam.py   only implementation for now
├── design.py         sizes a column or flash given a feasible verdict
├── report.py         formats output; prints rules fired and not fired
└── cli.py
```

Data flow is a single pass: feed spec -> property record -> verdicts ->
(if feasible) design -> verification -> report.

**Three structural decisions:**

- The **property record is the only input to the rule engine.** Rules cannot
  reach the simulator or raw chemicals, so the engine is testable with a
  hand-written record and no chemistry.
- The **simulator sits behind a protocol** with two methods. DWSIM becomes a
  second file later, not a refactor.
- **Verdicts carry their own provenance** — rule id, condition text, and the
  values that fired it — so nothing downstream can invent a justification.

## Property layer

Relative volatility is a property of a pair *at a condition*, not of a pair.
It is computed at the **mixture bubble point, at the proposed column pressure**,
where the separation actually occurs. Column pressure itself comes from a rule:
the lowest pressure at which the overhead condenses against cooling water at
~40 C.

Alpha is never stored as a bare number. The record carries value, T, P and basis.

Additional properties the rules require:

- `n_supercritical_at_feed` — count of components above Tc at feed conditions
- `condensable_at_cooling_water` — distinguishes "needs refrigeration" from
  "impossible"
- `has_azeotrope`, `min_alpha`, `n_components`

## Rule engine

Rules are YAML records with a stable id, a priority, a condition over named
properties, a verdict, candidate technologies, and a plain-language reason that
is printed verbatim.

```yaml
- id: R-04
  name: no condensable phase at feed
  priority: 10
  when: "n_supercritical_at_feed == n_components"
  verdict: infeasible
  technologies: [PSA, membrane, cryogenic_partial_condensation]
  because: "all components are above their critical temperature at feed
            conditions, so no liquid phase exists"
```

**Evaluation is ordered and does not stop at the first hit.** All matching rules
are collected, because a mixture can be both low-alpha and azeotropic and the
report should say both.

### The rule table for milestone 1

| id | condition | verdict | technologies |
|---|---|---|---|
| R-01 | `min_alpha >= 1.05 and n_supercritical_at_feed == 0` | feasible | distillation |
| R-02 | `min_alpha < 1.05` | infeasible | extractive_distillation, adsorption, membrane |
| R-03 | `has_azeotrope` | infeasible | pressure_swing, extractive, hybrid_adsorption |
| R-04 | `n_supercritical_at_feed == n_components` | infeasible | PSA, membrane, cryogenic_partial_condensation |
| R-05 | `0 < n_supercritical_at_feed < n_components` | caution | cryogenic_partial_condensation, flash |
| R-06 | `min_alpha > 10` | feasible | flash (single stage may suffice, no reflux) |
| R-07 | `feed_phase == 'liquid' and light_key_mole_fraction < 0.05` | feasible | stripping |
| R-08 | `feed_phase == 'vapor' and heavy_key_mole_fraction < 0.05` | feasible | absorption |
| R-09 | `condensing_T_at_column_P < cooling_water_T` | caution | distillation (refrigerated condenser) |

Nine rules, not seven — R-05 and R-09 were added during review. R-05 covers the
case where *some* components are supercritical, which the original seven missed
and which is common in gas processing. R-09 is the refrigeration caution.

Each row also carries a `because` string and a citation, omitted here for width.

**Three verdicts:** `feasible`, `infeasible`, `caution`. The third prevents the
tool being binary — a cold flash requiring refrigeration is a caution, not a
failure.

**If no rule fires the engine returns `unknown` and refuses to proceed.** It
never falls through to a default technology.

`when` expressions are parsed with `ast` and evaluated against a restricted
namespace containing only the property record: no builtins, no imports, no
arbitrary calls. A rule file edited by a student cannot execute code.

## Design layer

```python
class Simulator(Protocol):
    def design_column(self, feed: Feed, spec: ColumnSpec) -> ColumnResult: ...
    def design_flash(self, feed: Feed, spec: FlashSpec) -> FlashResult: ...
```

Nothing simulator-specific crosses that boundary.

**ColumnSpec specifies recoveries, not mole fractions.** Recovery is
unambiguous; mole fraction is not — BioSTEAM divides by the keys, DWSIM by the
total stream, and that difference produced a 175% error in the ETJ comparison.
Each adapter converts recovery to its simulator's native basis in one tested
place.

**Reflux comes from a sweep, not a default.** k is swept over 1.05 to 2.0 in
ten steps, annualised cost computed at each point, and the curve returned
alongside the minimum. Annualised cost uses a deliberately simple model:
`installed_cost / plant_life_years + utility_cost_per_hr * operating_hours`,
with plant life 10 years, 8000 operating hours, and utility costs taken from
BioSTEAM's own defaults. The model is crude on purpose -- the tool reports the
whole curve, and the location of the knee is insensitive to these constants. At 0.01 s per BioSTEAM solve this is free, and it shows the trade-off
rather than asserting an answer.

**Every design result is verified before return:** mass balance closes; the
requested recovery was achieved; no spec value is suspiciously equal to an input
(spec-binding check); reboiler below decomposition temperature; condenser above
the cooling-water limit. Failures are attached to the result as data, not
raised — a design that fails verification is still returned, clearly marked.

## Error handling

| Kind | Example | Behaviour |
|---|---|---|
| Bad input | chemical not in database | fail immediately, list near-matches |
| No rule fires | combination not covered | return `unknown`, refuse to guess |
| Simulator fails | column will not converge | return result with failure attached, verbatim |

## Testing

1. **Property tests** — Tb, Tc for a dozen chemicals against literature.
2. **Azeotrope tests** — ethanol/water 95.6 wt%, acetone/methanol, IPA/water,
   with documented sources. Most likely module to be quietly wrong.
3. **Rule engine tests with hand-written property records** — no chemistry;
   assert the right rules fire and no others.
4. **Two acceptance tests** — the problems in Scope. These define done.
5. **A negative acceptance test** — a feed that should return `unknown`,
   asserting the tool refuses rather than guessing. Stops a future rule change
   silently making the fallthrough permissive.

## Success criteria

Milestone 1 is complete when both acceptance tests and the negative acceptance
test pass, `--explain` prints rules fired and not fired with their values, and
the rule table can be read and extended without touching Python.
