# M3 Phase B: Constraints and Heuristic Scoring — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Answer the review question — when two sequencing heuristics disagree, which one is right — by measuring each against the evaluated ranking Phase A produces, and by showing corrosion exposure as a trade-off rather than arbitrating it away.

**Architecture:** Four classic heuristics become *proxies*: cheap functions that greedily build one sequence from feed properties alone, without designing anything. Phase A's exhaustive ranking is the ground truth they are scored against. Corrosion and hazard tags are counted, not enforced: for every sequence, how many columns each tagged component passes through, reported beside the cost.

**Tech Stack:** Python 3.11+, BioSTEAM 2.53.11, thermosteam 0.53.5, pytest 9.1.1. No new dependencies.

**Spec:** `docs/specs/2026-09-08-multicomponent-sequencing-design.md`

**Depends on:** `docs/plans/2026-09-08-m3-phase-a-sequencing.md`, complete and merged.

## Global Constraints

- Constraints **count**, they do not eliminate or penalise (spec §12, resolved 2026-09-08). Neither a traversal threshold nor a materials cost factor may be invented.
- A proxy never designs a column. It reads feed properties and returns one sequence. That cheapness is what makes it a proxy; it is being tested, not trusted.
- Every proxy records the conditions its relative volatilities were evaluated at. An alpha without its conditions is meaningless, and a proxy is not exempt.
- Tags are supplied by the user. Corrosivity is in no property database and must not be inferred from structure or a curated list.
- If a tag would change what the report says and none was supplied, say so. Do not default to benign.
- Run the full suite before every commit. 307 tests pass at the time of writing; it must stay green.
- The adversarial test set is a deliverable, not scaffolding. It is the only thing that can demonstrate a heuristic conflict, because on ordinary feeds the heuristics agree (spec §5).

---

### Task 1: Component tags

**Files:**
- Create: `sepsyn/sequencing/tags.py`
- Test: `tests/test_component_tags.py`

**Interfaces:**
- Consumes: nothing. Pure Python.
- Produces:
  - `KNOWN_TAGS = frozenset({"corrosive", "hazardous", "fouling", "thermally_sensitive"})`
  - `parse_tags(specs: list[str], names: tuple[str, ...]) -> dict[str, frozenset[str]]`
  - `UnknownTag(ValueError)`

- [ ] **Step 1: Write the failing test**

```python
"""Component tags. Corrosivity is in no property database, so it is supplied.

CRC, DIPPR and IUPAC give boiling points and critical constants. None of them
says whether a component is corrosive, and structure does not settle it either:
corrosivity depends on concentration, temperature and the material of
construction. So the tool is told, or it does not know.
"""
import pytest

from sepsyn.sequencing.tags import KNOWN_TAGS, UnknownTag, parse_tags

NAMES = ("Propane", "HCl", "Water")


def test_a_single_tag_is_parsed():
    assert parse_tags(["HCl:corrosive"], NAMES) == {"HCl": frozenset({"corrosive"})}


def test_several_tags_on_one_component():
    tags = parse_tags(["HCl:corrosive", "HCl:hazardous"], NAMES)
    assert tags["HCl"] == frozenset({"corrosive", "hazardous"})


def test_comma_separated_tags_on_one_component():
    tags = parse_tags(["HCl:corrosive,hazardous"], NAMES)
    assert tags["HCl"] == frozenset({"corrosive", "hazardous"})


def test_untagged_components_are_absent_rather_than_marked_benign():
    """Absent, not tagged 'safe'. The tool has not been told propane is
    harmless; it has simply not been told anything."""
    tags = parse_tags(["HCl:corrosive"], NAMES)
    assert "Propane" not in tags


def test_an_unknown_tag_is_refused_with_the_vocabulary():
    """A typo that parses is a tag that silently never matches a rule, which is
    the failure mode this project exists to catch."""
    with pytest.raises(UnknownTag, match="corrossive"):
        parse_tags(["HCl:corrossive"], NAMES)


def test_the_error_names_what_was_allowed():
    with pytest.raises(UnknownTag) as exc:
        parse_tags(["HCl:sticky"], NAMES)
    for known in KNOWN_TAGS:
        assert known in str(exc.value)


def test_a_tag_on_an_absent_component_is_refused():
    with pytest.raises(UnknownTag, match="Benzene"):
        parse_tags(["Benzene:corrosive"], NAMES)


def test_a_malformed_spec_is_refused():
    with pytest.raises(UnknownTag, match="HCl-corrosive"):
        parse_tags(["HCl-corrosive"], NAMES)


def test_no_specs_gives_no_tags():
    assert parse_tags([], NAMES) == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/projects/process_simulation/sepsyn && ../.venv/bin/python -m pytest tests/test_component_tags.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'sepsyn.sequencing.tags'`

- [ ] **Step 3: Write minimal implementation**

Create `sepsyn/sequencing/tags.py`:

```python
"""Component attributes that no property database carries.

CRC, DIPPR and IUPAC give boiling points and critical constants. None of them
says whether a component is corrosive. Structure does not settle it either:
corrosivity depends on concentration, temperature and the material of
construction, so a functional-group rule would be confidently wrong often
enough to matter.

So these are supplied by the user or they are absent, and absent means the tool
does not know rather than that the component is benign.
"""

KNOWN_TAGS = frozenset({
    "corrosive",
    "hazardous",
    "fouling",
    "thermally_sensitive",
})


class UnknownTag(ValueError):
    """A tag or component that would silently never match anything."""


def parse_tags(specs: list[str],
               names: tuple[str, ...]) -> dict[str, frozenset[str]]:
    """Parse 'HCl:corrosive' or 'HCl:corrosive,hazardous' into a tag map.

    Both an unknown tag and an unknown component are rejected rather than
    ignored. A typo that parses is a tag that never matches a rule, and a rule
    that silently never fires is the failure this project exists to catch.
    """
    tags: dict[str, set[str]] = {}
    for spec in specs:
        if ":" not in spec:
            raise UnknownTag(
                f"expected Component:tag, got {spec!r}. Tags available: "
                f"{', '.join(sorted(KNOWN_TAGS))}"
            )
        name, raw = spec.split(":", 1)
        name = name.strip()
        if name not in names:
            raise UnknownTag(
                f"cannot tag {name!r}: it is not in the feed. Feed contains: "
                f"{', '.join(names)}"
            )
        for tag in (t.strip() for t in raw.split(",")):
            if tag not in KNOWN_TAGS:
                raise UnknownTag(
                    f"unknown tag {tag!r} on {name}. Tags available: "
                    f"{', '.join(sorted(KNOWN_TAGS))}"
                )
            tags.setdefault(name, set()).add(tag)
    return {n: frozenset(v) for n, v in tags.items()}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `../.venv/bin/python -m pytest tests/test_component_tags.py -q`
Expected: PASS, 9 passed

- [ ] **Step 5: Run the full suite**

Run: `../.venv/bin/python -m pytest -q`
Expected: PASS, 316 passed

- [ ] **Step 6: Commit**

```bash
git add sepsyn/sequencing/tags.py tests/test_component_tags.py
git commit -m "feat: component tags for attributes no database carries

