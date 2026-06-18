#!/usr/bin/env python3
"""Twitter Agent Dashboard — local-only view/edit layer over this folder's files.

Per 01-spec.md §10: files remain the source of truth. This server reads and writes
the same CSVs, YAML, and Markdown the agent modes use (AGENTS.md) — it never
maintains a second database, and nothing runs when idle beyond this one process.

Run:  python server.py
Then open http://localhost:8787
"""

import csv
import datetime
import json
import mimetypes
import re
import subprocess
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # twitter-agent/
STATIC_DIR = Path(__file__).resolve().parent / "static"
def read_simple_yaml(path):
    data = {}
    if not path.is_file():
        return data
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data

APP_CONFIG = read_simple_yaml(ROOT / "config" / "app.yaml")
DATA_ROOT_NAME = APP_CONFIG.get("data_root", "data")
DATA_ROOT = (ROOT / DATA_ROOT_NAME).resolve()
PORT = int(APP_CONFIG.get("dashboard_port", "8787"))


def data_path(*parts):
    path = (DATA_ROOT.joinpath(*parts)).resolve()
    try:
        path.relative_to(DATA_ROOT)
    except ValueError:
        raise ValueError("path escapes data root")
    return path


def data_rel(*parts):
    return str(data_path(*parts).relative_to(ROOT)).replace("\\", "/")

VALID_MODES = ["learn", "scroll", "compose", "send", "review"]
EDITABLE_MD_PREFIXES = (f"{DATA_ROOT_NAME}/personas/", "guidelines/", f"{DATA_ROOT_NAME}/style/", f"{DATA_ROOT_NAME}/learnings/", f"{DATA_ROOT_NAME}/writing/")


# ---------------------------------------------------------------------------
# Path safety
# ---------------------------------------------------------------------------

def safe_md_path(rel: str) -> Path:
    """Resolve rel to a path inside ROOT, restricted to editable Markdown areas."""
    rel = rel.strip("/\\")
    if not rel.endswith(".md"):
        raise ValueError("only .md files are editable here")
    if not rel.startswith(EDITABLE_MD_PREFIXES):
        raise ValueError("path not in an editable area")
    p = (ROOT / rel).resolve()
    try:
        p.relative_to(ROOT.resolve())
    except ValueError:
        raise ValueError("path escapes repo root")
    if not p.is_file():
        raise ValueError("file does not exist")
    return p


def list_editable_md():
    out = []
    for prefix in EDITABLE_MD_PREFIXES:
        base = ROOT / prefix
        if base.is_dir():
            for p in sorted(base.rglob("*.md")):
                out.append(str(p.relative_to(ROOT)).replace("\\", "/"))
        elif base.parent.is_dir():
            # Data-root prefixes can be directories or glob-like prefixes.
            for p in sorted(base.parent.glob(base.name + "*.md")):
                out.append(str(p.relative_to(ROOT)).replace("\\", "/"))
    return sorted(set(out))


# Knowledge tab — ordered file groups for the rendered Markdown view
KNOWLEDGE_FILES = {
    "persona": [
        data_rel("personas", "shubham.md"),
        data_rel("personas", "yash.md"),
    ],
    "style": [
        data_rel("style", "shubham-twitter-style.md"),
        data_rel("style", "yash-twitter-style.md"),
    ],
    "learnings": [
        data_rel("learnings", "content-playbook.md"),
        data_rel("learnings", "timing-playbook.md"),
        data_rel("learnings", "engagement-targets.md"),
    ],
    "guidelines": [
        "guidelines/target-posts.md",
        "guidelines/reply-playbook.md",
        "guidelines/profile-rubric.md",
        "guidelines/tagging-playbook.md",
        "guidelines/compose-playbook.md",
        "guidelines/format-playbooks/reply.md",
        "guidelines/format-playbooks/thread-reply.md",
        "guidelines/format-playbooks/quote.md",
        "guidelines/format-playbooks/original-tweet.md",
    ],
}


def api_knowledge():
    result = {}
    for section, paths in KNOWLEDGE_FILES.items():
        result[section] = []
        for rel in paths:
            p = ROOT / rel
            try:
                content = p.read_text(encoding="utf-8") if p.is_file() else "(file not yet created)"
            except Exception as e:
                content = f"(error reading file: {e})"
            result[section].append({"path": rel, "content": content})
    return result


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------

