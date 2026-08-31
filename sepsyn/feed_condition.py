"""Feed thermal condition, q. Heuristic steps 15 to 17.

Step 15 decides q, step 16 decides whether to move it, step 17 says record it.
The third is the one this module exists for: q changes minimum reflux and stage
count, and it is the most commonly unstated assumption in a column
specification. A design that does not carry its q is not comparable to any
other design.

    q = (H_saturated_vapour - H_feed) / (H_saturated_vapour - H_saturated_liquid)

all at the FEED COMPOSITION and the COLUMN pressure.
"""
import contextlib
import io
import warnings
from dataclasses import dataclass

from sepsyn.properties import critical_pressure, critical_temperature, resolve
from sepsyn.types import Feed

warnings.filterwarnings("ignore")

# How far from exactly 1.0 (or 0.0) still counts as saturated. Enthalpy solves
# land a few parts in 1e-6 away from the endpoint they were asked for, and
# reporting "two phase, q = 0.9999997" for a stream that is a saturated liquid
# is noise dressed as a finding.
SATURATION_TOL = 1e-3


@dataclass(frozen=True)
class FeedCondition:
    """q and everything needed to check it.

    The bubble and dew temperatures are carried, not just q, because q alone
    cannot be audited: the same q describes a different stream at a different
    pressure, and a reader has to be able to see which one was meant.
    """
    q: float
    classification: str
    bubble_T_K: float
    dew_T_K: float
    T_K: float
    """Feed temperature the q was computed at."""
    P_Pa: float
    """COLUMN pressure, not feed pressure."""
    basis: str

    @property
    def vapor_fraction(self) -> float:
        """Molar vapour fraction of the feed, 1 - q, clamped to the two-phase
        range. Outside it the feed is single phase and the fraction is exact."""
        return min(1.0, max(0.0, 1.0 - self.q))


def classify(q: float) -> str:
    """Name the thermal condition. The five states of heuristic step 15."""
    if q > 1.0 + SATURATION_TOL:
        return "subcooled_liquid"
    if q >= 1.0 - SATURATION_TOL:
        return "saturated_liquid"
    if q > SATURATION_TOL:
        return "two_phase"
    if q >= -SATURATION_TOL:
        return "saturated_vapor"
    return "superheated_vapor"


_PHRASES = {
    "subcooled_liquid": "subcooled liquid",
    "saturated_liquid": "saturated liquid",
    "two_phase": "part vapour",
    "saturated_vapor": "saturated vapour",
    "superheated_vapor": "superheated vapour",
}


def describe(q: float) -> str:
    """Plain-English thermal condition, for reports read by people."""
    return _PHRASES[classify(q)]


def _stream(tmo, feed: Feed, P_Pa: float):
    s = tmo.Stream(None, T=feed.T_K, P=P_Pa)
    for c in feed.components:
        s.imol[c.name] = c.flow_kmol_hr
    return s


@dataclass(frozen=True)
class SaturationEndpoints:
    """The two enthalpies q is measured between, and the temperatures they sit
    at. Shared by the code that MEASURES q and the code that SETS it, so the
    two can never drift onto different bases -- which is the exact class of
    error (a silent basis mismatch) this project exists to catch."""
    T_bubble_K: float
    H_bubble_kJ_hr: float
    T_dew_K: float
    H_dew_kJ_hr: float

    def q_of(self, H_kJ_hr: float) -> float:
        return (self.H_dew_kJ_hr - H_kJ_hr) / (self.H_dew_kJ_hr - self.H_bubble_kJ_hr)

    def enthalpy_at_q(self, q: float) -> float:
        return self.H_dew_kJ_hr - q * (self.H_dew_kJ_hr - self.H_bubble_kJ_hr)


def saturation_endpoints(feed: Feed, P_Pa: float) -> SaturationEndpoints | None:
    """Saturated-liquid and saturated-vapour states of the feed composition at
    P_Pa, or None where no VLE region exists. See feed_condition for why the
    critical guards are here rather than left to the solver."""
    import thermosteam as tmo

    criticals_P = [critical_pressure(c.cas or resolve(c.name))
                   for c in feed.components]
    criticals_T = [critical_temperature(c.cas or resolve(c.name))
                   for c in feed.components]
    if P_Pa >= max(criticals_P):
        return None

    try:
        with contextlib.redirect_stdout(io.StringIO()):
            chems = tmo.Chemicals(list(feed.names))
            chems.compile()
            tmo.settings.set_thermo(chems)

            saturated_liquid = _stream(tmo, feed, P_Pa)
            saturated_liquid.vle(P=P_Pa, V=0.0)
            T_bubble, H_bubble = float(saturated_liquid.T), float(saturated_liquid.H)

            saturated_vapor = _stream(tmo, feed, P_Pa)
            saturated_vapor.vle(P=P_Pa, V=1.0)
            T_dew, H_dew = float(saturated_vapor.T), float(saturated_vapor.H)
    except Exception:
        return None

    if H_dew - H_bubble <= 0 or T_bubble > max(criticals_T):
        return None
    return SaturationEndpoints(T_bubble, H_bubble, T_dew, H_dew)


def feed_condition(feed: Feed, P_Pa: float) -> FeedCondition | None:
    """q for this feed entering a column at P_Pa, or None if it has no bubble
    point there.

    None means the calculation could not be made -- typically because every
    component is above its critical temperature, so no saturated liquid exists
    to measure q against. It must not be read as q = 0, which is the specific
    claim that the feed is a saturated vapour.
    """
    import thermosteam as tmo

    ends = saturation_endpoints(feed, P_Pa)
    if ends is None:
        return None

    try:
        with contextlib.redirect_stdout(io.StringIO()):
            chems = tmo.Chemicals(list(feed.names))
            chems.compile()
            tmo.settings.set_thermo(chems)
            # A TP flash, NOT a bare Stream.H. An unflashed Stream carries
            # whatever phase it was built with (liquid by default), so reading
            # H off it at 500 K returns a liquid enthalpy for what is really a
            # superheated vapour -- which flips the sign of q and reports a
            # vapour feed as deeply subcooled. Letting VLE settle the phase is
            # what makes the sign trustworthy.
            actual = _stream(tmo, feed, P_Pa)
            actual.vle(T=feed.T_K, P=P_Pa)
            H_feed = float(actual.H)
    except Exception:
        # Returned as a missing number, not raised. Screening runs on feeds
        # that have no liquid phase at all, and "q could not be computed" is a
        # fact about the feed rather than a crash.
        return None

    q = ends.q_of(H_feed)
    return FeedCondition(
        q=q,
        classification=classify(q),
        bubble_T_K=ends.T_bubble_K,
        dew_T_K=ends.T_dew_K,
        T_K=feed.T_K,
        P_Pa=P_Pa,
        basis=(
            f"enthalpy balance against the saturated liquid "
            f"({ends.T_bubble_K:.2f} K) and saturated vapour "
            f"({ends.T_dew_K:.2f} K) of the feed composition at "
            f"{P_Pa/1e5:.3f} bar"
        ),
    )
