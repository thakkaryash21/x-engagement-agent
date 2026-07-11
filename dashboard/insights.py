"""InsightsView — the send funnel, edit rate, and performance breakdown.

Kept as one module on purpose (the do-not-over-split guardrail): funnel counts,
edit rate, latest-metric selection, and per-archetype/content-type performance are
one cohesive aggregation over the replies/tweets/metrics/profiles tables. All CSV
access goes through ``tables.Table``, so this view is testable against any object
exposing ``data_path`` — no CSV fixtures required for the aggregation logic.
"""

from __future__ import annotations

from typing import Any

from .paths import PathResolver
from .tables import METRICS, PROFILES, REPLIES, STATUS, TWEETS, Table


class InsightsView:
    def __init__(self, paths: PathResolver) -> None:
        self.paths = paths

    @staticmethod
    def to_float(value: str | None) -> float | None:
        try:
            return float(value) if value not in (None, "") else None
        except ValueError:
            return None

    def funnel_counts(self, table: Table, statuses: list[str]) -> dict[str, int]:
        rows = table.rows()
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
        for spec in (REPLIES, TWEETS):
            for row in Table(self.paths, spec).rows():
                if row.get("status") == "sent":
                    total_sent += 1
                    if (row.get("user_edited") or "").strip().lower() == "true":
                        edited += 1
        return {"sent": total_sent, "edited": edited, "rate": (edited / total_sent) if total_sent else None}

    def latest_metrics_by_item(self) -> dict[str, dict[str, str]]:
        latest: dict[str, dict[str, str]] = {}
        for row in Table(self.paths, METRICS).rows():
            item_id = row.get("item_id")
            if item_id and (item_id not in latest or row.get("captured_at", "") > latest[item_id].get("captured_at", "")):
                latest[item_id] = row
        return latest

    def performance_breakdown(self) -> dict[str, dict[str, dict[str, float | int]]]:
        metrics = self.latest_metrics_by_item()
        by_archetype: dict[str, list[float]] = {}
        for row in Table(self.paths, REPLIES).rows():
            metric = metrics.get(row.get("reply_id", ""))
            rate = self.to_float(metric.get("engagement_rate") if metric else None)
            if rate is not None:
                by_archetype.setdefault(row.get("reply_archetype") or "(unset)", []).append(rate)

        by_content_type: dict[str, list[float]] = {}
        for row in Table(self.paths, TWEETS).rows():
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
                "replies": self.funnel_counts(Table(self.paths, REPLIES), STATUS),
                "tweets": self.funnel_counts(Table(self.paths, TWEETS), STATUS),
            },
            "edit_rate": self.edit_rate(),
            "performance": self.performance_breakdown(),
            "profiles": Table(self.paths, PROFILES).rows(),
        }
