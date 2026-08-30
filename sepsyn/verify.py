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

# Condenser duty divided by the overhead vapour it condenses is a molar latent
# heat, and for ordinary organics that lands between about 20 and 50 kJ/mol.
# The band is wide on purpose: it is not measuring latent heat, it is catching
# a duty of the wrong SHAPE. A partial condenser condenses only the reflux and
# so does roughly R/(R+1) of the work, landing well under the floor. That exact
# mismatch produced a 58% disagreement between two simulators and nothing
# detected it.
LATENT_HEAT_FLOOR_J_MOL = 20_000.0
LATENT_HEAT_CEILING_J_MOL = 50_000.0
# Measured, not chosen. BioSTEAM's reboiler duty sits a CONSTANT 5.00 % above
# the value that closes the balance against stream enthalpies -- measured at
# exactly 5.00 % on methanol/water/glycerol, methanol/water, benzene/toluene,
# and again at a different reflux ratio. Four cases, one number, so it is a
# systematic margin in the model rather than model error. The tolerance sits
# just above it: anything materially past 6 % is something new and worth
# reading, while a real defect such as a partial condenser mistaken for a total
# one moves this by tens of percent and is still caught easily.
ENERGY_BALANCE_TOL = 0.06    # relative to reboiler duty


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

    # Everything below tests a PREDICTED quantity. The checks above largely test
    # imposed ones: a recovery the simulator was told to hit will be hit, so it
    # cannot fail unless something upstream is badly wrong.
    checks.extend(_thermal_checks(result))
    return checks


def _thermal_checks(result: ColumnResult) -> list[Check]:
    """Duty, end temperatures and energy balance, each SKIPPED when the
    simulator did not report the inputs it needs. Absent is not wrong, and a
    spurious FAIL on a capable-but-quiet adapter would train the reader to
    ignore failures."""
    out: list[Check] = []

    D = sum(result.distillate.values())
    if result.condenser_duty_kW is not None and D > 0:
        V_mol_s = (result.reflux + 1.0) * D * 1000.0 / 3600.0   # V = (R+1)D
        per_mol = result.condenser_duty_kW * 1000.0 / V_mol_s
        out.append(Check(
            "condenser duty",
            LATENT_HEAT_FLOOR_J_MOL <= per_mol <= LATENT_HEAT_CEILING_J_MOL,
            f"{result.condenser_duty_kW:.1f} kW over {V_mol_s*3.6:.1f} kmol/hr "
            f"of overhead vapour = {per_mol/1000:.1f} kJ/mol (expected "
            f"{LATENT_HEAT_FLOOR_J_MOL/1000:.0f} to "
            f"{LATENT_HEAT_CEILING_J_MOL/1000:.0f}; under the floor usually "
            f"means a partial condenser)",
        ))

    if result.distillate_T_K is not None and result.bottoms_T_K is not None:
        ordered = result.distillate_T_K < result.bottoms_T_K
        # Ordering only. Comparing each end against its key's boiling point
        # needs thermodynamics, and this module deliberately has none: it takes
        # a result and does arithmetic on it.
        out.append(Check(
            "end temperatures", ordered,
            f"distillate {result.distillate_T_K:.1f} K, bottoms "
            f"{result.bottoms_T_K:.1f} K"
            + ("" if ordered else " -- inverted, the overhead cannot be hotter "
                                  "than the bottoms"),
        ))

    if None not in (result.reboiler_duty_kW, result.condenser_duty_kW,
                    result.feed_H_kW, result.distillate_H_kW,
                    result.bottoms_H_kW):
        net_heat = result.reboiler_duty_kW - result.condenser_duty_kW
        net_enthalpy = (result.distillate_H_kW + result.bottoms_H_kW
                        - result.feed_H_kW)
        gap = abs(net_heat - net_enthalpy)
        scale = abs(result.reboiler_duty_kW) or 1.0
        out.append(Check(
            "energy balance", gap / scale < ENERGY_BALANCE_TOL,
            f"reboiler minus condenser {net_heat:.1f} kW against a product "
            f"minus feed enthalpy of {net_enthalpy:.1f} kW "
            f"({100*gap/scale:.2f}% of reboiler duty)",
        ))
    return out
