"""Command line entry point."""
import argparse
import sys

from sepsyn.engine import evaluate, load_rules, overall_verdict
from sepsyn.properties import build_property_record, resolve
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


def screen(feed: Feed):
    """Property record, all verdicts, and the overall answer."""
    record = build_property_record(feed)
    verdicts = evaluate(load_rules(), record)
    return record, verdicts, overall_verdict(verdicts)


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
    args = p.parse_args(argv)

    feed = parse_feed(args.feed, args.T, args.P)
    record, verdicts, overall = screen(feed)
    print(format_report(feed, record, verdicts, overall, explain=args.explain))
    return 0


if __name__ == "__main__":
    sys.exit(main())
