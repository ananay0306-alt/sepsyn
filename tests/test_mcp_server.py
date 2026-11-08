"""sepsyn's MCP server. The tools wrap the CLI, so these check the wrapping:
arguments reach the CLI, the report comes back, usage errors become tool
errors, and stdout stays clean for the protocol."""
import asyncio
import os
import sys

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from sepsyn import mcp_server as srv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_screening_returns_the_report_with_its_verdict():
    text = srv.screen_mixture({"Benzene": 60, "Toluene": 40},
                              light_key="Benzene", heavy_key="Toluene")
    assert "VERDICT" in text and "FEASIBLE" in text
    assert "alpha Benzene/Toluene" in text


def test_design_returns_a_column():
    text = srv.design_column({"Benzene": 60, "Toluene": 40}, "Benzene",
                             "Toluene")
    assert "stages" in text.lower()


def test_purity_and_impurity_must_come_together():
    with pytest.raises(ToolError, match="together"):
        srv.design_column({"Benzene": 60, "Toluene": 40}, "Benzene",
                          "Toluene", distillate_purity=0.99)


def test_a_bad_name_is_refused_before_the_cli_sees_it():
    with pytest.raises(ToolError, match="contains"):
        srv.screen_mixture({"Benzene,Toluene": 60})


def test_a_misspelt_name_comes_back_WITH_the_suggestion():
    """Review 11-08: the suggestion went to stderr, which was not captured, so
    the model saw only 'invalid arguments' and could not correct the name."""
    with pytest.raises(ToolError, match="Did you mean"):
        srv.screen_mixture({"Benzzzene": 60, "Toluene": 40})


def test_tools_run_one_at_a_time():
    """BioSTEAM's thermo settings and sys.stdout are process-wide. Two tools
    overlapping would each be able to run on the other's chemicals."""
    import threading
    from unittest import mock

    inside, peak, lock = [0], [0], threading.Lock()

    def fake_main(argv):
        with lock:
            inside[0] += 1
            peak[0] = max(peak[0], inside[0])
        threading.Event().wait(0.05)
        with lock:
            inside[0] -= 1
        print("VERDICT FEASIBLE")
        return 0

    with mock.patch.object(srv, "main", fake_main):
        ts = [threading.Thread(target=srv.screen_mixture,
                               args=({"Benzene": 60, "Toluene": 40},))
              for _ in range(4)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
    assert peak[0] == 1


def test_a_cli_usage_error_becomes_a_tool_error():
    with pytest.raises(ToolError):
        srv.sequence_by_minimum_vapour({"Benzene": 60, "Toluene": 40},
                                       ["Benzene", "Xylene"])


def test_the_azeotrope_gate_reaches_the_tool():
    text = srv.sequence_by_minimum_vapour(
        {"Ethanol": 40, "Water": 40, "Butanol": 20},
        ["Ethanol", "Water", "Butanol"])
    assert "CANNOT BE PERFORMED" in text


def test_find_azeotropes():
    assert "Ethanol/Water" in srv.find_azeotropes(["Ethanol", "Water"])
    assert "No azeotrope" in srv.find_azeotropes(["Methanol", "Water"])


def test_the_server_speaks_mcp_over_stdio_with_a_clean_stdout():
    """End to end, as Claude would call it: a real subprocess. If anything but
    protocol reached stdout the session would fail to parse it."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(
        command=sys.executable, args=["-m", "sepsyn.mcp_server"],
        env={**os.environ, "PYTHONPATH": ROOT}, cwd=ROOT)

    async def go():
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as session:
                await session.initialize()
                names = {t.name for t in (await session.list_tools()).tools}
                res = await session.call_tool(
                    "screen_mixture",
                    {"feed": {"Benzene": 60, "Toluene": 40}})
                return names, res

    names, res = asyncio.run(go())
    assert names == {"screen_mixture", "design_column",
                     "sequence_by_minimum_vapour", "rank_sequences",
                     "find_azeotropes"}
    assert not res.is_error
    assert "VERDICT" in res.content[0].text
