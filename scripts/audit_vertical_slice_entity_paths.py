"""Audit and conservatively improve entity linking and four ontology event-stock paths."""
from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime
from difflib import SequenceMatcher
from pathlib import Path
import sys

from rdflib import Graph, Literal, Namespace, RDF, URIRef
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wfkg.event_processing.text_input import prepare_extraction_input
from wfkg.event_processing.kg_entity_resolution import (
    argument_compatibility, build_index as build_kg_entity_index,
    normalize_surface, repair_mojibake as repair_kg_mojibake,
    resolve_mention as resolve_kg_mention,
)

RUN = ROOT / "runs/news_event_vertical_slice_20261019"
KG_PATH = ROOT / "data/gold/knowledge_graph.ttl"
W = Namespace("https://example.org/wfkg/v1#")
PATHS = ("DIRECT", "INDIRECT_SUBSIDIARY", "INDIRECT_LEADERSHIP", "INDIRECT_INDUSTRY")
ENTITY_TYPES = {"Company", "Bank", "GovernmentOrganization", "CorporateLeader", "Industry"}
ORG_TYPES = {"Company", "Bank", "GovernmentOrganization", "Industry"}
ROLE_COMPANY = {"Entity", "Org", "Organization", "Beneficiary", "Buyer", "Seller", "Giver", "Recipient"}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf8"))


