"""Scoring the proxies against the evaluated ranking.

This is the module that answers the review question. When two heuristics
disagree, which is right? Not argued: measured. The exhaustive ranking is the
ground truth, each proxy names one sequence, and the scorecard reports whether
it picked the winner and what it cost to be wrong.
"""
import pytest

from sepsyn.properties import resolve
from sepsyn.sequencing.rank import sweep
from sepsyn.sequencing.score import score_proxies
from sepsyn.simulators.biosteam_adapter import BioSteamSimulator
from sepsyn.types import Component, Feed

ORDER = ("Propane", "Butane", "Pentane", "Hexane")


def alkane_feed():
    return Feed(
        components=tuple(Component(n, resolve(n), f)
                         for n, f in zip(ORDER, (40.0, 30.0, 20.0, 10.0))),
        T_K=330.0, P_Pa=101325.0,
    )


@pytest.fixture(scope="module")
def card():
    feed = alkane_feed()
    ranking = sweep(BioSteamSimulator(), feed, ORDER)
    return score_proxies(feed, ORDER, ranking, 101325.0)


def test_every_proxy_is_scored(card):
    assert {s.name for s in card.scores} == {
        "easiest_first", "hardest_last", "most_plentiful_first", "equimolar"}


def test_each_score_names_the_sequence_that_proxy_chose(card):
    for s in card.scores:
        assert s.sequence_name


def test_every_classic_heuristic_names_a_route_the_tool_CANNOT_ENDORSE(card):
    """Corrected 2026-09-10. This previously asserted all four proxies picked
    the winner, which they did while undetermined columns were being costed.

    All four favour taking the lightest component off first. That route sends
    light traces into low-pressure condensers, R-09 fires, and the sequence is
    undetermined. So every textbook heuristic recommends a train sepsyn
    declines to endorse, and none of them picks the survivor.

    That is a finding about the heuristics, not a failure of the scorecard.
    """
    assert not any(s.picked_winner for s in card.scores)
    assert all(s.sequence_status == "undetermined" for s in card.scores)
    assert card.proxies_agree is True


def test_the_cost_penalty_of_a_correct_proxy_is_zero(card):
    for s in card.scores:
        if s.picked_winner:
            assert s.cost_penalty == pytest.approx(0.0, abs=1e-9)


def test_the_scorecard_names_the_winner_it_scored_against(card):
    assert card.winner_name


def test_a_proxy_naming_a_sequence_that_was_eliminated_is_not_a_hit():
    """A heuristic can happily recommend a train containing an azeotropic
    column. That is a miss, and a particularly informative one."""
    feed = Feed(
        components=tuple(Component(n, resolve(n), f) for n, f in
                         [("Acetone", 30.0), ("Ethanol", 40.0), ("Water", 30.0)]),
        T_K=330.0, P_Pa=101325.0)
    order = ("Acetone", "Ethanol", "Water")
    ranking = sweep(BioSteamSimulator(), feed, order)
    assert ranking.winner is None
    card = score_proxies(feed, order, ranking, 101325.0)
    assert all(not s.picked_winner for s in card.scores)
    assert all(s.cost_penalty is None for s in card.scores)
