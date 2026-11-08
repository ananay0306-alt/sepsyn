"""The DWSIM/BioSTEAM stage conventions, pinned. Measured 11-07; see
sepsyn/simulators/conventions.py for the source reading and the sweep."""
import pytest

from sepsyn.properties import resolve
from sepsyn.simulators.base import ColumnSpec
from sepsyn.simulators.biosteam_adapter import BioSteamSimulator
from sepsyn.simulators.conventions import (
    FEED_STAGE_ORIGIN, STAGE_COUNT_INCLUDES_ENDS, dwsim_feed_stage,
    dwsim_stage_count)
from sepsyn.types import Component, Feed


def test_the_feed_stage_counts_from_the_top():
    assert FEED_STAGE_ORIGIN == "top"


def test_biosteam_does_not_count_both_ends():
    assert STAGE_COUNT_INCLUDES_ENDS is False


def test_dwsim_gets_one_more_stage_for_the_condenser():
    """BioSTEAM's 24 is DWSIM's 25. The 09-09 probe handed over 20 for 20."""
    assert dwsim_stage_count(24) == 25


def test_the_measured_benzene_toluene_case():
    """BioSTEAM 24 stages, feed 13. DWSIM's reboiler duty was lowest at index
    13 of 25 across a sweep of 9 to 18."""
    assert dwsim_stage_count(24) == 25
    assert dwsim_feed_stage(13, 24) == 13


def test_the_feed_can_land_on_neither_end():
    with pytest.raises(ValueError):
        dwsim_feed_stage(0, 24)
    with pytest.raises(ValueError):
        dwsim_feed_stage(24, 24)


def test_a_partial_condenser_is_refused_because_it_was_not_measured():
    with pytest.raises(ValueError, match="partial"):
        dwsim_stage_count(24, condenser_type="partial")


def test_the_adapter_reports_the_numbers_the_mapping_needs():
    """The theoretical count and feed stage, not the ACTUAL count, which is
    larger by the tray efficiency and must never reach a rigorous column."""
    feed = Feed(components=(Component("Benzene", resolve("Benzene"), 60.0),
                            Component("Toluene", resolve("Toluene"), 40.0)),
                T_K=298.15, P_Pa=101325.0)
    r = BioSteamSimulator().design_column(
        feed, ColumnSpec("Benzene", "Toluene", 0.99, 0.99, 101325.0))
    assert r.theoretical_stages == 24
    assert r.theoretical_feed_stage == 13
    assert r.stages > r.theoretical_stages
