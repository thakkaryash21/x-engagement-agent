"""Plan 3 — tables schema module: anti-drift header guard + Table row IO."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from dashboard import tables
from dashboard.tables import STATUS, Table

REPO_ROOT = Path(__file__).resolve().parent.parent


def _live_header(spec) -> list[str]:
    path = REPO_ROOT / "data" / spec.relpath
    with path.open(newline="", encoding="utf-8") as file:
        return next(csv.reader(file))


@pytest.mark.parametrize("spec", tables.ALL_SPECS, ids=lambda s: s.relpath)
def test_specs_match_live_headers(spec):
    """Anti-drift guard: every declared spec equals the live CSV header exactly."""
    path = REPO_ROOT / "data" / spec.relpath
    if not path.is_file():
        pytest.skip(f"live CSV not present: {spec.relpath}")
    assert _live_header(spec) == list(spec.columns)


def test_status_enum_is_the_single_home():
    assert STATUS == ["drafted", "approved", "edited", "discarded", "sent"]


def test_id_fields_are_declared_columns():
    for spec in tables.ALL_SPECS:
        assert spec.id_field in spec.columns


def test_table_rows_reads_all(temp_store):
    replies = Table(temp_store.paths, tables.REPLIES)
    rows = replies.rows()
    assert {r["reply_id"] for r in rows} == {"r1", "r2"}


def test_table_update_matches_id_and_persists(temp_store):
    replies = Table(temp_store.paths, tables.REPLIES)
    updated = replies.update("r2", {"status": "approved"})
    assert updated is not None and updated["status"] == "approved"
    # persisted to disk
    assert {r["reply_id"]: r["status"] for r in replies.rows()}["r2"] == "approved"


def test_table_update_unknown_id_returns_none(temp_store):
    assert Table(temp_store.paths, tables.REPLIES).update("nope", {"status": "x"}) is None


def test_table_append_adds_row(temp_store):
    profiles = Table(temp_store.paths, tables.PROFILES)
    profiles.append({"handle": "@new", "times_engaged": "1"})
    assert "@new" in {r["handle"] for r in profiles.rows()}


def test_table_header_preserved_on_write(temp_store):
    incidents = Table(temp_store.paths, tables.INCIDENTS)
    fieldnames, rows = incidents.read()
    incidents.write(fieldnames, rows)
    assert _live_or_temp_header(incidents) == list(tables.COLUMNS_INCIDENTS)


def _live_or_temp_header(table: Table) -> list[str]:
    with table.path().open(newline="", encoding="utf-8") as file:
        return next(csv.reader(file))
