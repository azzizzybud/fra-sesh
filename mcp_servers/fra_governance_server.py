"""
fra_governance_server.py — MCP server: FRA governance + all 5 FRA agents.

13 tools total:
  Governance (7): fra_governance_process, fra_governance_report, fra_cauchy_balance,
                   fra_chamber_status, fra_baseline_health, fra_spawn_agent, fra_run_3agent_loop
  Agents (6):     fra_content_generate, fra_math_agent, fra_explore_direction,
                   fra_voice_render, fra_jt_scan, fra_jt_status
"""
import asyncio, json, os, subprocess, sys
from pathlib import Path

_fra_dir = os.environ.get("FRA_DIR", r"C:\Users\info\OneDrive\Desktop\Claude-workspace\feather-research-agent")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, _fra_dir)  # For FRA module imports

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

server = Server("fra_governance")
_initialized = False
_odysseus_id = None
_fra_dir = os.environ.get("FRA_DIR", r"C:\Users\info\OneDrive\Desktop\Claude-workspace\feather-research-agent")


def _ensure_init():
    global _initialized, _odysseus_id
    if _initialized: return
    _initialized = True
    from fra_governance.sandwich_bridge import register_fra_sesh
    result = register_fra_sesh("FRA Sesh", trust_level="amber", chamber_depth=0)
    _odysseus_id = result["system_id"]
    from fra_governance.baseline_tracker import establish_baseline
    from fra_governance.cost_function import set_optimal
    for metric, base, tol in [("rounds", 10.0, 0.5), ("tool_calls", 5.0, 0.5), ("errors", 0.0, 0.1)]:
        establish_baseline(_odysseus_id, metric, base)
        set_optimal(_odysseus_id, metric, base, tolerance=tol)


