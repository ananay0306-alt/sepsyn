# sepsyn Milestone 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Python library and CLI that decides whether distillation is feasible for a given feed, says why by citing a printed rule, and designs the column when it is.

**Architecture:** Feed spec in, property record out, rules evaluated against that record, design only if a rule says feasible. The property record is the only thing rules can see, so the engine is testable with no chemistry. The simulator sits behind a two-method protocol so DWSIM can be added later without a refactor.

**Tech Stack:** Python 3.14, `chemicals` (property lookups), `thermosteam` (VLE for azeotropes), `biosteam` (column design), `PyYAML` (rule table), `pytest`.

**Spec:** `docs/superpowers/specs/2026-08-21-sepsyn-design.md`

## Global Constraints

- Python interpreter is `../.venv/bin/python` relative to the repo root. All commands use it explicitly.
- Flows are kmol/hr, temperatures K, pressures Pa. No other units anywhere.
- Relative volatility is NEVER stored as a bare float. It always carries `T_K`, `P_Pa` and `basis`.
- `ColumnSpec` takes recoveries, never mole fractions.
- If no rule fires, the engine returns `unknown`. It never defaults to distillation.
- Cooling water design temperature is 313.15 K (40 C) throughout.
- Every dataclass is `frozen=True` unless a task says otherwise.

---

### Task 1: Package scaffold and core data types

**Files:**
- Create: `sepsyn/__init__.py`
- Create: `sepsyn/types.py`
- Create: `tests/test_types.py`
- Create: `pytest.ini`

**Interfaces:**
- Consumes: nothing
- Produces: `Component(name: str, cas: str, flow_kmol_hr: float)`, `Feed(components: tuple[Component, ...], T_K: float, P_Pa: float)` with properties `total_kmol_hr -> float` and `mole_fractions -> dict[str, float]`

- [ ] **Step 1: Write the failing test**

Create `tests/test_types.py`:

```python
import pytest
from sepsyn.types import Component, Feed


def test_feed_totals_and_mole_fractions():
    feed = Feed(
        components=(
            Component("Methanol", "67-56-1", 100.0),
            Component("Water", "7732-18-5", 80.0),
            Component("Glycerol", "56-81-5", 20.0),
        ),
        T_K=330.0,
        P_Pa=101325.0,
    )
    assert feed.total_kmol_hr == 200.0
    assert feed.mole_fractions["Methanol"] == pytest.approx(0.5)
    assert feed.mole_fractions["Water"] == pytest.approx(0.4)
    assert feed.mole_fractions["Glycerol"] == pytest.approx(0.1)


def test_feed_rejects_zero_total_flow():
    with pytest.raises(ValueError, match="total flow must be positive"):
        Feed(components=(Component("Water", "7732-18-5", 0.0),),
             T_K=298.15, P_Pa=101325.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sepsyn && ../.venv/bin/python -m pytest tests/test_types.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sepsyn.types'`

- [ ] **Step 3: Write minimal implementation**

Create `sepsyn/__init__.py` (empty file).

Create `pytest.ini`:

```ini
[pytest]
testpaths = tests
pythonpath = .
```

Create `sepsyn/types.py`:

```python
"""Core data types. Flows kmol/hr, T in K, P in Pa, everywhere."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Component:
    name: str
    cas: str
    flow_kmol_hr: float


@dataclass(frozen=True)
class Feed:
    components: tuple[Component, ...]
    T_K: float
    P_Pa: float

    def __post_init__(self) -> None:
        if self.total_kmol_hr <= 0:
            raise ValueError("total flow must be positive")

    @property
    def total_kmol_hr(self) -> float:
        return sum(c.flow_kmol_hr for c in self.components)

    @property
    def mole_fractions(self) -> dict[str, float]:
        total = self.total_kmol_hr
        return {c.name: c.flow_kmol_hr / total for c in self.components}

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(c.name for c in self.components)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sepsyn && ../.venv/bin/python -m pytest tests/test_types.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add sepsyn/__init__.py sepsyn/types.py tests/test_types.py pytest.ini
git commit -m "feat: Feed and Component data types"
```

---

### Task 2: Chemical property lookups with helpful failures

**Files:**
- Create: `sepsyn/properties.py`
- Create: `tests/test_properties.py`

**Interfaces:**
- Consumes: nothing
- Produces: `resolve(name: str) -> str` (returns CAS, raises `UnknownChemical`), `boiling_point(cas: str) -> float`, `critical_temperature(cas: str) -> float`, `critical_pressure(cas: str) -> float`, exception `UnknownChemical`

- [ ] **Step 1: Write the failing test**

Create `tests/test_properties.py`:

```python
import pytest
from sepsyn.properties import (
    UnknownChemical, resolve, boiling_point,
    critical_temperature, critical_pressure,
)

# literature values; tolerances are loose enough to survive a database update
KNOWN = [
    ("Hydrogen", 20.37, 33.15),
    ("Methane", 111.67, 190.56),
    ("Methanol", 337.63, 513.38),
    ("Water", 373.12, 647.10),
    ("Glycerol", 562.15, 850.00),
    ("Ethanol", 351.57, 514.71),
]


@pytest.mark.parametrize("name,tb,tc", KNOWN)
def test_boiling_and_critical_temperatures(name, tb, tc):
    cas = resolve(name)
    assert boiling_point(cas) == pytest.approx(tb, abs=0.5)
    assert critical_temperature(cas) == pytest.approx(tc, abs=0.5)


def test_critical_pressure_is_positive():
    assert critical_pressure(resolve("Methane")) > 1e6


def test_unknown_chemical_names_near_matches():
    with pytest.raises(UnknownChemical) as exc:
        resolve("Methanool")
    assert "Methanool" in str(exc.value)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sepsyn && ../.venv/bin/python -m pytest tests/test_properties.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sepsyn.properties'`

- [ ] **Step 3: Write minimal implementation**

Create `sepsyn/properties.py`:

```python
"""Chemical property lookups. Cheap and pure -- no VLE, no simulator."""
import chemicals


class UnknownChemical(ValueError):
    """Raised when a chemical name cannot be resolved to a CAS number."""


def resolve(name: str) -> str:
    """Resolve a chemical name to its CAS number."""
    try:
        return chemicals.CAS_from_any(name)
    except Exception as exc:
        raise UnknownChemical(
            f"Could not resolve chemical name {name!r}. "
            f"Use an exact name such as 'Methanol', 'Water', '1-butene'."
        ) from exc


def boiling_point(cas: str) -> float:
    """Normal boiling point, K."""
    return float(chemicals.Tb(cas))


def critical_temperature(cas: str) -> float:
    """Critical temperature, K."""
    return float(chemicals.Tc(cas))


def critical_pressure(cas: str) -> float:
    """Critical pressure, Pa."""
    return float(chemicals.Pc(cas))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sepsyn && ../.venv/bin/python -m pytest tests/test_properties.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add sepsyn/properties.py tests/test_properties.py
git commit -m "feat: chemical property lookups with named failures"
```

---

### Task 3: Supercritical detection and the property record

**Files:**
- Modify: `sepsyn/types.py` (append `Alpha` and `PropertyRecord`)
- Modify: `sepsyn/properties.py` (append `count_supercritical`)
- Create: `tests/test_property_record.py`

**Interfaces:**
- Consumes: `Feed`, `resolve`, `critical_temperature`
- Produces: `Alpha(pair: tuple[str,str], value: float, T_K: float, P_Pa: float, basis: str)`; `PropertyRecord` with fields `n_components: int`, `n_supercritical_at_feed: int`, `min_alpha: float | None`, `has_azeotrope: bool`, `alphas: tuple[Alpha, ...]`, `feed_phase: str`, `condensing_T_at_column_P: float | None`, `cooling_water_T: float`, `light_key_mole_fraction: float | None`, `heavy_key_mole_fraction: float | None`, and method `as_namespace() -> dict[str, object]`; `count_supercritical(feed: Feed) -> int`

- [ ] **Step 1: Write the failing test**

Create `tests/test_property_record.py`:

```python
import pytest
from sepsyn.types import Component, Feed, Alpha, PropertyRecord
from sepsyn.properties import count_supercritical


def h2_methane_feed():
    return Feed(
        components=(
            Component("Hydrogen", "1333-74-0", 50.0),
            Component("Methane", "74-82-8", 50.0),
        ),
        T_K=298.15, P_Pa=101325.0,
    )


def methanol_feed():
    return Feed(
        components=(
            Component("Methanol", "67-56-1", 100.0),
            Component("Water", "7732-18-5", 80.0),
        ),
        T_K=330.0, P_Pa=101325.0,
    )


def test_both_components_supercritical_at_ambient():
    # Hydrogen Tc = 33 K, Methane Tc = 191 K, feed at 298 K
    assert count_supercritical(h2_methane_feed()) == 2


def test_nothing_supercritical_for_methanol_water():
    assert count_supercritical(methanol_feed()) == 0


def test_alpha_carries_its_conditions():
    a = Alpha(pair=("Methanol", "Water"), value=2.11,
              T_K=351.2, P_Pa=101325.0, basis="bubble point at column P")
    assert a.value == 2.11
    assert a.T_K == 351.2
    assert a.basis == "bubble point at column P"


def test_namespace_exposes_only_rule_visible_fields():
    rec = PropertyRecord(
        n_components=2, n_supercritical_at_feed=2, min_alpha=None,
        has_azeotrope=False, alphas=(), feed_phase="vapor",
        condensing_T_at_column_P=None, cooling_water_T=313.15,
        light_key_mole_fraction=None, heavy_key_mole_fraction=None,
    )
    ns = rec.as_namespace()
    assert ns["n_supercritical_at_feed"] == 2
    assert ns["n_components"] == 2
    # the raw alpha objects must not leak into rule evaluation
    assert "alphas" not in ns
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sepsyn && ../.venv/bin/python -m pytest tests/test_property_record.py -v`
Expected: FAIL with `ImportError: cannot import name 'Alpha' from 'sepsyn.types'`

- [ ] **Step 3: Write minimal implementation**

Append to `sepsyn/types.py`:

