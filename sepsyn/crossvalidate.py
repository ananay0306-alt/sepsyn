"""How far is sepsyn's shortcut design from a rigorous column? M2, Task 6.

A gap is reported only when every configuration assertion holds. Otherwise the
comparison says it cannot attribute the difference and names the assertion
that blocked it. That is the honest answer, and the one the 08-27 findings
were paid for: a 58 % condenser and a 43 % stage disagreement both turned out
to be bookkeeping, not physics.

Products are deliberately not reported. Recovery specs impose them on both
sides, so agreement there is evidence of nothing. Only the unimposed numbers
carry information: the two duties and the two end temperatures. DWSIM's reflux
is not read back by the transport, so reflux is not compared, and the report
says so rather than leaving it out silently.

Relative gaps are signed, (sepsyn - DWSIM) / DWSIM. Whether the shortcut over-
or under-predicts a duty is design information that an absolute value throws
away. Temperatures are compared in kelvin, because a percentage of an absolute
temperature is a number that looks small whatever it is.
"""
import math
from dataclasses import dataclass

from sepsyn.simulators.conventions import dwsim_feed_stage, dwsim_stage_count
from sepsyn.simulators.equivalence import (
    UNATTRIBUTED, Assertion, can_report_gap, check_equivalence)

# The identity feed-stage mapping was established on a binary. On the
# multicomponent (Kirkbride) column it was not: the 11-07 sweep put DWSIM's
# best feed one stage lower, so part of any multicomponent gap is placement.
MULTICOMPONENT_FEED_STAGE = (
    "feed stage placement: the mapping was measured on a binary column. On "
    "the 4-component alkane column DWSIM's best feed was index 7, not the "
    "mapped 6, worth 1.7 % of reboiler duty (11-07 sweep)"
)

NOT_COMPARED = (
    "reflux ratio: the DWSIM transport does not read it back",
)


@dataclass(frozen=True)
class Gap:
    quantity: str
    sepsyn: float
    dwsim: float
    unit: str
    relative: float | None
    """(sepsyn - DWSIM) / DWSIM, signed. None for temperatures."""

    @property
    def difference(self) -> float:
        return self.sepsyn - self.dwsim


@dataclass(frozen=True)
class Comparison:
    assertions: tuple[Assertion, ...]
    gaps: tuple[Gap, ...]
    reportable: bool
    unattributed: tuple[str, ...]
    dwsim_stages: int | None = None
    dwsim_feed_stage: int | None = None


# Vapour fractions within this are the same feed. q and vapour fraction are
# measured on different property packages, so exact agreement is not expected;
# the failure this exists to catch is a whole phase apart.
FEED_STATE_TOLERANCE = 0.05


def _feed_condition(spec, design, run) -> Assertion:
    """Do the two tools see the same feed? Measured on both sides.

    An imposed q on the sepsyn side is a different feed from the one DWSIM is
    handed, so it blocks. Otherwise sepsyn's q at column pressure gives the
    vapour fraction it is modelling (1 - q, clipped to [0, 1]), and DWSIM's
    flashed feed is read back. The previous check said "both sides take the
    feed as it arrives", which held by construction: on 11-08 it passed a feed
    BioSTEAM kept liquid and DWSIM flashed to all vapour.
    """
    if spec.feed_q is not None:
        return Assertion("feed condition", False,
                         f"sepsyn imposes q = {spec.feed_q}, DWSIM takes the "
                         f"feed as it arrives; that is a different feed")
    q, vf = design.feed_q, run.feed_vapour_fraction
    if q is None or vf is None:
        return Assertion(
            "feed condition", None,
            f"feed state not measured on both sides (sepsyn q = {q}, DWSIM "
            f"vapour fraction = {vf})")
    ours = min(1.0, max(0.0, 1.0 - q))
    ok = abs(ours - vf) <= FEED_STATE_TOLERANCE
    return Assertion(
        "feed condition", ok,
        f"sepsyn q = {q:.3f} (vapour fraction {ours:.2f}), DWSIM vapour "
        f"fraction {vf:.2f}" + ("" if ok else
        ". The tools are modelling different feeds; BioSTEAM keeps the stream "
        "it is handed while DWSIM flashes it at column pressure"))


def _refused(*assertions: Assertion) -> Comparison:
    return Comparison(assertions=tuple(assertions), gaps=(), reportable=False,
                      unattributed=UNATTRIBUTED)


