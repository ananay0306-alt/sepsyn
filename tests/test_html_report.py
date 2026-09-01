"""The run as a page. --html.

The reflux sweep was already a chart pretending to be a table: eight rows in
which the reader has to find the minimum themselves. Its job is to locate an
optimum in a trade-off, which is a line with the minimum marked.

Stages against k is a SECOND measure on a different scale. It gets its own
chart. Never a dual axis.
"""
import json
import re

import pytest

from sepsyn.cli import main

BT = ["--feed", "Benzene:60,Toluene:40", "--T", "298.15",
      "--light-key", "Benzene", "--heavy-key", "Toluene"]


@pytest.fixture(scope="module")
def designed(tmp_path_factory):
    path = tmp_path_factory.mktemp("html") / "run.html"
    assert main(BT + ["--design", "--html", str(path)]) == 0
    return path.read_text()


def test_the_page_is_written_and_names_the_verdict(designed):
    assert "FEASIBLE" in designed


def test_the_page_is_SELF_CONTAINED(designed):
    """No fonts, no CDN, no script src. An engineering record has to open on a
    machine with no network and keep working in five years."""
    external = re.findall(r'(?:src|href)\s*=\s*["\'](https?://[^"\']+)', designed)
    assert external == [], f"external resources: {external}"


def test_the_pressure_basis_is_shown_not_just_the_number(designed):
    assert "derived" in designed
    assert "cooling water" in designed


def test_the_cost_curve_is_drawn_as_a_chart(designed):
    assert "<svg" in designed
    assert "polyline" in designed or "<path" in designed


def test_stages_get_their_OWN_chart_rather_than_a_second_axis(designed):
    """Two measures of different scale, so two charts. A dual axis would let
    the crossing point of two arbitrary scalings look like a finding."""
    assert designed.count("<svg") >= 2


def test_the_optimum_is_marked(designed):
    assert "cheapest" in designed.lower()


def test_equipment_status_is_TEXT_not_only_a_colour(designed):
    """Colour alone cannot carry the difference between convention and
    evidence, which is the distinction the whole project rests on."""
    assert "by default" in designed
    for step in (22, 23, 24, 25):
        assert f"step {step}" in designed


def test_verification_results_are_labelled_not_only_coloured(designed):
    assert "PASS" in designed
    assert "mass balance" in designed


def test_rules_that_did_not_fire_are_shown_too(designed):
    assert "R-01" in designed
    assert "did not fire" in designed.lower()


def test_a_screening_only_run_renders_without_a_design_section(tmp_path):
    path = tmp_path / "screen.html"
    assert main(BT + ["--html", str(path)]) == 0
    page = path.read_text()
    assert "FEASIBLE" in page
    assert "REFLUX SWEEP" not in page.upper() or "no column" in page.lower()


def test_html_and_json_describe_the_same_run(tmp_path):
    html, js = tmp_path / "r.html", tmp_path / "r.json"
    assert main(BT + ["--design", "--html", str(html), "--json", str(js)]) == 0
    data = json.loads(js.read_text())
    assert f"{data['design']['chosen']['stages']:.0f}" in html.read_text()
