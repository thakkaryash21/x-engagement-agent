"""ConfigStore — read/write the three text-backed config surfaces.

Owns limits.yaml, metrics.yaml, and the AGENTS.md active-persona block. All the
format-preserving field editing lives in ``ConfigDocument``; ConfigStore adds the
per-surface validation (int limits, list metrics, known persona, on/off tagging).
"""

from __future__ import annotations

from typing import Any

from .config_document import (
    ConfigDocument,
    FrontmatterAdapter,
    ListYamlAdapter,
    ScalarYamlAdapter,
)
from .paths import PathResolver


class ConfigStore:
    def __init__(self, paths: PathResolver) -> None:
        self.paths = paths

    def _limits_doc(self) -> ConfigDocument:
        return ConfigDocument(self.paths.config_path("limits.yaml"), ScalarYamlAdapter())

    def _metrics_doc(self) -> ConfigDocument:
        return ConfigDocument(self.paths.config_path("metrics.yaml"), ListYamlAdapter())

    def _persona_doc(self) -> ConfigDocument:
        return ConfigDocument(
            self.paths.root / "AGENTS.md",
            FrontmatterAdapter({"persona": r"[\w-]+", "tagging": r"on|off"}),
        )

    def read_limits(self) -> dict[str, int]:
        return self._limits_doc().as_dict()

    def write_limits(self, updates: dict[str, Any]) -> dict[str, int]:
        for key, value in updates.items():
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"limits.{key} must be an integer")
        self._limits_doc().set_many(updates)
        return self.read_limits()

    def read_metrics_yaml(self) -> dict[str, list[str]]:
        return self._metrics_doc().as_dict()

    def write_metrics_yaml(self, updates: dict[str, Any]) -> dict[str, list[str]]:
        for key, items in updates.items():
            if not isinstance(items, list):
                raise ValueError(f"metrics.{key} must be a list")
        self._metrics_doc().set_many(updates)
        return self.read_metrics_yaml()

    def list_personas(self) -> list[str]:
        return self.paths.list_personas()

    def active_persona(self) -> dict[str, str | None]:
        values = self._persona_doc().as_dict()
        active = values.get("persona")
        available = self.list_personas()
        if active not in available and available:
            active = available[0]
        return {"persona": active, "tagging": values.get("tagging")}

    def write_active_persona(self, persona: str | None = None, tagging: str | None = None) -> dict[str, str | None]:
        doc = self._persona_doc()
        if persona is not None:
            if persona not in self.list_personas():
                raise ValueError("unknown persona")
            doc.set("persona", persona)
        if tagging is not None:
            if tagging not in ("on", "off"):
                raise ValueError("tagging must be 'on' or 'off'")
            doc.set("tagging", tagging)
        return self.active_persona()
