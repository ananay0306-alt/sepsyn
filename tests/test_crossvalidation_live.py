"""The comparison against a live DWSIM. Opt in with: pytest -m dwsim_live

Re-measures what the recorded fixtures replay, so a drift in DWSIM or in the
transport shows up as a changed gap rather than going unnoticed.
"""
import pytest

from sepsyn.crossvalidate import compare, format_comparison
from sepsyn.properties import resolve
from sepsyn.simulators.base import ColumnSpec
from sepsyn.simulators.biosteam_adapter import BioSteamSimulator
from sepsyn.simulators.dwsim_adapter import DwsimSimulator, LiveTransport
from sepsyn.types import Component, Feed

pytestmark = pytest.mark.dwsim_live


def test_benzene_toluene_live():
    feed = Feed(components=(Component("Benzene", resolve("Benzene"), 60.0),
                            Component("Toluene", resolve("Toluene"), 40.0)),
                T_K=298.15, P_Pa=101325.0)
    spec = ColumnSpec("Benzene", "Toluene", 0.99, 0.99, 101325.0)
    c = compare(feed, spec, BioSteamSimulator(),
                DwsimSimulator(LiveTransport(timeout_s=300)))
    print("\n" + format_comparison(c))
    assert c.reportable
    assert all(abs(g.relative) < 0.10 for g in c.gaps if g.unit == "kW")


def test_alkanes_live():
    order = ("Propane", "Butane", "Pentane", "Hexane")
    feed = Feed(components=tuple(Component(n, resolve(n), f) for n, f in
                                 zip(order, (10.0, 20.0, 60.0, 10.0))),
                T_K=330.0, P_Pa=101325.0)
    spec = ColumnSpec("Propane", "Butane", 0.99, 0.99, 1369410.0)
    c = compare(feed, spec, BioSteamSimulator(),
                DwsimSimulator(LiveTransport(timeout_s=300)))
    print("\n" + format_comparison(c))
    assert c.reportable
