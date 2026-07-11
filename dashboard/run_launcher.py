"""RunLauncher — launch an agent mode in a new terminal and track run state."""

from __future__ import annotations

import datetime as dt
import json
import subprocess
from pathlib import Path
from typing import Any

from .paths import PathResolver

VALID_MODES = ["learn", "scroll", "compose", "send", "review"]


class RunLauncher:
    def __init__(self, paths: PathResolver) -> None:
        self.paths = paths

    def run_state_path(self) -> Path:
        return self.paths.root / "dashboard" / "run-state.json"

    def read_run_state(self) -> dict[str, Any]:
        path = self.run_state_path()
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"last_launch": None}

    def write_run_state(self, state: dict[str, Any]) -> None:
        self.run_state_path().write_text(json.dumps(state, indent=2), encoding="utf-8")

    def launch_run(self, mode: str, persona: str | None = None, tagging: bool = False) -> dict[str, Any]:
        if mode not in VALID_MODES:
            raise ValueError(f"unknown mode: {mode}")
        prompt = mode
        if persona:
            prompt += f" --persona {persona}"
        if tagging:
            if mode != "scroll":
                raise ValueError("--tagging is only valid for scroll mode")
            prompt += " --tagging"

        agent_command = self.paths.app_config.get("agent_command", "codex")
        # Enable Codex native off-X web search for the Context Brief when opted in
        # via config/app.yaml agent_web_search; see guidelines/context-enrichment.md §5
        # adapter (c). read_simple_yaml yields string values.
        web_search = str(self.paths.app_config.get("agent_web_search", "")).strip().lower() in ("true", "1", "yes", "on")
        invocation = f"{agent_command} --search '{prompt}'" if web_search else f"{agent_command} '{prompt}'"
        run_cmd = f"Set-Location -LiteralPath '{self.paths.root}'; {invocation}"
        subprocess.Popen(f'start "X Engagement Agent" powershell -NoExit -Command "{run_cmd}"', shell=True)
        state = {"last_launch": {
            "mode": mode,
            "persona": persona,
            "tagging": bool(tagging),
            "prompt": prompt,
            "started_at": dt.datetime.now().isoformat(timespec="seconds"),
        }}
        self.write_run_state(state)
        return state
