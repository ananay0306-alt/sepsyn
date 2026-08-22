"""The simulator boundary.

Nothing simulator-specific crosses this line -- no Stream, no Unit, no
flowsheet. That is what makes DWSIM a second file later rather than a rewrite,
and what lets the design code be tested against a fake with no chemistry in it.
"""
from dataclasses import dataclass
from typing import Protocol

from sepsyn.types import Feed


@dataclass(frozen=True)
class ColumnSpec:
    """Recoveries, NOT mole fractions.

    Recovery is unambiguous: "99% of the methanol leaves overhead" means the
    same thing in every simulator. Mole fraction does not -- BioSTEAM reads it
    against the two keys, DWSIM against the whole product stream, and that
    mismatch produced a 175% error in an earlier comparison of the two.

    Keeping the spec in recoveries also means the BioSTEAM adapter never has to
    build a mole-fraction basis at all: BioSTEAM accepts recoveries directly.
    """
    light_key: str
    heavy_key: str
    lk_recovery_to_distillate: float
    hk_recovery_to_bottoms: float
    pressure_Pa: float
    reflux_over_minimum: float = 1.2


@dataclass(frozen=True)
class ColumnResult:
    """A design, or an explained failure. Never a silent half-answer.

    `converged` is the only field worth reading first: when it is False every
    number here is a placeholder and `error` says why.
    """
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
    """Exactly two of the three must be given -- a flash has two degrees of
    freedom, and supplying one or three is a caller bug, not a design choice."""
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
