"""DraftQueue — the draft review queue and its approve/discard lifecycle.

Owns the queue view (api_drafts, with staleness flagging), item lookup across the
replies/tweets tables, and the approve/discard transitions. Draft file structure
is delegated to ``DraftFile``; CSV row IO to ``tables.Table``; the staleness
threshold is read from ``ConfigStore``.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from .config_store import ConfigStore
from .draft_file import DraftFile
from .paths import PathResolver
from .tables import REPLIES, TWEETS, Table


class DraftQueue:
    def __init__(self, paths: PathResolver, config: ConfigStore) -> None:
        self.paths = paths
        self.config = config

    def find_item(self, item_id: str) -> tuple[Table | None, str | None, dict[str, str] | None]:
        for spec, item_type in ((REPLIES, None), (TWEETS, "tweet")):
            table = Table(self.paths, spec)
            for row in table.rows():
                if row.get(spec.id_field) == item_id:
                    resolved_type = item_type or (row.get("format") or "reply")
                    return table, resolved_type, row
        return None, None, None

    @staticmethod
    def parse_drafted_at(value: str) -> dt.datetime | None:
        try:
            parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)
        except (TypeError, ValueError):
            return None

    def api_drafts(self) -> dict[str, list[dict[str, Any]]]:
        staleness_hours = self.config.read_limits().get("draft_staleness_hours", 12)
        now = dt.datetime.now(dt.timezone.utc)
        drafts: list[dict[str, Any]] = []
        for path in sorted(self.paths.data_path("drafts").glob("*.md")):
            if path.name == ".gitkeep":
                continue
            item_id = path.stem
            _, item_type, row = self.find_item(item_id)
            if row is None:
                continue
            drafted_at = self.parse_drafted_at(row.get("drafted_at", ""))
            stale = (now - drafted_at) > dt.timedelta(hours=staleness_hours) if drafted_at else None
            drafts.append({
                "id": item_id,
                "type": item_type,
                "status": row.get("status"),
                "row": row,
                "raw": path.read_text(encoding="utf-8"),
                "stale_age": stale,
            })
        return {"drafts": drafts}

    def discard_draft(self, item_id: str, reason: str | None = None) -> dict[str, bool]:
        table, _, row = self.find_item(item_id)
        if row is None or table is None:
            raise ValueError("unknown draft id")
        table.update(item_id, {"status": "discarded"})
        src = self.paths.data_path("drafts", f"{item_id}.md")
        dst_dir = self.paths.data_path("drafts", "discarded")
        dst_dir.mkdir(parents=True, exist_ok=True)
        note = f"**Discarded**: user (dashboard), {dt.datetime.now().isoformat(timespec='seconds')}"
        if reason:
            note += f" - {reason}"
        (dst_dir / f"{item_id}.md").write_text(note + "\n\n" + src.read_text(encoding="utf-8"), encoding="utf-8")
        src.unlink()
        return {"ok": True}

    def approve_draft(self, item_id: str, edited_text: str | None = None) -> dict[str, str | bool]:
        table, _, row = self.find_item(item_id)
        if row is None or table is None:
            raise ValueError("unknown draft id")
        draft_path = self.paths.data_path("drafts", f"{item_id}.md")
        content = draft_path.read_text(encoding="utf-8")
        original = (row.get("draft_text") or "").strip()
        if edited_text is not None and edited_text.strip() != original:
            new_text = edited_text.strip()
            edit_summary = f"dashboard edit: {len(original)} -> {len(new_text)} chars"
            table.update(item_id, {
                "draft_text": new_text,
                "user_edited": "true",
                "edit_summary": edit_summary,
                "status": "edited",
            })
            draft_path.write_text(DraftFile.rewrite_body(content, new_text), encoding="utf-8")
            return {"ok": True, "status": "edited", "edit_summary": edit_summary}
        table.update(item_id, {"status": "approved"})
        return {"ok": True, "status": "approved"}
