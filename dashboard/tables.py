"""The executable schema owner for every CSV in ``data/csv/``.

Each CSV had its column names spread as bare string literals across the
aggregation methods in ``file_store.py`` (and duplicated in prose). A header
change was a literal-hunt, not a migration. This module declares each table's
column set + id field once (``TableSpec``), exposes the ``status`` enum once
(``STATUS``), and routes row IO through ``Table``. Aggregation logic references
these names instead of raw literals.

Scope guard: this is a *schema owner*, not an ORM. ``Table`` is a thin typed
accessor over ``list[dict[str, str]]`` — no query DSL.

``tests/test_tables.py::test_specs_match_live_headers`` asserts each spec equals
the live ``data/csv/*.csv`` header; that is the anti-drift guard.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # avoid a runtime import cycle; any object with data_path works
    from .paths import PathResolver


# The draft/send lifecycle status enum — one home. `funnel_counts` and the
# insights funnel share this; `reviewed` is a derived count, not a status value.
STATUS = ["drafted", "approved", "edited", "discarded", "sent"]


# --- Canonical column sets (order matters; these ARE the CSV headers) ----------

COLUMNS_REPLIES = (
    "reply_id", "drafted_at", "persona", "format", "target_tweet_url",
    "target_tweet_summary", "thread_position", "target_author_handle",
    "target_author_category", "target_follower_tier", "tweet_topic",
    "tweet_format", "reply_archetype", "tagging_mode", "tagged_users",
    "draft_text", "final_text", "user_edited", "edit_summary", "status",
    "sent_at", "sent_day_of_week", "sent_hour_local",
    "persona_follower_count_at_send", "target_tweet_views_at_draft",
    "reply_rank", "review_due", "reviewed_at",
)

COLUMNS_TWEETS = (
    "tweet_id", "drafted_at", "persona", "topic", "content_type", "hook_type",
    "draft_text", "final_text", "user_edited", "edit_summary", "status",
    "sent_at", "sent_day_of_week", "sent_hour_local", "review_due", "reviewed_at",
)

COLUMNS_METRICS = (
    "item_id", "item_type", "captured_at", "days_since_sent", "views_l1",
    "likes_l1", "replies_l1", "reposts_l1", "quotes_l1", "bookmarks_l1",
    "panel_available", "impressions_l2", "detail_expands_l2", "profile_visits_l2",
    "link_clicks_l2", "new_follows_l2", "engagement_rate", "author_liked",
    "author_replied", "author_reposted", "follower_count_at_capture",
    "notable_engagers", "target_tweet_views_at_capture", "notes",
)

COLUMNS_PROFILES = (
    "handle", "display_name", "first_seen", "last_updated", "category",
    "follower_count", "follower_tier", "role_clout", "audience_activity",
    "geography", "relevance", "credibility", "relationship", "bio_summary",
    "notes", "times_engaged", "engagement_outcomes",
)

COLUMNS_INCIDENTS = (
    "incident_id", "occurred_at", "persona", "mode", "type", "description",
    "session_action", "lockout_triggered", "acknowledged_at", "notes",
)

COLUMNS_LEARN_PROGRESS = (
    "persona", "section", "status", "direction", "last_processed_at",
    "last_processed_item_url", "items_processed", "session_count", "notes",
)

COLUMNS_CONTEXT_PROVENANCE = (
    "reply_id", "context_used", "gap_type", "n_lookups", "source_types",
    "dossier_slugs", "scope_blend",
)


@dataclass(frozen=True)
class TableSpec:
    """A CSV's declared columns + id field, keyed to a data-root-relative path."""

    relpath: str  # relative to the data root, e.g. "csv/replies.csv"
    columns: tuple[str, ...]
    id_field: str


REPLIES = TableSpec("csv/replies.csv", COLUMNS_REPLIES, "reply_id")
TWEETS = TableSpec("csv/tweets.csv", COLUMNS_TWEETS, "tweet_id")
METRICS = TableSpec("csv/metrics.csv", COLUMNS_METRICS, "item_id")
PROFILES = TableSpec("csv/profiles.csv", COLUMNS_PROFILES, "handle")
INCIDENTS = TableSpec("csv/incidents.csv", COLUMNS_INCIDENTS, "incident_id")
LEARN_PROGRESS = TableSpec("csv/learn-progress.csv", COLUMNS_LEARN_PROGRESS, "persona")
CONTEXT_PROVENANCE = TableSpec(
    "csv/context-provenance.csv", COLUMNS_CONTEXT_PROVENANCE, "reply_id"
)

ALL_SPECS = (
    REPLIES, TWEETS, METRICS, PROFILES, INCIDENTS, LEARN_PROGRESS,
    CONTEXT_PROVENANCE,
)


class Table:
    """A thin typed accessor binding a ``TableSpec`` to a store for row IO."""

    def __init__(self, store: "PathResolver", spec: TableSpec) -> None:
        self.store = store
        self.spec = spec

    @property
    def id_field(self) -> str:
        return self.spec.id_field

    def path(self):
        return self.store.data_path(*self.spec.relpath.split("/"))

    def read(self) -> tuple[list[str], list[dict[str, str]]]:
        with self.path().open(newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            rows = list(reader)
            return reader.fieldnames or [], rows

    def rows(self) -> list[dict[str, str]]:
        return self.read()[1]

    def write(self, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
        with self.path().open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def update(self, id_value: str, updates: dict[str, str]) -> dict[str, str] | None:
        fieldnames, rows = self.read()
        for row in rows:
            if row.get(self.spec.id_field) == id_value:
                row.update(updates)
                self.write(fieldnames, rows)
                return row
        return None

    def append(self, row: dict[str, str]) -> None:
        fieldnames, rows = self.read()
        rows.append(row)
        self.write(fieldnames or list(self.spec.columns), rows)
