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
STEAM_T = 433.15          # K, 160 C -- low pressure steam, the default hot utility
STEAM_APPROACH_K = 5.0    # K, driving force the reboiler needs below the steam


def count_supercritical(feed: Feed) -> int:
    """How many components are above their critical temperature at feed T.

    If this equals the component count there is no liquid phase and no
    distillation is possible at any pressure.
    """
    return sum(
        1 for c in feed.components
        if feed.T_K > critical_temperature(c.cas or resolve(c.name))
    )


import contextlib
import io
import itertools
import warnings

from sepsyn.types import Alpha, PropertyRecord
from sepsyn.azeotropes import find_azeotropes
from sepsyn.lle import find_liquid_split

warnings.filterwarnings("ignore")


def relative_volatilities(feed: Feed, P_Pa: float) -> tuple[Alpha, ...]:
    """Alpha for every adjacent pair, at the mixture bubble point.

    Computed where the separation actually happens, not at feed conditions --
    a feed at 25 C tells you nothing about a column running at 80 C.
    """
    import numpy as np
    import thermosteam as tmo

    names = list(feed.names)
    out: list[Alpha] = []
    with contextlib.redirect_stdout(io.StringIO()):
        chems = tmo.Chemicals(names)
        chems.compile()
        tmo.settings.set_thermo(chems)
        # BubblePoint, NOT Stream.vle(V=0.0): at V=0 the vapour phase holds zero
        # moles, so a vapour composition read off the stream is all zeros and no
        # alpha is ever computed. BubblePoint returns the incipient vapour.
        bp = tmo.equilibrium.BubblePoint(chemicals=chems)
        z = np.array([c.flow_kmol_hr for c in feed.components], dtype=float)
        total = float(z.sum())
        if total <= 0:
            return ()
        z = z / total
        try:
            T, y = bp.solve_Ty(z, P=P_Pa)
        except Exception:
            return ()
        xs = dict(zip(names, [float(v) for v in z]))
        ys = dict(zip(names, [float(v) for v in y]))
        for a, b in itertools.combinations(names, 2):
            xa, xb, ya, yb = xs[a], xs[b], ys[a], ys[b]
            if min(xa, xb, ya, yb) <= 0:
                # Guards exact zeros only. A non-volatile such as glycerol
                # does NOT read y = 0 here -- BubblePoint gives it a tiny but
                # strictly positive incipient vapour fraction (~1e-9), so this
                # branch rarely triggers for it in practice. That is correct
                # chemistry, not a bug: a near-zero vapour fraction produces a
                # very large but finite alpha, which means the pair is
                # trivially separable, and min_alpha (the smallest alpha
                # returned) is unaffected by these large values.
                continue
            out.append(Alpha(
                pair=(a, b),
                value=(ya / xa) / (yb / xb),
                T_K=float(T), P_Pa=P_Pa,
                basis="bubble point at column P",
            ))
    return tuple(out)


def condensing_temperature(name: str, P_Pa: float) -> float | None:
    """Saturation temperature of a pure component at P, or None if it cannot
    be condensed at that pressure. Used to decide whether the overhead can be
    condensed against cooling water or needs refrigeration."""
    import thermosteam as tmo

    cas = resolve(name)
    if P_Pa >= critical_pressure(cas):
        return None
    with contextlib.redirect_stdout(io.StringIO()):
        chems = tmo.Chemicals([name])
        chems.compile()
        tmo.settings.set_thermo(chems)
        s = tmo.Stream(None, P=P_Pa)
        s.imol[name] = 1.0
        try:
            s.vle(P=P_Pa, V=0.0)
            return float(s.T)
        except Exception:
            return None


