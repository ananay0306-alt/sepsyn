# M2: Configuration Equivalence and Cross-Validation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Measure how far sepsyn's shortcut designs sit from a rigorous DWSIM solution — but only after proving the two columns being compared are the same column.

**Architecture:** A `DwsimSimulator` speaks to `dwsim-mcp` over a subprocess and builds a fresh flowsheet on every call. Before any gap is reported, a configuration-equivalence harness asserts three conventions that the 09-09 probe found unpinned. A gap that cannot be attributed is reported as unattributed rather than named.

**Tech Stack:** Python 3.11+, `dwsim-mcp` (C#/mono JSON-RPC over MCP), BioSTEAM 2.53.11, pytest 9.1.1. Recorded fixtures as JSON; live path behind an opt-in marker.

**Spec:** `docs/specs/2026-09-09-milestone-2-configuration-equivalence.md`

## Global Constraints

- **Nothing may report a gap until all three conventions of spec §5 are pinned by tests.** A gap reported before then is uninterpretable, which is worse than no gap.
- **The adapter builds a fresh flowsheet per run.** Never reconfigure, never reconnect, never disconnect. The 09-09 probe mutated one and got a silently doubled feed with entirely plausible numbers.
- **Every comparison asserts a mass balance**, total in equals total out, for the reason above.
- **Stages handed to DWSIM are always THEORETICAL.** BioSTEAM's `Actual stages` must never reach the adapter. 28 against 20 caused outright non-convergence.
- **Products are imposed by recovery specs, so product agreement proves nothing.** Only reflux, duties and temperatures carry information.
- Live DWSIM solves never run in the default suite. A 300 s timeout was already observed. Live tests sit behind `@pytest.mark.dwsim_live`.
- Property package mismatch is a known unattributed contributor to every number and must be named in every reported gap.
- Run the full suite before every commit. 355 tests pass at the time of writing.

---

### Task 1: A recorded DWSIM run, and the fixture format

**Files:**
- Create: `sepsyn/simulators/dwsim_fixtures.py`
- Create: `tests/fixtures/dwsim/benzene_toluene_20stage.json`
- Test: `tests/test_dwsim_fixtures.py`

**Interfaces:**
- Consumes: nothing. Pure data handling, no MCP, no BioSTEAM.
- Produces:
  - `DwsimRun(feed_mol_s: dict[str, float], T_K: float, P_Pa: float, stages: int, feed_stage: int, condenser_spec: dict, reboiler_spec: dict, property_package: str, solver: str, converged: bool, errors: tuple[str, ...], distillate_mol_s: dict[str, float], bottoms_mol_s: dict[str, float], condenser_duty_kW: float | None, reboiler_duty_kW: float | None, distillate_T_K: float | None, bottoms_T_K: float | None)`
  - `load_fixture(path: str) -> DwsimRun`
  - `save_fixture(path: str, run: DwsimRun) -> None`
  - `FixtureMismatch(ValueError)`

**Why the fixture carries the whole configuration:** a recorded result that does not record what it was configured with cannot be checked for equivalence later, which is the entire point of the milestone.

- [ ] **Step 1: Write the failing test**

```python
"""Recorded DWSIM runs.

A fixture records the CONFIGURATION as well as the result. A recorded number
whose configuration is unknown cannot be checked for equivalence, and checking
equivalence is what this milestone is for.
"""
import json

import pytest

from sepsyn.simulators.dwsim_fixtures import (
    DwsimRun, FixtureMismatch, load_fixture, save_fixture)


def a_run(**over):
    base = dict(
        feed_mol_s={"Benzene": 16.6667, "Toluene": 11.1111},
        T_K=298.15, P_Pa=101325.0,
        stages=20, feed_stage=10,
        condenser_spec={"type": "Component Recovery", "compound": "Benzene",
                        "value": 99.0},
        reboiler_spec={"type": "Component Recovery", "compound": "Toluene",
                       "value": 99.0},
        property_package="Peng-Robinson (PR)",
        solver="Napthali-Sandholm (Simultaneous Correction)",
        converged=True, errors=(),
        distillate_mol_s={"Benzene": 16.5, "Toluene": 0.111},
        bottoms_mol_s={"Benzene": 0.1667, "Toluene": 11.0},
        condenser_duty_kW=1083.4, reboiler_duty_kW=1447.1,
        distillate_T_K=353.4, bottoms_T_K=383.3,
    )
    base.update(over)
    return DwsimRun(**base)


def test_a_run_round_trips_through_a_file(tmp_path):
    path = tmp_path / "r.json"
    original = a_run()
    save_fixture(str(path), original)
    assert load_fixture(str(path)) == original


def test_the_fixture_records_the_CONFIGURATION_not_only_the_result(tmp_path):
    """The whole point. A recorded duty whose stage count is unknown cannot be
    compared against anything."""
    path = tmp_path / "r.json"
    save_fixture(str(path), a_run())
    data = json.loads(path.read_text())
    for key in ("stages", "feed_stage", "property_package", "solver",
                "condenser_spec", "reboiler_spec", "P_Pa", "T_K"):
        assert key in data, f"{key} must be recorded"


def test_a_non_converged_run_is_recordable(tmp_path):
    """A DWSIM failure is data. The 09-09 probe produced two, and a harness
    that can only record successes cannot record what it learned."""
    path = tmp_path / "r.json"
    run = a_run(converged=False, errors=("DCErrorStillHigh",),
                condenser_duty_kW=None, reboiler_duty_kW=None,
                distillate_mol_s={}, bottoms_mol_s={})
    save_fixture(str(path), run)
    back = load_fixture(str(path))
    assert back.converged is False
    assert back.errors == ("DCErrorStillHigh",)


def test_a_fixture_missing_a_configuration_field_is_refused(tmp_path):
    path = tmp_path / "bad.json"
    data = json.loads(json.dumps({
        "feed_mol_s": {"Benzene": 1.0}, "T_K": 298.15, "P_Pa": 101325.0,
        "converged": True, "errors": [],
        "distillate_mol_s": {}, "bottoms_mol_s": {},
    }))
    path.write_text(json.dumps(data))
    with pytest.raises(FixtureMismatch, match="stages"):
        load_fixture(str(path))


def test_mass_balance_is_checkable_from_a_fixture():
    """Finding 4 of the probe: a mutated flowsheet produced a doubled feed with
    plausible numbers, and only a mass balance caught it. The fixture must
    carry enough to re-check that."""
    run = a_run()
    fed = sum(run.feed_mol_s.values())
    out = sum(run.distillate_mol_s.values()) + sum(run.bottoms_mol_s.values())
    assert out == pytest.approx(fed, rel=1e-3)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/projects/process_simulation/sepsyn && ../.venv/bin/python -m pytest tests/test_dwsim_fixtures.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'sepsyn.simulators.dwsim_fixtures'`

- [ ] **Step 3: Write minimal implementation**

Create `sepsyn/simulators/dwsim_fixtures.py`:

```python
"""Recorded DWSIM runs, and the configuration that produced them.

A fixture records what the column was CONFIGURED with, not only what it
returned. The 09-09 probe measured an 11x condenser duty gap that could not be
attributed, because the feed-stage convention was unknown; a recorded number
whose configuration is unknown has exactly that problem permanently.

Failures are recordable too. The probe produced a DCErrorStillHigh and a
timeout, and both are findings.
"""
import json
from dataclasses import asdict, dataclass, fields

REQUIRED = (
    "feed_mol_s", "T_K", "P_Pa", "stages", "feed_stage",
    "condenser_spec", "reboiler_spec", "property_package", "solver",
)


class FixtureMismatch(ValueError):
    """A fixture that cannot be interpreted, usually because it records a
    result without the configuration that produced it."""


@dataclass(frozen=True)
class DwsimRun:
    feed_mol_s: dict[str, float]
    T_K: float
    P_Pa: float
    stages: int
    feed_stage: int
    condenser_spec: dict
    reboiler_spec: dict
    property_package: str
    solver: str
    converged: bool
    errors: tuple[str, ...]
    distillate_mol_s: dict[str, float]
    bottoms_mol_s: dict[str, float]
    condenser_duty_kW: float | None = None
    reboiler_duty_kW: float | None = None
    distillate_T_K: float | None = None
    bottoms_T_K: float | None = None


def save_fixture(path: str, run: DwsimRun) -> None:
    data = asdict(run)
    data["errors"] = list(run.errors)
    with open(path, "w") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.write("\n")


def load_fixture(path: str) -> DwsimRun:
    with open(path) as fh:
        data = json.load(fh)
    missing = [k for k in REQUIRED if k not in data]
    if missing:
        raise FixtureMismatch(
            f"{path} records a result without its configuration; missing "
            f"{', '.join(missing)}. A recorded number whose configuration is "
            f"unknown cannot be compared against anything."
        )
    data["errors"] = tuple(data.get("errors", ()))
    known = {f.name for f in fields(DwsimRun)}
    return DwsimRun(**{k: v for k, v in data.items() if k in known})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `../.venv/bin/python -m pytest tests/test_dwsim_fixtures.py -q`
Expected: PASS, 5 passed

- [ ] **Step 5: Run the full suite**

Run: `../.venv/bin/python -m pytest -q`
Expected: PASS, 360 passed

- [ ] **Step 6: Commit**

```bash
git add sepsyn/simulators/dwsim_fixtures.py tests/test_dwsim_fixtures.py
git commit -m "feat: DWSIM run fixtures that record configuration, not only results

A fixture records what the column was configured with. The 09-09 probe measured
an 11x condenser duty gap that could not be attributed because the feed-stage
convention was unknown; a recorded number whose configuration is unknown has
that problem permanently.

A fixture missing configuration is refused at load rather than silently
compared. Failures are recordable: the probe produced a DCErrorStillHigh and a
timeout, and both are findings.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Hio3TrGFNZt6VaANMaRCqZ"
```

---

### Task 2: The equivalence assertions

**Files:**
- Create: `sepsyn/simulators/equivalence.py`
- Test: `tests/test_configuration_equivalence.py`

**Interfaces:**
- Consumes: `DwsimRun` from Task 1; `ColumnResult`, `ColumnSpec` from `sepsyn.simulators.base`.
- Produces:
  - `Assertion(name: str, holds: bool | None, detail: str)` — `holds is None` means the convention could not be checked, which is distinct from failing.
  - `check_equivalence(spec: ColumnSpec, sepsyn_result: ColumnResult, sepsyn_theoretical_stages: int, sepsyn_feed_stage: int, dwsim: DwsimRun) -> tuple[Assertion, ...]`
  - `can_report_gap(assertions) -> bool`
  - `UNATTRIBUTED = ("property package differs: BioSTEAM defaults against DWSIM Peng-Robinson",)`

- [ ] **Step 1: Write the failing test**

```python
"""Are these two columns the same column?

Nothing may report a gap until this says yes. The 09-09 probe measured an 11x
condenser duty gap and it could not be attributed, because three conventions
were unpinned. Naming it as shortcut error would have repeated the 08-27
mistake, where a 58 percent and a 43 percent disagreement both turned out to be
bookkeeping.
"""
import pytest

from sepsyn.simulators.base import ColumnResult, ColumnSpec
from sepsyn.simulators.dwsim_fixtures import DwsimRun
from sepsyn.simulators.equivalence import (
    UNATTRIBUTED, can_report_gap, check_equivalence)

SPEC = ColumnSpec("Benzene", "Toluene", 0.99, 0.99, 101325.0)


def sepsyn_result(**over):
    base = dict(
        distillate={"Benzene": 59.4, "Toluene": 0.4},
        bottoms={"Benzene": 0.6, "Toluene": 39.6},
        stages=28.0, reflux=1.5, minimum_reflux=1.25,
        installed_cost_USD=1e6, utility_cost_USD_hr=10.0, converged=True,
        condenser_duty_kW=1083.4, reboiler_duty_kW=1447.1,
        distillate_T_K=353.4, bottoms_T_K=383.3,
    )
    base.update(over)
    return ColumnResult(**base)


def dwsim_run(**over):
    base = dict(
        feed_mol_s={"Benzene": 16.6667, "Toluene": 11.1111},
        T_K=298.15, P_Pa=101325.0, stages=20, feed_stage=10,
        condenser_spec={"type": "Component Recovery", "compound": "Benzene",
                        "value": 99.0},
        reboiler_spec={"type": "Component Recovery", "compound": "Toluene",
                       "value": 99.0},
        property_package="Peng-Robinson (PR)", solver="NS",
        converged=True, errors=(),
        distillate_mol_s={"Benzene": 16.5, "Toluene": 0.111},
        bottoms_mol_s={"Benzene": 0.1667, "Toluene": 11.0},
        condenser_duty_kW=1090.0, reboiler_duty_kW=1455.0,
        distillate_T_K=353.6, bottoms_T_K=383.5,
    )
    base.update(over)
    return DwsimRun(**base)


def by_name(assertions):
    return {a.name: a for a in assertions}


def test_matching_configuration_passes_every_assertion():
    a = check_equivalence(SPEC, sepsyn_result(), 20, 10, dwsim_run())
    assert all(x.holds for x in a)
    assert can_report_gap(a) is True


def test_an_ACTUAL_stage_count_reaching_dwsim_is_caught():
    """The trap that produced DCErrorStillHigh in the probe. BioSTEAM reports
    28 actual and 20 theoretical; handing 28 to DWSIM is a different column."""
    a = by_name(check_equivalence(SPEC, sepsyn_result(), 20, 10,
                                  dwsim_run(stages=28)))
    assert a["stage count"].holds is False
    assert "28" in a["stage count"].detail and "20" in a["stage count"].detail


def test_a_feed_stage_mismatch_is_caught():
    """The convention that flipped convergence in the probe: stage 14 solved in
    seconds, stage 6 timed out."""
    a = by_name(check_equivalence(SPEC, sepsyn_result(), 20, 6,
                                  dwsim_run(feed_stage=14)))
    assert a["feed stage"].holds is False


def test_a_pressure_mismatch_is_caught():
    a = by_name(check_equivalence(SPEC, sepsyn_result(), 20, 10,
                                  dwsim_run(P_Pa=5e5)))
    assert a["pressure"].holds is False


def test_a_recovery_spec_mismatch_is_caught():
    a = by_name(check_equivalence(
        SPEC, sepsyn_result(), 20, 10,
        dwsim_run(condenser_spec={"type": "Reflux Ratio", "value": 1.5})))
    assert a["specification basis"].holds is False


def test_the_mass_balance_assertion_catches_a_DOUBLED_feed():
    """Probe finding 4, exactly. A mutated flowsheet produced 55.55 mol/s of
    product from a 27.78 mol/s feed, with plausible compositions and
    temperatures. Only a mass balance caught it."""
    doubled = dwsim_run(
        distillate_mol_s={"Benzene": 33.0, "Toluene": 0.222},
        bottoms_mol_s={"Benzene": 0.333, "Toluene": 22.0})
    a = by_name(check_equivalence(SPEC, sepsyn_result(), 20, 10, doubled))
    assert a["mass balance"].holds is False
    assert "2" in a["mass balance"].detail


def test_a_gap_may_NOT_be_reported_when_an_assertion_fails():
    a = check_equivalence(SPEC, sepsyn_result(), 20, 10, dwsim_run(stages=28))
    assert can_report_gap(a) is False


def test_a_gap_may_NOT_be_reported_when_an_assertion_could_not_be_checked():
    """Unknown is not the same as satisfied. A convention that could not be
    checked leaves the gap unattributable exactly as a failing one does."""
    a = check_equivalence(SPEC, sepsyn_result(), 20, None, dwsim_run())
    assert by_name(a)["feed stage"].holds is None
    assert can_report_gap(a) is False


def test_a_non_converged_dwsim_run_blocks_the_gap():
    a = check_equivalence(SPEC, sepsyn_result(), 20, 10,
                          dwsim_run(converged=False,
                                    errors=("DCErrorStillHigh",)))
    assert can_report_gap(a) is False


def test_the_unattributed_contributors_are_always_named():
    """The property packages differ and that is deferred, not solved. Every
    reported gap must say so rather than implying the difference is all
    shortcut error."""
    assert UNATTRIBUTED
    assert any("property package" in u for u in UNATTRIBUTED)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../.venv/bin/python -m pytest tests/test_configuration_equivalence.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'sepsyn.simulators.equivalence'`

- [ ] **Step 3: Write minimal implementation**

Create `sepsyn/simulators/equivalence.py`:

```python
"""Are these two columns the same column?

Nothing may report a gap until this says yes.

The 09-09 probe measured an 11x condenser duty gap between sepsyn and a
rigorous DWSIM column and it could not be attributed, because three
configuration conventions were unpinned. Naming it shortcut error would have
repeated the 08-27 mistake, where a 58 percent condenser and a 43 percent stage
disagreement both turned out to be bookkeeping rather than physics.

An assertion has three states, not two. `holds is None` means the convention
could not be checked, which leaves a gap just as unattributable as a convention
that was checked and failed.
"""
from dataclasses import dataclass

# Named in every reported gap. Deferred by the spec so it does not confound the
# three conventions, but present in every number regardless.
UNATTRIBUTED = (
    "property package differs: BioSTEAM defaults against DWSIM Peng-Robinson",
)


@dataclass(frozen=True)
class Assertion:
    name: str
    holds: bool | None
    detail: str


def check_equivalence(spec, sepsyn_result, sepsyn_theoretical_stages,
                      sepsyn_feed_stage, dwsim) -> tuple[Assertion, ...]:
    out: list[Assertion] = []

    # Stage basis. BioSTEAM's Actual stages must never reach DWSIM; handing 28
    # where 20 was meant produced DCErrorStillHigh in the probe.
    if sepsyn_theoretical_stages is None:
        out.append(Assertion("stage count", None,
                             "sepsyn's theoretical stage count was not supplied"))
    else:
        ok = dwsim.stages == sepsyn_theoretical_stages
        out.append(Assertion(
            "stage count", ok,
            f"sepsyn theoretical {sepsyn_theoretical_stages}, DWSIM "
            f"{dwsim.stages}" + ("" if ok else
            ". BioSTEAM also reports an ACTUAL count, which is larger and must "
            "never be handed to a rigorous column")))

    if sepsyn_feed_stage is None:
        out.append(Assertion(
            "feed stage", None,
            "sepsyn's feed stage was not supplied, or the numbering convention "
            "between the two tools is not yet established"))
    else:
        ok = dwsim.feed_stage == sepsyn_feed_stage
        out.append(Assertion(
            "feed stage", ok,
            f"sepsyn {sepsyn_feed_stage}, DWSIM {dwsim.feed_stage}"))

    ok = abs(dwsim.P_Pa - spec.pressure_Pa) / spec.pressure_Pa < 1e-6
    out.append(Assertion("pressure", ok,
                         f"sepsyn {spec.pressure_Pa:,.0f} Pa, DWSIM "
                         f"{dwsim.P_Pa:,.0f} Pa"))

    both_recovery = (dwsim.condenser_spec.get("type") == "Component Recovery"
                     and dwsim.reboiler_spec.get("type") == "Component Recovery")
    out.append(Assertion(
        "specification basis", both_recovery,
        "both ends specified by component recovery" if both_recovery else
        f"DWSIM condenser spec is {dwsim.condenser_spec.get('type')!r}, "
        f"reboiler {dwsim.reboiler_spec.get('type')!r}; sepsyn specifies "
        f"recoveries, and a different basis is a different column"))

    # Probe finding 4: a mutated flowsheet produced a doubled feed with
    # entirely plausible compositions and temperatures. Only this caught it.
    fed = sum(dwsim.feed_mol_s.values())
    got = sum(dwsim.distillate_mol_s.values()) + sum(dwsim.bottoms_mol_s.values())
    ratio = (got / fed) if fed else 0.0
    ok = fed > 0 and abs(ratio - 1.0) < 1e-3
    out.append(Assertion(
        "mass balance", ok,
        f"DWSIM out/in = {ratio:.4f}" + ("" if ok else
        ". A ratio near 2 means the flowsheet was mutated and two feed streams "
        "are connected")))

    out.append(Assertion(
        "dwsim converged", dwsim.converged,
        "converged" if dwsim.converged else
        f"did not converge: {', '.join(dwsim.errors) or 'no reason given'}"))

    return tuple(out)


def can_report_gap(assertions) -> bool:
    """True only when every assertion actually holds.

    `None` blocks exactly as `False` does. A convention that could not be
    checked leaves the gap as unattributable as one that was checked and
    failed, and treating unknown as satisfied is how an 11x discrepancy gets
    published as shortcut error.
    """
    return all(a.holds is True for a in assertions)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `../.venv/bin/python -m pytest tests/test_configuration_equivalence.py -q`
Expected: PASS, 10 passed

- [ ] **Step 5: Run the full suite**

Run: `../.venv/bin/python -m pytest -q`
Expected: PASS, 370 passed

- [ ] **Step 6: Commit**

```bash
git add sepsyn/simulators/equivalence.py tests/test_configuration_equivalence.py
git commit -m "feat: assert two columns are the same column before reporting any gap

The 09-09 probe measured an 11x condenser duty gap that could not be
attributed, because three configuration conventions were unpinned. Naming it
shortcut error would have repeated the 08-27 mistake, where a 58 percent and a
43 percent disagreement both turned out to be bookkeeping.

An assertion has three states. holds is None means the convention could not be
checked, and that blocks a gap exactly as a failing assertion does. Treating
unknown as satisfied is how an 11x discrepancy gets published as physics.

The mass balance assertion exists because of probe finding 4 specifically: a
mutated flowsheet produced 55.55 mol/s of product from a 27.78 mol/s feed with
entirely plausible compositions and temperatures, and only a mass balance
caught it.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Hio3TrGFNZt6VaANMaRCqZ"
```

---

### Task 3: Pin the feed-stage and stage-inclusion conventions

**Files:**
- Create: `sepsyn/simulators/conventions.py`
- Create: `docs/findings/2026-09-XX-dwsim-conventions.md`
- Test: `tests/test_dwsim_conventions.py`
- Test: `tests/test_convention_sweep_live.py` (marked `dwsim_live`)

**Interfaces:**
- Consumes: `DwsimRun`, `load_fixture` from Task 1.
- Produces:
  - `FEED_STAGE_ORIGIN: str` — `"top"` or `"bottom"`, the empirically determined convention
  - `STAGE_COUNT_INCLUDES_ENDS: bool`
  - `dwsim_feed_stage(biosteam_feed_stage: int, biosteam_theoretical_stages: int) -> int`
  - `dwsim_stage_count(biosteam_theoretical_stages: int) -> int`

**This task is a measurement, not a construction.** The constants above are unknown when the task starts. The live sweep determines them; the unit tests then pin them so they cannot drift.

- [ ] **Step 1: Write the failing test**

```python
"""The DWSIM/BioSTEAM stage conventions, pinned.

Determined empirically by the live sweep in test_convention_sweep_live.py and
recorded here as constants so they cannot drift. Two conventions, confounded
with each other, and both had to be resolved together:

  1. Does BioSTEAM number the feed stage from the top or the bottom?
  2. Does a stage count include the condenser and reboiler?

The 09-09 probe could not separate them. With the feed at DWSIM stage 14 of 20
the column converged in seconds; at stage 6, which is what BioSTEAM reports,
the solver timed out after 300 s. Since 20 - 14 = 6, opposite numbering is the
economical explanation, but it was a hypothesis until the sweep ran.
"""
import pytest

from sepsyn.simulators.conventions import (
    FEED_STAGE_ORIGIN, STAGE_COUNT_INCLUDES_ENDS, dwsim_feed_stage,
    dwsim_stage_count)


def test_the_feed_stage_origin_is_pinned():
    assert FEED_STAGE_ORIGIN in ("top", "bottom")


def test_the_stage_inclusion_convention_is_pinned():
    assert isinstance(STAGE_COUNT_INCLUDES_ENDS, bool)


def test_the_feed_stage_mapping_is_self_consistent():
    """Whatever the origin, mapping twice returns the original. A mapping that
    is not an involution is a mapping that has been guessed."""
    total = 20
    for stage in range(1, total):
        mapped = dwsim_feed_stage(stage, total)
        assert 0 <= mapped < dwsim_stage_count(total)
        if FEED_STAGE_ORIGIN == "bottom":
            assert dwsim_feed_stage(mapped, total) == stage


def test_the_probe_case_maps_as_the_sweep_determined():
    """The concrete case from the 09-09 probe: BioSTEAM reported theoretical
    feed stage 6 of 20 theoretical stages, and DWSIM stage 14 converged."""
    assert dwsim_feed_stage(6, 20) == (14 if FEED_STAGE_ORIGIN == "bottom" else 6)


def test_an_out_of_range_feed_stage_is_refused():
    with pytest.raises(ValueError, match="feed stage"):
        dwsim_feed_stage(25, 20)
```

And the live sweep, which does the actual determining:

```python
"""Determine the DWSIM stage conventions by sweeping, not by reasoning.

Opt in with: pytest -m dwsim_live

Builds the same column at every feed stage and finds which placement
reproduces BioSTEAM's duties. That placement IS the convention. The result is
written into sepsyn/simulators/conventions.py by hand and pinned by
test_dwsim_conventions.py; this file exists to produce it and to re-run when
either tool is upgraded.
"""
import pytest

pytestmark = pytest.mark.dwsim_live


def test_sweep_feed_stage_to_find_the_convention(dwsim_live_runner):
    """Run the 4-component alkane column at every feed stage and report which
    one reproduces BioSTEAM's 71.2 kW condenser duty.

    This test ASSERTS only that some placement gets within 25 percent. It does
    not assert which, because which one is the thing being measured. If no
    placement comes close, the gap is not a feed-stage convention and that is
    itself the finding.
    """
    results = dwsim_live_runner.sweep_feed_stage(
        feed_mol_s={"Propane": 2.77778, "N-butane": 5.55556,
                    "N-pentane": 16.66667, "N-hexane": 2.77778},
        T_K=330.0, P_Pa=1369410.0, stages=20,
        lk="Propane", hk="N-butane", recovery=99.0)
    converged = {s: r for s, r in results.items() if r.converged}
    assert converged, "no feed stage converged; the case is unusable"

    target = 71.2
    best = min(converged.items(),
               key=lambda kv: abs(kv[1].condenser_duty_kW - target))
    stage, run = best
    print(f"\nclosest feed stage: {stage}, "
          f"condenser {run.condenser_duty_kW:.1f} kW against BioSTEAM {target}")
    for s, r in sorted(converged.items()):
        print(f"  stage {s:>2}: {r.condenser_duty_kW:>9.1f} kW")
    assert abs(run.condenser_duty_kW - target) / target < 0.25, (
        "no feed stage reproduces BioSTEAM's duty within 25 percent, so the "
        "11x gap is NOT a feed-stage convention mismatch and the finding is "
        "that it is something else")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../.venv/bin/python -m pytest tests/test_dwsim_conventions.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'sepsyn.simulators.conventions'`

- [ ] **Step 3: Run the live sweep to determine the conventions**

Run: `../.venv/bin/python -m pytest tests/test_convention_sweep_live.py -m dwsim_live -q -s`

Read the printed table. The feed stage whose condenser duty is closest to BioSTEAM's is the convention. Record what you observed in `docs/findings/2026-09-XX-dwsim-conventions.md`, including the whole table, not only the winner.

**If no placement comes within 25 percent**, stop and report. That result means the 11x gap is not a feed-stage convention mismatch, the milestone's premise needs revisiting, and no constant should be invented to make the test pass.

- [ ] **Step 4: Write the constants the sweep determined**

Create `sepsyn/simulators/conventions.py`, filling the two constants from what the sweep printed:

```python
"""DWSIM and BioSTEAM stage conventions, determined empirically.

These are MEASUREMENTS, recorded from the sweep in
tests/test_convention_sweep_live.py and pinned by tests/test_dwsim_conventions.py.
They are not derived from documentation, because the 09-09 probe showed the
documented reading of "theoretical feed stage 6" does not converge while its
mirror image does.

Re-run the sweep after any BioSTEAM or DWSIM upgrade. See
docs/findings/ for the table these came from.
"""

# "top" or "bottom": which end BioSTEAM counts the feed stage from, relative to
# DWSIM, whose stage 0 is the condenser.
FEED_STAGE_ORIGIN = "bottom"        # <- set from the sweep

# Whether BioSTEAM's theoretical stage count already includes the condenser and
# the reboiler, as DWSIM's does.
STAGE_COUNT_INCLUDES_ENDS = True    # <- set from the sweep


def dwsim_stage_count(biosteam_theoretical_stages: int) -> int:
    if STAGE_COUNT_INCLUDES_ENDS:
        return biosteam_theoretical_stages
    return biosteam_theoretical_stages + 2


def dwsim_feed_stage(biosteam_feed_stage: int,
                     biosteam_theoretical_stages: int) -> int:
    """Map BioSTEAM's feed stage onto DWSIM's 0-based, condenser-first index."""
    total = dwsim_stage_count(biosteam_theoretical_stages)
    if not 0 <= biosteam_feed_stage < total:
        raise ValueError(
            f"feed stage {biosteam_feed_stage} is outside a {total}-stage "
            f"column")
    if FEED_STAGE_ORIGIN == "bottom":
        return total - biosteam_feed_stage
    return biosteam_feed_stage
```

- [ ] **Step 5: Run test to verify it passes**

Run: `../.venv/bin/python -m pytest tests/test_dwsim_conventions.py -q`
Expected: PASS, 5 passed

Run: `../.venv/bin/python -m pytest -q`
Expected: PASS, 375 passed, with the live sweep deselected by default.

- [ ] **Step 6: Commit**

```bash
git add sepsyn/simulators/conventions.py tests/test_dwsim_conventions.py \
        tests/test_convention_sweep_live.py docs/findings/
git commit -m "feat: pin the DWSIM stage conventions by measuring them

Two conventions, confounded with each other, and neither derivable from
documentation: whether BioSTEAM numbers the feed stage from the top or the
bottom, and whether a stage count includes the condenser and reboiler.

The 09-09 probe could not separate them. At DWSIM stage 14 of 20 the column
converged in seconds; at stage 6, which is what BioSTEAM reports, the solver
timed out after 300 s. Since 20 minus 14 is 6, opposite numbering was the
economical explanation, but it stayed a hypothesis until the sweep ran.

The sweep builds the same column at every feed stage and finds which one
reproduces BioSTEAM's duty. That placement IS the convention. The constants are
measurements, and the findings note records the whole table rather than only
the winner.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Hio3TrGFNZt6VaANMaRCqZ"
```

---

### Task 4: The DWSIM adapter

**Files:**
- Create: `sepsyn/simulators/dwsim_adapter.py`
- Modify: `pytest.ini` (register the `dwsim_live` marker)
- Test: `tests/test_dwsim_adapter.py`
- Test: `tests/test_dwsim_adapter_live.py` (marked `dwsim_live`)

**Interfaces:**
- Consumes: `DwsimRun` and `load_fixture` from Task 1; `dwsim_feed_stage`, `dwsim_stage_count` from Task 3; `ColumnSpec`, `ColumnResult` from `base.py`.
- Produces:
  - `DwsimSimulator(transport)` with `design_from_stages(feed, spec, theoretical_stages, feed_stage) -> DwsimRun`
  - `FixtureTransport(directory)` — replays recorded runs
  - `LiveTransport(timeout_s=300)` — speaks to `dwsim-mcp`
  - `DwsimTimeout(RuntimeError)`

**The fresh-flowsheet rule is the adapter's core invariant.** Every call creates a new flowsheet. There is no code path that reconfigures, reconnects or disconnects, because the probe showed a mutated flowsheet silently doubles the feed.

- [ ] **Step 1: Write the failing test**

```python
"""The DWSIM adapter. Fixture transport by default, live behind a marker."""
import pytest

from sepsyn.simulators.base import ColumnSpec
from sepsyn.simulators.dwsim_adapter import (
    DwsimSimulator, FixtureTransport)
from sepsyn.types import Component, Feed

SPEC = ColumnSpec("Benzene", "Toluene", 0.99, 0.99, 101325.0)


def bt_feed():
    return Feed(components=(Component("Benzene", "71-43-2", 60.0),
                            Component("Toluene", "108-88-3", 40.0)),
                T_K=298.15, P_Pa=101325.0)


def test_a_recorded_run_is_replayed(tmp_path):
    from sepsyn.simulators.dwsim_fixtures import DwsimRun, save_fixture
    run = DwsimRun(
        feed_mol_s={"Benzene": 16.6667, "Toluene": 11.1111},
        T_K=298.15, P_Pa=101325.0, stages=20, feed_stage=10,
        condenser_spec={"type": "Component Recovery", "compound": "Benzene",
                        "value": 99.0},
        reboiler_spec={"type": "Component Recovery", "compound": "Toluene",
                       "value": 99.0},
        property_package="Peng-Robinson (PR)", solver="NS",
        converged=True, errors=(),
        distillate_mol_s={"Benzene": 16.5, "Toluene": 0.111},
        bottoms_mol_s={"Benzene": 0.1667, "Toluene": 11.0},
        condenser_duty_kW=1083.4, reboiler_duty_kW=1447.1)
    save_fixture(str(tmp_path / "benzene_toluene_20_10.json"), run)

    sim = DwsimSimulator(FixtureTransport(str(tmp_path)))
    got = sim.design_from_stages(bt_feed(), SPEC, 20, 10)
    assert got.converged
    assert got.condenser_duty_kW == pytest.approx(1083.4)


def test_a_missing_fixture_is_an_explicit_failure_not_a_silent_zero(tmp_path):
    sim = DwsimSimulator(FixtureTransport(str(tmp_path)))
    with pytest.raises(FileNotFoundError, match="benzene_toluene"):
        sim.design_from_stages(bt_feed(), SPEC, 20, 10)


def test_the_adapter_converts_kmol_hr_to_mol_s(tmp_path):
    """sepsyn works in kmol/hr and DWSIM in mol/s. A factor of 3.6 in the wrong
    place is the kind of basis error this project exists to prevent."""
    from sepsyn.simulators.dwsim_adapter import feed_to_mol_s
    got = feed_to_mol_s(bt_feed())
    assert got["Benzene"] == pytest.approx(60.0 / 3.6)
    assert got["Toluene"] == pytest.approx(40.0 / 3.6)


def test_component_names_are_mapped_to_the_dwsim_database():
    """sepsyn says Butane, the DWSIM database says N-butane. An unmapped name
    would silently produce a column missing a component."""
    from sepsyn.simulators.dwsim_adapter import dwsim_name
    assert dwsim_name("Butane") == "N-butane"
    assert dwsim_name("Pentane") == "N-pentane"
    assert dwsim_name("Hexane") == "N-hexane"
    assert dwsim_name("Benzene") == "Benzene"


def test_an_unmappable_name_is_refused_rather_than_passed_through():
    from sepsyn.simulators.dwsim_adapter import UnknownDwsimCompound, dwsim_name
    with pytest.raises(UnknownDwsimCompound, match="Unobtainium"):
        dwsim_name("Unobtainium")


def test_the_adapter_never_mutates_a_flowsheet():
    """Probe finding 4. A mutated flowsheet silently doubled the feed. The
    invariant is enforced by reading the source, because the failure it
    prevents is invisible in the numbers."""
    import sepsyn.simulators.dwsim_adapter as a
    source = open(a.__file__).read()
    for forbidden in ("disconnect_objects", "reconfigure"):
        assert forbidden not in source, (
            f"{forbidden} appears in the adapter; a mutated flowsheet produced "
            f"a silently doubled feed in the 09-09 probe")
    assert "create_flowsheet" in source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../.venv/bin/python -m pytest tests/test_dwsim_adapter.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'sepsyn.simulators.dwsim_adapter'`

- [ ] **Step 3: Write minimal implementation**

Register the marker in `pytest.ini`:

```ini
[pytest]
testpaths = tests
pythonpath = .
markers =
    dwsim_live: talks to a real DWSIM through dwsim-mcp; slow, opt in with -m dwsim_live
addopts = -m "not dwsim_live"
```

Create `sepsyn/simulators/dwsim_adapter.py`:

```python
"""Talk to DWSIM's rigorous column.

ONE invariant governs this module: every call builds a FRESH flowsheet. There
is no code path that reconfigures, reconnects or disconnects an existing one.

That is not tidiness. In the 09-09 probe, disconnect_objects reported success
and left the feed attached; the next solve ran with two feed streams and
produced 55.55 mol/s of product from a 27.78 mol/s feed, with entirely
plausible compositions and temperatures. Nothing in the result flagged it.
"""
import os

from sepsyn.simulators.dwsim_fixtures import DwsimRun, load_fixture

# sepsyn uses the common name; the DWSIM database is specific about isomers.
# An unmapped name would silently produce a column missing a component.
DWSIM_NAMES = {
    "Butane": "N-butane",
    "Pentane": "N-pentane",
    "Hexane": "N-hexane",
    "Heptane": "N-heptane",
    "Octane": "N-octane",
}
PASS_THROUGH = {"Propane", "Benzene", "Toluene", "Ethanol", "Water",
                "Methanol", "Acetone"}


class UnknownDwsimCompound(ValueError):
    """A name with no established DWSIM database equivalent."""


class DwsimTimeout(RuntimeError):
    """The solver exceeded its budget. An outcome, not an error."""


def dwsim_name(name: str) -> str:
    if name in DWSIM_NAMES:
        return DWSIM_NAMES[name]
    if name in PASS_THROUGH:
        return name
    raise UnknownDwsimCompound(
        f"no DWSIM database name established for {name!r}. Add it to "
        f"DWSIM_NAMES after confirming the exact database spelling; passing "
        f"an unmapped name through silently omits the component."
    )


def feed_to_mol_s(feed) -> dict[str, float]:
    """kmol/hr to mol/s, with the DWSIM names. Divide by 3.6."""
    return {dwsim_name(c.name): c.flow_kmol_hr / 3.6 for c in feed.components}


def fixture_key(feed, spec, stages: int, feed_stage: int) -> str:
    names = "_".join(c.name.lower() for c in feed.components)
    return f"{names}_{stages}_{feed_stage}.json"


class FixtureTransport:
    """Replay a recorded run. Keeps the default suite hermetic and fast."""

    def __init__(self, directory: str):
        self.directory = directory

    def run(self, feed, spec, stages: int, feed_stage: int) -> DwsimRun:
        path = os.path.join(self.directory,
                            fixture_key(feed, spec, stages, feed_stage))
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"no recorded DWSIM run at {path}. Record one with the live "
                f"transport rather than falling back to a default, which would "
                f"compare against a number nobody measured."
            )
        return load_fixture(path)


class DwsimSimulator:
    """The rigorous reference. Not a peer to sepsyn's shortcut methods."""

    def __init__(self, transport):
        self.transport = transport

    def design_from_stages(self, feed, spec, theoretical_stages: int,
                           feed_stage: int) -> DwsimRun:
        """Solve a column with the stage count and feed stage GIVEN.

        Rigorous columns run in the simulation direction: stages in, duties
        out. sepsyn's shortcut runs the other way. That asymmetry is the
        milestone's point, and it is why this method takes stages rather than
        computing them.
        """
        return self.transport.run(feed, spec, theoretical_stages, feed_stage)
```

The `LiveTransport` is written in Task 5, where its behaviour can be tested against a real DWSIM.

- [ ] **Step 4: Run test to verify it passes**

Run: `../.venv/bin/python -m pytest tests/test_dwsim_adapter.py -q`
Expected: PASS, 6 passed

- [ ] **Step 5: Run the full suite**

Run: `../.venv/bin/python -m pytest -q`
Expected: PASS, 381 passed, live tests deselected by `addopts`.

Confirm the marker works: `../.venv/bin/python -m pytest -m dwsim_live -q --collect-only` should collect the live files and nothing else.

- [ ] **Step 6: Commit**

```bash
git add sepsyn/simulators/dwsim_adapter.py tests/test_dwsim_adapter.py pytest.ini
git commit -m "feat: DWSIM adapter with a fresh flowsheet per run

One invariant governs the module: every call builds a fresh flowsheet, and no
code path reconfigures, reconnects or disconnects an existing one. That is
enforced by a test which reads the source, because the failure it prevents is
invisible in the numbers: in the 09-09 probe disconnect reported success, left
the feed attached, and the next solve produced 55.55 mol/s of product from a
27.78 mol/s feed with entirely plausible compositions.

Component names are mapped explicitly. sepsyn says Butane and the DWSIM
database says N-butane; an unmapped name is refused rather than passed through,
because passing it through silently omits the component.

A missing fixture raises rather than falling back to a default, which would
compare against a number nobody measured.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Hio3TrGFNZt6VaANMaRCqZ"
```

---

### Task 5: The live transport, and record the benzene/toluene fixture

**Files:**
- Modify: `sepsyn/simulators/dwsim_adapter.py` (add `LiveTransport`)
- Create: `tests/fixtures/dwsim/benzene_toluene_*.json` (recorded, not written by hand)
- Test: `tests/test_dwsim_adapter_live.py` (marked `dwsim_live`)

**Interfaces:**
- Consumes: everything from Task 4.
- Produces: `LiveTransport(timeout_s: int = 300)` with the same `run(feed, spec, stages, feed_stage) -> DwsimRun` signature as `FixtureTransport`, plus `record(path, ...)`.

- [ ] **Step 1: Write the failing test**

```python
"""The live DWSIM transport. Opt in with: pytest -m dwsim_live

Slow by nature. A 300 s timeout was already observed in the 09-09 probe, which
is why these never run in the default suite.
"""
import pytest

from sepsyn.simulators.base import ColumnSpec
from sepsyn.simulators.dwsim_adapter import DwsimSimulator, LiveTransport
from sepsyn.types import Component, Feed

pytestmark = pytest.mark.dwsim_live

SPEC = ColumnSpec("Benzene", "Toluene", 0.99, 0.99, 101325.0)


def bt_feed():
    return Feed(components=(Component("Benzene", "71-43-2", 60.0),
                            Component("Toluene", "108-88-3", 40.0)),
                T_K=298.15, P_Pa=101325.0)


def test_a_live_benzene_toluene_column_converges():
    sim = DwsimSimulator(LiveTransport(timeout_s=300))
    run = sim.design_from_stages(bt_feed(), SPEC, 20, 10)
    assert run.converged, run.errors


def test_the_live_run_closes_its_mass_balance():
    """The doubled-feed guard, against a real solver. This is the assertion the
    09-09 probe lacked."""
    sim = DwsimSimulator(LiveTransport(timeout_s=300))
    run = sim.design_from_stages(bt_feed(), SPEC, 20, 10)
    fed = sum(run.feed_mol_s.values())
    out = sum(run.distillate_mol_s.values()) + sum(run.bottoms_mol_s.values())
    assert out == pytest.approx(fed, rel=1e-3)


def test_a_timeout_is_an_OUTCOME_not_a_crash():
    """A rigorous solve that does not finish is a fact about the case. Raising
    would lose it; the probe's stage-6 timeout is a finding worth recording."""
    from sepsyn.simulators.dwsim_adapter import DwsimTimeout
    sim = DwsimSimulator(LiveTransport(timeout_s=1))
    try:
        run = sim.design_from_stages(bt_feed(), SPEC, 20, 10)
        assert run.converged is False
        assert any("timeout" in e.lower() for e in run.errors)
    except DwsimTimeout:
        pytest.fail("a timeout must be returned as a non-converged run, "
                    "not raised")


def test_recording_produces_a_fixture_the_default_suite_can_replay(tmp_path):
    from sepsyn.simulators.dwsim_fixtures import load_fixture
    sim = DwsimSimulator(LiveTransport(timeout_s=300))
    path = tmp_path / "benzene_toluene_20_10.json"
    run = sim.design_from_stages(bt_feed(), SPEC, 20, 10)
    from sepsyn.simulators.dwsim_fixtures import save_fixture
    save_fixture(str(path), run)
    assert load_fixture(str(path)) == run
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../.venv/bin/python -m pytest tests/test_dwsim_adapter_live.py -m dwsim_live -q`
Expected: FAIL, `ImportError: cannot import name 'LiveTransport'`

- [ ] **Step 3: Write minimal implementation**

Add `LiveTransport` to `sepsyn/simulators/dwsim_adapter.py`. It drives the `dwsim-mcp` server through a subprocess speaking MCP over stdio, and performs exactly this sequence per call, in order, with no reuse:

```
create_flowsheet
add_compound          (once per component, DWSIM names)
set_property_package  ("Peng-Robinson (PR)")
add_object            MaterialStream F, D, B; EnergyStream QC, QR;
                      DistillationColumn T1
set_stream            F: T, P, compound_molar_flows
configure_column      T1: stages, top_pressure, dP=0,
                      Component Recovery on both ends,
                      Napthali-Sandholm, max_iterations
connect_column_stream F as feed at the mapped stage, D distillate,
                      B bottoms, QC condenser_duty, QR reboiler_duty
solve                 with the timeout
get_results
```

Return a `DwsimRun` carrying that configuration alongside the result. On
timeout, return `converged=False` with a `"timeout"` error rather than raising:
a solve that does not finish is a fact about the case, and the probe's stage-6
timeout is exactly the kind of finding that must survive.

- [ ] **Step 4: Run the live tests**

Run: `../.venv/bin/python -m pytest tests/test_dwsim_adapter_live.py -m dwsim_live -q`
Expected: PASS, 4 passed. Minutes, not seconds.

- [ ] **Step 5: Record the fixture and confirm the default suite stays fast**

Record the benzene/toluene run into `tests/fixtures/dwsim/`, then:

Run: `../.venv/bin/python -m pytest -q`
Expected: PASS, still under 90 s, live tests deselected.

- [ ] **Step 6: Commit**

```bash
git add sepsyn/simulators/dwsim_adapter.py tests/test_dwsim_adapter_live.py \
        tests/fixtures/dwsim/
git commit -m "feat: live DWSIM transport, and the recorded benzene/toluene run

Fresh flowsheet per call, in a fixed sequence, with nothing reused between
runs. A timeout returns a non-converged run rather than raising: a rigorous
solve that does not finish is a fact about the case, and the 09-09 probe's
stage-6 timeout is exactly the kind of finding that must survive rather than
becoming an exception.

The live tests sit behind the dwsim_live marker and are deselected by default,
because a single solve can take minutes and the suite finishes in under one.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Hio3TrGFNZt6VaANMaRCqZ"
```

---

### Task 6: The comparison, and refusing to report an unattributable gap

**Files:**
- Create: `sepsyn/crossvalidate.py`
- Create: `docs/findings/2026-09-XX-shortcut-error.md`
- Test: `tests/test_crossvalidation.py`
- Test: `tests/test_crossvalidation_live.py` (marked `dwsim_live`)

**Interfaces:**
- Consumes: `check_equivalence`, `can_report_gap`, `UNATTRIBUTED` from Task 2; `DwsimSimulator` from Task 4; `BioSteamSimulator`.
- Produces:
  - `Gap(quantity: str, sepsyn: float, dwsim: float, relative: float)`
  - `Comparison(assertions: tuple, gaps: tuple[Gap, ...], reportable: bool, unattributed: tuple[str, ...])`
  - `compare(feed, spec, biosteam_sim, dwsim_sim) -> Comparison`
  - `format_comparison(c: Comparison) -> str`

- [ ] **Step 1: Write the failing test**

```python
"""The comparison, and the refusal.

A gap is only reported when every configuration assertion holds. Otherwise the
comparison says it cannot attribute the difference, which is the honest answer
and the one the 08-27 findings were paid for.
"""
import pytest

from sepsyn.crossvalidate import compare, format_comparison

# (Fixtures and fakes as in tests/test_configuration_equivalence.py; the
# helpers below build a matched pair and a mismatched pair.)


def test_a_matched_pair_reports_gaps_on_the_UNIMPOSED_quantities(matched):
    c = compare(*matched)
    assert c.reportable is True
    quantities = {g.quantity for g in c.gaps}
    assert "condenser duty" in quantities
    assert "reboiler duty" in quantities


def test_products_are_NOT_reported_as_a_gap(matched):
    """Recovery specs impose the products on both sides, so agreement there is
    evidence of nothing. Reporting it as a finding would be reporting the
    specification back to the user."""
    c = compare(*matched)
    assert not any("product" in g.quantity or "recovery" in g.quantity
                   for g in c.gaps)


def test_a_mismatched_configuration_reports_NO_gap_at_all(mismatched):
    c = compare(*mismatched)
    assert c.reportable is False
    assert c.gaps == ()


def test_the_refusal_names_which_assertion_failed(mismatched):
    text = format_comparison(compare(*mismatched))
    assert "cannot" in text.lower()
    assert "stage count" in text


def test_a_reported_gap_always_names_the_unattributed_contributors(matched):
    """The property packages differ and that is deferred, not solved. A gap
    printed without saying so implies the whole difference is shortcut error."""
    text = format_comparison(compare(*matched))
    assert "property package" in text


def test_the_relative_gap_is_signed(matched):
    """Direction matters: whether the shortcut over- or under-predicts a duty
    is design information, and an absolute value throws it away."""
    c = compare(*matched)
    assert any(g.relative < 0 for g in c.gaps) or any(g.relative > 0 for g in c.gaps)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../.venv/bin/python -m pytest tests/test_crossvalidation.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'sepsyn.crossvalidate'`

- [ ] **Step 3: Write minimal implementation**

Create `sepsyn/crossvalidate.py` with `Gap`, `Comparison`, `compare` and
`format_comparison`. `compare` runs the equivalence check first and returns
`gaps=()` with `reportable=False` whenever `can_report_gap` is false. Gaps are
computed only on the unimposed quantities: reflux, condenser duty, reboiler
duty, distillate temperature, bottoms temperature. `relative` is signed,
`(sepsyn - dwsim) / dwsim`.

`format_comparison` prints, in this order: the assertions with their state, then
either the gaps or an explicit refusal naming the failing assertion, then the
`UNATTRIBUTED` contributors in every case.

- [ ] **Step 4: Run test to verify it passes**

Run: `../.venv/bin/python -m pytest tests/test_crossvalidation.py -q`
Expected: PASS, 6 passed

- [ ] **Step 5: Run the real comparison and write the finding**

Run the live comparison on both staged cases:

```bash
../.venv/bin/python -m pytest tests/test_crossvalidation_live.py -m dwsim_live -q -s
```

Record the measured gaps in `docs/findings/2026-09-XX-shortcut-error.md`:
benzene/toluene first, then the four-component alkane column. State the
tolerance as a measurement, not inherited from 08-27. Where a gap could not be
reported, record the refusal and which assertion blocked it — that is a result.

**Do not tune anything to make a gap smaller.** The gap is the deliverable.

- [ ] **Step 6: Commit**

```bash
git add sepsyn/crossvalidate.py tests/test_crossvalidation.py \
        tests/test_crossvalidation_live.py docs/findings/
git commit -m "feat: cross-validation that refuses to report an unattributable gap

A gap is reported only when every configuration assertion holds. Otherwise the
comparison says it cannot attribute the difference and names the assertion that
blocked it, which is the honest answer and the one the 08-27 findings were paid
for.

Products are deliberately not reported as a gap. Recovery specs impose them on
both sides, so agreement there is evidence of nothing and printing it would be
reporting the specification back to the reader. Only reflux, duties and
temperatures carry information.

Relative gaps are signed. Whether the shortcut over- or under-predicts a duty
is design information that an absolute value throws away.

Every reported gap names the unattributed contributors, the property package
difference among them, so a reader does not read the whole difference as
shortcut error.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Hio3TrGFNZt6VaANMaRCqZ"
```

---

## Self-review

**Spec coverage.** §4 harness-first: Task 2 gates every gap on `can_report_gap`. §5 three conventions: stage basis in Task 2's assertion, feed stage and stage inclusion measured in Task 3. §6 transport: `FixtureTransport` in Task 4, `LiveTransport` in Task 5, marker registered in Task 4. §6 fresh flowsheet: enforced by a source-reading test in Task 4. §7 staged bring-up: benzene/toluene fixture in Task 5, both cases compared in Task 6. §8 acceptance: criteria 1–3 in Tasks 2, 3 and 6; criterion 4 in Task 6 step 5; criterion 5 in the findings note; criterion 6 in Task 6's refusal path. §9 property package deferral: carried as `UNATTRIBUTED` and asserted present in Task 6.

**Placeholder scan.** No TBD or "similar to Task N". Task 3 step 4 contains two constants marked `<- set from the sweep`; those are the measurement the task exists to make and are the one place a value is legitimately unknown when the plan is written. Task 3 step 3 says explicitly what to do if no placement fits: stop and report, invent nothing. Task 6 step 5 says do not tune to shrink a gap.

**Type consistency.** `DwsimRun` is constructed identically in Tasks 1, 2, 4 and 5. `Assertion.holds` is tri-state in Task 2 and consumed as tri-state by `can_report_gap`. `FixtureTransport.run` and `LiveTransport.run` share a signature so `DwsimSimulator` is transport-agnostic. `dwsim_feed_stage` from Task 3 is what Task 5 uses to map the feed stage.

**Two risks worth naming.** Task 3 may find that no feed-stage placement reproduces BioSTEAM's duty, in which case the 11× gap is not a convention mismatch and the milestone's premise needs revisiting; the plan makes that a loud failure rather than a tuned constant. Task 5's `LiveTransport` is the only part whose implementation is described rather than written out, because the MCP client wiring depends on how `dwsim-mcp` is launched in this environment and guessing it here would produce code that looks authoritative and does not run.
