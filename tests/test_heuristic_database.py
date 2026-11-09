"""M4: the heuristic database. Guidance that points at a calculation, never an
answer, and every entry cited."""
import pytest
import yaml

from sepsyn import heuristicdb
from sepsyn.cli import main
from sepsyn.heuristicdb import applicable, by_proxy, load_heuristics
from sepsyn.sequencing.heuristics import PROXIES

ALKANES = ["--feed", "Propane:10,Butane:20,Pentane:60,Hexane:10", "--T", "330",
           "--vmin", "--order", "Propane,Butane,Pentane,Hexane"]

GOOD = dict(id="H-90", statement="A rule", source="Somebody (2000)",
            source_verified=True, scope="sequencing",
            applies_when="n_components >= 3", proxy="equimolar",
            tested_by="vmin", conflicts_with=[], measured=[])


def write(tmp_path, *entries):
    path = tmp_path / "h.yaml"
    path.write_text(yaml.safe_dump(list(entries)))
    return str(path)


def test_the_shipped_database_loads():
    hs = load_heuristics()
    assert {h.id for h in hs} >= {"H-01", "H-02", "H-03", "H-04", "H-05"}


def test_the_four_from_the_projects_source_are_there_word_for_word():
    """Separation_heuristics.pdf, attributed to Douglas (1985)."""
    statements = {h.statement for h in load_heuristics()}
    assert statements >= {"Recover the lightest component first",
                          "Recover the most plentiful component first",
                          "Make the most difficult splits last",
                          "Favor equimolar splits"}


def test_every_proxy_in_code_has_a_cited_entry():
    """A proxy scored in the report without an entry would print a code name
    with no source, which is the unaudited guidance M4 removes."""
    assert set(by_proxy(load_heuristics())) == set(PROXIES)


def test_easiest_first_carries_an_UNVERIFIED_citation():
    """Research 11-08: Harbert (1957) is known only through a secondary
    review, so the citation must say so wherever it is printed."""
    h = by_proxy(load_heuristics())["easiest_first"]
    assert "Harbert" in h.source
    assert h.source_verified is False
    assert "unverified" in h.citation


@pytest.mark.parametrize("bad, match", [
    (dict(source=""), "no source"),
    (dict(proxy="cheapest_first"), "does not exist"),
    (dict(tested_by="gut_feeling"), "not a sepsyn calculation"),
    (dict(applies_when="min_alpha > 2"), "may use only"),
    (dict(applies_when="n_components >="), "unparseable"),
    (dict(scope="crystallisation"), "scope"),
    (dict(conflicts_with=["H-99"]), "unknown heuristic"),
])
def test_a_defective_entry_is_refused_at_load(tmp_path, bad, match):
    with pytest.raises(ValueError, match=match):
        load_heuristics(write(tmp_path, {**GOOD, **bad}))


def test_a_duplicate_id_is_refused(tmp_path):
    with pytest.raises(ValueError, match="duplicate"):
        load_heuristics(write(tmp_path, GOOD, {**GOOD, "proxy": "hardest_last"}))


def test_two_entries_claiming_one_proxy_are_refused(tmp_path):
    with pytest.raises(ValueError, match="claimed by two"):
        load_heuristics(write(tmp_path, GOOD, {**GOOD, "id": "H-91"}))


def test_retrieval_is_plain_filtering():
    hs = load_heuristics()
    assert applicable(hs, 2) == ()
    assert len(applicable(hs, 4)) == len(hs)


def test_the_lightest_first_proxy_is_the_direct_sequence():
    from sepsyn.sequencing.heuristics import adjacent_alphas  # noqa: F401
    order = ("A", "B", "C", "D")
    root = PROXIES["lightest_first"](order, {}, None)
    assert [n.k for n in root.splits()] == [1, 1, 1]


def test_the_report_prints_statement_and_citation(capsys):
    assert main(ALKANES) == 0
    out = capsys.readouterr().out
    assert "H-02  Recover the most plentiful component first" in out
    assert "Douglas (1985)" in out
    assert "Harbert (1957)" in out and "(citation unverified)" in out


def test_a_heuristic_can_NOT_change_the_answer(capsys, monkeypatch):
    """The fourth M4 decision, enforced. With the database empty the report
    loses its citations and nothing else: the verdict, the optimal sequence,
    its vapour and the verification are byte for byte the same."""
    def body(out):
        return out.split("HEURISTICS")[0]

    main(ALKANES)
    with_db = capsys.readouterr().out
    monkeypatch.setattr(heuristicdb, "default_heuristics", lambda: ())
    main(ALKANES)
    without_db = capsys.readouterr().out
    assert "Douglas" not in without_db
    assert body(with_db) == body(without_db)
