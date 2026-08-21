"""Chemical property lookups. Cheap and pure -- no VLE, no simulator."""
import chemicals
import difflib
import warnings


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
    except (ValueError, LookupError) as exc:
        # chemicals.CAS_from_any raises ValueError on an unresolved name --
        # but once thermosteam has configured the thermo package (which it
        # always has in the real tool, since Task 5 imports both this module
        # and azeotropes.py), the identifier lookup is swapped out and the
        # same failure raises builtins.LookupError instead. Catch both, or a
        # misspelled chemical surfaces a raw traceback instead of
        # UnknownChemical with suggestions. Do not narrow this back down.
        # Generate suggestions on failure path only
        suggestions_text = ""
        try:
            from chemicals.identifiers import pubchem_db
            # thermosteam replaces this module-level object with its own
            # ChemicalMetadataDB (no autoload_main_db method) once the thermo
            # package is configured. Its name_index is already populated in
            # that case, so only call autoload_main_db when it exists rather
            # than letting the AttributeError get swallowed below and silently
            # drop all suggestions.
            if hasattr(pubchem_db, "autoload_main_db"):
                pubchem_db.autoload_main_db()
            names = list(pubchem_db.name_index.keys())
            matches = difflib.get_close_matches(name.lower(), names, n=5, cutoff=0.75)
            if matches:
                suggestions_text = f"\nDid you mean: {', '.join(repr(m) for m in matches)}?"
            else:
                suggestions_text = "\nNo similar names found in the database."
        except (AttributeError, KeyError, LookupError) as suggest_exc:
            # Narrowed from a bare `except Exception: pass`, which is what let
            # the pubchem_db swap (thermosteam replacing the module-level
            # ChemicalMetadataDB) go undetected for a whole extra debugging
            # round -- the guard meant to protect against a broken suggestion
            # engine became the thing hiding it. These three types are the
            # failure modes a swapped or renamed database actually produces
            # (missing attribute, missing dict key, failed lookup). Anything
            # else is a genuine bug and should propagate. UnknownChemical is
            # still raised with the original name either way; only the
            # suggestion text is lost, and now loudly.
            warnings.warn(
                f"sepsyn: chemical-name suggestion lookup failed: {suggest_exc!r}",
                RuntimeWarning,
            )

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


from sepsyn.types import Feed

COOLING_WATER_T = 313.15  # K, 40 C -- design limit used throughout


def count_supercritical(feed: Feed) -> int:
    """How many components are above their critical temperature at feed T.

    If this equals the component count there is no liquid phase and no
    distillation is possible at any pressure.
    """
    return sum(
        1 for c in feed.components
        if feed.T_K > critical_temperature(c.cas or resolve(c.name))
    )
