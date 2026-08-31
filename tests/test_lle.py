"""Two liquid phases. Heuristic step 6.

"If the mixture splits, an ordinary vapour liquid calculation is the wrong
model and will miss it silently." Silently is the operative word: every other
screening rule here fires on a number that is visibly wrong, while a missed
liquid-liquid split produces a column design that looks entirely reasonable and
describes a separation that will not happen.
"""
from sepsyn.lle import find_liquid_split

ATM = 101325.0


def test_benzene_toluene_does_not_split():
    """The acceptance binary. If this reported a split, every design in the
    suite would be under suspicion."""
    assert find_liquid_split(["Benzene", "Toluene"], ATM) is None


def test_water_and_n_butanol_split():
    """A textbook partially-miscible pair: a water-rich phase and a
    butanol-rich phase, used industrially with a decanter."""
    split = find_liquid_split(["Water", "Butanol"], ATM)
    assert split is not None
    assert split.components == ("Water", "Butanol")


def test_the_reported_phases_have_GENUINELY_DIFFERENT_compositions():
    """The criterion, asserted directly.

    Both phases holding material is NOT enough: thermosteam's LLE solver will
    happily hand back two phases of identical composition for a fully miscible
    mixture, which is one liquid divided in two rather than a miscibility gap.
    """
    split = find_liquid_split(["Water", "Butanol"], ATM)
    assert split is not None
    assert abs(split.x_phase_1 - split.x_phase_2) > 0.1


def test_ethanol_water_does_NOT_split():
    """The regression case that set the criterion.

    Ethanol and water are miscible in all proportions. Detecting on phase
    AMOUNTS alone reported a split here at two compositions, because the solver
    divided the liquid into two phases of identical composition (dx = 0.0000).
    Detecting on composition DIFFERENCE rejects both, while water/n-butanol
    separates by dx = 0.51.
    """
    assert find_liquid_split(["Ethanol", "Water"], ATM) is None


def test_water_and_benzene_split():
    """Very nearly total immiscibility -- the easy end of the case."""
    assert find_liquid_split(["Water", "Benzene"], ATM) is not None


def test_the_split_carries_the_conditions_it_was_found_at():
    """Same discipline as Alpha: a split is a property of a pair AT a condition,
    and a bare boolean cannot be checked by anyone."""
    split = find_liquid_split(["Water", "Butanol"], ATM)
    assert split is not None
    assert split.P_Pa == ATM
    assert 273.0 < split.T_K < 500.0
    assert 0.0 < split.overall_x < 1.0


def test_a_mixture_with_no_liquid_phase_returns_None():
    assert find_liquid_split(["Hydrogen", "Methane"], ATM) is None
