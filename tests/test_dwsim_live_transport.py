"""LiveTransport: parsing, and a real connection behind the marker.

The parsing tests run in the default suite because they are pure. The
connection tests do not: a rigorous solve takes minutes and one 300 s timeout
was already observed on 09-09.
"""
import pytest

from sepsyn.simulators.dwsim_adapter import parse_results

RESULTS = {
    "material_streams": [
        {"tag": "F", "T_K": 298.15, "P_Pa": 101325.0,
         "molar_flow_mol_s": 27.77778,
         "mole_fractions": {"Benzene": 0.6, "Toluene": 0.4}},
        {"tag": "D", "T_K": 352.95, "P_Pa": 101325.0,
         "molar_flow_mol_s": 16.611114,
         "mole_fractions": {"Benzene": 0.993311, "Toluene": 0.006689}},
        {"tag": "B", "T_K": 383.13, "P_Pa": 101325.0,
         "molar_flow_mol_s": 11.166666,
         "mole_fractions": {"Benzene": 0.014925, "Toluene": 0.985075}},
    ],
    "energy_streams": [
        {"tag": "QC", "energy_flow_kW": 1189.054272},
        {"tag": "QR", "energy_flow_kW": 1458.577217},
    ],
}


def test_mole_fractions_are_converted_back_to_per_compound_flows():
    """DWSIM reports a total flow and mole fractions; the fixture needs molar
    flows per compound so a mass balance can be checked component by
    component."""
    d, b, qc, qr, td, tb = parse_results(RESULTS)
    assert d["Benzene"] == pytest.approx(16.611114 * 0.993311)
    assert b["Toluene"] == pytest.approx(11.166666 * 0.985075)


def test_the_duties_are_picked_off_the_named_energy_streams():
    _, _, qc, qr, _, _ = parse_results(RESULTS)
    assert qc == pytest.approx(1189.054272)
    assert qr == pytest.approx(1458.577217)


def test_the_product_temperatures_are_returned():
    _, _, _, _, td, tb = parse_results(RESULTS)
    assert td == pytest.approx(352.95)
    assert tb == pytest.approx(383.13)


def test_the_parsed_products_close_the_mass_balance():
    """The doubled-feed guard, checkable straight off a parsed result."""
    d, b, _, _, _, _ = parse_results(RESULTS)
    fed = 27.77778
    assert sum(d.values()) + sum(b.values()) == pytest.approx(fed, rel=1e-4)


def test_a_result_missing_a_product_stream_is_refused():
    """A solve that did not produce both products is not a run to be parsed
    into plausible-looking zeros."""
    from sepsyn.simulators.dwsim_adapter import DwsimResultError
    partial = {"material_streams": [RESULTS["material_streams"][0]],
               "energy_streams": []}
    with pytest.raises(DwsimResultError, match="D"):
        parse_results(partial)