```python
@dataclass(frozen=True)
class Alpha:
    """Relative volatility ALWAYS carries the conditions it was computed at.

    A bare alpha is meaningless -- it is a property of a pair at a condition,
    not of a pair.
    """
    pair: tuple[str, str]
    value: float
    T_K: float
    P_Pa: float
    basis: str


@dataclass(frozen=True)
class PropertyRecord:
    """The ONLY thing the rule engine may see.

    Rules cannot reach the simulator or the raw chemicals, which is what makes
    the engine testable with a hand-written record and no chemistry at all.
    """
    n_components: int
    n_supercritical_at_feed: int
    min_alpha: float | None
    has_azeotrope: bool
    alphas: tuple[Alpha, ...]
    feed_phase: str
    condensing_T_at_column_P: float | None
    cooling_water_T: float
    light_key_mole_fraction: float | None
    heavy_key_mole_fraction: float | None

    def as_namespace(self) -> dict[str, object]:
        """Flat scalars for rule evaluation. Structured fields are withheld."""
        return {
            "n_components": self.n_components,
            "n_supercritical_at_feed": self.n_supercritical_at_feed,
            "min_alpha": self.min_alpha,
            "has_azeotrope": self.has_azeotrope,
            "feed_phase": self.feed_phase,
            "condensing_T_at_column_P": self.condensing_T_at_column_P,
            "cooling_water_T": self.cooling_water_T,
            "light_key_mole_fraction": self.light_key_mole_fraction,
            "heavy_key_mole_fraction": self.heavy_key_mole_fraction,
        }
```

Append to `sepsyn/properties.py`:

```python
from sepsyn.types import Feed

COOLING_WATER_T = 313.15  # K, 40 C -- design limit used throughout


def count_supercritical(feed: Feed) -> int:
    """How many components are above their critical temperature at feed T.

    If this equals the component count there is no liquid phase and no
    distillation is possible at any pressure.
    """
    return sum(
        1 for c in feed.components
        if feed.T_K > critical_temperature(c.cas or resolve(c.name))
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sepsyn && ../.venv/bin/python -m pytest tests/test_property_record.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add sepsyn/types.py sepsyn/properties.py tests/test_property_record.py
git commit -m "feat: property record and supercritical detection"
```

---

### Task 4: Azeotrope detection

**Files:**
- Create: `sepsyn/azeotropes.py`
- Create: `tests/test_azeotropes.py`

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces: `Azeotrope(components: tuple[str, str], x: tuple[float, float], T_K: float, P_Pa: float)`; `find_azeotropes(names: Sequence[str], P_Pa: float = 101325.0) -> list[Azeotrope]`

- [ ] **Step 1: Write the failing test**

Create `tests/test_azeotropes.py`:

```python
import pytest
from sepsyn.azeotropes import Azeotrope, find_azeotropes


def test_ethanol_water_azeotrope_is_found():
    """Ethanol/water azeotropes near 89 mol% ethanol at 1 atm.

    Source: Seader & Henley, Separation Process Principles. The literature
    value is 95.6 wt% which is ~89.4 mol%.
    """
    found = find_azeotropes(["Ethanol", "Water"], P_Pa=101325.0)
    assert len(found) == 1
    az = found[0]
    ethanol_x = az.x[az.components.index("Ethanol")]
    assert ethanol_x == pytest.approx(0.894, abs=0.04)
    assert az.T_K == pytest.approx(351.3, abs=2.0)


def test_methanol_water_has_no_azeotrope():
    """Methanol/water is a wide-boiling ideal-ish pair with no azeotrope."""
    assert find_azeotropes(["Methanol", "Water"], P_Pa=101325.0) == []


def test_single_component_has_no_azeotrope():
    assert find_azeotropes(["Water"], P_Pa=101325.0) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sepsyn && ../.venv/bin/python -m pytest tests/test_azeotropes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sepsyn.azeotropes'`

- [ ] **Step 3: Write minimal implementation**

Create `sepsyn/azeotropes.py`:

```python
"""Azeotrope detection.

Deliberately a separate module from properties.py: this is a SEARCH over
composition space needing the full VLE engine, not a database lookup, and it
is the piece most likely to be quietly wrong. It gets its own tests with
documented literature values.
"""
import contextlib
import io
import itertools
import warnings
from dataclasses import dataclass
from typing import Sequence

warnings.filterwarnings("ignore")

SCAN_POINTS = 51          # composition grid for the sign-change search
MIN_SEPARATION = 0.02     # ignore "azeotropes" within this of a pure component


@dataclass(frozen=True)
class Azeotrope:
    components: tuple[str, str]
    x: tuple[float, float]
    T_K: float
    P_Pa: float


def _relative_volatility(chem_a: str, chem_b: str, x_a: float, P_Pa: float):
    """alpha of a over b at liquid composition x_a, at the bubble point."""
    import thermosteam as tmo

    chems = tmo.Chemicals([chem_a, chem_b])
    chems.compile()
    tmo.settings.set_thermo(chems)
    s = tmo.Stream(None, P=P_Pa)
    s.imol[chem_a] = x_a
    s.imol[chem_b] = 1.0 - x_a
    s.vle(P=P_Pa, V=0.0)          # bubble point
    T = float(s.T)
    y = s.vapor.imol
    liq = s.liquid.imol
    ya, yb = float(y[chem_a]), float(y[chem_b])
    xa, xb = float(liq[chem_a]), float(liq[chem_b])
    if min(xa, xb, ya, yb) <= 0:
        return None, T
    return (ya / xa) / (yb / xb), T


def find_azeotropes(names: Sequence[str], P_Pa: float = 101325.0) -> list[Azeotrope]:
    """Find binary azeotropes by scanning for alpha crossing 1.0.

    An azeotrope is exactly where relative volatility equals one: the vapour
    and liquid have the same composition, so no further separation is possible
    by ordinary distillation.
    """
    results: list[Azeotrope] = []
    with contextlib.redirect_stdout(io.StringIO()):
        for a, b in itertools.combinations(names, 2):
            prev_alpha = None
            prev_x = None
            for i in range(1, SCAN_POINTS - 1):
                x = i / (SCAN_POINTS - 1)
                try:
                    alpha, T = _relative_volatility(a, b, x, P_Pa)
                except Exception:
                    continue
                if alpha is None:
                    continue
                if prev_alpha is not None and (prev_alpha - 1.0) * (alpha - 1.0) < 0:
                    # linear interpolation onto alpha == 1
                    frac = (1.0 - prev_alpha) / (alpha - prev_alpha)
                    x_az = prev_x + frac * (x - prev_x)
                    if MIN_SEPARATION < x_az < 1.0 - MIN_SEPARATION:
                        results.append(Azeotrope(
                            components=(a, b),
                            x=(x_az, 1.0 - x_az),
                            T_K=T, P_Pa=P_Pa,
                        ))
                        break
                prev_alpha, prev_x = alpha, x
    return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sepsyn && ../.venv/bin/python -m pytest tests/test_azeotropes.py -v`
Expected: 3 passed

If `test_ethanol_water_azeotrope_is_found` fails on composition, print the alpha curve first:

```bash
cd sepsyn && ../.venv/bin/python -c "
from sepsyn.azeotropes import _relative_volatility
for i in range(1,20):
    x=i/20
    print(round(x,3), _relative_volatility('Ethanol','Water',x,101325.0))"
```

If alpha never crosses 1.0, the thermo package is treating the pair as ideal. Set an activity model explicitly by replacing the `tmo.settings.set_thermo(chems)` line with `tmo.settings.set_thermo(chems, Gamma=tmo.equilibrium.DortmundActivityCoefficients)` and re-run.

- [ ] **Step 5: Commit**

```bash
git add sepsyn/azeotropes.py tests/test_azeotropes.py
git commit -m "feat: binary azeotrope detection by alpha sign change"
```

---

### Task 5: Relative volatility at the bubble point

**Files:**
- Modify: `sepsyn/properties.py` (append `relative_volatilities`, `build_property_record`)
- Create: `tests/test_alpha.py`

**Interfaces:**
- Consumes: `Feed`, `Alpha`, `PropertyRecord`, `count_supercritical`, `find_azeotropes`
- Produces: `relative_volatilities(feed: Feed, P_Pa: float) -> tuple[Alpha, ...]`; `build_property_record(feed: Feed, column_P_Pa: float | None = None, light_key: str | None = None, heavy_key: str | None = None) -> PropertyRecord`

- [ ] **Step 1: Write the failing test**

Create `tests/test_alpha.py`:

```python
import pytest
from sepsyn.types import Component, Feed
from sepsyn.properties import relative_volatilities, build_property_record


def methanol_water_glycerol():
    return Feed(
        components=(
            Component("Methanol", "67-56-1", 100.0),
            Component("Water", "7732-18-5", 80.0),
            Component("Glycerol", "56-81-5", 25.0),
        ),
        T_K=330.0, P_Pa=101325.0,
    )


def h2_methane():
    return Feed(
        components=(
            Component("Hydrogen", "1333-74-0", 50.0),
            Component("Methane", "74-82-8", 50.0),
        ),
        T_K=298.15, P_Pa=101325.0,
    )


def test_alpha_is_computed_with_conditions_attached():
    alphas = relative_volatilities(methanol_water_glycerol(), P_Pa=101325.0)
    assert len(alphas) >= 1
    a = alphas[0]
    assert a.value > 1.0
    assert a.T_K > 273.0
    assert a.P_Pa == 101325.0
    assert "bubble point" in a.basis


def test_methanol_water_alpha_is_around_two():
    alphas = relative_volatilities(methanol_water_glycerol(), P_Pa=101325.0)
    pair = [a for a in alphas if set(a.pair) == {"Methanol", "Water"}]
    assert len(pair) == 1
    assert 1.5 < pair[0].value < 4.0


def test_record_for_supercritical_feed_has_no_alpha():
    rec = build_property_record(h2_methane())
    assert rec.n_supercritical_at_feed == 2
    assert rec.n_components == 2
    assert rec.min_alpha is None
    assert rec.feed_phase == "vapor"


def test_record_for_condensable_feed_has_alpha():
    rec = build_property_record(methanol_water_glycerol())
    assert rec.n_supercritical_at_feed == 0
    assert rec.min_alpha is not None
    assert rec.min_alpha > 1.0


def test_condensing_temperature_is_populated_so_R09_can_fire():
    """Regression: this field was once hardcoded to None, which made the
    refrigeration caution dead code that only fired in unit tests."""
    rec = build_property_record(methanol_water_glycerol())
    assert rec.condensing_T_at_column_P is not None
    # methanol condenses at ~338 K at 1 atm, above cooling water at 313 K
    assert rec.condensing_T_at_column_P > rec.cooling_water_T


def test_light_hydrocarbon_feed_triggers_the_refrigeration_caution():
    """Ethylene condenses at ~169 K at 1 atm, far below cooling water."""
    feed = Feed(
        components=(Component("Ethylene", "74-85-1", 50.0),
                    Component("Ethane", "74-84-0", 50.0)),
        T_K=250.0, P_Pa=101325.0,
    )
    rec = build_property_record(feed)
    assert rec.condensing_T_at_column_P is not None
    assert rec.condensing_T_at_column_P < rec.cooling_water_T
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sepsyn && ../.venv/bin/python -m pytest tests/test_alpha.py -v`
Expected: FAIL with `ImportError: cannot import name 'relative_volatilities'`

