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
        "lightest_first", "easiest_first", "hardest_last",
        "most_plentiful_first", "equimolar"}


def test_each_score_names_the_sequence_that_proxy_chose(card):
    for s in card.scores:
        assert s.sequence_name


def test_every_heuristic_picks_the_winner_once_R09_is_answered(card):
    """Corrected 2026-11-08. R-09 is now answered by designing each column, and
    on this feed every doubt it raised is answered (two by a small pressure
    raise). DWSIM converges the raised Pentane/Hexane column and agrees on its
    condenser temperature to 0.1 K.

    It previously asserted every heuristic named a route the tool could not
    endorse. On this feed (40/30/20/10, lightest most plentiful) all five now
    agree, and all five pick the cost winner, the direct sequence. Agreement
    means the scorecard cannot tell them apart here, which the report says.
    """
    assert all(s.picked_winner for s in card.scores)
    assert not any(s.sequence_status == "undetermined" for s in card.scores)
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
