"""Underwood's constant, from the equation.

    sum_i [ alpha_i z_i / (alpha_i - theta) ] = 1 - q

Implemented here rather than taken from BioSTEAM's ShortcutColumn on purpose.
A measurement on 2026-09-09 found that chain's minimum reflux falling as heavy
non-key content rose, and it could not be established whether that was a defect
in the package or a misuse of it. A bound this milestone rests on has to be
code that can be read, and running our own on the same feeds is the cheapest
way to settle the question.

The root matters as much as the equation. theta must lie strictly between the
volatilities of the two KEYS; a root from a different interval solves the same
equation and gives a different, wrong, minimum vapour.
"""
from scipy.optimize import brentq

# The pole at alpha_i = theta makes the residual infinite at each end of the
# interval. Step inside by this fraction of the interval to bracket safely.
_EDGE = 1e-9


class NoUnderwoodRoot(ValueError):
    """No root exists in the interval between the two keys' volatilities."""


def _residual(theta: float, alpha: dict, z: dict, q: float) -> float:
    return sum(alpha[i] * z[i] / (alpha[i] - theta) for i in z) - (1.0 - q)


def underwood_theta(alpha: dict[str, float], z: dict[str, float], q: float,
                    light_key: str, heavy_key: str) -> float:
    """The Underwood constant for a sharp split between these two keys."""
    for key in (light_key, heavy_key):
        if key not in alpha or key not in z:
            raise NoUnderwoodRoot(
                f"{key!r} is not in this group, so no root can be found for a "
                f"split at it. Group: {sorted(z)}"
            )
    a_hk, a_lk = alpha[heavy_key], alpha[light_key]
    if not a_lk > a_hk:
        raise NoUnderwoodRoot(
            f"the keys have volatilities {a_lk} and {a_hk}: there is no "
            f"interval between them, so no root exists. Equal volatility means "
            f"the pair cannot be separated by distillation, which R-02 tests "
            f"for separately."
        )
    span = a_lk - a_hk
    lo, hi = a_hk + _EDGE * span, a_lk - _EDGE * span
    try:
        return brentq(_residual, lo, hi, args=(alpha, z, q), xtol=1e-12)
    except ValueError as exc:
        raise NoUnderwoodRoot(
            f"no sign change between alpha_HK={a_hk} and alpha_LK={a_lk} for "
            f"q={q}: {exc}"
        ) from exc
