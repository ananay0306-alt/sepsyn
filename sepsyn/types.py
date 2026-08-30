"""Core data types. Flows kmol/hr, T in K, P in Pa, everywhere."""
from dataclasses import dataclass

RULE_VISIBLE_FIELDS = frozenset({
    "n_components",
    "n_supercritical_at_feed",
    "min_alpha",
    "has_azeotrope",
    "feed_phase",
    "condensing_T_at_column_P",
    "cooling_water_T",
    "light_key_mole_fraction",
    "heavy_key_mole_fraction",
    "bottoms_T_at_column_P",
    "steam_T",
})


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
    has_azeotrope: bool | None
    """True/False if the azeotrope search actually ran; None means it was
    never checked (no liquid phase exists -- every component is
    supercritical at feed conditions), which is NOT the same claim as
    "checked and found none"."""
    alphas: tuple[Alpha, ...]
    feed_phase: str
    condensing_T_at_column_P: float | None
    cooling_water_T: float
    light_key_mole_fraction: float | None
    heavy_key_mole_fraction: float | None
    bottoms_T_at_column_P: float | None = None
    """Boiling temperature of the heaviest component at column pressure. The
    hot end of the column, and the counterpart to condensing_T_at_column_P.
    None means it could not be computed, NOT that the column runs cold."""
    steam_T: float = 433.15
    """Available heating utility temperature. Default mirrors
    properties.STEAM_T (low pressure steam, 160 C)."""

    def as_namespace(self) -> dict[str, object]:
        """Flat scalars for rule evaluation. Structured fields are withheld."""
        return {name: getattr(self, name) for name in RULE_VISIBLE_FIELDS}
