"""Chemical property lookups. Cheap and pure -- no VLE, no simulator."""
import chemicals


class UnknownChemical(ValueError):
    """Raised when a chemical name cannot be resolved to a CAS number."""


def resolve(name: str) -> str:
    """Resolve a chemical name to its CAS number."""
    try:
        return chemicals.CAS_from_any(name)
    except Exception as exc:
        raise UnknownChemical(
            f"Could not resolve chemical name {name!r}. "
            f"Use an exact name such as 'Methanol', 'Water', '1-butene'."
        ) from exc


def boiling_point(cas: str) -> float:
    """Normal boiling point, K."""
    return float(chemicals.Tb(cas))


def critical_temperature(cas: str) -> float:
    """Critical temperature, K."""
    return float(chemicals.Tc(cas))


def critical_pressure(cas: str) -> float:
    """Critical pressure, Pa."""
    return float(chemicals.Pc(cas))
