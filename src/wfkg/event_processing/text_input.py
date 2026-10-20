"""Choose and prepare the article text used by entity/event extraction.

Full text is the preferred source. The RAW summary is only a fallback when a
usable full-text body is unavailable; it is never appended to an available body.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import Mapping


_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class ExtractionInput:
    """Auditable text selection result passed to a model adapter.

    ``text`` contains the title and the selected content. ``content_text`` is
    the selected body/summary without the title, which is useful for retaining
    source offsets when a later extractor adds evidence spans.
    """

    article_id: str
    source: str
    status: str
    reason: str
    title: str
    content_text: str
    text: str
    char_count: int
    sha256: str
    short_body_review: bool

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation for run logs/manifests."""

        return asdict(self)


def _clean(value: object) -> str:
    """Normalize Unicode and whitespace without deleting punctuation or facts."""

    if not isinstance(value, str):
        return ""
    normalized = unicodedata.normalize("NFC", value)
    return _WHITESPACE.sub(" ", normalized).strip()


def _same_as_title(value: str, title: str) -> bool:
    """Identify a title copied into a body/summary, ignoring case and spacing."""

    return bool(value and title and value.casefold() == title.casefold())


def prepare_extraction_input(
    article: Mapping[str, object],
    enriched_article: Mapping[str, object] | None = None,
    *,
    short_body_review_chars: int = 500,
) -> ExtractionInput:
    """Select full text first, then a substantive summary, then title only.

    A non-empty body that differs from the title is used even when it is short.
    Short bodies are flagged for review instead of silently discarded: short
    corporate disclosures can still contain the event facts needed downstream.
    Set ``short_body_review_chars`` to change only the warning threshold, not
    the full-text preference or fallback rules.

    The enrichment record is expected to be joined to the RAW article by
    ``articleId`` by the caller. This function checks mismatched IDs when both
    records provide one, preventing accidental cross-article text selection.
    """

    if short_body_review_chars < 0:
        raise ValueError("short_body_review_chars must be non-negative")

    article_id = str(article.get("articleId") or "")
    enriched = enriched_article or {}
    enriched_id = str(enriched.get("articleId") or "")
    if article_id and enriched_id and article_id != enriched_id:
        raise ValueError(
            f"Enrichment/articleId mismatch: RAW={article_id!r}, enriched={enriched_id!r}"
        )

    title = _clean(article.get("title"))
    body = _clean(enriched.get("bodyText") or article.get("bodyText"))
    summary = _clean(article.get("summary"))

    if body and not _same_as_title(body, title):
        source = "FULL_TEXT"
        status = "SELECTED"
        reason = "NON_EMPTY_BODY_PREFERRED_OVER_SUMMARY"
        content = body
        short_review = len(body) < short_body_review_chars
        if short_review:
            status = "SELECTED_SHORT_REVIEW"
            reason = "BODY_SELECTED_BUT_BELOW_REVIEW_LENGTH_THRESHOLD"
    elif summary and not _same_as_title(summary, title):
        source = "SUMMARY_FALLBACK"
        status = "FALLBACK"
        reason = "FULL_TEXT_MISSING_OR_TITLE_COPY"
        content = summary
        short_review = False
    elif title:
        source = "TITLE_ONLY"
        status = "FALLBACK"
        reason = "NO_USABLE_BODY_OR_SUBSTANTIVE_SUMMARY"
        content = ""
        short_review = False
    else:
        source = "MISSING"
        status = "UNUSABLE"
        reason = "TITLE_BODY_AND_SUMMARY_MISSING_OR_EMPTY"
        content = ""
        short_review = False

    # Keep title as context while retaining the selected source as a separate
    # field. Summary is intentionally absent whenever FULL_TEXT was selected.
    model_text = "\n".join(part for part in (title, content) if part)
    digest = hashlib.sha256(model_text.encode("utf-8")).hexdigest()
    return ExtractionInput(
        article_id=article_id,
        source=source,
        status=status,
        reason=reason,
        title=title,
        content_text=content,
        text=model_text,
        char_count=len(model_text),
        sha256=digest,
        short_body_review=short_review,
    )