def read_csv(relpath):
    path = ROOT / relpath
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []
    return fieldnames, rows


def write_csv(relpath, fieldnames, rows):
    path = ROOT / relpath
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def update_csv_row(relpath, id_field, id_value, updates):
    fieldnames, rows = read_csv(relpath)
    for row in rows:
        if row.get(id_field) == id_value:
            row.update(updates)
            write_csv(relpath, fieldnames, rows)
            return row
    return None


def find_item(item_id):
    """Return (csv_relpath, id_field, item_type, row) for a reply or tweet id."""
    fieldnames, rows = read_csv(data_rel("data", "replies.csv"))
    for row in rows:
        if row.get("reply_id") == item_id:
            return data_rel("data", "replies.csv"), "reply_id", row.get("format") or "reply", row
    fieldnames, rows = read_csv(data_rel("data", "tweets.csv"))
    for row in rows:
        if row.get("tweet_id") == item_id:
            return data_rel("data", "tweets.csv"), "tweet_id", "tweet", row
    return None, None, None, None


# ---------------------------------------------------------------------------
# Drafts
# ---------------------------------------------------------------------------

def parse_drafted_at(value):
    try:
        # Normalize Z suffix for Python < 3.11, then ensure UTC-aware
        dt = datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def api_drafts():
    limits = read_limits()
    staleness_hours = limits.get("draft_staleness_hours", 12)
    now = datetime.datetime.now(datetime.timezone.utc)

    drafts = []
    drafts_dir = data_path("drafts")
    for path in sorted(drafts_dir.glob("*.md")):
        item_id = path.stem
        _, _, item_type, row = find_item(item_id)
        if row is None:
            continue  # not yet recorded in a CSV — shouldn't happen, skip defensively
        drafted_at = parse_drafted_at(row.get("drafted_at", ""))
        stale = None
        if drafted_at is not None:
            stale = (now - drafted_at) > datetime.timedelta(hours=staleness_hours)
        drafts.append({
            "id": item_id,
            "type": item_type,
            "status": row.get("status"),
            "row": row,
            "raw": path.read_text(encoding="utf-8"),
            "stale_age": stale,
        })
    return {"drafts": drafts}


def split_draft_body(text):
    """Split a draft file into (header, body, trailer) on '---' lines."""
    lines = text.splitlines()
    sep_indices = [i for i, l in enumerate(lines) if l.strip() == "---"]
    if len(sep_indices) < 2:
        return text, None, None
    a, b = sep_indices[0], sep_indices[1]
    header = "\n".join(lines[:a])
    body = "\n".join(lines[a + 1:b]).strip()
    trailer = "\n".join(lines[b + 1:])
    return header, body, trailer


def rewrite_draft_body(text, new_body):
    header, _, trailer = split_draft_body(text)
    if header is None:
        return text  # unrecognized template shape — leave untouched
    parts = [header.rstrip(), "", "---", new_body.strip(), "---"]
    if trailer.strip():
        parts += ["", trailer.strip()]
    return "\n".join(parts) + "\n"


def api_discard_draft(item_id, reason=None):
    csv_path, id_field, _, row = find_item(item_id)
    if row is None:
        raise ValueError("unknown draft id")
    update_csv_row(csv_path, id_field, item_id, {"status": "discarded"})

    src = data_path("drafts", f"{item_id}.md")
    dst_dir = data_path("drafts", "discarded")
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / f"{item_id}.md"

    content = src.read_text(encoding="utf-8")
    note = f"**Discarded**: user (dashboard), {datetime.datetime.now().isoformat(timespec='seconds')}"
    if reason:
        note += f" — {reason}"
    content = note + "\n\n" + content
    dst.write_text(content, encoding="utf-8")
    src.unlink()
    return {"ok": True}


def api_approve_draft(item_id, edited_text=None):
    csv_path, id_field, _, row = find_item(item_id)
    if row is None:
        raise ValueError("unknown draft id")

    draft_path = data_path("drafts", f"{item_id}.md")
    content = draft_path.read_text(encoding="utf-8")

    original = (row.get("draft_text") or "").strip()
    if edited_text is not None and edited_text.strip() != original:
        new_text = edited_text.strip()
        edit_summary = f"dashboard edit: {len(original)} -> {len(new_text)} chars"
        update_csv_row(csv_path, id_field, item_id, {
            "draft_text": new_text,
            "user_edited": "true",
            "edit_summary": edit_summary,
            "status": "edited",
        })
        draft_path.write_text(rewrite_draft_body(content, new_text), encoding="utf-8")
        return {"ok": True, "status": "edited", "edit_summary": edit_summary}

    update_csv_row(csv_path, id_field, item_id, {"status": "approved"})
    return {"ok": True, "status": "approved"}


