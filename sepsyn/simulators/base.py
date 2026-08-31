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
    condenser_type: str = "total"
    """"total" or "partial". Heuristic step 22.

    Carried on the SPEC, not left to the adapter, because this is the choice
    that produced the project's 58 percent condenser-duty discrepancy: a
    partial condenser does roughly R/(R+1) of the duty of a total one and hands
    back a vapour distillate. An equipment rule that recommends a condenser
    while the adapter hardcodes a different one reproduces that failure with
    better documentation attached."""
    feed_q: float | None = None
    """Feed thermal condition to impose, at the column pressure. Heuristic
    steps 15 and 16.

    None means TAKE THE FEED AS IT ARRIVES -- it is not a default of 1.0. That
    distinction matters: every design sepsyn made before this field existed
    used the arriving condition, and quietly asserting a saturated liquid here
    would change all of them while looking like a no-op.

    A number imposes the condition, which is step 16's preheat-or-not decision
    made explicit: 1.0 a saturated liquid, 0.0 a saturated vapour, above 1
    subcooled, below 0 superheated. The duty needed to get there is a feed
    heater or cooler that this tool does not yet cost."""


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
    # Thermal results. All optional: an adapter that cannot supply them leaves
    # them None and verify_column SKIPS the corresponding check rather than
    # failing it, because absent is not the same as wrong. Duties are positive
    # magnitudes in kW; enthalpies are stream enthalpy in kW.
    condenser_duty_kW: float | None = None
    reboiler_duty_kW: float | None = None
    distillate_T_K: float | None = None
    bottoms_T_K: float | None = None
    feed_H_kW: float | None = None
    distillate_H_kW: float | None = None
    bottoms_H_kW: float | None = None
    biosteam_reported_diameter_m: float | None = None
    """The diameter BioSTEAM actually designed and COSTED the column at, in
    metres. Kept alongside column_diameter_m because BioSTEAM floors the
    diameter at 0.914 m and then sizes the shell, wall and cost from that
    floored value -- so the cost belongs to this number, while the equipment
    rules need the other one. Neither may be silently substituted for the
    other."""
    column_diameter_m: float | None = None
    """Column diameter in METRES. BioSTEAM reports it in feet; the conversion
    happens in the adapter so no rule ever sees a foot. The internals rule
    keys on 0.6 m, and 3.8 ft read as metres would make its small-diameter
    branch unreachable for every column ever designed.

    This is the TRUE hydraulic diameter, recovered from under BioSTEAM's
    0.914 m floor -- see _hydraulic_diameter_m in the adapter. Above the floor
    it equals biosteam_reported_diameter_m exactly."""
    feed_q: float | None = None
    """The feed thermal condition this design ACTUALLY ran at, measured at the
    column pressure. Heuristic step 17.

    Recorded on the result and not only in the printed report, because two
    designs at different q are not comparable and a q that cannot be asserted
    on is a q that will go unchecked. None means it could not be measured (no
    VLE region at this pressure), never that the feed was a saturated
    vapour -- that is q = 0.0."""


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
