"""Store-level integration: config validation, aggregation shapes, /api parity.

Covers the plan-1 validation guarantees and confirms the composed services keep
the /api/* response shapes stable after the plan-4 DashboardStore split. Endpoints
now call the owning service (store.config, store.drafts, store.insights, ...).
"""

from __future__ import annotations

import pytest

from dashboard import tables


# --- Plan 1: config write validation still raises -----------------------------

def test_write_limits_rejects_non_int(temp_store):
    with pytest.raises(ValueError):
        temp_store.config.write_limits({"max_drafts_per_session": "lots"})


def test_write_limits_rejects_bool(temp_store):
    with pytest.raises(ValueError):
        temp_store.config.write_limits({"max_drafts_per_session": True})


def test_write_limits_persists_and_preserves_comment(temp_store):
    temp_store.config.write_limits({"max_sends_per_day": 3})
    text = temp_store.paths.config_path("limits.yaml").read_text(encoding="utf-8")
    assert "max_sends_per_day: 3 # inline comment" in text
    assert temp_store.config.read_limits()["max_sends_per_day"] == 3


def test_write_metrics_rejects_non_list(temp_store):
    with pytest.raises(ValueError):
        temp_store.config.write_metrics_yaml({"layer1": "not a list"})


def test_write_active_persona_rejects_unknown(temp_store):
    with pytest.raises(ValueError):
        temp_store.config.write_active_persona(persona="does-not-exist")


def test_write_active_persona_rejects_bad_tagging(temp_store):
    with pytest.raises(ValueError):
        temp_store.config.write_active_persona(tagging="maybe")


def test_write_active_persona_updates_both(temp_store):
    result = temp_store.config.write_active_persona(persona="shubham", tagging="on")
    assert result == {"persona": "shubham", "tagging": "on"}
    text = (temp_store.root / "AGENTS.md").read_text(encoding="utf-8")
    assert "persona: shubham # comment" in text
    assert "```yaml" in text  # fence preserved


# --- Plans 1-4: /api response shapes stable -----------------------------------

def test_api_insights_shape(temp_store):
    ins = temp_store.insights.api_insights()
    assert set(ins) == {"funnel", "edit_rate", "performance", "profiles"}
    assert set(ins["funnel"]) == {"replies", "tweets"}
    assert set(ins["funnel"]["replies"]) == {
        "drafted", "approved", "edited", "discarded", "sent", "reviewed",
    }
    assert set(ins["edit_rate"]) == {"sent", "edited", "rate"}
    assert set(ins["performance"]) == {"by_reply_archetype", "by_content_type"}
    assert isinstance(ins["profiles"], list)


def test_api_insights_values(temp_store):
    ins = temp_store.insights.api_insights()
    # r1 sent+reviewed; r2 drafted
    assert ins["funnel"]["replies"]["sent"] == 1
    assert ins["funnel"]["replies"]["reviewed"] == 1
    assert ins["funnel"]["replies"]["drafted"] == 1
    # r1 (edited) + t1 (not edited) both sent => 1/2 across replies+tweets
    assert ins["edit_rate"] == {"sent": 2, "edited": 1, "rate": 0.5}
    # latest metric for r1 is 0.20 (latest-wins by captured_at)
    arche = ins["performance"]["by_reply_archetype"]["sharp question"]
    assert arche == {"n": 1, "avg_engagement_rate": 0.20}


def test_api_incidents_and_clear_lockout(temp_store):
    assert temp_store.incidents.api_incidents()["locked_out"] is True
    result = temp_store.incidents.clear_lockout()
    assert result == {"ok": True, "cleared": True}
    assert temp_store.incidents.api_incidents()["locked_out"] is False


def test_api_drafts_shape(temp_store):
    # a draft file for r2 (drafted status) should surface
    temp_store.paths.data_path("drafts", "r2.md").write_text(
        "# Draft r2\n**Content type**: x\n\n---\ndraft two\n---\n", encoding="utf-8"
    )
    drafts = temp_store.drafts.api_drafts()["drafts"]
    assert len(drafts) == 1
    item = drafts[0]
    assert set(item) == {"id", "type", "status", "row", "raw", "stale_age"}
    assert item["id"] == "r2"
    assert item["status"] == "drafted"


def test_approve_draft_with_edit_rewrites_body(temp_store):
    draft_path = temp_store.paths.data_path("drafts", "r2.md")
    draft_path.write_text("# Draft r2\n\n---\ndraft two\n---\n", encoding="utf-8")
    result = temp_store.drafts.approve_draft("r2", edited_text="a fresh edited body")
    assert result["status"] == "edited"
    body = draft_path.read_text(encoding="utf-8")
    assert "a fresh edited body" in body
    row = {r["reply_id"]: r for r in tables.Table(temp_store.paths, tables.REPLIES).rows()}["r2"]
    assert row["status"] == "edited" and row["user_edited"] == "true"


def test_approve_draft_without_edit_marks_approved(temp_store):
    temp_store.paths.data_path("drafts", "r2.md").write_text(
        "# Draft r2\n\n---\ndraft two\n---\n", encoding="utf-8"
    )
    result = temp_store.drafts.approve_draft("r2", edited_text="draft two")
    assert result == {"ok": True, "status": "approved"}
