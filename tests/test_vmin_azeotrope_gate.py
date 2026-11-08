"""No minimum vapour for a train that has to cross an azeotrope.

Underwood is evaluated at the bubble point, where an azeotrope does not show:
ethanol/water reads alpha 1.9 there while the split is thermodynamically
impossible. Before this gate the dynamic program returned a confident
415.3 kmol/hr for that train, and stage 2 caught it only afterwards.

A sharp-split train separates EVERY pair of components somewhere, so any
azeotropic pair blocks every sequence, not just the column that takes the pair
as its keys. The gate therefore checks all pairs, which is broader than R-03's
per-column scope on purpose.
"""
import pytest

from sepsyn.cli import main
from sepsyn.properties import resolve
from sepsyn.simulators.biosteam_adapter import BioSteamSimulator
from sepsyn.types import Component, Feed
from sepsyn.vmin.gate import AzeotropeBlocksSelection, azeotrope_gate
from sepsyn.vmin.pipeline import select_and_verify

ATM = 101325.0


def feed_of(pairs, T_K=298.0):
    return Feed(components=tuple(Component(n, resolve(n), f) for n, f in pairs),
                T_K=T_K, P_Pa=ATM)


ALCOHOLS = feed_of([("Ethanol", 40.0), ("Water", 40.0), ("Butanol", 20.0)])
ALKANES = feed_of([("Propane", 10.0), ("Butane", 20.0),
                   ("Pentane", 60.0), ("Hexane", 10.0)], T_K=330.0)


def test_the_gate_finds_the_ethanol_water_azeotrope():
    found = azeotrope_gate(ALCOHOLS, ATM)
    pairs = {frozenset(a.components) for a in found}
    assert frozenset({"Ethanol", "Water"}) in pairs


def test_the_gate_passes_an_ideal_feed():
    assert azeotrope_gate(ALKANES, ATM) == []


def test_a_component_with_no_flow_is_not_checked():
    """It is not in the train, so nothing has to separate it."""
    feed = feed_of([("Ethanol", 40.0), ("Water", 0.0), ("Butanol", 20.0)])
    pairs = {frozenset(a.components) for a in azeotrope_gate(feed, ATM)}
    assert frozenset({"Ethanol", "Water"}) not in pairs


def test_selection_refuses_before_computing_any_vapour():
    with pytest.raises(AzeotropeBlocksSelection) as caught:
        select_and_verify(BioSteamSimulator(), ALCOHOLS,
                          ("Ethanol", "Water", "Butanol"), ATM)
    message = str(caught.value)
    assert "Ethanol" in message and "Water" in message
    assert "1.013 bar" in message


def test_the_refusal_carries_the_azeotropes_and_their_pressure():
    with pytest.raises(AzeotropeBlocksSelection) as caught:
        select_and_verify(BioSteamSimulator(), ALCOHOLS,
                          ("Ethanol", "Water", "Butanol"), ATM)
    assert caught.value.P_Pa == ATM
    assert caught.value.azeotropes


CLI = ["--feed", "Ethanol:40,Water:40,Butanol:20", "--T", "298",
       "--vmin", "--order", "Ethanol,Water,Butanol"]


def test_the_cli_prints_the_refusal_and_NO_vapour_number(capsys):
    code = main(CLI)
    out = capsys.readouterr().out
    assert code == 1
    assert "CANNOT BE PERFORMED" in out.upper()
    assert "Ethanol" in out and "Water" in out
    assert "OPTIMAL SEQUENCE" not in out
    assert "kmol/hr total" not in out


def test_the_cli_names_what_would_work_instead(capsys):
    """A refusal with no way forward is half an answer."""
    main(CLI)
    out = capsys.readouterr().out.lower()
    assert "pressure-swing" in out or "extractive" in out


def test_the_json_records_the_refusal(tmp_path):
    """Review 11-08: a refused selection used to write a JSON that read as a
    plain screening run."""
    import json
    path = tmp_path / "run.json"
    assert main(CLI + ["--json", str(path)]) == 1
    sel = json.loads(path.read_text())["selection"]
    assert sel["refused"] == "azeotrope"
    assert any(set(a["components"]) == {"Ethanol", "Water"}
               for a in sel["azeotropes"])
