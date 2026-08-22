"""Design decisions that are rules, not judgment.

Column pressure comes from the cooling-water heuristic. Reflux comes from a
sweep that returns the whole curve -- including the points that failed -- so
the output shows the trade-off rather than asserting a single answer.
"""
import contextlib
import dataclasses
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


def _saturation_pressure(name: str, T_K: float) -> float | None:
    """Pure-component saturation pressure at T, Pa.

    Uses Chemical.Psat directly. The obvious-looking alternative --
    build a Stream and call s.vle(T=T, V=0.0), then read s.P -- does NOT
    solve for pressure: it leaves P at the Stream default and hands back
    101325.0 for every chemical alike, which silently turns the
    raise-the-pressure branch below into dead code. Verified against
    literature at 313.15 K: methanol 0.355 bar (lit 0.354), propane 13.69
    (13.71), n-butane 3.785 (3.784). Do not replace this with a VLE call.
    """
    import thermosteam as tmo

    with contextlib.redirect_stdout(io.StringIO()):
        try:
            P = float(tmo.Chemical(name).Psat(T_K))
        except Exception:
            return None
    return P if P > 0 else None


def choose_pressure(feed: Feed, light_key: str) -> tuple[float, str]:
    """Lowest pressure at which the overhead condenses against cooling water.

    The standard heuristic: go as low as you can, because low pressure improves
    relative volatility, but stop where the condenser stops working.
    """
    cas = resolve(light_key)
    if COOLING_WATER_T > critical_temperature(cas):
        return MAX_PRESSURE_Pa, (
            f"{light_key} is supercritical at cooling water temperature "
            f"({COOLING_WATER_T:.1f} K); refrigeration required"
        )

    p_required = _saturation_pressure(light_key, COOLING_WATER_T)
    if p_required is None:
        return 101325.0, (
            f"could not determine the pressure at which {light_key} condenses "
            f"against cooling water; assumed atmospheric -- this is a gap in "
            f"the evidence, not a finding that atmospheric is sufficient"
        )

    if p_required <= 101325.0:
        return 101325.0, (
            f"atmospheric is sufficient; {light_key} condenses against "
            f"cooling water at {COOLING_WATER_T:.1f} K "
            f"(saturation pressure {p_required/1e5:.2f} bar)"
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
    """One reflux multiple. `converged` False means the design failed here and
    every number below is a placeholder -- the point is kept in the curve
    anyway, because "could not be designed" and "was not tried" are different
    facts and the caller is entitled to tell them apart."""
    k: float
    stages: float
    annualised_cost_USD_yr: float
    installed_cost_USD: float
    utility_cost_USD_hr: float
    converged: bool = True
    error: str | None = None


def _annualised(installed: float, utility_per_hr: float) -> float:
    """Deliberately crude. The tool reports the whole curve, and the knee's
    position is insensitive to these constants."""
    return installed / PLANT_LIFE_YEARS + utility_per_hr * OPERATING_HOURS_YR


def sweep_reflux(sim, feed: Feed, spec: ColumnSpec,
                 k_values: list[float] | None = None) -> list[SweepPoint]:
    """Design the column at each reflux multiple and return the whole curve.

    Failed points are recorded, not skipped. Dropping them would hand back a
    curve that looks complete while quietly hiding the region the column cannot
    be built in -- and that region is usually the interesting one, since it
    borders the minimum reflux.
    """
    points: list[SweepPoint] = []
    for k in (k_values or DEFAULT_K_VALUES):
        r = sim.design_column(feed, dataclasses.replace(spec,
                                                        reflux_over_minimum=k))
        if not r.converged:
            points.append(SweepPoint(k=k, stages=0.0,
                                     annualised_cost_USD_yr=float("inf"),
                                     installed_cost_USD=0.0,
                                     utility_cost_USD_hr=0.0,
                                     converged=False, error=r.error))
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
    """Cheapest annualised cost among the designs that actually converged."""
    converged = [p for p in points if p.converged]
    if not converged:
        raise ValueError(
            f"no converged points in sweep ({len(points)} attempted)"
        )
    return min(converged, key=lambda p: p.annualised_cost_USD_yr)
