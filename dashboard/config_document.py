"""Comment- and format-preserving field editor over text-backed config files.

`ConfigDocument` is a deep module: its interface is `get` / `set` / `set_many` /
`as_dict`, and all the surgical, in-place, regex-based editing that preserves
comments, blank lines, and key order lives inside the adapters below.

The adapters are the seam. Three real config-file shapes vary here, so this is a
genuine seam rather than a hypothetical one:

- ``ScalarYamlAdapter``       ``key: 123``            (config/limits.yaml)
- ``ListYamlAdapter``         ``key: [a, b, c]``      (config/metrics.yaml, nested)
- ``FrontmatterAdapter``      ``key: value``          (AGENTS.md ```yaml block)

Delete this module and the four bespoke regex parse/write pairs re-appear in
``file_store.py``; that is the depth check.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Protocol


class FieldAdapter(Protocol):
    """Knows how to read every field and rewrite one field for a file shape."""

    def read(self, text: str) -> dict[str, Any]:
        ...

    def write(self, text: str, key: str, value: Any) -> str:
        ...


class ScalarYamlAdapter:
    """``key: 123`` integer scalars; preserves trailing ``# inline comments``."""

    _READ = re.compile(r"^(\w+):\s*([0-9]+)", re.M)

    def read(self, text: str) -> dict[str, int]:
        return {m.group(1): int(m.group(2)) for m in self._READ.finditer(text)}

    def write(self, text: str, key: str, value: Any) -> str:
        # Only the digits are replaced, so an inline `# comment` after the value survives.
        return re.sub(rf"^({re.escape(key)}:\s*)[0-9]+", rf"\g<1>{value}", text, flags=re.M)


class ListYamlAdapter:
    """``key: [a, b, c]`` inline lists; matches indented (nested) keys too."""

    _READ = re.compile(r"^\s*(\w+):\s*\[(.*?)\]", re.M)

    def read(self, text: str) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for match in self._READ.finditer(text):
            result[match.group(1)] = [item.strip() for item in match.group(2).split(",") if item.strip()]
        return result

    def write(self, text: str, key: str, value: Any) -> str:
        newlist = ", ".join(str(item) for item in value)
        return re.sub(rf"^(\s*{re.escape(key)}:\s*)\[.*?\]", rf"\g<1>[{newlist}]", text, flags=re.M)


class FrontmatterAdapter:
    """``key: value`` lines (e.g. inside AGENTS.md's ```yaml active-config block).

    ``fields`` maps each editable key to a regex fragment its value must match, so
    the same adapter serves ``persona`` (``[\\w-]+``) and ``tagging`` (``on|off``)
    without assuming a leading ``---`` frontmatter fence.
    """

    def __init__(self, fields: dict[str, str]) -> None:
        self.fields = fields

    def read(self, text: str) -> dict[str, str | None]:
        out: dict[str, str | None] = {}
        for key, pattern in self.fields.items():
            match = re.search(rf"^{re.escape(key)}:\s*({pattern})", text, re.M)
            out[key] = match.group(1) if match else None
        return out

    def write(self, text: str, key: str, value: Any) -> str:
        pattern = self.fields[key]
        return re.sub(
            rf"^({re.escape(key)}:\s*)(?:{pattern})",
            rf"\g<1>{value}",
            text,
            count=1,
            flags=re.M,
        )


class ConfigDocument:
    """A text-backed config file edited one field at a time, format preserved."""

    def __init__(self, path: Path, adapter: FieldAdapter) -> None:
        self.path = path
        self.adapter = adapter

    def _text(self) -> str:
        return self.path.read_text(encoding="utf-8")

    def as_dict(self) -> dict[str, Any]:
        return self.adapter.read(self._text())

    def get(self, key: str) -> Any:
        return self.as_dict().get(key)

    def set(self, key: str, value: Any) -> None:
        self.path.write_text(self.adapter.write(self._text(), key, value), encoding="utf-8")

    def set_many(self, updates: dict[str, Any]) -> None:
        """Apply several field edits with a single read and a single write."""
        text = self._text()
        for key, value in updates.items():
            text = self.adapter.write(text, key, value)
        self.path.write_text(text, encoding="utf-8")
