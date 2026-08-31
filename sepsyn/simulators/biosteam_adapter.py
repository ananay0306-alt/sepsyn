"""BioSTEAM implementation of the Simulator protocol.

Import is deferred into the methods. BioSTEAM costs several seconds to load and
pulls in a large dependency tree; the rule engine and the whole screening path
must stay usable without it, so nothing at module scope touches it.
"""
import contextlib
import dataclasses
import io
import warnings

from sepsyn.feed_condition import saturation_endpoints
from sepsyn.simulators.base import (
    ColumnResult,
    ColumnSpec,
    FlashResult,
    FlashSpec,
)
from sepsyn.types import Feed

warnings.filterwarnings("ignore")

_EMPTY_COLUMN = ColumnResult({}, {}, 0.0, 0.0, 0.0, 0.0, 0.0, False)
_EMPTY_FLASH = FlashResult({}, {}, 0.0, 0.0, False)


class BioSteamSimulator:
    """Passes recoveries straight through to BioSTEAM.

    No recovery-to-mole-fraction conversion happens here, deliberately.
    BinaryDistillation accepts `product_specification_format="Recovery"` with
    Lr and Hr, which are exactly the two numbers ColumnSpec already carries.
    Converting to a keys-only mole fraction first was possible and gave the
    same answer when measured, but it is a basis change with nothing to gain,
    and a basis change is precisely what went wrong the last time these two
    simulators were compared.
    """

    def _setup(self, feed: Feed):
        import biosteam as bst
        import thermosteam as tmo

        # Units register themselves in a module-level flowsheet, so a second
        # call would collide on the unit ID without this.
        bst.main_flowsheet.clear()
        chems = tmo.Chemicals(list(feed.names))
        chems.compile()
        tmo.settings.set_thermo(chems)
        s = tmo.Stream("feed", T=feed.T_K, P=feed.P_Pa)
        for c in feed.components:
            s.imol[c.name] = c.flow_kmol_hr
        return bst, s

    def _apply_and_measure_feed_q(self, s, feed: Feed,
                                  spec: ColumnSpec) -> float | None:
        """Impose spec.feed_q if one was asked for, and report the q the column
        actually sees. Heuristic steps 15 to 17.

        The asymmetry is deliberate. When spec.feed_q is None the stream is left
        exactly as it arrived and only MEASURED -- because that is what every
        design before this field existed already did, and silently flashing the
        feed here would change all of their numbers under the cover of adding a
        record. Only an explicit q moves the feed.
        """
        ends = saturation_endpoints(feed, spec.pressure_Pa)
        if ends is None:
            # No VLE region at this pressure, so there is nothing to measure q
            # against. None, not 0.0 -- 0.0 is the claim "saturated vapour".
            return None
        if spec.feed_q is not None:
            s.vle(P=spec.pressure_Pa, H=ends.enthalpy_at_q(spec.feed_q))
            return spec.feed_q
        return ends.q_of(float(s.H))

    def design_column(self, feed: Feed, spec: ColumnSpec) -> ColumnResult:
        try:
            if spec.condenser_type not in ("total", "partial"):
                raise ValueError(
                    f"condenser_type must be 'total' or 'partial', got "
                    f"{spec.condenser_type!r}. Guessing here would hide the "
                    f"choice, which is the one thing step 22 forbids."
                )
            with contextlib.redirect_stdout(io.StringIO()):
                bst, s = self._setup(feed)
                feed_q = self._apply_and_measure_feed_q(s, feed, spec)
                col = bst.BinaryDistillation(
                    "C1", ins=s, outs=("D", "B"),
                    LHK=(spec.light_key, spec.heavy_key),
                    product_specification_format="Recovery",
                    Lr=spec.lk_recovery_to_distillate,
                    Hr=spec.hk_recovery_to_bottoms,
                    k=spec.reflux_over_minimum,
                    P=spec.pressure_Pa,
                    is_divided=False,
                    # Taken from the SPEC, not inherited and not hardcoded.
                    # BinaryDistillation defaults to a PARTIAL condenser, which
                    # condenses only the reflux and so does roughly R/(R+1) of
                    # the duty and hands back a vapour distillate. A liquid
                    # product is the normal default and the one every
                    # downstream cost and comparison assumes -- but it is now a
                    # recorded decision (step 22) rather than a constant.
                    partial_condenser=(spec.condenser_type == "partial"),
                )
                col.simulate()
                D, B = col.outs
                d = col.design_results
                # PROCESS duties, from the condenser and reboiler exchangers.
                #
                # NOT col.heat_utilities. Those are UTILITY duties -- what you
                # buy -- and BioSTEAM inflates the steam side by the heating
                # utility's efficiency, about 5%. Measured on the acceptance
                # feed: utility Qr - Qc = 327.7 kW against col.Hnet of 221.8 kW,
                # a constant 105.9 kW gap, while the process-side balance closes
                # exactly. Mixing the two makes an energy-balance check compare
                # purchased heat against process enthalpy and fail by ~5% on a
                # perfectly good design. kJ/hr, so /3600 gives kW.
                qc = abs(float(col.condenser.Q)) / 3600.0
                qr = abs(float(col.reboiler.Q)) / 3600.0
                return ColumnResult(
                    # Every feed component is reported, not just the keys.
                    # Nothing in a light/heavy-key spec constrains the others,
                    # so where they went is a result, not a detail.
                    distillate={n: float(D.imol[n]) for n in feed.names},
                    bottoms={n: float(B.imol[n]) for n in feed.names},
                    stages=float(d.get("Actual stages", 0.0)),
                    reflux=float(d.get("Reflux", 0.0)),
                    minimum_reflux=float(d.get("Minimum reflux", 0.0)),
                    installed_cost_USD=float(col.installed_cost),
                    utility_cost_USD_hr=float(col.utility_cost),
                    converged=True, error=None,
                    condenser_duty_kW=float(qc),
                    reboiler_duty_kW=float(qr),
                    distillate_T_K=float(D.T),
                    bottoms_T_K=float(B.T),
                    feed_H_kW=float(s.H) / 3600.0,
                    # BioSTEAM reports Diameter in FEET.
                    column_diameter_m=float(d.get("Diameter", 0.0)) * 0.3048
                    or None,
                    feed_q=feed_q,
                    distillate_H_kW=float(D.H) / 3600.0,
                    bottoms_H_kW=float(B.H) / 3600.0,
                )
        except Exception as exc:
            # Returned as data, never raised. A caller sweeping refluxes or
            # pressures will hit infeasible points routinely, and an infeasible
            # point is an answer about the design, not a crash.
            return dataclasses.replace(
                _EMPTY_COLUMN, error=f"{type(exc).__name__}: {exc}"
            )

    def design_flash(self, feed: Feed, spec: FlashSpec) -> FlashResult:
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                bst, s = self._setup(feed)
                kwargs = {
                    k: v for k, v in (("T", spec.T_K),
                                      ("P", spec.P_Pa),
                                      ("V", spec.vapor_fraction))
                    if v is not None
                }
                if len(kwargs) != 2:
                    raise ValueError(
                        "a flash has two degrees of freedom: specify exactly "
                        f"two of T_K, P_Pa, vapor_fraction (got {len(kwargs)})"
                    )
                f = bst.Flash("F1", ins=s, outs=("V", "L"), **kwargs)
                f.simulate()
                V, L = f.outs
                return FlashResult(
                    vapor={n: float(V.imol[n]) for n in feed.names},
                    liquid={n: float(L.imol[n]) for n in feed.names},
                    T_K=float(V.T), P_Pa=float(V.P),
                    converged=True, error=None,
                )
        except Exception as exc:
            return dataclasses.replace(
                _EMPTY_FLASH, error=f"{type(exc).__name__}: {exc}"
            )
