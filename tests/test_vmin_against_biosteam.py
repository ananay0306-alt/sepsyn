"""Does OUR Underwood reproduce the falling minimum reflux?

On 2026-09-09, BioSTEAM's ShortcutColumn returned a minimum reflux that FELL as
inert heavy non-key was added to the same propane/butane split:

    C3 10, C4 20                   Rmin 1.1324
    C3 10, C4 20, C5 60            Rmin 0.6121
    C3 10, C4 20, C5 60, C6 10     Rmin 0.5339
    C3 10, C4 20, C5 180           Rmin 0.3006

It was never established whether that is a defect in BioSTEAM or a misuse of
it, and this file settles it by running the identical series through our own
implementation, with q as the controlled variable.

THE ANSWER: the fall is the FEED THERMAL CONDITION, not the method.

Every feed in that series sits at a fixed 330 K. Adding heavy pentane raises
the mixture bubble point at 13.69 bar, so the same 330 K feed becomes
progressively more subcooled -- q climbs 1.098 -> 1.381 -> 1.402 -> 1.558. A
subcooled feed condenses vapour on entry and supplies part of the reflux for
free, which lowers what the reboiler has to raise.

Hold q at 1.0 and the series RISES monotonically, which is the direction
physical intuition expects: more heavy non-key means more material to boil past
the light key. Let q float and the series falls. Both behaviours come out of
the same forty lines of Underwood, so neither is a defect in anyone's package.

See docs/findings/2026-09-10-the-falling-rmin-is-the-feed-condition.md
"""
import pytest

from sepsyn.cli import resolve_column_pressure
from sepsyn.feed_condition import feed_condition
from sepsyn.properties import resolve
from sepsyn.types import Component, Feed
from sepsyn.vmin.pipeline import volatilities_for
from sepsyn.vmin.vapour import minimum_vapour

# The 09-09 series, verbatim. BioSTEAM's numbers are recorded for the record;
# nothing here asserts against them, because they were measured under a
# configuration this file is not reproducing.
SERIES = [
    (("Propane", "Butane"), (10.0, 20.0), 1.1324),
    (("Propane", "Butane", "Pentane"), (10.0, 20.0, 60.0), 0.6121),
    (("Propane", "Butane", "Pentane", "Hexane"), (10.0, 20.0, 60.0, 10.0), 0.5339),
    (("Propane", "Butane", "Pentane"), (10.0, 20.0, 180.0), 0.3006),
]


def _case(names, flows):
    feed = Feed(components=tuple(Component(n, resolve(n), f)
                                 for n, f in zip(names, flows)),
                T_K=330.0, P_Pa=101325.0)
    P, _ = resolve_column_pressure(feed, names[0], None)
    alpha, _ = volatilities_for(feed, P)
    fc = feed_condition(feed, P)
    return feed, P, alpha, (fc.q if fc else 1.0)


def rmin(names, flows, q=None):
    """R_min = V_min/D - 1 for the propane/butane split. q=None uses the feed's
    own thermal condition; a number imposes it."""
    _, _, alpha, feed_q = _case(names, flows)
    v = minimum_vapour(tuple(names), alpha, dict(zip(names, flows)),
                       feed_q if q is None else q, k=1)
    return v.V_min_kmol_hr / flows[0] - 1.0


def test_the_whole_series_sits_at_the_SAME_pressure():
    """Propane is the lightest in every case, and it is propane condensing
    against cooling water that sets the pressure. If the pressure moved between
    cases, the alphas would move with it and the series would be comparing four
    different columns."""
    pressures = {round(_case(n, f)[1]) for n, f, _ in SERIES}
    assert len(pressures) == 1


def test_the_feed_gets_MORE_SUBCOOLED_as_heavy_non_key_is_added():
    """The mechanism. Every feed is at 330 K; adding pentane raises the bubble
    point, so the same temperature is further below it each time."""
    qs = [_case(n, f)[3] for n, f, _ in SERIES]
    assert qs == sorted(qs), f"q should rise across the series, got {qs}"
    assert qs[0] > 1.0          # already subcooled at the start
    assert qs[-1] > qs[0] + 0.4  # and substantially more so by the end


def test_at_FIXED_q_the_minimum_reflux_RISES_with_heavy_non_key():
    """The controlled experiment, and the physically expected direction: more
    heavy non-key means more material to boil past the light key.

    This is the assertion that clears Underwood. A method that produced a
    falling minimum reflux here, with the one confounding variable held still,
    would be a method with something wrong in it.
    """
    series = [rmin(n, f, q=1.0) for n, f, _ in SERIES]
    assert series == sorted(series), (
        f"at q=1.0 the minimum reflux should rise, got {series}")


def test_at_the_feeds_OWN_q_the_minimum_reflux_FALLS_just_as_BioSTEAM_did():
    """Same equations, same code, only q released. Our own implementation
    reproduces the direction of the 09-09 measurement, which means that
    measurement was never evidence of a defect in ShortcutColumn."""
    series = [rmin(n, f) for n, f, _ in SERIES]
    assert series == sorted(series, reverse=True), (
        f"at the feeds' own q the minimum reflux should fall, got {series}")


def test_q_is_the_ONLY_variable_that_changed_the_direction():
    """Both series are computed from the same alphas, the same pressure and the
    same flows. Nothing but q differs between them, so nothing but q can
    explain the reversal."""
    fixed = [rmin(n, f, q=1.0) for n, f, _ in SERIES]
    floating = [rmin(n, f) for n, f, _ in SERIES]
    assert fixed[0] > floating[0]        # even the binary is subcooled
    assert fixed[-1] > floating[-1] * 4  # and the effect grows with subcooling


def test_minimum_reflux_never_goes_negative():
    """The one result that would be unambiguously wrong under any q. A negative
    minimum reflux is not a physical quantity."""
    for names, flows, _ in SERIES:
        assert rmin(names, flows) > 0.0
        assert rmin(names, flows, q=1.0) > 0.0
