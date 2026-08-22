"""Azeotrope detection.

Deliberately a separate module from properties.py: this is a SEARCH over
composition space needing the full VLE engine, not a database lookup, and it
is the piece most likely to be quietly wrong. It gets its own tests with
documented literature values.
"""
import contextlib
import io
import itertools
import warnings
from dataclasses import dataclass
from typing import Sequence

warnings.filterwarnings("ignore")

# Grid resolution for the sign-change search. Detection requires alpha to
# cross 1.0 *between two consecutive samples*; an azeotrope narrower than one
# grid interval is missed with NO error -- the search just returns [], which
# makes has_azeotrope=False, so R-03 never fires and the tool confidently
# recommends distillation for a mixture that cannot actually be distilled.
# That is a wrong answer, not a wrong number, so the resolution has to be
# chosen deliberately rather than left at whatever value first passed tests.
#
# Measured six literature azeotropes at 51 points (interval 0.02) and again
# at 201 points (interval 0.005) -- identical x_az to 3 decimals at both
# resolutions:
#   Ethanol/Water      x=0.894 / x=0.894
#   Acetone/Methanol   x=0.786 / x=0.786
#   Ethanol/Benzene    x=0.462 / x=0.462
#   Water/Formic acid  x=0.422 / x=0.422
#   Methanol/Benzene   x=0.616 / x=0.616
#   Ethanol/Toluene    x=0.813 / x=0.813
# All six are broad crossings, so this does NOT bound the narrow-azeotrope
# case -- it only shows 51 points isn't currently missing anything on these
# six. The cost of more resolution is nil (0.01 s warm at 101 points, 0.02 s
# at 201), so there is no reason to stay coarse. Set to 201.
SCAN_POINTS = 201

# Ignore "azeotropes" found within this of a pure component (x=0 or x=1) --
# guards against reporting a spurious crossing that is really just numerical
# noise near a pure-component endpoint, not a real azeotrope. At 201 points
# (interval 0.005) this is now a 4-interval band rather than a 1-interval
# band, i.e. a wider, more conservative guard than before, not a narrower
# one -- so it stays sensible at the finer grid without being loosened.
MIN_SEPARATION = 0.02


@dataclass(frozen=True)
class Azeotrope:
    components: tuple[str, str]
    x: tuple[float, float]
    T_K: float
    P_Pa: float


def _alpha_curve(chem_a: str, chem_b: str, P_Pa: float) -> list[tuple[float, float, float]]:
    """(x_a, alpha, T) across composition, at the bubble point.

    Uses BubblePoint rather than Stream.vle(V=0.0). At V=0 the vapour phase
    holds ZERO moles, so a vapour composition read off the stream is all zeros
    and no azeotrope is ever found. BubblePoint returns the INCIPIENT vapour
    composition, which is what relative volatility is defined against.

    Chemicals and the solver are built once per pair, not once per point.
    """
    import numpy as np
    import thermosteam as tmo

    out: list[tuple[float, float, float]] = []
    with contextlib.redirect_stdout(io.StringIO()):
        chems = tmo.Chemicals([chem_a, chem_b])
        chems.compile()
        tmo.settings.set_thermo(chems)
        bp = tmo.equilibrium.BubblePoint(chemicals=chems)
        for i in range(1, SCAN_POINTS - 1):
            x = i / (SCAN_POINTS - 1)
            try:
                T, y = bp.solve_Ty(np.array([x, 1.0 - x]), P=P_Pa)
            except Exception:
                continue
            ya, yb = float(y[0]), float(y[1])
            if min(ya, yb) <= 0:
                continue
            out.append((x, (ya / x) / (yb / (1.0 - x)), float(T)))
    return out


def find_azeotropes(names: Sequence[str], P_Pa: float = 101325.0) -> list[Azeotrope]:
    """Find binary azeotropes by scanning for alpha crossing 1.0.

    An azeotrope is exactly where relative volatility equals one: vapour and
    liquid have the same composition, so no number of stages can cross it.
    """
    results: list[Azeotrope] = []
    for a, b in itertools.combinations(names, 2):
        prev_alpha: float | None = None
        prev_x: float | None = None
        for x, alpha, T in _alpha_curve(a, b, P_Pa):
            if prev_alpha is not None and (prev_alpha - 1.0) * (alpha - 1.0) < 0:
                # linear interpolation onto alpha == 1
                frac = (1.0 - prev_alpha) / (alpha - prev_alpha)
                x_az = prev_x + frac * (x - prev_x)
                if MIN_SEPARATION < x_az < 1.0 - MIN_SEPARATION:
                    results.append(Azeotrope(
                        components=(a, b),
                        x=(x_az, 1.0 - x_az),
                        T_K=T, P_Pa=P_Pa,
                    ))
                    break
            prev_alpha, prev_x = alpha, x
    return results
