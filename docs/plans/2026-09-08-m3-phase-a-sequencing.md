# M3 Phase A: Sequence Enumeration and Ranking — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enumerate every sharp-split distillation sequence for a 3 to 8 component feed, screen and design each column, and report the cheapest sequence together with the set that is statistically indistinguishable from it.

**Architecture:** A sequence is a binary tree of sharp splits over a volatility-ordered component list. Evaluation walks that tree, feeding each column the *actual product* of its parent, screening it with the twelve existing rules, settling its pressure with the existing resolver, and designing it with BioSTEAM's multicomponent `ShortcutColumn`. Almost nothing about the rule engine changes; this is orchestration over machinery that already exists.

**Tech Stack:** Python 3.11+, BioSTEAM 2.53.11 (`ShortcutColumn`), thermosteam 0.53.5, pytest 9.1.1.

**Spec:** `docs/specs/2026-09-08-multicomponent-sequencing-design.md`

## Global Constraints

- Sharp splits only. Each column divides one contiguous group into two contiguous subgroups. Non-sharp splits, side draws, thermal coupling and dividing-wall columns are out of scope (spec §6).
- Distillation only. No other unit types enter the train.
- 3 to 8 components.
- Products propagate: the feed to a downstream column is the actual product of the column above it, never the idealised group flow (spec §8).
- Every column is screened with the existing twelve rules. A sequence eliminated by screening must carry the rule id that eliminated it.
- The winner is reported as a winner; everything past it is an **unordered near-optimal set**, never an ordered leaderboard. Measured justification: a sequence moves up to 14 of 42 places depending on ranking metric (spec §4).
- No network access at any point. All property data is local.
- Run the full suite (`../.venv/bin/python -m pytest -q`) before every commit. It must stay green; 251 tests pass at the time of writing.
- Phase B (component tags, constraint rules, proxy scoring, adversarial test set) is **not** in this plan and gets its own.

---

### Task 1: Sequence tree and enumeration

**Files:**
- Create: `sepsyn/sequencing/__init__.py`
- Create: `sepsyn/sequencing/train.py`
- Create: `sepsyn/sequencing/enumeration.py`
- Test: `tests/test_sequence_enumeration.py`

**Interfaces:**
- Consumes: nothing. Pure Python, no chemistry, no BioSTEAM. Tests run in milliseconds.
- Produces:
  - `Node(group: tuple[str, ...], k: int | None = None, light: Node | None = None, heavy: Node | None = None)` with properties `is_leaf -> bool`, `light_group -> tuple[str, ...]`, `heavy_group -> tuple[str, ...]`, `light_key -> str`, `heavy_key -> str`, and method `splits() -> list[Node]` returning every non-leaf node in pre-order.
  - `enumerate_sequences(group: tuple[str, ...]) -> Iterator[Node]`
  - `label(node: Node) -> str`

- [ ] **Step 1: Write the failing test**

```python
"""Sharp-split sequence enumeration. Pure combinatorics, no chemistry."""
import pytest

from sepsyn.sequencing.enumeration import enumerate_sequences, label
from sepsyn.sequencing.train import Node

# Catalan(n-1) is the number of sharp-split sequences for n components.
CATALAN = {1: 1, 2: 1, 3: 2, 4: 5, 5: 14, 6: 42, 7: 132}


@pytest.mark.parametrize("n", sorted(CATALAN))
def test_sequence_count_is_catalan(n):
    group = tuple("ABCDEFG"[:n])
    assert len(list(enumerate_sequences(group))) == CATALAN[n]


@pytest.mark.parametrize("n", [3, 4, 5, 6])
def test_every_sequence_has_exactly_n_minus_one_columns(n):
    group = tuple("ABCDEFG"[:n])
    for root in enumerate_sequences(group):
        assert len(root.splits()) == n - 1


def test_no_duplicate_sequences():
    group = tuple("ABCDE")
    labels = [label(r) for r in enumerate_sequences(group)]
    assert len(labels) == len(set(labels))


def test_a_split_names_the_adjacent_pair_as_its_keys():
    """The light key is the heaviest component going overhead and the heavy key
    is the lightest going to the bottoms. They are adjacent in volatility
    order, which is what makes the split sharp."""
    root = Node(group=("A", "B", "C"), k=2,
                light=Node(group=("A", "B"), k=1,
                           light=Node(group=("A",)), heavy=Node(group=("B",))),
                heavy=Node(group=("C",)))
    assert root.light_group == ("A", "B")
    assert root.heavy_group == ("C",)
    assert root.light_key == "B"
    assert root.heavy_key == "C"


def test_a_leaf_is_a_single_component_and_is_not_a_split():
    leaf = Node(group=("A",))
    assert leaf.is_leaf
    assert leaf.splits() == []


def test_every_group_in_a_tree_is_contiguous_in_volatility_order():
    """A sharp split cannot produce a group with a gap in it. If it did, the
    tree would describe a separation no single column can perform."""
    order = tuple("ABCDE")
    index = {c: i for i, c in enumerate(order)}
    for root in enumerate_sequences(order):
        for node in [root] + root.splits():
            positions = sorted(index[c] for c in node.group)
            assert positions == list(range(positions[0], positions[-1] + 1))


def test_a_single_component_yields_one_empty_sequence():
    roots = list(enumerate_sequences(("A",)))
    assert len(roots) == 1
    assert roots[0].splits() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/projects/process_simulation/sepsyn && ../.venv/bin/python -m pytest tests/test_sequence_enumeration.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'sepsyn.sequencing'`

- [ ] **Step 3: Write minimal implementation**

Create `sepsyn/sequencing/__init__.py` as an empty file.

Create `sepsyn/sequencing/train.py`:

```python
"""The shape of a separation train.

A sequence is a binary TREE, not a flat list of splits. The tree is what makes
product propagation natural: a column's light product is the feed to its light
subtree and its heavy product the feed to its heavy subtree. A flat list would
lose which stream feeds which column and force that structure to be rebuilt.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Node:
    """One column, or a leaf product.

    `group` is the components entering, in volatility order, lightest first.
    `k` is the split point: everything before it goes overhead. `k is None`
    means this is a finished product, not a column.
    """
    group: tuple[str, ...]
    k: int | None = None
    light: "Node | None" = None
    heavy: "Node | None" = None

    @property
    def is_leaf(self) -> bool:
        return self.k is None

    @property
    def light_group(self) -> tuple[str, ...]:
        return self.group[:self.k]

    @property
    def heavy_group(self) -> tuple[str, ...]:
        return self.group[self.k:]

    @property
    def light_key(self) -> str:
        """Heaviest component going overhead. Adjacent to the heavy key, which
        is what makes the split sharp."""
        return self.group[self.k - 1]

    @property
    def heavy_key(self) -> str:
        return self.group[self.k]

    def splits(self) -> list["Node"]:
        """Every column in the tree, in pre-order: this one, then the light
        branch, then the heavy branch. Pre-order matters because it is also a
        valid evaluation order once products propagate."""
        if self.is_leaf:
            return []
        return [self] + self.light.splits() + self.heavy.splits()
```

Create `sepsyn/sequencing/enumeration.py`:

```python
"""Every sharp-split sequence for an ordered component list.

The count is Catalan(n-1), which is 42 at six components and 429 at eight. The
probes recorded in the spec measured 0.01 s per column, so exhaustive
enumeration is affordable across the whole supported range and no pruning
heuristic is needed.
"""
from typing import Iterator

from sepsyn.sequencing.train import Node


def enumerate_sequences(group: tuple[str, ...]) -> Iterator[Node]:
    """Yield the root Node of every sharp-split sequence.

    A sharp split divides a CONTIGUOUS group into two contiguous subgroups, so
    the recursion only ever chooses where to cut, never which components to
    take. That constraint is what keeps the count at Catalan rather than
    exponential, and it is also what makes each split performable by one
    ordinary column.
    """
    if len(group) == 1:
        yield Node(group=group)
        return
    for k in range(1, len(group)):
        for light in enumerate_sequences(group[:k]):
            for heavy in enumerate_sequences(group[k:]):
                yield Node(group=group, k=k, light=light, heavy=heavy)


def label(node: Node) -> str:
    """A stable one-line name for a sequence, for reports and for de-duping."""
    return " | ".join(
        f"{'+'.join(s.light_group)}/{'+'.join(s.heavy_group)}"
        for s in node.splits()
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/projects/process_simulation/sepsyn && ../.venv/bin/python -m pytest tests/test_sequence_enumeration.py -q`
Expected: PASS, 15 passed

- [ ] **Step 5: Run the full suite**

Run: `../.venv/bin/python -m pytest -q`
Expected: PASS, 266 passed (251 existing + 15 new)

- [ ] **Step 6: Commit**

```bash
git add sepsyn/sequencing/ tests/test_sequence_enumeration.py
git commit -m "feat: sharp-split sequence enumeration

A sequence is a binary tree, not a flat list of splits. The tree is what makes
product propagation natural in the next task: a column's light product feeds
its light subtree. A flat list loses which stream feeds which column.

Count is pinned against Catalan(n-1) for n=1..7, and contiguity is asserted
directly: a sharp split cannot produce a group with a gap, because no single
column could perform that separation.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Hio3TrGFNZt6VaANMaRCqZ"
```

---

### Task 2: Multicomponent column via ShortcutColumn

**Files:**
- Modify: `sepsyn/simulators/base.py` (add one method to the `Simulator` Protocol)
- Modify: `sepsyn/simulators/biosteam_adapter.py` (add `design_multicomponent`)
- Test: `tests/test_multicomponent_column.py`

**Interfaces:**
- Consumes: `Feed`, `Component`, `ColumnSpec`, `ColumnResult` from `sepsyn.simulators.base` and `sepsyn.types`; the existing module-level helpers `_true_diameter_m` and `BIOSTEAM_FT_PER_M` in `biosteam_adapter.py`.
- Produces: `BioSteamSimulator.design_multicomponent(feed: Feed, spec: ColumnSpec) -> ColumnResult`

**Why a new method rather than extending `design_column`:** 251 existing tests depend on `design_column` using `BinaryDistillation`. `ShortcutColumn` is a different correlation with different convergence behaviour, and silently swapping it would change every existing number. The two live side by side and the caller chooses.

- [ ] **Step 1: Write the failing test**

```python
"""Multicomponent columns via BioSTEAM ShortcutColumn (Fenske-Underwood-Gilliland).

design_column stays on BinaryDistillation. This is a separate method because
swapping the correlation underneath the existing one would change every number
in the 251 tests that depend on it.
"""
import pytest

from sepsyn.properties import resolve
from sepsyn.simulators.base import ColumnSpec
from sepsyn.simulators.biosteam_adapter import BioSteamSimulator
from sepsyn.types import Component, Feed

ORDER = ["Propane", "Butane", "Pentane", "Hexane"]
FLOWS = [40.0, 30.0, 20.0, 10.0]


def alkane_feed(names=None, flows=None):
    names = names or ORDER
    flows = flows or FLOWS
    return Feed(
        components=tuple(Component(n, resolve(n), f) for n, f in zip(names, flows)),
        T_K=330.0, P_Pa=5.0e5,
    )


@pytest.fixture(scope="module")
def result():
    return BioSteamSimulator().design_multicomponent(
        alkane_feed(),
        ColumnSpec("Butane", "Pentane", 0.99, 0.99, 5.0e5),
    )


def test_a_four_component_column_converges(result):
    assert result.converged, result.error


def test_the_split_is_SHARP_at_the_named_keys(result):
    """Everything lighter than the light key goes overhead, everything heavier
    than the heavy key goes to the bottoms. That is what makes the sequence
    tree meaningful: a group either leaves together or it does not."""
    assert result.distillate["Propane"] == pytest.approx(40.0, rel=1e-3)
    assert result.bottoms["Hexane"] == pytest.approx(10.0, rel=1e-3)
    assert result.distillate["Hexane"] == pytest.approx(0.0, abs=1e-6)
    assert result.bottoms["Propane"] == pytest.approx(0.0, abs=1e-6)


def test_the_keys_meet_their_recoveries(result):
    assert result.distillate["Butane"] / 30.0 == pytest.approx(0.99, abs=5e-3)
    assert result.bottoms["Pentane"] / 20.0 == pytest.approx(0.99, abs=5e-3)


def test_it_returns_the_numbers_ranking_needs(result):
    """Cost and reflux are what Task 5 aggregates. A design that converged but
    reported no cost would rank as free."""
    assert result.stages > 0
    assert result.reflux > result.minimum_reflux > 0
    assert result.installed_cost_USD > 0
    assert result.utility_cost_USD_hr > 0


def test_every_feed_component_appears_in_both_products(result):
    """Reported, not just the keys. Nothing in a light/heavy-key spec
    constrains the others, so where they went is a result."""
    for name in ORDER:
        assert name in result.distillate
        assert name in result.bottoms


def test_a_failure_is_returned_as_data_not_raised():
    """Sweeping sequences will hit infeasible columns routinely, and an
    infeasible column is an answer about the design rather than a crash."""
    bad = BioSteamSimulator().design_multicomponent(
        alkane_feed(),
        ColumnSpec("Butane", "Pentane", 0.99, 0.99, 5.0e5,
                   condenser_type="thermosiphon"),
    )
    assert not bad.converged
    assert "thermosiphon" in (bad.error or "")


def test_it_works_on_a_binary_group_too():
    """Leaves of a sequence tree are single components, but a two-component
    group is a perfectly ordinary column and the evaluator must not special
    case it."""
    r = BioSteamSimulator().design_multicomponent(
        alkane_feed(["Propane", "Butane"], [40.0, 30.0]),
        ColumnSpec("Propane", "Butane", 0.99, 0.99, 5.0e5),
    )
    assert r.converged, r.error
    assert r.stages > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../.venv/bin/python -m pytest tests/test_multicomponent_column.py -q`
Expected: FAIL, `AttributeError: 'BioSteamSimulator' object has no attribute 'design_multicomponent'`

- [ ] **Step 3: Write minimal implementation**

In `sepsyn/simulators/base.py`, add to the `Simulator` Protocol, directly under the existing `design_column` line:

```python
    def design_multicomponent(self, feed: Feed, spec: ColumnSpec) -> ColumnResult: ...
```