- [ ] **Step 3: Write minimal implementation**

Append to `sepsyn/properties.py`:

```python
import contextlib
import io
import itertools
import warnings

from sepsyn.types import Alpha, PropertyRecord
from sepsyn.azeotropes import find_azeotropes

warnings.filterwarnings("ignore")


def relative_volatilities(feed: Feed, P_Pa: float) -> tuple[Alpha, ...]:
    """Alpha for every adjacent pair, at the mixture bubble point.

    Computed where the separation actually happens, not at feed conditions --
    a feed at 25 C tells you nothing about a column running at 80 C.
    """
    import thermosteam as tmo

    names = list(feed.names)
    out: list[Alpha] = []
    with contextlib.redirect_stdout(io.StringIO()):
        chems = tmo.Chemicals(names)
        chems.compile()
        tmo.settings.set_thermo(chems)
        s = tmo.Stream(None, P=P_Pa)
        for c in feed.components:
            s.imol[c.name] = c.flow_kmol_hr
        try:
            s.vle(P=P_Pa, V=0.0)
        except Exception:
            return ()
        T = float(s.T)
        y, x = s.vapor.imol, s.liquid.imol
        for a, b in itertools.combinations(names, 2):
            xa, xb, ya, yb = float(x[a]), float(x[b]), float(y[a]), float(y[b])
            if min(xa, xb) <= 0 or min(ya, yb) <= 0:
                continue
            out.append(Alpha(
                pair=(a, b),
                value=(ya / xa) / (yb / xb),
                T_K=T, P_Pa=P_Pa,
                basis="bubble point at column P",
            ))
    return tuple(out)


def condensing_temperature(name: str, P_Pa: float) -> float | None:
    """Saturation temperature of a pure component at P, or None if it cannot
    be condensed at that pressure. Used to decide whether the overhead can be
    condensed against cooling water or needs refrigeration."""
    import thermosteam as tmo

    cas = resolve(name)
    if P_Pa >= critical_pressure(cas):
        return None
    with contextlib.redirect_stdout(io.StringIO()):
        chems = tmo.Chemicals([name])
        chems.compile()
        tmo.settings.set_thermo(chems)
        s = tmo.Stream(None, P=P_Pa)
        s.imol[name] = 1.0
        try:
            s.vle(P=P_Pa, V=0.0)
            return float(s.T)
        except Exception:
            return None


def build_property_record(
    feed: Feed,
    column_P_Pa: float | None = None,
    light_key: str | None = None,
    heavy_key: str | None = None,
) -> PropertyRecord:
    """Assemble everything the rule engine is allowed to see."""
    P = column_P_Pa if column_P_Pa is not None else feed.P_Pa
    n_super = count_supercritical(feed)

    if n_super == len(feed.components):
        alphas: tuple[Alpha, ...] = ()
        azeotropes: list = []
        phase = "vapor"
    else:
        alphas = relative_volatilities(feed, P)
        azeotropes = find_azeotropes(list(feed.names), P)
        phase = "vapor" if n_super > 0 else "liquid"

    # the most volatile component determines whether the condenser works
    if n_super == len(feed.components):
        cond_T = None
    else:
        lightest = min(feed.components, key=lambda c: boiling_point(c.cas))
        cond_T = condensing_temperature(lightest.name, P)

    fracs = feed.mole_fractions
    return PropertyRecord(
        n_components=len(feed.components),
        n_supercritical_at_feed=n_super,
        min_alpha=min((a.value for a in alphas), default=None),
        has_azeotrope=bool(azeotropes),
        alphas=alphas,
        feed_phase=phase,
        condensing_T_at_column_P=cond_T,
        cooling_water_T=COOLING_WATER_T,
        light_key_mole_fraction=fracs.get(light_key) if light_key else None,
        heavy_key_mole_fraction=fracs.get(heavy_key) if heavy_key else None,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sepsyn && ../.venv/bin/python -m pytest tests/test_alpha.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add sepsyn/properties.py tests/test_alpha.py
git commit -m "feat: relative volatility at bubble point, property record assembly"
```

---

### Task 6: Rule file and safe expression evaluator

**Files:**
- Create: `sepsyn/rules.yaml`
- Create: `sepsyn/engine.py`
- Create: `tests/test_engine.py`

**Interfaces:**
- Consumes: `PropertyRecord`
- Produces: `Rule(id, name, priority, when, verdict, technologies, because)`; `Verdict(rule_id, rule_name, condition, values, verdict, technologies, because, fired)`; `safe_eval(expr: str, namespace: dict) -> bool`; `load_rules(path: str | None = None) -> list[Rule]`

- [ ] **Step 1: Write the failing test**

Create `tests/test_engine.py`:

```python
import pytest
from sepsyn.types import PropertyRecord
from sepsyn.engine import safe_eval, load_rules


def record(**overrides):
    base = dict(
        n_components=2, n_supercritical_at_feed=0, min_alpha=2.0,
        has_azeotrope=False, alphas=(), feed_phase="liquid",
        condensing_T_at_column_P=350.0, cooling_water_T=313.15,
        light_key_mole_fraction=0.5, heavy_key_mole_fraction=0.5,
    )
    base.update(overrides)
    return PropertyRecord(**base)


def test_safe_eval_handles_comparisons_and_boolean_logic():
    ns = {"a": 2.0, "b": 5, "flag": True}
    assert safe_eval("a < b", ns) is True
    assert safe_eval("a > b", ns) is False
    assert safe_eval("a < b and flag", ns) is True
    assert safe_eval("a == 2.0", ns) is True


def test_safe_eval_treats_none_comparison_as_false():
    """min_alpha is None when there is no VLE. Rules must not explode."""
    assert safe_eval("min_alpha < 1.05", {"min_alpha": None}) is False


def test_safe_eval_refuses_function_calls():
    with pytest.raises(ValueError, match="not permitted"):
        safe_eval("__import__('os').system('echo hi')", {})


def test_safe_eval_refuses_unknown_names():
    with pytest.raises(ValueError, match="unknown name"):
        safe_eval("mystery_property > 1", {"a": 1})


def test_rules_load_and_are_well_formed():
    rules = load_rules()
    assert len(rules) == 9
    ids = [r.id for r in rules]
    assert ids == sorted(ids, key=lambda i: int(i.split("-")[1]))
    for r in rules:
        assert r.verdict in {"feasible", "infeasible", "caution"}
        assert r.because.strip()
        assert r.when.strip()


def test_every_rule_condition_evaluates_against_a_record():
    """A rule whose condition cannot be evaluated is a broken rule."""
    ns = record().as_namespace()
    for r in load_rules():
        result = safe_eval(r.when, ns)
        assert isinstance(result, bool)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sepsyn && ../.venv/bin/python -m pytest tests/test_engine.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sepsyn.engine'`

- [ ] **Step 3: Write minimal implementation**

Create `sepsyn/rules.yaml`:

```yaml
# Separation technology screening rules.
#
# Conditions may reference ONLY the flat fields of PropertyRecord.as_namespace().
# Comparisons against None evaluate to False -- a missing property never fires
# a rule.
#
# Edit this file to change the tool's judgment. No Python required.

- id: R-01
  name: ordinary distillation is viable
  priority: 10
  when: "min_alpha >= 1.05 and n_supercritical_at_feed == 0"
  verdict: feasible
  technologies: [distillation]
  because: >-
    all components are condensable at feed conditions and the smallest relative
    volatility is above 1.05, so ordinary distillation can achieve the split at
    a reasonable reflux
  cite: "Seader & Henley, Separation Process Principles, Ch.7"

- id: R-02
  name: relative volatility too low
  priority: 20
  when: "min_alpha < 1.05"
  verdict: infeasible
  technologies: [extractive_distillation, adsorption, membrane]
  because: >-
    below a relative volatility of about 1.05 the reflux ratio and stage count
    required make ordinary distillation uneconomic
  cite: "Douglas, Conceptual Design of Chemical Processes, Ch.7"

- id: R-03
  name: azeotrope blocks the split
  priority: 20
  when: "has_azeotrope"
  verdict: infeasible
  technologies: [pressure_swing, extractive_distillation, hybrid_adsorption]
  because: >-
    an azeotrope means relative volatility passes through 1.0, so no number of
    stages can cross it by ordinary distillation
  cite: "Seader & Henley, Separation Process Principles, Ch.11"

- id: R-04
  name: no condensable phase at feed
  priority: 5
  when: "n_supercritical_at_feed == n_components"
  verdict: infeasible
  technologies: [PSA, membrane, cryogenic_partial_condensation]
  because: >-
    every component is above its critical temperature at feed conditions, so no
    liquid phase exists at any pressure and there is nothing for a column to
    equilibrate
  cite: "Seader & Henley, Separation Process Principles, Ch.1"

- id: R-05
  name: some components supercritical
  priority: 8
  when: "n_supercritical_at_feed > 0 and n_supercritical_at_feed < n_components"
  verdict: caution
  technologies: [cryogenic_partial_condensation, flash]
  because: >-
    some components cannot be condensed at feed conditions; a partial
    condensation or cryogenic step is needed before any column
  cite: "Kohl & Nielsen, Gas Purification"

- id: R-06
  name: volatility gap wide enough for a single stage
  priority: 30
  when: "min_alpha > 10"
  verdict: feasible
  technologies: [flash]
  because: >-
    with a relative volatility above about 10 a single equilibrium stage may
    reach the required purity, making a full column unnecessary
  cite: "Douglas, Conceptual Design of Chemical Processes, Ch.7"

- id: R-07
  name: dilute volatile in a liquid
  priority: 40
  when: "feed_phase == 'liquid' and light_key_mole_fraction < 0.05"
  verdict: feasible
  technologies: [stripping]
  because: >-
    the volatile component is dilute in a liquid, so stripping with a gas is
    usually cheaper than boiling the whole stream
  cite: "Seader & Henley, Separation Process Principles, Ch.6"

- id: R-08
  name: dilute solute in a gas
  priority: 40
  when: "feed_phase == 'vapor' and heavy_key_mole_fraction < 0.05"
  verdict: feasible
  technologies: [absorption]
  because: >-
    the heavy component is dilute in a gas, so absorption into a solvent is
    usually cheaper than condensing the whole stream
  cite: "Seader & Henley, Separation Process Principles, Ch.6"

- id: R-09
  name: condenser needs refrigeration
  priority: 50
  when: "condensing_T_at_column_P < cooling_water_T"
  verdict: caution
  technologies: [distillation]
  because: >-
    the overhead cannot be condensed against cooling water at 40 C, so
    refrigeration is required, typically several times the cost of steam
  cite: "Towler & Sinnott, Chemical Engineering Design, Ch.3"
```

