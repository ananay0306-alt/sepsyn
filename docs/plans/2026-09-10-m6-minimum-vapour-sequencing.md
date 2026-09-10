# M6: Minimum-Vapour Sequencing — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Choose the separation sequence for a 3 to 12 component feed by minimising total vapour flow, found exactly by dynamic programming, then verify the chosen sequence with the existing screening machinery.

**Architecture:** Underwood's equations, implemented directly, give the minimum vapour requirement for any sharp split of any contiguous group. Dynamic programming over those groups returns the provable optimum in O(n³). The chosen sequence — and only that one — is then handed to M3's evaluator for real product propagation, per-column screening and `undetermined` blocking.

**Tech Stack:** Python 3.11+, numpy, scipy (Brent root finding), thermosteam for relative volatilities. BioSTEAM is used only for relative volatility data, never for `ShortcutColumn`.

**Spec:** `docs/specs/2026-09-10-minimum-vapour-sequencing.md`

## Global Constraints

- **V_min is a BOUND, never a design.** No stage counts, no tray efficiency, no condenser type, no cost correlation enters selection. Every defect of 09-09 and 09-10 lives downstream of Underwood; this stops there.
- **Underwood is implemented from the equations, not taken from `ShortcutColumn`.** A bound the milestone rests on must be code we can read.
- **Nothing is filed against BioSTEAM until Task 5 runs.** The falling-Rmin measurement may be their defect or our misuse and that is not yet established.
- **Selection and verification stay separate.** DP selects under sharp splits; M3's evaluator verifies with real propagation. Conflating a bound problem with a design problem is what produced a ranking built on unbuildable columns.
- Relative volatilities always carry the temperature and pressure they were computed at. A bare alpha is meaningless (`sepsyn/types.py:Alpha`).
- Underwood requires near-constant relative volatility. R-03 (azeotrope) and R-12 (two liquid phases) gate entry; a mixture that trips either must not be sequenced by this method.
- Run the full suite before every commit. 395 tests pass at the time of writing.

---

### Task 1: Underwood roots

**Files:**
- Create: `sepsyn/vmin/__init__.py`
- Create: `sepsyn/vmin/underwood.py`
- Test: `tests/test_underwood_roots.py`

**Interfaces:**
- Consumes: nothing but numpy and scipy. Pure mathematics, no chemistry lookups, so the tests run in milliseconds against hand-checkable numbers.
- Produces:
  - `underwood_theta(alpha: dict[str, float], z: dict[str, float], q: float, light_key: str, heavy_key: str) -> float`
  - `NoUnderwoodRoot(ValueError)`

**The equation.** With volatilities relative to the heavy key, solve for the θ lying strictly between α(heavy key) and α(light key):

    sum_i [ alpha_i * z_i / (alpha_i - theta) ] = 1 - q

- [ ] **Step 1: Write the failing test**

```python
"""Underwood's constant, solved from the equation rather than borrowed.

sum_i [ alpha_i z_i / (alpha_i - theta) ] = 1 - q

theta lies strictly between the volatilities of the two keys. Volatilities here
are relative to the heavy key, so alpha_HK = 1 by construction and the root is
bracketed by (1, alpha_LK).
"""
import pytest

from sepsyn.vmin.underwood import NoUnderwoodRoot, underwood_theta


def residual(alpha, z, q, theta):
    return sum(alpha[i] * z[i] / (alpha[i] - theta) for i in z) - (1.0 - q)


def test_the_root_satisfies_the_equation():
    alpha = {"A": 4.0, "B": 2.0, "C": 1.0}
    z = {"A": 0.3, "B": 0.3, "C": 0.4}
    theta = underwood_theta(alpha, z, q=1.0, light_key="B", heavy_key="C")
    assert residual(alpha, z, 1.0, theta) == pytest.approx(0.0, abs=1e-9)


def test_the_root_is_bracketed_by_the_KEY_volatilities():
    """The defining property. A root outside the keys' volatilities is a
    different root and gives a different, wrong, minimum vapour."""
    alpha = {"A": 4.0, "B": 2.0, "C": 1.0}
    z = {"A": 0.3, "B": 0.3, "C": 0.4}
    theta = underwood_theta(alpha, z, q=1.0, light_key="B", heavy_key="C")
    assert 1.0 < theta < 2.0


def test_a_different_key_pair_gives_a_different_root():
    """Splitting A from B is a different separation from splitting B from C,
    and must select a root in a different interval."""
    alpha = {"A": 4.0, "B": 2.0, "C": 1.0}
    z = {"A": 0.3, "B": 0.3, "C": 0.4}
    ab = underwood_theta(alpha, z, q=1.0, light_key="A", heavy_key="B")
    bc = underwood_theta(alpha, z, q=1.0, light_key="B", heavy_key="C")
    assert 2.0 < ab < 4.0
    assert 1.0 < bc < 2.0
    assert ab != bc


def test_a_binary_feed_has_an_analytic_root():
    """With two components at q=1 the equation reduces to a quadratic and the
    root can be checked by hand."""
    alpha = {"A": 3.0, "B": 1.0}
    z = {"A": 0.5, "B": 0.5}
    theta = underwood_theta(alpha, z, q=1.0, light_key="A", heavy_key="B")
    assert residual(alpha, z, 1.0, theta) == pytest.approx(0.0, abs=1e-9)
    assert 1.0 < theta < 3.0


@pytest.mark.parametrize("q", [0.0, 0.5, 1.0, 1.3])
def test_feed_condition_moves_the_root(q):
    """q enters the equation directly. A saturated vapour feed and a subcooled
    liquid feed give different roots and therefore different minimum vapour,
    which is why q travels with every design in this project."""
    alpha = {"A": 4.0, "B": 2.0, "C": 1.0}
    z = {"A": 0.3, "B": 0.3, "C": 0.4}
    theta = underwood_theta(alpha, z, q=q, light_key="B", heavy_key="C")
    assert residual(alpha, z, q, theta) == pytest.approx(0.0, abs=1e-9)


def test_components_absent_from_the_group_are_refused():
    alpha = {"A": 4.0, "B": 2.0}
    z = {"A": 0.5, "B": 0.5}
    with pytest.raises(NoUnderwoodRoot, match="C"):
        underwood_theta(alpha, z, q=1.0, light_key="B", heavy_key="C")


def test_keys_with_equal_volatility_are_refused_rather_than_returning_a_root():
    """No interval, no root. Alpha of 1.0 between the keys means they cannot be
    separated by distillation at all, and R-02 should already have said so."""
    alpha = {"A": 2.0, "B": 1.0, "C": 1.0}
    z = {"A": 0.4, "B": 0.3, "C": 0.3}
    with pytest.raises(NoUnderwoodRoot, match="volatilit"):
        underwood_theta(alpha, z, q=1.0, light_key="B", heavy_key="C")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/projects/process_simulation/sepsyn && ../.venv/bin/python -m pytest tests/test_underwood_roots.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'sepsyn.vmin'`

