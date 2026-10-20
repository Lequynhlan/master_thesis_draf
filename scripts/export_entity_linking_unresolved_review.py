"""Export every saved role proposal that still lacks a safe URI."""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/news_event_vertical_slice_20261019/eae_trigger_conditioned_v1"
AUDIT = RUN / "entity_linking_v3"
OUT = RUN / "entity_linking_unresolved_causes.csv"


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def main():
    resolutions = read_csv(AUDIT / "entity_resolution_audit.csv")
    arguments = read_csv(AUDIT / "event_argument_linking_audit.csv")
    articles = {str(row["articleId"]): row for row in
                (json.loads(line) for line in (ROOT / "data/cleaned/news_100_v1/clean_articles.jsonl").read_text(encoding="utf-8").splitlines() if line.strip())}
    mentions = {(row["eventId"], row["startChar"], row["endChar"], row["mentionText"]): row for row in resolutions}
    rows, counts = [], Counter()
    for argument in arguments:
        if argument["linkStatus"] != "UNRESOLVED_ENTITY":
            continue
        key = (argument["eventId"], argument["argumentStart"], argument["argumentEnd"], argument["argumentText"])
        mention = mentions.get(key, {})
        surface = argument["argumentText"]
        if mention.get("resolutionStatus") == "AMBIGUOUS":
            cause = "AMBIGUOUS_URI_CANDIDATE"
            note = "Multiple existing KG URIs share the normalized candidate; retain unresolved pending context review."
        elif mention.get("candidateUris"):
            cause = "NEAR_KG_CANDIDATE_REVIEW"
            note = "Fuzzy candidate(s) exist but are not automatically promoted; possible alias/normalization gap or a distinct entity."
        elif re.search(r"\s-$|\($|triển$|KQKD|^[-–—]+$|\d+\s*CSV|4$", surface, re.I):
            cause = "SUSPECT_EMD_FRAGMENT_OR_BOUNDARY"
            note = "Surface looks truncated, contaminated or attached to adjacent text; EMD span is source-verifiable but semantically suspect."
        elif argument["mentionType"] == "PER":
            cause = "PERSON_NOT_IN_KG_LABELS_OR_NOT_LEADER"
            note = "No safe existing CorporateLeader URI; may be a missing KG entity, out-of-scope person, or title/context error."
        else:
            cause = "NO_KG_CANDIDATE_ENTITY_OR_ALIAS_REVIEW"
            note = "No exact or fuzzy KG URI candidate; cannot distinguish missing entity/alias, out-of-scope entity, or EAE context error without researcher review."
        counts[cause] += 1
        article = articles.get(argument["articleId"], {})
        rows.append({
            "articleId": argument["articleId"], "articleTitle": article.get("title", ""), "sourceUrl": argument["sourceUrl"],
            "eventId": argument["eventId"], "eventType": argument["eventType"], "trigger": argument["triggerText"],
            "evidenceText": argument["evidenceText"], "entityMention": surface, "mentionType": argument["mentionType"],
            "argumentRole": argument["argumentRole"], "argumentConfidence": argument["argumentConfidence"],
            "spanVerified": argument["spanVerified"], "evidenceVerified": argument["inEventEvidence"],
            "candidateUris": mention.get("candidateUris", ""), "candidateEvidence": mention.get("candidateEvidence", ""),
            "resolutionStatus": mention.get("resolutionStatus", ""), "causeCategory": cause, "causeNote": note,
            "reviewDecision": "", "reviewerComment": "",
        })
    fields = list(rows[0]) if rows else []
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    print(json.dumps({"unresolvedArguments": len(rows), "causeCounts": counts, "path": str(OUT.relative_to(ROOT))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