In `sepsyn/simulators/biosteam_adapter.py`, add this method to `BioSteamSimulator`, after `design_column`:

```python
    def design_multicomponent(self, feed: Feed, spec: ColumnSpec) -> ColumnResult:
        """A column with more than two components, by Fenske, Underwood and
        Gilliland.

        Separate from design_column rather than replacing it. ShortcutColumn is
        a different correlation with different convergence behaviour, and
        swapping it underneath the existing method would change every number
        the 251 existing tests pin.

        Components lighter than the light key leave overhead and those heavier
        than the heavy key leave in the bottoms; BioSTEAM assumes that, which is
        exactly the sharp-split assumption the sequence tree is built on.
        """
        try:
            if spec.condenser_type not in ("total", "partial"):
                raise ValueError(
                    f"condenser_type must be 'total' or 'partial', got "
                    f"{spec.condenser_type!r}. Guessing here would hide the "
                    f"choice, which is the one thing step 22 forbids."
                )
            with contextlib.redirect_stdout(io.StringIO()):
                bst, s = self._setup(feed)
                feed_q = self._apply_and_measure_feed_q(s, feed, spec)
                col = bst.ShortcutColumn(
                    "C1", ins=s, outs=("D", "B"),
                    LHK=(spec.light_key, spec.heavy_key),
                    Lr=spec.lk_recovery_to_distillate,
                    Hr=spec.hk_recovery_to_bottoms,
                    k=spec.reflux_over_minimum,
                    P=spec.pressure_Pa,
                    partial_condenser=(spec.condenser_type == "partial"),
                )
                col.simulate()
                D, B = col.outs
                d = col.design_results
                qc = abs(float(col.condenser.Q)) / 3600.0
                qr = abs(float(col.reboiler.Q)) / 3600.0
                return ColumnResult(
                    distillate={n: float(D.imol[n]) for n in feed.names},
                    bottoms={n: float(B.imol[n]) for n in feed.names},
                    stages=float(d.get("Actual stages", 0.0)),
                    reflux=float(d.get("Reflux", 0.0)),
                    minimum_reflux=float(d.get("Minimum reflux", 0.0)),
                    installed_cost_USD=float(col.installed_cost),
                    utility_cost_USD_hr=float(col.utility_cost),
                    converged=True, error=None,
                    condenser_duty_kW=float(qc),
                    reboiler_duty_kW=float(qr),
                    distillate_T_K=float(D.T),
                    bottoms_T_K=float(B.T),
                    feed_H_kW=float(s.H) / 3600.0,
                    distillate_H_kW=float(D.H) / 3600.0,
                    bottoms_H_kW=float(B.H) / 3600.0,
                    biosteam_reported_diameter_m=(
                        float(d.get("Diameter", 0.0)) / BIOSTEAM_FT_PER_M or None),
                    column_diameter_m=_true_diameter_m(col, d),
                    feed_q=feed_q,
                )
        except Exception as exc:
            return dataclasses.replace(
                _EMPTY_COLUMN, error=f"{type(exc).__name__}: {exc}"
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `../.venv/bin/python -m pytest tests/test_multicomponent_column.py -q`
Expected: PASS, 7 passed

If `test_it_returns_the_numbers_ranking_needs` fails on `column_diameter_m`, that means `_true_diameter_m` reads private attributes `ShortcutColumn` does not expose. It is wrapped in `try/except` and falls back to the floored value, so the test above does not assert on diameter. Do not widen the test to cover it; note it and move on.

- [ ] **Step 5: Run the full suite**

Run: `../.venv/bin/python -m pytest -q`
Expected: PASS, 273 passed. If any previously passing test now fails, `design_column` was modified by mistake. Revert and add only the new method.

- [ ] **Step 6: Commit**

```bash
git add sepsyn/simulators/ tests/test_multicomponent_column.py
git commit -m "feat: multicomponent columns via ShortcutColumn

A new method rather than an extension of design_column. ShortcutColumn is a
different correlation with different convergence behaviour, and swapping it in
underneath would change every number the existing 251 tests pin.

The sharp split is asserted directly: components lighter than the light key
leave entirely overhead and heavier than the heavy key entirely in the bottoms.
That assumption is what the sequence tree is built on, so it is pinned rather
than trusted.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Hio3TrGFNZt6VaANMaRCqZ"
```

---

### Task 3: Evaluate one sequence, with products propagating

**Files:**
- Create: `sepsyn/sequencing/evaluate.py`
- Test: `tests/test_sequence_evaluation.py`

**Interfaces:**
- Consumes: `Node` and `label` from Task 1; `design_multicomponent` from Task 2; `resolve_column_pressure` from `sepsyn.cli`; `_annualised`, `PLANT_LIFE_YEARS`, `OPERATING_HOURS_YR` from `sepsyn.design`.
- Produces:
  - `ColumnOutcome(split: Node, pressure_Pa: float, pressure_basis: str, result: ColumnResult, annualised_cost_USD_yr: float | None, vapour_kmol_hr: float | None, screening: str = "", eliminated_by: str = "")`
  - `SequenceOutcome(root: Node, columns: tuple[ColumnOutcome, ...], total_cost_USD_yr: float | None, total_vapour_kmol_hr: float | None, eliminated_by: str)` with property `feasible -> bool` and `name -> str`
  - `evaluate_sequence(sim, feed: Feed, root: Node, *, lk_recovery: float = 0.99, hk_recovery: float = 0.99) -> SequenceOutcome`

- [ ] **Step 1: Write the failing test**

```python
"""Evaluating one sequence end to end.

The property that matters most here is PROPAGATION: the feed to a downstream
column is the actual product of the column above it, carrying its impurities,
not the idealised group flow. The spec's probes used idealised flows and said
so; this is where that simplification is removed.
"""
import pytest

from sepsyn.properties import resolve
from sepsyn.sequencing.enumeration import enumerate_sequences
from sepsyn.sequencing.evaluate import evaluate_sequence
from sepsyn.sequencing.train import Node
from sepsyn.simulators.biosteam_adapter import BioSteamSimulator
from sepsyn.types import Component, Feed

ORDER = ("Propane", "Butane", "Pentane", "Hexane")
FLOWS = (40.0, 30.0, 20.0, 10.0)


def alkane_feed():
    return Feed(
        components=tuple(Component(n, resolve(n), f) for n, f in zip(ORDER, FLOWS)),
        T_K=330.0, P_Pa=101325.0,
    )


def direct_sequence():
    """Remove the lightest component first, one at a time."""
    return Node(
        group=ORDER, k=1,
        light=Node(group=("Propane",)),
        heavy=Node(
            group=("Butane", "Pentane", "Hexane"), k=1,
            light=Node(group=("Butane",)),
            heavy=Node(group=("Pentane", "Hexane"), k=1,
                       light=Node(group=("Pentane",)),
                       heavy=Node(group=("Hexane",))),
        ),
    )


@pytest.fixture(scope="module")
def outcome():
    return evaluate_sequence(BioSteamSimulator(), alkane_feed(), direct_sequence())


def test_a_sequence_of_four_components_has_three_columns(outcome):
    assert len(outcome.columns) == 3


