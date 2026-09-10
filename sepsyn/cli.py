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


def resolve_column_pressure(feed: Feed, light_key: str | None,
                            column_P_Pa: float | None) -> tuple[float, str]:
    """Settle the column pressure BEFORE anything is evaluated at it.

    Raised in review, and it invalidated the ordering this tool inherited:
    relative volatility is a property of a pair AT a condition, so screening
    cannot precede the pressure decision. Screening used to run at the FEED
    pressure while the column was later designed somewhere else entirely. On
    propane/n-butane that reported alpha 6.100 for a column that actually runs
    at 13.69 bar with alpha 3.383 -- an 80 percent error in the headline
    screening number.

    Three outcomes, kept distinct because they are three different things the
    tool knows:

      specified  the user fixed it, so the pressure heuristic does not run at
                 all. This is the reviewer's point: a heuristic for a value
                 the user has already given is not skipped, it is DISABLED
      derived    no pressure was given, so the cooling-water heuristic chose one
      fallback   no pressure and no light key, so there is nothing to condense
                 against and the pressure cannot be settled. The feed pressure
                 is used and SAID to be unsettled, rather than a feed-pressure
                 alpha being presented as a column alpha
    """
    if column_P_Pa is not None:
        return column_P_Pa, (
            f"specified as {column_P_Pa/1e5:.3f} bar; the pressure heuristic "
            f"was not run"
        )
    if light_key is None:
        return feed.P_Pa, (
            f"feed pressure {feed.P_Pa/1e5:.3f} bar used because the column "
            f"pressure has not been settled: without a light key there is "
            f"nothing to condense against. Name the keys, or give a pressure"
        )
    from sepsyn.design import choose_pressure

    pressure, note = choose_pressure(feed, light_key)
    return pressure, f"derived, {note}"


def screen(feed: Feed, light_key: str | None = None,
           heavy_key: str | None = None,
           column_P_Pa: float | None = None):
    """Property record, all verdicts, and the overall answer.

    The keys are optional but they MUST be forwarded when the user gave them.
    Without them the record leaves light_key_mole_fraction,
    heavy_key_mole_fraction and bottoms_T_at_column_P as None, and since
    safe_eval treats any comparison against None as False, every rule naming
    those properties silently cannot fire. R-07 and R-08 were unreachable from
    the CLI for exactly this reason.

    Every property is evaluated at the COLUMN pressure, which is settled first.
    See resolve_column_pressure.
    """
    pressure, basis = resolve_column_pressure(feed, light_key, column_P_Pa)
    record = build_property_record(feed, column_P_Pa=pressure,
                                   light_key=light_key, heavy_key=heavy_key,
                                   column_P_basis=basis)
    verdicts = evaluate(load_rules(), record)
    return record, verdicts, overall_verdict(verdicts)