Corrosivity is not in CRC, DIPPR or IUPAC, and structure does not settle it
either: it depends on concentration, temperature and material of construction.
So it is supplied or it is absent, and absent means unknown rather than benign.

An unknown tag and a tag on an absent component are both refused. A typo that
parses is a tag that silently never matches a rule, which is the failure mode
this project exists to catch.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Hio3TrGFNZt6VaANMaRCqZ"
```

---

### Task 2: Count exposure

**Files:**
- Modify: `sepsyn/sequencing/evaluate.py`
- Test: `tests/test_exposure.py`

**Interfaces:**
- Consumes: `SequenceOutcome`, `ColumnOutcome`, `evaluate_sequence` from Phase A; `parse_tags` from Task 1.
- Produces: `SequenceOutcome.exposure: dict[str, int]`, mapping a tagged component to the number of columns it passes through. `evaluate_sequence` gains a keyword argument `tags: dict[str, frozenset[str]] | None = None`.

**The rule, restated:** exposure is COUNTED, never used to eliminate or penalise. A threshold would be invented and a cost factor has no source, and burying an invented number in a verdict is the thing this project exists to prevent.

- [ ] **Step 1: Write the failing test**

```python
"""Exposure counting. How many columns does a tagged component pass through?

Counted, never enforced. Eliminating above a threshold would need a number
nothing justifies, and a materials cost multiplier would need a factor the tool
has no source for. Both bury an invented value inside a verdict. The count is
reported beside the cost and the reader resolves the trade-off.
"""
import pytest

from sepsyn.properties import resolve
from sepsyn.sequencing.evaluate import evaluate_sequence
from sepsyn.sequencing.train import Node
from sepsyn.simulators.biosteam_adapter import BioSteamSimulator
from sepsyn.types import Component, Feed

ORDER = ("Propane", "Butane", "Pentane", "Hexane")


def alkane_feed():
    return Feed(
        components=tuple(Component(n, resolve(n), f)
                         for n, f in zip(ORDER, (40.0, 30.0, 20.0, 10.0))),
        T_K=330.0, P_Pa=101325.0,
    )


def direct():
    """Lightest off first, one at a time. Hexane reaches the last column."""
    return Node(group=ORDER, k=1,
                light=Node(group=("Propane",)),
                heavy=Node(group=("Butane", "Pentane", "Hexane"), k=1,
                           light=Node(group=("Butane",)),
                           heavy=Node(group=("Pentane", "Hexane"), k=1,
                                      light=Node(group=("Pentane",)),
                                      heavy=Node(group=("Hexane",)))))


def indirect():
    """Heaviest off first. Hexane leaves at column one."""
    return Node(group=ORDER, k=3,
                light=Node(group=("Propane", "Butane", "Pentane"), k=2,
                           light=Node(group=("Propane", "Butane"), k=1,
                                      light=Node(group=("Propane",)),
                                      heavy=Node(group=("Butane",))),
                           heavy=Node(group=("Pentane",))),
                heavy=Node(group=("Hexane",)))


def test_no_tags_means_no_exposure_reported():
    out = evaluate_sequence(BioSteamSimulator(), alkane_feed(), direct())
    assert out.exposure == {}


def test_a_tagged_component_is_counted_through_every_column_it_enters():
    """Hexane enters all three columns of the direct sequence: it is only
    removed at the last one."""
    tags = {"Hexane": frozenset({"corrosive"})}
    out = evaluate_sequence(BioSteamSimulator(), alkane_feed(), direct(),
                            tags=tags)
    assert out.exposure == {"Hexane": 3}


def test_removing_it_early_lowers_the_count():
    """THE point of the whole feature. Taking hexane off first exposes one
    column instead of three, and that difference is the trade-off against
    cost."""
    tags = {"Hexane": frozenset({"corrosive"})}
    direct_out = evaluate_sequence(BioSteamSimulator(), alkane_feed(),
                                   direct(), tags=tags)
    indirect_out = evaluate_sequence(BioSteamSimulator(), alkane_feed(),
                                     indirect(), tags=tags)
    assert indirect_out.exposure["Hexane"] == 1
    assert direct_out.exposure["Hexane"] == 3


def test_exposure_does_NOT_eliminate_or_change_the_cost():
    """Counted, not enforced. Both sequences remain feasible and their costs
    are identical with and without the tag."""
    tags = {"Hexane": frozenset({"corrosive"})}
    plain = evaluate_sequence(BioSteamSimulator(), alkane_feed(), direct())
    tagged = evaluate_sequence(BioSteamSimulator(), alkane_feed(), direct(),
                               tags=tags)
    assert tagged.feasible and plain.feasible
    assert tagged.total_cost_USD_yr == pytest.approx(plain.total_cost_USD_yr)


def test_a_trace_carried_forward_still_counts_as_exposure():
    """Propane is nominally removed at column one, but 1% of it goes into the
    bottoms and travels on. The metal downstream sees it, so it counts."""
    tags = {"Propane": frozenset({"corrosive"})}
    out = evaluate_sequence(BioSteamSimulator(), alkane_feed(), direct(),
                            tags=tags)
    assert out.exposure["Propane"] > 1, (
        "propagated impurity reaches downstream columns and must be counted")


