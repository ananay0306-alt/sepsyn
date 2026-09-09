"""The four classic heuristics, as cheap proxies for the objective.

Each one states which split to perform FIRST, so each is a rule for choosing a
split point, applied recursively. One proxy produces one sequence from feed
properties alone, designing nothing. That cheapness is the point: proxies exist
to be scored against the evaluated ranking, not trusted.
"""
import pytest

from sepsyn.properties import resolve
from sepsyn.sequencing.heuristics import PROXIES, AdjacentAlphas, adjacent_alphas
from sepsyn.types import Component, Feed

ORDER = ("Propane", "Butane", "Pentane", "Hexane")
FLOWS = {"Propane": 40.0, "Butane": 30.0, "Pentane": 20.0, "Hexane": 10.0}


def alkane_feed():
    return Feed(
        components=tuple(Component(n, resolve(n), FLOWS[n]) for n in ORDER),
        T_K=330.0, P_Pa=101325.0,
    )


@pytest.fixture(scope="module")
def alphas():
    return adjacent_alphas(alkane_feed(), ORDER, 101325.0)


def test_alphas_carry_the_conditions_they_were_computed_at(alphas):
    """A proxy is cheap, not exempt. An alpha without its temperature and
    pressure is meaningless whoever is using it."""
    assert alphas.T_K > 0
    assert alphas.P_Pa == 101325.0
    assert alphas.basis


def test_every_adjacent_pair_has_an_alpha(alphas):
    for a, b in zip(ORDER, ORDER[1:]):
        assert alphas.values[(a, b)] > 1.0


def test_there_are_exactly_four_proxies():
    assert set(PROXIES) == {"easiest_first", "hardest_last",
                            "most_plentiful_first", "equimolar"}


@pytest.mark.parametrize("name", ["easiest_first", "hardest_last",
                                  "most_plentiful_first", "equimolar"])
def test_each_proxy_returns_a_complete_sequence(name, alphas):
    root = PROXIES[name](ORDER, FLOWS, alphas)
    assert len(root.splits()) == len(ORDER) - 1
    assert root.group == ORDER


def test_easiest_first_cuts_where_alpha_is_largest(alphas):
    """The pair with the widest volatility gap is split first."""
    root = PROXIES["easiest_first"](ORDER, FLOWS, alphas)
    widest = max(alphas.values, key=alphas.values.get)
    assert (root.light_key, root.heavy_key) == widest


def test_easiest_first_and_hardest_last_agree_on_a_FIRST_cut():
    """Deferring the hardest split and doing the easiest first are the same
    instruction when there is one cut to make. They diverge on SUBSEQUENT
    cuts, which is why both exist and both are scored."""
    order = ("A", "B", "C")
    flows = {"A": 1.0, "B": 1.0, "C": 1.0}
    a = AdjacentAlphas({("A", "B"): 5.0, ("B", "C"): 1.2}, 300.0, 1e5, "test")
    assert PROXIES["easiest_first"](order, flows, a).k == 1
    assert PROXIES["hardest_last"](order, flows, a).k == 1


def test_most_plentiful_first_removes_the_largest_flow():
    """Propane is 40 of 100, so it comes off first as a single product."""
    root = PROXIES["most_plentiful_first"](ORDER, FLOWS, None)
    assert root.k == 1
    assert root.light_group == ("Propane",)


def test_most_plentiful_first_can_cut_in_the_MIDDLE():
    """If the most plentiful component sits in the middle it must still be
    isolated, which means the first cut is not at an end. This is the case
    that makes the proxy disagree with the others."""
    order = ("A", "B", "C")
    flows = {"A": 10.0, "B": 80.0, "C": 10.0}
    root = PROXIES["most_plentiful_first"](order, flows, None)
    assert root.k in (1, 2)
    assert any(s.light_group == ("B",) or s.heavy_group == ("B",)
               for s in root.splits())


def test_equimolar_splits_the_flow_as_evenly_as_it_can():
    order = ("A", "B", "C", "D")
    flows = {"A": 25.0, "B": 25.0, "C": 25.0, "D": 25.0}
    root = PROXIES["equimolar"](order, flows, None)
    assert root.k == 2


def test_a_proxy_designs_nothing():
    """No simulator is passed and none may be reached. If a proxy needed a
    design it would not be a proxy, and scoring it against the designed answer
    would be circular."""
    import sepsyn.sequencing.heuristics as h
    source = open(h.__file__).read()
    assert "design_multicomponent" not in source
    assert "BioSteam" not in source