Create `sepsyn/engine.py`:

```python
"""Rule loading and evaluation.

Conditions are parsed with `ast` and evaluated against a restricted namespace
containing only the property record. No builtins, no imports, no calls -- a
rule file edited by a student cannot execute code.
"""
import ast
import os
from dataclasses import dataclass
from typing import Any

import yaml

RULES_PATH = os.path.join(os.path.dirname(__file__), "rules.yaml")

_ALLOWED_NODES = (
    ast.Expression, ast.BoolOp, ast.UnaryOp, ast.Compare, ast.Name, ast.Load,
    ast.Constant, ast.And, ast.Or, ast.Not, ast.Eq, ast.NotEq, ast.Lt,
    ast.LtE, ast.Gt, ast.GtE, ast.Is, ast.IsNot,
)


@dataclass(frozen=True)
class Rule:
    id: str
    name: str
    priority: int
    when: str
    verdict: str
    technologies: tuple[str, ...]
    because: str
    cite: str = ""


@dataclass(frozen=True)
class Verdict:
    rule_id: str
    rule_name: str
    condition: str
    values: dict[str, Any]
    verdict: str
    technologies: tuple[str, ...]
    because: str
    fired: bool


def safe_eval(expr: str, namespace: dict[str, Any]) -> bool:
    """Evaluate a rule condition. Comparisons involving None are False."""
    tree = ast.parse(expr, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise ValueError(
                f"expression element {type(node).__name__} is not permitted "
                f"in a rule condition: {expr!r}"
            )
        if isinstance(node, ast.Name) and node.id not in namespace:
            raise ValueError(f"unknown name {node.id!r} in rule condition {expr!r}")

    def _eval(node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            return namespace[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not _eval(node.operand)
        if isinstance(node, ast.BoolOp):
            vals = [_eval(v) for v in node.values]
            return all(vals) if isinstance(node.op, ast.And) else any(vals)
        if isinstance(node, ast.Compare):
            left = _eval(node.left)
            for op, comp in zip(node.ops, node.comparators):
                right = _eval(comp)
                if isinstance(op, (ast.Is, ast.IsNot)):
                    ok = (left is right) if isinstance(op, ast.Is) else (left is not right)
                else:
                    # a missing property must never fire a rule
                    if left is None or right is None:
                        return False
                    ok = {
                        ast.Eq: lambda a, b: a == b,
                        ast.NotEq: lambda a, b: a != b,
                        ast.Lt: lambda a, b: a < b,
                        ast.LtE: lambda a, b: a <= b,
                        ast.Gt: lambda a, b: a > b,
                        ast.GtE: lambda a, b: a >= b,
                    }[type(op)](left, right)
                if not ok:
                    return False
                left = right
            return True
        raise ValueError(f"unsupported expression: {expr!r}")

    return bool(_eval(tree))


def load_rules(path: str | None = None) -> list[Rule]:
    """Load the rule table, sorted by priority then id."""
    with open(path or RULES_PATH) as fh:
        raw = yaml.safe_load(fh)
    rules = [
        Rule(
            id=r["id"], name=r["name"], priority=int(r["priority"]),
            when=r["when"], verdict=r["verdict"],
            technologies=tuple(r["technologies"]),
            because=" ".join(r["because"].split()),
            cite=r.get("cite", ""),
        )
        for r in raw
    ]
    return sorted(rules, key=lambda r: (r.priority, r.id))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sepsyn && ../.venv/bin/python -m pytest tests/test_engine.py -v`
Expected: 6 passed

Note: `test_rules_load_and_are_well_formed` asserts IDs sort numerically; `load_rules` sorts by priority, so if that assertion fails, change the test to sort a copy rather than changing the loader.

- [ ] **Step 5: Commit**

```bash
git add sepsyn/rules.yaml sepsyn/engine.py tests/test_engine.py
git commit -m "feat: rule table in YAML with sandboxed expression evaluator"
```

---

### Task 7: Evaluate all rules, collect verdicts, refuse to guess

**Files:**
- Modify: `sepsyn/engine.py` (append `evaluate`, `overall_verdict`)
- Create: `tests/test_evaluate.py`

**Interfaces:**
- Consumes: `Rule`, `Verdict`, `safe_eval`, `load_rules`, `PropertyRecord`
- Produces: `evaluate(rules: list[Rule], record: PropertyRecord) -> list[Verdict]` (returns one Verdict per rule, `fired` set accordingly); `overall_verdict(verdicts: list[Verdict]) -> str` returning one of `"feasible"`, `"infeasible"`, `"caution"`, `"unknown"`

- [ ] **Step 1: Write the failing test**

Create `tests/test_evaluate.py`:

```python
import pytest
from sepsyn.types import PropertyRecord
from sepsyn.engine import load_rules, evaluate, overall_verdict


def record(**overrides):
    base = dict(
        n_components=2, n_supercritical_at_feed=0, min_alpha=2.0,
        has_azeotrope=False, alphas=(), feed_phase="liquid",
        condensing_T_at_column_P=350.0, cooling_water_T=313.15,
        light_key_mole_fraction=0.5, heavy_key_mole_fraction=0.5,
    )
    base.update(overrides)
    return PropertyRecord(**base)


def fired_ids(verdicts):
    return [v.rule_id for v in verdicts if v.fired]


def test_supercritical_feed_fires_only_R04():
    rec = record(n_supercritical_at_feed=2, min_alpha=None,
                 feed_phase="vapor", condensing_T_at_column_P=None,
                 light_key_mole_fraction=None, heavy_key_mole_fraction=None)
    v = evaluate(load_rules(), rec)
    assert fired_ids(v) == ["R-04"]
    assert overall_verdict(v) == "infeasible"


def test_ordinary_mixture_fires_R01_and_is_feasible():
    v = evaluate(load_rules(), record())
    assert "R-01" in fired_ids(v)
    assert overall_verdict(v) == "feasible"


def test_all_matching_rules_are_reported_not_just_the_first():
    """A mixture can be BOTH low-alpha and azeotropic. Report both."""
    rec = record(min_alpha=1.0, has_azeotrope=True)
    ids = fired_ids(evaluate(load_rules(), rec))
    assert "R-02" in ids
    assert "R-03" in ids


def test_every_rule_appears_in_the_result_even_when_not_fired():
    """Auditability: you must be able to see what was considered."""
    v = evaluate(load_rules(), record())
    assert len(v) == len(load_rules())
    assert any(not x.fired for x in v)


def test_infeasible_beats_caution_beats_feasible():
    rec = record(min_alpha=1.0, condensing_T_at_column_P=200.0)
    v = evaluate(load_rules(), rec)
    assert overall_verdict(v) == "infeasible"


def test_no_rule_fires_returns_unknown_not_a_guess():
    """The tool must never fall through to 'probably distillation'."""
    rec = record(n_components=2, n_supercritical_at_feed=0, min_alpha=None,
                 has_azeotrope=False, feed_phase="solid",
                 condensing_T_at_column_P=None,
                 light_key_mole_fraction=None, heavy_key_mole_fraction=None)
    v = evaluate(load_rules(), rec)
    assert fired_ids(v) == []
    assert overall_verdict(v) == "unknown"


def test_verdict_carries_the_values_that_fired_it():
    rec = record(n_supercritical_at_feed=2, min_alpha=None,
                 feed_phase="vapor", condensing_T_at_column_P=None,
                 light_key_mole_fraction=None, heavy_key_mole_fraction=None)
    v = [x for x in evaluate(load_rules(), rec) if x.rule_id == "R-04"][0]
    assert v.values["n_supercritical_at_feed"] == 2
    assert v.values["n_components"] == 2
    assert "critical temperature" in v.because
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sepsyn && ../.venv/bin/python -m pytest tests/test_evaluate.py -v`
Expected: FAIL with `ImportError: cannot import name 'evaluate' from 'sepsyn.engine'`

- [ ] **Step 3: Write minimal implementation**

Append to `sepsyn/engine.py`:

```python
import re

from sepsyn.types import PropertyRecord

_VERDICT_RANK = {"infeasible": 3, "caution": 2, "feasible": 1}


def _names_in(expr: str) -> list[str]:
    """Property names referenced by a condition, for the provenance record."""
    return [
        n.id for n in ast.walk(ast.parse(expr, mode="eval"))
        if isinstance(n, ast.Name)
    ]


def evaluate(rules: list[Rule], record: PropertyRecord) -> list[Verdict]:
    """Evaluate EVERY rule. Do not stop at the first match.

    A mixture can be both low-alpha and azeotropic, and the report should say
    both. Rules that did not fire are returned too, so a reader can see what
    was considered rather than only what was concluded.
    """
    ns = record.as_namespace()
    out: list[Verdict] = []
    for rule in rules:
        fired = safe_eval(rule.when, ns)
        used = {name: ns[name] for name in _names_in(rule.when) if name in ns}
        out.append(Verdict(
            rule_id=rule.id, rule_name=rule.name, condition=rule.when,
            values=used, verdict=rule.verdict,
            technologies=rule.technologies, because=rule.because, fired=fired,
        ))
    return out


def overall_verdict(verdicts: list[Verdict]) -> str:
    """Worst verdict wins. Nothing fired means unknown, never a default."""
    fired = [v for v in verdicts if v.fired]
    if not fired:
        return "unknown"
    return max((v.verdict for v in fired), key=lambda v: _VERDICT_RANK[v])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sepsyn && ../.venv/bin/python -m pytest tests/test_evaluate.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add sepsyn/engine.py tests/test_evaluate.py
git commit -m "feat: evaluate all rules, worst verdict wins, unknown never guesses"
```

