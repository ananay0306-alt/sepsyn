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