# ---------------------------------------------------------------------------
# Insights
# ---------------------------------------------------------------------------

def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def funnel_counts(relpath, statuses):
    _, rows = read_csv(relpath)
    counts = {s: 0 for s in statuses}
    for row in rows:
        status = row.get("status", "")
        if status in counts:
            counts[status] += 1
    reviewed = sum(1 for row in rows if row.get("status") == "sent" and (row.get("reviewed_at") or "").strip())
    counts["reviewed"] = reviewed
    return counts


def edit_rate():
    total_sent = 0
    edited = 0
    for relpath in (data_rel("data", "replies.csv"), data_rel("data", "tweets.csv")):
        _, rows = read_csv(relpath)
        for row in rows:
            if row.get("status") == "sent":
                total_sent += 1
                if (row.get("user_edited") or "").strip().lower() == "true":
                    edited += 1
    return {"sent": total_sent, "edited": edited, "rate": (edited / total_sent) if total_sent else None}


def latest_metrics_by_item():
    _, rows = read_csv(data_rel("data", "metrics.csv"))
    latest = {}
    for row in rows:
        item_id = row.get("item_id")
        captured = row.get("captured_at", "")
        if item_id not in latest or captured > latest[item_id].get("captured_at", ""):
            latest[item_id] = row
    return latest


def performance_breakdown():
    metrics = latest_metrics_by_item()

    by_archetype = {}
    _, replies = read_csv(data_rel("data", "replies.csv"))
    for row in replies:
        m = metrics.get(row.get("reply_id"))
        if not m:
            continue
        rate = to_float(m.get("engagement_rate"))
        if rate is None:
            continue
        key = row.get("reply_archetype") or "(unset)"
        by_archetype.setdefault(key, []).append(rate)

    by_content_type = {}
    _, tweets = read_csv(data_rel("data", "tweets.csv"))
    for row in tweets:
        m = metrics.get(row.get("tweet_id"))
        if not m:
            continue
        rate = to_float(m.get("engagement_rate"))
        if rate is None:
            continue
        key = row.get("content_type") or "(unset)"
        by_content_type.setdefault(key, []).append(rate)

    def summarize(d):
        return {k: {"n": len(v), "avg_engagement_rate": sum(v) / len(v)} for k, v in d.items()}

    return {"by_reply_archetype": summarize(by_archetype), "by_content_type": summarize(by_content_type)}


def api_insights():
    return {
        "funnel": {
            "replies": funnel_counts(data_rel("data", "replies.csv"),
                                      ["drafted", "approved", "edited", "discarded", "sent"]),
            "tweets": funnel_counts(data_rel("data", "tweets.csv"),
                                     ["drafted", "approved", "edited", "discarded", "sent"]),
        },
        "edit_rate": edit_rate(),
        "performance": performance_breakdown(),
        "profiles": read_csv(data_rel("data", "profiles.csv"))[1],
    }


# ---------------------------------------------------------------------------
# Incidents / lockout
# ---------------------------------------------------------------------------

def is_lockout_row(row):
    triggered = (row.get("lockout_triggered") or "").strip().lower() in ("true", "1", "yes")
    acknowledged = (row.get("acknowledged_at") or "").strip()
    return triggered and not acknowledged


def api_incidents():
    _, rows = read_csv(data_rel("data", "incidents.csv"))
    locked_out = any(is_lockout_row(row) for row in rows)
    return {"incidents": rows, "locked_out": locked_out}


def api_clear_lockout():
    fieldnames, rows = read_csv(data_rel("data", "incidents.csv"))
    now = datetime.datetime.now().isoformat(timespec="seconds")
    changed = False
    for row in rows:
        if is_lockout_row(row):
            row["acknowledged_at"] = now
            changed = True
    if changed:
        write_csv(data_rel("data", "incidents.csv"), fieldnames, rows)
    return {"ok": True, "cleared": changed}


