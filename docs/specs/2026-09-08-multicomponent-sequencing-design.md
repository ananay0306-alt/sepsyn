# Multicomponent sequencing (M3) — design

**Date:** 2026-09-08
**Status:** design approved, ready for implementation planning
**Supersedes:** the one-line M3 placeholder in `STATUS.md`

## 1. The question

For a feed of N components you need N−1 columns, and they can be arranged in
Catalan(N−1) different sequences. Textbooks give heuristics for choosing among
them:

- do the easiest separation first (highest relative volatility)
- do the most difficult separation last
- remove the most plentiful component first
- favour equimolar splits
- remove corrosive components early
- remove hazardous components early

**These conflict.** If a component is both the one with the highest relative
volatility and the corrosive one, two rules point in opposite directions and
nothing in the literature says which wins. The usual answer is "evaluate the
cost", which assumes cost data that a screening exercise often does not have.

This design answers that question, and the answer turns out to have two parts:
one structural, one empirical.

## 2. The structural claim

The six heuristics above are not six statements of the same kind. Sorting them
by *what kind of statement they are* removes most of the apparent conflict.

**Total vapour load** is used throughout as the second objective and is defined
here once: for each column, V = D x (R + 1), the molar vapour reaching the
condenser, summed over every column in the train. Both capital cost (through
column diameter) and energy cost (through reboiler duty) scale with it, which is
why it works as a cost surrogate when no cost correlations are available.

| Class | What it is | Which heuristics |
|---|---|---|
| `objective` | The quantity being minimised | annualised cost; total vapour load |
| `proxy` | A cheap *estimator* of the objective, from an era before you could evaluate 42 sequences in two seconds | easiest split first; most difficult last; most plentiful first; equimolar splits |
| `constraint` | Eliminates sequences, or attaches a materials or containment penalty | corrosive removed early; hazardous removed early |

The four volatility and flow heuristics are competing estimators of one
quantity. They do not conflict in principle; where they disagree, at most one is
right and the disagreement is measurable.

"Remove the corrosive component early" is a different kind of claim. Its reason
is that corrosive material forces exotic metallurgy in **every column it passes
through**. That is a cost term, or a hard constraint when it cannot be
quantified. It is not a preference competing with relative volatility.

The two only look like they collide because textbooks write them in identical
imperative grammar and list them in one flat set. That formatting choice
manufactures the conflict.

## 3. The empirical claim

Once the classification above separates constraints from objectives, the
remaining question — which proxy is right when two proxies disagree — becomes a
measurement rather than an argument. Enumerate every sequence, evaluate it,
rank it, and score each proxy by how often it predicted the evaluated winner.

The probes below establish that this is affordable.

## 4. Measured evidence

Throwaway probes run 2026-09-08 against BioSTEAM `ShortcutColumn`, n-alkane
feeds (propane through octane), sharp splits, ideal group flows.

| | 4 comp | 5 comp | 6 comp |
|---|---|---|---|
| Sequences | 5 | 14 | 42 |
| Columns solved | 15 | 56 | 210 |
| Wall time | 0.2 s | 0.5 s | 2.0 s |
| Convergence failures | 0 | 0 | 0 |
| Same winner, cost vs vapour load | yes | yes | yes |
| Full ranking identical | yes | **no** | **no** |
| Worst rank displacement | 0 | 3 of 14 | **14 of 42** |

Three findings, and the design turns on all three.

**Exhaustive evaluation is effectively free.** A flat 0.01 s per column, scaling
linearly. Six components is two seconds. There is no need to prune the search
space at the sizes this tool targets, so heuristics are not needed as a search
strategy.

**The winner is robust to the cost model.** Annualised cost and total vapour
load select the same sequence in all three cases. `design.py` describes its
annualised cost function as "deliberately crude"; for choosing a winner, that
crudeness has not yet mattered.

**The rest of the ranking is not robust.** At six components a sequence moves up
to fourteen of forty-two places depending on which metric ranks it. Anything
downstream that consumes a *shortlist* rather than a winner is consuming an
artefact of the metric choice.

## 5. What the probes could not establish

Stated because the project's standard is that assumptions are labelled, not
avoided.

- **All three cases are n-alkanes.** Ideal solutions, monotonic volatility, no
  azeotropes, no corrosion, nothing close-boiling. The friendliest possible
  family. Agreement here does not transfer to a difficult feed.
- **The heuristics all agreed on these feeds, so the cases cannot discriminate
  between them.** Propane is simultaneously the lightest and the most plentiful,
  so "lightest first", "most plentiful first" and "easiest split first" select
  the same sequence and it wins. Nothing was learned about which is right.
