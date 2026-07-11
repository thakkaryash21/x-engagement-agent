"""context_cli — the runtime bridge over ContextMemory (Plan 08 fix 1).

This is the wiring the earlier build lacked: the modes (`scroll` §2.4b, `learn`
seeding, `review`) invoke this CLI as a shell command instead of naming Python
methods abstractly. It constructs ``ContextMemory`` directly — no running-server
dependency — so every call is auditable in the agent transcript.

JSON in / JSON out. Subcommands:

- ``search``          — the content read (``retrieve_content``); query + scope +
                        gap_type in, ranked chunks out.
- ``write-back``      — the unified write-back (§5.5); findings (+ reply_id, gaps,
                        queries, shaped_draft) in on stdin, a summary out
                        (promoted / merged / brief_only / evidence / dossiers /
                        brief paths).
- ``reflect``         — consolidation (§5.5.1); scope (+ subject) in, insight out.
- ``style-exemplars`` — the diversity-selected voice read; persona + k in.
- ``reindex``         — rebuild the vector index from the authoritative chunk files.

Usage (from the repo root)::

    echo '{"findings":[...],"reply_id":"r1"}' \\
        | python -m dashboard.context_cli write-back --context-dir data/context
    python -m dashboard.context_cli search --query "acme pricing" --scope world
    python -m dashboard.context_cli reflect --scope world --subject acme

``--embedder`` selects the vector backend: ``fastembed`` (default, runtime) or
``hash`` (deterministic + offline, used by the end-to-end test so it needs no
model download). Input JSON may come from stdin or ``--json '<...>'``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from dashboard.context_memory import ContextMemory
from dashboard.context_store import ContextStore, FastEmbedEmbedder, HashEmbedder


def _build_memory(context_dir: str, embedder_name: str) -> ContextMemory:
    embedder = HashEmbedder() if embedder_name == "hash" else FastEmbedEmbedder()
    store = ContextStore(context_dir, embedder=embedder)
    return ContextMemory(store)


def _read_payload(args: argparse.Namespace) -> dict[str, Any]:
    """Load the JSON request from ``--json`` or stdin (empty = {})."""
    raw = args.json
    if raw is None and not sys.stdin.isatty():
        raw = sys.stdin.read()
    raw = (raw or "").strip()
    if not raw:
        return {}
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("input JSON must be an object")
    return payload


def _emit(obj: Any) -> None:
    json.dump(obj, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def _cmd_search(memory: ContextMemory, args: argparse.Namespace) -> Any:
    payload = _read_payload(args)
    query = args.query if args.query is not None else payload.get("query", "")
    scope = args.scope or payload.get("scope")
    gap_type = args.gap_type or payload.get("gap_type")
    persona = args.persona or payload.get("persona")
    k = args.k if args.k is not None else int(payload.get("k", 8))
    return memory.retrieve_content(query, scope=scope, gap_type=gap_type, k=k, persona=persona)


def _cmd_write_back(memory: ContextMemory, args: argparse.Namespace) -> Any:
    payload = _read_payload(args)
    findings = payload.get("findings", [])
    if not isinstance(findings, list):
        raise ValueError("`findings` must be a list")
    return memory.write_back(
        findings,
        reply_id=args.reply_id or payload.get("reply_id"),
        gaps=payload.get("gaps"),
        queries=payload.get("queries"),
        shaped_draft=payload.get("shaped_draft"),
    )


def _cmd_reflect(memory: ContextMemory, args: argparse.Namespace) -> Any:
    payload = _read_payload(args)
    scope = args.scope or payload.get("scope") or "world"
    subject = args.subject or payload.get("subject")
    return memory.reflect(scope, subject=subject)


def _cmd_style_exemplars(memory: ContextMemory, args: argparse.Namespace) -> Any:
    payload = _read_payload(args)
    persona = args.persona or payload.get("persona") or ""
    k = args.k if args.k is not None else int(payload.get("k", 5))
    return memory.style_exemplars(persona, k=k)


def _cmd_reindex(memory: ContextMemory, args: argparse.Namespace) -> Any:
    reindexed = memory.store.reindex()
    return {"reindexed": reindexed, "skipped": memory.store.reindex_skipped}


_COMMANDS = {
    "search": _cmd_search,
    "write-back": _cmd_write_back,
    "reflect": _cmd_reflect,
    "style-exemplars": _cmd_style_exemplars,
    "reindex": _cmd_reindex,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="context_cli", description=__doc__)
    parser.add_argument("command", choices=sorted(_COMMANDS))
    parser.add_argument("--context-dir", default="data/context",
                        help="root of the context stores (default: data/context)")
    parser.add_argument("--embedder", choices=("fastembed", "hash"), default="fastembed",
                        help="vector backend; 'hash' is deterministic + offline")
    parser.add_argument("--json", default=None, help="inline JSON request (else read stdin)")
    parser.add_argument("--query", default=None)
    parser.add_argument("--scope", default=None, choices=("world", "self", "both"))
    parser.add_argument("--gap-type", dest="gap_type", default=None)
    parser.add_argument("--subject", default=None)
    parser.add_argument("--persona", default=None)
    parser.add_argument("--reply-id", dest="reply_id", default=None)
    parser.add_argument("--k", type=int, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    scope = None if args.scope == "both" else args.scope
    args.scope = scope
    Path(args.context_dir).mkdir(parents=True, exist_ok=True)
    memory = _build_memory(args.context_dir, args.embedder)
    try:
        _emit(_COMMANDS[args.command](memory, args))
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"context_cli error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