def design_if_feasible(feed: Feed, light_key: str, heavy_key: str,
                       lk_recovery: float = 0.99, hk_recovery: float = 0.99,
                       distillate_purity: float | None = None,
                       bottoms_impurity: float | None = None,
                       feed_q: float | None = None,
                       column_P_Pa: float | None = None):
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

    from sepsyn.design import best_point, recoveries_for_purity, sweep_reflux
    from sepsyn.equipment import DesignContext, choose_equipment
    from sepsyn.properties import (COOLING_WATER_T, boiling_point,
                                   condensing_temperature, count_supercritical)
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

    # The SAME resolution screening used. Deriving it twice invites the two to
    # disagree, and a design built at a pressure the screening never saw is the
    # bug this function was just fixed for.
    pressure, _basis = resolve_column_pressure(feed, light_key, column_P_Pa)

    # Equipment choices are settled in TWO passes, and the split is forced by
    # the physics rather than chosen for tidiness. Step 22 must be decided
    # BEFORE the column is built, because the adapter needs the condenser type
    # to build it. Step 24 cannot be decided until AFTER, because it keys on a
    # diameter that does not exist until the column has been sized.
    n_super = count_supercritical(feed)
    bottoms_T = condensing_temperature(heavy_key, pressure)
    lightest = min(feed.components, key=lambda c: boiling_point(c.cas))
    before = DesignContext(pressure_Pa=pressure, n_supercritical_at_feed=n_super,
                           bottoms_T_at_column_P=bottoms_T,
                           condensing_T_at_column_P=condensing_temperature(
                               lightest.name, pressure),
                           cooling_water_T=COOLING_WATER_T,
                           feed_q=feed_q)
    condenser = next(d for d in choose_equipment(before) if d.step == 22)

    spec = ColumnSpec(light_key, heavy_key, lk_recovery, hk_recovery, pressure,
                      condenser_type=condenser.choice or "total",
                      feed_q=feed_q)
    sim = BioSteamSimulator()

    def equipment_record(result) -> list:
        """The decisions as they stand once the column is sized.

        Step 22 is deliberately carried over from the pre-design pass rather
        than recomputed. That decision is what BOUND the simulation, and a
        record that recomputes it could describe a condenser the column never
        had -- which is the 58 percent discrepancy, rebuilt.
        """
        after = DesignContext(
            pressure_Pa=pressure, n_supercritical_at_feed=n_super,
            bottoms_T_at_column_P=bottoms_T,
            condensing_T_at_column_P=before.condensing_T_at_column_P,
            cooling_water_T=COOLING_WATER_T,
            feed_q=result.feed_q if result is not None else feed_q,
            stages=result.stages if result is not None else None,
            column_diameter_m=(result.column_diameter_m
                               if result is not None else None),
        )
        return [condenser if d.step == 22 else d
                for d in choose_equipment(after)]

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
        return (spec, points, None, failed, verify_column(feed, spec, failed),
                unseparated, equipment_record(failed))

    spec = replace(spec, reflux_over_minimum=best.k)
    result = sim.design_column(feed, spec)
    checks = verify_column(feed, spec, result)
    return (spec, points, best, result, checks, unseparated,
            equipment_record(result))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="sepsyn",
        description="Screen a feed for separation feasibility, showing the rule that decided it.",
    )
    p.add_argument("--feed", required=True, help="e.g. 'Methanol:100,Water:80'")
    p.add_argument("--T", type=float, default=298.15, help="feed temperature, K")
    p.add_argument("--P", type=float, default=101325.0, help="feed pressure, Pa")
    p.add_argument("--column-P", type=float,
                   help="column operating pressure, Pa. Giving it DISABLES the "
                        "cooling-water pressure heuristic rather than running "
                        "it and overriding the answer. Omit to let the tool "
                        "settle the pressure; either way every property is "
                        "evaluated at the pressure that ends up being used")
    p.add_argument("--out", help="also write the printed report to this file")
    p.add_argument("--json", dest="json_path",
                   help="write the whole run as structured data: the pressure "
                        "and its basis, q and whether it was imposed, every "
                        "rule fired or not, the equipment choices with their "
                        "status, and every verification check. This is what "
                        "makes two runs comparable rather than merely readable")
    p.add_argument("--html", dest="html_path",
                   help="write the run as a self-contained HTML page: the cost "
                        "curve plotted with its optimum marked, the assumptions "
                        "it made, every rule, and the verification checks. No "
                        "network needed to open it")
    p.add_argument("--vmin", action="store_true",
                   help="choose the separation sequence by MINIMUM VAPOUR, "
                        "found exactly by dynamic programming rather than by "
                        "enumerating and costing. Needs no cost data, scales "
                        "to a dozen components, and returns the provable "
                        "optimum. Requires --order")
    p.add_argument("--sequence", action="store_true",
                   help="enumerate every sharp-split sequence for a "
                        "multicomponent feed, design each one, and report the "
                        "cheapest. Requires --order")
    p.add_argument("--order",
                   help="component names lightest to heaviest, comma "
                        "separated, e.g. 'Propane,Butane,Pentane'. Volatility "
                        "order is what makes a split sharp, so it is required "
                        "rather than guessed from boiling points")
    p.add_argument("--tag", action="append", default=[],
                   help="mark a component, e.g. --tag HCl:corrosive. Counted "
                        "and reported, never used to rank or eliminate. "
                        "Repeatable")
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

    printed: list[str] = []

    def emit(text: str = "") -> None:
        """Print and remember. --out must save what the user actually saw, not
        a second rendering that could drift from it."""
        printed.append(text)
        print(text)

    record, verdicts, overall = screen(feed, args.light_key, args.heavy_key,
                                       column_P_Pa=args.column_P)
    emit(format_report(feed, record, verdicts, overall, explain=args.explain))
    designed = None

    def save() -> None:
        if args.out:
            with open(args.out, "w") as fh:
                fh.write("\n".join(printed).rstrip() + "\n")
        if args.json_path or args.html_path:
            from sepsyn.serialize import run_to_dict, write_json
            payload = run_to_dict(feed, record, verdicts, overall, designed)
            if args.json_path:
                write_json(args.json_path, payload)
            if args.html_path:
                from sepsyn.htmlreport import write_html
                write_html(args.html_path, payload)

    if args.vmin:
        if not args.order:
            emit("\n--vmin requires --order, the component names from "
                 "lightest to heaviest")
            save()
            return 2
        order = tuple(n.strip() for n in args.order.split(","))
        missing = [n for n in order if n not in feed.names]
        if missing:
            emit(f"\n--vmin --order names components that are not in the "
                 f"feed: {', '.join(missing)}")
            save()
            return 2
        from sepsyn.feed_condition import feed_condition
        from sepsyn.sequencing.score import score_proxies_against_vmin
        from sepsyn.simulators.biosteam_adapter import BioSteamSimulator
        from sepsyn.vmin.pipeline import select_and_verify, volatilities_for
        from sepsyn.vmin.report import format_vmin
        from sepsyn.vmin.sequence import NoFeasibleSequence

        column_P, _ = resolve_column_pressure(feed, order[0], args.column_P)
        try:
            selection, outcome = select_and_verify(
                BioSteamSimulator(), feed, order, column_P)
        except (NoFeasibleSequence, ValueError) as exc:
            emit(f"\nNo sequence could be selected: {exc}")
            save()
            return 1
        alpha, _ = volatilities_for(feed, column_P)
        flows = {c.name: c.flow_kmol_hr for c in feed.components}
        fc = feed_condition(feed, column_P)
        q = fc.q if fc is not None else 1.0
        scores = score_proxies_against_vmin(
            feed, order, alpha, flows, q, selection, column_P)
        emit()
        emit(format_vmin(selection, outcome, scores, order))
        save()
        return 0

    if args.sequence:
        if not args.order:
            emit("\n--sequence requires --order, the component names from "
                 "lightest to heaviest")
            save()
            return 2
        order = tuple(n.strip() for n in args.order.split(","))
        missing = [n for n in order if n not in feed.names]
        if missing:
            emit(f"\n--order names components that are not in the feed: "
                 f"{', '.join(missing)}")
            save()
            return 2
        from sepsyn.sequencing.rank import sweep
        from sepsyn.sequencing.report import format_sequencing
        from sepsyn.sequencing.score import score_proxies
        from sepsyn.sequencing.tags import UnknownTag, parse_tags
        from sepsyn.simulators.biosteam_adapter import BioSteamSimulator
        try:
            tags = parse_tags(args.tag, feed.names)
        except UnknownTag as exc:
            emit(f"\n{exc}")
            save()
            return 2
        ranking = sweep(BioSteamSimulator(), feed, order, tags=tags or None)
        card = score_proxies(feed, order, ranking, feed.P_Pa)
        emit()
        emit(format_sequencing(ranking, card, tags))
        save()
        return 0

    if args.design:
        if overall not in ("feasible", "caution"):
            emit(f"\nNot designing: screening returned {overall.upper()}.")
            save()
            return 0
        if not (args.light_key and args.heavy_key):
            emit("\n--design requires --light-key and --heavy-key")
            save()
            return 2
        from sepsyn.report import format_design
        try:
            out = design_if_feasible(
                feed, args.light_key, args.heavy_key,
                args.lk_recovery, args.hk_recovery,
                distillate_purity=args.distillate_purity,
                bottoms_impurity=args.bottoms_impurity,
                feed_q=args.feed_q,
                column_P_Pa=args.column_P)
        except ValueError as exc:
            emit(f"\nCannot design: {exc}")
            save()
            return 2
        designed = out
        emit()
        emit(format_design(*out))
    save()
    return 0


if __name__ == "__main__":
    sys.exit(main())
