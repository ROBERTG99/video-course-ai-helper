from __future__ import annotations

import json
import subprocess
from pathlib import Path


def run_claude(prompt_path: Path, model: str, budget_usd: float, max_turns: int = 20,
               allowed_tools: tuple[str, ...] = ("Read", "Write"), timeout_s: int = 1800) -> dict:
    """Headless Claude Code run with a hard budget. Returns {cost_usd, turns, result}. Raises on non-zero exit."""
    cmd = ["claude", "-p", "--model", model, "--max-turns", str(max_turns), "--max-budget-usd", str(budget_usd),
           "--allowedTools", ",".join(allowed_tools), "--output-format", "json"]
    r = subprocess.run(cmd, input=prompt_path.read_text(encoding="utf-8"), capture_output=True, text=True, timeout=timeout_s, check=False)
    if r.returncode != 0:
        raise RuntimeError(f"claude -p failed ({r.returncode}): {r.stderr[-800:]}")
    out = json.loads(r.stdout)
    return {"cost_usd": out.get("total_cost_usd"), "turns": out.get("num_turns"), "result": (out.get("result") or "")[:500]}
