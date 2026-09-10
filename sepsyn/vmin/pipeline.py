"""Select on a bound, then verify as a design.

Stage 1 chooses the sequence by minimum vapour under sharp splits: cheap, exact
within its idealisation, and polynomial in the component count.

Stage 2 hands that ONE sequence to M3's evaluator, which propagates real
products, resolves each column's pressure, screens every column with the twelve
rules and lets an undetermined column block a cost.

Keeping these apart is the lesson of 09-10. A ranking computed from designs was
a ranking of columns that could not be built, because the selection step was
carrying assumptions it had no way to check. Minimum vapour cannot see
condenser feasibility either -- which is exactly why stage 2 still runs.
"""
from sepsyn.vmin.sequence import OptimalSequence, best_sequence


def volatilities_for(feed, P_Pa: float) -> tuple[dict[str, float], str]:
    """Relative volatilities against the HEAVIEST component, with their basis.

    Underwood is written against the heavy key, and referencing the heaviest
    component makes every alpha at least 1, which is what brackets the root.
    """
    from sepsyn.properties import boiling_point, relative_volatilities, resolve

    alphas = relative_volatilities(feed, P_Pa)
    heaviest = max(feed.components,
                   key=lambda c: boiling_point(c.cas or resolve(c.name))).name
    ratio = {a.pair: a.value for a in alphas}
    out: dict[str, float] = {heaviest: 1.0}
    for c in feed.components:
        if c.name == heaviest:
            continue
        if (c.name, heaviest) in ratio:
            out[c.name] = ratio[(c.name, heaviest)]
        elif (heaviest, c.name) in ratio and ratio[(heaviest, c.name)] > 0:
            out[c.name] = 1.0 / ratio[(heaviest, c.name)]
    missing = [c.name for c in feed.components if c.name not in out]
    if missing:
        # relative_volatilities drops a pair whose mole fraction reads exact
        # zero. Selection cannot proceed on a partial volatility set, and a
        # bare KeyError deep inside the dynamic program would not say why.
        raise ValueError(
            f"no relative volatility against {heaviest} for {missing}; "
            f"minimum vapour cannot be computed for this feed"
        )
    T = alphas[0].T_K if alphas else 0.0
    return out, (f"relative to {heaviest}, at the bubble point {T:.1f} K and "
                 f"{P_Pa / 1e5:.3f} bar")


def select_and_verify(sim, feed, order: tuple[str, ...],
                      P_Pa: float | None = None,
                      *, lk_recovery: float = 0.99,
                      hk_recovery: float = 0.99,
                      tags: dict | None = None):
    """Stage 1 then stage 2. Returns (OptimalSequence, SequenceOutcome)."""
    from sepsyn.cli import resolve_column_pressure
    from sepsyn.feed_condition import feed_condition
    from sepsyn.sequencing.evaluate import evaluate_sequence

    pressure = P_Pa
    if pressure is None:
        pressure, _ = resolve_column_pressure(feed, order[0], None)

    alpha, basis = volatilities_for(feed, pressure)

    # q enters Underwood's equation directly, so a subcooled feed and a
    # saturated one select on different numbers. Defaulting it to 1.0 when it
    # cannot be computed is stated in the basis rather than hidden.
    fc = feed_condition(feed, pressure)
    if fc is None:
        q, q_basis = 1.0, "q assumed 1.0: the feed condition could not be solved"
    else:
        q, q_basis = fc.q, f"q = {fc.q:.4f} ({fc.classification})"

    flows = {c.name: c.flow_kmol_hr for c in feed.components}
    selection = best_sequence(tuple(order), alpha, flows, q,
                              f"{basis}; {q_basis}")
    outcome = evaluate_sequence(sim, feed, selection.root,
                                lk_recovery=lk_recovery,
                                hk_recovery=hk_recovery, tags=tags)
    return selection, outcome