# ---------------------------------------------------------------------------
# Config: limits.yaml / metrics.yaml / active persona (AGENTS.md §0)
# ---------------------------------------------------------------------------

def read_limits():
    text = data_path("config", "limits.yaml").read_text(encoding="utf-8")
    values = {}
    for m in re.finditer(r"^(\w+):\s*([0-9]+)", text, re.M):
        values[m.group(1)] = int(m.group(2))
    return values


def write_limits(updates):
    path = data_path("config", "limits.yaml")
    text = path.read_text(encoding="utf-8")
    for key, val in updates.items():
        if not isinstance(val, int) or isinstance(val, bool):
            raise ValueError(f"limits.{key} must be an integer")
        text = re.sub(rf"^({re.escape(key)}:\s*)[0-9]+", rf"\g<1>{val}", text, flags=re.M)
    path.write_text(text, encoding="utf-8")


def read_metrics_yaml():
    text = data_path("config", "metrics.yaml").read_text(encoding="utf-8")
    result = {}
    for m in re.finditer(r"^\s*(\w+):\s*\[(.*?)\]", text, re.M):
        key = m.group(1)
        items = [x.strip() for x in m.group(2).split(",") if x.strip()]
        result[key] = items
    return result


def write_metrics_yaml(updates):
    path = data_path("config", "metrics.yaml")
    text = path.read_text(encoding="utf-8")
    for key, items in updates.items():
        if not isinstance(items, list):
            raise ValueError(f"metrics.{key} must be a list")
        newlist = ", ".join(str(i) for i in items)
        text = re.sub(rf"^(\s*{re.escape(key)}:\s*)\[.*?\]", rf"\g<1>[{newlist}]", text, flags=re.M)
    path.write_text(text, encoding="utf-8")


def read_active_persona():
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    persona = re.search(r"^persona:\s*(\w+)", text, re.M)
    tagging = re.search(r"^tagging:\s*(on|off)", text, re.M)
    return {
        "persona": persona.group(1) if persona else None,
        "tagging": tagging.group(1) if tagging else None,
    }


def write_active_persona(persona=None, tagging=None):
    path = ROOT / "AGENTS.md"
    text = path.read_text(encoding="utf-8")
    if persona is not None:
        if persona not in ("shubham", "yash"):
            raise ValueError("unknown persona")
        text = re.sub(r"^(persona:\s*)\w+", rf"\g<1>{persona}", text, count=1, flags=re.M)
    if tagging is not None:
        if tagging not in ("on", "off"):
            raise ValueError("tagging must be 'on' or 'off'")
        text = re.sub(r"^(tagging:\s*)(on|off)", rf"\g<1>{tagging}", text, count=1, flags=re.M)
    path.write_text(text, encoding="utf-8")
    return read_active_persona()


def list_personas():
    return sorted(p.stem for p in data_path("personas").glob("*.md"))


# ---------------------------------------------------------------------------
# Editable Markdown files
# ---------------------------------------------------------------------------

def read_md_file(rel):
    return safe_md_path(rel).read_text(encoding="utf-8")


def write_md_file(rel, content):
    path = safe_md_path(rel)
    # Keep the last_updated stamp honest when the dashboard edits a file.
    today = datetime.date.today().isoformat()
    if re.search(r"^last_updated:\s*\S+", content, re.M):
        content = re.sub(r"^(last_updated:\s*)\S+", rf"\g<1>{today}", content, count=1, flags=re.M)
    path.write_text(content, encoding="utf-8")
    return {"ok": True, "last_updated": today}


# ---------------------------------------------------------------------------
# Run control (launch a mode session in a new terminal — see dashboard/README.md)
# ---------------------------------------------------------------------------

RUN_STATE_PATH = Path(__file__).resolve().parent / "run-state.json"
RUN_CONFIG_PATH = Path(__file__).resolve().parent / "run-config.json"


def read_run_config():
    if RUN_CONFIG_PATH.is_file():
        return json.loads(RUN_CONFIG_PATH.read_text(encoding="utf-8"))
    return {"agent_command": "codex"}


def read_run_state():
    if RUN_STATE_PATH.is_file():
        return json.loads(RUN_STATE_PATH.read_text(encoding="utf-8"))
    return {"last_launch": None}


