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


def test_the_R09_raised_column_live():
    """Re-measures the 11-08 gate: the raised Pentane/Hexane column converges
    and condenses above cooling water in DWSIM."""
    from sepsyn.properties import COOLING_WATER_T

    flows = {"Butane": 0.2, "Pentane": 59.4, "Hexane": 9.999978788248363}
    feed = Feed(components=tuple(Component(n, resolve(n), f)
                                 for n, f in flows.items()),
                T_K=330.0, P_Pa=101325.0)
    spec = ColumnSpec("Pentane", "Hexane", 0.99, 0.99, 117999.0)
    c = compare(feed, spec, BioSteamSimulator(),
                DwsimSimulator(LiveTransport(timeout_s=300)))
    print("\n" + format_comparison(c))
    # The feed is liquid to BioSTEAM and vapour to DWSIM, so no gap.
    (fc,) = [a for a in c.assertions if a.name == "feed condition"]
    assert fc.holds is False and not c.reportable
    run = LiveTransport(timeout_s=300).run(feed, spec, c.dwsim_stages,
                                          c.dwsim_feed_stage)
    assert run.converged and run.distillate_T_K >= COOLING_WATER_T