- [ ] **Step 3: Write minimal implementation**

Create `sepsyn/vmin/__init__.py` as an empty file, then `sepsyn/vmin/underwood.py`:

```python
"""Underwood's constant, from the equation.

    sum_i [ alpha_i z_i / (alpha_i - theta) ] = 1 - q

Implemented here rather than taken from BioSTEAM's ShortcutColumn on purpose.
A measurement on 2026-09-09 found that chain's minimum reflux falling as heavy
non-key content rose, and it could not be established whether that was a defect
in the package or a misuse of it. A bound this milestone rests on has to be
code that can be read, and running our own on the same feeds is the cheapest
way to settle the question (Task 5).

The root matters as much as the equation. theta must lie strictly between the
volatilities of the two KEYS; a root from a different interval solves the same
equation and gives a different, wrong, minimum vapour.
"""
from scipy.optimize import brentq

# The pole at alpha_i = theta makes the residual infinite at each end of the
# interval. Step inside by this fraction of the interval to bracket safely.
_EDGE = 1e-9


class NoUnderwoodRoot(ValueError):
    """No root exists in the interval between the two keys' volatilities."""


def _residual(theta: float, alpha: dict, z: dict, q: float) -> float:
    return sum(alpha[i] * z[i] / (alpha[i] - theta) for i in z) - (1.0 - q)


def underwood_theta(alpha: dict[str, float], z: dict[str, float], q: float,
                    light_key: str, heavy_key: str) -> float:
    """The Underwood constant for a sharp split between these two keys."""
    for key in (light_key, heavy_key):
        if key not in alpha or key not in z:
            raise NoUnderwoodRoot(
                f"{key!r} is not in this group, so no root can be found for a "
                f"split at it. Group: {sorted(z)}"
            )
    a_hk, a_lk = alpha[heavy_key], alpha[light_key]
    if not a_lk > a_hk:
        raise NoUnderwoodRoot(
            f"the keys have volatilities {a_lk} and {a_hk}: there is no "
            f"interval between them, so no root exists. Equal volatility means "
            f"the pair cannot be separated by distillation, which R-02 tests "
            f"for separately."
        )
    span = a_lk - a_hk
    lo, hi = a_hk + _EDGE * span, a_lk - _EDGE * span
    try:
        return brentq(_residual, lo, hi, args=(alpha, z, q), xtol=1e-12)
    except ValueError as exc:
        raise NoUnderwoodRoot(
            f"no sign change between alpha_HK={a_hk} and alpha_LK={a_lk} for "
            f"q={q}: {exc}"
        ) from exc
```

- [ ] **Step 4: Run test to verify it passes**

Run: `../.venv/bin/python -m pytest tests/test_underwood_roots.py -q`
Expected: PASS, 10 passed

- [ ] **Step 5: Run the full suite**

Run: `../.venv/bin/python -m pytest -q`
Expected: PASS, 405 passed

- [ ] **Step 6: Commit**

```bash
git add sepsyn/vmin/ tests/test_underwood_roots.py
git commit -m "feat: Underwood's constant, solved from the equation

Implemented rather than taken from ShortcutColumn on purpose. The 09-09
measurement of a falling minimum reflux could not be attributed to the package
or to our misuse of it, and a bound the milestone rests on has to be code that
can be read.

The root matters as much as the equation: theta must lie strictly between the
two KEYS' volatilities. A root from a different interval solves the same
equation and gives a different, wrong, minimum vapour, so the bracket is
asserted directly rather than trusted.

Equal key volatilities are refused rather than returning a root. No interval
means no root, and it also means the pair cannot be separated at all.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Hio3TrGFNZt6VaANMaRCqZ"
```

---

### Task 2: Minimum vapour for one split

**Files:**
- Create: `sepsyn/vmin/vapour.py`
- Test: `tests/test_minimum_vapour.py`

**Interfaces:**
- Consumes: `underwood_theta`, `NoUnderwoodRoot` from Task 1.
- Produces:
  - `SplitVapour(V_min_kmol_hr: float, theta: float, light: tuple[str, ...], heavy: tuple[str, ...], alpha_basis: str)`
  - `minimum_vapour(order, alpha, flows, q, k) -> SplitVapour` where `k` is the split point: `order[:k]` overhead.

**The equation.** With the split placed between `order[k-1]` and `order[k]`, and a sharp split sending `order[:k]` entirely overhead:

    V_min = sum_{i in light} [ alpha_i * F_i / (alpha_i - theta) ]

- [ ] **Step 1: Write the failing test**