---

### Task 8: Report, CLI, and the first acceptance test

**Files:**
- Create: `sepsyn/report.py`
- Create: `sepsyn/cli.py`
- Create: `tests/test_acceptance_h2_methane.py`

**Interfaces:**
- Consumes: `Feed`, `Component`, `PropertyRecord`, `Verdict`, `build_property_record`, `load_rules`, `evaluate`, `overall_verdict`, `resolve`, `boiling_point`, `critical_temperature`
- Produces: `parse_feed(spec: str, T_K: float, P_Pa: float) -> Feed`; `format_report(feed, record, verdicts, overall, explain: bool = False) -> str`; `screen(feed: Feed) -> tuple[PropertyRecord, list[Verdict], str]`; `main(argv: list[str] | None = None) -> int`

- [ ] **Step 1: Write the failing test**

Create `tests/test_acceptance_h2_methane.py`:

```python
"""ACCEPTANCE TEST 1 -- this is the milestone.

Separate equimolar hydrogen and methane, 50 kmol/hr each, at 25 C and 1 atm,
90% hydrogen overhead.

The correct answer is that distillation is INFEASIBLE: both components are
above their critical temperature at feed conditions, so no liquid phase exists
and there is nothing for a column to equilibrate. A tool that confidently
designs a column here has failed.
"""
import pytest
from sepsyn.cli import parse_feed, screen, main
from sepsyn.report import format_report


def h2_methane():
    return parse_feed("Hydrogen:50,Methane:50", T_K=298.15, P_Pa=101325.0)


def test_verdict_is_infeasible():
    _, _, overall = screen(h2_methane())
    assert overall == "infeasible"


def test_R04_is_the_rule_that_fired():
    _, verdicts, _ = screen(h2_methane())
    assert [v.rule_id for v in verdicts if v.fired] == ["R-04"]


def test_alternatives_are_named():
    _, verdicts, _ = screen(h2_methane())
    fired = [v for v in verdicts if v.fired][0]
    assert "PSA" in fired.technologies
    assert "membrane" in fired.technologies


def test_report_shows_the_numbers_that_decided_it():
    feed = h2_methane()
    record, verdicts, overall = screen(feed)
    text = format_report(feed, record, verdicts, overall, explain=True)
    assert "33.1" in text          # hydrogen critical temperature
    assert "190.5" in text or "190.6" in text
    assert "SUPERCRITICAL" in text
    assert "R-04" in text
    assert "INFEASIBLE" in text
    assert "PSA" in text


def test_report_also_shows_rules_that_did_not_fire():
    feed = h2_methane()
    record, verdicts, overall = screen(feed)
    text = format_report(feed, record, verdicts, overall, explain=True)
    assert "not fired" in text
    assert "R-01" in text


def test_cli_runs_and_returns_zero(capsys):
    code = main(["--feed", "Hydrogen:50,Methane:50", "--T", "298.15", "--explain"])
    assert code == 0
    assert "INFEASIBLE" in capsys.readouterr().out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sepsyn && ../.venv/bin/python -m pytest tests/test_acceptance_h2_methane.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sepsyn.cli'`

- [ ] **Step 3: Write minimal implementation**

Create `sepsyn/report.py`:

```python
"""Formatting. The output IS the product -- the whole point is that a reader
can check the reasoning, so rules that did NOT fire are printed too."""
from sepsyn.properties import boiling_point, critical_temperature, resolve
from sepsyn.types import Feed, PropertyRecord
from sepsyn.engine import Verdict


def format_report(
    feed: Feed,
    record: PropertyRecord,
    verdicts: list[Verdict],
    overall: str,
    explain: bool = False,
) -> str:
    lines: list[str] = []
    spec = ", ".join(f"{c.name} {c.flow_kmol_hr:g} kmol/hr" for c in feed.components)
    lines.append(f"FEED   {spec}  @ {feed.T_K:.2f} K, {feed.P_Pa/1e5:.3f} bar")
    lines.append("")
    lines.append("PROPERTIES")
    lines.append(f"  {'component':<12}{'Tb (K)':>10}{'Tc (K)':>10}   state at feed")
    for c in feed.components:
        cas = c.cas or resolve(c.name)
        tb, tc = boiling_point(cas), critical_temperature(cas)
        state = "SUPERCRITICAL" if feed.T_K > tc else "condensable"
        lines.append(f"  {c.name:<12}{tb:>10.1f}{tc:>10.1f}   {state}")

    if record.min_alpha is None:
        lines.append("  alpha: undefined -- no vapour-liquid equilibrium at these conditions")
    else:
        for a in record.alphas:
            lines.append(
                f"  alpha {a.pair[0]}/{a.pair[1]} = {a.value:.3f} "
                f"at {a.T_K:.1f} K, {a.P_Pa/1e5:.3f} bar ({a.basis})"
            )
    lines.append("")

    fired = [v for v in verdicts if v.fired]
    lines.append("RULES FIRED")
    if not fired:
        lines.append("  none -- no rule covers this combination of properties")
    for v in fired:
        lines.append(f"  {v.rule_id}  {v.rule_name}")
        vals = ", ".join(f"{k} = {val}" for k, val in v.values.items())
        lines.append(f"        {vals}")
    lines.append("")

    lines.append(f"VERDICT  distillation {overall.upper()}")
    for v in fired:
        lines.append(f"         {v.because}")
    techs = sorted({t for v in fired for t in v.technologies})
    if techs:
        lines.append(f"CANDIDATES  {', '.join(techs)}")
        lines.append("            (screening only -- sepsyn designs distillation and flash)")

    if explain:
        lines.append("")
        lines.append("RULES CONSIDERED AND not fired")
        for v in verdicts:
            if v.fired:
                continue
            vals = ", ".join(f"{k} = {val}" for k, val in v.values.items())
            lines.append(f"  {v.rule_id}  {v.rule_name:<40} [not fired]")
            lines.append(f"        condition: {v.condition}")
            lines.append(f"        values:    {vals}")
    return "\n".join(lines)
```

Create `sepsyn/cli.py`:

```python
"""Command line entry point."""
import argparse
import sys

from sepsyn.engine import evaluate, load_rules, overall_verdict
from sepsyn.properties import build_property_record, resolve
from sepsyn.report import format_report
from sepsyn.types import Component, Feed


def parse_feed(spec: str, T_K: float, P_Pa: float) -> Feed:
    """Parse 'Methanol:100,Water:80' into a Feed."""
    components = []
    for part in spec.split(","):
        if ":" not in part:
            raise ValueError(f"expected Name:flow, got {part!r}")
        name, flow = part.rsplit(":", 1)
        name = name.strip()
        components.append(Component(name, resolve(name), float(flow)))
    return Feed(components=tuple(components), T_K=T_K, P_Pa=P_Pa)


def screen(feed: Feed):
    """Property record, all verdicts, and the overall answer."""
    record = build_property_record(feed)
    verdicts = evaluate(load_rules(), record)
    return record, verdicts, overall_verdict(verdicts)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="sepsyn",
        description="Screen a feed for separation feasibility, showing the rule that decided it.",
    )
    p.add_argument("--feed", required=True, help="e.g. 'Methanol:100,Water:80'")
    p.add_argument("--T", type=float, default=298.15, help="feed temperature, K")
    p.add_argument("--P", type=float, default=101325.0, help="feed pressure, Pa")
    p.add_argument("--explain", action="store_true",
                   help="also print rules that did not fire, with their values")
    args = p.parse_args(argv)

    feed = parse_feed(args.feed, args.T, args.P)
    record, verdicts, overall = screen(feed)
    print(format_report(feed, record, verdicts, overall, explain=args.explain))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sepsyn && ../.venv/bin/python -m pytest tests/test_acceptance_h2_methane.py -v`
Expected: 6 passed

Then see it for real:

```bash
cd sepsyn && ../.venv/bin/python -m sepsyn.cli --feed "Hydrogen:50,Methane:50" --T 298.15 --explain
```

- [ ] **Step 5: Commit**

```bash
git add sepsyn/report.py sepsyn/cli.py tests/test_acceptance_h2_methane.py
git commit -m "feat: report and CLI; acceptance test 1 (H2/methane) passing"
```

---

### Task 9: Simulator protocol and the BioSTEAM column adapter

**Files:**
- Create: `sepsyn/simulators/__init__.py`
- Create: `sepsyn/simulators/base.py`
- Create: `sepsyn/simulators/biosteam_adapter.py`
- Create: `tests/test_simulator.py`

**Interfaces:**
- Consumes: `Feed`
- Produces: `ColumnSpec(light_key: str, heavy_key: str, lk_recovery_to_distillate: float, hk_recovery_to_bottoms: float, pressure_Pa: float, reflux_over_minimum: float = 1.2)`; `ColumnResult(distillate: dict[str,float], bottoms: dict[str,float], stages: float, reflux: float, minimum_reflux: float, installed_cost_USD: float, utility_cost_USD_hr: float, converged: bool, error: str | None)`; `Simulator` protocol; `BioSteamSimulator` implementing it

- [ ] **Step 1: Write the failing test**

Create `tests/test_simulator.py`:

