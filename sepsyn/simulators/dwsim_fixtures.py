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