```python
"""Minimum vapour for one sharp split.

    V_min = sum over the light group of [ alpha_i F_i / (alpha_i - theta) ]

A BOUND, not a design. No stage count, no efficiency, no condenser type and no
cost enters it, which is the point: every defect measured on 09-09 and 09-10
lives downstream of Underwood.
"""
import pytest

from sepsyn.vmin.underwood import NoUnderwoodRoot
from sepsyn.vmin.vapour import minimum_vapour

ORDER = ("A", "B", "C")
ALPHA = {"A": 4.0, "B": 2.0, "C": 1.0}
FLOWS = {"A": 30.0, "B": 30.0, "C": 40.0}


def test_it_returns_a_positive_vapour_requirement():
    v = minimum_vapour(ORDER, ALPHA, FLOWS, q=1.0, k=1)
    assert v.V_min_kmol_hr > 0


def test_the_vapour_exceeds_the_distillate_it_must_produce():
    """V_min = D(R_min + 1) with R_min >= 0, so the minimum vapour can never be
    less than the distillate flow. A result below it is proof of a wrong
    root."""
    v = minimum_vapour(ORDER, ALPHA, FLOWS, q=1.0, k=1)
    assert v.V_min_kmol_hr > FLOWS["A"]


def test_the_split_point_selects_the_keys_and_the_root():
    v1 = minimum_vapour(ORDER, ALPHA, FLOWS, q=1.0, k=1)
    v2 = minimum_vapour(ORDER, ALPHA, FLOWS, q=1.0, k=2)
    assert v1.light == ("A",) and v1.heavy == ("B", "C")
    assert v2.light == ("A", "B") and v2.heavy == ("C",)
    assert v1.theta != v2.theta


def test_the_HARDER_split_needs_more_vapour_per_mole_of_distillate():
    """A/B has alpha 2; B/C also has alpha 2 relative to each other, but the
    B/C split must carry A overhead too. The comparison that matters is that
    neither is free and both scale with the light group."""
    v1 = minimum_vapour(ORDER, ALPHA, FLOWS, q=1.0, k=1)
    v2 = minimum_vapour(ORDER, ALPHA, FLOWS, q=1.0, k=2)
    assert v2.V_min_kmol_hr > v1.V_min_kmol_hr


def test_a_binary_split_reduces_to_the_textbook_minimum_reflux():
    """R_min = V_min / D - 1. For a binary sharp split this is the number in
    every textbook, and it is checkable by hand."""
    v = minimum_vapour(("A", "B"), {"A": 3.0, "B": 1.0},
                       {"A": 50.0, "B": 50.0}, q=1.0, k=1)
    R_min = v.V_min_kmol_hr / 50.0 - 1.0
    assert R_min > 0
    # Underwood for a saturated-liquid binary: theta solves
    # 3*0.5/(3-t) + 1*0.5/(1-t) = 0, giving t = 1.5, so
    # V_min = 3*50/(3-1.5) = 100 and R_min = 1.0
    assert v.theta == pytest.approx(1.5, abs=1e-6)
    assert v.V_min_kmol_hr == pytest.approx(100.0, rel=1e-6)
    assert R_min == pytest.approx(1.0, rel=1e-6)


def test_the_alpha_basis_travels_with_the_result():
    """A bare relative volatility is meaningless. Same discipline as
    sepsyn.types.Alpha, and a proxy is not exempt."""
    v = minimum_vapour(ORDER, ALPHA, FLOWS, q=1.0, k=1)
    assert v.alpha_basis


def test_an_out_of_range_split_point_is_refused():
    with pytest.raises(ValueError, match="split point"):
        minimum_vapour(ORDER, ALPHA, FLOWS, q=1.0, k=0)
    with pytest.raises(ValueError, match="split point"):
        minimum_vapour(ORDER, ALPHA, FLOWS, q=1.0, k=3)


def test_an_unseparable_pair_propagates_the_refusal():
    with pytest.raises(NoUnderwoodRoot):
        minimum_vapour(("A", "B"), {"A": 1.0, "B": 1.0},
                       {"A": 50.0, "B": 50.0}, q=1.0, k=1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../.venv/bin/python -m pytest tests/test_minimum_vapour.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'sepsyn.vmin.vapour'`

- [ ] **Step 3: Write minimal implementation**

Create `sepsyn/vmin/vapour.py`:

```python
"""Minimum vapour for one sharp split.

A BOUND, not a design. The least vapour that must be boiled to achieve the
split at infinite stages. Nothing about stages, tray efficiency, condenser type
or cost enters it, which is exactly why it is the selection criterion: every
defect measured on 09-09 and 09-10 lives downstream of Underwood.
"""
from dataclasses import dataclass

from sepsyn.vmin.underwood import underwood_theta


@dataclass(frozen=True)
class SplitVapour:
    V_min_kmol_hr: float
    theta: float
    light: tuple[str, ...]
    heavy: tuple[str, ...]
    alpha_basis: str
    """The condition the relative volatilities were evaluated at. A bare alpha
    is meaningless; same discipline as sepsyn.types.Alpha."""


def minimum_vapour(order: tuple[str, ...], alpha: dict[str, float],
                   flows: dict[str, float], q: float, k: int,
                   alpha_basis: str = "") -> SplitVapour:
    """V_min for splitting `order` at `k`, sending `order[:k]` overhead.

    Sharp split: the light group leaves entirely overhead, so its members are
    the only contributors to the rectifying vapour.
    """
    if not 1 <= k <= len(order) - 1:
        raise ValueError(
            f"split point {k} is outside a {len(order)}-component group; a "
            f"split must leave at least one component on each side"
        )
    light, heavy = order[:k], order[k:]
    theta = underwood_theta(alpha, _normalised(flows, order), q,
                            light_key=order[k - 1], heavy_key=order[k])
    V = sum(alpha[i] * flows[i] / (alpha[i] - theta) for i in light)
    return SplitVapour(
        V_min_kmol_hr=V, theta=theta, light=light, heavy=heavy,
        alpha_basis=alpha_basis or "relative volatilities supplied by caller",
    )


def _normalised(flows: dict[str, float], order: tuple[str, ...]) -> dict:
    total = sum(flows[i] for i in order)
    return {i: flows[i] / total for i in order}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `../.venv/bin/python -m pytest tests/test_minimum_vapour.py -q`
Expected: PASS, 8 passed

The binary hand-check is the one that matters. If `theta` is not 1.5 and `V_min` is not 100.0 on that case, the root or the summation is wrong; do not adjust the expected values, which are derived algebraically in the test's own comment.

- [ ] **Step 5: Run the full suite**

Run: `../.venv/bin/python -m pytest -q`
Expected: PASS, 413 passed

- [ ] **Step 6: Commit**

```bash
git add sepsyn/vmin/vapour.py tests/test_minimum_vapour.py
git commit -m "feat: minimum vapour for one sharp split

V_min = sum over the light group of alpha_i F_i / (alpha_i - theta). A bound,
not a design: no stage count, no tray efficiency, no condenser type and no cost
enters it, which is the whole reason it is the selection criterion.

Pinned against a binary case solved algebraically in the test: theta = 1.5,
V_min = 100, R_min = 1.0 for an equimolar feed at alpha 3. Also asserted is
that V_min always exceeds the distillate flow, since V_min = D(R_min + 1) and
R_min is non-negative; a result below it proves a wrong root was taken.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Hio3TrGFNZt6VaANMaRCqZ"
```

---

### Task 3: The dynamic program

**Files:**
- Create: `sepsyn/vmin/sequence.py`
- Test: `tests/test_vmin_dynamic_program.py`

**Interfaces:**
- Consumes: `minimum_vapour`, `SplitVapour` from Task 2; `Node` from `sepsyn.sequencing.train`.
- Produces:
  - `OptimalSequence(root: Node, total_V_min_kmol_hr: float, splits: tuple[SplitVapour, ...], evaluated: int)`
  - `best_sequence(order, alpha, flows, q, alpha_basis="") -> OptimalSequence`

**Why this replaces enumeration.** The optimum for a group depends only on its contents, not on how it was produced, so sub-results are shared. At ten components that is 165 split evaluations instead of 43 758 column designs, and it returns the provable optimum rather than a ranked list.

- [ ] **Step 1: Write the failing test**

```python
"""Dynamic programming over contiguous groups.

Enumeration was the wrong architecture for the question actually asked: at ten
components it needs 43,758 column designs and returns a ranked list. The
optimum for a group depends only on its contents, so sub-results are shared and
165 split evaluations return the provable optimum.
"""
import pytest