- **Feed to each column was the ideal group flow**, not the actual product of
  the column above. Impurity carry-through is hidden by that simplification.
- **Convergence.** Zero failures on ideal alkanes says little about a real feed.

The first two dictate a requirement, in section 9: the test set must be
**adversarial by construction**. On ordinary feeds the heuristics mostly agree
and the research question never arises. The conflict is not hard to resolve; it
is hard to *observe*.

## 6. Scope

**In scope.** Sharp splits only, where each column divides one contiguous group
of an ordered component list into two contiguous subgroups. Simple columns, one
feed, two products. Distillation only. Three to eight components.

**Out of scope, deliberately.** Non-sharp or sloppy splits; thermally coupled,
Petlyuk and dividing-wall configurations; side draws; non-distillation units in
the train; inter-column heat integration; recycles. Each is real, and each is
excluded so that the boundary is stated rather than discovered.

## 7. Architecture

Most of M3 is orchestration over machinery that already exists. Every column in
a train is a binary-key split of a multicomponent group, which is exactly what
sepsyn already screens and designs today.

```
sepsyn/sequencing/
  enumerate.py    sharp-split sequence generation
  train.py        Split, Sequence, ColumnOutcome, SequenceOutcome
  evaluate.py     design each column in order; aggregate cost and vapour
  heuristics.py   proxy scorers and constraint rules
  score.py        heuristic hit-rate against the evaluated ranking
sepsyn/sequencing_rules.yaml
```

| Reused unchanged | Genuinely new |
|---|---|
| The 12 screening rules, applied per column | Sequence enumeration |
| `resolve_column_pressure` | Aggregation across a train |
| Feed condition q | Constraint filtering and tagging |
| Equipment rules | Proxy scoring |
| The verification checks | A `ShortcutColumn` adapter path |

The only new physics is `ShortcutColumn` in place of `BinaryDistillation`. The
existing adapter gains a multicomponent method; the `Simulator` protocol gains
one entry. Nothing about the rule engine changes.

### Types

```python
@dataclass(frozen=True)
class Split:
    group: tuple[str, ...]      # components entering, volatility order
    k: int                      # split point; light = group[:k]
    # light_key = group[k-1], heavy_key = group[k], both derived

@dataclass(frozen=True)
class Sequence:
    splits: tuple[Split, ...]   # N-1 of them

@dataclass(frozen=True)
class ColumnOutcome:
    split: Split
    screening: str              # the verdict from the existing 12 rules
    pressure_Pa: float
    pressure_basis: str
    result: ColumnResult | None
    annualised_cost_USD_yr: float | None
    vapour_kmol_hr: float | None

@dataclass(frozen=True)
class SequenceOutcome:
    sequence: Sequence
    columns: tuple[ColumnOutcome, ...]
    total_cost_USD_yr: float | None
    total_vapour_kmol_hr: float | None
    eliminated_by: str          # "" if it survived; else a rule id and reason
```

## 8. Data flow

```
feed + component tags
  -> enumerate every sharp-split sequence
  -> for each column, in order:
        screen the group with the existing 12 rules
        settle its pressure with resolve_column_pressure
        design it with ShortcutColumn
        pass its ACTUAL products to the next column
  -> eliminate sequences containing an infeasible column, citing the rule
  -> aggregate annualised cost and total vapour load
  -> apply constraint rules
  -> rank
  -> report winner, the near-optimal set, and the proxy scorecard
```

**The near-optimal set, not a leaderboard.** Section 4 measured a sequence
moving up to fourteen of forty-two places depending on the ranking metric, so an
ordered list past the winner asserts precision the evidence does not support.
The report gives the winner, then every sequence whose total cost is within a
stated tolerance of it, presented as an unordered set with both metrics shown.
A Pareto front is deliberately not used: with two objectives that agree on the
winner it would contain almost everything and inform nothing.

**Products propagate.** The feed to a downstream column is the actual product of
the column above it, not the idealised group flow. Impurity carry-through is a
real effect and the sharp-split idealisation hides it. This forces the columns
of a sequence to be solved in order, which costs nothing at 0.01 s per column.

**Sub-mixtures are screened, not assumed.** A pair that is well behaved in the
full feed can be azeotropic once another component is removed. Every column gets
the full screen, and a sequence eliminated this way is eliminated for a reason
that can be printed.

### Component tags

```bash
--feed "Propane:40,Butane:30,HCl:5" --tag HCl:corrosive
```

Tags carry the non-thermodynamic attributes: corrosive, hazardous, fouling,
thermally sensitive. None of these are in CRC, DIPPR or IUPAC, so none can be
derived; they are supplied or they are absent.