def test_it_reports_a_total_cost_and_a_total_vapour_load(outcome):
    assert outcome.feasible, outcome.eliminated_by
    assert outcome.total_cost_USD_yr > 0
    assert outcome.total_vapour_kmol_hr > 0


def test_the_total_is_the_sum_of_the_columns(outcome):
    """A total that is not the sum of its parts cannot be audited."""
    assert outcome.total_cost_USD_yr == pytest.approx(
        sum(c.annualised_cost_USD_yr for c in outcome.columns))
    assert outcome.total_vapour_kmol_hr == pytest.approx(
        sum(c.vapour_kmol_hr for c in outcome.columns))


def test_PRODUCTS_PROPAGATE_rather_than_ideal_flows_being_reused(outcome):
    """THE test for this task.

    The second column's feed is the first column's bottoms, so it carries the
    1% of propane the first column failed to recover overhead. If idealised
    group flows were reused, the second column would see exactly zero propane.
    """
    second = outcome.columns[1]
    first = outcome.columns[0]
    propane_into_second = first.result.bottoms["Propane"]
    assert propane_into_second > 0.0, "the first column is not perfect"
    total_second = sum(second.result.distillate.values()) + \
        sum(second.result.bottoms.values())
    assert total_second == pytest.approx(
        sum(first.result.bottoms.values()), rel=1e-6)


def test_each_column_settles_its_own_pressure(outcome):
    """A propane overhead needs a far higher pressure than a hexane one, so a
    single train-wide pressure would be wrong for most of the columns."""
    pressures = [c.pressure_Pa for c in outcome.columns]
    assert len(set(round(p) for p in pressures)) > 1
    for c in outcome.columns:
        assert c.pressure_basis


def test_vapour_load_is_distillate_times_reflux_plus_one(outcome):
    """Defined once in the spec; pinned here so it cannot drift."""
    c = outcome.columns[0]
    D = sum(c.result.distillate.values())
    assert c.vapour_kmol_hr == pytest.approx(D * (c.result.reflux + 1.0))


def test_a_column_that_fails_marks_the_SEQUENCE_not_just_the_column():
    """One unbuildable column makes the whole sequence unbuildable. Reporting
    a total cost for a train containing a column that did not converge would
    be reporting the cost of something that cannot be built."""
    class AlwaysFails:
        def design_multicomponent(self, feed, spec):
            from sepsyn.simulators.base import ColumnResult
            return ColumnResult({}, {}, 0.0, 0.0, 0.0, 0.0, 0.0, False,
                                error="ValueError: contrived failure")

    out = evaluate_sequence(AlwaysFails(), alkane_feed(), direct_sequence())
    assert not out.feasible
    assert "contrived failure" in out.eliminated_by
    assert out.total_cost_USD_yr is None


def test_every_enumerated_sequence_can_be_evaluated():
    """Five sequences for four components, all of them designable."""
    sim = BioSteamSimulator()
    feed = alkane_feed()
    outs = [evaluate_sequence(sim, feed, r) for r in enumerate_sequences(ORDER)]
    assert len(outs) == 5
    assert all(o.feasible for o in outs), [o.eliminated_by for o in outs if not o.feasible]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../.venv/bin/python -m pytest tests/test_sequence_evaluation.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'sepsyn.sequencing.evaluate'`

- [ ] **Step 3: Write minimal implementation**

Create `sepsyn/sequencing/evaluate.py`:

```python
"""Design every column in one sequence, and add up what it costs.

Products propagate. The feed to a downstream column is the actual product of
the column above it, impurities included, never the idealised group flow. That
matters because a sharp split is not perfect: at 99% recovery the first column
sends 1% of its light key into the bottoms, and the next column has to deal
with it. The idealised version hides that entirely.

Because products propagate, the columns of a sequence must be solved in
dependency order rather than independently. At the measured 0.01 s per column
that costs nothing.
"""
from dataclasses import dataclass

from sepsyn.design import _annualised
from sepsyn.sequencing.train import Node
from sepsyn.simulators.base import ColumnResult, ColumnSpec
from sepsyn.types import Component, Feed


@dataclass(frozen=True)
class ColumnOutcome:
    split: Node
    pressure_Pa: float
    pressure_basis: str
    result: ColumnResult
    annualised_cost_USD_yr: float | None
    vapour_kmol_hr: float | None
    screening: str = ""
    eliminated_by: str = ""


@dataclass(frozen=True)
class SequenceOutcome:
    root: Node
    columns: tuple[ColumnOutcome, ...]
    total_cost_USD_yr: float | None
    total_vapour_kmol_hr: float | None
    eliminated_by: str

    @property
    def feasible(self) -> bool:
        return not self.eliminated_by

    @property
    def name(self) -> str:
        from sepsyn.sequencing.enumeration import label
        return label(self.root)


def _feed_from(flows: dict[str, float], names: tuple[str, ...],
               T_K: float, P_Pa: float, cas: dict[str, str]) -> Feed:
    return Feed(
        components=tuple(Component(n, cas[n], flows[n]) for n in names),
        T_K=T_K, P_Pa=P_Pa,
    )


