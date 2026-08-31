"""Liquid-liquid split detection. Heuristic step 6.

A separate module from properties.py for the same reason azeotropes.py is: this
is a SEARCH over composition space needing the full activity-coefficient model,
not a database lookup.

Step 6 is the one screening check whose failure mode is silence. A mixture with
too low a relative volatility produces a visibly enormous stage count; an
azeotrope produces a design that will not converge. A missed liquid-liquid
split produces a perfectly reasonable-looking column that describes a
separation which will not happen, because the vapour-liquid model it was
designed with never represented the second liquid phase at all.
"""
import contextlib
import io
import itertools
import warnings
from dataclasses import dataclass
from typing import Sequence

warnings.filterwarnings("ignore")

# Coarser than the azeotrope scan (201). A miscibility gap is a wide contiguous
# region -- water/n-butanol occupies about 20 of 49 sampled compositions and
# water/benzene very nearly all of them -- so it does not need the resolution a
# narrow azeotrope crossing does, and each point here costs an LLE solve rather
# than a bubble-point solve.
SCAN_POINTS = 51

# THE detection criterion, and the reason this module is not three lines long.
#
# Both phases holding material is NOT evidence of a split. Asked to flash a
# fully miscible mixture, thermosteam's LLE solver returns two phases of
# IDENTICAL composition -- one liquid divided in two, which is a degenerate
# solution rather than a miscibility gap. Measured at 1 atm across composition:
#
#   Ethanol/Water    two phases reported, dx = 0.0000   miscible, correct
#   Water/n-Butanol  two phases reported, dx = 0.5082   splits, correct
#
# Detecting on phase amounts alone therefore reported ethanol/water as
# splitting, which would have fired the rule on the single most common binary
# in the whole test suite. Detecting on composition difference separates the
# two cases by more than two orders of magnitude, so the threshold sits in a
# gap rather than on a slope.
MIN_COMPOSITION_DIFFERENCE = 0.01

# A phase holding less than this fraction of the total is numerical residue,
# not a phase.
MIN_PHASE_FRACTION = 1e-3

# KNOWN FALSE POSITIVE, measured, and not fixable by any threshold here.
#
# UNIFAC predicts a spurious miscibility gap for water/glycerol, which are in
# fact miscible in all proportions. Measured at 1 atm across 49 compositions,
# against pairs of known behaviour:
#
#   pair               truth      points  width  max dx
#   Water/n-Butanol    SPLITS         20   0.42   0.510
#   Water/Benzene      SPLITS         48   0.94   0.995
#   Water/Glycerol     miscible       10   0.22   0.493   <- false positive
#   Ethanol/Water      miscible        0   0.00   0.000
#   Methanol/Water     miscible        0   0.00   0.000
#   Methanol/Glycerol  miscible        0   0.00   0.000
#   Benzene/Toluene    miscible        0   0.00   0.000
#   Ethanol/Benzene    miscible        0   0.00   0.000
#
# Seven of eight are classified correctly. The eighth is indistinguishable from
# a true split by point count, gap width and composition difference alike, so
# no tightening of the constants above separates it -- the error is in the
# activity-coefficient model, not in this search. Aqueous polyols are a known
# weak point for UNIFAC liquid-liquid predictions.
#
# This is why R-12 carries the verdict `caution` rather than `undetermined`.
# An undetermined verdict blocks design, and blocking design on a false alarm
# at this rate is worse calibrated than flagging it and letting the reader
# dismiss it -- which they can, because the rule names the pair.


@dataclass(frozen=True)
class LiquidSplit:
    """Two liquid phases, WITH the conditions they were found at.

    Same discipline as Alpha: a split is a property of a pair at a temperature
    and pressure, not of a pair. A bare boolean cannot be checked by a reader.
    """
    components: tuple[str, str]
    overall_x: float
    """Overall mole fraction of the FIRST component at which the split was
    found. The first one found while scanning upward, not the middle or the
    widest point of the gap."""
    x_phase_1: float
    x_phase_2: float
    """Mole fraction of the first component in each liquid phase."""
    T_K: float
    P_Pa: float


def _split_at(tmo, a: str, b: str, x: float, T_K: float,
              P_Pa: float) -> tuple[float, float] | None:
    """Phase compositions at one point, or None if there is only one liquid."""
    s = tmo.Stream(None, T=T_K, P=P_Pa)
    s.imol[a] = x
    s.imol[b] = 1.0 - x
    try:
        s.lle(T=T_K, P=P_Pa)
    except Exception:
        return None

    heavy = [float(v) for v in s.imol["L"]]
    light = [float(v) for v in s.imol["l"]]
    total_heavy, total_light = sum(heavy), sum(light)
    if min(total_heavy, total_light) <= MIN_PHASE_FRACTION:
        return None

    x1, x2 = heavy[0] / total_heavy, light[0] / total_light
    if abs(x1 - x2) < MIN_COMPOSITION_DIFFERENCE:
        # Two phases of the same composition. See MIN_COMPOSITION_DIFFERENCE.
        return None
    return x1, x2


def find_liquid_split(names: Sequence[str],
                      P_Pa: float = 101325.0) -> LiquidSplit | None:
    """First liquid-liquid split found scanning composition, or None.

    Each composition is tested at ITS OWN bubble temperature, because that is
    the temperature the corresponding tray sits at and miscibility gaps are
    strongly temperature dependent.

    That bubble temperature comes from the ordinary vapour-liquid model -- the
    very model step 6 says is wrong for a splitting mixture. The circularity is
    real and is accepted deliberately: the VLE bubble point is used only to
    place the probe somewhere near where the column would operate, and if a
    split is found there, the finding is precisely that this temperature should
    not be trusted either. It is a screening test, not a three-phase flash.

    Returns on the FIRST split found rather than mapping the whole gap. The
    question step 6 asks is whether the mixture splits anywhere, and a gap is
    contiguous, so the remaining points would add cost without adding an answer.
    """
    import numpy as np
    import thermosteam as tmo

    for a, b in itertools.combinations(names, 2):
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                chems = tmo.Chemicals([a, b])
                chems.compile()
                tmo.settings.set_thermo(chems)
                bp = tmo.equilibrium.BubblePoint(chemicals=chems)
            except Exception:
                continue
            for i in range(1, SCAN_POINTS - 1):
                x = i / (SCAN_POINTS - 1)
                try:
                    T, _ = bp.solve_Ty(np.array([x, 1.0 - x]), P=P_Pa)
                except Exception:
                    continue
                phases = _split_at(tmo, a, b, x, float(T), P_Pa)
                if phases is None:
                    continue
                return LiquidSplit(
                    components=(a, b), overall_x=x,
                    x_phase_1=phases[0], x_phase_2=phases[1],
                    T_K=float(T), P_Pa=P_Pa,
                )
    return None
