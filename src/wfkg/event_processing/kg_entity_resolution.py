"""Evidence-aware resolution of extracted Vietnamese entity mentions to KG URIs.

This module never writes aliases or entities to the graph. Normalized exact
labels/aliases are candidates; document context may resolve a collision only
when it contains another KG label unique to one candidate. Fuzzy candidates
are returned for review and never promoted to links.
"""
from __future__ import annotations

import re
import unicodedata
import json
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from rdflib import Graph, Namespace, RDF

W = Namespace("https://example.org/wfkg/v1#")
ENTITY_TYPES = {"Company", "Bank", "CorporateLeader", "Industry", "GovernmentOrganization"}
NER_TO_KG = {
    "ORG": {"Company", "Bank", "GovernmentOrganization", "Industry"},
    "PER": {"CorporateLeader"},
    "JOB": set(), "LOC": set(), "FAC": set(),
}
_MOJIBAKE = re.compile(r"(?:[Ãã][\w€]|[Ää][\w]|[Ææ][\w]|á[»º]|[Ââ][\w]|â€)")
_HONORIFIC = re.compile(r"^(?:ông|bà|cô|chú|anh|chị|bác|gs|pgs|ts|thầy)\s+", re.IGNORECASE)
_ABBREVIATIONS = (
    (re.compile(r"\bt\s*\.?\s*p\s*\.?\b", re.IGNORECASE), " thành phố "),
    (re.compile(r"\btmcp\b", re.IGNORECASE), " thương mại cổ phần "),
    (re.compile(r"\bctcp\b", re.IGNORECASE), " công ty cổ phần "),
    (re.compile(r"\btnhh\b", re.IGNORECASE), " trách nhiệm hữu hạn "),
    (re.compile(r"\bcp\b", re.IGNORECASE), " cổ phần "),
)
_LEGAL_PREFIXES = (
    "ngân hàng thương mại cổ phần", "ngân hàng tmcp", "ngân hàng",
    "tổng công ty cổ phần", "công ty cổ phần", "công ty trách nhiệm hữu hạn",
    "công ty", "commercial joint stock bank", "joint stock commercial bank",
    "joint stock company",
)


def repair_mojibake(value: str) -> str:
    """Repair one reversible UTF-8/Windows-1252 or Latin-1 decoding error."""
    if not _MOJIBAKE.search(value):
        return value
    candidates = []
    for encoding in ("cp1252", "latin1"):
        try:
            candidate = value.encode(encoding).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
        before = len(_MOJIBAKE.findall(value))
        after = len(_MOJIBAKE.findall(candidate))
        if after < before:
            candidates.append((after, candidate))
    return min(candidates, default=(0, value), key=lambda row: row[0])[1]


def normalize_surface(value: Any) -> str:
    """Unicode NFC, casefold, expanded common Vietnamese abbreviations, spaces."""
    text = unicodedata.normalize("NFC", repair_mojibake(str(value or "")))
    text = re.sub(r"\s+", " ", text.casefold()).strip()
    for pattern, replacement in _ABBREVIATIONS:
        text = pattern.sub(replacement, text)
    return re.sub(r"\s+", " ", text).strip()


def _key(value: Any) -> str:
    text = normalize_surface(value)
    text = "".join(ch for ch in unicodedata.normalize("NFD", text)
                   if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^\w]+", "", text, flags=re.UNICODE)


def name_keys(value: Any) -> set[str]:
    """Create exact-match variants, stripping only verified honorific/legal prefixes."""
    text = normalize_surface(value)
    variants = {_key(text)} - {""}
    text = _HONORIFIC.sub("", text)
    if text:
        variants.add(_key(text))
    changed = True
    while changed:
        changed = False
        for prefix in _LEGAL_PREFIXES:
            if text.startswith(prefix + " ") and len(text) > len(prefix) + 3:
                text = text[len(prefix):].strip()
                variants.add(_key(text))
                changed = True
                break
    return variants


