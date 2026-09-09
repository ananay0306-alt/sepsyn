"""Exposure counting. How many columns does a tagged component pass through?

Counted, never enforced. Eliminating above a threshold would need a number
nothing justifies, and a materials cost multiplier would need a factor the tool
has no source for. Both bury an invented value inside a verdict. The count is
reported beside the cost and the reader resolves the trade-off.

FLOW WEIGHTED, and these tests are why. A plain column count saturates: sharp
splits are imperfect, so a trace of every component propagates almost
everywhere, and hexane scores 3 columns in both the direct sequence that
carries it at full flow throughout and the indirect one that removes it
immediately. Weighting by flow separates them without inventing a threshold.
"""
import pytest

from sepsyn.properties import resolve
from sepsyn.sequencing.evaluate import evaluate_sequence
from sepsyn.sequencing.train import Node
from sepsyn.simulators.biosteam_adapter import BioSteamSimulator
from sepsyn.types import Component, Feed

ORDER = ("Propane", "Butane", "Pentane", "Hexane")


def alkane_feed():
    return Feed(
        components=tuple(Component(n, resolve(n), f)
                         for n, f in zip(ORDER, (40.0, 30.0, 20.0, 10.0))),
        T_K=330.0, P_Pa=101325.0,
    )


def direct():
    """Lightest off first, one at a time. Hexane reaches the last column."""
    return Node(group=ORDER, k=1,
                light=Node(group=("Propane",)),
                heavy=Node(group=("Butane", "Pentane", "Hexane"), k=1,
                           light=Node(group=("Butane",)),
                           heavy=Node(group=("Pentane", "Hexane"), k=1,
                                      light=Node(group=("Pentane",)),
                                      heavy=Node(group=("Hexane",)))))


def indirect():
    """Heaviest off first. Hexane leaves at column one."""
    return Node(group=ORDER, k=3,
                light=Node(group=("Propane", "Butane", "Pentane"), k=2,
                           light=Node(group=("Propane", "Butane"), k=1,
                                      light=Node(group=("Propane",)),
                                      heavy=Node(group=("Butane",))),
                           heavy=Node(group=("Pentane",))),
                heavy=Node(group=("Hexane",)))


def test_no_tags_means_no_exposure_reported():
    out = evaluate_sequence(BioSteamSimulator(), alkane_feed(), direct())
    assert out.exposure == {}


def test_a_tagged_component_is_counted_through_every_column_it_enters():
    """Hexane enters all three columns of the direct sequence at essentially
    full flow: it is only removed at the last one. 10 kmol/hr, three times."""
    tags = {"Hexane": frozenset({"corrosive"})}
    out = evaluate_sequence(BioSteamSimulator(), alkane_feed(), direct(),
                            tags=tags)
    assert out.exposure["Hexane"] == pytest.approx(30.0, rel=0.02)
    assert out.exposure_columns == {"Hexane": 3}


def test_removing_it_early_lowers_the_count():
    """THE point of the whole feature. Taking hexane off first exposes one
    column instead of three, and that difference is the trade-off against
    cost."""
    tags = {"Hexane": frozenset({"corrosive"})}
    direct_out = evaluate_sequence(BioSteamSimulator(), alkane_feed(),
                                   direct(), tags=tags)
    indirect_out = evaluate_sequence(BioSteamSimulator(), alkane_feed(),
                                     indirect(), tags=tags)
    # The column COUNT cannot tell these apart: the 1% of hexane that goes
    # overhead at the first column propagates onward, so both score 3. This is
    # exactly why exposure is weighted by flow.
    assert indirect_out.exposure_columns["Hexane"] == 3
    assert direct_out.exposure_columns["Hexane"] == 3
    # The flow-weighted figure separates them by roughly threefold.
    assert indirect_out.exposure["Hexane"] < 11.0
    assert direct_out.exposure["Hexane"] > 28.0


def test_exposure_does_NOT_eliminate_or_change_the_cost():
    """Counted, not enforced. Both sequences remain feasible and their costs
    are identical with and without the tag."""
    tags = {"Hexane": frozenset({"corrosive"})}
    plain = evaluate_sequence(BioSteamSimulator(), alkane_feed(), direct())
    tagged = evaluate_sequence(BioSteamSimulator(), alkane_feed(), direct(),
                               tags=tags)
    assert tagged.feasible and plain.feasible
    assert tagged.total_cost_USD_yr == pytest.approx(plain.total_cost_USD_yr)


def test_a_trace_carried_forward_still_counts_as_exposure():
    """Propane is nominally removed at column one, but 1% of it goes into the
    bottoms and travels on. The metal downstream sees it, so it counts."""
    tags = {"Propane": frozenset({"corrosive"})}
    out = evaluate_sequence(BioSteamSimulator(), alkane_feed(), direct(),
                            tags=tags)
    assert out.exposure_columns["Propane"] > 1, (
        "propagated impurity reaches downstream columns and must be counted")
    # But it is a trace, and the flow weighting says so: 40 kmol/hr through the
    # first column, then 0.4 through each of the others.
    assert out.exposure["Propane"] < 42.0


def test_several_tagged_components_are_counted_separately():
    tags = {"Propane": frozenset({"corrosive"}),
            "Hexane": frozenset({"hazardous"})}
    out = evaluate_sequence(BioSteamSimulator(), alkane_feed(), direct(),
                            tags=tags)
    assert set(out.exposure) == {"Propane", "Hexane"}