def dump_csv(path: Path, rows: list[dict], fields: list[str]):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def repair_mojibake(value: str) -> str:
    return repair_kg_mojibake(value)
    """Repair only reversible UTF-8-as-Windows-1252 mojibake; preserve all else."""
    if not any(marker in value for marker in ("Ã", "Â", "á»", "Ä‘", "Æ°")):
        return value
    try:
        candidate = value.encode("cp1252").decode("utf8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value
    markers = ("Ã", "Â", "á»", "Ä‘", "Æ°")
    return candidate if sum(value.count(x) for x in markers) > sum(candidate.count(x) for x in markers) else value


def strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def norm(value: object) -> str:
    text = strip_accents(normalize_surface(value))
    return re.sub(r"[^\w]+", "", text, flags=re.UNICODE)


LEGAL_PREFIXES = (
    "nganhangthuongmaicophan", "nganhangtmcp", "nganhangthuongmai", "nganhang",
    "tongcongtycophan", "congtycophan", "congtytnhh", "congty",
    "commercialjointstockbank", "jointstockcommercialbank", "jointstockcompany",
)


def variants(value: object) -> set[str]:
    base = norm(value)
    result = {base} if base else set()
    honorific_match = re.match(r"^\s*(?:ông|bà|cô|chú|anh|chị|bác|gs\.?|pgs\.?|ts\.?|thầy)\s+(.+)$", repair_mojibake(str(value or "")), flags=re.IGNORECASE)
    if honorific_match:
        result.add(norm(honorific_match.group(1)))
    changed = True
    current = base
    while changed:
        changed = False
        for prefix in LEGAL_PREFIXES:
            if current.startswith(prefix) and len(current) > len(prefix) + 2:
                current = current[len(prefix):]
                result.add(current)
                changed = True
                break
    return result


def values(g: Graph, subject, predicates: tuple) -> list[str]:
    return [str(value) for predicate in predicates for value in g.objects(subject, predicate)]


def build_entity_index(g: Graph) -> tuple[dict[str, dict], dict[str, list[str]]]:
    by_uri: dict[str, dict] = {}
    by_key: dict[str, set[str]] = defaultdict(set)
    name_preds = (W.fullName, W.shortName, W.aliasName, W.ticker, W.companyId, W.stockSymbol, W.name,
                  W.organizationName, W.industryName, W.industryCode, W.personId)
    for subject in set(g.subjects(RDF.type, None)):
        classes = {str(o).rsplit("#", 1)[-1] for o in g.objects(subject, RDF.type) if str(o).startswith(str(W))}
        accepted = classes & ENTITY_TYPES
        if not accepted:
            continue
        names = set(values(g, subject, name_preds))
        alias_uris = list(g.objects(subject, W.hasAlias))
        alias_refs = []
        for alias in alias_uris:
            names.update(values(g, alias, (W.aliasName, W.shortName, W.ticker, W.fullName)))
            alias_refs.extend(str(v) for v in g.objects(alias, W.sourceReference))
        names = {repair_mojibake(name).strip() for name in names if name.strip()}
        # A parenthetical brand explicitly present in the KG fullName is an existing alias fact.
        for name in list(names):
            names.update(re.findall(r"\(([^()]{3,80})\)", name))
        uri = str(subject)
        by_uri[uri] = {"uri": uri, "types": sorted(accepted), "names": sorted(names),
                       "sourceReferences": sorted(set(str(x) for x in g.objects(subject, W.sourceReference)) | set(alias_refs))}
        for name in names:
            for key in variants(name):
                by_key[key].add(uri)
    return by_uri, {key: sorted(uris) for key, uris in by_key.items()}


def fuzzy_candidates(text: str, index: dict[str, dict], allowed: set[str]) -> list[tuple[str, str, float]]:
    query = norm(text)
    if len(query) < 5:
        return []
    candidates = []
    for uri, entity in index.items():
        if not (set(entity["types"]) & allowed):
            continue
        for name in entity["names"]:
            target = norm(name)
            score = SequenceMatcher(None, query, target).ratio()
            if score >= 0.78 or (len(query) >= 7 and (query in target or target in query)):
                candidates.append((uri, name, score))
    best_by_uri = {}
    for uri, name, score in candidates:
        if uri not in best_by_uri or score > best_by_uri[uri][1]:
            best_by_uri[uri] = (name, score)
    return [(uri, name, score) for uri, (name, score) in sorted(best_by_uri.items(), key=lambda x: -x[1][1]) if score >= .78]


def resolve_mention(mention: dict, index: dict[str, dict], by_key: dict[str, list[str]], context_supported: bool) -> dict:
    text = str(mention.get("text", ""))
    ner = str(mention.get("entityType", ""))
    allowed = ORG_TYPES if ner == "ORG" else ({"CorporateLeader"} if ner == "PER" else set())
    if not allowed:
        return {"status": "OUT_OF_SCOPE", "matches": [], "nearMatches": [], "reason": f"NER type {ner or 'UNKNOWN'} is not an entity type used by the four paths."}
    matches = sorted({uri for key in variants(text) for uri in by_key.get(key, []) if set(index[uri]["types"]) & allowed})
    if len(matches) == 1:
        return {"status": "MATCHED", "matches": matches, "nearMatches": [], "reason": "Unique KG URI matched by accent/punctuation/legal-prefix normalization or existing CompanyAlias."}
    if len(matches) > 1:
        return {"status": "AMBIGUOUS", "matches": matches, "nearMatches": [], "reason": "Normalized mention maps to multiple eligible KG URIs."}
    near = fuzzy_candidates(text, index, allowed)
    if near:
        status = "MISSING_ALIAS" if context_supported else "INSUFFICIENT_EVIDENCE"
        reason = "Event argument supports this entity, but KG has only a near name; verify/add an alias before linking." if context_supported else "Near KG names exist, but this mention is not aligned to an event argument; relevance is unestablished."
        return {"status": status, "matches": [], "nearMatches": near, "reason": reason}
    meaningful = len(norm(text)) >= 5 and len(text.split()) >= 1
    if meaningful and context_supported:
        return {"status": "MISSING_KG_ENTITY", "matches": [], "nearMatches": [], "reason": "Entity-like ORG/PER mention has no exact or close in-scope KG entity."}
    if meaningful:
        return {"status": "INSUFFICIENT_EVIDENCE", "matches": [], "nearMatches": [], "reason": "No event-argument alignment establishes this mention as relevant to the Event; do not require a KG mapping."}
    return {"status": "INSUFFICIENT_EVIDENCE", "matches": [], "nearMatches": [], "reason": "Mention is too short or generic to identify a KG entity."}


def parse_datetime(value: object):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_date(value: object):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def active_for_event(g: Graph, relation, event_day: date | None, event_available: datetime | None, *, snapshot_only: bool = False) -> tuple[str, str]:
    available = parse_datetime(next(iter(g.objects(relation, W.availableAt)), None))
    if available and event_available and available > event_available:
        return "INSUFFICIENT_EVIDENCE", f"relation availableAt={available.isoformat()} is after event availableAt={event_available.isoformat()}"
    start = parse_date(next(iter(g.objects(relation, W.validFrom)), None))
    end = parse_date(next(iter(g.objects(relation, W.validTo)), None))
    observed = parse_date(next(iter(g.objects(relation, W.observedAsOf)), None))
    if event_day and start:
        if start > event_day or (end and end < event_day):
            return "INSUFFICIENT_EVIDENCE", f"event date {event_day} falls outside valid interval {start}..{end or 'open'}"
        return "MATCHED", f"valid interval {start}..{end or 'open'} covers effectiveTradingDate {event_day}"
    if snapshot_only and event_day and observed == event_day:
        return "MATCHED", f"observedAsOf exactly matches effectiveTradingDate {event_day}"
    if observed:
        return "INSUFFICIENT_EVIDENCE", f"observedAsOf={observed} is a snapshot, not validFrom; it does not prove relation active on {event_day}"
    return "INSUFFICIENT_EVIDENCE", "no usable validFrom/validTo or matching observedAsOf interval"


def stock_obs_at(g: Graph, stock, event_day: date | None) -> list[str]:
    found = []
    for obs in g.objects(stock, W.hasMarketObservation):
        day = parse_date(next(iter(g.objects(obs, W.tradingDate)), None))
        if day == event_day:
            found.append(str(obs))
    return sorted(found)


def main() -> dict:
    g = Graph().parse(KG_PATH)
    index, by_key = build_entity_index(g)
    staging_path = RUN / "staging_review.json"
    events = load_json(staging_path)
    articles = {str(row["articleId"]): row for row in load_jsonl(ROOT / "data/cleaned/news_100_v1/clean_articles.jsonl")}
    enriched = {str(row["articleId"]): row for row in load_jsonl(ROOT / "data/enriched_cleaned/news_100_v1/articles.jsonl")}
    previous_report_path = RUN / "entity_linking_report.json"
    previous_report = load_json(previous_report_path) if previous_report_path.exists() else {}
    # The pre-audit resolver snapshot reported 26 LINKED_UNIQUE mentions; later
    # reports are generated by this script and must not be reused as baseline.
    original_matched_count = 26
    mention_rows = []
    gaps: dict[tuple, dict] = {}
    total_improved = 0

    for event in events:
        article = articles.get(str(event["articleId"]), {})
        evidence_id = str(event.get("evidence", {}).get("evidenceId", ""))
        evidence = str(event.get("evidence", {}).get("evidenceText", ""))
        updated_suggestions = []
        old_suggestions = event.get("entityLinkSuggestions", [])
        for i, mention in enumerate(event.get("entities", [])):
            start, end = mention.get("startChar"), mention.get("endChar")
            relevant_args = [arg for arg in event.get("arguments", [])
                             if norm(arg.get("text")) == norm(mention.get("text"))
                             or ((arg.get("entityMention") or {}).get("startChar") == start and (arg.get("entityMention") or {}).get("endChar") == end)]
            roles = sorted({str(arg.get("role", "")) for arg in relevant_args})
            ticker_prefix = evidence_starts_with_entity(event.get("evidence", {}).get("evidenceText", ""), mention.get("text", ""))
            context_supported = bool(set(roles) & (ROLE_COMPANY | {"Person"})) or ticker_prefix
            result = resolve_mention(mention, index, by_key, context_supported)
            prior = old_suggestions[i] if i < len(old_suggestions) else {}
            if result["status"] == "MATCHED" and prior.get("status") != "LINKED_UNIQUE":
                total_improved += 1
            updated = {"mention": mention,
                       "matches": [{"uri": uri, "type": index[uri]["types"], "matchedName": mention.get("text"), "sourceReferences": index[uri]["sourceReferences"]} for uri in result["matches"]],
                       "status": result["status"], "reason": result["reason"],
                       "nearMatches": [{"uri": uri, "matchedName": name, "similarity": round(score, 4)} for uri, name, score in result["nearMatches"]]}
            updated_suggestions.append(updated)
            span_text = ""
            if isinstance(start, int) and isinstance(end, int) and start <= end:
                full = prepare_extraction_input(article, enriched.get(str(event["articleId"]))).text
                span_text = full[start:end]
            if mention.get("text") and norm(span_text or mention.get("text")) != norm(mention.get("text")):
                result_status = "EXTRACTION_ERROR"
                result_reason = f"Mention span does not verify against prepared article text (span={span_text!r})."
            else:
                result_status = result["status"]
                result_reason = result["reason"]
            mention_in_evidence = bool(mention.get("text") and norm(mention["text"]) in norm(evidence))
            event_relevance = "ARGUMENT_SPAN_SUPPORT_REVIEW" if set(roles) & (ROLE_COMPANY | {"Person"}) else ("EXPLICIT_EVIDENCE_SUBJECT_PREFIX" if ticker_prefix else "NOT_ESTABLISHED")
            mention_rows.append({
                "articleId": event["articleId"], "eventId": event["eventId"], "evidenceId": evidence_id,
                "sourceUrl": article.get("url", ""), "eventType": event.get("eventType", ""),
                "evidenceText": evidence, "mentionText": mention.get("text", ""), "predictedEntityType": mention.get("entityType", ""),
                "startChar": start, "endChar": end, "spanVerified": result_status != "EXTRACTION_ERROR",
                "confidence": mention.get("confidence", ""), "argumentRoles": "|".join(roles),
                "eventRelevance": event_relevance,
                "argumentSpanStatuses": "|".join(sorted({str(arg.get("entityMatchStatus", "")) for arg in relevant_args})),
                "mentionOccursInEvidence": mention_in_evidence, "entityLinkStatus": result_status,
                "matchedUris": "|".join(result["matches"]), "matchedEntityTypes": "|".join("|".join(index[u]["types"]) for u in result["matches"]),
                "nearMatchUris": "|".join(x[0] for x in result["nearMatches"]), "reason": result_reason,
            })
            if result_status in {"MISSING_KG_ENTITY", "MISSING_ALIAS"}:
                key = (result_status, norm(mention.get("text")), mention.get("entityType"))
                gap = gaps.setdefault(key, {"gapType": result_status, "mentionText": mention.get("text", ""), "predictedEntityType": mention.get("entityType", ""),
                                            "candidateUris": "|".join(result["matches"] or [x[0] for x in result["nearMatches"]]),
                                            "mentionCount": 0, "eventIds": set(), "articleIds": set(), "priority": "LOW", "nextFactToVerify": ""})
                gap["mentionCount"] += 1; gap["eventIds"].add(event["eventId"]); gap["articleIds"].add(event["articleId"])
                if mention.get("entityType") in {"ORG", "PER"}:
                    gap["priority"] = "MEDIUM" if result_status == "MISSING_ALIAS" else "LOW"
                    gap["nextFactToVerify"] = "Verify official/canonical name or alias against issuer/regulator source before adding alias/entity to KG."

        event["entityLinkSuggestions"] = updated_suggestions
        # Existing EAE alignment is recorded separately; no argument is promoted to event truth here.
        for arg in event.get("arguments", []):
            if arg.get("entityMatchStatus") == "EXACT_SPAN" and (not arg.get("entityMention") or
                    (arg.get("role") == "Person" and arg.get("entityMention", {}).get("entityType") == "JOB")):
                reason = ("EAE Person argument aligns to EMD JOB type, which cannot identify a CorporateLeader."
                          if arg.get("entityMention") else "EAE exact span has no aligned EMD mention.")
                mention_rows.append({
                    "recordKind": "ARGUMENT", "articleId": event["articleId"], "eventId": event["eventId"],
                    "evidenceId": evidence_id, "sourceUrl": articles.get(str(event["articleId"]), {}).get("url", ""),
                    "eventType": event.get("eventType", ""), "evidenceText": evidence, "mentionText": arg.get("text", ""),
                    "predictedEntityType": (arg.get("entityMention") or {}).get("entityType", "UNALIGNED"),
                    "startChar": arg.get("startChar", ""), "endChar": arg.get("endChar", ""), "spanVerified": "",
                    "confidence": arg.get("confidence", ""), "argumentRoles": arg.get("role", ""),
                    "eventRelevance": "ARGUMENT_ALIGNMENT_ERROR", "argumentSpanStatuses": arg.get("entityMatchStatus", ""),
                    "mentionOccursInEvidence": bool(arg.get("text") and norm(arg["text"]) in norm(evidence)),
                    "entityLinkStatus": "ARGUMENT_LINKING_ERROR", "matchedUris": "", "matchedEntityTypes": "",
                    "nearMatchUris": "", "reason": reason,
                })
                key = ("ARGUMENT_LINKING_ERROR", norm(arg.get("text")), arg.get("role"))
                gap = gaps.setdefault(key, {"gapType": "ARGUMENT_LINKING_ERROR", "mentionText": arg.get("text", ""), "predictedEntityType": arg.get("role", ""), "candidateUris": "", "mentionCount": 0,
                                            "eventIds": set(), "articleIds": set(), "priority": "LOW", "nextFactToVerify": "Inspect EAE span-to-EMD alignment; do not create KG facts."})
                gap["mentionCount"] += 1; gap["eventIds"].add(event["eventId"]); gap["articleIds"].add(event["articleId"])
                gap["nextFactToVerify"] = reason + " Keep the argument unresolved until the span/type is corrected."

    # Persist only derived resolver suggestions in review staging; main KG remains untouched.
    staging_path.write_text(json.dumps(events, indent=2, ensure_ascii=False) + "\n", encoding="utf8")

    links_by_event: dict[str, list[dict]] = defaultdict(list)
    mention_row_by_event: dict[str, list[dict]] = defaultdict(list)
    for event in events:
        links_by_event[event["eventId"]] = event.get("entityLinkSuggestions", [])
    for row in mention_rows:
        mention_row_by_event[row["eventId"]].append(row)

    path_rows = []
    for event in events:
        article = articles.get(str(event["articleId"]), {})
        eff_day = parse_date(event.get("effectiveTradingDate"))
        event_available = parse_datetime(event.get("availableAt"))
        suggestions = event.get("entityLinkSuggestions", [])
        mention_map = {id(s["mention"]): s for s in suggestions}
        args = event.get("arguments", [])
        by_path_participant = {"Company": [], "CorporateLeader": [], "Industry": []}
        linked_entities = []
        for suggestion in suggestions:
            mention = suggestion.get("mention", {})
            if suggestion.get("status") != "MATCHED" or len(suggestion.get("matches", [])) != 1:
                continue
            uri = suggestion["matches"][0]["uri"]
            types = set(suggestion["matches"][0]["type"])
            role_rows = [arg for arg in args if norm(arg.get("text")) == norm(mention.get("text"))
                         or ((arg.get("entityMention") or {}).get("startChar") == mention.get("startChar") and (arg.get("entityMention") or {}).get("endChar") == mention.get("endChar"))]
            roles = {str(arg.get("role", "")) for arg in role_rows}
            ticker_prefix = bool(mention.get("text") and evidence_starts_with_entity(event.get("evidence", {}).get("evidenceText", ""), mention.get("text")))
            in_evidence = bool(mention.get("text") and norm(mention.get("text")) in norm(event.get("evidence", {}).get("evidenceText", "")))
            if not in_evidence:
                continue
            support = ""
            participant_kind = None
            if "CorporateLeader" in types and "Person" in roles:
                participant_kind = "CorporateLeader"; support = "EAE Person span aligned to EMD PER mention in Event Evidence"
            elif types & {"Company", "Bank"} and (roles & ROLE_COMPANY):
                participant_kind = "Company"; support = "EAE Entity/Org span aligned to EMD ORG mention in Event Evidence"
            elif types & {"Company", "Bank"} and ticker_prefix:
                participant_kind = "Company"; support = "Company ticker/name occurs as explicit Evidence subject prefix before colon"
            elif "Industry" in types and (roles & ROLE_COMPANY):
                participant_kind = "Industry"; support = "EAE entity span aligned to explicit Industry name in Event Evidence"
            if participant_kind:
                by_path_participant[participant_kind].append({"uri": uri, "mention": mention, "roles": sorted(roles), "support": support})
            linked_entities.append({"uri": uri, "mention": mention, "types": sorted(types), "roles": sorted(roles), "tickerPrefix": ticker_prefix, "inEvidence": in_evidence})

        for path_name in PATHS:
            row = {"articleId": event["articleId"], "eventId": event["eventId"], "evidenceId": event.get("evidence", {}).get("evidenceId", ""),
                   "sourceUrl": article.get("url", ""), "eventType": event.get("eventType", ""), "effectiveTradingDate": event.get("effectiveTradingDate", ""),
                   "path": path_name, "pathStatus": "NO_ENTITY", "eventToEntityEvidence": "", "entityUri": "", "intermediateNodeUris": "", "candidateStockUris": "",
                   "missingRelationships": "", "temporalCondition": "", "reason": "", "reviewRequired": True}
            evidence_txt = str(event.get("evidence", {}).get("evidenceText", ""))
            if path_name == "DIRECT":
                participants = by_path_participant["Company"]
                if not participants:
                    linked_company = [x for x in linked_entities if set(x["types"]) & {"Company", "Bank"}]
                    row["pathStatus"] = "INSUFFICIENT_EVIDENCE" if linked_company else "NO_ENTITY"
                    row["entityUri"] = "|".join(x["uri"] for x in linked_company)
                    row["reason"] = "Company/Bank mention exists but is not aligned to an event Entity/Org argument or explicit evidence subject prefix." if linked_company else "No uniquely linked, event-relevant Company/Bank entity in the Event Evidence."
                else:
                    stock_uris, companies = set(), set()
                    for part in participants:
                        companies.add(part["uri"])
                        stock_uris.update(str(x) for x in g.objects(URIRef(part["uri"]), W.hasStock))
                    if not stock_uris:
                        row["pathStatus"] = "MISSING_RELATION"; row["missingRelationships"] = "Company --hasStock--> Stock"; row["reason"] = "Event-supported company has no hasStock edge in KG."
                    else:
                        row["pathStatus"] = "MATCHED"; row["candidateStockUris"] = "|".join(sorted(stock_uris)); row["reason"] = "Event-linked company is supported by Event Evidence and has a direct KG stock link."
                        row["temporalCondition"] = "Company-hasStock has no validFrom/validTo in ontology; Stock identity resolved. Observation on effectiveTradingDate: " + json.dumps({s: stock_obs_at(g, URIRef(s), eff_day) for s in sorted(stock_uris)}, ensure_ascii=False)
                    row["entityUri"] = "|".join(sorted(companies)); row["eventToEntityEvidence"] = event_support_text(participants, evidence_txt)
            elif path_name == "INDIRECT_SUBSIDIARY":
                participants = by_path_participant["Company"]
                if not participants:
                    linked_company = [x for x in linked_entities if set(x["types"]) & {"Company", "Bank"}]
                    row["pathStatus"] = "INSUFFICIENT_EVIDENCE" if linked_company else "NO_ENTITY"
                    row["entityUri"] = "|".join(x["uri"] for x in linked_company)
                    row["reason"] = "No event-supported subsidiary mention; linked company references alone do not establish this event path." if linked_company else "No uniquely linked event-relevant Company/Bank mention."
                else:
                    rels = [(part, rel) for part in participants for rel in g.subjects(W.subsidiaryCompany, URIRef(part["uri"]))]
                    if not rels:
                        row["pathStatus"] = "NOT_APPLICABLE"; row["entityUri"] = "|".join(sorted({p["uri"] for p in participants})); row["reason"] = "Event-supported company is not the subsidiaryCompany in any current KG SubsidiaryRelation."
                    else:
                        candidates, relation_uris, temporal_notes, parents = set(), set(), [], set()
                        statuses = []
                        for part, rel in rels:
                            relation_uris.add(str(rel)); parents.update(str(x) for x in g.objects(rel, W.parentCompany))
                            active_status, note = active_for_event(g, rel, eff_day, event_available, snapshot_only=True); statuses.append(active_status); temporal_notes.append(str(rel)+": "+note)
                            if active_status == "MATCHED":
                                for parent in g.objects(rel, W.parentCompany): candidates.update(str(x) for x in g.objects(parent, W.hasStock))
                        if candidates and all(s == "MATCHED" for s in statuses):
                            row["pathStatus"] = "MATCHED"; row["candidateStockUris"] = "|".join(sorted(candidates)); row["reason"] = "Event-supported subsidiary, temporally supported SubsidiaryRelation, parent, and Stock links are present."
                        else:
                            row["pathStatus"] = "INSUFFICIENT_EVIDENCE"; row["reason"] = "Subsidiary relation exists, but its observedAsOf snapshot does not establish continued validity at the Event date (or required relation/stock edge is absent)."
                        row["entityUri"] = "|".join(sorted({p["uri"] for p in participants})); row["intermediateNodeUris"] = "relations="+"|".join(sorted(relation_uris))+";parents="+"|".join(sorted(parents)); row["candidateStockUris"] = row["candidateStockUris"] or ""
                        row["temporalCondition"] = " || ".join(temporal_notes); row["eventToEntityEvidence"] = event_support_text([p for p, _ in rels], evidence_txt)
            elif path_name == "INDIRECT_LEADERSHIP":
                participants = by_path_participant["CorporateLeader"]
                if not participants:
                    linked_leaders = [x for x in linked_entities if "CorporateLeader" in x["types"]]
                    row["pathStatus"] = "INSUFFICIENT_EVIDENCE" if linked_leaders else "NO_ENTITY"
                    row["entityUri"] = "|".join(x["uri"] for x in linked_leaders)
                    row["reason"] = "A leader is linked but not aligned to an EAE Person role in Event Evidence." if linked_leaders else "No uniquely linked, event-relevant CorporateLeader mention."
                else:
                    active = []; known_positions = []; temporal_notes = []; companies = set()
                    event_companies = {p["uri"] for p in by_path_participant["Company"]}
                    for part in participants:
                        for pos in g.objects(URIRef(part["uri"]), W.hasLeadershipPosition):
                            known_positions.append(str(pos)); company = next(iter(g.objects(pos, W.positionAtCompany)), None)
                            if company is None: continue
                            temporal_status, note = active_for_event(g, pos, eff_day, event_available)
                            temporal_notes.append(str(pos)+": "+note)
                            if temporal_status == "MATCHED" and (not event_companies or str(company) in event_companies):
                                active.append((part, pos, company)); companies.add(str(company))
                    stocks = {str(stock) for _, _, company in active for stock in g.objects(URIRef(company), W.hasStock)}
                    if not known_positions:
                        row["pathStatus"] = "MISSING_RELATION"; row["missingRelationships"] = "CorporateLeader --hasLeadershipPosition--> LeadershipPosition"; row["reason"] = "No LeadershipPosition relation for the linked, event-supported leader."
                    elif active and stocks:
                        row["pathStatus"] = "MATCHED" if len(stocks) == 1 else "AMBIGUOUS"
                        row["candidateStockUris"] = "|".join(sorted(stocks)) if len(stocks) == 1 else ""
                        row["reason"] = "Effective, available LeadershipPosition reaches a Company Stock." if len(stocks) == 1 else "Multiple companies/stocks are reached; evidence does not disambiguate the leader's event affiliation."
                    else:
                        row["pathStatus"] = "INSUFFICIENT_EVIDENCE"; row["reason"] = "Position exists but is not effective/available at event cutoff, or event-supported company context does not match the position company."
                    row["entityUri"] = "|".join(sorted({p["uri"] for p in participants})); row["intermediateNodeUris"] = "positions="+"|".join(sorted(set(known_positions)))+";companies="+"|".join(sorted(companies)); row["temporalCondition"] = " || ".join(temporal_notes)
                    row["eventToEntityEvidence"] = event_support_text(participants, evidence_txt)
                    row["missingRelationships"] = row["missingRelationships"] or ("Company --hasStock--> Stock" if active and not stocks else "")
            else:  # INDIRECT_INDUSTRY
                participants = by_path_participant["Industry"]
                if not participants:
                    linked_industries = [x for x in linked_entities if "Industry" in x["types"]]
                    row["pathStatus"] = "INSUFFICIENT_EVIDENCE" if linked_industries else "NO_ENTITY"
                    row["entityUri"] = "|".join(x["uri"] for x in linked_industries)
                    row["reason"] = "No event-supported explicit Industry mention; a company's ordinary industry exposure cannot be assumed to be this Event's industry." if not linked_industries else "Industry mention exists but lacks event Entity/Org argument support."
                else:
                    exposures = [(part, exposure) for part in participants for exposure in g.subjects(W.exposureIndustry, URIRef(part["uri"]))]
                    statuses = []; temporal_notes = []; banks = set(); candidates = set(); exposure_uris = set()
                    for part, exposure in exposures:
                        exposure_uris.add(str(exposure)); bank = next(iter(g.objects(exposure, W.exposureBank)), None)
                        if bank is None: continue
                        status, note = active_for_event(g, exposure, eff_day, event_available, snapshot_only=True); statuses.append(status); temporal_notes.append(str(exposure)+": "+note); banks.add(str(bank))
                        if status == "MATCHED": candidates.update(str(stock) for stock in g.objects(bank, W.hasStock))
                    if not exposures:
                        row["pathStatus"] = "MISSING_RELATION"; row["missingRelationships"] = "Industry <- IndustryExposure <- Bank --hasStock--> Stock"; row["reason"] = "Event-supported Industry has no exposure path in KG."
                    elif candidates and statuses and all(s == "MATCHED" for s in statuses):
                        row["pathStatus"] = "MATCHED"; row["candidateStockUris"] = "|".join(sorted(candidates)); row["reason"] = "Event-supported Industry connects through temporally supported exposure to Bank Stock."
                    else:
                        row["pathStatus"] = "INSUFFICIENT_EVIDENCE"; row["reason"] = "IndustryExposure is a period snapshot and does not establish exposure validity at the Event date."
                    row["entityUri"] = "|".join(sorted({p["uri"] for p in participants})); row["intermediateNodeUris"] = "exposures="+"|".join(sorted(exposure_uris))+";banks="+"|".join(sorted(banks)); row["temporalCondition"] = " || ".join(temporal_notes); row["eventToEntityEvidence"] = event_support_text(participants, evidence_txt)
            path_rows.append(row)

    mention_fields = ["recordKind", "articleId", "eventId", "evidenceId", "sourceUrl", "eventType", "evidenceText", "mentionText", "predictedEntityType", "startChar", "endChar", "spanVerified", "confidence", "argumentRoles", "eventRelevance", "argumentSpanStatuses", "mentionOccursInEvidence", "entityLinkStatus", "matchedUris", "matchedEntityTypes", "nearMatchUris", "reason"]
    path_fields = ["articleId", "eventId", "evidenceId", "sourceUrl", "eventType", "effectiveTradingDate", "path", "pathStatus", "entityUri", "intermediateNodeUris", "candidateStockUris", "missingRelationships", "eventToEntityEvidence", "temporalCondition", "reason", "reviewRequired"]
    dump_csv(RUN / "entity_linking_audit.csv", mention_rows, mention_fields)
    dump_csv(RUN / "event_path_coverage.csv", path_rows, path_fields)
    gap_rows = []
    for gap in gaps.values():
        item = dict(gap); item["eventIds"] = "|".join(sorted(item["eventIds"])); item["articleIds"] = "|".join(sorted(item["articleIds"]))
        item["eventCount"] = len(item["eventIds"].split("|")) if item["eventIds"] else 0
        gap_rows.append(item)
    for row in path_rows:
        if row["pathStatus"] == "MISSING_RELATION" or (row["pathStatus"] == "INSUFFICIENT_EVIDENCE" and ("observedAsOf" in row["temporalCondition"] or "periodEnd" in row["temporalCondition"])):
            key = ("PATH_BLOCKER", row["path"], row["missingRelationships"] or row["reason"])
            item = gaps.setdefault(key, {"gapType": "MISSING_KG_RELATION" if row["pathStatus"] == "MISSING_RELATION" else "INSUFFICIENT_EVIDENCE",
                                         "mentionText": row["path"], "predictedEntityType": "PATH", "candidateUris": row["entityUri"], "mentionCount": 0,
                                         "eventIds": set(), "articleIds": set(), "priority": "HIGH" if row["path"] in {"DIRECT", "INDIRECT_SUBSIDIARY", "INDIRECT_LEADERSHIP"} else "LOW",
                                         "nextFactToVerify": row["missingRelationships"] or row["reason"]})
            item["mentionCount"] += 1; item["eventIds"].add(row["eventId"]); item["articleIds"].add(row["articleId"])
    gap_rows = []
    for gap in gaps.values():
        item = dict(gap); ev_ids=item.pop("eventIds"); art_ids=item.pop("articleIds"); item["eventIds"]="|".join(sorted(ev_ids)); item["articleIds"]="|".join(sorted(art_ids)); item["eventCount"]=len(ev_ids); item["articleCount"]=len(art_ids)
        gap_rows.append(item)
    dump_csv(RUN / "kg_missing_facts.csv", gap_rows, ["gapType", "mentionText", "predictedEntityType", "candidateUris", "mentionCount", "eventCount", "articleCount", "eventIds", "articleIds", "priority", "nextFactToVerify"])

    link_counts = Counter(row["entityLinkStatus"] for row in mention_rows)
    path_counts = {path: Counter(row["pathStatus"] for row in path_rows if row["path"] == path) for path in PATHS}
    event_path_status = defaultdict(list)
    for row in path_rows: event_path_status[row["eventId"]].append(row["pathStatus"])
    events_with_path = sum(any(status == "MATCHED" for status in statuses) for statuses in event_path_status.values())
    path_candidates = {path: sum(1 for row in path_rows if row["path"] == path and row["pathStatus"] == "MATCHED") for path in PATHS}
    improved = max(0, link_counts.get("MATCHED", 0) - int(original_matched_count or 0))
    type_counts = Counter(entity_type for entity in index.values() for entity_type in entity["types"])
    aliases = sum(1 for s in g.subjects(RDF.type, W.CompanyAlias))
    relation_inventory = {
        "Company_hasStock": sum(1 for _ in g.triples((None, W.hasStock, None))),
        "Company_hasSubsidiaryRelation": sum(1 for _ in g.triples((None, W.hasSubsidiaryRelation, None))),
        "SubsidiaryRelation_count": sum(1 for _ in g.subjects(RDF.type, W.SubsidiaryRelation)),
        "LeadershipPosition_count": sum(1 for _ in g.subjects(RDF.type, W.LeadershipPosition)),
        "IndustryExposure_count": sum(1 for _ in g.subjects(RDF.type, W.IndustryExposure)),
        "eventParticipantLinks_in_base_KG": sum(1 for predicate in (W.involvesCompany, W.involvesLeader, W.relatedToIndustry) for _ in g.triples((None, predicate, None))),
    }
    summary = {
        "ontologyVersion": "1.0.5", "ontologyFile": "schema/ontology.ttl", "shapesFile": "schema/shapes.ttl",
        "eventCount": len(events), "mentionCount": len([r for r in mention_rows if r.get("recordKind") != "ARGUMENT"]),
        "auditRowCount": len(mention_rows), "mentionStatusCounts": dict(link_counts),
        "eventPathStatusCounts": {path: dict(count) for path, count in path_counts.items()},
        "eventsWithAtLeastOneSufficientPath": events_with_path, "eventsWithoutSufficientPath": len(events) - events_with_path,
        "candidateCountByPath": path_candidates, "entityLinksImprovedVsPriorUniqueCount": improved,
        "kgEntityCountsByType": dict(type_counts), "kgCompanyAliasCount": aliases, "kgRelationInventory": relation_inventory,
        "baseKgTriples": len(g), "mainKgModified": False, "modelsRun": False, "newsCrawled": False,
        "notes": ["All Event-to-entity associations remain review proposals supported by aligned spans or explicit ticker prefix in Evidence; no EventStockCandidate or relation was inserted into the main KG.",
                  "Temporal checks use effectiveTradingDate, availableAt <= Event.availableAt, and explicit validFrom/validTo. observedAsOf is treated as a snapshot, not as validFrom.",
                  "CompanyAlias and Unicode/accent/punctuation/legal-prefix normalization are read from existing KG facts only. Fuzzy matches are surfaced for review, never auto-linked."]
    }
    (RUN / "entity_linking_report.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf8")
    write_report(summary, path_rows, mention_rows, gap_rows)
    return summary


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf8").splitlines() if line.strip()]


def evidence_starts_with_entity(evidence: object, surface: object) -> bool:
    text = str(evidence or "").lstrip(" \t\r\n\ufeff")
    start = norm(str(surface or ""))
    lead = norm(text.split(":", 1)[0]) if ":" in text else ""
    return bool(start and lead == start)


def event_support_text(participants: list[dict], evidence: str) -> str:
    return " | ".join(f"{p['mention'].get('text','')} [{p['support']}] Evidence='{evidence[:500]}'" for p in participants)


def write_report(summary: dict, path_rows: list[dict], mention_rows: list[dict], gaps: list[dict]):
    matched_paths = summary["candidateCountByPath"]
    lines = [
        "# Entity Linking and Event–Stock Path Audit", "",
        f"- Schema: ontology/shapes v{summary['ontologyVersion']} (`schema/ontology.ttl`, `schema/shapes.ttl`).",
        f"- Staged Events: {summary['eventCount']}; entity mentions: {summary['mentionCount']}; mentions matched after safe normalization: {summary['mentionStatusCounts'].get('MATCHED',0)}.",
        f"- Events with at least one evidence-supported, temporally sufficient path: {summary['eventsWithAtLeastOneSufficientPath']}/{summary['eventCount']}; without a sufficient path: {summary['eventsWithoutSufficientPath']}/{summary['eventCount']}.",
        "- Complete path rows (review candidates, not KG insertions): " + ", ".join(f"{path}={count}" for path, count in matched_paths.items()) + ".",
        f"- Unambiguous/normalized entity links added versus old LINKED_UNIQUE baseline: {summary['entityLinksImprovedVsPriorUniqueCount']}.",
        f"- KG entities by type: {summary['kgEntityCountsByType']}; CompanyAlias resources: {summary['kgCompanyAliasCount']}; relation inventory: {summary['kgRelationInventory']}.",
        "- Main KG unchanged; no EventStockCandidate, AR, or CAR was created.", "",
        "## Path blockers", "",
    ]
    for path in PATHS:
        counts = summary["eventPathStatusCounts"][path]
        lines.append(f"- **{path}**: " + ", ".join(f"{status}={count}" for status, count in sorted(counts.items())) + ".")
    lines += ["", "## Main findings", "",
              "- Event-to-entity relations are not present in the base KG. A path is counted MATCHED only when an existing KG endpoint chain and event evidence support the participant; all outputs remain review proposals.",
              "- The direct `Company → hasStock → Stock` KG chain is available for the listed entities. For subsidiary/leadership/industry paths, the event-specific relation and temporal interval are the main gates.",
              "- SubsidiaryRelation facts marked `observedAsOf` are point-in-time observations, not start dates; the ontology comments prohibit treating them as indefinitely valid.",
              "- IndustryExposure records describe reporting-period snapshots. They do not by themselves establish that every later Event is industry-related or that the exposure persists at the Event date.",
              "- CompanyAlias and conservative Unicode/accent/punctuation/legal-prefix normalization are used. Similarity-only candidates remain `MISSING_ALIAS` for review.",
              "", "## Data additions to prioritize", "",
              "1. **High:** source-supported event-to-company/leader arguments and event-specific links, because they gate direct and leadership candidates.",
              "2. **High:** explicit `validFrom`/`validTo` or a current observation for subsidiaries involved in staged events.",
              "3. **Medium:** missing CompanyAlias facts where the mention closely matches an existing KG entity; verify against issuer/regulator materials.",
              "4. **Low:** current, source-backed IndustryExposure periods and explicit event–industry evidence; do not infer industry relevance from a bank's general exposure alone.",
              "5. Add missing leaders/companies only after official source verification; PhoBERT mentions are not ground truth.",
              "", "## Artifacts", "", "- `entity_linking_audit.csv`: per mention, article/event/evidence/source, spans/roles, URIs and reason.",
              "- `event_path_coverage.csv`: 155 Events × four paths with node URIs, evidence, temporal conditions, blockers and candidate stocks.",
              "- `kg_missing_facts.csv`: grouped potential entity/alias/path facts and verification work.",
              "- `entity_linking_report.json`: machine-readable counts.", ""]
    (RUN / "entity_linking_report.md").write_text("\n".join(lines), encoding="utf8")


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False))
