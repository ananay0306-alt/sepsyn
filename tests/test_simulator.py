"""The simulator boundary, and the one assumption underneath it.

ColumnSpec is written in RECOVERIES because recovery means the same thing in
every simulator and mole fraction does not: BioSTEAM divides by the two keys,
DWSIM by the whole product stream. That mismatch produced a 175% error in an
earlier DWSIM/BioSTEAM comparison, so the basis is pinned by assertion here
rather than trusted from a docstring.
"""
import pytest

from sepsyn.simulators.base import ColumnResult, ColumnSpec, FlashResult, FlashSpec
from sepsyn.simulators.biosteam_adapter import BioSteamSimulator
from sepsyn.types import Component, Feed

MEOH_FED, WATER_FED, GLYCEROL_FED = 100.0, 80.0, 25.0


def methanol_feed():
    return Feed(
        components=(
            Component("Methanol", "67-56-1", MEOH_FED),
            Component("Water", "7732-18-5", WATER_FED),
            Component("Glycerol", "56-81-5", GLYCEROL_FED),
        ),
        T_K=330.0, P_Pa=101325.0,
    )


@pytest.fixture(scope="module")
def base_result():
    """One simulation shared by the tests that only read a converged design."""
    sim = BioSteamSimulator()
    spec = ColumnSpec("Methanol", "Water", 0.99, 0.99, 101325.0)
    return sim.design_column(methanol_feed(), spec)


def test_column_meets_the_requested_recovery(base_result):
    assert base_result.converged, base_result.error
    assert base_result.distillate["Methanol"] / MEOH_FED == pytest.approx(0.99, abs=5e-4)


def test_recovery_means_fraction_of_feed_not_fraction_of_keys(base_result):
    """THE basis test. Its tolerance is the whole point.

    A recovery of 0.99 must mean 99% of the methanol FED leaves overhead:
    99.0000 kmol/hr of the 100 fed, exactly. The plausible wrong reading is a
    keys-only mole fraction -- methanol as a share of (methanol + water) in the
    distillate -- which yields 99.2020 kmol/hr instead.

    The two differ by 0.2 kmol/hr, or 0.002 in recovery. MEASURED, both ways,
    before this tolerance was chosen. Anything looser than about 1e-3 cannot
    tell the correct basis from the wrong one, so a loose tolerance here
    silently retires the only assertion standing between this project and the
    error that cost 175% last time. The plan proposed abs=0.02 -- forty times
    too loose to detect the very defect the recovery spec exists to prevent.

    Recovery is exact by definition, so the tight tolerance costs nothing.
    """
    assert base_result.converged, base_result.error
    d = base_result.distillate

    # Premise guard: the two readings must actually be distinguishable in THIS
    # feed, or the assertions below would have no power regardless of tolerance.
    keys_fraction = d["Methanol"] / (d["Methanol"] + d["Water"])
    assert abs(keys_fraction - 0.99) > 1e-3, (
        "feed chosen so the two bases diverge; they no longer do"
    )

    assert d["Methanol"] == pytest.approx(99.0, abs=0.05)
    assert d["Methanol"] / MEOH_FED == pytest.approx(0.99, abs=5e-4)
    assert base_result.bottoms["Water"] / WATER_FED == pytest.approx(0.99, abs=5e-4)


def test_non_keys_are_reported(base_result):
    """Nothing in a light/heavy-key spec constrains glycerol. Say where it went."""
    assert "Glycerol" in base_result.bottoms
    assert base_result.bottoms["Glycerol"] == pytest.approx(GLYCEROL_FED, abs=0.5)


def test_every_feed_component_appears_in_both_products(base_result):
    """A component silently dropped from the report is a lost mass balance."""
    for name in ("Methanol", "Water", "Glycerol"):
        assert name in base_result.distillate
        assert name in base_result.bottoms


def test_mass_balance_closes(base_result):
    """Distillate + bottoms must return the feed, or the design is fiction."""
    fed = {"Methanol": MEOH_FED, "Water": WATER_FED, "Glycerol": GLYCEROL_FED}
    for name, amount in fed.items():
        out = base_result.distillate[name] + base_result.bottoms[name]
        assert out == pytest.approx(amount, rel=1e-6)


def test_design_numbers_are_present(base_result):
    assert base_result.stages > 1
    assert base_result.minimum_reflux > 0
    assert base_result.reflux > base_result.minimum_reflux
    assert base_result.installed_cost_USD > 0


def test_impossible_spec_returns_error_as_data_not_an_exception():
    """A broken design must never be reported as success."""
    sim = BioSteamSimulator()
    spec = ColumnSpec(light_key="Water", heavy_key="Methanol",   # keys reversed
                      lk_recovery_to_distillate=0.99,
                      hk_recovery_to_bottoms=0.99,
                      pressure_Pa=101325.0)
    r = sim.design_column(methanol_feed(), spec)
    assert r.converged is False
    assert r.error
    # Fails because the design is impossible, not because the adapter is broken.
    assert "specification" in r.error.lower() or "stages" in r.error.lower()


def test_out_of_range_recovery_is_rejected_as_data():
    sim = BioSteamSimulator()
    spec = ColumnSpec("Methanol", "Water", 1.5, 0.99, 101325.0)
    r = sim.design_column(methanol_feed(), spec)
    assert r.converged is False
    assert r.error


