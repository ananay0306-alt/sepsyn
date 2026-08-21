"""Core data types. Flows kmol/hr, T in K, P in Pa, everywhere."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Component:
    name: str
    cas: str
    flow_kmol_hr: float


@dataclass(frozen=True)
class Feed:
    components: tuple[Component, ...]
    T_K: float
    P_Pa: float

    def __post_init__(self) -> None:
        if self.total_kmol_hr <= 0:
            raise ValueError("total flow must be positive")

    @property
    def total_kmol_hr(self) -> float:
        return sum(c.flow_kmol_hr for c in self.components)

    @property
    def mole_fractions(self) -> dict[str, float]:
        total = self.total_kmol_hr
        return {c.name: c.flow_kmol_hr / total for c in self.components}

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(c.name for c in self.components)


@dataclass(frozen=True)
class Alpha:
    """Relative volatility ALWAYS carries the conditions it was computed at.

    A bare alpha is meaningless -- it is a property of a pair at a condition,
    not of a pair.
    """
    pair: tuple[str, str]
    value: float
    T_K: float
    P_Pa: float
    basis: str


@dataclass(frozen=True)
class PropertyRecord:
    """The ONLY thing the rule engine may see.

    Rules cannot reach the simulator or the raw chemicals, which is what makes
    the engine testable with a hand-written record and no chemistry at all.
    """
    n_components: int
    n_supercritical_at_feed: int
    min_alpha: float | None
    has_azeotrope: bool
    alphas: tuple[Alpha, ...]
    feed_phase: str
    condensing_T_at_column_P: float | None
    cooling_water_T: float
    light_key_mole_fraction: float | None
    heavy_key_mole_fraction: float | None

    def as_namespace(self) -> dict[str, object]:
        """Flat scalars for rule evaluation. Structured fields are withheld."""
        return {
            "n_components": self.n_components,
            "n_supercritical_at_feed": self.n_supercritical_at_feed,
            "min_alpha": self.min_alpha,
            "has_azeotrope": self.has_azeotrope,
            "feed_phase": self.feed_phase,
            "condensing_T_at_column_P": self.condensing_T_at_column_P,
            "cooling_water_T": self.cooling_water_T,
            "light_key_mole_fraction": self.light_key_mole_fraction,
            "heavy_key_mole_fraction": self.heavy_key_mole_fraction,
        }
