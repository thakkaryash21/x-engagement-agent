"""Plan 2 — DraftFile: parse/render round-trip and body rewrite preservation."""

from __future__ import annotations

from dashboard.draft_file import DraftDoc, DraftFile

# A canonically-rendered reply draft (matches render() output shape).
CANONICAL = (
    "# Draft r1\n"
    "**Target**: https://x.com/example/status/123\n"
    "**Author**: @example — founder, small, relevance 4, credibility 4\n"
    "\n"
    "---\n"
    "what changed after you stopped treating the first reply as distribution?\n"
    "---\n"
)

# The real example draft has extra trailing blank lines (non-canonical input).
EXAMPLE_DRAFT = (
    "# Example Draft\n\n"
    "**Target**: https://x.com/example/status/123\n"
    "**Archetype**: sharp question        **Tagging**: none\n\n"
    "---\n"
    "body text here\n"
    "---\n\n\n"
)

WITH_TRAILER = (
    "# Draft r1\n"
    "**Content type**: insight\n"
    "\n"
    "---\n"
    "the body\n"
    "---\n"
    "\n"
    "Alt (different angle, optional):\n"
    "an alternate\n"
)


def test_parse_splits_around_first_two_separators():
    doc = DraftFile.parse(EXAMPLE_DRAFT)
    assert doc.header.startswith("# Example Draft")
    assert doc.body == "body text here"
    assert doc.trailer.strip() == ""


def test_render_is_byte_stable_for_canonical_input():
    assert DraftFile.render(DraftFile.parse(CANONICAL)) == CANONICAL


def test_render_is_idempotent_for_messy_input():
    once = DraftFile.render(DraftFile.parse(EXAMPLE_DRAFT))
    twice = DraftFile.render(DraftFile.parse(once))
    assert once == twice


def test_parse_preserves_trailer_block():
    doc = DraftFile.parse(WITH_TRAILER)
    assert doc.body == "the body"
    assert "Alt (different angle, optional):" in doc.trailer
    assert "an alternate" in doc.trailer


def test_rewrite_body_preserves_header_and_trailer():
    out = DraftFile.rewrite_body(WITH_TRAILER, "a brand new body")
    doc = DraftFile.parse(out)
    assert doc.body == "a brand new body"
    assert doc.header.startswith("# Draft r1")
    assert "an alternate" in doc.trailer


def test_fewer_than_two_separators_yields_no_body():
    text = "# Just a header\nno separators here\n"
    doc = DraftFile.parse(text)
    assert doc.header == text
    assert doc.body is None
    assert doc.trailer is None


def test_rewrite_body_with_no_separators_still_produces_valid_draft():
    text = "# Header only\n"
    out = DraftFile.rewrite_body(text, "new body")
    doc = DraftFile.parse(out)
    assert doc.body == "new body"
    assert doc.header.startswith("# Header only")


def test_templates_are_parseable_and_declare_both_shapes():
    reply = DraftFile.parse(DraftFile.TEMPLATE_REPLY)
    assert "<draft text" in (reply.body or "")
    assert "**Target**" in reply.header
    original = DraftFile.parse(DraftFile.TEMPLATE_ORIGINAL)
    assert "**Content type**" in original.header
    assert "===" in (original.body or "")
