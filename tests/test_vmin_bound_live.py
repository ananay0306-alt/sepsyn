"""V_min must be a genuine LOWER BOUND. Opt in with: pytest -m dwsim_live

A rigorous column given more and more stages needs less and less reflux,
approaching the minimum from ABOVE. If a rigorous solve ever converges using
LESS vapour than our computed minimum, our implementation is wrong.

This is the unambiguous failure signal M2 never had. A bound is falsified by a
single counterexample; a design comparison could only ever produce a gap that
then needed attributing, which is how the 09-09 measurement sat unexplained for
a day.

The comparison is deliberately made on BENZENE/TOLUENE, a binary. It has no
non-keys at all, so nothing about heavy-non-key handling -- the open question
from `2026-09-10-the-falling-rmin-is-the-feed-condition.md` -- can confound the
result. If our bound is wrong even here, it is wrong for a simple reason.
"""
import pytest

from sepsyn.feed_condition import feed_condition
from sepsyn.properties import resolve
from sepsyn.simulators.base import ColumnSpec
from sepsyn.simulators.dwsim_adapter import DwsimSimulator, LiveTransport
from sepsyn.types import Component, Feed
from sepsyn.vmin.pipeline import volatilities_for
from sepsyn.vmin.vapour import minimum_vapour

pytestmark = pytest.mark.dwsim_live

P_PA = 101325.0
STAGE_COUNTS = (20, 30, 45)

# MEASURED, not chosen. The 09-09 probe found this column converging in seconds
# with the feed low in the tower and timing out with it mid-tower; a first run
# of this file at feed_stage = n // 2 confirmed it, sitting on DWSIM's solver
# for 5.4 minutes before the transport gave up. At 0.7 it converges in 19 s.
FEED_STAGE_FRACTION = 0.7

# The feed is taken AS IT ARRIVES rather than having a thermal condition
# imposed on it. Imposing q was the second half of that non-convergence, and
# the comparison does not need it: our own V_min is computed from the q this
# same feed actually has, so both sides describe the same stream.
IMPOSE_FEED_Q = None


def benzene_toluene():
    return Feed(components=(Component("Benzene", resolve("Benzene"), 60.0),
                            Component("Toluene", resolve("Toluene"), 40.0)),
                T_K=353.0, P_Pa=P_PA)


def latent_heat_kJ_per_mol(names_to_flows: dict[str, float], T_K: float) -> float:
    """Molar latent heat of a stream at T, flow-weighted.

    The rigorous column reports a condenser DUTY, not a vapour flow. For a
    total condenser the duty is the heat of condensing the whole overhead
    vapour, so V = Q / lambda. This is the same derivation the 09-09 finding
    used to recover R = 4.95 from 258.2 kW.
    """
    import thermosteam as tmo

    total = sum(names_to_flows.values())
    out = 0.0
    for name, flow in names_to_flows.items():
        chem = tmo.Chemical(name)
        out += (flow / total) * chem.Hvap(T_K) / 1000.0
    return out


def rigorous_vapour_kmol_hr(run) -> float:
    """Overhead vapour implied by the converged condenser duty."""
    T = run.distillate_T_K
    lam = latent_heat_kJ_per_mol(run.distillate_mol_s, T)
    return run.condenser_duty_kW / lam * 3.6      # mol/s -> kmol/hr


def test_a_rigorous_column_never_converges_BELOW_the_computed_minimum():
    """THE falsification test. More stages means less reflux, so the sequence
    must fall toward V_min and stop above it. A converged solve underneath the
    bound is proof the bound is wrong, and no part of M6 survives it."""
    feed = benzene_toluene()
    alpha, basis = volatilities_for(feed, P_PA)
    fc = feed_condition(feed, P_PA)
    q = fc.q if fc else 1.0
    bound = minimum_vapour(("Benzene", "Toluene"), alpha,
                           {"Benzene": 60.0, "Toluene": 40.0}, q, k=1, alpha_basis=basis)

    sim = DwsimSimulator(LiveTransport(timeout_s=300))
    spec = ColumnSpec(light_key="Benzene", heavy_key="Toluene",
                      lk_recovery_to_distillate=0.99,
                      hk_recovery_to_bottoms=0.99,
                      pressure_Pa=P_PA, feed_q=IMPOSE_FEED_Q)

    measured = {}
    for n in STAGE_COUNTS:
        run = sim.design_from_stages(
            feed, spec, n, feed_stage=int(n * FEED_STAGE_FRACTION))
        if not run.converged:
            pytest.skip(f"DWSIM did not converge at {n} stages: {run.errors}")
        measured[n] = rigorous_vapour_kmol_hr(run)

    print(f"\n  V_min (ours, {bound.alpha_basis}) = "
          f"{bound.V_min_kmol_hr:.2f} kmol/hr")
    for n, V in sorted(measured.items()):
        print(f"  {n:>3} theoretical stages: V = {V:8.2f}  "
              f"ratio {V / bound.V_min_kmol_hr:.3f}")

    for n, V in measured.items():
        assert V >= bound.V_min_kmol_hr, (
            f"a rigorous solve at {n} stages converged on {V:.2f} kmol/hr, "
            f"BELOW our computed minimum of {bound.V_min_kmol_hr:.2f}. The "
            f"bound is wrong and nothing in M6 stands until it is found."
        )


def test_more_stages_needs_LESS_vapour():
    """The other half of approaching from above: the sequence must be
    decreasing. A rigorous column that wanted MORE vapour as stages were added
    would mean the stage count is not reaching the solver at all, which is
    exactly the 09-09 finding-2 trap."""
    feed = benzene_toluene()
    fc = feed_condition(feed, P_PA)
    q = fc.q if fc else 1.0
    sim = DwsimSimulator(LiveTransport(timeout_s=300))
    spec = ColumnSpec(light_key="Benzene", heavy_key="Toluene",
                      lk_recovery_to_distillate=0.99,
                      hk_recovery_to_bottoms=0.99,
                      pressure_Pa=P_PA, feed_q=IMPOSE_FEED_Q)

    vapours = []
    for n in STAGE_COUNTS:
        run = sim.design_from_stages(
            feed, spec, n, feed_stage=int(n * FEED_STAGE_FRACTION))
        if not run.converged:
            pytest.skip(f"DWSIM did not converge at {n} stages: {run.errors}")
        vapours.append(rigorous_vapour_kmol_hr(run))

    assert vapours == sorted(vapours, reverse=True), (
        f"vapour should fall as stages are added, got {vapours}")
