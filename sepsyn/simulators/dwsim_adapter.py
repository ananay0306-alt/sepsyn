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
import asyncio
import json
import os

from sepsyn.simulators.dwsim_fixtures import DwsimRun, load_fixture

DWSIM_MCP = ("/Users/ananaykhandelwal/projects/process_simulation/"
             "dwsim-mcp/dwsim-mcp.sh")

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


class DwsimResultError(ValueError):
    """A results payload that cannot be turned into a run."""


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


def parse_results(results: dict):
    """DWSIM results into per-compound flows, duties and temperatures.

    DWSIM reports a total molar flow and mole fractions; the fixture needs
    flows per compound so a mass balance can be checked component by component
    rather than only in total.
    """
    streams = {s["tag"]: s for s in results.get("material_streams", ())}
    for tag in ("D", "B"):
        if tag not in streams:
            raise DwsimResultError(
                f"results contain no {tag!r} stream. A solve that did not "
                f"produce both products is not a run; parsing it would invent "
                f"plausible-looking zeros."
            )

    def flows(tag):
        s = streams[tag]
        total = float(s.get("molar_flow_mol_s", 0.0))
        return {n: total * float(x)
                for n, x in (s.get("mole_fractions") or {}).items()}

    energy = {e["tag"]: float(e.get("energy_flow_kW", 0.0))
              for e in results.get("energy_streams", ())}
    return (flows("D"), flows("B"),
            energy.get("QC"), energy.get("QR"),
            float(streams["D"].get("T_K", 0.0)) or None,
            float(streams["B"].get("T_K", 0.0)) or None)


async def _build_and_solve(session, feed, spec, stages, feed_stage, timeout_s):
    """One column, on a FRESH flowsheet. See the module docstring."""
    async def call(name, args=None):
        res = await session.call_tool(name, args or {})
        return res.content[0].text if res.content else ""

    mol_s = feed_to_mol_s(feed)
    await call("create_flowsheet")
    for name in mol_s:
        await call("add_compound", {"name": name})
    await call("set_property_package", {"name": PROPERTY_PACKAGE})
    for tag, kind in (("F", "MaterialStream"), ("D", "MaterialStream"),
                      ("B", "MaterialStream"), ("QC", "EnergyStream"),
                      ("QR", "EnergyStream"), ("T1", "DistillationColumn")):
        await call("add_object", {"type": kind, "tag": tag})
    await call("set_stream", {"tag": "F", "temperature": feed.T_K,
                              "pressure": spec.pressure_Pa,
                              "compound_molar_flows": mol_s})
    condenser = {"type": "Component Recovery",
                 "compound": dwsim_name(spec.light_key),
                 "value": spec.lk_recovery_to_distillate * 100.0, "unit": "%"}
    reboiler = {"type": "Component Recovery",
                "compound": dwsim_name(spec.heavy_key),
                "value": spec.hk_recovery_to_bottoms * 100.0, "unit": "%"}
    await call("configure_column", {
        "tag": "T1", "stages": stages, "top_pressure": spec.pressure_Pa,
        "pressure_drop": 0, "condenser_spec": condenser,
        "reboiler_spec": reboiler, "solver_method": SOLVER,
        "max_iterations": 200})
    await call("connect_column_stream", {"column_tag": "T1", "stream_tag": "F",
                                         "role": "feed", "stage": feed_stage})
    for tag, role in (("D", "distillate"), ("B", "bottoms"),
                      ("QC", "condenser_duty"), ("QR", "reboiler_duty")):
        await call("connect_column_stream", {"column_tag": "T1",
                                             "stream_tag": tag, "role": role})

    solved = json.loads(await call("solve", {"timeout_seconds": timeout_s}))
    common = dict(
        feed_mol_s=mol_s, T_K=feed.T_K, P_Pa=spec.pressure_Pa, stages=stages,
        feed_stage=feed_stage, condenser_spec=condenser,
        reboiler_spec=reboiler, property_package=PROPERTY_PACKAGE,
        solver=SOLVER)

    if not solved.get("converged"):
        # A solve that does not finish is a FACT about the case, not an
        # exception. The 09-09 stage-6 timeout is exactly the kind of finding
        # that must survive into the record rather than becoming a traceback.
        return DwsimRun(converged=False,
                        errors=tuple(solved.get("errors", ()) or ("unknown",)),
                        distillate_mol_s={}, bottoms_mol_s={}, **common)

    results = json.loads(await call("get_results"))
    d, b, qc, qr, td, tb = parse_results(results)
    return DwsimRun(converged=True, errors=(), distillate_mol_s=d,
                    bottoms_mol_s=b, condenser_duty_kW=qc,
                    reboiler_duty_kW=qr, distillate_T_K=td, bottoms_T_K=tb,
                    **common)


class LiveTransport:
    """Speak to a real DWSIM through dwsim-mcp over stdio.

    Slow by nature: the engine takes about two seconds to initialise and a
    rigorous solve takes seconds to minutes. Never used by the default suite.
    """

    def __init__(self, timeout_s: int = 300, command: str = DWSIM_MCP):
        self.timeout_s = timeout_s
        self.command = command

    def _params(self):
        from mcp import StdioServerParameters
        return StdioServerParameters(command=self.command, args=[], env=None)

    def run(self, feed, spec, stages: int, feed_stage: int) -> DwsimRun:
        return self.sweep_feed_stage(feed, spec, stages, [feed_stage])[feed_stage]

    def sweep_feed_stage(self, feed, spec, stages: int,
                         feed_stages) -> dict[int, DwsimRun]:
        """Solve the same column at several feed stages, in one session.

        One session, many flowsheets. The fresh-flowsheet invariant is about
        the FLOWSHEET, not the process: create_flowsheet resets everything, and
        the doubled-feed failure came from mutating a flowsheet rather than
        from reusing a connection.
        """
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client

        async def go():
            out: dict[int, DwsimRun] = {}
            async with stdio_client(self._params()) as (r, w):
                async with ClientSession(r, w) as session:
                    await session.initialize()
                    for stage in feed_stages:
                        out[stage] = await _build_and_solve(
                            session, feed, spec, stages, stage, self.timeout_s)
            return out

        return asyncio.run(go())