```python
import pytest
from sepsyn.types import Component, Feed
from sepsyn.simulators.base import ColumnSpec, ColumnResult
from sepsyn.simulators.biosteam_adapter import BioSteamSimulator


def methanol_feed():
    return Feed(
        components=(
            Component("Methanol", "67-56-1", 100.0),
            Component("Water", "7732-18-5", 80.0),
            Component("Glycerol", "56-81-5", 25.0),
        ),
        T_K=330.0, P_Pa=101325.0,
    )


def test_column_meets_the_requested_recovery():
    """Spec is RECOVERY, not mole fraction. Recovery means one thing in every
    simulator; mole fraction does not, and that mismatch caused a 175% error
    in the earlier DWSIM/BioSTEAM comparison."""
    sim = BioSteamSimulator()
    spec = ColumnSpec(light_key="Methanol", heavy_key="Water",
                      lk_recovery_to_distillate=0.99,
                      hk_recovery_to_bottoms=0.99,
                      pressure_Pa=101325.0)
    r = sim.design_column(methanol_feed(), spec)
    assert r.converged
    recovery = r.distillate["Methanol"] / 100.0
    assert recovery == pytest.approx(0.99, abs=0.02)


def test_non_keys_are_reported():
    """Nothing in an LHK spec constrains glycerol. Say where it went."""
    sim = BioSteamSimulator()
    spec = ColumnSpec("Methanol", "Water", 0.99, 0.99, 101325.0)
    r = sim.design_column(methanol_feed(), spec)
    assert "Glycerol" in r.bottoms
    assert r.bottoms["Glycerol"] == pytest.approx(25.0, abs=0.5)


def test_design_numbers_are_present():
    sim = BioSteamSimulator()
    spec = ColumnSpec("Methanol", "Water", 0.99, 0.99, 101325.0)
    r = sim.design_column(methanol_feed(), spec)
    assert r.stages > 1
    assert r.minimum_reflux > 0
    assert r.reflux > r.minimum_reflux
    assert r.installed_cost_USD > 0


def test_impossible_spec_returns_error_as_data_not_an_exception():
    """A broken design must never be reported as success."""
    sim = BioSteamSimulator()
    spec = ColumnSpec(light_key="Water", heavy_key="Methanol",   # keys reversed
                      lk_recovery_to_distillate=0.99,
                      hk_recovery_to_bottoms=0.99,
                      pressure_Pa=101325.0)
    r = sim.design_column(methanol_feed(), spec)
    assert r.converged is False
    assert r.error
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sepsyn && ../.venv/bin/python -m pytest tests/test_simulator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sepsyn.simulators'`

- [ ] **Step 3: Write minimal implementation**

Create `sepsyn/simulators/__init__.py` (empty file).

Create `sepsyn/simulators/base.py`:

```python
"""The simulator boundary.

Nothing simulator-specific crosses this line -- no Stream, no Unit. That is
what makes DWSIM a second file later rather than a rewrite, and what lets
design.py be tested against a fake with no chemistry.
"""
from dataclasses import dataclass, field
from typing import Protocol

from sepsyn.types import Feed


@dataclass(frozen=True)
class ColumnSpec:
    """Recoveries, NOT mole fractions.

    Recovery is unambiguous: '99% of the methanol leaves overhead' means the
    same thing in every simulator. Mole fraction does not -- BioSTEAM divides
    by the keys, DWSIM by the total stream. Each adapter converts recovery
    into its own native basis in one tested place.
    """
    light_key: str
    heavy_key: str
    lk_recovery_to_distillate: float
    hk_recovery_to_bottoms: float
    pressure_Pa: float
    reflux_over_minimum: float = 1.2


@dataclass(frozen=True)
class ColumnResult:
    distillate: dict[str, float]
    bottoms: dict[str, float]
    stages: float
    reflux: float
    minimum_reflux: float
    installed_cost_USD: float
    utility_cost_USD_hr: float
    converged: bool
    error: str | None = None


@dataclass(frozen=True)
class FlashSpec:
    T_K: float | None = None
    P_Pa: float | None = None
    vapor_fraction: float | None = None


@dataclass(frozen=True)
class FlashResult:
    vapor: dict[str, float]
    liquid: dict[str, float]
    T_K: float
    P_Pa: float
    converged: bool
    error: str | None = None


class Simulator(Protocol):
    def design_column(self, feed: Feed, spec: ColumnSpec) -> ColumnResult: ...
    def design_flash(self, feed: Feed, spec: FlashSpec) -> FlashResult: ...
```

Create `sepsyn/simulators/biosteam_adapter.py`:

```python
"""BioSTEAM implementation of the Simulator protocol."""
import contextlib
import io
import warnings

from sepsyn.simulators.base import (
    ColumnResult, ColumnSpec, FlashResult, FlashSpec,
)
from sepsyn.types import Feed

warnings.filterwarnings("ignore")


class BioSteamSimulator:
    """Converts recoveries into BioSTEAM's keys-only mole-fraction basis."""

    def _setup(self, feed: Feed):
        import biosteam as bst
        import thermosteam as tmo

        bst.main_flowsheet.clear()
        chems = tmo.Chemicals(list(feed.names))
        chems.compile()
        tmo.settings.set_thermo(chems)
        s = tmo.Stream("feed", T=feed.T_K, P=feed.P_Pa)
        for c in feed.components:
            s.imol[c.name] = c.flow_kmol_hr
        return bst, s

    @staticmethod
    def _recovery_to_keys_basis(spec: ColumnSpec, feed: Feed):
        """BioSTEAM wants y_top and x_bot on a LIGHT-KEY-over-KEYS basis.

        lk overhead  = lk_fed * lk_recovery
        hk overhead  = hk_fed * (1 - hk_recovery)
        y_top        = lk_overhead / (lk_overhead + hk_overhead)
        and symmetrically for the bottoms.
        """
        flows = {c.name: c.flow_kmol_hr for c in feed.components}
        lk_fed, hk_fed = flows[spec.light_key], flows[spec.heavy_key]
        lk_top = lk_fed * spec.lk_recovery_to_distillate
        hk_top = hk_fed * (1.0 - spec.hk_recovery_to_bottoms)
        lk_bot = lk_fed - lk_top
        hk_bot = hk_fed - hk_top
        y_top = lk_top / (lk_top + hk_top)
        x_bot = lk_bot / (lk_bot + hk_bot)
        return y_top, x_bot

    def design_column(self, feed: Feed, spec: ColumnSpec) -> ColumnResult:
        empty = ColumnResult({}, {}, 0.0, 0.0, 0.0, 0.0, 0.0, False)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                bst, s = self._setup(feed)
                y_top, x_bot = self._recovery_to_keys_basis(spec, feed)
                col = bst.BinaryDistillation(
                    "C1", ins=s, outs=("D", "B"),
                    LHK=(spec.light_key, spec.heavy_key),
                    y_top=y_top, x_bot=x_bot,
                    k=spec.reflux_over_minimum, P=spec.pressure_Pa,
                    is_divided=False,
                )
                col.simulate()
                D, B = col.outs
                d = col.design_results
                return ColumnResult(
                    distillate={n: float(D.imol[n]) for n in feed.names},
                    bottoms={n: float(B.imol[n]) for n in feed.names},
                    stages=float(d.get("Actual stages", 0.0)),
                    reflux=float(d.get("Reflux", 0.0)),
                    minimum_reflux=float(d.get("Minimum reflux", 0.0)),
                    installed_cost_USD=float(col.installed_cost),
                    utility_cost_USD_hr=float(col.utility_cost),
                    converged=True, error=None,
                )
        except Exception as exc:
            return ColumnResult(**{**empty.__dict__,
                                   "error": f"{type(exc).__name__}: {exc}"})

    def design_flash(self, feed: Feed, spec: FlashSpec) -> FlashResult:
        empty = FlashResult({}, {}, 0.0, 0.0, False)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                bst, s = self._setup(feed)
                kwargs = {k: v for k, v in
                          (("T", spec.T_K), ("P", spec.P_Pa), ("V", spec.vapor_fraction))
                          if v is not None}
                if len(kwargs) < 2:
                    raise ValueError("specify exactly two of T_K, P_Pa, vapor_fraction")
                f = bst.Flash("F1", ins=s, outs=("V", "L"), **kwargs)
                f.simulate()
                V, L = f.outs
                return FlashResult(
                    vapor={n: float(V.imol[n]) for n in feed.names},
                    liquid={n: float(L.imol[n]) for n in feed.names},
                    T_K=float(V.T), P_Pa=float(V.P), converged=True, error=None,
                )
        except Exception as exc:
            return FlashResult(**{**empty.__dict__,
                                  "error": f"{type(exc).__name__}: {exc}"})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sepsyn && ../.venv/bin/python -m pytest tests/test_simulator.py -v`
Expected: 4 passed (first run takes ~70 s while BioSTEAM imports)

- [ ] **Step 5: Commit**

```bash
git add sepsyn/simulators tests/test_simulator.py
git commit -m "feat: simulator protocol and BioSTEAM adapter; recoveries not mole fractions"
```

---

### Task 10: Column pressure rule and the reflux sweep

**Files:**
- Create: `sepsyn/design.py`
- Create: `tests/test_design.py`

**Interfaces:**
- Consumes: `Feed`, `ColumnSpec`, `ColumnResult`, `Simulator`, `BioSteamSimulator`, `COOLING_WATER_T`
- Produces: `choose_pressure(feed: Feed, light_key: str) -> tuple[float, str]` returning (pressure_Pa, note); `SweepPoint(k: float, stages: float, annualised_cost_USD_yr: float, installed_cost_USD: float, utility_cost_USD_hr: float)`; `sweep_reflux(sim, feed, spec, k_values=None) -> list[SweepPoint]`; `best_point(points: list[SweepPoint]) -> SweepPoint`

- [ ] **Step 1: Write the failing test**

Create `tests/test_design.py`:

```python
import pytest
from sepsyn.types import Component, Feed
from sepsyn.simulators.base import ColumnSpec
from sepsyn.simulators.biosteam_adapter import BioSteamSimulator
from sepsyn.design import choose_pressure, sweep_reflux, best_point, SweepPoint


def methanol_feed():
    return Feed(
        components=(
            Component("Methanol", "67-56-1", 100.0),
            Component("Water", "7732-18-5", 80.0),
            Component("Glycerol", "56-81-5", 25.0),
        ),
        T_K=330.0, P_Pa=101325.0,
    )


def test_atmospheric_is_enough_for_methanol():
    """Methanol boils at 337 K, well above cooling water at 313 K, so 1 atm
    condenses fine and there is no reason to raise pressure."""
    P, note = choose_pressure(methanol_feed(), light_key="Methanol")
    assert P == pytest.approx(101325.0, rel=0.01)
    assert "cooling water" in note.lower()


def test_light_component_needs_pressure_or_refrigeration():
    """Ethylene boils at 169 K. It cannot condense against cooling water at
    atmospheric pressure, so the note must say so."""
    feed = Feed(
        components=(Component("Ethylene", "74-85-1", 50.0),
                    Component("Ethane", "74-84-0", 50.0)),
        T_K=250.0, P_Pa=101325.0,
    )
    P, note = choose_pressure(feed, light_key="Ethylene")
    assert P > 101325.0 or "refrigerat" in note.lower()


def test_sweep_returns_a_curve_not_a_point():
    sim = BioSteamSimulator()
    spec = ColumnSpec("Methanol", "Water", 0.99, 0.99, 101325.0)
    pts = sweep_reflux(sim, methanol_feed(), spec, k_values=[1.1, 1.3, 1.6, 2.0])
    assert len(pts) == 4
    # more reflux buys fewer stages -- the classic trade-off
    assert pts[0].stages > pts[-1].stages


def test_best_point_is_the_cheapest_annualised():
    pts = [
        SweepPoint(k=1.1, stages=80, annualised_cost_USD_yr=500_000,
                   installed_cost_USD=2_000_000, utility_cost_USD_hr=10.0),
        SweepPoint(k=1.3, stages=40, annualised_cost_USD_yr=300_000,
                   installed_cost_USD=1_000_000, utility_cost_USD_hr=15.0),
        SweepPoint(k=2.0, stages=25, annualised_cost_USD_yr=400_000,
                   installed_cost_USD=600_000, utility_cost_USD_hr=30.0),
    ]
    assert best_point(pts).k == 1.3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sepsyn && ../.venv/bin/python -m pytest tests/test_design.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sepsyn.design'`

