"""Re-audit saved ED/EMD/EAE output with evidence-aware URI and argument linking."""
from __future__ import annotations

import csv
import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from rdflib import Graph, Namespace, RDF, URIRef

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from wfkg.event_processing.kg_entity_resolution import build_index, resolve_mention, argument_compatibility
from wfkg.event_processing.text_input import prepare_extraction_input
import audit_vertical_slice_entity_paths as old_audit

RUN = ROOT / "runs/news_event_vertical_slice_20261019"
OUT = RUN / "entity_linking_v2"
KG = ROOT / "data/gold/knowledge_graph.ttl"
W = Namespace("https://example.org/wfkg/v1#")
PATHS = ("DIRECT", "INDIRECT_SUBSIDIARY", "INDIRECT_LEADERSHIP", "INDIRECT_INDUSTRY")
COMPANY_ROLES = {"Entity", "Org", "Organization", "Beneficiary", "Buyer", "Seller", "Giver", "Recipient"}
EVENT_ROLES = {
    "Nominate": {"Person", "Position", "Time", "Entity", "Org"},
    "Elect": {"Person", "Time", "Entity", "Org"},
    "Start-position": {"Person", "Position", "Time", "Entity", "Org"},
    "End-position": {"Person", "Position", "Time", "Entity", "Org"},
    "Transfer-ownership": {"Entity", "Org", "Person", "Money", "Time", "Destination"},
    "Transfer-money": {"Entity", "Org", "Person", "Money", "Time"},
    "Start-org": {"Org", "Entity", "Time"},
    "Meet": {"Entity", "Person", "Time"},
    "Transport": {"Destination", "Entity", "Person", "Time"},
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_csv(path: Path, rows: list[dict], fields: list[str]):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def event_evidence_bounds(text: str, event: dict) -> tuple[int | None, int | None]:
    trigger = event.get("trigger", {})
    ts, te = trigger.get("startChar"), trigger.get("endChar")
    evidence = str(event.get("evidence", {}).get("evidenceText", ""))
    if not isinstance(ts, int) or not evidence:
        return None, None
    starts, cursor = [], 0
    while True:
        found = text.find(evidence, cursor)
        if found < 0:
            break
        if found <= ts and ts + len(str(trigger.get("text", ""))) <= found + len(evidence):
            starts.append(found)
        cursor = found + 1
    if not starts:
        return None, None
    start = min(starts, key=lambda value: abs((ts - value) - evidence.find(str(trigger.get("text", "")))))
    return start, start + len(evidence)


def verified_span(text: str, item: dict, text_key: str = "text") -> bool:
    start, end, surface = item.get("startChar"), item.get("endChar"), str(item.get(text_key, ""))
    return isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(text) and text[start:end] == surface


def sentence_bounds(text: str, start: int, end: int) -> tuple[int, int]:
    # Conservative sentence boundary approximation; punctuation/newline are retained in span.
    left = max(text.rfind(mark, 0, start) for mark in (".", "?", "!", ";", "\n"))
    right_options = [p for mark in (".", "?", "!", ";", "\n") if (p := text.find(mark, end)) >= 0]
    return left + 1, (min(right_options) + 1) if right_options else len(text)


def same_trigger_sentence(text: str, start: int, end: int, trigger: dict) -> bool:
    ts, te = trigger.get("startChar"), trigger.get("endChar")
    if not isinstance(ts, int) or not isinstance(te, int):
        return False
    return sentence_bounds(text, start, end) == sentence_bounds(text, ts, te)


def nearest_trigger_event_ids(text: str, start: int, end: int, trigger_rows: list[dict]) -> list[str]:
    sentence = sentence_bounds(text, start, end)
    candidates = [row for row in trigger_rows if row["sentence"] == sentence]
    distances = [(max(0, max(row["trigger"]["startChar"] - end,
                             start - row["trigger"]["endChar"])), row["eventId"])
                 for row in candidates]
    closest = min((distance for distance, _ in distances), default=None)
    return [event_id for distance, event_id in distances if distance == closest] if closest is not None else []


def event_role_compatible(event_type: str, role: str) -> bool:
    return role in EVENT_ROLES.get(event_type, set())


def argument_is_conditioned_on_event(argument: dict, event_id: str, trigger: dict) -> bool:
    """Use explicit EAE trigger conditioning when present; distance is legacy-only."""
    conditioned_span = argument.get("conditionedOnTriggerSpan") or {}
    return (argument.get("triggerConditioned") is True
            and argument.get("conditionedOnEventId") == event_id
            and conditioned_span.get("startChar") == trigger.get("startChar")
            and conditioned_span.get("endChar") == trigger.get("endChar"))


def participants_from_linked_arguments(accepted_arguments: list[dict]) -> dict[str, list[dict]]:
    """A resolved in-document entity is not a participant without linked argument evidence."""
    participants = {"Company": [], "CorporateLeader": [], "Industry": []}
    for row in accepted_arguments:
        types = set(row["types"])
        role = row["argument"].get("role")
        if role == "Person" and "CorporateLeader" in types:
            participants["CorporateLeader"].append(row)
        elif role in COMPANY_ROLES and types & {"Company", "Bank"}:
            participants["Company"].append(row)
        elif role in COMPANY_ROLES and "Industry" in types:
            participants["Industry"].append(row)
    return participants


def align_argument_span(argument: dict, mentions_by_span: dict, event_type: str,
                        evidence_start: int, evidence_end: int) -> tuple[dict | None, str]:
    """Align exact EAE/EMD offsets, or one compatible strict containment only."""
    start, end = argument.get("startChar"), argument.get("endChar")
    if not isinstance(start, int) or not isinstance(end, int) or not (evidence_start <= start < end <= evidence_end):
        return None, ""
    exact = mentions_by_span.get((start, end))
    if exact:
        return exact, "EXACT_SPAN"
    if argument.get("role") not in (COMPANY_ROLES | {"Person"}):
        return None, ""
    possible = []
    for (mention_start, mention_end), row in mentions_by_span.items():
        if mention_start < evidence_start or mention_end > evidence_end:
            continue
        inside = (mention_start <= start < end <= mention_end) or (start <= mention_start < mention_end <= end)
        compatible, _ = argument_compatibility(event_type, str(argument.get("role", "")),
                                                str(row["mention"].get("entityType", "")))
        if inside and compatible:
            possible.append(row)
    return (possible[0], "UNIQUE_NESTED_SPAN") if len(possible) == 1 else (None, "")


def disambiguate_leader_by_linked_company(graph: Graph, candidates: list[str], company_uris: set[str],
                                          event_day: date | None, event_available) -> str | None:
    """Resolve a leader collision only through an active KG position and a linked event company."""
    supported = set()
    for leader in candidates:
        for position in graph.objects(URIRef(leader), W.hasLeadershipPosition):
            company = next(iter(graph.objects(position, W.positionAtCompany)), None)
            if company is None or str(company) not in company_uris:
                continue
            status, _ = old_audit.active_for_event(graph, position, event_day, event_available)
            if status == "MATCHED":
                supported.add(leader)
    return next(iter(supported)) if len(supported) == 1 else None


def main(staging_path: Path = RUN / "staging_review.json", out_dir: Path = OUT) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    graph = Graph().parse(KG)
    entity_index, key_index = build_index(graph, ROOT / "data/external/verified_entity_aliases.json")
    events = read_json(staging_path)
    articles = {str(x["articleId"]): x for x in read_jsonl(ROOT / "data/cleaned/news_100_v1/clean_articles.jsonl")}
    enriched = {str(x["articleId"]): x for x in read_jsonl(ROOT / "data/enriched_cleaned/news_100_v1/articles.jsonl")}
    prepared = {aid: prepare_extraction_input(article, enriched.get(aid)).text for aid, article in articles.items()}

    # Candidate ED triggers by article/sentence, used to avoid attaching one EAE span to every event.
    trigger_rows = defaultdict(list)
    for event in events:
        aid = str(event["articleId"])
        trigger = event.get("trigger", {})
        if verified_span(prepared.get(aid, ""), trigger):
            trigger_rows[aid].append({"eventId": event["eventId"], "trigger": trigger,
                                      "sentence": sentence_bounds(prepared[aid], trigger["startChar"], trigger["endChar"])})

    mention_rows, argument_rows, gaps = [], [], {}
    resolution_by_event = {}
    accepted_arguments = {}
    event_evidence_verification = Counter()
    for event in events:
        aid, event_id = str(event["articleId"]), str(event["eventId"])
        article, text = articles.get(aid, {}), prepared.get(aid, "")
        evidence = str(event.get("evidence", {}).get("evidenceText", ""))
        evidence_start, evidence_end = event_evidence_bounds(text, event)
        ev_ok = evidence_start is not None and evidence_end is not None
        trigger = event.get("trigger", {})
        trigger_ok = verified_span(text, trigger) and ev_ok and evidence_start <= trigger["startChar"] and trigger["endChar"] <= evidence_end
        event_evidence_verification["VERIFIED"] += int(bool(trigger_ok))
        event_evidence_verification["FAILED"] += int(not trigger_ok)
        event_day = old_audit.parse_date(event.get("effectiveTradingDate"))
        event_available = old_audit.parse_datetime(event.get("availableAt"))
        preliminary = {}
        for mention in event.get("entities", []):
            ms, me = mention.get("startChar"), mention.get("endChar")
            if verified_span(text, mention) and ev_ok and evidence_start <= ms < me <= evidence_end:
                preliminary[(ms, me)] = resolve_mention(mention, entity_index, key_index, context=text)
        linked_company_context = set()
        for arg in event.get("arguments", []):
            astart, aend = arg.get("startChar"), arg.get("endChar")
            if arg.get("role") not in COMPANY_ROLES or not isinstance(astart, int) or not isinstance(aend, int):
                continue
            if not verified_span(text, arg) or not ev_ok or not (evidence_start <= astart < aend <= evidence_end):
                continue
            company_result = preliminary.get((astart, aend))
            if company_result and company_result.get("status") == "MATCHED" and set(entity_index[company_result["uri"]]["types"]) & {"Company", "Bank"}:
                if (argument_is_conditioned_on_event(arg, event_id, trigger)
                        or nearest_trigger_event_ids(text, astart, aend, trigger_rows[aid]) == [event_id]):
                    linked_company_context.add(company_result["uri"])
        links, accepted = [], []
        mentions_by_span = {}
        mentions_by_id = {}

        for mention in event.get("entities", []):
            start, end = mention.get("startChar"), mention.get("endChar")
            span_ok = verified_span(text, {**mention, "text": mention.get("text", "")})
            evidence_ok = span_ok and ev_ok and evidence_start <= start < end <= evidence_end
            result = preliminary.get((start, end))
            if result is None:
                result = resolve_mention(mention, entity_index, key_index, context=text)
            person_argument = any(arg.get("role") == "Person" and arg.get("startChar") == start and arg.get("endChar") == end
                                  and arg.get("entityMatchStatus") == "EXACT_SPAN" for arg in event.get("arguments", []))
            if result["status"] == "AMBIGUOUS" and mention.get("entityType") == "PER" and person_argument and linked_company_context:
                candidate_uris = [candidate for candidate in result["candidates"] if isinstance(candidate, str)]
                selected = disambiguate_leader_by_linked_company(graph, candidate_uris, linked_company_context, event_day, event_available)
                if selected:
                    result = {"status": "MATCHED", "uri": selected, "candidates": candidate_uris,
                              "method": "KG_ACTIVE_LEADERSHIP_AND_ARGUMENT_CONTEXT",
                              "reason": "Exact Person argument and active KG position uniquely connect the candidate to a separately linked Event company."}
            if not trigger_ok or not evidence_ok:
                result = {"status": "UNRESOLVED", "uri": None, "candidates": result.get("candidates", []),
                          "method": None, "reason": "Mention/trigger/evidence offsets do not verify inside the same event evidence span."}
            link = {"mention": mention, **result, "spanVerified": span_ok, "evidenceSpanVerified": evidence_ok}
            links.append(link)
            if isinstance(start, int) and isinstance(end, int):
                mentions_by_span[(start, end)] = link
            if mention.get("mentionId"):
                mentions_by_id[str(mention["mentionId"])] = link
            mention_rows.append({
                "recordKind": "ENTITY_MENTION", "articleId": aid, "eventId": event_id,
                "evidenceId": event.get("evidence", {}).get("evidenceId", ""), "sourceUrl": article.get("url", ""),
                "eventType": event.get("eventType", ""), "triggerText": trigger.get("text", ""),
                "triggerStart": trigger.get("startChar", ""), "triggerEnd": trigger.get("endChar", ""),
                "evidenceText": evidence, "mentionText": mention.get("text", ""), "mentionType": mention.get("entityType", ""),
                "startChar": start, "endChar": end, "spanVerified": span_ok, "evidenceSpanVerified": evidence_ok,
                "mentionDetectionStatus": "VERIFIED" if span_ok and evidence_ok else ("SPAN_ERROR" if not span_ok else "OUTSIDE_EVENT_EVIDENCE"),
                "confidence": mention.get("confidence", ""), "resolutionStatus": result["status"],
                "resolvedUri": result.get("uri") or "", "resolutionMethod": result.get("method") or "",
                "candidateUris": "|".join(row.get("uri", "") for row in result.get("candidates", [])) if result["status"] == "UNRESOLVED" else "|".join(result.get("candidates", [])),
                "candidateEvidence": json.dumps(result.get("candidates", []), ensure_ascii=False), "reason": result["reason"],
            })

        # EAE arguments link only to the exact EMD span, compatible role/type, and nearest ED trigger.
        other_triggers = trigger_rows[aid]
        for arg in event.get("arguments", []):
            start, end = arg.get("startChar"), arg.get("endChar")
            span_ok = verified_span(text, arg)
            in_event_evidence = span_ok and ev_ok and evidence_start <= start < end <= evidence_end
            mention_id = arg.get("entityMentionId") or (arg.get("entityMention") or {}).get("mentionId")
            direct_mention = mentions_by_id.get(str(mention_id)) if mention_id else None
            direct_surface = (direct_mention or {}).get("mention", {})
            direct_id_verified = (direct_mention is not None
                                  and direct_surface.get("startChar") == start
                                  and direct_surface.get("endChar") == end
                                  and direct_surface.get("text") == arg.get("text"))
            if direct_id_verified and span_ok and in_event_evidence:
                mention_link, alignment_method = direct_mention, "MENTION_ID_REFERENCE"
            else:
                mention_link, alignment_method = align_argument_span(
                    arg, mentions_by_span, str(event.get("eventType", "")),
                    evidence_start if evidence_start is not None else -1,
                    evidence_end if evidence_end is not None else -1,
                ) if span_ok and in_event_evidence else (None, "")
            mention_type = str((mention_link or {}).get("mention", {}).get("entityType", ""))
            aligned = mention_link is not None
            compatible, type_reason = argument_compatibility(str(event.get("eventType", "")), str(arg.get("role", "")), mention_type)
            if "entityTypeObservedForRoleInBkeeTrain" in arg:
                compatible = bool(arg.get("entityTypeObservedForRoleInBkeeTrain"))
                type_reason = ("Entity type/argument role combination was observed in BKEE train."
                               if compatible else "Entity type/argument role combination was not observed in BKEE train.")
            event_role_ok = bool(arg.get("eventRoleObservedInBkeeTrain")) if "eventRoleObservedInBkeeTrain" in arg else event_role_compatible(str(event.get("eventType", "")), str(arg.get("role", "")))
            nearest = nearest_trigger_event_ids(text, start, end, other_triggers) if span_ok else []
            trigger_conditioned = argument_is_conditioned_on_event(arg, event_id, trigger)
            nearest_this = trigger_conditioned or nearest == [event_id]
            participant_role = arg.get("role") in (COMPANY_ROLES | {"Person"})
            if not participant_role:
                status, reason = "OUT_OF_SCOPE", "Argument role is not a participant role used by the four audited paths."
            elif not span_ok or not in_event_evidence or not trigger_ok:
                status, reason = "EXTRACTION_ERROR", "EAE argument span does not verify inside the same evidence span as its event trigger."
            elif not aligned:
                status, reason = "ARGUMENT_LINKING_ERROR", "EAE span is not aligned to exactly one EMD mention span."
            elif not event_role_ok or not compatible:
                status, reason = "ARGUMENT_LINKING_ERROR", type_reason if not compatible else f"Role {arg.get('role')} is not supported for BKEE event type {event.get('eventType')}."
            elif not trigger_conditioned and (len(nearest) != 1 or not nearest_this):
                status, reason = "UNRESOLVED_TRIGGER", "Argument is closer to another trigger or tied across triggers in the same sentence."
            elif mention_link["status"] != "MATCHED":
                status, reason = "UNRESOLVED_ENTITY", "Argument is trigger-aligned, but its EMD mention has no unique KG URI."
            else:
                association = "explicit trigger-conditioned EAE input" if trigger_conditioned else "unique nearest ED trigger"
                status, reason = "LINKED_TO_TRIGGER", f"{alignment_method} EAE/EMD alignment, compatible type/role, verified evidence, and {association}."
                accepted.append({"argument": arg, "mention": mention_link["mention"], "uri": mention_link["uri"],
                                 "types": entity_index[mention_link["uri"]]["types"], "support": reason})
            arg["auditLinkStatus"] = status
            argument_rows.append({
                "articleId": aid, "eventId": event_id, "evidenceId": event.get("evidence", {}).get("evidenceId", ""),
                "sourceUrl": article.get("url", ""), "eventType": event.get("eventType", ""),
                "triggerText": trigger.get("text", ""), "triggerStart": trigger.get("startChar", ""),
                "triggerEnd": trigger.get("endChar", ""), "evidenceText": evidence,
                "argumentText": arg.get("text", ""), "argumentRole": arg.get("role", ""),
                "entityMentionId": mention_id or "",
                "argumentStart": start, "argumentEnd": end, "argumentConfidence": arg.get("confidence", ""),
                "mentionType": mention_type, "resolvedUri": (mention_link or {}).get("uri", "") or "",
                "spanVerified": span_ok, "inEventEvidence": in_event_evidence, "exactMentionAlignment": aligned,
                "alignmentMethod": alignment_method,
                "eventRoleCompatible": event_role_ok, "entityTypeCompatible": compatible,
                "nearestTriggerEventIds": "|".join(nearest), "linkStatus": status, "reason": reason,
            })

        resolution_by_event[event_id] = links
        accepted_arguments[event_id] = accepted

    # Build path participants from validated trigger-linked arguments only, not all co-mentioned entities.
    path_rows = []
    for event in events:
        aid, eid = str(event["articleId"]), str(event["eventId"])
        article = articles.get(aid, {})
        evidence = str(event.get("evidence", {}).get("evidenceText", ""))
        eff_day = old_audit.parse_date(event.get("effectiveTradingDate"))
        event_available = old_audit.parse_datetime(event.get("availableAt"))
        participants = participants_from_linked_arguments(accepted_arguments[eid])

        all_linked = [link for link in resolution_by_event[eid] if link["status"] == "MATCHED"]
        unresolved_in_evidence = [row for row in mention_rows if row["eventId"] == eid and row["evidenceSpanVerified"] and row["resolutionStatus"] in {"UNRESOLVED", "AMBIGUOUS"}]
        for path in PATHS:
            part_kind = {"DIRECT": "Company", "INDIRECT_SUBSIDIARY": "Company", "INDIRECT_LEADERSHIP": "CorporateLeader", "INDIRECT_INDUSTRY": "Industry"}[path]
            parts = participants[part_kind]
            out = {"articleId": aid, "eventId": eid, "evidenceId": event.get("evidence", {}).get("evidenceId", ""),
                   "sourceUrl": article.get("url", ""), "eventType": event.get("eventType", ""),
                   "effectiveTradingDate": event.get("effectiveTradingDate", ""), "path": path,
                   "pathStatus": "NO_ENTITY", "blockerCategory": "", "entityUri": "", "intermediateNodeUris": "",
                   "candidateStockUris": "", "eventToEntityEvidence": "", "temporalCondition": "", "reason": ""}
            if not parts:
                types_present = {t for link in all_linked for t in entity_index[link["uri"]]["types"]}
                if unresolved_in_evidence:
                    out["blockerCategory"] = "ENTITY_UNRESOLVED"
                    out["reason"] = "One or more in-evidence entity mentions remain ambiguous/unresolved; no URI was forced."
                elif types_present & {"Company", "Bank", "CorporateLeader", "Industry"}:
                    out["blockerCategory"] = "EVENT_ENTITY_RELATION_UNSUPPORTED"
                    out["reason"] = "KG entity is resolved in the article but no compatible, trigger-linked argument supports this path."
                else:
                    out["blockerCategory"] = "EVENT_OUT_OF_SCOPE"
                    out["reason"] = "No entity of this path type is supported by the extracted event evidence."
            elif path == "DIRECT":
                companies = {p["uri"] for p in parts}
                stocks = {str(stock) for company in companies for stock in graph.objects(URIRef(company), W.hasStock)}
                out["entityUri"] = "|".join(sorted(companies))
                out["eventToEntityEvidence"] = " | ".join(f"{p['mention'].get('text','')} via {p['support']}" for p in parts)
                if stocks:
                    out.update(pathStatus="MATCHED", blockerCategory="", candidateStockUris="|".join(sorted(stocks)),
                               reason="Trigger-linked Company/Bank has a KG hasStock relation.")
                else:
                    out.update(pathStatus="MISSING_RELATION", blockerCategory="KG_RELATION_MISSING", reason="Event participant URI is linked, but Company --hasStock--> Stock is absent.")
            elif path == "INDIRECT_SUBSIDIARY":
                rels = [(p, rel) for p in parts for rel in graph.subjects(W.subsidiaryCompany, URIRef(p["uri"]))]
                if not rels:
                    out.update(pathStatus="NOT_APPLICABLE", blockerCategory="EVENT_OUT_OF_SCOPE", entityUri="|".join(sorted({p['uri'] for p in parts})),
                               reason="Linked event participant is not a subsidiary in the current KG.")
                else:
                    candidate, notes, intermediate, temporally_valid = set(), [], set(), True
                    for part, rel in rels:
                        intermediate.add(str(rel))
                        parents = list(graph.objects(rel, W.parentCompany))
                        intermediate.update(str(parent) for parent in parents)
                        status, note = old_audit.active_for_event(graph, rel, eff_day, event_available, snapshot_only=True)
                        notes.append(note); temporally_valid &= status == "MATCHED"
                        if status == "MATCHED":
                            candidate.update(str(stock) for parent in parents for stock in graph.objects(parent, W.hasStock))
                    out.update(entityUri="|".join(sorted({p['uri'] for p, _ in rels})), intermediateNodeUris="|".join(sorted(intermediate)),
                               temporalCondition=" | ".join(notes), eventToEntityEvidence=" | ".join(p["support"] for p, _ in rels))
                    if candidate and temporally_valid:
                        out.update(pathStatus="MATCHED", candidateStockUris="|".join(sorted(candidate)), blockerCategory="", reason="Subsidiary, parent, stock and event-date validity are supported.")
                    else:
                        out.update(pathStatus="INSUFFICIENT_EVIDENCE", blockerCategory="KG_RELATION_TEMPORAL_INSUFFICIENT" if not temporally_valid else "KG_RELATION_MISSING",
                                   reason="Subsidiary relation exists but lacks event-date validity or a complete parent-stock chain.")
            elif path == "INDIRECT_LEADERSHIP":
                active, positions, companies, notes = [], set(), set(), []
                company_context = {p["uri"] for p in participants["Company"]}
                for part in parts:
                    for pos in graph.objects(URIRef(part["uri"]), W.hasLeadershipPosition):
                        positions.add(str(pos))
                        company = next(iter(graph.objects(pos, W.positionAtCompany)), None)
                        if company is None:
                            continue
                        status, note = old_audit.active_for_event(graph, pos, eff_day, event_available)
                        notes.append(note)
                        if status == "MATCHED" and (not company_context or str(company) in company_context):
                            active.append((part, pos, company)); companies.add(str(company))
                stocks = {str(stock) for _, _, company in active for stock in graph.objects(company, W.hasStock)}
                out.update(entityUri="|".join(sorted({p['uri'] for p in parts})), intermediateNodeUris="positions=" + "|".join(sorted(positions)) + ";companies=" + "|".join(sorted(companies)),
                           temporalCondition=" | ".join(notes), eventToEntityEvidence=" | ".join(p["support"] for p in parts))
                if stocks:
                    out.update(pathStatus="MATCHED", candidateStockUris="|".join(sorted(stocks)), blockerCategory="", reason="Event-linked leader has an available, effective KG position at a Company with Stock.")
                elif positions:
                    out.update(pathStatus="INSUFFICIENT_EVIDENCE", blockerCategory="KG_RELATION_TEMPORAL_INSUFFICIENT", reason="Leadership relation exists but is not proven effective/available at the Event cutoff or company context conflicts.")
                else:
                    out.update(pathStatus="MISSING_RELATION", blockerCategory="KG_RELATION_MISSING", reason="Resolved Event-linked leader has no LeadershipPosition in KG.")
            else:
                exposures = [(p, exposure) for p in parts for exposure in graph.subjects(W.exposureIndustry, URIRef(p["uri"]))]
                candidates, notes, intermediate, valid = set(), [], set(), True
                for part, exposure in exposures:
                    intermediate.add(str(exposure))
                    bank = next(iter(graph.objects(exposure, W.exposureBank)), None)
                    if bank is None:
                        valid = False; continue
                    intermediate.add(str(bank))
                    status, note = old_audit.active_for_event(graph, exposure, eff_day, event_available, snapshot_only=True)
                    notes.append(note); valid &= status == "MATCHED"
                    if status == "MATCHED":
                        candidates.update(str(stock) for stock in graph.objects(bank, W.hasStock))
                out.update(entityUri="|".join(sorted({p['uri'] for p in parts})), intermediateNodeUris="|".join(sorted(intermediate)),
                           temporalCondition=" | ".join(notes), eventToEntityEvidence=" | ".join(p["support"] for p in parts))
                if candidates and valid:
                    out.update(pathStatus="MATCHED", candidateStockUris="|".join(sorted(candidates)), blockerCategory="", reason="Event-linked Industry reaches Bank Stock through time-supported exposure.")
                elif not exposures:
                    out.update(pathStatus="MISSING_RELATION", blockerCategory="KG_RELATION_MISSING", reason="Event-linked Industry has no IndustryExposure/Bank/Stock path in KG.")
                else:
                    out.update(pathStatus="INSUFFICIENT_EVIDENCE", blockerCategory="KG_RELATION_TEMPORAL_INSUFFICIENT", reason="IndustryExposure snapshot does not establish validity at the Event date.")
            path_rows.append(out)

    mention_fields = list(mention_rows[0]) if mention_rows else []
    arg_fields = list(argument_rows[0]) if argument_rows else []
    path_fields = list(path_rows[0]) if path_rows else []
    write_csv(out_dir / "entity_resolution_audit.csv", mention_rows, mention_fields)
    write_csv(out_dir / "event_argument_linking_audit.csv", argument_rows, arg_fields)
    write_csv(out_dir / "event_path_coverage.csv", path_rows, path_fields)

    resolution_counts = Counter(row["resolutionStatus"] for row in mention_rows)
    resolved_uri_rows = [row for row in mention_rows if row["resolvedUri"]]
    resolved_type_counts = Counter(t for row in resolved_uri_rows for t in entity_index[row["resolvedUri"]]["types"])
    unresolved_with_candidates = sum(row["resolutionStatus"] == "UNRESOLVED" and bool(row["candidateUris"]) for row in mention_rows)
    argument_counts = Counter(row["linkStatus"] for row in argument_rows)
    path_counts = {path: Counter(row["pathStatus"] for row in path_rows if row["path"] == path) for path in PATHS}
    blocker_counts = Counter(row["blockerCategory"] for row in path_rows if row["blockerCategory"])
    event_paths = defaultdict(list)
    for row in path_rows:
        event_paths[row["eventId"]].append(row["pathStatus"])
    event_participants = {eid for eid, rows in accepted_arguments.items() if rows}
    events_with_path = sum(any(s == "MATCHED" for s in statuses) for statuses in event_paths.values())
    previous = read_json(RUN / "entity_linking_report.json")
    previous_links = {(row.get("eventId"), row.get("startChar"), row.get("endChar")): row.get("matchedUris", "")
                      for row in read_csv(RUN / "entity_linking_audit.csv") if row.get("entityLinkStatus") == "MATCHED"}
    current_links = {(row.get("eventId"), str(row.get("startChar", "")), str(row.get("endChar", ""))): row.get("resolvedUri", "")
                     for row in resolved_uri_rows}
    preserved_links = sum(key in current_links and current_links[key] == uri for key, uri in previous_links.items())
    summary = {
        "ontologyVersion": "1.0.5", "corpusArticleCount": len(articles),
        "articlesWithStagedEvents": len({str(event["articleId"]) for event in events}),
        "eventCount": len(events), "mentionCount": len(mention_rows),
        "triggerEvidenceSpanVerification": dict(event_evidence_verification),
        "argumentCount": len(argument_rows), "entityResolutionStatusCounts": dict(resolution_counts),
        "resolvedMentionUriLinkCount": len(resolved_uri_rows), "uniqueResolvedUriCount": len({row["resolvedUri"] for row in resolved_uri_rows}),
        "resolvedUriTypeCounts": dict(resolved_type_counts),
        "unresolvedMentionsWithNearKgCandidates": unresolved_with_candidates,
        "previousExactUriLinksPreserved": preserved_links,
        "newlyMatchedMentionCount": max(0, len(resolved_uri_rows) - preserved_links),
        "eventArgumentStatusCounts": dict(argument_counts), "eventsWithResolvedParticipant": len(event_participants),
        "eventsWithAtLeastOneCompletePath": events_with_path, "eventsWithoutCompletePath": len(events) - events_with_path,
        "pathStatusCounts": {path: dict(counts) for path, counts in path_counts.items()},
        "pathBlockerCounts": dict(blocker_counts),
        "candidatePathCountByType": {path: sum(row["path"] == path and row["pathStatus"] == "MATCHED" for row in path_rows) for path in PATHS},
        "previousAuditEntityStatusCounts": previous.get("mentionStatusCounts", {}),
        "kgEntityCounts": dict(Counter(t for item in entity_index.values() for t in item["types"])),
        "kgAliases": sum(1 for _ in graph.subjects(RDF.type, W.CompanyAlias)), "kgTriples": len(graph),
        "sourceInferenceReused": True, "trainingRun": False, "crawlRun": False,
        "kgOntologyShaclAnnotationCheckpointModified": False,
        "notes": ["Matched means a unique type-compatible URI based on existing KG label/alias and verified context; fuzzy candidates are review-only.",
                  "Event participant counts require verified EAE/EMD mention references, compatible role/type, same verified evidence, and explicit trigger conditioning for new EAE (legacy output uses unique-nearest-trigger fallback).",
                  "Path absence is reported separately from URI resolution failure; no EventStockCandidate/AR/CAR is generated."]
    }
    (out_dir / "report.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_report(summary, path_rows, mention_rows, argument_rows, out_dir)
    return summary


def write_report(summary: dict, paths: list[dict], mentions: list[dict], arguments: list[dict], out_dir: Path = OUT):
    lines = [
        "# Entity Linking v2 Audit", "",
        f"- Ontology/SHACL: v{summary['ontologyVersion']}; corpus articles: {summary['corpusArticleCount']}; articles with staged Events: {summary['articlesWithStagedEvents']}; Events: {summary['eventCount']}; EMD mentions: {summary['mentionCount']}; EAE arguments: {summary['argumentCount']}.",
        f"- Verified trigger/evidence spans: `{summary['triggerEvidenceSpanVerification']}`; detected mention spans: {summary['mentionCount']} (per-mention verification is in the resolution CSV).",
        "- Reused stored inference; did not retrain, recrawl, change KG/schema/checkpoint/annotations, or create candidates/reactions.",
        "", "## Separate stages", "",
        "1. **Entity Mention Detection:** recorded PhoBERT mention type and verified character span in prepared article text and event evidence.",
        "2. **Entity Resolution:** resolved to an existing KG URI only with a unique type-compatible label/alias match; document context may disambiguate only through a distinct existing KG label. Similarity results remain unresolved.",
        "3. **Event-Entity Argument Linking:** requires a verified EAE/EMD mention reference (direct mention ID when available; legacy exact/nested span otherwise), role/type compatibility, evidence containment, and explicit trigger conditioning or a unique nearest ED trigger for legacy output.",
        "4. **KG Path Validation:** traverses existing relations and checks temporal facts independently of mention/URI correctness.",
        "", "## Before and after", "",
        f"- Previous audit mention outcomes: `{summary['previousAuditEntityStatusCounts']}`.",
        f"- New URI resolution outcomes: `{summary['entityResolutionStatusCounts']}`.",
        f"- URI links: {summary['resolvedMentionUriLinkCount']} mention-to-URI links across {summary['uniqueResolvedUriCount']} URIs; previous URI links preserved unchanged: {summary['previousExactUriLinksPreserved']}; newly matched mentions: {summary['newlyMatchedMentionCount']}; unresolved mentions with near-KG candidates for review: {summary['unresolvedMentionsWithNearKgCandidates']}.",
        f"- Resolved URI types (KG may assign more than one type per URI): `{summary['resolvedUriTypeCounts']}`.",
        f"- Event argument outcomes: `{summary['eventArgumentStatusCounts']}`.",
        f"- Events with resolved trigger-linked participant: {summary['eventsWithResolvedParticipant']}/{summary['eventCount']}; with at least one complete path: {summary['eventsWithAtLeastOneCompletePath']}/{summary['eventCount']}.",
        "- A higher MATCHED count is not treated as proof of higher precision. `MATCHED` records exact KG-backed links, while context resolutions and all non-matches retain method/reason/candidates for review.",
        "", "## Four paths", "",
    ]
    for path in PATHS:
        counts = summary["pathStatusCounts"][path]
        lines.append(f"- **{path}**: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items())) +
                     f"; complete candidate rows={summary['candidatePathCountByType'][path]}.")
    lines += ["", "## Interpretation of missing paths", "",
              f"Blocker counts (Event x path rows): `{summary['pathBlockerCounts']}`.",
              "`ENTITY_UNRESOLVED` means no safe URI; `EVENT_ENTITY_RELATION_UNSUPPORTED` means a URI exists but no compatible argument ties it to this trigger; `KG_RELATION_MISSING` means the event participant is linked but the KG edge is absent; `KG_RELATION_TEMPORAL_INSUFFICIENT` means the edge exists but the event-time condition is unproven; `EVENT_OUT_OF_SCOPE` means there is no evidence-backed participant for that path type.",
              "", "## Known review cases", "",
              "- Source-backed resolver aliases for Vietcombank/VCB, VPBank/VPB, HDBank/HDB, VietinBank/CTG, and BIDV/BID are read from `data/external/verified_entity_aliases.json`; they remain outside the KG graph. Explicit parenthetical name/ticker mentions are resolved only when both candidates point to one URI.",
              "- Full bank names and ticker aliases resolve from existing KG facts or the separately sourced alias registry. Leaders resolve only against existing `CorporateLeader` labels and preserve ambiguity where names collide.",
              "- A ticker in a headline/evidence prefix identifies a likely article subject, but does not by itself establish an Event argument. Government organizations and industries do not become Company/Bank participants merely because a Stock path is desired.",
              "- The three `Person`/EMD `JOB` cases are rejected as person links; a position/title does not identify a person URI.",
              "", "## Artifacts", "",
              "- `entity_resolution_audit.csv`: per EMD mention, URI/candidates, evidence, source, span, method and reason.",
              "- `event_argument_linking_audit.csv`: per EAE argument, trigger, exact-span alignment, role/type compatibility and link status.",
              "- `event_path_coverage.csv`: 155 Events x 4 paths, candidate stock, node URIs, blocker category and time condition.",
              "- `report.json`: machine-readable counts.", ""]
    (out_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("--staging", type=Path, default=RUN / "staging_review.json")
    cli.add_argument("--output-dir", type=Path, default=OUT)
    args = cli.parse_args()
    print(json.dumps(main(args.staging, args.output_dir), ensure_ascii=False))
