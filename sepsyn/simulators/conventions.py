"""How BioSTEAM's stage numbers map onto DWSIM's. Pinned, measured 11-07.

Two conventions, which the 09-09 probe could not separate:

  1. Where does each tool count the feed stage from?
  2. Does a stage count include the condenser and the reboiler?

Settled first from the source, then by experiment.

From the source:
  BioSTEAM. 'Theoretical stages' come from the McCabe-Thiele staircase, which
  starts at the reboiler, or from Gilliland, which counts the same way: the
  reboiler IS a stage, a total condenser is NOT. 'Theoretical feed stage' is
  reported as N minus the stripping stages (Kirkbride, or the staircase
  position), so it counts from the TOP.
  DWSIM. The stage count includes both ends: index 0 is the condenser and the
  last index the reboiler, 0-based from the top (dwsim-mcp configure_column
  and connect_column_stream).

By experiment, on benzene/toluene 60/40 at 1 atm, 99 % recoveries, feed at
298.15 K. BioSTEAM designs N = 24 with the feed at 13. A 25-stage DWSIM column
was solved at every feed index from 9 to 18, and the reboiler duty is lowest
at index 13 (1397.1 kW; 1401.9 at 14, 1405.6 at 12) with a smooth minimum and
the mass balance closed on every run. With the stage count fixed, the correct
feed location is the one that minimises duty, so that criterion is physical,
not a fit to BioSTEAM's duty. The mapping is the identity: BioSTEAM's stage k
from the top is DWSIM's index k, because DWSIM's index 0 is the condenser
that BioSTEAM does not count.

The 09-09 hypothesis, that BioSTEAM counts from the bottom (20 - 14 = 6), is
refuted on the binary. That probe also handed DWSIM 20 stages for BioSTEAM's
20, one short. See docs/findings/2026-11-07-stage-conventions.md.
"""

FEED_STAGE_ORIGIN = "top"
"""BioSTEAM's theoretical feed stage counts from the top of the column."""

STAGE_COUNT_INCLUDES_ENDS = False
"""For BioSTEAM: its count includes the reboiler but not a total condenser.
DWSIM's includes both, which is why dwsim_stage_count adds one."""


def dwsim_stage_count(biosteam_theoretical_stages: int,
                      condenser_type: str = "total") -> int:
    """DWSIM's stage count for a column BioSTEAM designed.

    Only a TOTAL condenser is pinned. A partial condenser is an equilibrium
    stage, so BioSTEAM may already count it, and that case was not measured.
    """
    if condenser_type != "total":
        raise ValueError(
            f"stage mapping is measured for a total condenser only, not "
            f"{condenser_type!r}. A partial condenser is an equilibrium stage "
            f"and may already be in BioSTEAM's count; measure it before "
            f"mapping it.")
    if biosteam_theoretical_stages < 3:
        raise ValueError("DWSIM requires more than 3 stages")
    return biosteam_theoretical_stages + 1


def dwsim_feed_stage(biosteam_feed_stage: int,
                     biosteam_theoretical_stages: int) -> int:
    """DWSIM's 0-based feed index for BioSTEAM's feed stage counted from the top.

    The identity, for the reason in the module docstring. Bounded so the feed
    can never land on the condenser (0) or the reboiler (the last index).
    """
    last = dwsim_stage_count(biosteam_theoretical_stages) - 1
    if not 1 <= biosteam_feed_stage < last:
        raise ValueError(
            f"feed stage {biosteam_feed_stage} is outside the trays of a "
            f"{biosteam_theoretical_stages}-stage column")
    return biosteam_feed_stage