If a constraint rule could change the ranking and its tag is absent, that
dimension reports `undetermined` and names what to tag. It does not default to
benign. This matches the existing treatment of glycerol's decomposition
temperature.

## 9. Testing

- **Enumeration**: count equals Catalan(n−1) for n = 2 through 7; every sequence
  has exactly n−1 splits; no duplicates.
- **Known answer**: the alkane case. Direct sequence wins on both metrics.
- **Adversarial set**, the requirement section 5 produced. Feeds constructed so
  the proxies disagree: the most plentiful component placed in the middle of the
  volatility order; a corrosive species positioned so that the easiest split
  leaves it traversing three further columns. Assert the tool *surfaces* the
  disagreement rather than silently resolving it.
- **Sub-mixture azeotrope**: a feed where removing one component leaves an
  azeotropic pair. Assert the sequence is eliminated citing R-03.
- **Ranking robustness**: assert the winner agrees between cost and vapour load
  across the test set, and that the report warns whenever the full orderings
  differ. The 14-of-42 displacement is the reason this check exists.
- **Missing tags**: a corrosive-sensitive feed with no tags returns
  `undetermined` on that dimension and names the tag, rather than ranking as
  though nothing were corrosive.
- **Propagation**: a two-column train where the first column's 1 % impurity
  measurably changes the second column's duty, asserting products propagate
  rather than idealised flows being reused.

## 10. Assumptions carried into the implementation

Listed so they are labelled rather than discovered.

| Assumption | Status |
|---|---|
| Sharp splits are the relevant design space | Scope decision, not a finding |
| Shortcut methods rank sequences correctly | Unverified. M2 exists to measure it |
| Annualised cost is adequate for picking a winner | Supported on three alkane cases; untested on hard feeds |
| The ranked list beyond the winner is meaningful | **Contradicted** at 5 and 6 components. Report as a set |
| Total vapour load is a valid cost surrogate | Standard, and agrees with cost on the winner here |
| Component tags are supplied correctly | Cannot be checked; the tool records who supplied them |

## 11. Implementation order

Two phases. The first is a usable tool on its own and the second depends on it,
so they should not be interleaved.

**Phase A, the ranking.** Enumeration, the `ShortcutColumn` adapter path,
per-column screening and pressure, product propagation, aggregation, the
near-optimal set. Answers "what sequence should I build" and is independently
useful.

**Phase B, the research question.** Constraint rules and tagging, the proxy
scorers, and the scorecard measuring each proxy against Phase A's ranking. This
is the part that answers which heuristic wins when two conflict, and it cannot
begin before Phase A produces the ground truth it scores against.

The adversarial test set belongs to Phase B, since Phase A has nothing to
disagree with.

## 12. Open questions

- ~~Should a constraint eliminate a sequence outright, or attach a materials
  cost multiplier?~~ **RESOLVED 2026-09-08: neither. It COUNTS.**

  Both original options required inventing a number the tool has no source for:
  elimination needs a threshold (how many columns may a corrosive component
  traverse?) and a multiplier needs a materials cost factor. Nothing justifies
  either value, and burying an invented number inside a verdict is precisely
  what this project exists to prevent.

  Instead, exposure is measured and reported beside the cost, WEIGHTED BY FLOW:
  for every sequence, the tagged component's molar flow summed over every
  column it enters.

  Flow weighting was forced by measurement, not chosen for elegance. A plain
  column count saturates, because sharp splits are imperfect and a trace of
  every component propagates almost everywhere. Tagging hexane on the alkane
  train gives a count of three columns for BOTH the direct sequence, which
  carries it at full flow the whole way, and the indirect one, which removes it
  at the first column. A metric that cannot separate those two cannot show the
  trade-off it exists for. Weighting by flow separates them roughly threefold
  and still invents no threshold. The output is a
  trade-off the reader resolves: this route is cheapest and exposes three
  columns to HCl, that one costs eight percent more and exposes one.

  This is the same treatment equipment choices already get: surface the decision
  with its basis, do not silently make it. It also answers the review question
  more honestly than a ranking would, because the conflict between corrosion and
  volatility is shown rather than arbitrated away.

  A materials cost factor remains a sensible future addition for anyone who has
  one, at which point corrosion enters the objective directly and the conflict
  genuinely dissolves rather than being displayed.
- How many components before exhaustive enumeration should give way to a pruned
  search? Measured comfortable at 6 (2 s). Eight is 429 sequences and roughly
  30 s by extrapolation, which is itself an extrapolation and should be measured
  before it is relied on.