def write_run_state(state):
    RUN_STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def api_run_launch(mode, persona=None, tagging=False):
    if mode not in VALID_MODES:
        raise ValueError(f"unknown mode: {mode}")
    agent_command = APP_CONFIG.get("agent_command", read_run_config().get("agent_command", "codex"))

    prompt = mode
    if persona:
        prompt += f" --persona {persona}"
    if tagging:
        if mode != "scroll":
            raise ValueError("--tagging is only valid for scroll mode")
        prompt += " --tagging"

    # Opens a new PowerShell window in twitter-agent/ running the agent CLI.
    # Streaming output back into this dashboard would need a pty, which the stdlib
    # doesn't provide — see dashboard/README.md "Known limitations".
    # Single-quote ROOT and prompt for PowerShell (no double-quote escaping needed;
    # prompt only contains alphanum/hyphens so single quotes are safe).
    run_cmd = f"Set-Location -LiteralPath '{ROOT}'; {agent_command} '{prompt}'"
    subprocess.Popen(
        f'start "Twitter Agent" powershell -NoExit -Command "{run_cmd}"',
        shell=True,
    )

    state = {"last_launch": {
        "mode": mode, "persona": persona, "tagging": bool(tagging),
        "prompt": prompt, "started_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }}
    write_run_state(state)
    return state


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    server_version = "TwitterAgentDashboard/1.0"

    def log_message(self, fmt, *args):
        pass  # quiet — this is a local single-user tool

    def _send_json(self, obj, status=200):
        body = json.dumps(obj, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _serve_static(self, relname):
        if not relname:
            relname = "index.html"
        path = (STATIC_DIR / relname).resolve()
        try:
            path.relative_to(STATIC_DIR.resolve())
        except ValueError:
            return self._send_json({"error": "not found"}, 404)
        if not path.is_file():
            return self._send_json({"error": "not found"}, 404)
        ctype, _ = mimetypes.guess_type(str(path))
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        try:
            if path in ("/", "/index.html"):
                return self._serve_static("index.html")
            if path.startswith("/static/"):
                return self._serve_static(path[len("/static/"):])
            if path == "/api/drafts":
                return self._send_json(api_drafts())
            if path == "/api/insights":
                return self._send_json(api_insights())
            if path == "/api/incidents":
                return self._send_json(api_incidents())
            if path == "/api/config/limits":
                return self._send_json(read_limits())
            if path == "/api/config/metrics":
                return self._send_json(read_metrics_yaml())
            if path == "/api/config/persona":
                return self._send_json({"active": read_active_persona(), "available": list_personas()})
            if path == "/api/knowledge":
                return self._send_json(api_knowledge())
            if path == "/api/files":
                return self._send_json({"files": list_editable_md()})
            if path == "/api/file":
                rel = (query.get("path") or [""])[0]
                return self._send_json({"path": rel, "content": read_md_file(rel)})
            if path == "/api/run/state":
                return self._send_json(read_run_state())
            return self._send_json({"error": "not found"}, 404)
        except Exception as e:  # noqa: BLE001 - surface as JSON error to the UI
            return self._send_json({"error": str(e)}, 400)

    def do_POST(self):
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path
        try:
            body = self._read_json()
            m = re.match(r"^/api/drafts/([^/]+)/(discard|approve)$", path)
            if m:
                item_id, action = m.group(1), m.group(2)
                if action == "discard":
                    return self._send_json(api_discard_draft(item_id, body.get("reason")))
                return self._send_json(api_approve_draft(item_id, body.get("edited_text")))
            if path == "/api/incidents/clear-lockout":
                return self._send_json(api_clear_lockout())
            if path == "/api/config/limits":
                write_limits(body)
                return self._send_json(read_limits())
            if path == "/api/config/metrics":
                write_metrics_yaml(body)
                return self._send_json(read_metrics_yaml())
            if path == "/api/config/persona":
                return self._send_json(write_active_persona(body.get("persona"), body.get("tagging")))
            if path == "/api/file":
                return self._send_json(write_md_file(body["path"], body["content"]))
            if path == "/api/run/launch":
                return self._send_json(api_run_launch(body.get("mode"), body.get("persona"), body.get("tagging", False)))
            return self._send_json({"error": "not found"}, 404)
        except Exception as e:  # noqa: BLE001 - surface as JSON error to the UI
            return self._send_json({"error": str(e)}, 400)


def main():
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Twitter Agent Dashboard — http://localhost:{PORT}")
    print(f"Serving files from: {ROOT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()






