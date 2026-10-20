"""Conservative exact and alias-based linking to canonical KG entities."""

from __future__ import annotations

import re
import unicodedata
from copy import deepcopy
from typing import Mapping


def normalize_alias(value: str) -> str:
    """Casefold and normalize Unicode/whitespace while retaining Vietnamese marks."""
    text = unicodedata.normalize("NFC", value).casefold()
    return re.sub(r"\s+", " ", text).strip()


def link_entities(
    events: list[dict[str, object]],
    entities: list[dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    """Attach canonical URIs to explicit participant mentions.

    An entity record has ``uri``, ``name`` and optional ``aliases``. A mention
    may contain ``text``. Multiple exact alias matches are retained as REVIEW.
    No fuzzy matching or relation inference is performed.
    """
    registry = entities or []
    index: dict[str, list[dict[str, object]]] = {}
    for entity in registry:
        uri = entity.get("uri") or entity.get("entityUri")
        if not uri:
            continue
        names = [entity.get("name"), *_list(entity.get("aliases"))]
        for name in names:
            if isinstance(name, str) and normalize_alias(name):
                index.setdefault(normalize_alias(name), []).append({**entity, "uri": str(uri)})

    output = []
    for original in events:
        event = deepcopy(original)
        mentions = _list(event.get("participants") or event.get("entities"))
        linked = []
        for mention in mentions:
            if isinstance(mention, str):
                mention = {"text": mention}
            if not isinstance(mention, Mapping):
                continue
            text = str(mention.get("text") or mention.get("mention") or "")
            matches = index.get(normalize_alias(text), [])
            unique = {str(x["uri"]): x for x in matches}
            row = dict(mention)
            row["linkCandidates"] = [
                {"uri": uri, "name": entity.get("name")}
                for uri, entity in sorted(unique.items())
            ]
            if len(unique) == 1:
                row.update(entityUri=next(iter(unique)), linkingStatus="LINKED_EXACT_ALIAS", linkingConfidence=1.0)
            elif len(unique) > 1:
                row.update(linkingStatus="REVIEW_AMBIGUOUS", linkingConfidence=None)
            else:
                row.update(linkingStatus="UNLINKED", linkingConfidence=None)
            linked.append(row)
        if "participants" in event or "entities" not in event:
            event["participants"] = linked
        else:
            event["entities"] = linked
        output.append(event)
    return output


def _list(value: object) -> list[object]:
    if value is None:
        return []
    return list(value) if isinstance(value, (list, tuple, set)) else [value]
