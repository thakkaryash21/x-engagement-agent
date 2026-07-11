from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .file_store import DashboardStore


class FileUpdate(BaseModel):
    path: str
    content: str


class DraftAction(BaseModel):
    edited_text: str | None = None
    reason: str | None = None


class RunLaunch(BaseModel):
    mode: str
    persona: str | None = None
    tagging: bool = False


def api_error(exc: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


def create_app(root: Path | None = None) -> FastAPI:
    store = DashboardStore(root)
    app = FastAPI(title="X Engagement Agent Dashboard")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/drafts")
    def drafts() -> dict[str, Any]:
        return store.drafts.api_drafts()

    @app.post("/api/drafts/{item_id}/approve")
    def approve_draft(item_id: str, body: DraftAction) -> dict[str, Any]:
        try:
            return store.drafts.approve_draft(item_id, body.edited_text)
        except Exception as exc:
            raise api_error(exc) from exc

    @app.post("/api/drafts/{item_id}/discard")
    def discard_draft(item_id: str, body: DraftAction) -> dict[str, Any]:
        try:
            return store.drafts.discard_draft(item_id, body.reason)
        except Exception as exc:
            raise api_error(exc) from exc

    @app.get("/api/insights")
    def insights() -> dict[str, Any]:
        return store.insights.api_insights()

    @app.get("/api/incidents")
    def incidents() -> dict[str, Any]:
        return store.incidents.api_incidents()

    @app.post("/api/incidents/clear-lockout")
    def clear_lockout() -> dict[str, Any]:
        return store.incidents.clear_lockout()

    @app.get("/api/config/limits")
    def limits() -> dict[str, int]:
        return store.config.read_limits()

    @app.post("/api/config/limits")
    def update_limits(body: dict[str, Any]) -> dict[str, int]:
        try:
            return store.config.write_limits(body)
        except Exception as exc:
            raise api_error(exc) from exc

    @app.get("/api/config/metrics")
    def metrics() -> dict[str, list[str]]:
        return store.config.read_metrics_yaml()

    @app.post("/api/config/metrics")
    def update_metrics(body: dict[str, Any]) -> dict[str, list[str]]:
        try:
            return store.config.write_metrics_yaml(body)
        except Exception as exc:
            raise api_error(exc) from exc

    @app.get("/api/config/persona")
    def persona() -> dict[str, Any]:
        return {"active": store.config.active_persona(), "available": store.config.list_personas()}

    @app.post("/api/config/persona")
    def update_persona(body: dict[str, Any]) -> dict[str, str | None]:
        try:
            return store.config.write_active_persona(body.get("persona"), body.get("tagging"))
        except Exception as exc:
            raise api_error(exc) from exc

    @app.get("/api/knowledge")
    def knowledge() -> dict[str, Any]:
        return store.paths.api_knowledge()

    @app.get("/api/files")
    def files() -> dict[str, list[str]]:
        return {"files": store.paths.list_editable_md()}

    @app.get("/api/file")
    def read_file(path: str) -> dict[str, str]:
        try:
            return {"path": path, "content": store.paths.read_md_file(path)}
        except Exception as exc:
            raise api_error(exc) from exc

    @app.post("/api/file")
    def write_file(body: FileUpdate) -> dict[str, Any]:
        try:
            return store.paths.write_md_file(body.path, body.content)
        except Exception as exc:
            raise api_error(exc) from exc

    @app.get("/api/run/state")
    def run_state() -> dict[str, Any]:
        return store.runner.read_run_state()

    @app.post("/api/run/launch")
    def run_launch(body: RunLaunch) -> dict[str, Any]:
        try:
            return store.runner.launch_run(body.mode, body.persona, body.tagging)
        except Exception as exc:
            raise api_error(exc) from exc

    static_dir = store.root / "dashboard" / "frontend" / "dist"
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="dashboard")

    return app


app = create_app()

