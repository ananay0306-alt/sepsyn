"""Saving a run. --out for people, --json for comparison.

The project's own argument is that two designs at different q are not
comparable, so the assumptions must be recorded. Until now the tool recorded
nothing: every number went to stdout and died with the terminal. Structured
output is what makes runs actually comparable rather than merely readable.
"""
import json

import pytest

from sepsyn.cli import main

BT = ["--feed", "Benzene:60,Toluene:40", "--T", "298.15",
      "--light-key", "Benzene", "--heavy-key", "Toluene"]


def run(tmp_path, *extra):
    out = tmp_path / "run.json"
    assert main(BT + list(extra) + ["--json", str(out)]) == 0
    return json.loads(out.read_text())


def test_json_is_written_and_parses(tmp_path):
    assert run(tmp_path)["screening"]["verdict"] == "feasible"


def test_the_pressure_AND_ITS_BASIS_are_recorded(tmp_path):
    """Not just the number. A specified pressure and a derived one are
    different claims, and a saved run that cannot tell them apart is the
    unrecorded-assumption failure in a new file format."""
    data = run(tmp_path)
    assert data["column_pressure"]["Pa"] == pytest.approx(101325.0)
    assert "derived" in data["column_pressure"]["basis"]

    specified = run(tmp_path, "--column-P", "150000")
    assert specified["column_pressure"]["Pa"] == pytest.approx(150000.0)
    assert "specified" in specified["column_pressure"]["basis"]


def test_alpha_is_recorded_with_the_conditions_it_was_computed_at(tmp_path):
    data = run(tmp_path)
    alpha = data["screening"]["alphas"][0]
    assert alpha["value"] == pytest.approx(2.519, rel=0.01)
    assert alpha["P_Pa"] == pytest.approx(data["column_pressure"]["Pa"])
    assert alpha["T_K"] > 0


def test_rules_that_did_not_fire_are_saved_too(tmp_path):
    """The report prints them under --explain because what was considered is
    part of the reasoning. A saved run keeps all of them unconditionally."""
    rules = run(tmp_path)["screening"]["rules"]
    assert len(rules) == 12
    assert any(r["fired"] for r in rules)
    assert any(not r["fired"] for r in rules)


def test_the_design_records_q_and_whether_it_was_imposed(tmp_path):
    as_arrives = run(tmp_path, "--design")["design"]
    imposed = run(tmp_path, "--design", "--feed-q", "1.0")["design"]
    assert as_arrives["feed_q"]["value"] == pytest.approx(1.301, rel=0.01)
    assert as_arrives["feed_q"]["imposed"] is False
    assert imposed["feed_q"]["imposed"] is True


def test_equipment_STATUS_survives_serialisation(tmp_path):
    """The 58 percent lesson, in the file format. 'total because a rule proved
    it' and 'total because that is the convention' must not serialise
    identically."""
    equipment = run(tmp_path, "--design")["design"]["equipment"]
    assert {d["step"] for d in equipment} == {22, 23, 24, 25}
    condenser = next(d for d in equipment if d["step"] == 22)
    assert condenser["choice"] == "total"
    assert condenser["status"] == "default"
    assert condenser["must_record"]


def test_verification_checks_are_all_saved_with_their_numbers(tmp_path):
    checks = run(tmp_path, "--design")["design"]["verification"]
    assert len(checks) >= 8
    assert all(c["passed"] for c in checks)
    assert all(c["detail"] for c in checks)


def test_two_runs_at_different_q_are_MECHANICALLY_comparable(tmp_path):
    """The point of the whole feature. Not that both were saved, but that a
    difference in an assumption shows up as a difference in the data."""
    a = run(tmp_path, "--design")["design"]
    b = run(tmp_path, "--design", "--feed-q", "1.0")["design"]
    assert a["feed_q"]["value"] != b["feed_q"]["value"]
    assert a["chosen"]["annualised_cost_USD_yr"] != b["chosen"]["annualised_cost_USD_yr"]


def test_out_writes_the_same_text_that_was_printed(tmp_path, capsys):
    path = tmp_path / "run.txt"
    assert main(BT + ["--out", str(path)]) == 0
    printed = capsys.readouterr().out
    saved = path.read_text()
    assert "VERDICT" in saved
    assert saved.strip() in printed


def test_a_screening_only_run_has_no_design_section(tmp_path):
    """None, not an empty object. The run did not design a column, which is
    different from designing one with nothing in it."""
    assert run(tmp_path)["design"] is None