def test_several_tagged_components_are_counted_separately():
    tags = {"Propane": frozenset({"corrosive"}),
            "Hexane": frozenset({"hazardous"})}
    out = evaluate_sequence(BioSteamSimulator(), alkane_feed(), direct(),
                            tags=tags)
    assert set(out.exposure) == {"Propane", "Hexane"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../.venv/bin/python -m pytest tests/test_exposure.py -q`
Expected: FAIL, `AttributeError: 'SequenceOutcome' object has no attribute 'exposure'`

- [ ] **Step 3: Write minimal implementation**

In `sepsyn/sequencing/evaluate.py`, add a field to `SequenceOutcome`, after `eliminated_by`:

```python
    exposure: dict[str, int] = field(default_factory=dict)
```

and add `field` to the dataclasses import:

```python
from dataclasses import dataclass, field
```

Change the `evaluate_sequence` signature to accept tags:

```python
def evaluate_sequence(sim, feed: Feed, root: Node, *,
                      lk_recovery: float = 0.99,
                      hk_recovery: float = 0.99,
                      tags: dict[str, frozenset[str]] | None = None) -> SequenceOutcome:
```

Inside `walk`, immediately after `group_feed` is built and before screening, record which tagged components entered this column:

```python
        # Exposure is COUNTED, never enforced. A threshold for how many columns
        # a corrosive component may traverse would be invented, and a materials
        # cost multiplier needs a factor the tool has no source for. Both bury
        # an invented number inside a verdict. The count travels beside the cost
        # and the reader resolves the trade-off.
        #
        # Counted from the ACTUAL stream, so a trace carried forward counts:
        # propane nominally leaves at column one, but the 1% in the bottoms
        # still reaches the metal downstream.
        for name in (tags or {}):
            if flows.get(name, 0.0) > 0.0:
                exposure[name] = exposure.get(name, 0) + 1
```

Declare `exposure` alongside `columns` before `walk` is defined:

```python
    exposure: dict[str, int] = {}
```

Pass it into both `SequenceOutcome` constructions:

```python
    if failure:
        return SequenceOutcome(root, tuple(columns), None, None, failure,
                               exposure)
    return SequenceOutcome(
        root, tuple(columns),
        sum(c.annualised_cost_USD_yr for c in columns),
        sum(c.vapour_kmol_hr for c in columns),
        "",
        exposure,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `../.venv/bin/python -m pytest tests/test_exposure.py -q`
Expected: PASS, 6 passed

If `test_a_trace_carried_forward_still_counts_as_exposure` fails with exposure of exactly 1, the count is being taken from `node.group` rather than from `flows`. Take it from `flows`: the group is nominal, the stream is real.

- [ ] **Step 5: Run the full suite**

Run: `../.venv/bin/python -m pytest -q`
Expected: PASS, 322 passed

- [ ] **Step 6: Commit**

```bash
git add sepsyn/sequencing/evaluate.py tests/test_exposure.py
git commit -m "feat: count how many columns a tagged component passes through

Counted, never enforced. Eliminating above a threshold would need a number
nothing justifies, and a materials cost multiplier would need a factor the tool
has no source for; both bury an invented value inside a verdict. The count is
reported beside the cost and the reader resolves the trade-off, which is the
same treatment equipment choices already get.

Counted from the actual stream rather than the nominal group, so a propagated
trace counts: propane leaves at column one on paper, but the 1% in the bottoms
still reaches the metal downstream.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Hio3TrGFNZt6VaANMaRCqZ"
```

---

### Task 3: The four proxy heuristics

**Files:**
- Create: `sepsyn/sequencing/heuristics.py`
- Test: `tests/test_proxy_heuristics.py`

**Interfaces:**
- Consumes: `Node` from `sepsyn.sequencing.train`; `relative_volatilities` from `sepsyn.properties`.
- Produces:
  - `AdjacentAlphas(values: dict[tuple[str, str], float], T_K: float, P_Pa: float, basis: str)`
  - `adjacent_alphas(feed, order, P_Pa) -> AdjacentAlphas`
  - `PROXIES: dict[str, callable]` with keys `easiest_first`, `hardest_last`, `most_plentiful_first`, `equimolar`
  - each proxy: `(order: tuple[str, ...], flows: dict[str, float], alphas: AdjacentAlphas) -> Node`

**What a proxy is:** a textbook heuristic states which split to do *first*, so a proxy chooses one split point for a group and recurses. That produces exactly one sequence per proxy per feed, which is what gets compared against the evaluated winner. A proxy never designs a column.

- [ ] **Step 1: Write the failing test**

```python
"""The four classic heuristics, as cheap proxies for the objective.

Each one states which split to perform FIRST, so each is a rule for choosing a
split point, applied recursively. One proxy produces one sequence from feed
properties alone, designing nothing. That cheapness is the point: proxies exist
to be scored against the evaluated ranking, not trusted.
"""
import pytest

from sepsyn.properties import resolve
from sepsyn.sequencing.heuristics import PROXIES, adjacent_alphas
from sepsyn.types import Component, Feed

ORDER = ("Propane", "Butane", "Pentane", "Hexane")
FLOWS = {"Propane": 40.0, "Butane": 30.0, "Pentane": 20.0, "Hexane": 10.0}


def alkane_feed():
    return Feed(
        components=tuple(Component(n, resolve(n), FLOWS[n]) for n in ORDER),
        T_K=330.0, P_Pa=101325.0,
    )


@pytest.fixture(scope="module")
def alphas():
    return adjacent_alphas(alkane_feed(), ORDER, 101325.0)


def test_alphas_carry_the_conditions_they_were_computed_at(alphas):
    """A proxy is cheap, not exempt. An alpha without its temperature and
    pressure is meaningless whoever is using it."""
    assert alphas.T_K > 0
    assert alphas.P_Pa == 101325.0
    assert alphas.basis


def test_every_adjacent_pair_has_an_alpha(alphas):
    for a, b in zip(ORDER, ORDER[1:]):
        assert alphas.values[(a, b)] > 1.0


def test_there_are_exactly_four_proxies():
    assert set(PROXIES) == {"easiest_first", "hardest_last",
                            "most_plentiful_first", "equimolar"}


@pytest.mark.parametrize("name", ["easiest_first", "hardest_last",
                                  "most_plentiful_first", "equimolar"])
def test_each_proxy_returns_a_complete_sequence(name, alphas):
    root = PROXIES[name](ORDER, FLOWS, alphas)
    assert len(root.splits()) == len(ORDER) - 1
    assert root.group == ORDER


def test_easiest_first_cuts_where_alpha_is_largest(alphas):
    """The pair with the widest volatility gap is split first."""
    root = PROXIES["easiest_first"](ORDER, FLOWS, alphas)
    widest = max(alphas.values, key=alphas.values.get)
    assert (root.light_key, root.heavy_key) == widest


def test_hardest_last_cuts_where_alpha_is_largest_too_but_not_by_accident():
    """Deferring the hardest split and doing the easiest first are the same
    instruction on a first cut. They diverge on the SUBSEQUENT cuts, which is
    why both exist and why they must be scored separately."""
    order = ("A", "B", "C")
    flows = {"A": 1.0, "B": 1.0, "C": 1.0}
    from sepsyn.sequencing.heuristics import AdjacentAlphas
    a = AdjacentAlphas({("A", "B"): 5.0, ("B", "C"): 1.2}, 300.0, 1e5, "test")
    assert PROXIES["easiest_first"](order, flows, a).k == 1
    assert PROXIES["hardest_last"](order, flows, a).k == 1


def test_most_plentiful_first_removes_the_largest_flow():
    """Propane is 40 of 100, so it comes off first as a single product."""
    root = PROXIES["most_plentiful_first"](ORDER, FLOWS, None)
    assert root.k == 1
    assert root.light_group == ("Propane",)


def test_most_plentiful_first_can_cut_in_the_MIDDLE():
    """If the most plentiful component sits in the middle it must still be
    isolated, which means the first cut is not at an end. This is the case
    that makes the proxy disagree with the others."""
    order = ("A", "B", "C")
    flows = {"A": 10.0, "B": 80.0, "C": 10.0}
    root = PROXIES["most_plentiful_first"](order, flows, None)
    assert root.k in (1, 2)
    assert any(s.light_group == ("B",) or s.heavy_group == ("B",)
               for s in root.splits())


def test_equimolar_splits_the_flow_as_evenly_as_it_can():
    order = ("A", "B", "C", "D")
    flows = {"A": 25.0, "B": 25.0, "C": 25.0, "D": 25.0}
    root = PROXIES["equimolar"](order, flows, None)
    assert root.k == 2


def test_a_proxy_designs_nothing(alphas):
    """No simulator is passed and none may be reached. If a proxy needed a
    design it would not be a proxy, and scoring it against the designed answer
    would be circular."""
    import sepsyn.sequencing.heuristics as h
    source = open(h.__file__).read()
    assert "design_multicomponent" not in source
    assert "BioSteam" not in source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../.venv/bin/python -m pytest tests/test_proxy_heuristics.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'sepsyn.sequencing.heuristics'`

- [ ] **Step 3: Write minimal implementation**

Create `sepsyn/sequencing/heuristics.py`:

```python
"""The four classic sequencing heuristics, as proxies.

A proxy is a cheap ESTIMATOR of the objective, not a competitor to it. The spec
argues that "easiest split first", "hardest last", "most plentiful first" and
"favour equimolar splits" are four estimators of one quantity, invented before
anyone could evaluate 42 sequences in two seconds. They exist here to be
SCORED against the evaluated ranking, not trusted.

Each textbook rule states which split to perform first, so each proxy chooses a
split point for a group and recurses. One proxy yields one sequence per feed,
and designs nothing on the way. If a proxy needed a design, scoring it against
the designed answer would be circular.
"""
from dataclasses import dataclass

from sepsyn.sequencing.train import Node


@dataclass(frozen=True)
class AdjacentAlphas:
    """Relative volatility for each adjacent pair, WITH its conditions.

    Same discipline as sepsyn.types.Alpha. A proxy is cheap, not exempt: an
    alpha quoted without its temperature and pressure is meaningless whoever is
    holding it.
    """
    values: dict[tuple[str, str], float]
    T_K: float
    P_Pa: float
    basis: str


def adjacent_alphas(feed, order: tuple[str, ...], P_Pa: float) -> AdjacentAlphas:
    """Alphas for the adjacent pairs of the ordered list, at one condition.

    ONE condition for the whole train, deliberately. Each column in a real
    sequence settles its own pressure, but a proxy that had to resolve pressures
    would be doing the expensive part of the work it exists to avoid. The single
    reference condition is an approximation, and it is recorded here so that the
    approximation travels with the number.
    """
    from sepsyn.properties import relative_volatilities

    alphas = relative_volatilities(feed, P_Pa)
    by_pair = {a.pair: a.value for a in alphas}
    values: dict[tuple[str, str], float] = {}
    for a, b in zip(order, order[1:]):
        if (a, b) in by_pair:
            values[(a, b)] = by_pair[(a, b)]
        elif (b, a) in by_pair and by_pair[(b, a)] > 0:
            values[(a, b)] = 1.0 / by_pair[(b, a)]
    T = alphas[0].T_K if alphas else 0.0
    return AdjacentAlphas(
        values=values, T_K=T, P_Pa=P_Pa,
        basis=(f"bubble point of the whole feed at {P_Pa/1e5:.3f} bar, one "
               f"reference condition for the entire train"),
    )


def _build(order: tuple[str, ...], choose) -> Node:
    """Apply a split-point rule recursively to make one sequence."""
    if len(order) == 1:
        return Node(group=order)
    k = choose(order)
    return Node(group=order, k=k,
                light=_build(order[:k], choose),
                heavy=_build(order[k:], choose))


def _easiest_first(order, flows, alphas):
    """Split where the volatility gap is widest."""
    def choose(group):
        return max(range(1, len(group)),
                   key=lambda k: alphas.values.get((group[k - 1], group[k]), 1.0))
    return _build(order, choose)


def _hardest_last(order, flows, alphas):
    """Defer the narrowest volatility gap.

    On a first cut this agrees with easiest_first, because avoiding the hardest
    pair and taking the easiest one are the same instruction when there is one
    cut to make. They diverge further down, which is why both are scored.
    """
    def choose(group):
        if len(group) == 2:
            return 1
        hardest = min(range(1, len(group)),
                      key=lambda k: alphas.values.get((group[k - 1], group[k]), 1.0))
        options = [k for k in range(1, len(group)) if k != hardest]
        return max(options or [hardest],
                   key=lambda k: alphas.values.get((group[k - 1], group[k]), 1.0))
    return _build(order, choose)


def _most_plentiful_first(order, flows, alphas):
    """Isolate the largest flow as early as possible.

    The cut is made on whichever side of the most plentiful component is
    nearer, so that it is removed in the fewest cuts. When it sits in the middle
    this does NOT cut at an end, which is exactly where this proxy parts company
    with the volatility ones.
    """
    def choose(group):
        biggest = max(group, key=lambda n: flows.get(n, 0.0))
        i = group.index(biggest)
        return i if i > 0 else 1
    return _build(order, choose)


def _equimolar(order, flows, alphas):
    """Split the molar flow as evenly as the cut points allow."""
    def choose(group):
        total = sum(flows.get(n, 0.0) for n in group)
        def imbalance(k):
            light = sum(flows.get(n, 0.0) for n in group[:k])
            return abs(light - (total - light))
        return min(range(1, len(group)), key=imbalance)
    return _build(order, choose)


PROXIES = {
    "easiest_first": _easiest_first,
    "hardest_last": _hardest_last,
    "most_plentiful_first": _most_plentiful_first,
    "equimolar": _equimolar,
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `../.venv/bin/python -m pytest tests/test_proxy_heuristics.py -q`
Expected: PASS, 13 passed

- [ ] **Step 5: Run the full suite**

Run: `../.venv/bin/python -m pytest -q`
Expected: PASS, 335 passed

- [ ] **Step 6: Commit**

```bash
git add sepsyn/sequencing/heuristics.py tests/test_proxy_heuristics.py
git commit -m "feat: the four classic heuristics as scorable proxies

A proxy is a cheap estimator of the objective, not a competitor to it. Each
textbook rule states which split to do first, so each proxy chooses a split
point and recurses, producing one sequence per feed and designing nothing.

Designing nothing is enforced by a test that reads the module source: if a
proxy needed a design, scoring it against the designed answer would be
circular.

The alphas carry the condition they were computed at. One reference condition
for the whole train is an approximation, since each real column settles its own
pressure, and it is recorded so the approximation travels with the number.

easiest_first and hardest_last agree on a first cut, because avoiding the
hardest pair and taking the easiest are the same instruction when one cut is to
be made. They diverge further down, which is why both are scored separately.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Hio3TrGFNZt6VaANMaRCqZ"
```

---

### Task 4: The scorecard

**Files:**
- Create: `sepsyn/sequencing/score.py`
- Test: `tests/test_heuristic_scorecard.py`

**Interfaces:**
- Consumes: `Ranking`, `sweep` from Phase A's `rank.py`; `PROXIES`, `adjacent_alphas` from Task 3; `label` from `enumeration.py`.
- Produces:
  - `ProxyScore(name: str, sequence_name: str, picked_winner: bool, within_near_optimal: bool, cost_penalty: float | None, cost_USD_yr: float | None)`
  - `Scorecard(scores: tuple[ProxyScore, ...], winner_name: str, proxies_agree: bool)`
  - `score_proxies(feed, order, ranking: Ranking, P_Pa: float) -> Scorecard`

- [ ] **Step 1: Write the failing test**

```python
"""Scoring the proxies against the evaluated ranking.

This is the module that answers the review question. When two heuristics
disagree, which is right? Not argued: measured. The exhaustive ranking is the
ground truth, each proxy names one sequence, and the scorecard reports whether
it picked the winner and what it cost to be wrong.
"""
import pytest

from sepsyn.properties import resolve
from sepsyn.sequencing.rank import sweep
from sepsyn.sequencing.score import score_proxies
from sepsyn.simulators.biosteam_adapter import BioSteamSimulator
from sepsyn.types import Component, Feed

ORDER = ("Propane", "Butane", "Pentane", "Hexane")


def alkane_feed():
    return Feed(
        components=tuple(Component(n, resolve(n), f)
                         for n, f in zip(ORDER, (40.0, 30.0, 20.0, 10.0))),
        T_K=330.0, P_Pa=101325.0,
    )


@pytest.fixture(scope="module")
def card():
    feed = alkane_feed()
    ranking = sweep(BioSteamSimulator(), feed, ORDER)
    return score_proxies(feed, ORDER, ranking, 101325.0)


def test_every_proxy_is_scored(card):
    assert {s.name for s in card.scores} == {
        "easiest_first", "hardest_last", "most_plentiful_first", "equimolar"}


def test_each_score_names_the_sequence_that_proxy_chose(card):
    for s in card.scores:
        assert s.sequence_name


def test_a_proxy_that_picked_the_winner_is_marked_as_such(card):
    """On this alkane feed every heuristic picks the same sequence and it
    wins, so all four should score a hit. That is exactly why this feed cannot
    discriminate between them, which is the adversarial set's job."""
    assert all(s.picked_winner for s in card.scores)
    assert card.proxies_agree is True


def test_the_cost_penalty_of_a_correct_proxy_is_zero(card):
    for s in card.scores:
        if s.picked_winner:
            assert s.cost_penalty == pytest.approx(0.0, abs=1e-9)


def test_the_scorecard_names_the_winner_it_scored_against(card):
    assert card.winner_name


def test_a_proxy_choosing_a_worse_sequence_reports_what_it_cost():
    """Constructed so the proxies disagree. The scorecard must quantify being
    wrong, not merely record it."""
    order = ("A", "B", "C")
    from sepsyn.sequencing.evaluate import SequenceOutcome
    from sepsyn.sequencing.rank import rank
    from sepsyn.sequencing.train import Node

    good = Node(group=order, k=1, light=Node(group=("A",)),
                heavy=Node(group=("B", "C"), k=1, light=Node(group=("B",)),
                           heavy=Node(group=("C",))))
    bad = Node(group=order, k=2,
               light=Node(group=("A", "B"), k=1, light=Node(group=("A",)),
                          heavy=Node(group=("B",))),
               heavy=Node(group=("C",)))
    ranking = rank([SequenceOutcome(good, (), 100.0, 10.0, ""),
                    SequenceOutcome(bad, (), 150.0, 15.0, "")])
    assert ranking.winner.total_cost_USD_yr == 100.0

    from sepsyn.sequencing.enumeration import label
    from sepsyn.sequencing.score import ProxyScore
    s = ProxyScore("made_up", label(bad), False, False, 0.5, 150.0)
    assert s.cost_penalty == 0.5


def test_a_proxy_naming_a_sequence_that_was_eliminated_is_not_a_hit():
    """A heuristic can happily recommend a train containing an azeotropic
    column. That is a miss, and a particularly informative one."""
    feed = Feed(
        components=tuple(Component(n, resolve(n), f) for n, f in
                         [("Acetone", 30.0), ("Ethanol", 40.0), ("Water", 30.0)]),
        T_K=330.0, P_Pa=101325.0)
    order = ("Acetone", "Ethanol", "Water")
    ranking = sweep(BioSteamSimulator(), feed, order)
    assert ranking.winner is None
    card = score_proxies(feed, order, ranking, 101325.0)
    assert all(not s.picked_winner for s in card.scores)
    assert all(s.cost_penalty is None for s in card.scores)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../.venv/bin/python -m pytest tests/test_heuristic_scorecard.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'sepsyn.sequencing.score'`

- [ ] **Step 3: Write minimal implementation**

Create `sepsyn/sequencing/score.py`:

```python
"""Score each proxy against the evaluated ranking.

This is the module that answers the question the whole milestone exists for.
When two textbook heuristics disagree about which split to do first, which one
is right? The answer is not argued from authority: the exhaustive ranking is
the ground truth, each proxy names one sequence, and the scorecard reports
whether it picked the winner and what being wrong cost.
"""
from dataclasses import dataclass

from sepsyn.sequencing.enumeration import label
from sepsyn.sequencing.heuristics import PROXIES, adjacent_alphas
from sepsyn.sequencing.rank import Ranking


@dataclass(frozen=True)
class ProxyScore:
    name: str
    sequence_name: str
    picked_winner: bool
    within_near_optimal: bool
    cost_penalty: float | None
    """Fraction above the winner's cost. None when the proxy named a sequence
    that could not be designed, or when nothing could be."""
    cost_USD_yr: float | None


@dataclass(frozen=True)
class Scorecard:
    scores: tuple[ProxyScore, ...]
    winner_name: str
    proxies_agree: bool
    """True when every proxy named the same sequence. On such a feed the
    scorecard cannot discriminate between them, however confident it looks."""


def score_proxies(feed, order: tuple[str, ...], ranking: Ranking,
                  P_Pa: float) -> Scorecard:
    alphas = adjacent_alphas(feed, order, P_Pa)
    flows = {c.name: c.flow_kmol_hr for c in feed.components}

    costs: dict[str, float] = {}
    near: set[str] = set()
    if ranking.winner is not None:
        for o in [ranking.winner, *ranking.near_optimal]:
            near.add(o.name)
    for o in list(ranking.near_optimal) + (
            [ranking.winner] if ranking.winner else []):
        costs[o.name] = o.total_cost_USD_yr

    winner_name = ranking.winner.name if ranking.winner else ""
    winner_cost = ranking.winner.total_cost_USD_yr if ranking.winner else None

    scores = []
    chosen_names = set()
    for name, proxy in PROXIES.items():
        picked = label(proxy(order, flows, alphas))
        chosen_names.add(picked)
        cost = costs.get(picked)
        penalty = (None if (cost is None or not winner_cost)
                   else cost / winner_cost - 1.0)
        scores.append(ProxyScore(
            name=name,
            sequence_name=picked,
            picked_winner=(picked == winner_name and bool(winner_name)),
            within_near_optimal=(picked in near),
            cost_penalty=penalty,
            cost_USD_yr=cost,
        ))
    return Scorecard(tuple(scores), winner_name, len(chosen_names) == 1)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `../.venv/bin/python -m pytest tests/test_heuristic_scorecard.py -q`
Expected: PASS, 7 passed

Note: `costs` only holds sequences inside the near-optimal set, so a proxy naming a feasible but expensive sequence reports `cost_penalty` of `None`. That is a real limitation and Task 5 fixes it by having `score_proxies` look up every evaluated outcome, not only the near-optimal ones. Do not fix it here; the test for it belongs with the adversarial set that exercises it.

- [ ] **Step 5: Run the full suite**

Run: `../.venv/bin/python -m pytest -q`
Expected: PASS, 342 passed

- [ ] **Step 6: Commit**

```bash
git add sepsyn/sequencing/score.py tests/test_heuristic_scorecard.py
git commit -m "feat: score each heuristic against the evaluated ranking

The module the milestone exists for. When two textbook heuristics disagree
about which split to do first, which is right? Not argued: measured. The
exhaustive ranking is the ground truth, each proxy names one sequence, and the
scorecard reports whether it picked the winner and what being wrong cost.

proxies_agree is reported explicitly, because a feed on which every proxy picks
the same sequence cannot discriminate between them no matter how confident the
scorecard looks. On the alkane feed all four agree and all four are right,
which demonstrates the machinery and settles nothing.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Hio3TrGFNZt6VaANMaRCqZ"
```

---

### Task 5: The adversarial test set

**Files:**
- Create: `tests/test_adversarial_feeds.py`
- Modify: `sepsyn/sequencing/score.py` (cost lookup across all evaluated outcomes)

**Interfaces:**
- Consumes: everything from Tasks 3 and 4.
- Produces: no new names. `score_proxies` gains an `outcomes` source so a proxy naming any feasible sequence gets a cost, not only one inside the near-optimal set.

**Why this is a deliverable and not scaffolding:** the Phase A probes showed that on ordinary feeds every heuristic picks the same sequence, so nothing is learned. These feeds are built so the heuristics disagree. Without them the scorecard is machinery with nothing to measure.

- [ ] **Step 1: Write the failing test**

```python
"""Feeds built so the heuristics disagree.

The Phase A probes measured that on n-alkane feeds every proxy picks the same
sequence, because the lightest component is also the most plentiful. Nothing
is learned from a case where nobody disagrees. These feeds are constructed to
create the conflict the review asked about.

The conflict is not hard to resolve. It is hard to OBSERVE, and that is what
this file is for.
"""
import pytest

from sepsyn.properties import resolve
from sepsyn.sequencing.rank import sweep
from sepsyn.sequencing.score import score_proxies
from sepsyn.simulators.biosteam_adapter import BioSteamSimulator
from sepsyn.types import Component, Feed

P = 101325.0


def feed_of(order, flows, T_K=330.0):
    return Feed(
        components=tuple(Component(n, resolve(n), f)
                         for n, f in zip(order, flows)),
        T_K=T_K, P_Pa=P,
    )


# The most plentiful component sits in the MIDDLE of the volatility order, so
# "remove the most plentiful first" cannot agree with "take an end off first".
MIDDLE_HEAVY_ORDER = ("Propane", "Butane", "Pentane", "Hexane")
MIDDLE_HEAVY_FLOWS = (10.0, 60.0, 20.0, 10.0)


@pytest.fixture(scope="module")
def middle_heavy():
    feed = feed_of(MIDDLE_HEAVY_ORDER, MIDDLE_HEAVY_FLOWS)
    ranking = sweep(BioSteamSimulator(), feed, MIDDLE_HEAVY_ORDER)
    return feed, ranking, score_proxies(feed, MIDDLE_HEAVY_ORDER, ranking, P)


def test_the_feed_actually_creates_a_disagreement(middle_heavy):
    """The premise of the whole file. If the proxies agree here, the feed is
    not adversarial and the case proves nothing."""
    _, _, card = middle_heavy
    assert card.proxies_agree is False, (
        "this feed was constructed to make the heuristics disagree; if they "
        "agree it cannot discriminate between them and must be replaced")


def test_at_least_two_proxies_name_different_sequences(middle_heavy):
    _, _, card = middle_heavy
    assert len({s.sequence_name for s in card.scores}) >= 2


def test_the_scorecard_says_which_proxy_was_right(middle_heavy):
    """The answer to the review question, on this feed."""
    _, _, card = middle_heavy
    hits = [s.name for s in card.scores if s.picked_winner]
    misses = [s.name for s in card.scores if not s.picked_winner]
    assert hits, "no proxy picked the winner, which is itself a finding"
    assert misses, "if every proxy is right the feed is not adversarial"


def test_being_wrong_is_QUANTIFIED_not_merely_recorded(middle_heavy):
    """A miss must carry what it cost. 'This heuristic is wrong' is an
    opinion; 'this heuristic costs 12% more' is a measurement."""
    _, _, card = middle_heavy
    for s in card.scores:
        if not s.picked_winner:
            assert s.cost_penalty is not None, (
                "a proxy naming a feasible sequence must report its penalty")
            assert s.cost_penalty > 0


def test_the_disagreement_is_recorded_against_the_ground_truth(middle_heavy):
    _, ranking, card = middle_heavy
    assert ranking.winner is not None
    assert card.winner_name == ranking.winner.name


def test_the_alkane_control_still_shows_agreement():
    """The control. On an ordinary feed the proxies agree, which is why an
    adversarial set had to be constructed at all."""
    order = ("Propane", "Butane", "Pentane", "Hexane")
    feed = feed_of(order, (40.0, 30.0, 20.0, 10.0))
    ranking = sweep(BioSteamSimulator(), feed, order)
    card = score_proxies(feed, order, ranking, P)
    assert card.proxies_agree is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../.venv/bin/python -m pytest tests/test_adversarial_feeds.py -q`
Expected: FAIL. `test_being_wrong_is_QUANTIFIED_not_merely_recorded` fails with `cost_penalty is None`, because Task 4's cost lookup only covers the near-optimal set.

If `test_the_feed_actually_creates_a_disagreement` also fails, the flows above do not produce a conflict for these components. Do NOT weaken the assertion. Adjust the flows until the proxies genuinely disagree, and record in the test docstring what made them diverge; a feed that cannot create the conflict is not an adversarial feed.

- [ ] **Step 3: Write minimal implementation**

In `sepsyn/sequencing/score.py`, replace the cost-lookup block in `score_proxies`:

```python
    # Every evaluated sequence, not only the near-optimal ones. A proxy that
    # names a feasible but expensive train must still report what it cost;
    # otherwise being badly wrong is indistinguishable from naming something
    # that could not be built.
    costs: dict[str, float] = {}
    near: set[str] = set()
    for o in ranking.all_feasible:
        costs[o.name] = o.total_cost_USD_yr
    for o in ranking.near_optimal:
        near.add(o.name)
```

In `sepsyn/sequencing/rank.py`, add the field to `Ranking` after `near_optimal`:

```python
    all_feasible: tuple[SequenceOutcome, ...] = ()
```

and populate it in both `return Ranking(...)` sites: `all_feasible=()` in the no-feasible branch, and `all_feasible=tuple(by_cost)` in the main branch.

- [ ] **Step 4: Run test to verify it passes**

Run: `../.venv/bin/python -m pytest tests/test_adversarial_feeds.py -q`
Expected: PASS, 6 passed

- [ ] **Step 5: Run the full suite**

Run: `../.venv/bin/python -m pytest -q`
Expected: PASS, 348 passed

- [ ] **Step 6: Commit**

```bash
git add tests/test_adversarial_feeds.py sepsyn/sequencing/score.py sepsyn/sequencing/rank.py
git commit -m "feat: adversarial feeds, where the heuristics actually disagree

A deliverable, not scaffolding. The Phase A probes measured that on n-alkane
feeds every proxy picks the same sequence, because the lightest component is
also the most plentiful; nothing is learned from a case where nobody disagrees.
Putting the most plentiful component in the MIDDLE of the volatility order
makes 'remove the most plentiful first' incompatible with taking an end off
first, and the conflict appears.

The first test asserts the feed is genuinely adversarial. If the proxies agree
on it the case proves nothing and must be replaced rather than the assertion
weakened.

Scoring now looks up cost across every feasible sequence rather than only the
near-optimal ones, so a proxy naming a feasible but expensive train reports its
penalty. Being badly wrong and naming something unbuildable were previously
indistinguishable.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Hio3TrGFNZt6VaANMaRCqZ"
```

---

### Task 6: Report the trade-off and the scorecard

**Files:**
- Modify: `sepsyn/sequencing/report.py`
- Modify: `sepsyn/cli.py`
- Test: `tests/test_sequence_report_phase_b.py`

**Interfaces:**
- Consumes: `Scorecard` from Task 4, `SequenceOutcome.exposure` from Task 2, `parse_tags` from Task 1.
- Produces: `format_sequencing(ranking, scorecard=None, tags=None) -> str`; CLI flag `--tag` (repeatable).

- [ ] **Step 1: Write the failing test**

```python
"""The Phase B report: exposure as a trade-off, and the heuristic scorecard."""
import pytest

from sepsyn.cli import main

BASE = ["--feed", "Propane:10,Butane:60,Pentane:20,Hexane:10", "--T", "330",
        "--sequence", "--order", "Propane,Butane,Pentane,Hexane"]


def test_the_scorecard_is_printed(capsys):
    assert main(BASE) == 0
    out = capsys.readouterr().out
    assert "HEURISTICS" in out
    for name in ("easiest_first", "most_plentiful_first"):
        assert name in out


def test_it_says_which_heuristic_picked_the_winner(capsys):
    main(BASE)
    out = capsys.readouterr().out
    assert "picked the winner" in out.lower() or "correct" in out.lower()


def test_a_wrong_heuristic_shows_what_it_cost(capsys):
    main(BASE)
    assert "%" in capsys.readouterr().out


def test_exposure_is_reported_when_a_component_is_tagged(capsys):
    assert main(BASE + ["--tag", "Hexane:corrosive"]) == 0
    out = capsys.readouterr().out
    assert "EXPOSURE" in out
    assert "Hexane" in out
    assert "corrosive" in out


def test_the_report_says_exposure_did_not_change_the_ranking(capsys):
    """It is counted, not enforced. A reader must not assume the cheapest
    sequence was chosen with corrosion weighed in."""
    main(BASE + ["--tag", "Hexane:corrosive"])
    out = capsys.readouterr().out.lower()
    assert "not" in out and "rank" in out


def test_no_exposure_section_without_tags(capsys):
    main(BASE)
    assert "EXPOSURE" not in capsys.readouterr().out


def test_an_unknown_tag_is_refused_before_anything_is_designed(capsys):
    code = main(BASE + ["--tag", "Hexane:corrossive"])
    assert code == 2
    assert "corrossive" in capsys.readouterr().out


def test_the_report_warns_when_the_proxies_all_agree(capsys):
    """On an ordinary feed the heuristics agree, so the scorecard cannot tell
    them apart. Saying so is the difference between a measurement and a
    coincidence presented as one."""
    main(["--feed", "Propane:40,Butane:30,Pentane:20,Hexane:10", "--T", "330",
          "--sequence", "--order", "Propane,Butane,Pentane,Hexane"])
    out = capsys.readouterr().out.lower()
    assert "agree" in out
    assert "cannot" in out or "does not" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../.venv/bin/python -m pytest tests/test_sequence_report_phase_b.py -q`
Expected: FAIL, `unrecognized arguments: --tag` and no `HEURISTICS` section.

- [ ] **Step 3: Write minimal implementation**

In `sepsyn/sequencing/report.py`, change the signature and append two sections before the `ELIMINATED` block:

```python
def format_sequencing(ranking: Ranking, scorecard=None, tags=None) -> str:
```

```python
    if tags and ranking.winner is not None:
        lines.append("")
        lines.append("EXPOSURE  (counted, NOT used to rank)")
        lines.extend(_wrap(
            "  ",
            "How many columns each tagged component passes through. This did "
            "not change the ranking above and no sequence was eliminated for "
            "it: a threshold would be invented and a materials cost factor has "
            "no source. The trade-off is yours to resolve."))
        for o in [ranking.winner, *[x for x in ranking.near_optimal
                                    if x is not ranking.winner]]:
            if not o.exposure:
                continue
            detail = ", ".join(
                f"{name} ({'/'.join(sorted(tags.get(name, ())))}) through "
                f"{n} of {len(o.columns)} columns"
                for name, n in sorted(o.exposure.items()))
            lines.append(f"    {o.name}")
            lines.extend(_wrap("      ", detail))
            lines.append(f"      ${o.total_cost_USD_yr:,.0f}/yr")

    if scorecard is not None and scorecard.scores:
        lines.append("")
        lines.append("HEURISTICS  (scored against the evaluated ranking)")
        if scorecard.proxies_agree:
            lines.extend(_wrap(
                "  ",
                "Every heuristic picked the same sequence on this feed, so "
                "this scorecard cannot tell them apart. Agreement here is not "
                "evidence that any of them is right."))
        for s in sorted(scorecard.scores, key=lambda s: s.name):
            if s.picked_winner:
                verdict = "picked the winner"
            elif s.cost_penalty is None:
                verdict = "named a sequence that could not be designed"
            else:
                verdict = f"{s.cost_penalty:+.1%} worse than the winner"
            lines.append(f"    {s.name:<22} {verdict}")
            lines.extend(_wrap("      ", s.sequence_name))
```

In `sepsyn/cli.py`, add the flag beside `--order`:

```python
    p.add_argument("--tag", action="append", default=[],
                   help="mark a component, e.g. --tag HCl:corrosive. Counted "
                        "and reported, never used to rank or eliminate. "
                        "Repeatable")
```

and replace the sequencing block's final three lines with:

```python
        from sepsyn.sequencing.rank import sweep
        from sepsyn.sequencing.report import format_sequencing
        from sepsyn.sequencing.score import score_proxies
        from sepsyn.sequencing.tags import UnknownTag, parse_tags
        from sepsyn.simulators.biosteam_adapter import BioSteamSimulator
        try:
            tags = parse_tags(args.tag, feed.names)
        except UnknownTag as exc:
            emit(f"\n{exc}")
            save()
            return 2
        ranking = sweep(BioSteamSimulator(), feed, order, tags=tags or None)
        card = score_proxies(feed, order, ranking, feed.P_Pa)
        emit()
        emit(format_sequencing(ranking, card, tags))
        save()
        return 0
```

In `sepsyn/sequencing/rank.py`, `sweep` already forwards `**kw` to `evaluate_sequence`, so `tags=` reaches it with no change.

- [ ] **Step 4: Run test to verify it passes**

Run: `../.venv/bin/python -m pytest tests/test_sequence_report_phase_b.py -q`
Expected: PASS, 8 passed

- [ ] **Step 5: Run the full suite and read the output**

Run: `../.venv/bin/python -m pytest -q`
Expected: PASS, 356 passed

Then run it and read it:

```bash
../.venv/bin/python -m sepsyn.cli --feed "Propane:10,Butane:60,Pentane:20,Hexane:10" \
  --T 330 --sequence --order "Propane,Butane,Pentane,Hexane" --tag Hexane:corrosive
```

Check by eye: a scorecard naming which heuristic won and by how much the others lost, and an exposure block stating plainly that it did not affect the ranking.

- [ ] **Step 6: Commit**

```bash
git add sepsyn/sequencing/report.py sepsyn/cli.py tests/test_sequence_report_phase_b.py
git commit -m "feat: report the exposure trade-off and the heuristic scorecard

The exposure block states in its heading that it is counted and NOT used to
rank, because a reader who assumes corrosion was weighed into the winner would
be badly misled.

The scorecard says which heuristic picked the winner and quantifies the others:
'12.4% worse than the winner' rather than 'wrong'. When every proxy agrees it
says so and warns that agreement is not evidence any of them is right, which is
the difference between a measurement and a coincidence presented as one.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Hio3TrGFNZt6VaANMaRCqZ"
```

---

## Self-review

**Spec coverage.** §2 classification: proxies (T3), constraints as counted exposure (T2), objective already in Phase A. §5 adversarial requirement: T5, with the control case pinned. §8 tags: T1, refusal on unknown tags and absent components. §9 testing: adversarial set (T5), missing tags (T1, T6). §12 resolved open question: T2 counts rather than eliminates, and the report says so. Phase A is untouched apart from two additive fields.

**Placeholder scan.** No TBD, no "similar to Task N", no "add error handling". Every code step carries its code. Task 4 step 4 states a known limitation and says explicitly not to fix it there; Task 5 step 2 forbids weakening the adversarial assertion if the constructed feed fails to create a conflict.

**Type consistency.** `AdjacentAlphas` is constructed in Task 3 and consumed in Tasks 3 and 4. `ProxyScore` fields are used identically in Tasks 4, 5 and 6. `Ranking.all_feasible` is added in Task 5 with a default so Task 4's construction sites stay valid. `SequenceOutcome.exposure` is added with `field(default_factory=dict)` in Task 2, so every Phase A construction of it continues to work unchanged; the Phase A tests that build `SequenceOutcome` positionally with five arguments are unaffected.

**One risk worth naming.** Task 5 assumes the constructed middle-heavy feed actually makes the proxies disagree. That is a claim about chemistry, not about code, and it may take a couple of attempts at the flows. The plan handles it by asserting the disagreement first, so a feed that fails to create one fails loudly rather than passing as a null result.
