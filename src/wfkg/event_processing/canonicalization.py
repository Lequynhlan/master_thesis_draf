"""Deterministic canonicalization for reviewed event records.

The canonical key is supplied by the extraction/review step. This module never
infers that two differently keyed records describe the same event.
"""

from __future__ import annotations

from copy import deepcopy


def canonicalize(extracted_events: list[dict[str, object]]) -> list[dict[str, object]]:
    """Merge records with the same explicit ``canonicalKey``.

    Keeps the first record's event identity and stable field values; unions
    provenance/article/evidence lists in input order and records merged IDs.
    Records without a key are retained as NOT_EVALUATED rather than guessed.
    """
    result: list[dict[str, object]] = []
    by_key: dict[str, dict[str, object]] = {}
    for source in extracted_events:
        item = deepcopy(source)
        key = str(item.get("canonicalKey") or "").strip()
        if not key:
            item.setdefault("canonicalizationStatus", "NOT_EVALUATED")
            item.setdefault("canonicalizationReason", "MISSING_CANONICAL_KEY")
            result.append(item)
            continue
        if key not in by_key:
            item["canonicalKey"] = key
            item.setdefault("canonicalizationStatus", "CANONICAL")
            for field in ("sourceArticles", "evidenceIds", "sourceRecords"):
                if field not in item:
                    aliases = {"sourceArticles": "articleIds", "evidenceIds": "evidence"}
                    item[field] = _as_list(item.get(aliases.get(field, "")))
            by_key[key] = item
            result.append(item)
            continue
        canonical = by_key[key]
        for field in ("sourceArticles", "evidenceIds", "sourceRecords", "mergedEventIds"):
            aliases = {"sourceArticles": "articleIds", "evidenceIds": "evidence"}
            incoming = item.get(field, item.get(aliases.get(field, "")))
            values = _as_list(canonical.get(field)) + _as_list(incoming)
            if field == "mergedEventIds":
                values += [str(item.get("eventId"))] if item.get("eventId") else []
            canonical[field] = _dedupe(values)
        canonical["canonicalizationStatus"] = "MERGED_REVIEWED_DUPLICATE"
    return result


def _as_list(value: object) -> list[object]:
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _dedupe(values: list[object]) -> list[object]:
    result: list[object] = []
    seen: set[str] = set()
    for value in values:
        marker = repr(value)
        if marker not in seen:
            seen.add(marker)
            result.append(value)
    return result