def build_property_record(
    feed: Feed,
    column_P_Pa: float | None = None,
    light_key: str | None = None,
    heavy_key: str | None = None,
    column_P_basis: str = "",
) -> PropertyRecord:
    """Assemble everything the rule engine is allowed to see."""
    P = column_P_Pa if column_P_Pa is not None else feed.P_Pa
    n_super = count_supercritical(feed)

    if n_super == len(feed.components):
        alphas: tuple[Alpha, ...] = ()
        # No liquid phase exists, so the azeotrope search never runs. None
        # means "not checked" -- it must not be conflated with False, which
        # would claim the search ran and found nothing.
        has_azeo: bool | None = None
        # Same discipline as the azeotrope search: with no liquid phase there
        # is nothing to split, so the search never ran. None, not False.
        splits: bool | None = None
        phase = "vapor"
    else:
        alphas = relative_volatilities(feed, P)
        # The KEY PAIR when it is known, every pair when it is not.
        #
        # Same reasoning as bottoms_T_at_column_P below: before keys are named
        # the tool does not know which separation is being asked about, so it
        # screens broadly; once they are named, the claim R-12 makes is about
        # the model underneath THIS separation, and the model underneath this
        # separation is the one for the key pair. The source heuristics are
        # explicitly binary and say non-key handling is a multicomponent
        # problem that does not apply.
        #
        # This is not a cosmetic narrowing. On the milestone feed the non-key
        # pair water/glycerol trips UNIFAC's known false miscibility gap (see
        # lle.py), while the actual key pair methanol/water does not.
        pair = ([light_key, heavy_key] if light_key and heavy_key
                else list(feed.names))
        splits = find_liquid_split(pair, P) is not None
        # The SAME pair the liquid-liquid check uses, and for the same reason.
        # An azeotrope is a property of the separation being attempted, not of
        # the mixture standing in the column. A column splitting acetone from
        # ethanol, with water leaving in the bottoms beside the ethanol, is not
        # attempting the ethanol/water separation and is not blocked by its
        # azeotrope; whichever later column DOES take that pair as its keys
        # will be blocked, and correctly so.
        #
        # These two checks were inconsistent: this one scanned every pair while
        # find_liquid_split had already been narrowed to the keys. On a
        # multicomponent train the difference eliminated every sequence at its
        # first column and reported that no separation was possible, when only
        # one of the splits was actually blocked.
        has_azeo = bool(find_azeotropes(pair, P))
        phase = "vapor" if n_super > 0 else "liquid"

    # the most volatile component determines whether the condenser works
    if n_super == len(feed.components):
        cond_T = None
    else:
        lightest = min(feed.components, key=lambda c: boiling_point(c.cas))
        cond_T = condensing_temperature(lightest.name, P)

    # The hot end, and ONLY once a heavy key is named.
    #
    # Before a column is specified there is no bottoms, so asking whether steam
    # can drive the reboiler is a question about equipment that does not exist
    # yet. None here means "not a design yet", matching the key mole fractions
    # below, and it keeps R-10 and R-11 from firing on a bare feed screen.
    #
    # The heavy key, NOT the heaviest component. The heaviest component's pure
    # boiling point is a valid upper bound but a useless one: in the milestone
    # acceptance feed, glycerol boils at 562 K while the real bottoms is three
    # quarters water and boils near 375 K. Screening on the upper bound fired
    # the thermal rules on any feed containing a trace heavy.
    if heavy_key is None or n_super == len(feed.components):
        bottoms_T = None
    else:
        bottoms_T = condensing_temperature(heavy_key, P)

    fracs = feed.mole_fractions
    return PropertyRecord(
        n_components=len(feed.components),
        n_supercritical_at_feed=n_super,
        min_alpha=min((a.value for a in alphas), default=None),
        has_azeotrope=has_azeo,
        alphas=alphas,
        feed_phase=phase,
        condensing_T_at_column_P=cond_T,
        cooling_water_T=COOLING_WATER_T,
        light_key_mole_fraction=fracs.get(light_key) if light_key else None,
        heavy_key_mole_fraction=fracs.get(heavy_key) if heavy_key else None,
        bottoms_T_at_column_P=bottoms_T,
        has_two_liquid_phases=splits,
        column_P_Pa=P,
        column_P_basis=column_P_basis,
        steam_T=STEAM_T,
    )