async def _run_fra_tool_async(script_name: str, args: list, timeout: int = 120) -> dict:
    """Run a FRA tool wrapper script via async subprocess."""
    script = os.path.join(_fra_dir, script_name)
    if not os.path.exists(script):
        return {"error": f"Script not found: {script}"}
    env = os.environ.copy()
    env["PYTHONPATH"] = _fra_dir + os.pathsep + env.get("PYTHONPATH", "")
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, script, *args,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            cwd=_fra_dir, env=env,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        out_text = (stdout.decode("utf-8", errors="replace") if stdout else "").strip()
        err_text = (stderr.decode("utf-8", errors="replace") if stderr else "").strip()
        if proc.returncode != 0:
            return {"error": err_text or f"Exit {proc.returncode}", "stdout": out_text[:500]}
        if not out_text:
            return {"error": "Empty output", "stderr": err_text[:500] if err_text else ""}
        try:
            return json.loads(out_text)
        except json.JSONDecodeError:
            return {"result": out_text[:5000]}
    except asyncio.TimeoutError:
        return {"error": f"Timed out after {timeout}s"}
    except Exception as e:
        return {"error": str(e)}


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(name="fra_governance_process", description="Process agent action through 7-layer Vine/SBT governance",
             inputSchema={"type":"object","properties":{"metrics":{"type":"object"},"actions":{"type":"array","items":{"type":"object"}},"metadata":{"type":"object"}}}),
        Tool(name="fra_governance_report", description="Comprehensive governance report: ledger, chamber, health",
             inputSchema={"type":"object","properties":{}}),
        Tool(name="fra_cauchy_balance", description="Cauchy ledger: total entries, balance, violations",
             inputSchema={"type":"object","properties":{}}),
        Tool(name="fra_chamber_status", description="Ordered chamber: priority ordering check",
             inputSchema={"type":"object","properties":{}}),
        Tool(name="fra_baseline_health", description="Geometric baseline: curvature, anomalies",
             inputSchema={"type":"object","properties":{}}),
        Tool(name="fra_spawn_agent", description="Spawn vine-structured sub-agents (scale 3-5, 2x2 or 3x3)",
             inputSchema={"type":"object","properties":{"scale":{"type":"integer","enum":[3,4,5]},"vine_type":{"type":"string","enum":["2x2","3x3"]},"parent_id":{"type":"string"}},"required":["scale"]}),
        Tool(name="fra_run_3agent_loop", description="Run 3-agent research loop on a research file",
             inputSchema={"type":"object","properties":{"research_file":{"type":"string"}},"required":["research_file"]}),
        Tool(name="fra_content_generate", description="Generate viral content: TikTok/Reels scripts, YouTube outlines, LinkedIn posts, hooks",
             inputSchema={"type":"object","properties":{"angle":{"type":"string"},"format":{"type":"string","enum":["short_form","long_form","linkedin","all"]},"product":{"type":"string"}},"required":["angle","format"]}),
        Tool(name="fra_math_agent", description="Run autonomous MathAgent for Hermite-Bezoutian positivity (Gate A/B)",
             inputSchema={"type":"object","properties":{"gate":{"type":"string","enum":["A","B"]},"max_iter":{"type":"integer"},"direction":{"type":"string"}},"required":["gate"]}),
        Tool(name="fra_explore_direction", description="Process user direction to unstick MathAgent (no Telegram)",
             inputSchema={"type":"object","properties":{"stuck_context":{"type":"string"},"user_direction":{"type":"string"},"barrier":{"type":"string"}},"required":["stuck_context","user_direction"]}),
        Tool(name="fra_voice_render", description="Render script to audio via ElevenLabs TTS",
             inputSchema={"type":"object","properties":{"script_path":{"type":"string"}},"required":["script_path"]}),
        Tool(name="fra_jt_scan", description="Jensen-Turan E-Turan numerical scan",
             inputSchema={"type":"object","properties":{"d_max":{"type":"integer"},"n_max":{"type":"integer"},"x_points":{"type":"integer"},"dps":{"type":"integer"}}}),
        Tool(name="fra_jt_status", description="Jensen-Turan programme status",
             inputSchema={"type":"object","properties":{}}),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    _ensure_init()

    # ── Governance tools ──
    if name == "fra_governance_process":
        from fra_governance.sandwich_bridge import process_request
        raw = {"metrics": arguments.get("metrics", {}), "actions": arguments.get("actions", []), "metadata": arguments.get("metadata", {})}
        return [TextContent(type="text", text=json.dumps(process_request(_odysseus_id, raw), indent=2))]

    if name == "fra_governance_report":
        from fra_governance.sandwich_bridge import get_report
        return [TextContent(type="text", text=json.dumps(get_report(_odysseus_id), indent=2))]

    if name == "fra_cauchy_balance":
        from fra_governance.cauchy_ledger import get_balance_sheet, verify_agent
        return [TextContent(type="text", text=json.dumps({"balance_sheet": get_balance_sheet(), "odysseus_ledger": verify_agent(_odysseus_id)}, indent=2))]

    if name == "fra_chamber_status":
        from fra_governance.chamber_monitor import get_chamber_status, check_chamber
        return [TextContent(type="text", text=json.dumps({"status": get_chamber_status(), "last_check": check_chamber()}, indent=2))]

    if name == "fra_baseline_health":
        from fra_governance.baseline_tracker import get_system_health, get_agent_health
        return [TextContent(type="text", text=json.dumps({"system": get_system_health(), "odysseus": get_agent_health(_odysseus_id)}, indent=2))]

    if name == "fra_spawn_agent":
        from fra_governance.vine_spawner import spawn_agent, compute_scale_complexity
        scale = arguments.get("scale", 3)
        vine_type = arguments.get("vine_type", "2x2")
        result = spawn_agent(scale, parent_id=arguments.get("parent_id"), vine_type=vine_type)
        result["predicted_complexity"] = compute_scale_complexity(scale, vine_type=vine_type)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    if name == "fra_run_3agent_loop":
        research_file = arguments.get("research_file", "")
        if not os.path.exists(research_file):
            return [TextContent(type="text", text=f"Error: file not found: {research_file}")]
        loop_script = os.path.join(_fra_dir, "fra_3agent_loop.py")
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, loop_script, research_file,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=_fra_dir)
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
            output = stdout.decode("utf-8", errors="replace")
            if stderr: output += "\nSTDERR:\n" + stderr.decode("utf-8", errors="replace")
            next_prompt = ""
            nf = os.path.join(_fra_dir, "05_research", "RH", "NEXT_FRA_PROMPT.txt")
            if os.path.exists(nf):
                with open(nf, "r", encoding="utf-8") as f: next_prompt = f.read()[:500]
            return [TextContent(type="text", text=json.dumps({"status":"completed" if proc.returncode==0 else "error","output":output[:2000],"next_prompt":next_prompt}, indent=2))]
        except asyncio.TimeoutError:
            return [TextContent(type="text", text="Error: timed out after 120s")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]

    # ── FRA Agent tools (via wrapper scripts) ──
    if name == "fra_content_generate":
        r = await _run_fra_tool_async("fra_tool_test.py", ["test_arg"], timeout=5)
        return [TextContent(type="text", text=json.dumps(r, indent=2))]

    if name == "fra_math_agent":
        args_list = [arguments.get("gate", "A"), str(arguments.get("max_iter", 10))]
        d = arguments.get("direction", "")
        if d: args_list.append(d)
        r = await _run_fra_tool_async("fra_tool_math.py", args_list, timeout=300)
        return [TextContent(type="text", text=json.dumps(r, indent=2))]

    if name == "fra_explore_direction":
        r = await _run_fra_tool_async("fra_tool_explore.py", [
            arguments.get("stuck_context", ""),
            arguments.get("user_direction", ""),
            arguments.get("barrier", ""),
        ], timeout=60)
        return [TextContent(type="text", text=json.dumps(r, indent=2))]

    if name == "fra_voice_render":
        r = await _run_fra_tool_async("fra_tool_voice.py", [arguments.get("script_path", "")], timeout=120)
        return [TextContent(type="text", text=json.dumps(r, indent=2))]

    if name == "fra_jt_scan":
        r = await _run_fra_tool_async("fra_tool_jt.py", [
            "scan",
            str(arguments.get("d_max", 10)),
            str(arguments.get("n_max", 10)),
            str(arguments.get("x_points", 41)),
            str(arguments.get("dps", 50)),
        ], timeout=300)
        return [TextContent(type="text", text=json.dumps(r, indent=2))]

    if name == "fra_jt_status":
        r = await _run_fra_tool_async("fra_tool_jt.py", ["status"], timeout=30)
        return [TextContent(type="text", text=json.dumps(r, indent=2) if isinstance(r, dict) else str(r))]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def run():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(run())
