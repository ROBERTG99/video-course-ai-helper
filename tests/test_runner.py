import json
import subprocess

import pytest

from pipeline import runner


def _fake(returncode=0, stdout="", stderr=""):
    calls = {}

    def run(cmd, **kw):
        calls["cmd"], calls["kw"] = cmd, kw
        return subprocess.CompletedProcess(cmd, returncode, stdout, stderr)

    return run, calls


def test_run_claude_builds_command_and_parses(tmp_path, monkeypatch):
    p = tmp_path / "p.md"
    p.write_text("hola prompt", encoding="utf-8")
    out = json.dumps({"total_cost_usd": 0.42, "num_turns": 3, "result": "x" * 600})
    fake, calls = _fake(stdout=out)
    monkeypatch.setattr(runner.subprocess, "run", fake)
    res = runner.run_claude(p, "sonnet", 2.5, max_turns=7, allowed_tools=("Read", "Write", "Grep"))
    cmd = calls["cmd"]
    assert cmd[:2] == ["claude", "-p"]
    assert cmd[cmd.index("--model") + 1] == "sonnet"
    assert cmd[cmd.index("--max-turns") + 1] == "7"
    assert cmd[cmd.index("--max-budget-usd") + 1] == "2.5"
    assert cmd[cmd.index("--allowedTools") + 1] == "Read,Write,Grep"
    assert cmd[cmd.index("--output-format") + 1] == "json"
    assert calls["kw"]["input"] == "hola prompt"
    assert res == {"cost_usd": 0.42, "turns": 3, "result": "x" * 500}


def test_run_claude_raises_on_nonzero(tmp_path, monkeypatch):
    p = tmp_path / "p.md"
    p.write_text("x", encoding="utf-8")
    fake, _ = _fake(returncode=1, stderr="boom")
    monkeypatch.setattr(runner.subprocess, "run", fake)
    with pytest.raises(RuntimeError, match="boom"):
        runner.run_claude(p, "sonnet", 1.0)
