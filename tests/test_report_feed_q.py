"""Step 17: q must be visible in the printed design, not just on the object.

The heuristic list calls q "the most commonly unstated assumption in a column
specification". A report that omits it reproduces exactly that failure.
"""
from sepsyn.report import format_design
from sepsyn.simulators.base import ColumnResult, ColumnSpec

P_ATM = 101325.0


def _rendered(spec_q, result_q):
    spec = ColumnSpec("Benzene", "Toluene", 0.99, 0.99, P_ATM, feed_q=spec_q)
    result = ColumnResult(
        distillate={"Benzene": 59.4, "Toluene": 0.4},
        bottoms={"Benzene": 0.6, "Toluene": 39.6},
        stages=20.0, reflux=1.5, minimum_reflux=1.25,
        installed_cost_USD=1.0e6, utility_cost_USD_hr=10.0,
        converged=True, feed_q=result_q,
    )
    return format_design(spec, [], None, result, [], [])


def test_the_report_states_q_and_names_the_thermal_condition():
    out = _rendered(None, 1.301)
    assert "1.301" in out
    assert "subcooled liquid" in out


def test_a_feed_taken_as_it_arrives_says_so():
    """An imposed q and an inherited one are different design decisions and
    must not print identically."""
    assert "as it arrives" in _rendered(None, 1.0)


def test_an_imposed_q_is_marked_as_imposed():
    out = _rendered(1.0, 1.0)
    assert "as it arrives" not in out
    assert "imposed" in out


def test_an_unmeasurable_q_is_reported_as_unmeasurable_not_as_zero():
    out = _rendered(None, None)
    assert "saturated vapour" not in out
    assert "could not be measured" in out
