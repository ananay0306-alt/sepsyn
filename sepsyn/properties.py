"""Chemical property lookups. Cheap and pure -- no VLE, no simulator."""
import chemicals
import difflib


class UnknownChemical(ValueError):
    """Raised when a chemical name cannot be resolved to a CAS number."""


def resolve(name: str) -> str:
    """Resolve a chemical name to its CAS number."""
    if not isinstance(name, str):
        raise TypeError(
            f"Chemical name must be a string, not {type(name).__name__}"
        )

    try:
        return chemicals.CAS_from_any(name)
    except ValueError as exc:
        # Generate suggestions on failure path only
        suggestions_text = ""
        try:
            from chemicals.identifiers import pubchem_db
            pubchem_db.autoload_main_db()
            names = list(pubchem_db.name_index.keys())
            matches = difflib.get_close_matches(name, names, n=5, cutoff=0.75)
            if matches:
                suggestions_text = f"\nDid you mean: {', '.join(repr(m) for m in matches)}?"
            else:
                suggestions_text = "\nNo similar names found in the database."
        except Exception:
            # If suggestion lookup fails, still raise UnknownChemical with original error
            pass

        raise UnknownChemical(
            f"Could not resolve chemical name {name!r}.{suggestions_text}"
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
