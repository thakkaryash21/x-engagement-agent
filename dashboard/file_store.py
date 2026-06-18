from __future__ import annotations

import csv
import datetime as dt
import json
import re
import subprocess
from pathlib import Path
from typing import Any


VALID_MODES = ["learn", "scroll", "compose", "send", "review"]


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


class DashboardStore:
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

    def csv_rel(self, filename: str) -> str:
        return self.data_rel("csv", filename)

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

    def read_csv(self, relpath: str) -> tuple[list[str], list[dict[str, str]]]:
        with (self.root / relpath).open(newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            rows = list(reader)
            return reader.fieldnames or [], rows

    def write_csv(self, relpath: str, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
        with (self.root / relpath).open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def update_csv_row(self, relpath: str, id_field: str, id_value: str, updates: dict[str, str]) -> dict[str, str] | None:
        fieldnames, rows = self.read_csv(relpath)
        for row in rows:
            if row.get(id_field) == id_value:
                row.update(updates)
                self.write_csv(relpath, fieldnames, rows)
                return row
        return None

    def find_item(self, item_id: str) -> tuple[str | None, str | None, str | None, dict[str, str] | None]:
        _, rows = self.read_csv(self.csv_rel("replies.csv"))
        for row in rows:
            if row.get("reply_id") == item_id:
                return self.csv_rel("replies.csv"), "reply_id", row.get("format") or "reply", row
        _, rows = self.read_csv(self.csv_rel("tweets.csv"))
        for row in rows:
            if row.get("tweet_id") == item_id:
                return self.csv_rel("tweets.csv"), "tweet_id", "tweet", row
        return None, None, None, None

    def read_limits(self) -> dict[str, int]:
        text = self.config_path("limits.yaml").read_text(encoding="utf-8")
        return {m.group(1): int(m.group(2)) for m in re.finditer(r"^(\w+):\s*([0-9]+)", text, re.M)}

    def write_limits(self, updates: dict[str, Any]) -> dict[str, int]:
        path = self.config_path("limits.yaml")
        text = path.read_text(encoding="utf-8")
        for key, value in updates.items():
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"limits.{key} must be an integer")
            text = re.sub(rf"^({re.escape(key)}:\s*)[0-9]+", rf"\g<1>{value}", text, flags=re.M)
        path.write_text(text, encoding="utf-8")
        return self.read_limits()

    def read_metrics_yaml(self) -> dict[str, list[str]]:
        text = self.config_path("metrics.yaml").read_text(encoding="utf-8")
        result: dict[str, list[str]] = {}
        for match in re.finditer(r"^\s*(\w+):\s*\[(.*?)\]", text, re.M):
            result[match.group(1)] = [item.strip() for item in match.group(2).split(",") if item.strip()]
        return result

    def write_metrics_yaml(self, updates: dict[str, Any]) -> dict[str, list[str]]:
        path = self.config_path("metrics.yaml")
        text = path.read_text(encoding="utf-8")
        for key, items in updates.items():
            if not isinstance(items, list):
                raise ValueError(f"metrics.{key} must be a list")
            newlist = ", ".join(str(item) for item in items)
            text = re.sub(rf"^(\s*{re.escape(key)}:\s*)\[.*?\]", rf"\g<1>[{newlist}]", text, flags=re.M)
        path.write_text(text, encoding="utf-8")
        return self.read_metrics_yaml()

    def active_persona(self) -> dict[str, str | None]:
        text = (self.root / "AGENTS.md").read_text(encoding="utf-8")
        persona = re.search(r"^persona:\s*([\w-]+)", text, re.M)
        tagging = re.search(r"^tagging:\s*(on|off)", text, re.M)
        active = persona.group(1) if persona else None
        available = self.list_personas()
        if active not in available and available:
            active = available[0]
        return {
            "persona": active,
            "tagging": tagging.group(1) if tagging else None,
        }

    def write_active_persona(self, persona: str | None = None, tagging: str | None = None) -> dict[str, str | None]:
        path = self.root / "AGENTS.md"
        text = path.read_text(encoding="utf-8")
        if persona is not None:
            if persona not in self.list_personas():
                raise ValueError("unknown persona")
            text = re.sub(r"^(persona:\s*)[\w-]+", rf"\g<1>{persona}", text, count=1, flags=re.M)
        if tagging is not None:
            if tagging not in ("on", "off"):
                raise ValueError("tagging must be 'on' or 'off'")
            text = re.sub(r"^(tagging:\s*)(on|off)", rf"\g<1>{tagging}", text, count=1, flags=re.M)
        path.write_text(text, encoding="utf-8")
        return self.active_persona()

    def list_personas(self) -> list[str]:
        return sorted(path.stem for path in self.data_path("personas").glob("*.md"))

    @staticmethod
    def parse_drafted_at(value: str) -> dt.datetime | None:
        try:
            parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)
        except (TypeError, ValueError):
            return None

    def api_drafts(self) -> dict[str, list[dict[str, Any]]]:
        staleness_hours = self.read_limits().get("draft_staleness_hours", 12)
        now = dt.datetime.now(dt.timezone.utc)
        drafts: list[dict[str, Any]] = []
        for path in sorted(self.data_path("drafts").glob("*.md")):
            if path.name == ".gitkeep":
                continue
            item_id = path.stem
            _, _, item_type, row = self.find_item(item_id)
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

    @staticmethod
    def split_draft_body(text: str) -> tuple[str, str | None, str | None]:
        lines = text.splitlines()
        sep_indices = [index for index, line in enumerate(lines) if line.strip() == "---"]
        if len(sep_indices) < 2:
            return text, None, None
        start, end = sep_indices[0], sep_indices[1]
        return "\n".join(lines[:start]), "\n".join(lines[start + 1:end]).strip(), "\n".join(lines[end + 1:])

    def rewrite_draft_body(self, text: str, new_body: str) -> str:
        header, _, trailer = self.split_draft_body(text)
        parts = [header.rstrip(), "", "---", new_body.strip(), "---"]
        if trailer and trailer.strip():
            parts += ["", trailer.strip()]
        return "\n".join(parts) + "\n"

    def discard_draft(self, item_id: str, reason: str | None = None) -> dict[str, bool]:
        csv_path, id_field, _, row = self.find_item(item_id)
        if row is None or csv_path is None or id_field is None:
            raise ValueError("unknown draft id")
        self.update_csv_row(csv_path, id_field, item_id, {"status": "discarded"})
        src = self.data_path("drafts", f"{item_id}.md")
        dst_dir = self.data_path("drafts", "discarded")
        dst_dir.mkdir(parents=True, exist_ok=True)
        note = f"**Discarded**: user (dashboard), {dt.datetime.now().isoformat(timespec='seconds')}"
        if reason:
            note += f" - {reason}"
        (dst_dir / f"{item_id}.md").write_text(note + "\n\n" + src.read_text(encoding="utf-8"), encoding="utf-8")
        src.unlink()
        return {"ok": True}

    def approve_draft(self, item_id: str, edited_text: str | None = None) -> dict[str, str | bool]:
        csv_path, id_field, _, row = self.find_item(item_id)
        if row is None or csv_path is None or id_field is None:
            raise ValueError("unknown draft id")
        draft_path = self.data_path("drafts", f"{item_id}.md")
        content = draft_path.read_text(encoding="utf-8")
        original = (row.get("draft_text") or "").strip()
        if edited_text is not None and edited_text.strip() != original:
            new_text = edited_text.strip()
            edit_summary = f"dashboard edit: {len(original)} -> {len(new_text)} chars"
            self.update_csv_row(csv_path, id_field, item_id, {
                "draft_text": new_text,
                "user_edited": "true",
                "edit_summary": edit_summary,
                "status": "edited",
            })
            draft_path.write_text(self.rewrite_draft_body(content, new_text), encoding="utf-8")
            return {"ok": True, "status": "edited", "edit_summary": edit_summary}
        self.update_csv_row(csv_path, id_field, item_id, {"status": "approved"})
        return {"ok": True, "status": "approved"}

    @staticmethod
    def to_float(value: str | None) -> float | None:
        try:
            return float(value) if value not in (None, "") else None
        except ValueError:
            return None

    def funnel_counts(self, relpath: str, statuses: list[str]) -> dict[str, int]:
        _, rows = self.read_csv(relpath)
        counts = {status: 0 for status in statuses}
        for row in rows:
            status = row.get("status", "")
            if status in counts:
                counts[status] += 1
        counts["reviewed"] = sum(1 for row in rows if row.get("status") == "sent" and (row.get("reviewed_at") or "").strip())
        return counts

    def edit_rate(self) -> dict[str, int | float | None]:
        total_sent = 0
        edited = 0
        for relpath in (self.csv_rel("replies.csv"), self.csv_rel("tweets.csv")):
            _, rows = self.read_csv(relpath)
            for row in rows:
                if row.get("status") == "sent":
                    total_sent += 1
                    if (row.get("user_edited") or "").strip().lower() == "true":
                        edited += 1
        return {"sent": total_sent, "edited": edited, "rate": (edited / total_sent) if total_sent else None}

    def latest_metrics_by_item(self) -> dict[str, dict[str, str]]:
        _, rows = self.read_csv(self.csv_rel("metrics.csv"))
        latest: dict[str, dict[str, str]] = {}
        for row in rows:
            item_id = row.get("item_id")
            if item_id and (item_id not in latest or row.get("captured_at", "") > latest[item_id].get("captured_at", "")):
                latest[item_id] = row
        return latest

    def performance_breakdown(self) -> dict[str, dict[str, dict[str, float | int]]]:
        metrics = self.latest_metrics_by_item()
        by_archetype: dict[str, list[float]] = {}
        _, replies = self.read_csv(self.csv_rel("replies.csv"))
        for row in replies:
            metric = metrics.get(row.get("reply_id", ""))
            rate = self.to_float(metric.get("engagement_rate") if metric else None)
            if rate is not None:
                by_archetype.setdefault(row.get("reply_archetype") or "(unset)", []).append(rate)

        by_content_type: dict[str, list[float]] = {}
        _, tweets = self.read_csv(self.csv_rel("tweets.csv"))
        for row in tweets:
            metric = metrics.get(row.get("tweet_id", ""))
            rate = self.to_float(metric.get("engagement_rate") if metric else None)
            if rate is not None:
                by_content_type.setdefault(row.get("content_type") or "(unset)", []).append(rate)

        def summarize(values: dict[str, list[float]]) -> dict[str, dict[str, float | int]]:
            return {key: {"n": len(items), "avg_engagement_rate": sum(items) / len(items)} for key, items in values.items()}

        return {"by_reply_archetype": summarize(by_archetype), "by_content_type": summarize(by_content_type)}

    def api_insights(self) -> dict[str, Any]:
        return {
            "funnel": {
                "replies": self.funnel_counts(self.csv_rel("replies.csv"), ["drafted", "approved", "edited", "discarded", "sent"]),
                "tweets": self.funnel_counts(self.csv_rel("tweets.csv"), ["drafted", "approved", "edited", "discarded", "sent"]),
            },
            "edit_rate": self.edit_rate(),
            "performance": self.performance_breakdown(),
            "profiles": self.read_csv(self.csv_rel("profiles.csv"))[1],
        }

    @staticmethod
    def is_lockout_row(row: dict[str, str]) -> bool:
        triggered = (row.get("lockout_triggered") or "").strip().lower() in ("true", "1", "yes")
        return triggered and not (row.get("acknowledged_at") or "").strip()

    def api_incidents(self) -> dict[str, Any]:
        _, rows = self.read_csv(self.csv_rel("incidents.csv"))
        return {"incidents": rows, "locked_out": any(self.is_lockout_row(row) for row in rows)}

    def clear_lockout(self) -> dict[str, bool]:
        fieldnames, rows = self.read_csv(self.csv_rel("incidents.csv"))
        now = dt.datetime.now().isoformat(timespec="seconds")
        changed = False
        for row in rows:
            if self.is_lockout_row(row):
                row["acknowledged_at"] = now
                changed = True
        if changed:
            self.write_csv(self.csv_rel("incidents.csv"), fieldnames, rows)
        return {"ok": True, "cleared": changed}

    def read_md_file(self, rel: str) -> str:
        return self.safe_md_path(rel).read_text(encoding="utf-8")

    def write_md_file(self, rel: str, content: str) -> dict[str, str | bool]:
        path = self.safe_md_path(rel)
        today = dt.date.today().isoformat()
        if re.search(r"^last_updated:\s*\S+", content, re.M):
            content = re.sub(r"^(last_updated:\s*)\S+", rf"\g<1>{today}", content, count=1, flags=re.M)
        path.write_text(content, encoding="utf-8")
        return {"ok": True, "last_updated": today}

    def run_state_path(self) -> Path:
        return self.root / "dashboard" / "run-state.json"

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

        agent_command = self.app_config.get("agent_command", "codex")
        run_cmd = f"Set-Location -LiteralPath '{self.root}'; {agent_command} '{prompt}'"
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
