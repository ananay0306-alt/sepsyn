"""Checks run on every design before it is reported.

Failures are returned as DATA, not raised. A design that fails verification is
still returned, clearly marked -- "here is what it produced and here is why you
should not trust it" is more useful than a stack trace.

Every check carries a detail line with the numbers it used, so a reader can
disagree with the verdict rather than having to take it.
"""
from dataclasses import dataclass

from sepsyn.simulators.base import ColumnResult, ColumnSpec
from sepsyn.types import Feed

# Both tolerances are set from measurements, not from habit.
#
# MASS_BALANCE_TOL: BioSTEAM closes a component balance to better than 1e-6
# relative (pinned by a test in tests/test_simulator.py), so 1e-3 leaves three
# orders of magnitude of headroom for a noisier simulator while still catching
# any violation large enough to matter.
#
# RECOVERY_TOL: BioSTEAM hits a requested recovery to 1.1e-16 across sixteen
# spec/reflux combinations -- recovery is imposed, not iterated, so there is
# essentially no numerical error to absorb. The error this must catch is 0.002,
# the shift produced by reading a recovery as a keys-only mole fraction. 1e-3
# sits between those two scales with a factor of two on the side that matters.
# DO NOT RELAX THIS toward the plan's original 0.03: at that value a design
# built on the wrong basis passes verification silently, which is the single
# failure mode the recovery spec exists to prevent.
MASS_BALANCE_TOL = 1e-3      # relative, PER COMPONENT
RECOVERY_TOL = 1e-3          # absolute, on a fraction


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str


def _component_balance(feed: Feed, result: ColumnResult) -> Check:
    """Mass balance component by component.

    An aggregate total is not a balance: errors in opposite directions cancel,
    so a design that destroys one component and creates another can close to a
    fraction of a percent overall. Checking each component separately is the
    only version of this check that means anything, and naming the worst
    offender is what makes a failure actionable.
    """
    worst_name, worst_rel, worst_line = None, 0.0, ""
    for c in feed.components:
        fed = c.flow_kmol_hr
        out = result.distillate.get(c.name, 0.0) + result.bottoms.get(c.name, 0.0)
        gap = abs(out - fed)
        rel = gap / fed if fed > 0 else (0.0 if gap == 0 else float("inf"))
        if rel > worst_rel:
            worst_name, worst_rel = c.name, rel
            worst_line = (f"{c.name}: in {fed:.4f}, out {out:.4f} kmol/hr "
                          f"({100*rel:.3f}% {'created' if out > fed else 'lost'})")

    if worst_name is None:
        total = sum(c.flow_kmol_hr for c in feed.components)
        return Check("mass balance", True,
                     f"every component closes exactly; {total:.3f} kmol/hr in and out")
    return Check("mass balance", worst_rel < MASS_BALANCE_TOL,
                 f"worst component {worst_line}")


def verify_column(feed: Feed, spec: ColumnSpec, result: ColumnResult) -> list[Check]:
    checks: list[Check] = []

    if not result.converged:
        # Nothing downstream is meaningful, so do not manufacture checks that
        # would "pass" against placeholder zeros.
        return [Check("converged", False,
                      result.error or "simulator did not converge")]
    checks.append(Check("converged", True, "simulator converged, 1 result returned"))

    checks.append(_component_balance(feed, result))

    flows = {c.name: c.flow_kmol_hr for c in feed.components}

    lk_fed = flows[spec.light_key]
    lk_rec = result.distillate.get(spec.light_key, 0.0) / lk_fed
    checks.append(Check(
        "light key recovery",
        abs(lk_rec - spec.lk_recovery_to_distillate) < RECOVERY_TOL,
        f"{spec.light_key}: asked {spec.lk_recovery_to_distillate:.6f}, "
        f"achieved {lk_rec:.6f} to the distillate",
    ))

    hk_fed = flows[spec.heavy_key]
    hk_rec = result.bottoms.get(spec.heavy_key, 0.0) / hk_fed
    checks.append(Check(
        "heavy key recovery",
        abs(hk_rec - spec.hk_recovery_to_bottoms) < RECOVERY_TOL,
        f"{spec.heavy_key}: asked {spec.hk_recovery_to_bottoms:.6f}, "
        f"achieved {hk_rec:.6f} to the bottoms",
    ))

    checks.append(Check(
        "reflux above minimum", result.reflux > result.minimum_reflux,
        f"reflux {result.reflux:.3f}, minimum {result.minimum_reflux:.3f}",
    ))
    return checks