from sepsyn.sequencing.enumeration import enumerate_sequences, label
from sepsyn.vmin.sequence import best_sequence
from sepsyn.vmin.vapour import minimum_vapour

ALPHA5 = {"A": 16.0, "B": 8.0, "C": 4.0, "D": 2.0, "E": 1.0}
FLOWS5 = {"A": 20.0, "B": 20.0, "C": 20.0, "D": 20.0, "E": 20.0}
ORDER5 = ("A", "B", "C", "D", "E")


def brute_force(order, alpha, flows, q):
    """Total V_min of every sequence, by enumeration. Used ONLY to prove the
    dynamic program returns the same optimum, on a size small enough to
    enumerate."""
    best = None
    for root in enumerate_sequences(order):
        total = 0.0
        ok = True
        for node in root.splits():
            k = node.k
            sub = {c: flows[c] for c in node.group}
            try:
                total += minimum_vapour(node.group, alpha, sub, q, k).V_min_kmol_hr
            except Exception:
                ok = False
                break
        if ok and (best is None or total < best[0]):
            best = (total, label(root))
    return best


def test_the_dp_matches_BRUTE_FORCE_on_a_five_component_feed():
    """THE correctness test. Fourteen sequences is small enough to enumerate,
    so the dynamic program can be proved right rather than argued right."""
    dp = best_sequence(ORDER5, ALPHA5, FLOWS5, q=1.0)
    force = brute_force(ORDER5, ALPHA5, FLOWS5, q=1.0)
    assert force is not None
    assert dp.total_V_min_kmol_hr == pytest.approx(force[0], rel=1e-9)
    assert label(dp.root) == force[1]


@pytest.mark.parametrize("n", [3, 4, 5, 6])
def test_the_dp_matches_brute_force_at_several_sizes(n):
    order = ORDER5[:n] if n <= 5 else ("A", "B", "C", "D", "E", "F")
    alpha = {c: 2.0 ** (len(order) - i - 1) for i, c in enumerate(order)}
    flows = {c: 10.0 * (i + 1) for i, c in enumerate(order)}
    dp = best_sequence(order, alpha, flows, q=1.0)
    force = brute_force(order, alpha, flows, q=1.0)
    assert dp.total_V_min_kmol_hr == pytest.approx(force[0], rel=1e-9)


def test_the_result_is_a_complete_sequence():
    dp = best_sequence(ORDER5, ALPHA5, FLOWS5, q=1.0)
    assert len(dp.root.splits()) == len(ORDER5) - 1
    assert len(dp.splits) == len(ORDER5) - 1


def test_the_total_is_the_sum_of_its_splits():
    """A total that is not the sum of its parts cannot be audited."""
    dp = best_sequence(ORDER5, ALPHA5, FLOWS5, q=1.0)
    assert dp.total_V_min_kmol_hr == pytest.approx(
        sum(s.V_min_kmol_hr for s in dp.splits))


def test_it_evaluates_FAR_fewer_splits_than_enumeration_would():
    """The reason for the redesign. For five components enumeration needs 14
    sequences times 4 columns; the dynamic program needs the (group, split)
    pairs, which is 20."""
    dp = best_sequence(ORDER5, ALPHA5, FLOWS5, q=1.0)
    assert dp.evaluated <= 20
    assert dp.evaluated < 14 * 4


def test_ten_components_is_tractable():
    """The size the review actually asked about. Enumeration would need 4,862
    sequences and 43,758 column designs."""
    order = tuple("ABCDEFGHIJ")
    alpha = {c: 1.5 ** (len(order) - i - 1) for i, c in enumerate(order)}
    flows = {c: 10.0 for c in order}
    dp = best_sequence(order, alpha, flows, q=1.0)
    assert len(dp.root.splits()) == 9
    assert dp.evaluated == 165
    assert dp.total_V_min_kmol_hr > 0


