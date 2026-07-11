"""Plan 4 — InsightsView aggregation, testable against a fake table (no CSV)."""

from __future__ import annotations

from dashboard.insights import InsightsView
from dashboard.tables import STATUS


class FakeTable:
    """Minimal stand-in exposing the only method funnel_counts needs: rows()."""

    def __init__(self, rows):
        self._rows = rows

    def rows(self):
        return self._rows


def test_funnel_counts_over_fake_table():
    view = InsightsView(paths=None)  # funnel_counts never touches paths
    table = FakeTable([
        {"status": "drafted"},
        {"status": "sent", "reviewed_at": "2026-01-01"},
        {"status": "sent", "reviewed_at": ""},
        {"status": "discarded"},
        {"status": "bogus"},
    ])
    counts = view.funnel_counts(table, STATUS)
    assert counts["drafted"] == 1
    assert counts["sent"] == 2
    assert counts["discarded"] == 1
    assert counts["reviewed"] == 1  # only the sent row with a reviewed_at
    assert "bogus" not in counts


def test_to_float_handles_blanks_and_bad_values():
    assert InsightsView.to_float("0.25") == 0.25
    assert InsightsView.to_float("") is None
    assert InsightsView.to_float(None) is None
    assert InsightsView.to_float("not-a-number") is None