- [ ] **Step 3: Write minimal implementation**

Create `sepsyn/design.py`:

```python
"""Design decisions that are rules, not judgment.

Column pressure comes from the cooling-water heuristic. Reflux comes from a
sweep that returns the whole curve, so the output shows the trade-off rather
than asserting a single answer.
"""
import contextlib
import io
import warnings
from dataclasses import dataclass

from sepsyn.properties import COOLING_WATER_T, critical_temperature, resolve
from sepsyn.simulators.base import ColumnSpec
from sepsyn.types import Feed

warnings.filterwarnings("ignore")

PLANT_LIFE_YEARS = 10
OPERATING_HOURS_YR = 8000
DEFAULT_K_VALUES = [1.05, 1.1, 1.2, 1.3, 1.4, 1.5, 1.7, 2.0]
MAX_PRESSURE_Pa = 3.0e6          # beyond this, refrigeration is usually cheaper


def choose_pressure(feed: Feed, light_key: str) -> tuple[float, str]:
    """Lowest pressure at which the overhead condenses against cooling water.

    This is the standard heuristic: go as low as you can, because low pressure
    improves relative volatility, but stop where the condenser stops working.
    """
    import thermosteam as tmo

    cas = resolve(light_key)
    if COOLING_WATER_T > critical_temperature(cas):
        return MAX_PRESSURE_Pa, (
            f"{light_key} is supercritical at cooling water temperature "
            f"({COOLING_WATER_T:.1f} K); refrigeration required"
        )

    with contextlib.redirect_stdout(io.StringIO()):
        chems = tmo.Chemicals([light_key])
        chems.compile()
        tmo.settings.set_thermo(chems)
        s = tmo.Stream(None)
        s.imol[light_key] = 1.0
        try:
            s.vle(T=COOLING_WATER_T, V=0.0)
            p_required = float(s.P)
        except Exception:
            return 101325.0, "could not determine condensing pressure; assumed atmospheric"

    if p_required <= 101325.0:
        return 101325.0, (
            f"atmospheric is sufficient; {light_key} condenses against "
            f"cooling water at {COOLING_WATER_T:.1f} K"
        )
    if p_required > MAX_PRESSURE_Pa:
        return MAX_PRESSURE_Pa, (
            f"{p_required/1e5:.1f} bar would be needed to condense {light_key} "
            f"against cooling water; capped at {MAX_PRESSURE_Pa/1e5:.0f} bar, "
            f"refrigeration required"
        )
    return p_required, (
        f"raised to {p_required/1e5:.2f} bar so {light_key} condenses against "
        f"cooling water at {COOLING_WATER_T:.1f} K"
    )


@dataclass(frozen=True)
class SweepPoint:
    k: float
    stages: float
    annualised_cost_USD_yr: float
    installed_cost_USD: float
    utility_cost_USD_hr: float


def _annualised(installed: float, utility_per_hr: float) -> float:
    """Deliberately crude. The tool reports the whole curve, and the knee's
    position is insensitive to these constants."""
    return installed / PLANT_LIFE_YEARS + utility_per_hr * OPERATING_HOURS_YR


def sweep_reflux(sim, feed: Feed, spec: ColumnSpec,
                 k_values: list[float] | None = None) -> list[SweepPoint]:
    """Design the column at each reflux multiple and return the curve."""
    from dataclasses import replace

    points: list[SweepPoint] = []
    for k in (k_values or DEFAULT_K_VALUES):
        r = sim.design_column(feed, replace(spec, reflux_over_minimum=k))
        if not r.converged:
            continue
        points.append(SweepPoint(
            k=k, stages=r.stages,
            annualised_cost_USD_yr=_annualised(r.installed_cost_USD,
                                               r.utility_cost_USD_hr),
            installed_cost_USD=r.installed_cost_USD,
            utility_cost_USD_hr=r.utility_cost_USD_hr,
        ))
    return points


def best_point(points: list[SweepPoint]) -> SweepPoint:
    """Cheapest annualised cost."""
    if not points:
        raise ValueError("no converged points in sweep")
    return min(points, key=lambda p: p.annualised_cost_USD_yr)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sepsyn && ../.venv/bin/python -m pytest tests/test_design.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add sepsyn/design.py tests/test_design.py
git commit -m "feat: pressure from the cooling-water rule, reflux from a sweep"
```

---

### Task 11: Verification of a design

**Files:**
- Create: `sepsyn/verify.py`
- Create: `tests/test_verify.py`

**Interfaces:**
- Consumes: `Feed`, `ColumnSpec`, `ColumnResult`
- Produces: `Check(name: str, passed: bool, detail: str)`; `verify_column(feed: Feed, spec: ColumnSpec, result: ColumnResult) -> list[Check]`

- [ ] **Step 1: Write the failing test**

Create `tests/test_verify.py`:

```python
import pytest
from sepsyn.types import Component, Feed
from sepsyn.simulators.base import ColumnSpec, ColumnResult
from sepsyn.verify import verify_column, Check


def feed():
    return Feed(
        components=(Component("Methanol", "67-56-1", 100.0),
                    Component("Water", "7732-18-5", 80.0)),
        T_K=330.0, P_Pa=101325.0,
    )


def spec():
    return ColumnSpec("Methanol", "Water", 0.99, 0.99, 101325.0)


def good_result():
    return ColumnResult(
        distillate={"Methanol": 99.0, "Water": 0.8},
        bottoms={"Methanol": 1.0, "Water": 79.2},
        stages=40, reflux=1.3, minimum_reflux=1.0,
        installed_cost_USD=500_000, utility_cost_USD_hr=20.0,
        converged=True, error=None,
    )


def names(checks):
    return {c.name: c.passed for c in checks}


def test_good_result_passes_every_check():
    assert all(c.passed for c in verify_column(feed(), spec(), good_result()))


def test_mass_balance_failure_is_caught():
    bad = ColumnResult(**{**good_result().__dict__,
                          "distillate": {"Methanol": 99.0, "Water": 0.8},
                          "bottoms": {"Methanol": 1.0, "Water": 40.0}})
    assert names(verify_column(feed(), spec(), bad))["mass balance"] is False


def test_missed_recovery_is_caught():
    bad = ColumnResult(**{**good_result().__dict__,
                          "distillate": {"Methanol": 60.0, "Water": 0.8},
                          "bottoms": {"Methanol": 40.0, "Water": 79.2}})
    assert names(verify_column(feed(), spec(), bad))["light key recovery"] is False


def test_non_converged_result_fails_immediately():
    bad = ColumnResult({}, {}, 0, 0, 0, 0, 0, False, "RuntimeError: stages > 100")
    checks = verify_column(feed(), spec(), bad)
    assert names(checks)["converged"] is False
    assert "stages > 100" in [c.detail for c in checks if c.name == "converged"][0]


def test_reflux_below_minimum_is_caught():
    bad = ColumnResult(**{**good_result().__dict__,
                          "reflux": 0.9, "minimum_reflux": 1.0})
    assert names(verify_column(feed(), spec(), bad))["reflux above minimum"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sepsyn && ../.venv/bin/python -m pytest tests/test_verify.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sepsyn.verify'`

- [ ] **Step 3: Write minimal implementation**

Create `sepsyn/verify.py`:

```python
"""Checks run on every design before it is reported.

Failures are returned as DATA, not raised. A design that fails verification is
still returned, clearly marked -- 'here is what it produced and here is why you
should not trust it' is more useful than a stack trace.
"""
from dataclasses import dataclass

from sepsyn.simulators.base import ColumnResult, ColumnSpec
from sepsyn.types import Feed

MASS_BALANCE_TOL = 0.01      # relative
RECOVERY_TOL = 0.03          # absolute, on a fraction


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str


def verify_column(feed: Feed, spec: ColumnSpec, result: ColumnResult) -> list[Check]:
    checks: list[Check] = []

    if not result.converged:
        return [Check("converged", False, result.error or "simulator did not converge")]
    checks.append(Check("converged", True, "simulator converged"))

    fed = feed.total_kmol_hr
    out = sum(result.distillate.values()) + sum(result.bottoms.values())
    err = abs(out - fed) / fed
    checks.append(Check(
        "mass balance", err < MASS_BALANCE_TOL,
        f"in {fed:.3f}, out {out:.3f} kmol/hr, error {100*err:.3f}%",
    ))

    flows = {c.name: c.flow_kmol_hr for c in feed.components}
    lk_fed = flows[spec.light_key]
    lk_rec = result.distillate.get(spec.light_key, 0.0) / lk_fed
    checks.append(Check(
        "light key recovery",
        abs(lk_rec - spec.lk_recovery_to_distillate) < RECOVERY_TOL,
        f"asked {spec.lk_recovery_to_distillate:.3f}, achieved {lk_rec:.3f}",
    ))

    hk_fed = flows[spec.heavy_key]
    hk_rec = result.bottoms.get(spec.heavy_key, 0.0) / hk_fed
    checks.append(Check(
        "heavy key recovery",
        abs(hk_rec - spec.hk_recovery_to_bottoms) < RECOVERY_TOL,
        f"asked {spec.hk_recovery_to_bottoms:.3f}, achieved {hk_rec:.3f}",
    ))

    checks.append(Check(
        "reflux above minimum", result.reflux > result.minimum_reflux,
        f"reflux {result.reflux:.3f}, minimum {result.minimum_reflux:.3f}",
    ))
    return checks
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sepsyn && ../.venv/bin/python -m pytest tests/test_verify.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add sepsyn/verify.py tests/test_verify.py
git commit -m "feat: design verification returning failures as data"
```