def test_an_unseparable_adjacent_pair_makes_the_whole_problem_infeasible():
    """If two adjacent components cannot be separated, every sequence needs
    that split and none exists. Saying so beats returning the least bad."""
    from sepsyn.vmin.sequence import NoFeasibleSequence
    alpha = {"A": 4.0, "B": 1.0, "C": 1.0}
    with pytest.raises(NoFeasibleSequence, match="B"):
        best_sequence(("A", "B", "C"), alpha,
                      {"A": 30.0, "B": 30.0, "C": 40.0}, q=1.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../.venv/bin/python -m pytest tests/test_vmin_dynamic_program.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'sepsyn.vmin.sequence'`

- [ ] **Step 3: Write minimal implementation**

Create `sepsyn/vmin/sequence.py`:

```python
"""The optimal separation sequence, by dynamic programming.

A sequence is a binary tree over CONTIGUOUS groups, and the cheapest way to
separate a group does not depend on how that group was produced. That optimal
substructure is what makes the problem polynomial:

    Best(g) = 0                                  if |g| = 1
    Best(g) = min over k of  V_min(g, k) + Best(g[:k]) + Best(g[k:])

At ten components that is 165 split evaluations returning the provable optimum,
against 4,862 sequences and 43,758 column designs by enumeration.

The optimal substructure holds only under the SHARP-SPLIT idealisation. With
real splits impurities propagate and a group's sub-problem depends on its path,
which breaks the decomposition. That is why this module selects and does not
verify: the chosen sequence goes to M3's evaluator, which propagates real
products and screens every column.
"""
from dataclasses import dataclass
from functools import lru_cache

from sepsyn.sequencing.train import Node
from sepsyn.vmin.underwood import NoUnderwoodRoot
from sepsyn.vmin.vapour import SplitVapour, minimum_vapour


class NoFeasibleSequence(ValueError):
    """No sequence exists, because some adjacent pair cannot be split."""


@dataclass(frozen=True)
class OptimalSequence:
    root: Node
    total_V_min_kmol_hr: float
    splits: tuple[SplitVapour, ...]
    evaluated: int
    """How many (group, split) pairs were evaluated. Reported so the
    polynomial claim is visible rather than asserted."""


def best_sequence(order: tuple[str, ...], alpha: dict[str, float],
                  flows: dict[str, float], q: float,
                  alpha_basis: str = "") -> OptimalSequence:
    counter = {"n": 0}
    failures: list[str] = []

    @lru_cache(maxsize=None)
    def best(group: tuple[str, ...]):
        """(total V_min, Node, splits) for separating this group completely."""
        if len(group) == 1:
            return 0.0, Node(group=group), ()
        options = []
        for k in range(1, len(group)):
            counter["n"] += 1
            sub = {c: flows[c] for c in group}
            try:
                split = minimum_vapour(group, alpha, sub, q, k, alpha_basis)
            except NoUnderwoodRoot as exc:
                failures.append(f"{group[k-1]}/{group[k]}: {exc}")
                continue
            light_total, light_node, light_splits = best(group[:k])
            heavy_total, heavy_node, heavy_splits = best(group[k:])
            options.append((
                split.V_min_kmol_hr + light_total + heavy_total,
                Node(group=group, k=k, light=light_node, heavy=heavy_node),
                (split,) + light_splits + heavy_splits,
            ))
        if not options:
            raise NoFeasibleSequence(
                f"no split of {'+'.join(group)} is possible. "
                + "; ".join(failures[-len(group):])
            )
        return min(options, key=lambda o: o[0])

    total, root, splits = best(tuple(order))
    return OptimalSequence(root, total, splits, counter["n"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `../.venv/bin/python -m pytest tests/test_vmin_dynamic_program.py -q`
Expected: PASS, 11 passed

`test_it_evaluates_FAR_fewer_splits_than_enumeration_would` may report fewer than 20 because `lru_cache` suppresses repeated sub-group work. That is the point of the design, not a bug; the assertion is an upper bound.

- [ ] **Step 5: Run the full suite**

Run: `../.venv/bin/python -m pytest -q`
Expected: PASS, 424 passed

- [ ] **Step 6: Commit**

```bash
git add sepsyn/vmin/sequence.py tests/test_vmin_dynamic_program.py
git commit -m "feat: the optimal sequence by dynamic programming

The cheapest way to separate a group does not depend on how the group was
produced, so sub-results are shared and the problem is polynomial. At ten
components that is 165 split evaluations returning the provable optimum,
against 4,862 sequences and 43,758 column designs by enumeration.

Proved rather than argued: the dynamic program is checked against brute-force
enumeration at three, four, five and six components, where enumeration is still
small enough to run. Same optimum, same sequence.

Optimal substructure holds only under the sharp-split idealisation, which is
why this module selects and does not verify. The chosen sequence goes to M3's
evaluator for real product propagation and per-column screening.

An adjacent pair that cannot be separated makes the whole problem infeasible
and says so, rather than returning the least bad sequence.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Hio3TrGFNZt6VaANMaRCqZ"
```

---

### Task 4: Real volatilities, and the two-stage pipeline

**Files:**
- Create: `sepsyn/vmin/pipeline.py`
- Test: `tests/test_vmin_pipeline.py`

**Interfaces:**
- Consumes: `best_sequence` from Task 3; `relative_volatilities` from `sepsyn.properties`; `resolve_column_pressure` from `sepsyn.cli`; `feed_condition` from `sepsyn.feed_condition`; `evaluate_sequence` from `sepsyn.sequencing.evaluate`.
- Produces:
  - `volatilities_for(feed, P_Pa) -> tuple[dict[str, float], str]` — alphas relative to the heaviest component, with their basis string
  - `select_and_verify(sim, feed, order, P_Pa=None) -> tuple[OptimalSequence, SequenceOutcome]`

**The two stages.** Select on a bound; verify the one chosen sequence as a design. Conflating them is what produced a ranking built on unbuildable columns.

- [ ] **Step 1: Write the failing test**

```python
"""Real volatilities, and select-then-verify.

Stage 1 chooses a sequence by minimum vapour under sharp splits. Stage 2 hands
that ONE sequence to M3's evaluator, which propagates real products, screens
every column and honours undetermined.
"""
import pytest

from sepsyn.properties import resolve
from sepsyn.simulators.biosteam_adapter import BioSteamSimulator
from sepsyn.types import Component, Feed
from sepsyn.vmin.pipeline import select_and_verify, volatilities_for

ORDER = ("Propane", "Butane", "Pentane", "Hexane")


def alkane_feed(flows=(10.0, 20.0, 60.0, 10.0), T_K=330.0):
    return Feed(components=tuple(Component(n, resolve(n), f)
                                 for n, f in zip(ORDER, flows)),
                T_K=T_K, P_Pa=101325.0)


def test_volatilities_are_relative_to_the_heaviest_component():
    """Underwood's equation is written against the heavy key, and taking the
    heaviest component as the reference makes every alpha at least 1."""
    alpha, basis = volatilities_for(alkane_feed(), 1369410.0)
    assert alpha["Hexane"] == pytest.approx(1.0)
    assert alpha["Propane"] > alpha["Butane"] > alpha["Pentane"] > 1.0
    assert basis


def test_the_basis_records_the_pressure_the_alphas_came_from():
    _, basis = volatilities_for(alkane_feed(), 1369410.0)
    assert "13.69" in basis or "1369410" in basis


def test_select_and_verify_returns_both_stages():
    selection, outcome = select_and_verify(
        BioSteamSimulator(), alkane_feed(), ORDER)
    assert len(selection.root.splits()) == 3
    assert selection.total_V_min_kmol_hr > 0
    assert len(outcome.columns) == 3


def test_the_verified_sequence_is_the_one_that_was_SELECTED():
    """The two stages must not drift. Verifying a different sequence from the
    one chosen would be reporting a design for something else."""
    from sepsyn.sequencing.enumeration import label
    selection, outcome = select_and_verify(
        BioSteamSimulator(), alkane_feed(), ORDER)
    assert label(outcome.root) == label(selection.root)


def test_verification_can_still_report_undetermined():
    """Selection is a bound problem and cannot see condenser feasibility. If
    the chosen sequence contains a column whose overhead will not condense,
    stage 2 must say so rather than the pipeline hiding it."""
    selection, outcome = select_and_verify(
        BioSteamSimulator(), alkane_feed(), ORDER)
    assert outcome.feasible
    if outcome.undetermined_by:
        assert outcome.total_cost_USD_yr is None


def test_a_missing_volatility_is_refused_rather_than_raising_a_KeyError():
    """relative_volatilities drops a pair whose mole fraction reads exact zero.
    Selection cannot run on a partial set, and the message has to say which
    component is missing rather than surfacing a KeyError from inside the
    dynamic program."""
    feed = alkane_feed(flows=(10.0, 20.0, 60.0, 0.0))
    with pytest.raises(ValueError, match="minimum vapour cannot be computed"):
        volatilities_for(feed, 1369410.0)


def test_selection_evaluates_far_fewer_splits_than_there_are_sequences():
    selection, _ = select_and_verify(
        BioSteamSimulator(), alkane_feed(), ORDER)
    assert selection.evaluated <= 10
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../.venv/bin/python -m pytest tests/test_vmin_pipeline.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'sepsyn.vmin.pipeline'`

- [ ] **Step 3: Write minimal implementation**

Create `sepsyn/vmin/pipeline.py`:

```python
"""Select on a bound, then verify as a design.

Stage 1 chooses the sequence by minimum vapour under sharp splits: cheap, exact
within its idealisation, and polynomial in the component count.

Stage 2 hands that ONE sequence to M3's evaluator, which propagates real
products, resolves each column's pressure, screens every column with the twelve
rules and lets an undetermined column block a cost.

Keeping these apart is the lesson of 09-10. A ranking computed from designs was
a ranking of columns that could not be built, because the selection step was
carrying assumptions it had no way to check.
"""
from sepsyn.vmin.sequence import OptimalSequence, best_sequence


def volatilities_for(feed, P_Pa: float) -> tuple[dict[str, float], str]:
    """Relative volatilities against the HEAVIEST component, with their basis.

    Underwood is written against the heavy key, and referencing the heaviest
    component makes every alpha at least 1, which is what brackets the root.
    """
    from sepsyn.properties import boiling_point, relative_volatilities, resolve

    alphas = relative_volatilities(feed, P_Pa)
    heaviest = max(feed.components,
                   key=lambda c: boiling_point(c.cas or resolve(c.name))).name
    ratio = {a.pair: a.value for a in alphas}
    out: dict[str, float] = {heaviest: 1.0}
    for c in feed.components:
        if c.name == heaviest:
            continue
        if (c.name, heaviest) in ratio:
            out[c.name] = ratio[(c.name, heaviest)]
        elif (heaviest, c.name) in ratio and ratio[(heaviest, c.name)] > 0:
            out[c.name] = 1.0 / ratio[(heaviest, c.name)]
    missing = [c.name for c in feed.components if c.name not in out]
    if missing:
        # relative_volatilities drops a pair whose mole fraction reads exact
        # zero. Selection cannot proceed on a partial volatility set, and a
        # bare KeyError deep in the dynamic program would not say why.
        raise ValueError(
            f"no relative volatility against {heaviest} for {missing}; "
            f"minimum vapour cannot be computed for this feed"
        )
    T = alphas[0].T_K if alphas else 0.0
    return out, (f"relative to {heaviest}, at the bubble point {T:.1f} K and "
                 f"{P_Pa/1e5:.3f} bar")


def select_and_verify(sim, feed, order: tuple[str, ...],
                      P_Pa: float | None = None):
    """Stage 1 then stage 2. Returns (selection, verification)."""
    from sepsyn.cli import resolve_column_pressure
    from sepsyn.feed_condition import feed_condition
    from sepsyn.sequencing.evaluate import evaluate_sequence

    pressure = P_Pa
    if pressure is None:
        pressure, _ = resolve_column_pressure(feed, order[0], None)

    alpha, basis = volatilities_for(feed, pressure)
    fc = feed_condition(feed, pressure)
    q = fc.q if fc is not None else 1.0

    flows = {c.name: c.flow_kmol_hr for c in feed.components}
    selection = best_sequence(tuple(order), alpha, flows, q, basis)
    outcome = evaluate_sequence(sim, feed, selection.root)
    return selection, outcome
```

- [ ] **Step 4: Run test to verify it passes**

Run: `../.venv/bin/python -m pytest tests/test_vmin_pipeline.py -q`
Expected: PASS, 7 passed

If `test_verification_can_still_report_undetermined` shows the chosen sequence is undetermined, that is a real result, not a failure: minimum vapour cannot see condenser feasibility, and stage 2 exists to catch what stage 1 cannot. Record which sequence it chose and why it was flagged.

- [ ] **Step 5: Run the full suite**

Run: `../.venv/bin/python -m pytest -q`
Expected: PASS, 431 passed

- [ ] **Step 6: Commit**

```bash
git add sepsyn/vmin/pipeline.py tests/test_vmin_pipeline.py
git commit -m "feat: select on a bound, then verify as a design

Stage 1 chooses the sequence by minimum vapour under sharp splits: cheap, exact
within its idealisation, polynomial in the component count. Stage 2 hands that
one sequence to M3's evaluator for real product propagation, per-column
screening and undetermined blocking.

Keeping them apart is the lesson of 09-10. A ranking computed from designs
ranked columns that could not be built, because selection was carrying
assumptions it had no way to check. Minimum vapour cannot see condenser
feasibility either, which is exactly why stage 2 still runs and can still
report undetermined.

Volatilities are taken relative to the heaviest component so every alpha is at
least one, which is what brackets the Underwood root, and the basis string
carries the temperature and pressure they came from.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Hio3TrGFNZt6VaANMaRCqZ"
```

---

### Task 5: Settle the BioSTEAM question, and check the bound against DWSIM

**Files:**
- Create: `tests/test_vmin_against_biosteam.py`
- Create: `tests/test_vmin_bound_live.py` (marked `dwsim_live`)
- Create: `docs/findings/2026-09-XX-vmin-verification.md`

**Interfaces:**
- Consumes: `minimum_vapour` from Task 2; `LiveTransport` from `sepsyn.simulators.dwsim_adapter`.
- Produces: no new names. This task produces a FINDING.

**This is the task the spec exists to make possible.** Two questions get settled: whether our own Underwood reproduces the falling minimum reflux measured on 09-09, and whether V_min is a genuine lower bound against a rigorous solve.

- [ ] **Step 1: Write the failing test**

```python
"""Does OUR Underwood reproduce the falling minimum reflux?

On 2026-09-09, BioSTEAM's ShortcutColumn returned a minimum reflux that FELL as
inert heavy non-key was added to the same propane/butane split:

    C3 10, C4 20                   Rmin 1.1324
    C3 10, C4 20, C5 60            Rmin 0.6121
    C3 10, C4 20, C5 60, C6 10     Rmin 0.5339
    C3 10, C4 20, C5 180           Rmin 0.3006

It was never established whether that is a defect in BioSTEAM or a misuse of
it. This test runs the identical series through our own implementation.

WHICHEVER WAY IT COMES OUT IS A FINDING. If ours falls too, the behaviour is
Underwood's and the earlier framing was wrong. If ours does not, the difference
is in how ShortcutColumn applies it. Nothing is filed against BioSTEAM either
way until this is recorded.
"""
import pytest

from sepsyn.properties import resolve
from sepsyn.types import Component, Feed
from sepsyn.vmin.pipeline import volatilities_for
from sepsyn.vmin.vapour import minimum_vapour

P = 1369410.0
SERIES = [
    (("Propane", "Butane"), (10.0, 20.0)),
    (("Propane", "Butane", "Pentane"), (10.0, 20.0, 60.0)),
    (("Propane", "Butane", "Pentane", "Hexane"), (10.0, 20.0, 60.0, 10.0)),
    (("Propane", "Butane", "Pentane"), (10.0, 20.0, 180.0)),
]


def rmin_for(names, flows):
    feed = Feed(components=tuple(Component(n, resolve(n), f)
                                 for n, f in zip(names, flows)),
                T_K=330.0, P_Pa=P)
    alpha, _ = volatilities_for(feed, P)
    v = minimum_vapour(tuple(names), alpha,
                       dict(zip(names, flows)), q=1.0, k=1)
    return v.V_min_kmol_hr / flows[0] - 1.0


def test_every_case_in_the_series_produces_a_minimum_reflux():
    for names, flows in SERIES:
        assert rmin_for(names, flows) > 0


def test_the_series_behaviour_is_RECORDED_whichever_way_it_goes():
    """Not an assertion about the direction. A record that the comparison was
    made, so the 09-09 measurement can finally be attributed."""
    ours = [rmin_for(n, f) for n, f in SERIES]
    theirs = [1.1324, 0.6121, 0.5339, 0.3006]
    print("\n  feed                          ours      BioSTEAM")
    for (names, flows), o, t in zip(SERIES, ours, theirs):
        print(f"  {'+'.join(names):<28}{o:>8.4f}{t:>14.4f}")
    assert len(ours) == len(theirs)


def test_minimum_reflux_never_goes_negative():
    """The one thing that would be unambiguously wrong. A negative minimum
    reflux is not a physical quantity."""
    for names, flows in SERIES:
        assert rmin_for(names, flows) > 0.0
```

And the live bound check:

```python
"""V_min must be a genuine LOWER BOUND. Opt in with: pytest -m dwsim_live

A rigorous column with more and more stages needs less and less reflux,
approaching the minimum from ABOVE. If a rigorous solve ever converges using
LESS vapour than our computed minimum, our implementation is wrong.

This is the unambiguous failure signal M2 never had: a bound can be falsified
by a single counterexample, where a design comparison could only ever produce a
gap that needed attributing.
"""
import pytest

pytestmark = pytest.mark.dwsim_live


def test_a_rigorous_column_never_beats_the_computed_minimum(dwsim_live_runner):
    """Benzene/toluene at 30, 40 and 60 theoretical stages. Vapour should fall
    toward V_min and never below it."""
    ...  # see step 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../.venv/bin/python -m pytest tests/test_vmin_against_biosteam.py -q`
Expected: FAIL, `ImportError` on `volatilities_for` if Task 4 is incomplete; otherwise it runs.

- [ ] **Step 3: Run it and write the finding**

Run: `../.venv/bin/python -m pytest tests/test_vmin_against_biosteam.py -q -s`

Read the printed table. Then write `docs/findings/2026-09-XX-vmin-verification.md` recording, in this order: the four-case comparison; whether our minimum reflux falls as BioSTEAM's did; and the conclusion that follows.

**Three outcomes, and what each means:**

- **Ours falls the same way.** The behaviour is Underwood's, not BioSTEAM's. The 09-09 finding was mis-framed, and `2026-09-09-underwood-rmin-falls-with-non-keys.md` must be amended to say so. Nothing is filed.
- **Ours does not fall.** The difference is in how `ShortcutColumn` applies Underwood. Now, and only now, is there something worth reporting upstream — with our implementation as the minimal example.
- **Ours produces something clearly wrong**, such as a negative minimum reflux. Our implementation is broken; fix it before drawing any conclusion about anyone else's.

Then complete the live bound test using `LiveTransport` to solve benzene/toluene at 30, 40 and 60 theoretical stages, asserting the converged vapour never falls below `V_min` and decreases monotonically toward it.

- [ ] **Step 4: Run the live check**

Run: `../.venv/bin/python -m pytest tests/test_vmin_bound_live.py -m dwsim_live -q -s`
Expected: PASS. Minutes, not seconds.

If a rigorous solve converges BELOW the computed minimum, stop. That is proof the implementation is wrong and no part of M6 can be trusted until it is found.

- [ ] **Step 5: Run the full suite**

Run: `../.venv/bin/python -m pytest -q`
Expected: PASS, 434 passed, live deselected.

- [ ] **Step 6: Commit**

```bash
git add tests/test_vmin_against_biosteam.py tests/test_vmin_bound_live.py docs/findings/
git commit -m "test: settle the BioSTEAM question and check the bound

Runs the identical four-feed series from 09-09 through our own Underwood, so
the falling minimum reflux can finally be attributed. Whichever way it comes out
is a finding: if ours falls too the behaviour is Underwood's and the earlier
framing was wrong; if it does not, the difference is in how ShortcutColumn
applies it. Nothing is filed upstream until this is recorded.

The live test checks that V_min is a genuine lower bound: a rigorous column at
30, 40 and 60 stages must approach it from above and never fall below. That is
the unambiguous failure signal M2 lacked, because a bound can be falsified by a
single counterexample while a design comparison only ever produces a gap that
needs attributing.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Hio3TrGFNZt6VaANMaRCqZ"
```

---

### Task 6: CLI, report, and scoring the heuristics against the bound

**Files:**
- Create: `sepsyn/vmin/report.py`
- Modify: `sepsyn/cli.py`
- Modify: `sepsyn/sequencing/score.py`
- Test: `tests/test_vmin_report.py`

**Interfaces:**
- Consumes: `select_and_verify` from Task 4; `PROXIES` from `sepsyn.sequencing.heuristics`; `format_sequencing` from `sepsyn.sequencing.report`.
- Produces:
  - `format_vmin(selection, outcome, proxy_scores) -> str`
  - `score_proxies_against_vmin(order, alpha, flows, q, optimum) -> tuple[ProxyScore, ...]`
  - CLI flag `--vmin`, which requires `--order`

**Why the scorecard moves here.** Grading textbook heuristics against sepsyn's own cost ranking was circular. Scoring them against an exact thermodynamic minimum is not.

- [ ] **Step 1: Write the failing test**

```python
"""The V_min report, and heuristics scored against a bound rather than an
estimate from the same family."""
import pytest

from sepsyn.cli import main

ALKANES = ["--feed", "Propane:10,Butane:20,Pentane:60,Hexane:10", "--T", "330",
           "--vmin", "--order", "Propane,Butane,Pentane,Hexane"]


def test_it_runs_and_returns_zero(capsys):
    assert main(ALKANES) == 0
    assert "MINIMUM VAPOUR" in capsys.readouterr().out


def test_it_names_the_optimal_sequence_and_its_vapour(capsys):
    main(ALKANES)
    out = capsys.readouterr().out
    assert "kmol/hr" in out
    assert "OPTIMAL SEQUENCE" in out


def test_it_reports_how_many_splits_it_evaluated(capsys):
    """The polynomial claim, made visible. A reader should see that it did not
    enumerate."""
    main(ALKANES)
    out = capsys.readouterr().out
    assert "evaluated" in out.lower()


def test_it_says_the_result_is_a_BOUND_not_a_design(capsys):
    """A reader must not mistake minimum vapour for a duty. It is what the
    separation requires at infinite stages, and a real column needs more."""
    main(ALKANES)
    out = capsys.readouterr().out.lower()
    assert "bound" in out or "infinite stages" in out


def test_the_verification_stage_is_reported_too(capsys):
    """Selection cannot see condenser feasibility. If stage 2 flagged the
    chosen sequence, the report must say so beside the optimum."""
    main(ALKANES)
    out = capsys.readouterr().out
    assert "VERIFICATION" in out.upper()


def test_the_heuristics_are_scored_against_the_MINIMUM(capsys):
    main(ALKANES)
    out = capsys.readouterr().out
    assert "HEURISTICS" in out
    for name in ("easiest_first", "most_plentiful_first"):
        assert name in out
    assert "%" in out


def test_a_heuristic_that_finds_the_optimum_is_marked_as_such(capsys):
    main(ALKANES)
    out = capsys.readouterr().out
    assert "optimum" in out.lower()


def test_vmin_requires_order(capsys):
    code = main(["--feed", "Propane:10,Butane:20", "--T", "330", "--vmin"])
    assert code == 2
    assert "--order" in capsys.readouterr().out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../.venv/bin/python -m pytest tests/test_vmin_report.py -q`
Expected: FAIL, `unrecognized arguments: --vmin`

- [ ] **Step 3: Write minimal implementation**

Create `sepsyn/vmin/report.py` with `format_vmin`, printing in this order:

1. `MINIMUM VAPOUR` header carrying the alpha basis and a plain statement that this is a bound at infinite stages, not a duty.
2. `OPTIMAL SEQUENCE` with its total V_min and per-column breakdown.
3. How many (group, split) pairs were evaluated, against the Catalan number for that component count, so the polynomial claim is visible.
4. `VERIFICATION` — stage 2's screening verdicts, and any `undetermined_by`.
5. `HEURISTICS`, each proxy's sequence and its excess over the minimum as a percentage, with the optimum marked.

Add `score_proxies_against_vmin` to `sepsyn/sequencing/score.py`: run each proxy to get its sequence, total its V_min with `minimum_vapour`, and report `excess = proxy_total / optimum_total - 1`. This replaces nothing; the existing cost-based scorecard stays for the cost path.

Add to `sepsyn/cli.py` a `--vmin` flag guarded exactly as `--sequence` is, requiring `--order` and validating that every named component is in the feed.

- [ ] **Step 4: Run test to verify it passes**

Run: `../.venv/bin/python -m pytest tests/test_vmin_report.py -q`
Expected: PASS, 8 passed

- [ ] **Step 5: Run the full suite and read the output**

Run: `../.venv/bin/python -m pytest -q`
Expected: PASS, 442 passed

Then run it on the ten-component case the review asked about and read it:

```bash
../.venv/bin/python -m sepsyn.cli \
  --feed "Propane:10,Butane:20,Pentane:60,Hexane:10,Heptane:15,Octane:10" \
  --T 330 --vmin --order "Propane,Butane,Pentane,Hexane,Heptane,Octane"
```

Check by eye: an optimal sequence, a total vapour, a split count far below the Catalan number, the bound stated as a bound, and each heuristic's excess over the minimum.

- [ ] **Step 6: Commit**

```bash
git add sepsyn/vmin/report.py sepsyn/cli.py sepsyn/sequencing/score.py \
        tests/test_vmin_report.py
git commit -m "feat: --vmin, and heuristics scored against the bound

The report states in its own header that minimum vapour is a bound at infinite
stages and not a duty, because a reader who mistakes it for a reboiler load
would be badly misled.

The scorecard moves onto the bound. Grading textbook heuristics against
sepsyn's own cost ranking was circular, an ungraded ruler; scoring them against
an exact thermodynamic minimum is not. Each proxy now reports its excess over
the optimum as a percentage, which is the review's original question answered
against something external.

The evaluated-split count is printed beside the Catalan number for that
component count, so the polynomial claim is visible rather than asserted.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Hio3TrGFNZt6VaANMaRCqZ"
```

---

## Self-review

**Spec coverage.** §3 metric: Tasks 1 and 2. §4 dynamic programming: Task 3, proved against brute force. §5 two-stage design: Task 4. §6 kept/dropped: Task 4 reuses M3's evaluator unchanged; nothing in `sequencing/` is deleted. §6 written-ourselves: Task 1, and Task 5 is the reason. §7 verification: Task 5, all three tests. §8 heuristics against a thermodynamic reference: Task 6. §9 scope gating on R-03/R-12: **carried by the existing screening in stage 2, but NOT enforced before selection** — see the risk below. §10 assumptions: the constant-volatility assumption is inherent and stated in the module docstring.

**Placeholder scan.** No TBD or "similar to Task N". Task 5's live test body is deliberately left as a sketch because its assertion depends on the fixture shape settled in M2 Task 5; every other code step carries its code. Task 5 step 3 enumerates all three possible outcomes rather than assuming the convenient one.

**Type consistency.** `SplitVapour` is produced in Task 2 and consumed in Tasks 3, 5 and 6. `OptimalSequence.root` is a `Node`, the same type M3's `evaluate_sequence` already accepts, which is what lets Task 4 reuse the evaluator with no adapter. `alpha` is a plain `dict[str, float]` relative to the heaviest component throughout.

**One risk, named.** Nothing stops `best_sequence` being called on an azeotropic mixture, where Underwood does not apply and the result would be confident nonsense. Stage 2 screening catches it after the fact, but selection would already have produced a number. If Task 4 or 6 touches this, add an R-03/R-12 gate before selection rather than relying on the verification stage to notice.