def build_index(graph: Graph, sourced_aliases_path: Path | None = None) -> tuple[dict[str, dict], dict[str, set[str]]]:
    """Index KG labels and explicitly sourced resolver aliases by exact key.

    Resolver aliases are kept in a separate provenance file and never added to
    the KG graph. Each entry must point to an existing, type-compatible URI.
    """
    index: dict[str, dict] = {}
    by_key: dict[str, set[str]] = defaultdict(set)
    predicates = (W.fullName, W.shortName, W.aliasName, W.ticker, W.companyId,
                  W.stockSymbol, W.name, W.organizationName, W.industryName,
                  W.industryCode, W.personId)
    for subject in set(graph.subjects(RDF.type, None)):
        types = {str(obj).rsplit("#", 1)[-1] for obj in graph.objects(subject, RDF.type)
                 if str(obj).startswith(str(W))} & ENTITY_TYPES
        if not types:
            continue
        labels = {str(v) for p in predicates for v in graph.objects(subject, p)}
        source_refs = {str(v) for v in graph.objects(subject, W.sourceReference)}
        for alias in graph.objects(subject, W.hasAlias):
            labels.update(str(v) for p in predicates for v in graph.objects(alias, p))
            source_refs.update(str(v) for v in graph.objects(alias, W.sourceReference))
        # Parenthetical names are explicitly embedded in an existing KG label.
        labels |= {alias for label in tuple(labels) for alias in re.findall(r"\(([^()]{3,100})\)", label)}
        uri = str(subject)
        index[uri] = {"uri": uri, "types": sorted(types), "labels": sorted(labels),
                      "sourceReferences": sorted(source_refs)}
        for label in labels:
            for key in name_keys(label):
                by_key[key].add(uri)
    if sourced_aliases_path is not None and Path(sourced_aliases_path).is_file():
        registry = json.loads(Path(sourced_aliases_path).read_text(encoding="utf-8"))
        for row in registry.get("entries", []):
            uri = str(row.get("uri", ""))
            alias = str(row.get("alias", "")).strip()
            entity = index.get(uri)
            allowed_types = set(row.get("entityTypes", []))
            if not entity or not alias or not (set(entity["types"]) & allowed_types):
                continue
            entity["labels"].append(alias)
            entity["labels"] = sorted(set(entity["labels"]))
            source_urls = list(row.get("sourceUrls", []))
            if row.get("sourceUrl"):
                source_urls.append(str(row["sourceUrl"]))
            entity["sourceReferences"] = sorted(set(entity["sourceReferences"] + [str(url) for url in source_urls if url]))
            for key in name_keys(alias):
                by_key[key].add(uri)
    return index, by_key


def _context_disambiguate(candidates: set[str], index: dict[str, dict], context: str) -> tuple[str | None, str]:
    """Resolve alias collision only if one candidate's distinct KG label occurs in context."""
    context_keys = {_key(context)}
    context_keys.update(_key(part) for part in re.split(r"[\n.!?;|]+", context) if part.strip())
    corroborated = set()
    for uri in candidates:
        for label in index[uri]["labels"]:
            label_key = _key(label)
            if len(label_key) >= 5 and any(label_key in part for part in context_keys):
                corroborated.add(uri)
                break
    if len(corroborated) == 1:
        return next(iter(corroborated)), "CONTEXT_UNIQUE_KG_LABEL"
    return None, "CONTEXT_DOES_NOT_DISAMBIGUATE"


