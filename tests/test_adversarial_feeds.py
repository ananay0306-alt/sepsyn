"""Feeds built so the heuristics disagree.

The Phase A probes measured that on n-alkane feeds every proxy picks the same
sequence, because the lightest component is also the most plentiful. Nothing is
learned from a case where nobody disagrees. These feeds are constructed to
create the conflict the review asked about.

The conflict is not hard to resolve. It is hard to OBSERVE, and that is what
this file is for.
"""
import pytest

from sepsyn.properties import resolve
from sepsyn.sequencing.rank import sweep
from sepsyn.sequencing.score import score_proxies
from sepsyn.simulators.biosteam_adapter import BioSteamSimulator
from sepsyn.types import Component, Feed

P = 101325.0
ORDER = ("Propane", "Butane", "Pentane", "Hexane")

# The most plentiful component sits in the MIDDLE of the volatility order, so
# "remove the most plentiful first" cannot agree with taking an end off first.
# Pentane is 60 of 100.
MIDDLE_HEAVY_FLOWS = (10.0, 20.0, 60.0, 10.0)


def feed_of(order, flows, T_K=330.0):
    return Feed(
        components=tuple(Component(n, resolve(n), f)
                         for n, f in zip(order, flows)),
        T_K=T_K, P_Pa=P,
    )


@pytest.fixture(scope="module")
def middle_heavy():
    feed = feed_of(ORDER, MIDDLE_HEAVY_FLOWS)
    ranking = sweep(BioSteamSimulator(), feed, ORDER)
    return feed, ranking, score_proxies(feed, ORDER, ranking, P)


def test_the_feed_actually_creates_a_disagreement(middle_heavy):
    """The premise of the whole file. If the proxies agree here, the feed is
    not adversarial and the case proves nothing."""
    _, _, card = middle_heavy
    assert card.proxies_agree is False, (
        "this feed was constructed to make the heuristics disagree; if they "
        "agree it cannot discriminate between them and must be replaced")


def test_at_least_two_proxies_name_different_sequences(middle_heavy):
    _, _, card = middle_heavy
    assert len({s.sequence_name for s in card.scores}) >= 2


def test_the_scorecard_says_what_became_of_each_proxys_choice(middle_heavy):
    """Corrected 2026-09-10. This previously asserted easiest_first picked the
    winner and most_plentiful_first did not, a result computed while
    undetermined columns were being costed.

    The proxies still disagree with each other, which is what makes the feed
    adversarial. What changed is that NONE of their choices is costable: they
    all route light traces into low-pressure condensers. The scorecard now
    reports that as its own status rather than as a cost penalty.
    """
    _, _, card = middle_heavy
    assert len({s.sequence_name for s in card.scores}) >= 2
    assert not any(s.picked_winner for s in card.scores)
    assert all(s.sequence_status in ("undetermined", "eliminated")
               for s in card.scores)


def test_a_miss_is_EXPLAINED_rather_than_left_blank(middle_heavy):
    """A miss must say what became of the choice. A blank penalty could mean
    'wrong by an unknown amount' or 'named something unbuildable', and those
    are different things for a reader to act on."""
    _, _, card = middle_heavy
    for s in card.scores:
        if not s.picked_winner:
            assert s.sequence_status != "unknown"
            if s.sequence_status in ("costable", "near-optimal"):
                assert s.cost_penalty is not None and s.cost_penalty > 0


def test_the_disagreement_is_recorded_against_the_ground_truth(middle_heavy):
    _, ranking, card = middle_heavy
    assert ranking.winner is not None
    assert card.winner_name == ranking.winner.name


def test_the_alkane_control_still_shows_agreement():
    """The control. On an ordinary feed the proxies agree, which is why an
    adversarial set had to be constructed at all."""
    feed = feed_of(ORDER, (40.0, 30.0, 20.0, 10.0))
    ranking = sweep(BioSteamSimulator(), feed, ORDER)
    card = score_proxies(feed, ORDER, ranking, P)
    assert card.proxies_agree is True
