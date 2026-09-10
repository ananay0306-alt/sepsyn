"""Minimum vapour for one sharp split.

A BOUND, not a design. The least vapour that must be boiled to achieve the
split at infinite stages. Nothing about stages, tray efficiency, condenser type
or cost enters it, which is exactly why it is the selection criterion: every
defect measured on 09-09 and 09-10 lives downstream of Underwood.
"""
from dataclasses import dataclass

from sepsyn.vmin.underwood import underwood_theta


@dataclass(frozen=True)
class SplitVapour:
    V_min_kmol_hr: float
    theta: float
    light: tuple[str, ...]
    heavy: tuple[str, ...]
    alpha_basis: str
    """The condition the relative volatilities were evaluated at. A bare alpha
    is meaningless; same discipline as sepsyn.types.Alpha."""


def minimum_vapour(order: tuple[str, ...], alpha: dict[str, float],
                   flows: dict[str, float], q: float, k: int,
                   alpha_basis: str = "") -> SplitVapour:
    """V_min for splitting `order` at `k`, sending `order[:k]` overhead.

    Sharp split: the light group leaves entirely overhead, so its members are
    the only contributors to the rectifying vapour.
    """
    if not 1 <= k <= len(order) - 1:
        raise ValueError(
            f"split point {k} is outside a {len(order)}-component group; a "
            f"split must leave at least one component on each side"
        )
    light, heavy = order[:k], order[k:]
    theta = underwood_theta(alpha, _normalised(flows, order), q,
                            light_key=order[k - 1], heavy_key=order[k])
    V = sum(alpha[i] * flows[i] / (alpha[i] - theta) for i in light)
    return SplitVapour(
        V_min_kmol_hr=V, theta=theta, light=light, heavy=heavy,
        alpha_basis=alpha_basis or "relative volatilities supplied by caller",
    )


def _normalised(flows: dict[str, float], order: tuple[str, ...]) -> dict:
    """Group mole fractions. Underwood's equation takes compositions, so a
    downstream group must be normalised against ITS OWN total, not the fresh
    feed's."""
    total = sum(flows[i] for i in order)
    return {i: flows[i] / total for i in order}
