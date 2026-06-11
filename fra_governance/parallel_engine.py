"""
fra_governance/parallel_engine.py — Concurrent Multi-Track Research Execution

Activates the 4-track parallel execution defined in FRA_PROMPT_2026-05-21_PARALLEL.txt.
Runs multiple research tracks simultaneously using asyncio, collects results,
and produces a unified findings report.

Previously, FRA ran tracks sequentially. This engine enables true concurrency:
  - Track 1 (NUMERICAL): Precision recheck scripts
  - Track 2 (NUMERICAL): Boundary scan scripts
  - Track 3 (ANALYTICAL): Symbolic/algebraic proofs
  - Track 4 (ANALYTICAL+NUMERICAL): Integral/CS approaches

Each track runs in its own asyncio task with timeout, error isolation, and
result collection. Failed tracks don't block successful ones.

Integrated with governance: each track's metrics flow through the sandwich bridge.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Callable, Awaitable

logger = logging.getLogger("fra_governance.parallel")


@dataclass
class TrackDefinition:
    """A single research track to execute."""
    track_id: int
    name: str
    track_type: str  # "numerical" | "analytical" | "mixed"
    script_path: str | None = None  # Path to Python script (for numerical)
    task_description: str = ""  # For analytical tracks
    output_file: str = ""  # Where to write findings
    timeout_seconds: int = 300
    dependencies: list[int] = field(default_factory=list)  # Other track IDs this depends on
    python_path: str = ""  # Python executable
    env: dict = field(default_factory=dict)


@dataclass
class TrackResult:
    """Result from executing a single research track."""
    track_id: int
    name: str
    status: str  # "success" | "failed" | "timeout" | "skipped"
    output: str = ""
    error: str = ""
    duration_seconds: float = 0.0
    metrics: dict = field(default_factory=dict)
    findings_file: str = ""
    evidence_level: str = "assumption"
    started_at: str = ""
    completed_at: str = ""


@dataclass
class ParallelResult:
    """Aggregate result from a parallel execution session."""
    session_id: str
    tracks: list[TrackResult] = field(default_factory=list)
    total_duration: float = 0.0
    success_count: int = 0
    failure_count: int = 0
    timeout_count: int = 0


# ── Track Executors ──────────────────────────────────────────────────────────

async def _run_numerical_track(track: TrackDefinition) -> TrackResult:
    """Execute a numerical track by running a Python script."""
    started = datetime.now(timezone.utc).isoformat()
    t0 = time.time()

    python_exe = track.python_path or sys.executable
    script = track.script_path

    if not script or not os.path.exists(script):
        return TrackResult(
            track_id=track.track_id,
            name=track.name,
            status="failed",
            error=f"Script not found: {script}",
            started_at=started,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )

    env = os.environ.copy()
    env.update(track.env)
    env.setdefault("PYTHONUNBUFFERED", "1")

    try:
        proc = await asyncio.wait_for(
            asyncio.create_subprocess_exec(
                python_exe, script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=os.path.dirname(script) or ".",
            ),
            timeout=5,
        )

        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=track.timeout_seconds,
        )

        duration = time.time() - t0
        output = stdout.decode("utf-8", errors="replace")
        error_out = stderr.decode("utf-8", errors="replace")

        if proc.returncode == 0:
            return TrackResult(
                track_id=track.track_id,
                name=track.name,
                status="success",
                output=output[:5000],
                error=error_out[:2000],
                duration_seconds=duration,
                metrics={"returncode": 0, "output_lines": len(output.splitlines())},
                findings_file=track.output_file,
                evidence_level="NUMERICAL" if "dps" in track.task_description.lower() else "runtime_success",
                started_at=started,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )
        else:
            return TrackResult(
                track_id=track.track_id,
                name=track.name,
                status="failed",
                output=output[:3000],
                error=error_out[:3000] or f"Return code: {proc.returncode}",
                duration_seconds=duration,
                metrics={"returncode": proc.returncode},
                started_at=started,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )

    except asyncio.TimeoutError:
        duration = time.time() - t0
        return TrackResult(
            track_id=track.track_id,
            name=track.name,
            status="timeout",
            error=f"Timed out after {track.timeout_seconds}s",
            duration_seconds=duration,
            started_at=started,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as e:
        duration = time.time() - t0
        return TrackResult(
            track_id=track.track_id,
            name=track.name,
            status="failed",
            error=f"{type(e).__name__}: {e}",
            duration_seconds=duration,
            started_at=started,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )


async def _run_analytical_track(track: TrackDefinition) -> TrackResult:
    """Execute an analytical track (in-process symbolic work).

    This is a placeholder for analytical reasoning that would normally
    be done by an LLM agent. In automated mode, it runs sympy-based
    verification scripts if provided.
    """
    started = datetime.now(timezone.utc).isoformat()
    t0 = time.time()

    # If there's a script, run it as numerical
    if track.script_path and os.path.exists(track.script_path):
        return await _run_numerical_track(track)

    # For pure analytical tracks without scripts, return a placeholder
    return TrackResult(
        track_id=track.track_id,
        name=track.name,
        status="skipped",
        output="Analytical track requires LLM agent execution. No script provided.",
        duration_seconds=time.time() - t0,
        evidence_level="assumption",
        started_at=started,
        completed_at=datetime.now(timezone.utc).isoformat(),
    )


# ── Orchestrator ─────────────────────────────────────────────────────────────

async def execute_parallel_tracks(
    tracks: list[TrackDefinition],
    max_concurrent: int = 4,
    system_id: str | None = None,
) -> ParallelResult:
    """Execute multiple research tracks concurrently.

    Tracks with dependencies wait for their prerequisites before starting.
    Independent tracks run simultaneously up to max_concurrent.

    Args:
        tracks: List of track definitions
        max_concurrent: Maximum simultaneous tracks
        system_id: FRA system ID for governance logging

    Returns:
        ParallelResult with all track results
    """
    session_id = str(uuid.uuid4())[:12]
    t0 = time.time()

    logger.info(f"Parallel session {session_id}: launching {len(tracks)} tracks (max {max_concurrent} concurrent)")

    # Build dependency graph
    track_map = {t.track_id: t for t in tracks}
    completed: dict[int, TrackResult] = {}
    results: list[TrackResult] = []

    # Separate independent vs dependent tracks
    independent = [t for t in tracks if not t.dependencies]
    dependent = [t for t in tracks if t.dependencies]

    # Run independent tracks concurrently
    if independent:
        semaphore = asyncio.Semaphore(max_concurrent)

        async def run_with_limit(track: TrackDefinition) -> TrackResult:
            async with semaphore:
                if track.track_type == "numerical":
                    return await _run_numerical_track(track)
                else:
                    return await _run_analytical_track(track)

        independent_results = await asyncio.gather(
            *[run_with_limit(t) for t in independent],
            return_exceptions=True,
        )

        for track, result in zip(independent, independent_results):
            if isinstance(result, Exception):
                result = TrackResult(
                    track_id=track.track_id,
                    name=track.name,
                    status="failed",
                    error=f"{type(result).__name__}: {result}",
                    started_at=datetime.now(timezone.utc).isoformat(),
                    completed_at=datetime.now(timezone.utc).isoformat(),
                )
            results.append(result)
            completed[track.track_id] = result

    # Run dependent tracks after their prerequisites
    for track in dependent:
        # Verify all dependencies completed
        deps_ok = all(dep_id in completed and completed[dep_id].status == "success" for dep_id in track.dependencies)
        if not deps_ok:
            failed_deps = [dep_id for dep_id in track.dependencies if dep_id not in completed or completed[dep_id].status != "success"]
            result = TrackResult(
                track_id=track.track_id,
                name=track.name,
                status="skipped",
                error=f"Dependencies not met: {failed_deps}",
                started_at=datetime.now(timezone.utc).isoformat(),
                completed_at=datetime.now(timezone.utc).isoformat(),
            )
        else:
            if track.track_type == "numerical":
                result = await _run_numerical_track(track)
            else:
                result = await _run_analytical_track(track)

        results.append(result)
        completed[track.track_id] = result

    total_duration = time.time() - t0

    # Count outcomes
    success_count = sum(1 for r in results if r.status == "success")
    failure_count = sum(1 for r in results if r.status == "failed")
    timeout_count = sum(1 for r in results if r.status == "timeout")

    parallel_result = ParallelResult(
        session_id=session_id,
        tracks=results,
        total_duration=total_duration,
        success_count=success_count,
        failure_count=failure_count,
        timeout_count=timeout_count,
    )

    # Log to governance if system_id provided
    if system_id:
        try:
            from fra_governance.sandwich_bridge import process_request
            gov_state = {
                "metrics": {
                    "parallel_tracks": len(tracks),
                    "success_count": success_count,
                    "failure_count": failure_count,
                    "timeout_count": timeout_count,
                    "total_duration": total_duration,
                },
                "actions": [
                    {"type": f"track_{t.track_id}", "source": t.name, "flow": t.status, "loss": str(t.duration_seconds), "balance": 1.0 if t.status == "success" else -1.0}
                    for t in results
                ],
                "metadata": {"session_id": session_id, "parallel": True},
            }
            process_request(system_id, gov_state)
        except Exception:
            pass

    logger.info(
        f"Parallel session {session_id} complete: {success_count}/{len(tracks)} success, "
        f"{failure_count} failed, {timeout_count} timeout ({total_duration:.1f}s)"
    )

    return parallel_result


# ── FRA-Specific Track Builder ────────────────────────────────────────────────

def build_standard_fra_tracks(
    rh_dir: str = r"C:\Users\info\OneDrive\Desktop\RH",
    python_exe: str = r"C:\Windows\py.exe",
) -> list[TrackDefinition]:
    """Build the 4 standard FRA parallel tracks from the launch prompt.

    These correspond to the tracks defined in FRA_PROMPT_2026-05-21_PARALLEL.txt:
      Track 1: Precision recheck (dps=120)
      Track 2: JT-R1 failure boundary scan
      Track 3: d=1 base case analytical
      Track 4: Cauchy-Schwarz / Gram matrix approach
    """
    env = {"PYTHONPATH": rh_dir}

    tracks = [
        TrackDefinition(
            track_id=1,
            name="Precision Recheck (dps=120)",
            track_type="numerical",
            script_path=os.path.join(rh_dir, "jt_precision_recheck.py"),
            output_file=os.path.join(rh_dir, "jt_precision_recheck_finding.md"),
            timeout_seconds=600,
            python_path=python_exe,
            env=env,
            task_description="Recheck borderline JT cases at dps=120 for d=28,n=5 and d=29,n=5",
        ),
        TrackDefinition(
            track_id=2,
            name="JT-R1 Boundary Scan (n=0, n=1)",
            track_type="numerical",
            script_path=os.path.join(rh_dir, "jt_n0_boundary_scan.py"),
            output_file=os.path.join(rh_dir, "jt_boundary_finding.md"),
            timeout_seconds=600,
            python_path=python_exe,
            env=env,
            task_description="Map JT-R1 failure boundary along n=0 from d=1..30",
        ),
        TrackDefinition(
            track_id=3,
            name="d=1 Base Case (Analytical)",
            track_type="analytical",
            script_path=os.path.join(rh_dir, "jt_d1_hamburger_verify.py"),
            output_file=os.path.join(rh_dir, "d1_basecase_analysis.md"),
            timeout_seconds=300,
            python_path=python_exe,
            env=env,
            task_description="Prove C² ≤ 4Δ₀Δ₂ via Hamburger theorem (symbolic verification)",
        ),
        TrackDefinition(
            track_id=4,
            name="Cauchy-Schwarz / Gram Matrix",
            track_type="analytical",
            script_path=os.path.join(rh_dir, "jt_gram_cauchy_verify.py"),
            output_file=os.path.join(rh_dir, "gram_cauchy_analysis.md"),
            timeout_seconds=300,
            python_path=python_exe,
            env=env,
            task_description="Verify integral representation and Hamburger connection",
        ),
    ]

    # Filter out tracks whose scripts don't exist
    valid_tracks = []
    for t in tracks:
        if t.script_path and os.path.exists(t.script_path):
            valid_tracks.append(t)
        elif t.track_type == "analytical":
            valid_tracks.append(t)  # Analytical tracks don't need scripts
        else:
            logger.warning(f"Skipping Track {t.track_id}: script not found at {t.script_path}")

    return valid_tracks


def build_custom_tracks(
    script_dir: str,
    scripts: list[dict],
    python_exe: str = sys.executable,
) -> list[TrackDefinition]:
    """Build custom parallel tracks from a list of script specs.

    Each spec: {"name": str, "script": str, "type": "numerical"|"analytical", "timeout": int}
    """
    tracks = []
    for i, spec in enumerate(scripts):
        tracks.append(TrackDefinition(
            track_id=i + 1,
            name=spec["name"],
            track_type=spec.get("type", "numerical"),
            script_path=os.path.join(script_dir, spec["script"]),
            output_file=os.path.join(script_dir, spec.get("output", f"track_{i+1}_output.txt")),
            timeout_seconds=spec.get("timeout", 300),
            python_path=python_exe,
            env={"PYTHONPATH": script_dir},
            task_description=spec.get("description", ""),
        ))
    return tracks


# ── Findings Merger ───────────────────────────────────────────────────────────

def merge_findings(result: ParallelResult, output_path: str) -> str:
    """Merge all track findings into a unified report."""
    now = datetime.now(timezone.utc).isoformat()
    lines = [
        f"# FRA Parallel Session Report",
        f"Session: {result.session_id}",
        f"Completed: {now}",
        f"Duration: {result.total_duration:.1f}s",
        f"Results: {result.success_count} success, {result.failure_count} failed, {result.timeout_count} timeout",
        "",
        "---",
        "",
    ]

    for track in result.tracks:
        status_icon = {"success": "+", "failed": "x", "timeout": "T", "skipped": "-"}.get(track.status, "?")
        lines.append(f"## Track {track.track_id}: {track.name}  [{status_icon}]")
        lines.append(f"Status: {track.status} | Duration: {track.duration_seconds:.1f}s")
        lines.append(f"Evidence: {track.evidence_level}")
        if track.error:
            lines.append(f"Error: {track.error}")
        if track.output:
            lines.append("")
            lines.append("```")
            output_preview = track.output[:3000]
            lines.append(output_preview)
            if len(track.output) > 3000:
                lines.append(f"... (truncated, {len(track.output)} total chars)")
            lines.append("```")
        if track.findings_file and os.path.exists(track.findings_file):
            lines.append(f"Findings: {track.findings_file}")
        lines.append("")

    lines.append("---")
    lines.append(f"*Ma'at is the measure. Generated by FRA Parallel Engine.*")

    report = "\n".join(lines)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    return report


# ── Self-Test ─────────────────────────────────────────────────────────────────

def self_test() -> bool:
    """Test the parallel engine with a simple concurrent workload."""
    import tempfile

    async def _test():
        # Create a small test script
        tmpdir = tempfile.mkdtemp()
        test_script = os.path.join(tmpdir, "test_track.py")
        with open(test_script, "w") as f:
            f.write("import time, json\nprint(json.dumps({'ok': True, 'n': 42}))\n")

        tracks = [
            TrackDefinition(
                track_id=1,
                name="Test Track 1",
                track_type="numerical",
                script_path=test_script,
                output_file=os.path.join(tmpdir, "out1.txt"),
                timeout_seconds=10,
            ),
            TrackDefinition(
                track_id=2,
                name="Test Track 2",
                track_type="numerical",
                script_path=test_script,
                output_file=os.path.join(tmpdir, "out2.txt"),
                timeout_seconds=10,
            ),
            TrackDefinition(
                track_id=3,
                name="Test Track 3 (Dependent)",
                track_type="numerical",
                script_path=test_script,
                output_file=os.path.join(tmpdir, "out3.txt"),
                timeout_seconds=10,
                dependencies=[1],
            ),
        ]

        result = await execute_parallel_tracks(tracks, max_concurrent=2)

        assert result.success_count == 3, f"Expected 3 successes, got {result.success_count}"
        assert result.total_duration > 0
        assert len(result.tracks) == 3

        # Test findings merge
        report = merge_findings(result, os.path.join(tmpdir, "report.md"))
        assert "Test Track 1" in report
        assert "Test Track 2" in report

        # Cleanup
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)
        return True

    try:
        result = asyncio.run(_test())
        print("  parallel_engine self-test: ALL PASS")
        return result
    except Exception as e:
        traceback.print_exc()
        print(f"  parallel_engine self-test: ERROR - {e}")
        return False


if __name__ == "__main__":
    sys.exit(0 if self_test() else 1)