def test_flash_splits_the_feed_and_closes_its_balance():
    """design_flash is half the Simulator protocol and had no test at all."""
    sim = BioSteamSimulator()
    r = sim.design_flash(methanol_feed(), FlashSpec(T_K=350.0, P_Pa=101325.0))
    assert r.converged, r.error
    assert r.T_K == pytest.approx(350.0, abs=0.1)
    for name, fed in (("Methanol", MEOH_FED), ("Water", WATER_FED),
                      ("Glycerol", GLYCEROL_FED)):
        assert r.vapor[name] + r.liquid[name] == pytest.approx(fed, rel=1e-6)
    assert sum(r.vapor.values()) > 0     # something actually vaporised
    assert sum(r.liquid.values()) > 0


@pytest.mark.parametrize("spec", [
    FlashSpec(T_K=350.0),                                        # one short
    FlashSpec(T_K=350.0, P_Pa=101325.0, vapor_fraction=0.5),     # one too many
])
def test_flash_rejects_a_wrong_number_of_specifications(spec):
    """A flash has two degrees of freedom. One or three is a caller bug.

    The message must name sepsyn's OWN field names. BioSTEAM independently
    rejects this case, but its error talks about "T, P, V, H, S, x, y" -- four
    of which FlashSpec does not expose -- so a caller who passed T_K alone is
    told to consider specifications that do not exist at this boundary.
    Asserting on our wording is also what makes this test bite: without the
    guard in the adapter, BioSTEAM's error surfaces instead and never mentions
    vapor_fraction. Verified by removing the guard and watching this fail.
    """
    r = BioSteamSimulator().design_flash(methanol_feed(), spec)
    assert r.converged is False
    assert r.error
    assert "vapor_fraction" in r.error
    assert "two degrees of freedom" in r.error


def test_adapter_reports_the_thermal_fields():
    """verify.py SKIPS its thermal checks when these are None, so an adapter
    that does not fill them makes three checks silently unreachable -- the same
    dead-code shape that hid R-07 and R-08 in the CLI."""
    from sepsyn.simulators.biosteam_adapter import BioSteamSimulator
    from sepsyn.simulators.base import ColumnSpec
    from sepsyn.types import Component, Feed

    feed = Feed(
        components=(Component("Methanol", "67-56-1", 100.0),
                    Component("Water", "7732-18-5", 80.0)),
        T_K=330.0, P_Pa=101325.0,
    )
    spec = ColumnSpec("Methanol", "Water", 0.99, 0.99, 101325.0)
    r = BioSteamSimulator().design_column(feed, spec)

    assert r.converged, r.error
    assert r.condenser_duty_kW is not None and r.condenser_duty_kW > 0
    assert r.reboiler_duty_kW is not None and r.reboiler_duty_kW > 0
    assert r.distillate_T_K is not None and r.bottoms_T_K is not None
    assert r.distillate_T_K < r.bottoms_T_K
    assert None not in (r.feed_H_kW, r.distillate_H_kW, r.bottoms_H_kW)


def test_the_thermal_checks_actually_run_on_a_real_design():
    """End to end: the checks must appear in verify_column's output for a real
    BioSTEAM design, not merely pass in a unit test with hand-made numbers."""
    from sepsyn.simulators.biosteam_adapter import BioSteamSimulator
    from sepsyn.simulators.base import ColumnSpec
    from sepsyn.types import Component, Feed
    from sepsyn.verify import verify_column

    feed = Feed(
        components=(Component("Methanol", "67-56-1", 100.0),
                    Component("Water", "7732-18-5", 80.0)),
        T_K=330.0, P_Pa=101325.0,
    )
    spec = ColumnSpec("Methanol", "Water", 0.99, 0.99, 101325.0)
    r = BioSteamSimulator().design_column(feed, spec)
    got = {c.name for c in verify_column(feed, spec, r)}
    assert {"condenser duty", "end temperatures", "energy balance"} <= got


def test_the_adapter_asks_for_a_TOTAL_condenser():
    """BinaryDistillation defaults to partial_condenser=True and the adapter
    never set it, so every design sepsyn has ever produced had a vapour
    distillate -- never chosen, just inherited. A total condenser is the normal
    default and the one a liquid product spec implies. The duty check catches
    the difference: a partial condenser condenses only the reflux, so it lands
    near 16 kJ/mol instead of about 30."""
    from sepsyn.simulators.biosteam_adapter import BioSteamSimulator
    from sepsyn.simulators.base import ColumnSpec
    from sepsyn.types import Component, Feed
    from sepsyn.verify import verify_column

    feed = Feed(
        components=(Component("Methanol", "67-56-1", 100.0),
                    Component("Water", "7732-18-5", 80.0)),
        T_K=330.0, P_Pa=101325.0,
    )
    spec = ColumnSpec("Methanol", "Water", 0.99, 0.99, 101325.0)
    r = BioSteamSimulator().design_column(feed, spec)
    duty = {c.name: c for c in verify_column(feed, spec, r)}["condenser duty"]
    assert duty.passed, duty.detail
