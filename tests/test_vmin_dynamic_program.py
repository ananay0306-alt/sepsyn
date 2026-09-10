"""Dynamic programming over contiguous groups.

Enumeration was the wrong architecture for the question actually asked: at ten
components it needs 43,758 column designs and returns a ranked list. The
optimum for a group depends only on its contents, so sub-results are shared and
165 split evaluations return the provable optimum.
"""
import pytest

from sepsyn.sequencing.enumeration import enumerate_sequences, label
from sepsyn.vmin.sequence import NoFeasibleSequence, best_sequence
from sepsyn.vmin.underwood import NoUnderwoodRoot
from sepsyn.vmin.vapour import minimum_vapour

ORDER5 = ("A", "B", "C", "D", "E")
ALPHA5 = {"A": 16.0, "B": 8.0, "C": 4.0, "D": 2.0, "E": 1.0}
FLOWS5 = {"A": 20.0, "B": 20.0, "C": 20.0, "D": 20.0, "E": 20.0}


def brute_force(order, alpha, flows, q):
    """Total V_min of every sequence, by enumeration.

    Used ONLY to prove the dynamic program returns the same optimum, on sizes
    small enough to enumerate. This is the reference, so it is written the
    slow obvious way on purpose.
    """
    best = None
    for root in enumerate_sequences(order):
        total = 0.0
        for node in root.splits():
            sub = {c: flows[c] for c in node.group}
            try:
                total += minimum_vapour(
                    node.group, alpha, sub, q, node.k).V_min_kmol_hr
            except NoUnderwoodRoot:
                total = None
                break
        if total is not None and (best is None or total < best[0]):
            best = (total, label(root))
    return best


def test_the_dp_matches_BRUTE_FORCE_on_a_five_component_feed():
    """THE correctness test. Fourteen sequences is small enough to enumerate,
    so the dynamic program can be proved right rather than argued right."""
    dp = best_sequence(ORDER5, ALPHA5, FLOWS5, q=1.0)
    force = brute_force(ORDER5, ALPHA5, FLOWS5, q=1.0)
    assert force is not None
    assert dp.total_V_min_kmol_hr == pytest.approx(force[0], rel=1e-9)
    assert label(dp.root) == force[1]


@pytest.mark.parametrize("n", [3, 4, 5, 6])
def test_the_dp_matches_brute_force_at_several_sizes(n):
    """Unequal flows and unequal volatility ratios, so a tie cannot hide a
    disagreement between the two methods."""
    order = tuple("ABCDEF")[:n]
    alpha = {c: 1.7 ** (len(order) - i - 1) for i, c in enumerate(order)}
    flows = {c: 10.0 * (i + 1) for i, c in enumerate(order)}
    dp = best_sequence(order, alpha, flows, q=1.0)
    force = brute_force(order, alpha, flows, q=1.0)
    assert force is not None
    assert dp.total_V_min_kmol_hr == pytest.approx(force[0], rel=1e-9)
    assert label(dp.root) == force[1]


def test_the_result_is_a_complete_sequence():
    dp = best_sequence(ORDER5, ALPHA5, FLOWS5, q=1.0)
    assert len(dp.root.splits()) == len(ORDER5) - 1
    assert len(dp.splits) == len(ORDER5) - 1


def test_the_total_is_the_sum_of_its_splits():
    """A total that is not the sum of its parts cannot be audited."""
    dp = best_sequence(ORDER5, ALPHA5, FLOWS5, q=1.0)
    assert dp.total_V_min_kmol_hr == pytest.approx(
        sum(s.V_min_kmol_hr for s in dp.splits))


def test_it_evaluates_FAR_fewer_splits_than_enumeration_would():
    """The reason for the redesign. Five components: enumeration needs 14
    sequences times 4 columns = 56 designs; the dynamic program needs the
    (group, split) pairs, which is 20."""
    dp = best_sequence(ORDER5, ALPHA5, FLOWS5, q=1.0)
    assert dp.evaluated == 20
    assert dp.evaluated < 14 * 4


def test_ten_components_is_tractable():
    """The size the review actually asked about. Enumeration would need 4,862
    sequences and 43,758 column designs."""
    order = tuple("ABCDEFGHIJ")
    alpha = {c: 1.5 ** (len(order) - i - 1) for i, c in enumerate(order)}
    flows = {c: 10.0 for c in order}
    dp = best_sequence(order, alpha, flows, q=1.0)
    assert len(dp.root.splits()) == 9
    assert dp.evaluated == 165
    assert dp.total_V_min_kmol_hr > 0


def test_an_unseparable_pair_makes_the_whole_problem_infeasible():
    """Components are ordered by volatility, so two with the same alpha are
    necessarily ADJACENT, and every complete sequence has to split them
    somewhere. There is no route around it, and saying so beats returning the
    least bad sequence."""
    alpha = {"A": 4.0, "B": 1.0, "C": 1.0}
    with pytest.raises(NoFeasibleSequence) as exc:
        best_sequence(("A", "B", "C"), alpha,
                      {"A": 30.0, "B": 30.0, "C": 40.0}, q=1.0)
    assert "B" in str(exc.value) and "C" in str(exc.value)


def test_the_refusal_names_the_PAIR_that_cannot_be_split():
    """A bare 'infeasible' sends the reader back to the thermodynamics with no
    idea where to look. The message has to point at the offending split."""
    alpha = {"A": 4.0, "B": 2.0, "C": 1.0, "D": 1.0}
    with pytest.raises(NoFeasibleSequence) as exc:
        best_sequence(("A", "B", "C", "D"), alpha,
                      {c: 25.0 for c in "ABCD"}, q=1.0)
    assert "C" in str(exc.value) and "D" in str(exc.value)


def test_only_the_FIRST_column_sees_the_fresh_feed_thermal_condition():
    """Downstream columns are fed a product of the column above them: a bottoms
    liquid, or a condensed overhead, each leaving at its own bubble point. They
    are saturated, not subcooled, whatever the fresh feed was.

    Applying the fresh feed's q to the whole tree would be assuming every
    column in the train is fed at the cold-storage temperature, which is not
    how a train is plumbed. It is not a small effect: measured on the alkane
    feed, q = 1.40 against q = 1.0 changes which sequence wins.
    """
    subcooled = best_sequence(ORDER5, ALPHA5, FLOWS5, q=1.6)
    saturated = best_sequence(ORDER5, ALPHA5, FLOWS5, q=1.0)

    # The root split alone is charged the subcooled feed, so the two runs
    # differ there and nowhere else.
    assert subcooled.splits[0].theta != saturated.splits[0].theta
    downstream_subcooled = sorted(s.theta for s in subcooled.splits[1:])
    downstream_saturated = sorted(s.theta for s in saturated.splits[1:])
    assert subcooled.root.k == saturated.root.k, "same tree expected here"
    assert downstream_subcooled == pytest.approx(downstream_saturated)


def test_the_downstream_condition_can_be_overridden():
    """A train with reboiled side-draws or an intercooler does not feed every
    downstream column at saturation. The assumption is a default, not a law, so
    it is a parameter."""
    a = best_sequence(ORDER5, ALPHA5, FLOWS5, q=1.0, downstream_q=1.0)
    b = best_sequence(ORDER5, ALPHA5, FLOWS5, q=1.0, downstream_q=0.5)
    assert a.total_V_min_kmol_hr != b.total_V_min_kmol_hr