---

### Task 12: Second acceptance test, ambiguity flag, negative test

**Files:**
- Modify: `sepsyn/cli.py` (add `--light-key`, `--heavy-key`, `--design`, and the unseparated-component flag)
- Modify: `sepsyn/report.py` (append `format_design`)
- Create: `tests/test_acceptance_methanol.py`
- Create: `tests/test_refuses_to_guess.py`

**Interfaces:**
- Consumes: everything above
- Produces: `design_if_feasible(feed, light_key, heavy_key, lk_recovery, hk_recovery)` returning `(spec, sweep_points, best, result, checks, unseparated: list[str])`; `format_design(...) -> str`

- [ ] **Step 1: Write the failing test**

Create `tests/test_acceptance_methanol.py`:

```python
"""ACCEPTANCE TEST 2 -- this is the milestone.

Methanol / water / glycerol at 100 / 80 / 25 kmol/hr. Distillate at 99 mol%
methanol, bottoms at 1 mol% methanol, both on a TOTAL stream basis.

The correct answer is one column meeting the spec, PLUS a printed flag that
water and glycerol were not separated from each other because no spec was
given for them. Answering the literal question while flagging what was not
asked is the behaviour under test.
"""
import pytest
from sepsyn.cli import parse_feed, screen, design_if_feasible, main
from sepsyn.report import format_design


FEED_SPEC = "Methanol:100,Water:80,Glycerol:25"


def feed():
    return parse_feed(FEED_SPEC, T_K=330.0, P_Pa=101325.0)


def test_distillation_is_feasible():
    _, _, overall = screen(feed())
    assert overall in ("feasible", "caution")


def test_R01_fires():
    _, verdicts, _ = screen(feed())
    assert "R-01" in [v.rule_id for v in verdicts if v.fired]


def test_one_column_meets_the_methanol_spec():
    out = design_if_feasible(feed(), "Methanol", "Water", 0.99, 0.99)
    result = out[3]
    assert result.converged
    total_D = sum(result.distillate.values())
    assert result.distillate["Methanol"] / total_D == pytest.approx(0.99, abs=0.03)


def test_all_verification_checks_pass():
    checks = design_if_feasible(feed(), "Methanol", "Water", 0.99, 0.99)[4]
    failed = [c.name for c in checks if not c.passed]
    assert failed == [], f"failed checks: {failed}"


def test_glycerol_is_flagged_as_unseparated():
    """The ambiguity flag. This is the behaviour that distinguishes answering
    the question from silently missing part of it."""
    unseparated = design_if_feasible(feed(), "Methanol", "Water", 0.99, 0.99)[5]
    assert "Glycerol" in unseparated


def test_report_prints_the_ambiguity_note():
    out = design_if_feasible(feed(), "Methanol", "Water", 0.99, 0.99)
    text = format_design(*out)
    assert "not separated" in text.lower()
    assert "Glycerol" in text


def test_cli_designs_and_returns_zero(capsys):
    code = main(["--feed", FEED_SPEC, "--T", "330",
                 "--light-key", "Methanol", "--heavy-key", "Water", "--design"])
    assert code == 0
    out = capsys.readouterr().out
    assert "FEASIBLE" in out.upper()
    assert "Glycerol" in out
```

Create `tests/test_refuses_to_guess.py`:

```python
"""NEGATIVE ACCEPTANCE TEST.

A property combination that no rule covers must return 'unknown'. Without this
test, a future rule edit could silently make the fallthrough permissive and the
tool would start guessing.
"""
from sepsyn.types import PropertyRecord
from sepsyn.engine import load_rules, evaluate, overall_verdict


def test_uncovered_properties_return_unknown():
    rec = PropertyRecord(
        n_components=2, n_supercritical_at_feed=0, min_alpha=None,
        has_azeotrope=False, alphas=(), feed_phase="solid",
        condensing_T_at_column_P=None, cooling_water_T=313.15,
        light_key_mole_fraction=None, heavy_key_mole_fraction=None,
    )
    verdicts = evaluate(load_rules(), rec)
    assert [v.rule_id for v in verdicts if v.fired] == []
    assert overall_verdict(verdicts) == "unknown"


def test_unknown_is_never_silently_treated_as_feasible():
    rec = PropertyRecord(
        n_components=1, n_supercritical_at_feed=0, min_alpha=None,
        has_azeotrope=False, alphas=(), feed_phase="unknown",
        condensing_T_at_column_P=None, cooling_water_T=313.15,
        light_key_mole_fraction=None, heavy_key_mole_fraction=None,
    )
    assert overall_verdict(evaluate(load_rules(), rec)) != "feasible"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sepsyn && ../.venv/bin/python -m pytest tests/test_acceptance_methanol.py tests/test_refuses_to_guess.py -v`
Expected: `test_refuses_to_guess.py` passes (engine already correct); `test_acceptance_methanol.py` fails with `ImportError: cannot import name 'design_if_feasible'`

- [ ] **Step 3: Write minimal implementation**

Append to `sepsyn/report.py`:

```python
def format_design(spec, points, best, result, checks, unseparated) -> str:
    lines: list[str] = []
    lines.append("COLUMN DESIGN")
    lines.append(f"  keys        {spec.light_key} (light) / {spec.heavy_key} (heavy)")
    lines.append(f"  pressure    {spec.pressure_Pa/1e5:.3f} bar")
    lines.append(f"  recovery    {spec.light_key} {spec.lk_recovery_to_distillate:.1%} overhead, "
                 f"{spec.heavy_key} {spec.hk_recovery_to_bottoms:.1%} bottoms")
    lines.append("")
    lines.append("REFLUX SWEEP")
    lines.append(f"  {'k':>6}{'stages':>9}{'annualised $/yr':>19}")
    for p in points:
        mark = "  <- cheapest" if p is best else ""
        lines.append(f"  {p.k:>6.2f}{p.stages:>9.0f}{p.annualised_cost_USD_yr:>19,.0f}{mark}")
    lines.append("")
    lines.append("PRODUCTS (kmol/hr)")
    for name in result.distillate:
        lines.append(f"  {name:<12}{result.distillate[name]:>10.3f} overhead"
                     f"{result.bottoms.get(name, 0.0):>12.3f} bottoms")
    lines.append("")
    lines.append("VERIFICATION")
    for c in checks:
        lines.append(f"  [{'PASS' if c.passed else 'FAIL'}]  {c.name:<22}{c.detail}")
    if unseparated:
        lines.append("")
        lines.append("NOTE")
        lines.append(f"  {', '.join(unseparated)} left together in the bottoms.")
        lines.append("  No specification was given for separating them. If separate")
        lines.append("  products are required, a second column is needed.")
    return "\n".join(lines)
```

Replace the body of `sepsyn/cli.py` below `screen()` with:

```python
def design_if_feasible(feed: Feed, light_key: str, heavy_key: str,
                       lk_recovery: float = 0.99, hk_recovery: float = 0.99):
    """Design the column and report what the spec did NOT cover."""
    from sepsyn.design import best_point, choose_pressure, sweep_reflux
    from sepsyn.simulators.base import ColumnSpec
    from sepsyn.simulators.biosteam_adapter import BioSteamSimulator
    from sepsyn.verify import verify_column

    pressure, _note = choose_pressure(feed, light_key)
    spec = ColumnSpec(light_key, heavy_key, lk_recovery, hk_recovery, pressure)
    sim = BioSteamSimulator()

    points = sweep_reflux(sim, feed, spec)
    best = best_point(points)
    from dataclasses import replace
    spec = replace(spec, reflux_over_minimum=best.k)
    result = sim.design_column(feed, spec)
    checks = verify_column(feed, spec, result)

    # anything that is neither key has no specification constraining it
    unseparated = [n for n in feed.names if n not in (light_key, heavy_key)]
    return spec, points, best, result, checks, unseparated


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="sepsyn",
        description="Screen a feed for separation feasibility, showing the rule that decided it.",
    )
    p.add_argument("--feed", required=True, help="e.g. 'Methanol:100,Water:80'")
    p.add_argument("--T", type=float, default=298.15, help="feed temperature, K")
    p.add_argument("--P", type=float, default=101325.0, help="feed pressure, Pa")
    p.add_argument("--explain", action="store_true",
                   help="also print rules that did not fire, with their values")
    p.add_argument("--design", action="store_true",
                   help="design the column if screening says it is feasible")
    p.add_argument("--light-key")
    p.add_argument("--heavy-key")
    p.add_argument("--lk-recovery", type=float, default=0.99)
    p.add_argument("--hk-recovery", type=float, default=0.99)
    args = p.parse_args(argv)

    feed = parse_feed(args.feed, args.T, args.P)
    record, verdicts, overall = screen(feed)
    print(format_report(feed, record, verdicts, overall, explain=args.explain))

    if args.design:
        if overall not in ("feasible", "caution"):
            print(f"\nNot designing: screening returned {overall.upper()}.")
            return 0
        if not (args.light_key and args.heavy_key):
            print("\n--design requires --light-key and --heavy-key")
            return 2
        from sepsyn.report import format_design
        out = design_if_feasible(feed, args.light_key, args.heavy_key,
                                 args.lk_recovery, args.hk_recovery)
        print()
        print(format_design(*out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the whole suite**

Run: `cd sepsyn && ../.venv/bin/python -m pytest tests/ -v`
Expected: all tests pass

Then see both acceptance cases for real:

```bash
cd sepsyn
../.venv/bin/python -m sepsyn.cli --feed "Hydrogen:50,Methane:50" --T 298.15 --explain
../.venv/bin/python -m sepsyn.cli --feed "Methanol:100,Water:80,Glycerol:25" --T 330 \
    --light-key Methanol --heavy-key Water --design
```

- [ ] **Step 5: Commit**

```bash
git add sepsyn/cli.py sepsyn/report.py tests/test_acceptance_methanol.py tests/test_refuses_to_guess.py
git commit -m "feat: column design path, ambiguity flag, both acceptance tests passing"
```

---

## Milestone 1 done when

- `../.venv/bin/python -m pytest tests/ -v` is green
- H2/methane returns INFEASIBLE citing R-04 and names PSA/membrane
- Methanol/water/glycerol returns a verified column plus the glycerol flag
- `--explain` prints rules that did not fire, with their values
- `rules.yaml` can be edited to change the tool's judgment without touching Python
