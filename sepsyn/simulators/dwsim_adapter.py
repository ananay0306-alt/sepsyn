"""Talk to DWSIM's rigorous column.

ONE invariant governs this module: every call builds a FRESH flowsheet. There
is no code path that reconfigures, reconnects or disconnects an existing one.

That is not tidiness. In the 09-09 probe, `disconnect_objects` reported success
and left the feed attached; the next solve ran with two feed streams and
produced 55.55 mol/s of product from a 27.78 mol/s feed, with entirely
plausible compositions and temperatures. Nothing in the result flagged it, and
only a mass balance caught it.

The MCP call sequence a live transport must perform, in this order, with
nothing reused between runs:

    create_flowsheet
    add_compound          once per component, DWSIM database names
    set_property_package  "Peng-Robinson (PR)"
    add_object            MaterialStream F, D, B; EnergyStream QC, QR;
                          DistillationColumn T1
    set_stream            F: T, P, compound_molar_flows
    configure_column      T1: stages, top_pressure, dP, both recovery specs,
                          Napthali-Sandholm, max_iterations
    connect_column_stream F feed at the mapped stage, D distillate, B bottoms,
                          QC condenser_duty, QR reboiler_duty
    solve                 with a timeout
    get_results
"""
import os

from sepsyn.simulators.dwsim_fixtures import DwsimRun, load_fixture

PROPERTY_PACKAGE = "Peng-Robinson (PR)"
SOLVER = "Napthali-Sandholm (Simultaneous Correction)"

# sepsyn uses the common name; the DWSIM database is specific about isomers.
# An unmapped name would silently produce a column missing a component, which
# is a wrong answer rather than an error.
DWSIM_NAMES = {
    "Butane": "N-butane",
    "Pentane": "N-pentane",
    "Hexane": "N-hexane",
    "Heptane": "N-heptane",
    "Octane": "N-octane",
}
PASS_THROUGH = {"Propane", "Benzene", "Toluene", "Ethanol", "Water",
                "Methanol", "Acetone", "Glycerol"}


class UnknownDwsimCompound(ValueError):
    """A name with no established DWSIM database equivalent."""


class DwsimTimeout(RuntimeError):
    """The solver exceeded its budget. An outcome, not an error."""


def dwsim_name(name: str) -> str:
    if name in DWSIM_NAMES:
        return DWSIM_NAMES[name]
    if name in PASS_THROUGH:
        return name
    raise UnknownDwsimCompound(
        f"no DWSIM database name established for {name!r}. Add it to "
        f"DWSIM_NAMES after confirming the exact database spelling; passing "
        f"an unmapped name through silently omits the component."
    )


def feed_to_mol_s(feed) -> dict[str, float]:
    """kmol/hr to mol/s, under the DWSIM names. Divide by 3.6."""
    return {dwsim_name(c.name): c.flow_kmol_hr / 3.6 for c in feed.components}


def fixture_key(feed, spec, stages: int, feed_stage: int) -> str:
    names = "_".join(c.name.lower() for c in feed.components)
    return f"{names}_{stages}_{feed_stage}.json"


class FixtureTransport:
    """Replay a recorded run. Keeps the default suite hermetic and fast."""

    def __init__(self, directory: str):
        self.directory = directory

    def run(self, feed, spec, stages: int, feed_stage: int) -> DwsimRun:
        path = os.path.join(self.directory,
                            fixture_key(feed, spec, stages, feed_stage))
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"no recorded DWSIM run at {path}. Record one with the live "
                f"transport rather than falling back to a default, which would "
                f"compare against a number nobody measured."
            )
        return load_fixture(path)


class DwsimSimulator:
    """The rigorous reference. Not a peer to sepsyn's shortcut methods."""

    def __init__(self, transport):
        self.transport = transport

    def design_from_stages(self, feed, spec, theoretical_stages: int,
                           feed_stage: int) -> DwsimRun:
        """Solve a column with the stage count and feed stage GIVEN.

        Rigorous columns run in the simulation direction: stages in, duties
        out. sepsyn's shortcut runs the other way, purity in and stages out.
        That asymmetry is the milestone's point, and it is why this method
        takes a stage count rather than computing one.

        The stage count must be THEORETICAL. BioSTEAM also reports an actual
        count, larger by the tray efficiency, and handing that to a rigorous
        column produced DCErrorStillHigh in the 09-09 probe.
        """
        return self.transport.run(feed, spec, theoretical_stages, feed_stage)
