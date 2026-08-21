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