def compare(feed, spec, biosteam_sim, dwsim_sim) -> Comparison:
    design_fn = (biosteam_sim.design_column if len(feed.components) == 2
                 else biosteam_sim.design_multicomponent)
    design = design_fn(feed, spec)
    if not design.converged:
        return _refused(Assertion("sepsyn design", False,
                                  f"sepsyn did not design this column: "
                                  f"{design.error}"))
    if design.theoretical_stages is None or design.theoretical_feed_stage is None:
        return _refused(Assertion(
            "stage count", None,
            "BioSTEAM did not report a theoretical stage count and feed stage, "
            "so there is no column to hand to DWSIM"))

    try:
        stages = dwsim_stage_count(design.theoretical_stages,
                                   spec.condenser_type)
        feed_stage = dwsim_feed_stage(design.theoretical_feed_stage,
                                      design.theoretical_stages)
    except ValueError as exc:
        return _refused(Assertion("stage count", None, str(exc)))

    unattributed = UNATTRIBUTED + (
        (MULTICOMPONENT_FEED_STAGE,) if len(feed.components) > 2 else ())
    run = dwsim_sim.design_from_stages(feed, spec, stages, feed_stage)
    assertions = (_feed_condition(spec, design, run),) + check_equivalence(
        spec, design, stages, feed_stage, run)
    duties = (
        ("condenser duty", design.condenser_duty_kW, run.condenser_duty_kW),
        ("reboiler duty", design.reboiler_duty_kW, run.reboiler_duty_kW))
    temperatures = (
        ("distillate temperature", design.distillate_T_K, run.distillate_T_K),
        ("bottoms temperature", design.bottoms_T_K, run.bottoms_T_K))
    assertions += (_values_usable(duties, temperatures),)
    if not can_report_gap(assertions):
        return Comparison(assertions, (), False, unattributed,
                          stages, feed_stage)

    gaps = [Gap(name, ours, abs(theirs), "kW",
                (ours - abs(theirs)) / abs(theirs))
            for name, ours, theirs in duties]
    gaps += [Gap(name, ours, theirs, "K", None)
             for name, ours, theirs in temperatures]
    return Comparison(assertions, tuple(gaps), True, unattributed,
                      stages, feed_stage)


def _values_usable(duties, temperatures) -> Assertion:
    """Every compared number must exist and be finite, and a converged
    column's duty cannot be zero. Dropping a bad one quietly would leave a
    reportable comparison the reader takes as agreement on that quantity."""
    bad = []
    for name, ours, theirs in duties + temperatures:
        for side, v in (("sepsyn", ours), ("DWSIM", theirs)):
            if v is None or not math.isfinite(v):
                bad.append(f"{side} {name} is {v}")
            elif "duty" in name and v == 0:
                bad.append(f"{side} {name} is 0 kW, which a working column "
                           f"cannot have")
    return Assertion("compared values", not bad,
                     "; ".join(bad) if bad else
                     "both duties and both end temperatures present on "
                     "both sides")


def format_comparison(c: Comparison) -> str:
    lines = ["CONFIGURATION"]
    for a in c.assertions:
        state = {True: "holds", False: "FAILS", None: "UNKNOWN"}[a.holds]
        lines.append(f"  {a.name:<22}{state:<9}{a.detail}")
    if c.dwsim_stages is not None:
        lines.append(f"  DWSIM column: {c.dwsim_stages} stages, feed at index "
                     f"{c.dwsim_feed_stage} (0 = condenser)")
    lines.append("")
    if c.reportable:
        lines.append("GAP  sepsyn shortcut against DWSIM rigorous, signed")
        for g in c.gaps:
            if g.relative is None:
                lines.append(f"  {g.quantity:<24}{g.sepsyn:>10.1f}{g.dwsim:>10.1f}"
                             f" {g.unit}   {g.difference:+.1f} {g.unit}")
            else:
                lines.append(f"  {g.quantity:<24}{g.sepsyn:>10.1f}{g.dwsim:>10.1f}"
                             f" {g.unit}  {g.relative * 100:+.1f} %")
        for item in NOT_COMPARED:
            lines.append(f"  not compared: {item}")
    else:
        failing = [a.name for a in c.assertions if a.holds is not True]
        lines.append("NO GAP REPORTED")
        lines.append(f"  The columns cannot be shown to be the same column: "
                     f"{', '.join(failing)}.")
        lines.append("  A number reported now could not be attributed to "
                     "shortcut error.")
    lines.append("")
    lines.append("UNATTRIBUTED, in every number above")
    for u in c.unattributed:
        lines.append(f"  {u}")
    return "\n".join(lines)
