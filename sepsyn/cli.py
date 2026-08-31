"""Command line entry point."""
import argparse
import sys

from sepsyn.engine import evaluate, load_rules, overall_verdict
from sepsyn.properties import UnknownChemical, build_property_record, resolve
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


def screen(feed: Feed, light_key: str | None = None,
           heavy_key: str | None = None):
    """Property record, all verdicts, and the overall answer.

    The keys are optional but they MUST be forwarded when the user gave them.
    Without them the record leaves light_key_mole_fraction,
    heavy_key_mole_fraction and bottoms_T_at_column_P as None, and since
    safe_eval treats any comparison against None as False, every rule naming
    those properties silently cannot fire. R-07 and R-08 were unreachable from
    the CLI for exactly this reason.
    """
    record = build_property_record(feed, light_key=light_key,
                                   heavy_key=heavy_key)
    verdicts = evaluate(load_rules(), record)
    return record, verdicts, overall_verdict(verdicts)


def design_if_feasible(feed: Feed, light_key: str, heavy_key: str,
                       lk_recovery: float = 0.99, hk_recovery: float = 0.99,
                       distillate_purity: float | None = None,
                       bottoms_impurity: float | None = None,
                       feed_q: float | None = None):
    """Design the column and report what the specification did NOT cover.

    Recoveries may be given directly, or TOTAL-stream purities may be given and
    converted. The conversion is explicit because the two are different
    specifications: 99% recovery asks how much of the light key fed goes
    overhead, 99 mol% purity asks how much of the overhead is light key.
    Substituting one for the other misses the target by ~0.002 on the milestone
    feed, which is the same magnitude as the basis error this project exists to
    avoid.
    """
    from dataclasses import replace

    from sepsyn.design import (best_point, choose_pressure, recoveries_for_purity,
                               sweep_reflux)
    from sepsyn.simulators.base import ColumnResult, ColumnSpec
    from sepsyn.simulators.biosteam_adapter import BioSteamSimulator
    from sepsyn.verify import verify_column

    if distillate_purity is not None or bottoms_impurity is not None:
        if distillate_purity is None or bottoms_impurity is None:
            raise ValueError(
                "give both distillate_purity and bottoms_impurity, or neither"
            )
        lk_recovery, hk_recovery = recoveries_for_purity(
            feed, light_key, heavy_key, distillate_purity, bottoms_impurity)

    pressure, _note = choose_pressure(feed, light_key)
    spec = ColumnSpec(light_key, heavy_key, lk_recovery, hk_recovery, pressure,
                      feed_q=feed_q)
    sim = BioSteamSimulator()

    # Anything that is neither key has no specification constraining it.
    unseparated = [n for n in feed.names if n not in (light_key, heavy_key)]

    points = sweep_reflux(sim, feed, spec)
    try:
        best = best_point(points)
    except ValueError:
        # Every reflux failed. Return that as data, with the reasons, rather
        # than raising -- the sweep is exactly where infeasibility shows up.
        why = "; ".join(f"k={p.k}: {p.error}" for p in points if not p.converged)
        failed = ColumnResult({}, {}, 0.0, 0.0, 0.0, 0.0, 0.0, False,
                              error=f"no reflux multiple produced a design. {why}")
        return spec, points, None, failed, verify_column(feed, spec, failed), unseparated

    spec = replace(spec, reflux_over_minimum=best.k)
    result = sim.design_column(feed, spec)
    checks = verify_column(feed, spec, result)
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
    p.add_argument("--lk-recovery", type=float, default=0.99,
                   help="fraction of the light key fed that leaves overhead")
    p.add_argument("--hk-recovery", type=float, default=0.99,
                   help="fraction of the heavy key fed that leaves in the bottoms")
    p.add_argument("--distillate-purity", type=float,
                   help="light key mole fraction of the TOTAL distillate; "
                        "converted to recoveries, use with --bottoms-impurity")
    p.add_argument("--bottoms-impurity", type=float,
                   help="light key mole fraction of the TOTAL bottoms")
    p.add_argument("--feed-q", type=float,
                   help="impose the feed thermal condition at the column "
                        "pressure: 1 saturated liquid, 0 saturated vapour, "
                        ">1 subcooled, <0 superheated. Omit to take the feed "
                        "as it arrives -- omitting is NOT the same as 1.0, "
                        "and either way the q used is reported")
    args = p.parse_args(argv)

    try:
        feed = parse_feed(args.feed, args.T, args.P)
    except (UnknownChemical, ValueError) as exc:
        # resolve() already assembled near-match suggestions; a traceback is the
        # one presentation that makes them read as a crash rather than an answer.
        print(f"sepsyn: {exc}", file=sys.stderr)
        return 2

    record, verdicts, overall = screen(feed, args.light_key, args.heavy_key)
    print(format_report(feed, record, verdicts, overall, explain=args.explain))

    if args.design:
        if overall not in ("feasible", "caution"):
            print(f"\nNot designing: screening returned {overall.upper()}.")
            return 0
        if not (args.light_key and args.heavy_key):
            print("\n--design requires --light-key and --heavy-key")
            return 2
        from sepsyn.report import format_design
        try:
            out = design_if_feasible(
                feed, args.light_key, args.heavy_key,
                args.lk_recovery, args.hk_recovery,
                distillate_purity=args.distillate_purity,
                bottoms_impurity=args.bottoms_impurity,
                feed_q=args.feed_q)
        except ValueError as exc:
            print(f"\nCannot design: {exc}")
            return 2
        print()
        print(format_design(*out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
