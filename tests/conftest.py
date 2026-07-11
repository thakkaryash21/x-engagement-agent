"""Shared fixtures: a minimal on-disk repo so store tests never touch real data."""

from __future__ import annotations

import csv
import math
import re
import zlib
from pathlib import Path
from typing import Sequence

import pytest

from dashboard import tables
from dashboard.file_store import DashboardStore


class FakeEmbedder:
    """Deterministic, offline embedder for context tests.

    Hashes each token into a fixed-width bag-of-words vector and L2-normalizes,
    so texts that share words land close (cosine ~ shared-token overlap) and
    unrelated texts land far. No model download, fully reproducible within a
    run — exactly why ContextStore takes the embedder as a constructor arg.
    """

    def __init__(self, dim: int = 32) -> None:
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            vector = [0.0] * self._dim
            for token in re.findall(r"[a-z0-9]+", (text or "").lower()):
                vector[zlib.crc32(token.encode()) % self._dim] += 1.0
            norm = math.sqrt(sum(component * component for component in vector))
            if norm:
                vector = [component / norm for component in vector]
            out.append(vector)
        return out


@pytest.fixture
def fake_embedder() -> FakeEmbedder:
    return FakeEmbedder()

APP_YAML = "data_root: data\nagent_command: codex\ndashboard_port: 8787\n"

LIMITS_YAML = """\
# limits
max_drafts_per_session: 15
session_time_limit_minutes: 45
max_sends_per_day: 8 # inline comment
draft_staleness_hours: 12
"""

METRICS_YAML = """\
# metrics
capture:
  layer1: [views, likes]
optimize:
  reply:       [profile_visits, likes]
"""

AGENTS_MD = """\
# AGENTS.md

```yaml
persona: founder-template # comment
tagging: off            # on | off
```

body.
"""


def _write_csv(path: Path, columns, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(columns))
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in columns})


@pytest.fixture
def temp_store(tmp_path: Path) -> DashboardStore:
    root = tmp_path
    (root / "config").mkdir()
    (root / "config" / "app.yaml").write_text(APP_YAML, encoding="utf-8")
    (root / "config" / "limits.yaml").write_text(LIMITS_YAML, encoding="utf-8")
    (root / "config" / "metrics.yaml").write_text(METRICS_YAML, encoding="utf-8")
    (root / "AGENTS.md").write_text(AGENTS_MD, encoding="utf-8")

    for sub in ("personas", "style", "learnings", "writing", "csv", "drafts"):
        (root / "data" / sub).mkdir(parents=True)
    (root / "guidelines").mkdir()
    (root / "data" / "personas" / "founder-template.md").write_text("# p\n", encoding="utf-8")
    (root / "data" / "personas" / "shubham.md").write_text("# p\n", encoding="utf-8")

    csv_dir = root / "data" / "csv"
    _write_csv(csv_dir / "replies.csv", tables.COLUMNS_REPLIES, [
        {"reply_id": "r1", "format": "reply", "status": "sent", "user_edited": "true",
         "reply_archetype": "sharp question", "drafted_at": "2026-06-01T10:00:00",
         "draft_text": "hello world", "reviewed_at": "2026-06-02T10:00:00"},
        {"reply_id": "r2", "format": "reply", "status": "drafted",
         "reply_archetype": "story", "drafted_at": "2026-06-05T10:00:00", "draft_text": "draft two"},
    ])
    _write_csv(csv_dir / "tweets.csv", tables.COLUMNS_TWEETS, [
        {"tweet_id": "t1", "content_type": "insight", "status": "sent", "user_edited": "false",
         "drafted_at": "2026-06-01T10:00:00", "draft_text": "a tweet"},
    ])
    _write_csv(csv_dir / "metrics.csv", tables.COLUMNS_METRICS, [
        {"item_id": "r1", "captured_at": "2026-06-03T00:00:00", "engagement_rate": "0.10"},
        {"item_id": "r1", "captured_at": "2026-06-04T00:00:00", "engagement_rate": "0.20"},
        {"item_id": "t1", "captured_at": "2026-06-03T00:00:00", "engagement_rate": "0.05"},
    ])
    _write_csv(csv_dir / "profiles.csv", tables.COLUMNS_PROFILES, [
        {"handle": "@a", "times_engaged": "1"},
    ])
    _write_csv(csv_dir / "incidents.csv", tables.COLUMNS_INCIDENTS, [
        {"incident_id": "i1", "lockout_triggered": "true", "acknowledged_at": ""},
    ])
    _write_csv(csv_dir / "learn-progress.csv", tables.COLUMNS_LEARN_PROGRESS, [])

    return DashboardStore(root)