def evaluate_sequence(sim, feed: Feed, root: Node, *,
                      lk_recovery: float = 0.99,
                      hk_recovery: float = 0.99) -> SequenceOutcome:
    """Walk the tree, designing each column with the products of its parent."""
    from sepsyn.cli import resolve_column_pressure

    cas = {c.name: c.cas for c in feed.components}
    columns: list[ColumnOutcome] = []
    failure = ""

    def walk(node: Node, flows: dict[str, float]) -> None:
        nonlocal failure
        if node.is_leaf or failure:
            return
        group_feed = _feed_from(flows, node.group, feed.T_K, feed.P_Pa, cas)
        pressure, basis = resolve_column_pressure(group_feed, node.group[0], None)
        spec = ColumnSpec(node.light_key, node.heavy_key,
                          lk_recovery, hk_recovery, pressure)
        result = sim.design_multicomponent(group_feed, spec)
        if not result.converged:
            failure = (f"column {'+'.join(node.light_group)}/"
                       f"{'+'.join(node.heavy_group)} did not converge: "
                       f"{result.error}")
            columns.append(ColumnOutcome(node, pressure, basis, result,
                                         None, None, eliminated_by=failure))
            return
        D = sum(result.distillate.values())
        columns.append(ColumnOutcome(
            split=node, pressure_Pa=pressure, pressure_basis=basis,
            result=result,
            annualised_cost_USD_yr=_annualised(result.installed_cost_USD,
                                               result.utility_cost_USD_hr),
            # Vapour to the condenser, the spec's cost surrogate. Defined once
            # there and pinned by a test here so the two cannot drift.
            vapour_kmol_hr=D * (result.reflux + 1.0),
        ))
        walk(node.light, dict(result.distillate))
        walk(node.heavy, dict(result.bottoms))

    walk(root, {c.name: c.flow_kmol_hr for c in feed.components})

    if failure:
        return SequenceOutcome(root, tuple(columns), None, None, failure)
    return SequenceOutcome(
        root, tuple(columns),
        sum(c.annualised_cost_USD_yr for c in columns),
        sum(c.vapour_kmol_hr for c in columns),
        "",
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `../.venv/bin/python -m pytest tests/test_sequence_evaluation.py -q`
Expected: PASS, 8 passed

- [ ] **Step 5: Run the full suite**

Run: `../.venv/bin/python -m pytest -q`
Expected: PASS, 281 passed

- [ ] **Step 6: Commit**

```bash
git add sepsyn/sequencing/evaluate.py tests/test_sequence_evaluation.py
git commit -m "feat: evaluate one sequence, with products propagating

The feed to a downstream column is the actual product of the column above it,
impurities included, not the idealised group flow. At 99% recovery the first
column sends 1% of its light key into the bottoms and the next column has to
deal with it; the idealised version hides that. The spec's probes used
idealised flows and said so, and this is where that goes away.

Each column settles its own pressure. A propane overhead needs 13.7 bar and a
hexane one does not, so a single train-wide pressure would be wrong for most
columns in a train.

One column that fails to converge marks the whole SEQUENCE infeasible. Totalling
a train that contains an unbuildable column would report the cost of something
that cannot be built.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Hio3TrGFNZt6VaANMaRCqZ"
```

---

### Task 4: Screen every column, eliminate with a reason

**Files:**
- Modify: `sepsyn/sequencing/evaluate.py`
- Test: `tests/test_sequence_screening.py`

**Interfaces:**
- Consumes: `build_property_record` from `sepsyn.properties`; `load_rules`, `evaluate`, `overall_verdict` from `sepsyn.engine`; the `ColumnOutcome.screening` field defined in Task 3.
- Produces: no new names. `evaluate_sequence` gains screening behaviour: each `ColumnOutcome.screening` is filled with the column's overall verdict, and a sequence containing a column that screens `infeasible` gets `eliminated_by` naming the rule ids that fired.

**Why this matters:** a pair that is well behaved in the full feed can be azeotropic once another component is removed. Screening only the original feed would miss it, and the sequence would be costed as though it worked.

- [ ] **Step 1: Write the failing test**

```python
"""Screening applies to every column, not just the original feed.

A sub-mixture can behave differently from the feed it came from. Ethanol and
water are separable on paper until you notice the azeotrope; a sequence that
creates that pair partway down the train must be eliminated there, citing the
rule, rather than costed as though it worked.
"""
import pytest

from sepsyn.properties import resolve
from sepsyn.sequencing.evaluate import evaluate_sequence
from sepsyn.sequencing.train import Node
from sepsyn.simulators.biosteam_adapter import BioSteamSimulator
from sepsyn.types import Component, Feed


def feed_of(pairs, T_K=330.0):
    return Feed(
        components=tuple(Component(n, resolve(n), f) for n, f in pairs),
        T_K=T_K, P_Pa=101325.0,
    )


def test_every_column_records_its_screening_verdict():
    order = ("Propane", "Butane", "Pentane")
    root = Node(group=order, k=1,
                light=Node(group=("Propane",)),
                heavy=Node(group=("Butane", "Pentane"), k=1,
                           light=Node(group=("Butane",)),
                           heavy=Node(group=("Pentane",))))
    out = evaluate_sequence(BioSteamSimulator(),
                            feed_of([("Propane", 40.0), ("Butane", 30.0),
                                     ("Pentane", 20.0)]), root)
    assert len(out.columns) == 2
    for c in out.columns:
        assert c.screening in ("feasible", "caution", "undetermined",
                               "infeasible", "unknown")


def test_a_sub_mixture_azeotrope_eliminates_the_sequence_CITING_THE_RULE():
    """Acetone, ethanol and water. Splitting acetone off first leaves the
    ethanol/water pair in one column, which is azeotropic. The sequence must be
    eliminated at that column and must name R-03."""
    order = ("Acetone", "Ethanol", "Water")
    root = Node(group=order, k=1,
                light=Node(group=("Acetone",)),
                heavy=Node(group=("Ethanol", "Water"), k=1,
                           light=Node(group=("Ethanol",)),
                           heavy=Node(group=("Water",))))
    out = evaluate_sequence(BioSteamSimulator(),
                            feed_of([("Acetone", 30.0), ("Ethanol", 40.0),
                                     ("Water", 30.0)]), root)
    assert not out.feasible
    assert "R-03" in out.eliminated_by
    assert "Ethanol" in out.eliminated_by


def test_screening_stops_the_train_before_the_expensive_design_runs():
    """A column that screens infeasible is not designed. Designing it anyway
    would waste the solve and, worse, produce a cost for a column that should
    never be built."""
    order = ("Acetone", "Ethanol", "Water")
    root = Node(group=order, k=1,
                light=Node(group=("Acetone",)),
                heavy=Node(group=("Ethanol", "Water"), k=1,
                           light=Node(group=("Ethanol",)),
                           heavy=Node(group=("Water",))))
    out = evaluate_sequence(BioSteamSimulator(),
                            feed_of([("Acetone", 30.0), ("Ethanol", 40.0),
                                     ("Water", 30.0)]), root)
    eliminated = [c for c in out.columns if c.eliminated_by]
    assert len(eliminated) == 1
    assert eliminated[0].result is None or not eliminated[0].result.converged


def test_a_clean_alkane_train_is_not_eliminated():
    order = ("Propane", "Butane", "Pentane")
    root = Node(group=order, k=2,
                light=Node(group=("Propane", "Butane"), k=1,
                           light=Node(group=("Propane",)),
                           heavy=Node(group=("Butane",))),
                heavy=Node(group=("Pentane",)))
    out = evaluate_sequence(BioSteamSimulator(),
                            feed_of([("Propane", 40.0), ("Butane", 30.0),
                                     ("Pentane", 20.0)]), root)
    assert out.feasible, out.eliminated_by
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../.venv/bin/python -m pytest tests/test_sequence_screening.py -q`
Expected: FAIL. `test_every_column_records_its_screening_verdict` fails because `screening` is the empty string, and the azeotrope tests fail because the sequence is not eliminated.

- [ ] **Step 3: Write minimal implementation**

In `sepsyn/sequencing/evaluate.py`, replace the body of `walk` between the `group_feed`/`pressure` lines and the `spec = ColumnSpec(...)` line with the following, and add the two imports at the top of the function:

```python
    from sepsyn.cli import resolve_column_pressure
    from sepsyn.engine import evaluate as evaluate_rules, load_rules, overall_verdict
    from sepsyn.properties import build_property_record

    rules = load_rules()
```

Then inside `walk`, after `pressure, basis = resolve_column_pressure(...)`:

```python
        # Screen THIS column, not just the original feed. A pair that is well
        # behaved in the full mixture can be azeotropic once a component is
        # removed, and a sequence that creates such a pair partway down the
        # train has to be eliminated there rather than costed as if it worked.
        record = build_property_record(
            group_feed, column_P_Pa=pressure,
            light_key=node.light_key, heavy_key=node.heavy_key,
            column_P_basis=basis)
        verdicts = evaluate_rules(rules, record)
        verdict = overall_verdict(verdicts)
        if verdict == "infeasible":
            fired = ", ".join(v.rule_id for v in verdicts
                              if v.fired and v.verdict == "infeasible")
            failure = (f"column {node.light_key}/{node.heavy_key} screens "
                       f"INFEASIBLE ({fired})")
            columns.append(ColumnOutcome(node, pressure, basis, None,
                                         None, None, screening=verdict,
                                         eliminated_by=failure))
            return
```

Change the `ColumnOutcome.result` annotation in the dataclass from `ColumnResult` to `ColumnResult | None`, since an eliminated column is never designed.

Pass `screening=verdict` into the successful `ColumnOutcome(...)` construction as well.

- [ ] **Step 4: Run test to verify it passes**

Run: `../.venv/bin/python -m pytest tests/test_sequence_screening.py -q`
Expected: PASS, 4 passed

If the acetone/ethanol/water case does not report `R-03`, check that the ethanol/water column is actually reached: the tree above splits acetone off first, so the second column is the ethanol/water pair. Print `out.columns[1].screening` to confirm before changing any threshold. Do not adjust `rules.yaml` to make the test pass.

- [ ] **Step 5: Run the full suite**

Run: `../.venv/bin/python -m pytest -q`
Expected: PASS, 285 passed

- [ ] **Step 6: Commit**

```bash
git add sepsyn/sequencing/evaluate.py tests/test_sequence_screening.py
git commit -m "feat: screen every column in a train, eliminate with the rule id

A pair that is well behaved in the full feed can be azeotropic once another
component is removed. Screening only the original feed misses that, and the
sequence gets costed as though it worked.

Acetone/ethanol/water is the case: split acetone off first and the remaining
column is ethanol/water, which R-03 rules out. The sequence is eliminated at
that column and says so.

An eliminated column is never designed, so ColumnResult is now optional on
ColumnOutcome. Designing a column that screened infeasible would waste the
solve and produce a cost for something that should not be built.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Hio3TrGFNZt6VaANMaRCqZ"
```

---

### Task 5: Rank the sequences, and report a set rather than a leaderboard

**Files:**
- Create: `sepsyn/sequencing/rank.py`
- Test: `tests/test_sequence_ranking.py`

**Interfaces:**
- Consumes: `SequenceOutcome` from Task 3; `enumerate_sequences` from Task 1; `evaluate_sequence` from Task 3.
- Produces:
  - `NEAR_OPTIMAL_TOLERANCE = 0.05`
  - `Ranking(winner: SequenceOutcome | None, near_optimal: tuple[SequenceOutcome, ...], eliminated: tuple[SequenceOutcome, ...], metrics_agree_on_winner: bool, orderings_identical: bool, worst_displacement: int, evaluated: int)`
  - `rank(outcomes: list[SequenceOutcome], tolerance: float = NEAR_OPTIMAL_TOLERANCE) -> Ranking`
  - `sweep(sim, feed, order: tuple[str, ...], **kw) -> Ranking`

- [ ] **Step 1: Write the failing test**

```python
"""Ranking sequences, and being honest about how far the ranking can be trusted.

The spec measured cost and vapour load agreeing on the WINNER at 4, 5 and 6
components but diverging by up to 14 of 42 places further down. So the winner is
reported as a winner and everything past it as an unordered near-optimal set.
An ordered leaderboard would assert precision the evidence does not support.
"""
import pytest

from sepsyn.properties import resolve
from sepsyn.sequencing.evaluate import SequenceOutcome
from sepsyn.sequencing.rank import Ranking, rank, sweep
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


def fake(name, cost, vapour, eliminated=""):
    root = Node(group=(name,))
    return SequenceOutcome(root, (), None if eliminated else cost,
                           None if eliminated else vapour, eliminated)


def test_the_cheapest_feasible_sequence_wins():
    r = rank([fake("a", 300.0, 10.0), fake("b", 200.0, 8.0),
              fake("c", 400.0, 12.0)])
    assert r.winner.total_cost_USD_yr == 200.0


def test_eliminated_sequences_are_kept_and_reported_separately():
    """Kept, not dropped. 'Could not be built' and 'was not tried' are
    different facts and a reader is entitled to tell them apart."""
    r = rank([fake("a", 300.0, 10.0), fake("bad", 0.0, 0.0, "R-03 azeotrope")])
    assert len(r.eliminated) == 1
    assert "R-03" in r.eliminated[0].eliminated_by
    assert r.winner.total_cost_USD_yr == 300.0


def test_the_near_optimal_set_holds_everything_within_tolerance():
    r = rank([fake("a", 100.0, 10.0), fake("b", 104.0, 11.0),
              fake("c", 130.0, 12.0)], tolerance=0.05)
    names = {o.total_cost_USD_yr for o in r.near_optimal}
    assert names == {100.0, 104.0}


def test_it_reports_whether_the_two_METRICS_AGREE_on_the_winner():
    agree = rank([fake("a", 100.0, 10.0), fake("b", 200.0, 20.0)])
    assert agree.metrics_agree_on_winner is True

    disagree = rank([fake("a", 100.0, 30.0), fake("b", 200.0, 10.0)])
    assert disagree.metrics_agree_on_winner is False


def test_it_reports_HOW_FAR_the_two_orderings_diverge():
    """The number the spec measured at 14 of 42. Reported so a reader knows
    how much of the ordering to trust."""
    r = rank([fake("a", 100.0, 30.0), fake("b", 200.0, 20.0),
              fake("c", 300.0, 10.0)])
    assert r.orderings_identical is False
    assert r.worst_displacement == 2


def test_identical_orderings_report_zero_displacement():
    r = rank([fake("a", 100.0, 10.0), fake("b", 200.0, 20.0),
              fake("c", 300.0, 30.0)])
    assert r.orderings_identical is True
    assert r.worst_displacement == 0


def test_all_sequences_eliminated_gives_no_winner_rather_than_a_crash():
    r = rank([fake("a", 0.0, 0.0, "R-03"), fake("b", 0.0, 0.0, "R-02")])
    assert r.winner is None
    assert r.near_optimal == ()
    assert len(r.eliminated) == 2


def test_sweep_evaluates_every_sequence_for_a_real_feed():
    """Four components: five sequences, fifteen columns. The spec measured
    this at 0.2 s."""
    r = sweep(BioSteamSimulator(), alkane_feed(), ORDER)
    assert r.evaluated == 5
    assert r.winner is not None
    assert r.winner.total_cost_USD_yr > 0


def test_the_direct_sequence_wins_on_this_feed():
    """Known answer. Propane is both lightest and most plentiful, so removing
    it first is favoured by every classic heuristic, and it wins on cost.

    NOTE: precisely because every heuristic agrees here, this case cannot
    discriminate between them. That is why Phase B needs an adversarial test
    set. See spec section 5.
    """
    r = sweep(BioSteamSimulator(), alkane_feed(), ORDER)
    assert r.winner.name.startswith("Propane/Butane+Pentane+Hexane")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../.venv/bin/python -m pytest tests/test_sequence_ranking.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'sepsyn.sequencing.rank'`

- [ ] **Step 3: Write minimal implementation**

Create `sepsyn/sequencing/rank.py`:

```python
"""Rank the sequences, and say how far the ranking can be trusted.

The measurement behind this module, recorded in the spec: annualised cost and
total vapour load select the SAME winner at 4, 5 and 6 components, but their
full orderings diverge by up to 14 of 42 places at six components.

So the winner is reported as a winner, and everything past it as an UNORDERED
near-optimal set. An ordered leaderboard past position one would assert a
precision the evidence does not support, and anything downstream consuming a
shortlist would be consuming an artefact of which metric happened to be chosen.
"""
from dataclasses import dataclass

from sepsyn.sequencing.enumeration import enumerate_sequences
from sepsyn.sequencing.evaluate import SequenceOutcome, evaluate_sequence

# Within this fraction of the winner's cost counts as indistinguishable. The
# shortcut methods underneath carry more error than this between them, which is
# what M2 exists to quantify; until it does, a 5% gap is not a real difference.
NEAR_OPTIMAL_TOLERANCE = 0.05


@dataclass(frozen=True)
class Ranking:
    winner: SequenceOutcome | None
    near_optimal: tuple[SequenceOutcome, ...]
    eliminated: tuple[SequenceOutcome, ...]
    metrics_agree_on_winner: bool
    orderings_identical: bool
    worst_displacement: int
    evaluated: int


def rank(outcomes: list[SequenceOutcome],
         tolerance: float = NEAR_OPTIMAL_TOLERANCE) -> Ranking:
    feasible = [o for o in outcomes if o.feasible]
    eliminated = tuple(o for o in outcomes if not o.feasible)
    if not feasible:
        return Ranking(None, (), eliminated, True, True, 0, len(outcomes))

    by_cost = sorted(feasible, key=lambda o: o.total_cost_USD_yr)
    by_vapour = sorted(feasible, key=lambda o: o.total_vapour_kmol_hr)
    winner = by_cost[0]

    position = {id(o): i for i, o in enumerate(by_vapour)}
    displacement = max(abs(i - position[id(o)]) for i, o in enumerate(by_cost))

    cutoff = winner.total_cost_USD_yr * (1.0 + tolerance)
    near = tuple(o for o in feasible if o.total_cost_USD_yr <= cutoff)

    return Ranking(
        winner=winner,
        near_optimal=near,
        eliminated=eliminated,
        metrics_agree_on_winner=(by_cost[0] is by_vapour[0]),
        orderings_identical=(displacement == 0),
        worst_displacement=displacement,
        evaluated=len(outcomes),
    )


def sweep(sim, feed, order: tuple[str, ...], **kw) -> Ranking:
    """Evaluate every sharp-split sequence for this feed and rank them.

    Exhaustive by design. The spec measured 0.01 s per column, so 42 sequences
    of six components take about two seconds and there is nothing to gain from
    pruning at the sizes this tool supports.
    """
    outcomes = [evaluate_sequence(sim, feed, root, **kw)
                for root in enumerate_sequences(order)]
    return rank(outcomes)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `../.venv/bin/python -m pytest tests/test_sequence_ranking.py -q`
Expected: PASS, 9 passed

- [ ] **Step 5: Run the full suite**

Run: `../.venv/bin/python -m pytest -q`
Expected: PASS, 294 passed

- [ ] **Step 6: Commit**

```bash
git add sepsyn/sequencing/rank.py tests/test_sequence_ranking.py
git commit -m "feat: rank sequences, report a set rather than a leaderboard

Cost and vapour load pick the same winner at 4, 5 and 6 components but their
full orderings diverge by up to 14 of 42 places. So the winner is reported as a
winner and everything past it as an unordered near-optimal set. An ordered list
past position one would assert precision the evidence does not support.

The Ranking carries both facts explicitly: whether the two metrics agreed on
the winner, and how far apart their orderings ran. A reader can then see how
much of the answer to trust rather than being handed a clean list.

Eliminated sequences are kept and reported separately. Could not be built and
was not tried are different facts.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Hio3TrGFNZt6VaANMaRCqZ"
```

---

### Task 6: CLI and report

**Files:**
- Create: `sepsyn/sequencing/report.py`
- Modify: `sepsyn/cli.py`
- Test: `tests/test_sequence_cli.py`

**Interfaces:**
- Consumes: `Ranking`, `sweep` from Task 5; `parse_feed` and `main` from `sepsyn.cli`.
- Produces:
  - `format_sequencing(ranking: Ranking) -> str`
  - CLI flag `--sequence`, which requires `--order`

- [ ] **Step 1: Write the failing test**

```python
"""The sequencing report, end to end from the command line."""
import pytest

from sepsyn.cli import main

ALKANES = ["--feed", "Propane:40,Butane:30,Pentane:20,Hexane:10",
           "--T", "330", "--sequence",
           "--order", "Propane,Butane,Pentane,Hexane"]


def test_it_runs_and_returns_zero(capsys):
    assert main(ALKANES) == 0
    assert "SEQUENCES" in capsys.readouterr().out


def test_it_reports_how_many_sequences_it_evaluated(capsys):
    main(ALKANES)
    assert "5 sequences" in capsys.readouterr().out


def test_it_names_the_winner_with_its_cost(capsys):
    main(ALKANES)
    out = capsys.readouterr().out
    assert "BEST SEQUENCE" in out
    assert "$" in out
    assert "Propane/Butane+Pentane+Hexane" in out


def test_it_shows_the_near_optimal_set_as_a_SET_not_a_ranked_list(capsys):
    """The wording matters. Numbering these 1, 2, 3 would reintroduce exactly
    the false precision the ranking module exists to avoid."""
    main(ALKANES)
    out = capsys.readouterr().out
    assert "WITHIN 5%" in out.upper()
    assert "not ranked" in out.lower()


def test_it_states_whether_the_two_metrics_agreed(capsys):
    main(ALKANES)
    out = capsys.readouterr().out
    assert "vapour" in out.lower()
    assert "agree" in out.lower()


def test_sequence_requires_order(capsys):
    code = main(["--feed", "Propane:40,Butane:30", "--T", "330", "--sequence"])
    assert code == 2
    assert "--order" in capsys.readouterr().out


def test_an_order_naming_an_absent_component_is_refused(capsys):
    code = main(["--feed", "Propane:40,Butane:30", "--T", "330", "--sequence",
                 "--order", "Propane,Heptane"])
    assert code == 2
    assert "Heptane" in capsys.readouterr().out


def test_eliminated_sequences_are_listed_with_their_reason(capsys):
    """Acetone/ethanol/water: some sequences create the azeotropic pair and
    must be shown as eliminated, citing the rule."""
    main(["--feed", "Acetone:30,Ethanol:40,Water:30", "--T", "330",
          "--sequence", "--order", "Acetone,Ethanol,Water"])
    out = capsys.readouterr().out
    assert "ELIMINATED" in out
    assert "R-03" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../.venv/bin/python -m pytest tests/test_sequence_cli.py -q`
Expected: FAIL, `SystemExit: 2` from argparse, `unrecognized arguments: --sequence`

- [ ] **Step 3: Write minimal implementation**

Create `sepsyn/sequencing/report.py`:

```python
"""The sequencing report.

The near-optimal set is printed as a SET and labelled as one. Numbering the
entries would reintroduce the false precision that rank.py exists to avoid: the
measured divergence between the two ranking metrics is up to 14 of 42 places,
so a numbered list past the winner would be an artefact of the metric.
"""
import textwrap

from sepsyn.sequencing.rank import NEAR_OPTIMAL_TOLERANCE, Ranking


def _wrap(prefix: str, text: str) -> list[str]:
    body = textwrap.wrap(" ".join(text.split()), width=78 - len(prefix)) or [""]
    pad = " " * len(prefix)
    return [prefix + body[0]] + [pad + line for line in body[1:]]


def format_sequencing(ranking: Ranking) -> str:
    lines: list[str] = []
    feasible = ranking.evaluated - len(ranking.eliminated)
    lines.append("SEQUENCES")
    lines.append(f"  {ranking.evaluated} sequences enumerated, "
                 f"{feasible} designable, {len(ranking.eliminated)} eliminated")
    lines.append("")

    if ranking.winner is None:
        lines.append("  No sequence could be designed. Reasons below.")
    else:
        w = ranking.winner
        lines.append("BEST SEQUENCE")
        lines.append(f"  {w.name}")
        lines.append(f"  ${w.total_cost_USD_yr:,.0f} per year"
                     f"   |   {w.total_vapour_kmol_hr:,.1f} kmol/hr vapour"
                     f"   |   {len(w.columns)} columns")
        lines.append("")

        others = [o for o in ranking.near_optimal if o is not w]
        pct = int(NEAR_OPTIMAL_TOLERANCE * 100)
        lines.append(f"WITHIN {pct}% OF THE BEST  (a set, not ranked)")
        if not others:
            lines.append("  Nothing else comes close.")
        else:
            lines.extend(_wrap(
                "  ",
                f"These {len(others)} are not meaningfully worse. The shortcut "
                f"methods underneath carry more error than {pct}% between them, "
                f"so ordering these would be reporting noise."))
            for o in others:
                lines.append(f"    {o.name}")
                lines.append(f"      ${o.total_cost_USD_yr:,.0f}/yr")
        lines.append("")

        lines.append("HOW FAR TO TRUST THE ORDER")
        if ranking.metrics_agree_on_winner:
            lines.extend(_wrap(
                "  ",
                "Annualised cost and total vapour load select the same winning "
                "sequence, so the winner does not depend on which was used."))
        else:
            lines.extend(_wrap(
                "  ",
                "WARNING: cost and vapour load select DIFFERENT winners. The "
                "answer depends on which metric you trust, and neither has been "
                "validated against a rigorous solution."))
        if not ranking.orderings_identical:
            lines.extend(_wrap(
                "  ",
                f"Past the winner the two orderings diverge by up to "
                f"{ranking.worst_displacement} of {feasible} places, which is "
                f"why the set above is unordered."))

    if ranking.eliminated:
        lines.append("")
        lines.append("ELIMINATED")
        for o in ranking.eliminated:
            lines.append(f"  {o.name}")
            lines.extend(_wrap("      ", o.eliminated_by))
    return "\n".join(lines)
```

In `sepsyn/cli.py`, add the two flags next to `--design`:

```python
    p.add_argument("--sequence", action="store_true",
                   help="enumerate every sharp-split sequence for a "
                        "multicomponent feed, design each one, and report the "
                        "cheapest. Requires --order")
    p.add_argument("--order",
                   help="component names lightest to heaviest, comma "
                        "separated, e.g. 'Propane,Butane,Pentane'. Volatility "
                        "order is what makes a split sharp, so it is required "
                        "rather than guessed from boiling points")
```

In `main`, after the screening report is emitted and before the `if args.design:` block:

```python
    if args.sequence:
        if not args.order:
            emit("\n--sequence requires --order, the component names from "
                 "lightest to heaviest")
            save()
            return 2
        order = tuple(n.strip() for n in args.order.split(","))
        missing = [n for n in order if n not in feed.names]
        if missing:
            emit(f"\n--order names components that are not in the feed: "
                 f"{', '.join(missing)}")
            save()
            return 2
        from sepsyn.sequencing.rank import sweep
        from sepsyn.sequencing.report import format_sequencing
        from sepsyn.simulators.biosteam_adapter import BioSteamSimulator
        emit()
        emit(format_sequencing(sweep(BioSteamSimulator(), feed, order)))
        save()
        return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `../.venv/bin/python -m pytest tests/test_sequence_cli.py -q`
Expected: PASS, 8 passed

- [ ] **Step 5: Run the full suite and look at real output**

Run: `../.venv/bin/python -m pytest -q`
Expected: PASS, 302 passed

Then run it and read the output rather than trusting the tests:

```bash
../.venv/bin/python -m sepsyn.cli --feed "Propane:40,Butane:30,Pentane:20,Hexane:10" \
  --T 330 --sequence --order "Propane,Butane,Pentane,Hexane"
```

Check by eye: five sequences, a named winner with a cost, the near-optimal set labelled as unordered, and a statement about metric agreement.

- [ ] **Step 6: Commit**

```bash
git add sepsyn/sequencing/report.py sepsyn/cli.py tests/test_sequence_cli.py
git commit -m "feat: --sequence, enumerate and rank separation trains

--order is required rather than inferred from boiling points. Volatility order
is what makes a split sharp, and guessing it from pure-component boiling points
would be wrong for any mixture where the ordering shifts with composition.

The near-optimal set is printed as a set and labelled as one. Numbering the
entries would reintroduce the false precision rank.py exists to avoid.

The report states whether cost and vapour load agreed on the winner, and by how
far their orderings diverged, so a reader can see how much of the answer to
trust instead of being handed a clean list.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Hio3TrGFNZt6VaANMaRCqZ"
```

---

## Self-review

**Spec coverage.** §7 architecture: Tasks 1–5 create `enumeration.py`, `train.py`, `evaluate.py`, `rank.py`; `heuristics.py` and `score.py` are Phase B and deliberately absent. §8 data flow: enumeration (T1), screening (T4), pressure (T3), design (T2), propagation (T3), elimination (T4), aggregation (T3), near-optimal set (T5), report (T6). §8 component tags: Phase B. §9 testing: enumeration count (T1), known answer (T5), sub-mixture azeotrope (T4), ranking robustness (T5), propagation (T3); the adversarial set and missing-tag tests are Phase B, as §11 requires. §10 assumptions: the ranked-list assumption the probes contradicted is handled by the unordered set in T5 and T6.

**Placeholder scan.** No TBD, TODO, "similar to Task N", or "add error handling". Every code step carries the code. Task 2 step 4 and Task 4 step 4 give explicit instructions for the two failure modes most likely to tempt an implementer into changing a threshold, and both say not to.

**Type consistency.** `Node` is constructed identically in Tasks 1, 3, 4 and 5. `ColumnOutcome.result` is widened to `ColumnResult | None` in Task 4, and Task 3's tests do not assert it is non-None on eliminated columns. `SequenceOutcome.name` is defined in Task 3 and used in Tasks 5 and 6. `evaluate_sequence`'s keyword arguments match `sweep`'s pass-through. `NEAR_OPTIMAL_TOLERANCE` is defined in Task 5 and imported by name in Task 6.

**One inherited weakness, stated rather than hidden.** `evaluate_sequence` calls `resolve_column_pressure` from `sepsyn.cli`, which means a library module imports from the command-line module. That is backwards, and it is the existing arrangement rather than something this plan introduces. Moving the resolver into `sepsyn/design.py` would be correct and is out of scope here; if a task ends up touching it anyway, move it and update the three call sites.
