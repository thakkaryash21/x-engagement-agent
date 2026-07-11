"""PathResolver — the path-safety core every other dashboard module depends on.

Owns repo/data-root resolution, path-escape guards, the editable-markdown
allowlist, knowledge-file listing, persona listing, and safe markdown read/write.
Every service module (ConfigStore, DraftQueue, InsightsView, IncidentLog,
RunLauncher) is constructed from a single ``PathResolver`` and routes filesystem
access through it, so the traversal guards live in exactly one place.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path


def read_simple_yaml(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.is_file():
        return data
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


class PathResolver:
    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or Path(__file__).resolve().parent.parent).resolve()
        self.app_config = read_simple_yaml(self.root / "config" / "app.yaml")
        self.data_root_name = self.app_config.get("data_root", "data")
        self.data_root = (self.root / self.data_root_name).resolve()
        self.editable_md_prefixes = (
            f"{self.data_root_name}/personas/",
            "guidelines/",
            f"{self.data_root_name}/style/",
            f"{self.data_root_name}/learnings/",
            f"{self.data_root_name}/writing/",
        )

    # --- Path safety -----------------------------------------------------------

    def data_path(self, *parts: str) -> Path:
        path = self.data_root.joinpath(*parts).resolve()
        try:
            path.relative_to(self.data_root)
        except ValueError as exc:
            raise ValueError("path escapes data root") from exc
        return path

    def data_rel(self, *parts: str) -> str:
        return str(self.data_path(*parts).relative_to(self.root)).replace("\\", "/")

    def config_path(self, filename: str) -> Path:
        path = (self.root / "config" / filename).resolve()
        try:
            path.relative_to(self.root / "config")
        except ValueError as exc:
            raise ValueError("path escapes config root") from exc
        return path

    def safe_md_path(self, rel: str) -> Path:
        rel = rel.strip("/\\")
        if not rel.endswith(".md"):
            raise ValueError("only .md files are editable here")
        if not rel.startswith(self.editable_md_prefixes):
            raise ValueError("path not in an editable area")
        path = (self.root / rel).resolve()
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("path escapes repo root") from exc
        if not path.is_file():
            raise ValueError("file does not exist")
        return path

    # --- Listings --------------------------------------------------------------

    def list_personas(self) -> list[str]:
        return sorted(path.stem for path in self.data_path("personas").glob("*.md"))

    def list_editable_md(self) -> list[str]:
        out: list[str] = []
        for prefix in self.editable_md_prefixes:
            base = self.root / prefix
            if not base.is_dir():
                continue
            for path in sorted(base.rglob("*.md")):
                out.append(str(path.relative_to(self.root)).replace("\\", "/"))
        return sorted(set(out))

    def knowledge_files(self) -> dict[str, list[str]]:
        return {
            "persona": [str(p).replace("\\", "/") for p in sorted(self.data_path("personas").glob("*.md"))],
            "style": [str(p).replace("\\", "/") for p in sorted(self.data_path("style").glob("*.md"))],
            "learnings": [str(p).replace("\\", "/") for p in sorted(self.data_path("learnings").glob("*.md"))],
            "writing": [str(p).replace("\\", "/") for p in sorted(self.data_path("writing").glob("*.md"))],
            "guidelines": [
                str(p).replace("\\", "/")
                for p in sorted((self.root / "guidelines").rglob("*.md"))
            ],
        }

    def api_knowledge(self) -> dict[str, list[dict[str, str]]]:
        result: dict[str, list[dict[str, str]]] = {}
        for section, paths in self.knowledge_files().items():
            result[section] = []
            for path_text in paths:
                path = Path(path_text)
                rel = str(path.relative_to(self.root)).replace("\\", "/")
                try:
                    content = path.read_text(encoding="utf-8") if path.is_file() else "(file not yet created)"
                except OSError as exc:
                    content = f"(error reading file: {exc})"
                result[section].append({"path": rel, "content": content})
        return result

    # --- Editable markdown -----------------------------------------------------

    def read_md_file(self, rel: str) -> str:
        return self.safe_md_path(rel).read_text(encoding="utf-8")

    def write_md_file(self, rel: str, content: str) -> dict[str, str | bool]:
        path = self.safe_md_path(rel)
        today = dt.date.today().isoformat()
        if re.search(r"^last_updated:\s*\S+", content, re.M):
            content = re.sub(r"^(last_updated:\s*)\S+", rf"\g<1>{today}", content, count=1, flags=re.M)
        path.write_text(content, encoding="utf-8")
        return {"ok": True, "last_updated": today}
