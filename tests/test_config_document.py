"""Plan 1 — ConfigDocument field editor: round-trip + format preservation."""

from __future__ import annotations

from pathlib import Path

import pytest

from dashboard.config_document import (
    ConfigDocument,
    FrontmatterAdapter,
    ListYamlAdapter,
    ScalarYamlAdapter,
)

LIMITS = """\
# Twitter Agent — operating limits
# comment block

max_drafts_per_session: 15
session_time_limit_minutes: 45
max_sends_per_day: 8 # human-approved sends, enforced in send mode
min_seconds_between_actions: 2
draft_staleness_hours: 12 # stale-draft flag threshold
"""

METRICS = """\
# metrics config

capture:
  layer1: [views, likes, replies]
  layer2: [impressions, new_follows]

optimize:
  reply:       [profile_visits, new_follows, likes]
  tweet:       [impressions, engagement_rate, new_follows]
"""

FRONTMATTER = """\
# AGENTS.md

```yaml
persona: founder-template # set to a file in data/personas/
tagging: off            # on | off
```

body text stays.
"""


def _doc(tmp_path: Path, name: str, text: str, adapter) -> ConfigDocument:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return ConfigDocument(path, adapter)


# --- ScalarYamlAdapter --------------------------------------------------------

def test_scalar_read(tmp_path):
    doc = _doc(tmp_path, "limits.yaml", LIMITS, ScalarYamlAdapter())
    data = doc.as_dict()
    assert data["max_drafts_per_session"] == 15
    assert data["draft_staleness_hours"] == 12
    assert isinstance(data["max_sends_per_day"], int)


def test_scalar_set_preserves_comments_and_order(tmp_path):
    doc = _doc(tmp_path, "limits.yaml", LIMITS, ScalarYamlAdapter())
    doc.set("max_drafts_per_session", 20)
    text = doc.path.read_text(encoding="utf-8")
    # comment header + blank line survive
    assert text.startswith("# Twitter Agent — operating limits\n# comment block\n\n")
    assert "max_drafts_per_session: 20" in text
    # inline comment on an untouched line survives
    assert "max_sends_per_day: 8 # human-approved sends" in text
    # key order preserved
    keys = [line.split(":")[0] for line in text.splitlines() if ":" in line and not line.startswith("#")]
    assert keys[0] == "max_drafts_per_session"
    assert keys[-1] == "draft_staleness_hours"


def test_scalar_set_preserves_inline_comment_on_edited_line(tmp_path):
    doc = _doc(tmp_path, "limits.yaml", LIMITS, ScalarYamlAdapter())
    doc.set("draft_staleness_hours", 6)
    text = doc.path.read_text(encoding="utf-8")
    assert "draft_staleness_hours: 6 # stale-draft flag threshold" in text


def test_scalar_set_many_single_write(tmp_path):
    doc = _doc(tmp_path, "limits.yaml", LIMITS, ScalarYamlAdapter())
    doc.set_many({"max_drafts_per_session": 1, "session_time_limit_minutes": 2})
    data = doc.as_dict()
    assert data["max_drafts_per_session"] == 1
    assert data["session_time_limit_minutes"] == 2


# --- ListYamlAdapter ----------------------------------------------------------

def test_list_read_nested_keys(tmp_path):
    doc = _doc(tmp_path, "metrics.yaml", METRICS, ListYamlAdapter())
    data = doc.as_dict()
    assert data["layer1"] == ["views", "likes", "replies"]
    assert data["reply"] == ["profile_visits", "new_follows", "likes"]


def test_list_set_preserves_indentation_and_comments(tmp_path):
    doc = _doc(tmp_path, "metrics.yaml", METRICS, ListYamlAdapter())
    doc.set("layer1", ["views", "bookmarks"])
    text = doc.path.read_text(encoding="utf-8")
    assert "  layer1: [views, bookmarks]" in text
    assert text.startswith("# metrics config\n")
    assert "capture:" in text and "optimize:" in text


# --- FrontmatterAdapter -------------------------------------------------------

def test_frontmatter_read(tmp_path):
    doc = _doc(tmp_path, "AGENTS.md", FRONTMATTER, FrontmatterAdapter({"persona": r"[\w-]+", "tagging": r"on|off"}))
    data = doc.as_dict()
    assert data["persona"] == "founder-template"
    assert data["tagging"] == "off"


def test_frontmatter_set_preserves_fence_and_body(tmp_path):
    adapter = FrontmatterAdapter({"persona": r"[\w-]+", "tagging": r"on|off"})
    doc = _doc(tmp_path, "AGENTS.md", FRONTMATTER, adapter)
    doc.set("persona", "shubham")
    doc.set("tagging", "on")
    text = doc.path.read_text(encoding="utf-8")
    assert "persona: shubham # set to a file in data/personas/" in text
    assert "tagging: on            # on | off" in text
    assert "```yaml" in text and "body text stays." in text


def test_frontmatter_missing_key_reads_none(tmp_path):
    doc = _doc(tmp_path, "AGENTS.md", "no fields here\n", FrontmatterAdapter({"persona": r"[\w-]+"}))
    assert doc.as_dict()["persona"] is None
