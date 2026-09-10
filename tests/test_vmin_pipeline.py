"""Real volatilities, and select-then-verify.

Stage 1 chooses a sequence by minimum vapour under sharp splits. Stage 2 hands
that ONE sequence to M3's evaluator, which propagates real products, screens
every column and honours undetermined.
"""
import pytest

from sepsyn.properties import resolve
from sepsyn.sequencing.enumeration import label
from sepsyn.simulators.biosteam_adapter import BioSteamSimulator
from sepsyn.types import Component, Feed
from sepsyn.vmin.pipeline import select_and_verify, volatilities_for

ORDER = ("Propane", "Butane", "Pentane", "Hexane")
ALKANE_P = 1369410.0     # measured: resolve_column_pressure on this feed


def alkane_feed(flows=(10.0, 20.0, 60.0, 10.0), T_K=330.0):
    return Feed(components=tuple(Component(n, resolve(n), f)
                                 for n, f in zip(ORDER, flows)),
                T_K=T_K, P_Pa=101325.0)


def test_volatilities_are_relative_to_the_heaviest_component():
    """Underwood's equation is written against the heavy key, and taking the
    heaviest component as the reference makes every alpha at least 1, which is
    what brackets the root."""
    alpha, _ = volatilities_for(alkane_feed(), ALKANE_P)
    assert alpha["Hexane"] == pytest.approx(1.0)
    assert alpha["Propane"] > alpha["Butane"] > alpha["Pentane"] > 1.0


def test_the_basis_records_the_pressure_AND_temperature_the_alphas_came_from():
    """A bare relative volatility is meaningless. Measured on this feed: the
    bubble point is 382.1 K at 13.694 bar."""
    _, basis = volatilities_for(alkane_feed(), ALKANE_P)
    assert "13.694" in basis
    assert "382" in basis
    assert "Hexane" in basis


def test_a_missing_volatility_is_refused_rather_than_raising_a_KeyError():
    """relative_volatilities drops a pair whose mole fraction reads exact zero.
    Selection cannot run on a partial set, and the message has to name the
    component rather than surfacing a KeyError from inside the dynamic
    program."""
    feed = alkane_feed(flows=(10.0, 20.0, 60.0, 0.0))
    with pytest.raises(ValueError, match="minimum vapour cannot be computed"):
        volatilities_for(feed, ALKANE_P)


def test_select_and_verify_returns_both_stages():
    selection, outcome = select_and_verify(
        BioSteamSimulator(), alkane_feed(), ORDER)
    assert len(selection.root.splits()) == 3
    assert selection.total_V_min_kmol_hr > 0
    assert len(outcome.columns) == 3


def test_the_verified_sequence_is_the_one_that_was_SELECTED():
    """The two stages must not drift. Verifying a different sequence from the
    one chosen would be reporting a design for something else entirely."""
    selection, outcome = select_and_verify(
        BioSteamSimulator(), alkane_feed(), ORDER)
    assert label(outcome.root) == label(selection.root)


def test_an_undetermined_column_still_blocks_a_cost_after_selection():
    """Selection is a bound problem and cannot see condenser feasibility.

    MEASURED on this feed: minimum vapour picks the direct sequence, and two of
    its three columns then screen UNDETERMINED under R-09 -- they run at 3.78
    and 1.16 bar, where their overheads will not condense against cooling
    water. Stage 1 has no way to know that; stage 2 does, and it still
    withholds the cost. The pipeline does not get to overrule the screening
    just because minimum vapour liked the route.

    This is the case that makes the two-stage design worth its cost.
    """
    _, outcome = select_and_verify(
        BioSteamSimulator(), alkane_feed(), ORDER)
    assert "R-09" in outcome.undetermined_by
    assert outcome.total_cost_USD_yr is None
    assert not outcome.costable
    assert outcome.feasible          # undetermined is NOT eliminated


def test_selection_evaluates_ten_split_pairs_on_a_four_component_feed():
    """Enumeration would design 5 sequences x 3 columns = 15."""
    selection, _ = select_and_verify(
        BioSteamSimulator(), alkane_feed(), ORDER)
    assert selection.evaluated == 10


def test_the_feed_thermal_condition_reaches_the_selection():
    """Measured: this feed at 330 K is subcooled at 13.694 bar, q = 1.40. q
    enters Underwood's equation directly, so a selection that defaulted it to
    1.0 would be solving a different problem."""
    selection, _ = select_and_verify(
        BioSteamSimulator(), alkane_feed(), ORDER)
    # theta for the first split at q = 1.4019, measured
    assert selection.splits[0].theta == pytest.approx(8.9657, rel=1e-3)
