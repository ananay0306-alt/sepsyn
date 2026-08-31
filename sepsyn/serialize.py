"""A run, as structured data.

The project's argument is that two designs at different q are not comparable
unless the assumptions are recorded. Until this module existed the tool
recorded nothing: every number went to stdout and died with the terminal
scrollback, so runs could be read but never compared.

What is saved is therefore chosen for COMPARABILITY, not for completeness. The
three things a saved run must never collapse are the three that make two runs
different:

  the pressure AND its basis   specified and derived are different claims
  q AND whether it was imposed  a q the feed had, and a q it was given
  an equipment choice AND its status  convention and evidence

Each of those is a pair. Saving only the left half of any of them reproduces
the unrecorded-assumption failure in a new file format.
"""
import datetime
import json
from dataclasses import asdict


def _alpha(a) -> dict:
    return {
        "pair": list(a.pair),
        "value": a.value,
        "T_K": a.T_K,
        "P_Pa": a.P_Pa,
        "basis": a.basis,
    }


def _verdict(v) -> dict:
    """Every rule, fired or not.

    The report prints the silent ones only under --explain, because there they
    compete for a reader's attention. A file has no such constraint, and what
    was considered and rejected is part of the reasoning: a run recording only
    the rules that fired cannot answer "was this even checked".
    """
    return {
        "id": v.rule_id,
        "name": v.rule_name,
        "fired": v.fired,
        "verdict": v.verdict,
        "condition": v.condition,
        "values": {k: _plain(x) for k, x in v.values.items()},
        "technologies": list(v.technologies),
        "because": v.because,
        "requires": list(v.requires),
        "limitations": v.limitations,
    }


def _plain(x):
    """Numpy scalars and the like reach here through rule values."""
    if isinstance(x, (bool, str)) or x is None:
        return x
    try:
        return float(x)
    except (TypeError, ValueError):
        return str(x)


def _equipment(d) -> dict:
    return {
        "step": d.step,
        "decision": d.decision,
        "question": d.question,
        "options": list(d.options),
        "choice": d.choice,
        "status": d.status,
        "rule_id": d.rule_id or None,
        "because": d.because,
        "requires": list(d.requires),
        "limitations": d.limitations,
        "must_record": d.must_record,
    }


def _design(spec, points, best, result, checks, unseparated, equipment) -> dict:
    from sepsyn.feed_condition import describe

    q = result.feed_q
    return {
        "keys": {"light": spec.light_key, "heavy": spec.heavy_key},
        "recoveries": {
            "lk_to_distillate": spec.lk_recovery_to_distillate,
            "hk_to_bottoms": spec.hk_recovery_to_bottoms,
        },
        "condenser_type": spec.condenser_type,
        "feed_q": {
            "value": q,
            # The pair. A q of 1.0 the feed happened to have and a q of 1.0
            # imposed by a preheater are different designs with the same
            # number, and only this flag separates them.
            "imposed": spec.feed_q is not None,
            "classification": describe(q) if q is not None else None,
        },
        "reflux_sweep": [
            {
                "k": p.k,
                "stages": p.stages,
                "annualised_cost_USD_yr": (
                    p.annualised_cost_USD_yr if p.converged else None),
                "installed_cost_USD": p.installed_cost_USD,
                "utility_cost_USD_hr": p.utility_cost_USD_hr,
                "converged": p.converged,
                "error": p.error,
            }
            for p in points
        ],
        "chosen": None if best is None else {
            "k": best.k,
            "stages": best.stages,
            "annualised_cost_USD_yr": best.annualised_cost_USD_yr,
            "installed_cost_USD": best.installed_cost_USD,
            "utility_cost_USD_hr": best.utility_cost_USD_hr,
        },
        "converged": result.converged,
        "error": result.error,
        "products": {
            "distillate_kmol_hr": dict(result.distillate),
            "bottoms_kmol_hr": dict(result.bottoms),
        },
        "column": {
            "stages": result.stages,
            "reflux": result.reflux,
            "minimum_reflux": result.minimum_reflux,
            # Both diameters. BioSTEAM sizes and prices the shell from the
            # floored one, so the cost belongs to it, while the equipment rules
            # key on the true one. Substituting either for the other silently
            # is exactly what this file format exists to prevent.
            "diameter_m": result.column_diameter_m,
            "simulator_reported_diameter_m": result.biosteam_reported_diameter_m,
        },
        "duties_kW": {
            "condenser": result.condenser_duty_kW,
            "reboiler": result.reboiler_duty_kW,
        },
        "temperatures_K": {
            "distillate": result.distillate_T_K,
            "bottoms": result.bottoms_T_K,
        },
        "costs": {
            "installed_USD": result.installed_cost_USD,
            "utility_USD_hr": result.utility_cost_USD_hr,
        },
        "equipment": [_equipment(d) for d in (equipment or ())],
        "verification": [asdict(c) for c in checks],
        "unseparated_components": list(unseparated),
    }


def run_to_dict(feed, record, verdicts, overall, designed=None) -> dict:
    """One run, whole. `designed` is the tuple design_if_feasible returns."""
    return {
        "sepsyn_run": 1,
        "generated": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "feed": {
            "components": [
                {"name": c.name, "cas": c.cas, "flow_kmol_hr": c.flow_kmol_hr}
                for c in feed.components
            ],
            "T_K": feed.T_K,
            "P_Pa": feed.P_Pa,
        },
        # The pressure and where it came from, at the top level rather than
        # inside screening, because every property below was evaluated at it
        # and none of them means anything without it.
        "column_pressure": {
            "Pa": record.column_P_Pa,
            "basis": record.column_P_basis,
        },
        "screening": {
            "verdict": overall,
            "min_alpha": record.min_alpha,
            "alphas": [_alpha(a) for a in record.alphas],
            "feed_phase": record.feed_phase,
            "n_supercritical_at_feed": record.n_supercritical_at_feed,
            "has_azeotrope": record.has_azeotrope,
            "has_two_liquid_phases": record.has_two_liquid_phases,
            "rules": [_verdict(v) for v in verdicts],
        },
        # None, not {}. The run did not design a column, which is a different
        # fact from designing one that came back empty.
        "design": None if designed is None else _design(*designed),
    }


def write_json(path: str, payload: dict) -> None:
    with open(path, "w") as fh:
        json.dump(payload, fh, indent=2, sort_keys=False)
        fh.write("\n")
