"""DashboardStore — the composition root over the cohesive dashboard services.

The former god-object was split (see tasks/plans/04) into focused modules:

    PathResolver  — path safety, listings, editable-markdown IO   (paths.py)
    ConfigStore   — limits / metrics / persona get + set          (config_store.py)
    DraftQueue    — the draft queue and approve/discard flow       (draft_queue.py)
    InsightsView  — funnel, edit rate, performance breakdown       (insights.py)
    IncidentLog   — incidents table + send-lockout ack             (incidents.py)
    RunLauncher   — launch an agent mode + run-state               (run_launcher.py)

This module wires them together from a shared ``PathResolver``. ``api.py`` and
``server.py`` construct one ``DashboardStore`` and call the owning service
(``store.config.read_limits()``, ``store.drafts.api_drafts()``, ...) rather than a
single wide interface. ``read_simple_yaml`` is re-exported for backward
compatibility.
"""

from __future__ import annotations

from pathlib import Path

from .config_store import ConfigStore
from .draft_queue import DraftQueue
from .incidents import IncidentLog
from .insights import InsightsView
from .paths import PathResolver, read_simple_yaml
from .run_launcher import VALID_MODES, RunLauncher

__all__ = ["DashboardStore", "read_simple_yaml", "VALID_MODES"]


class DashboardStore:
    def __init__(self, root: Path | None = None) -> None:
        self.paths = PathResolver(root)
        self.config = ConfigStore(self.paths)
        self.drafts = DraftQueue(self.paths, self.config)
        self.insights = InsightsView(self.paths)
        self.incidents = IncidentLog(self.paths)
        self.runner = RunLauncher(self.paths)

        # Frequently-read attributes kept on the root for convenience/back-compat.
        self.root = self.paths.root
        self.app_config = self.paths.app_config