def resolve_mention(mention: dict, index: dict[str, dict], by_key: dict[str, set[str]],
                    context: str = "") -> dict:
    """Return one URI only for a unique type-compatible exact/corroborated match."""
    surface = str(mention.get("text", ""))
    ner = str(mention.get("entityType", ""))
    allowed = NER_TO_KG.get(ner, set())
    if not allowed:
        return {"status": "OUT_OF_SCOPE", "uri": None, "candidates": [], "method": None,
                "reason": f"Mention type {ner or 'UNKNOWN'} is outside the KG path entity types."}
    query_surfaces = [surface]
    # A parenthetical alias is an explicit equivalence in the observed mention
    # (e.g. legal name (ticker)); consider each side independently. If they
    # point to different URIs the normal ambiguity guard below still applies.
    parenthetical = re.fullmatch(r"\s*(.+?)\s*\(\s*([^()]{2,40})\s*\)\s*", surface)
    if parenthetical:
        query_surfaces.extend(parenthetical.groups())
    candidates = {uri for query_surface in query_surfaces for key in name_keys(query_surface)
                  for uri in by_key.get(key, set()) if set(index[uri]["types"]) & allowed}
    if len(candidates) == 1:
        uri = next(iter(candidates))
        return {"status": "MATCHED", "uri": uri, "candidates": [uri], "method": "EXACT_NORMALIZED_LABEL_OR_ALIAS",
                "reason": "Unique type-compatible KG label/alias after conservative normalization."}
    if len(candidates) > 1:
        uri, method = _context_disambiguate(candidates, index, context)
        if uri:
            return {"status": "MATCHED", "uri": uri, "candidates": sorted(candidates), "method": method,
                    "reason": "Only the selected candidate has a distinct KG label in document context."}
        return {"status": "AMBIGUOUS", "uri": None, "candidates": sorted(candidates), "method": None,
                "reason": "Several type-compatible KG URIs share this normalized label; context is not decisive."}
    # A partial mention can match a complete KG label only at token boundaries.
    # This handles clipped EMD/EAE spans without accepting arbitrary fuzzy text.
    surface = normalize_surface(surface)
    surface_ascii = " ".join(re.sub(r"[^\w]+", " ", "".join(
        ch for ch in unicodedata.normalize("NFD", surface)
        if unicodedata.category(ch) != "Mn"), flags=re.UNICODE).split())
    nested: set[str] = set()
    if len(_key(surface)) >= 10 and len(surface_ascii.split()) >= 2:
        for uri, entity in index.items():
            if not (set(entity["types"]) & allowed):
                continue
            for label in entity["labels"]:
                label_norm = normalize_surface(label)
                label_ascii = " ".join(re.sub(r"[^\w]+", " ", "".join(
                    ch for ch in unicodedata.normalize("NFD", label_norm)
                    if unicodedata.category(ch) != "Mn"), flags=re.UNICODE).split())
                # Only accept a clipped mention that is wholly contained in a
                # longer KG label. A longer mention containing a short label
                # can name a distinct unit (for example, SHB Finance or a union).
                if f" {surface_ascii} " in f" {label_ascii} ":
                    nested.add(uri)
        if len(nested) == 1:
            uri = next(iter(nested))
            return {"status": "MATCHED", "uri": uri, "candidates": [uri], "method": "KG_LABEL_NESTED_SPAN",
                    "reason": "Unique type-compatible KG label contains the complete multi-token mention at token boundaries."}
        if len(nested) > 1:
            return {"status": "AMBIGUOUS", "uri": None, "candidates": sorted(nested), "method": None,
                    "reason": "Mention is a token-bounded part of multiple type-compatible KG labels."}
    # Brand/ticker co-reference needs explicit same-sentence parenthetical evidence.
    if surface:
        sentences = re.split(r"[.!?;\n]+", context)
        explicit = set()
        for sentence in sentences:
            if surface.casefold() not in sentence.casefold():
                continue
            for uri, entity in index.items():
                if not (set(entity["types"]) & allowed):
                    continue
                for label in entity["labels"]:
                    if len(_key(label)) < 2:
                        continue
                    pair = re.compile(r"(?:" + re.escape(surface) + r"\s*\(\s*" + re.escape(label) +
                                      r"\s*\)|" + re.escape(label) + r"\s*\(\s*" + re.escape(surface) + r"\s*\))", re.IGNORECASE)
                    if pair.search(sentence):
                        explicit.add(uri)
        if len(explicit) == 1:
            uri = next(iter(explicit))
            return {"status": "MATCHED", "uri": uri, "candidates": [uri], "method": "DOCUMENT_EXPLICIT_EQUIVALENCE",
                    "reason": "The article explicitly equates this surface with an existing KG alias in parentheses; no alias was added."}
        if len(explicit) > 1:
            return {"status": "AMBIGUOUS", "uri": None, "candidates": sorted(explicit), "method": None,
                    "reason": "Article contains conflicting explicit alias equivalences."}
    query = _key(surface)
    near = []
    if len(query) >= 5:
        for uri, entity in index.items():
            if not (set(entity["types"]) & allowed):
                continue
            best = max(((SequenceMatcher(None, query, _key(label)).ratio(), label)
                        for label in entity["labels"] if _key(label)), default=(0.0, ""))
            if best[0] >= .72 or (len(query) >= 7 and query in _key(best[1])):
                near.append({"uri": uri, "label": best[1], "similarity": round(best[0], 4)})
    near.sort(key=lambda row: (-row["similarity"], row["uri"]))
    return {"status": "UNRESOLVED", "uri": None, "candidates": near[:5], "method": None,
            "reason": "No unique exact type-compatible KG label/alias; near matches are review-only."}


def argument_compatibility(event_type: str, role: str, mention_type: str) -> tuple[bool, str]:
    """Conservative BKEE role/type compatibility for participant linking."""
    if role == "Person":
        return mention_type == "PER", "Person arguments require a PER mention; JOB is a role/title, not a person."
    if role in {"Entity", "Org", "Organization", "Beneficiary", "Buyer", "Seller", "Giver", "Recipient"}:
        return mention_type == "ORG", "Organization/entity arguments require an ORG mention."
    if role == "Position":
        return mention_type == "JOB", "Position arguments require a JOB mention."
    return False, f"Argument role {role or 'UNKNOWN'} is not a participant role used by the four audited paths."

