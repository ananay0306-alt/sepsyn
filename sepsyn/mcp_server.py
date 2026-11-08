"""sepsyn as an MCP server. M5.

A wrapper, not a rewrite: every tool builds the same argument list a person
would type and runs the CLI, so the server can never drift from the tool it
wraps and every number carries the same provenance the printed report does.
The core has no LLM in it, deliberately, and this module does not change that.

Run it with `python -m sepsyn.mcp_server` (stdio). stdout belongs to the
protocol, so the CLI's report is captured rather than printed, and BioSTEAM's
own chatter goes with it.

One tool runs at a time. The server calls sync tools from worker threads, but
sys.stdout and BioSTEAM's thermo settings belong to the whole process: two
columns solved at once could each run on the other's chemicals and return
wrong numbers without an error.
"""
import contextlib
import io
import threading

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from sepsyn.cli import main

INSTRUCTIONS = (
    "sepsyn screens mixtures for distillation and designs columns, recording "
    "every assumption it makes. Flows are kmol/hr, temperatures K, pressures "
    "Pa. Never compute a stage count, reflux, relative volatility, column "
    "pressure or feed q yourself; report the tool's numbers, the rule ids that "
    "fired, and the basis each number was evaluated at. UNDETERMINED is not "
    "INFEASIBLE, and minimum vapour is a lower bound, not a duty."
)

server = MCPServer("sepsyn", instructions=INSTRUCTIONS)
_one_at_a_time = threading.Lock()


def _feed_arg(feed: dict[str, float]) -> str:
    if not feed:
        raise ToolError("feed is empty; give component names and kmol/hr")
    for name, flow in feed.items():
        if "," in name or ":" in name:
            raise ToolError(f"component name {name!r} contains ',' or ':'")
        if flow < 0:
            raise ToolError(f"negative flow for {name}: {flow}")
    return ",".join(f"{n}:{f}" for n, f in feed.items())


def _run(argv: list[str]) -> str:
    out, err = io.StringIO(), io.StringIO()
    with _one_at_a_time, contextlib.redirect_stdout(out), \
            contextlib.redirect_stderr(err):
        try:
            code = main(argv)
        except SystemExit as exc:  # argparse rejecting the arguments
            code = exc.code
    if code == 2:
        # The CLI's usage errors: the request itself was wrong. Its message,
        # including resolve()'s "did you mean", goes to stderr, and the model
        # needs it to correct the request.
        raise ToolError(err.getvalue().strip() or out.getvalue().strip()
                        or "invalid arguments")
    return out.getvalue().strip()


def _common(feed, T_K, P_Pa, column_P_Pa) -> list[str]:
    argv = ["--feed", _feed_arg(feed), "--T", str(T_K), "--P", str(P_Pa)]
    if column_P_Pa is not None:
        argv += ["--column-P", str(column_P_Pa)]
    return argv


@server.tool()
def screen_mixture(feed: dict[str, float], T_K: float = 298.15,
                   P_Pa: float = 101325.0, light_key: str | None = None,
                   heavy_key: str | None = None,
                   column_P_Pa: float | None = None,
                   explain: bool = False) -> str:
    """Screen a mixture for separation by distillation.

    Returns the column pressure and where it came from, relative
    volatilities with the conditions they were evaluated at, the rules that
    fired and the verdict (FEASIBLE, CAUTION, UNDETERMINED, INFEASIBLE).
    Name the keys whenever the user has: without them four rules cannot fire.
    explain=True also lists rules that did not fire, with the values tested.
    """
    argv = _common(feed, T_K, P_Pa, column_P_Pa)
    if light_key:
        argv += ["--light-key", light_key]
    if heavy_key:
        argv += ["--heavy-key", heavy_key]
    if explain:
        argv.append("--explain")
    return _run(argv)


@server.tool()
def design_column(feed: dict[str, float], light_key: str, heavy_key: str,
                  T_K: float = 298.15, P_Pa: float = 101325.0,
                  lk_recovery: float = 0.99, hk_recovery: float = 0.99,
                  distillate_purity: float | None = None,
                  bottoms_impurity: float | None = None,
                  feed_q: float | None = None,
                  column_P_Pa: float | None = None) -> str:
    """Screen, then design the column if screening allows it.

    Specify by recoveries (default 99 % each) or by distillate_purity with
    bottoms_impurity; they are different specifications and are converted
    explicitly. feed_q imposes the feed condition; leaving it out takes the
    feed as it arrives, which is NOT the same as q = 1.
    """
    argv = _common(feed, T_K, P_Pa, column_P_Pa) + [
        "--design", "--light-key", light_key, "--heavy-key", heavy_key]
    if distillate_purity is not None or bottoms_impurity is not None:
        if distillate_purity is None or bottoms_impurity is None:
            raise ToolError("distillate_purity and bottoms_impurity go together")
        argv += ["--distillate-purity", str(distillate_purity),
                 "--bottoms-impurity", str(bottoms_impurity)]
    else:
        argv += ["--lk-recovery", str(lk_recovery),
                 "--hk-recovery", str(hk_recovery)]
    if feed_q is not None:
        argv += ["--feed-q", str(feed_q)]
    return _run(argv)


@server.tool()
def sequence_by_minimum_vapour(feed: dict[str, float], order: list[str],
                               T_K: float = 298.15, P_Pa: float = 101325.0,
                               column_P_Pa: float | None = None) -> str:
    """Choose the separation sequence for a multicomponent feed by minimum
    vapour (Underwood), found exactly by dynamic programming, then verify the
    chosen sequence as a real design.

    order lists every component lightest to heaviest. An azeotropic pair
    anywhere in the feed blocks every sequence and is refused before any
    number is computed. The result is a lower bound on vapour, not a duty.
    """
    argv = _common(feed, T_K, P_Pa, column_P_Pa) + [
        "--vmin", "--order", ",".join(order)]
    return _run(argv)


@server.tool()
def rank_sequences(feed: dict[str, float], order: list[str],
                   T_K: float = 298.15, P_Pa: float = 101325.0) -> str:
    """Enumerate every sharp-split sequence, design and cost each column, and
    rank them, alongside the four textbook sequencing heuristics. Slower than
    sequence_by_minimum_vapour: it designs every column of every sequence."""
    argv = _common(feed, T_K, P_Pa, None) + [
        "--sequence", "--order", ",".join(order)]
    return _run(argv)


@server.tool()
def find_azeotropes(components: list[str], P_Pa: float = 101325.0) -> str:
    """Scan every pair for an azeotrope at this pressure, by searching for
    relative volatility crossing one at the bubble point."""
    from sepsyn.azeotropes import find_azeotropes as search

    if len(components) < 2:
        raise ToolError("an azeotrope needs at least two components")
    with _one_at_a_time, contextlib.redirect_stdout(io.StringIO()):
        found = search(components, P_Pa)
    if not found:
        return (f"No azeotrope found among {', '.join(components)} at "
                f"{P_Pa / 1e5:.3f} bar (201-point scan per pair).")
    return "\n".join(
        f"{a.components[0]}/{a.components[1]}: x = {a.x[0]:.3f} "
        f"{a.components[0]}, {a.T_K:.1f} K, {a.P_Pa / 1e5:.3f} bar"
        for a in found)


if __name__ == "__main__":
    server.run("stdio")
