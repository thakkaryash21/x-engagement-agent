"""The one executable owner of the draft ``---`` markdown template.

The reply/quote/original draft format (header lines, two ``---`` body separators,
optional trailer such as an ``Alt`` block) previously had four homes that could
silently diverge: ``docs/file-map.md``, ``modes/scroll.md``, ``modes/compose.md``,
and the split/rewrite pair in ``file_store.py``. This module owns the executable
contract; the prose files are the human-readable spec and reference this module.

Interface = ``parse`` / ``render`` / ``rewrite_body``. The ``---`` separator
contract lives entirely inside. This is a *consolidation*, not a format change:
the ``---`` body separators and the in-thread ``===`` segment marker are
unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass

SEPARATOR = "---"


@dataclass
class DraftDoc:
    """A parsed draft: everything above / between / below the two ``---`` lines."""

    header: str
    body: str | None
    trailer: str | None


class DraftFile:
    """Parses, renders, and body-rewrites draft markdown around ``---`` separators."""

    SEPARATOR = SEPARATOR

    # Single source of the reply/thread/quote draft template (see docs/file-map.md).
    TEMPLATE_REPLY = (
        "# Draft <reply_id>\n"
        "**Target**: <target_tweet_url>\n"
        "**Author**: @<handle> — <category>, <follower_tier>, relevance <n>, credibility <n>\n"
        "**Tweet**: <quoted/paraphrased text of the target tweet>\n"
        "**Format**: <reply|thread_reply|quote>        **Archetype**: <archetype>        "
        "**Tagging**: <none | @handle>\n"
        "\n"
        "---\n"
        "<draft text — exactly what would be typed into the reply box>\n"
        "---\n"
        "\n"
        "Alt (different angle, optional):\n"
        "<one alternate>\n"
    )

    # Single source of the original-tweet draft template (see docs/file-map.md).
    TEMPLATE_ORIGINAL = (
        "# Draft <tweet_id>\n"
        "**Content type**: <content_type>        **Hook**: <hook_type>\n"
        "\n"
        "---\n"
        "<draft text — exactly what would be typed; thread segments separated by `===`>\n"
        "---\n"
        "\n"
        "Alt (different angle, optional):\n"
        "<one alternate — non-thread drafts only>\n"
    )

    @staticmethod
    def parse(text: str) -> DraftDoc:
        """Split into header / body / trailer around the first two ``---`` lines.

        With fewer than two separators the whole text is the header and there is
        no body or trailer (matching the legacy ``split_draft_body`` contract).
        """
        lines = text.splitlines()
        sep_indices = [index for index, line in enumerate(lines) if line.strip() == SEPARATOR]
        if len(sep_indices) < 2:
            return DraftDoc(header=text, body=None, trailer=None)
        start, end = sep_indices[0], sep_indices[1]
        return DraftDoc(
            header="\n".join(lines[:start]),
            body="\n".join(lines[start + 1:end]).strip(),
            trailer="\n".join(lines[end + 1:]),
        )

    @staticmethod
    def render(doc: DraftDoc) -> str:
        """Assemble canonical draft text from a ``DraftDoc``.

        Rendering is idempotent: ``render(parse(render(doc))) == render(doc)``.
        """
        parts = [doc.header.rstrip(), "", SEPARATOR, (doc.body or "").strip(), SEPARATOR]
        if doc.trailer and doc.trailer.strip():
            parts += ["", doc.trailer.strip()]
        return "\n".join(parts) + "\n"

    @staticmethod
    def rewrite_body(text: str, new_body: str) -> str:
        """Return ``text`` with the ``---`` body replaced, header + trailer preserved."""
        doc = DraftFile.parse(text)
        return DraftFile.render(DraftDoc(header=doc.header, body=new_body, trailer=doc.trailer))
