"""IncidentLog — the incidents table and the send-lockout acknowledgement flow."""

from __future__ import annotations

import datetime as dt
from typing import Any

from .paths import PathResolver
from .tables import INCIDENTS, Table


class IncidentLog:
    def __init__(self, paths: PathResolver) -> None:
        self.paths = paths

    def _table(self) -> Table:
        return Table(self.paths, INCIDENTS)

    @staticmethod
    def is_lockout_row(row: dict[str, str]) -> bool:
        triggered = (row.get("lockout_triggered") or "").strip().lower() in ("true", "1", "yes")
        return triggered and not (row.get("acknowledged_at") or "").strip()

    def api_incidents(self) -> dict[str, Any]:
        rows = self._table().rows()
        return {"incidents": rows, "locked_out": any(self.is_lockout_row(row) for row in rows)}

    def clear_lockout(self) -> dict[str, bool]:
        table = self._table()
        fieldnames, rows = table.read()
        now = dt.datetime.now().isoformat(timespec="seconds")
        changed = False
        for row in rows:
            if self.is_lockout_row(row):
                row["acknowledged_at"] = now
                changed = True
        if changed:
            table.write(fieldnames, rows)
        return {"ok": True, "cleared": changed}
