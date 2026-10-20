"""Run a small, reproducible PhoBERT token-classification NER pilot.

This script intentionally keeps all pilot artifacts separate from the PhoBERT
embedding MVP and from source/corpus/KG data. It uses an existing fine-tuned
checkpoint; it does not create or train a task head.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import numpy as np
import torch
from transformers import AutoModelForTokenClassification, AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_phobert_mvp as mvp  # noqa: E402 - reuse only locked input/KG helpers

MODEL_ID = "huyenbui117/Covid19_phoNER"
MODEL_REVISION = "ade09d2c05631d9172ec986bbc6abeb3ee61c46b"
MAX_TOKENS = 256  # includes BOS/EOS
CONTENT_LIMIT = MAX_TOKENS - 2
LONG_SENTENCE_OVERLAP = 32  # PhoBERT subword tokens; never split a VnCore word
PILOT_SIZE = 20
OUT_DIR = ROOT / "runs/phobert_ner_pilot_news_100_v1"


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def compact_text(value: str) -> str:
    """Fold case/NFC and omit spaces/segmenter underscores for alignment only."""
    normalized = unicodedata.normalize("NFC", value).casefold()
    return "".join(char for char in normalized if not char.isspace() and char != "_")


def compact_view(text: str) -> tuple[str, list[int], list[int]]:
    output: list[str] = []
    starts: list[int] = []
    ends: list[int] = []
    for pos, char in enumerate(unicodedata.normalize("NFC", text)):
        if char.isspace() or char == "_":
            continue
        for folded in char.casefold():
            output.append(folded)
            starts.append(pos)
            ends.append(pos + 1)
    return "".join(output), starts, ends


def align_sentence_words(body: str, sentence_id: int, segmented: str, cursor: int) -> tuple[dict[str, Any], int]:
    """Map RDRSegmenter words to monotonic exact source spans.

    Removing whitespace and underscores from the alignment view handles the
    common source/segmenter distinction between syllable spaces and segmented
    compounds. It does not alter input text. Every exported entity span is
    independently checked by reconstructing it from the original body.
    """
    view, starts, ends = compact_view(body)
    words = []
    search_at = cursor
    misses = []
    for word_index, word in enumerate(segmented.split()):
        needle = compact_text(word)
        if not needle:
            words.append({"wordIndex": word_index, "word": word, "startChar": None, "endChar": None})
            misses.append(word_index)
            continue
        # Bounded local search avoids a failed word leaping across paragraphs.
        search_end = min(len(view), search_at + max(768, len(needle) * 24))
        found = view.find(needle, search_at, search_end)
        if found < 0:
            words.append({"wordIndex": word_index, "word": word, "startChar": None, "endChar": None})
            misses.append(word_index)
            continue
        start = starts[found]
        end = ends[found + len(needle) - 1]
        words.append({"wordIndex": word_index, "word": word, "startChar": start, "endChar": end})
        search_at = found + len(needle)
    valid = [word for word in words if word["startChar"] is not None]
    status = "PARTIAL" if valid else "UNVERIFIED"
    if len(valid) == len(words) and valid:
        source_sentence = body[valid[0]["startChar"]:valid[-1]["endChar"]]
        if compact_text(source_sentence) == compact_text(segmented):
            status = "VERIFIED"
    return {
        "sentenceId": sentence_id,
        "segmentedSentence": segmented,
        "words": words,
        "alignmentStatus": status,
        "alignmentMissWordIndices": misses,
        "sourceStartChar": valid[0]["startChar"] if valid else None,
        "sourceEndChar": valid[-1]["endChar"] if valid else None,
    }, search_at


def prepare_article(body: str, segmenter: Any, tokenizer: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    segmented_sentences = segmenter.word_segment(body)
    sentence_rows = []
    cursor = 0
    for sentence_id, segmented in enumerate(segmented_sentences):
        row, cursor = align_sentence_words(body, sentence_id, segmented, cursor)
        words = row["words"]
        for word in words:
            word["subtokenIds"] = tokenizer.encode(word["word"], add_special_tokens=False, truncation=False)
            if not word["subtokenIds"]:
                word["subtokenIds"] = [tokenizer.unk_token_id]
        # Use tokenize/convert directly here: some long source sentences exceed
        # PhoBERT's context window before we split them, and this check is only
        # for tokenization equivalence, not a model forward pass.
        full_ids = tokenizer.convert_tokens_to_ids(tokenizer.tokenize(segmented))
        concatenated = [token_id for word in words for token_id in word["subtokenIds"]]
        if full_ids != concatenated:
            raise ValueError(f"sentence {sentence_id}: per-word PhoBERT tokenization differs from sentence tokenization")
        sentence_rows.append(row)

    chunks: list[dict[str, Any]] = []
    for sentence in sentence_rows:
        words = sentence["words"]
        if not words:
            continue
        word_counts = [len(word["subtokenIds"]) for word in words]
        total = sum(word_counts)
        start_word = 0
        overlap_from_previous = 0
        while start_word < len(words):
            end_word = start_word
            count = 0
            while end_word < len(words) and count + word_counts[end_word] <= CONTENT_LIMIT:
                count += word_counts[end_word]
                end_word += 1
            if end_word == start_word:
                # A single tokenizer-atomic word cannot fit the declared budget.
                raise ValueError(f"sentence {sentence['sentenceId']}: one segmenter word exceeds PhoBERT limit")
            selected = words[start_word:end_word]
            text = " ".join(word["word"] for word in selected)
            encoded = tokenizer.encode(text, add_special_tokens=True, truncation=False)
            if len(encoded) > MAX_TOKENS:
                raise ValueError(f"sentence {sentence['sentenceId']}: no-truncation chunk exceeds {MAX_TOKENS}")
            chunks.append({
                "chunkId": len(chunks),
                "sentenceId": sentence["sentenceId"],
                "wordStartIndex": start_word,
                "wordEndIndexExclusive": end_word,
                "wordIndices": list(range(start_word, end_word)),
                "text": text,
                "contentTokenCount": count,
                "sequenceTokenCount": len(encoded),
                "overlapFromPreviousSubtokens": overlap_from_previous,
            })
            if end_word >= len(words):
                break
            next_start = end_word
            overlap = 0
            while next_start > start_word and overlap + word_counts[next_start - 1] <= LONG_SENTENCE_OVERLAP:
                overlap += word_counts[next_start - 1]
                next_start -= 1
            if next_start == start_word:
                next_start = end_word
                overlap = 0
            overlap_from_previous = overlap
            start_word = next_start

    # Report source-span alignment without changing sentence/chunk text.
    for chunk in chunks:
        sentence = sentence_rows[chunk["sentenceId"]]
        chunk["sentenceAlignmentStatus"] = sentence["alignmentStatus"]
        chunk["sourceStartChar"] = sentence["sourceStartChar"]
        chunk["sourceEndChar"] = sentence["sourceEndChar"]
    return sentence_rows, chunks


def select_articles(cohort: dict[str, Any], records: list[dict[str, Any]], candidates: list[dict[str, str]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Select 15 CafeF + 5 Vietstock with length and KG-candidate diversity."""
    order = [str(row["articleId"]) for row in cohort["articles"]]
    by_id = {row["articleId"]: row for row in records}
    candidate_by_id: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in candidates:
        candidate_by_id[row["articleId"]].append(row)
    domains: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for aid in order:
        row = by_id[aid]
        host = urlparse(row["url"]).netloc.lower().removeprefix("www.")
        if host.endswith("cafef.vn"):
            domain_group = "cafef.vn"
        elif host.endswith("vietstock.vn"):
            domain_group = "vietstock.vn" if host == "vietstock.vn" else "en.vietstock.vn"
        else:
            domain_group = host or "UNKNOWN"
        domains[domain_group].append({**row, "domainGroup": domain_group})

    def select_bucket(rows: list[dict[str, Any]], take: int) -> list[dict[str, Any]]:
        if not rows or take <= 0:
            return []
        ranked = sorted(rows, key=lambda row: (len(row["bodyText"]), row["articleId"]))
        n = len(ranked)
        buckets = [ranked[: max(1, n // 3)], ranked[max(1, n // 3): max(2, 2 * n // 3)], ranked[max(2, 2 * n // 3):]]
        if not buckets[2]:
            buckets[2] = buckets[1][-1:]
        chosen = []
        used = set()
        # Cycle length buckets, preferring absent KG match evidence first,
        # then coverage of different candidate entity groups, then stable ID.
        while len(chosen) < take:
            progressed = False
            for bucket in buckets:
                options = [row for row in bucket if row["articleId"] not in used]
                if not options:
                    continue
                chosen_groups = {candidate_by_id[row["articleId"]][0]["entityGroup"]
                                 for row in chosen if candidate_by_id[row["articleId"]]}
                options.sort(key=lambda row: (
                    0 if not candidate_by_id[row["articleId"]] else 1,
                    -len({item["entityGroup"] for item in candidate_by_id[row["articleId"]]} - chosen_groups),
                    row["articleId"],
                ))
                chosen.append(options[0]); used.add(options[0]["articleId"]); progressed = True
                if len(chosen) == take:
                    break
            if not progressed:
                break
        return chosen

    selected = []
    selected.extend(select_bucket(domains.get("cafef.vn", []), 15))
    selected.extend(select_bucket(domains.get("en.vietstock.vn", []), 3))
    selected.extend(select_bucket(domains.get("vietstock.vn", []), 2))
    if len(selected) != PILOT_SIZE or len({row["articleId"] for row in selected}) != PILOT_SIZE:
        raise RuntimeError(f"Stratified pilot selection produced {len(selected)} unique articles, expected 20")
    selected.sort(key=lambda row: order.index(row["articleId"]))
    manifest = {
        "selectionRule": "15 cafef.vn + 3 en.vietstock.vn + 2 vietstock.vn; round-robin short/medium/long body-length buckets within source; prefer coverage of unseen KG candidate groups and include articles without MVP candidates where available; tie-break by articleId.",
        "selectedArticleIds": [row["articleId"] for row in selected],
        "selectedSourceCounts": dict(Counter(row["domainGroup"] for row in selected)),
        "sourceCountsInCohort": dict(Counter(row["domainGroup"] for group in domains.values() for row in group)),
    }
    return selected, manifest


def infer_chunks(chunks: list[dict[str, Any]], tokenizer: Any, model: Any, device: torch.device) -> None:
    model.eval()
    for offset in range(0, len(chunks), 8):
        batch = chunks[offset:offset + 8]
        encoded = tokenizer([row["text"] for row in batch], padding=True, truncation=False, add_special_tokens=True, return_tensors="pt")
        if encoded["input_ids"].shape[1] > MAX_TOKENS:
            raise RuntimeError("Tokenized inference batch exceeds maximum; truncation is disabled")
        input_ids = encoded["input_ids"].to(device)
        attention_mask = encoded["attention_mask"].to(device)
        with torch.inference_mode():
            logits = model(input_ids=input_ids, attention_mask=attention_mask).logits
        probs = torch.softmax(logits, dim=-1).cpu().numpy()
        for batch_pos, chunk in enumerate(batch):
            article_words = chunk["_words"]
            cursor = 1  # PhoBERT BOS token occupies position zero.
            if int(input_ids[batch_pos, 0]) != int(tokenizer.bos_token_id):
                raise RuntimeError("Unexpected PhoBERT BOS token placement")
            for word_index in chunk["wordIndices"]:
                word = article_words[word_index]
                count = len(word["subtokenIds"])
                distribution = probs[batch_pos, cursor]
                label_id = int(np.argmax(distribution))
                word["predictedLabel"] = model.config.id2label[label_id]
                word["confidence"] = float(distribution[label_id])
                word["chunkId"] = chunk["chunkId"]
                cursor += count
            if cursor != int(attention_mask[batch_pos].sum().item()) - 1:
                raise RuntimeError("Per-word logits do not align with tokenized chunk content")


def decode_entities(article: dict[str, Any], sentence_rows: list[dict[str, Any]], body: str,
                    model_id: str, revision: str) -> list[dict[str, Any]]:
    entities = []
    for sentence in sentence_rows:
        words = sentence["words"]
        active: list[dict[str, Any]] = []
        active_type = None

        def flush() -> None:
            nonlocal active, active_type
            if not active:
                return
            valid_spans = all(word["startChar"] is not None and word["endChar"] is not None for word in active)
            ordered = all(active[i]["endChar"] <= active[i + 1]["startChar"] for i in range(len(active) - 1)) if valid_spans else False
            surface_segmented = " ".join(word["word"] for word in active)
            start = active[0]["startChar"] if valid_spans and ordered else None
            end = active[-1]["endChar"] if valid_spans and ordered else None
            original = body[start:end] if start is not None else None
            verified = original is not None and compact_text(original) == compact_text(surface_segmented)
            checkpoint_label = active_type
            canonical_label = {"NAME": "PERSON", "DATE": "DATETIME"}.get(checkpoint_label, checkpoint_label)
            entities.append({
                "articleId": article["articleId"],
                "sourceDomain": article["domainGroup"],
                "sentenceId": sentence["sentenceId"],
                "sentence": body[sentence["sourceStartChar"]:sentence["sourceEndChar"]] if sentence["alignmentStatus"] == "VERIFIED" else None,
                "segmentedSentence": sentence["segmentedSentence"],
                "entityLabel": canonical_label,
                "checkpointEntityLabel": checkpoint_label,
                "bioLabels": [word["predictedLabel"] for word in active],
                "predictedSegmentedMention": surface_segmented,
                "originalText": original if verified else None,
                "startChar": start if verified else None,
                "endChar": end if verified else None,
                "spanStatus": "VERIFIED_EXACT_SOURCE_RECONSTRUCTION" if verified else "UNVERIFIED_ALIGNMENT",
                "sentenceAlignmentStatus": sentence["alignmentStatus"],
                "confidence": float(np.mean([word["confidence"] for word in active])),
                "tokenConfidences": [float(word["confidence"]) for word in active],
                "chunkIds": sorted({word["chunkId"] for word in active}),
                "modelId": model_id,
                "modelRevision": revision,
            })
            active = []
            active_type = None

        for word in words:
            label = word.get("predictedLabel", "O")
            if label == "O" or "-" not in label:
                flush(); continue
            prefix, entity_type = label.split("-", 1)
            if prefix == "B" or (prefix == "I" and active_type != entity_type):
                flush()
                active_type = entity_type
                active = [word]
            elif prefix == "I" and active_type == entity_type:
                active.append(word)
            else:
                flush()
        flush()
    return entities


def compare_with_kg(entities: list[dict[str, Any]], kg_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    by_article: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in kg_rows:
        by_article[row["articleId"]].append(row)
    output = []
    matched_ids: set[tuple[str, int]] = set()
    for prediction_id, entity in enumerate(entities):
        article_candidates = by_article[entity["articleId"]]
        if entity["spanStatus"] != "VERIFIED_EXACT_SOURCE_RECONSTRUCTION":
            output.append({"predictionId": prediction_id, **entity, "comparison": "UNVERIFIED_SPAN_NOT_COMPARED", "kgCandidateUris": "", "kgCandidateGroups": ""})
            continue
        overlaps = [row for row in article_candidates if int(row["startChar"]) < int(entity["endChar"]) and int(row["endChar"]) > int(entity["startChar"])]
        if not overlaps:
            output.append({"predictionId": prediction_id, **entity, "comparison": "POTENTIAL_NEW_ENTITY_OR_KG_ALIAS_GAP", "kgCandidateUris": "", "kgCandidateGroups": ""})
            continue
        def compatible(group: str) -> bool:
            return (entity["entityLabel"] == "PERSON" and group == "CORPORATE_LEADER") or (
                entity["entityLabel"] == "ORGANIZATION" and group in {"BANK", "COMPANY", "SUBSIDIARY_COMPANY"})
        status = "KG_CANDIDATE_MATCH" if any(compatible(row["entityGroup"]) for row in overlaps) else "KG_SPAN_TYPE_MISMATCH"
        for row in overlaps:
            matched_ids.add((row["articleId"], int(row["startChar"])))
        output.append({
            "predictionId": prediction_id, **entity, "comparison": status,
            "kgCandidateUris": "|".join(sorted({row["entityUri"] for row in overlaps})),
            "kgCandidateGroups": "|".join(sorted({row["entityGroup"] for row in overlaps})),
        })
    for row in kg_rows:
        key = (row["articleId"], int(row["startChar"]))
        if key not in matched_ids:
            output.append({
                "predictionId": "", "articleId": row["articleId"], "sourceDomain": "",
                "entityLabel": "", "originalText": row["mention"], "startChar": row["startChar"],
                "endChar": row["endChar"], "spanStatus": "KG_CANDIDATE_SOURCE_SPAN",
                "confidence": "", "comparison": "KG_CANDIDATE_NOT_PREDICTED_BY_NER",
                "kgCandidateUris": row["entityUri"], "kgCandidateGroups": row["entityGroup"],
            })
    return output


def build_gold_template(articles: list[dict[str, Any]], sentence_rows_by_article: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Create a blind-to-predictions 2-sentence/article annotation starter."""
    rows = []
    for article in articles:
        body = article["bodyText"]
        # Deterministic original-body sentence fragments; each span is exact by construction.
        spans = []
        cursor = 0
        for match in re.finditer(r"(?<=[.!?…])\s+|\r?\n+", body):
            if match.start() > cursor:
                spans.append((cursor, match.start(), body[cursor:match.start()].strip()))
            cursor = match.end()
        if cursor < len(body):
            spans.append((cursor, len(body), body[cursor:].strip()))
        spans = [(start, end, text) for start, end, text in spans if text]
        spans.sort(key=lambda row: hashlib.sha256(f"{article['articleId']}:{row[0]}".encode()).hexdigest())
        for start, end, text in spans[:2]:
            # Recover exact trimmed offsets after stripping surrounding spaces.
            left = len(body[start:end]) - len(body[start:end].lstrip())
            right = len(body[start:end].rstrip())
            real_start, real_end = start + left, start + right
            rows.append({
                "articleId": article["articleId"], "sourceDomain": article["domainGroup"], "url": article["url"],
                "sampleId": f"{article['articleId']}#chars-{real_start}-{real_end}",
                "sentenceStartChar": real_start, "sentenceEndChar": real_end,
                "sentenceText": body[real_start:real_end], "goldEntitySpansJson": "",
                "annotator": "", "adjudicationStatus": "PENDING",
            })
    return rows


def main() -> int:
    started = time.perf_counter()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cohort, enrichment_manifest, records, _ = mvp.read_corpus()
    candidate_path = mvp.OUT_DIR / "phobert_entity_candidates.csv"
    with candidate_path.open("r", encoding="utf-8-sig", newline="") as stream:
        all_kg_candidates = list(csv.DictReader(stream))
    articles, selection = select_articles(cohort, records, all_kg_candidates)
    selected_ids = {row["articleId"] for row in articles}
    kg_candidates = [row for row in all_kg_candidates if row["articleId"] in selected_ids]
    with (mvp.OUT_DIR / "phobert_inference_results.jsonl").open("r", encoding="utf-8") as stream:
        mvp_chunk_rows = [json.loads(line) for line in stream if line.strip() and "vectorIndex" in line]
    mvp_alignment_counts = Counter(row.get("sourceSpanMapping", "UNSPECIFIED") for row in mvp_chunk_rows)

    # Load the immutable checkpoint and its own tokenizer. Check labels before inference.
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, revision=MODEL_REVISION, use_fast=False)
    model = AutoModelForTokenClassification.from_pretrained(MODEL_ID, revision=MODEL_REVISION)
    id2label = {int(key): value for key, value in model.config.id2label.items()}
    required = {"NAME", "ORGANIZATION", "LOCATION", "DATE"}
    observed = {label.split("-", 1)[1] for label in id2label.values() if label.startswith(("B-", "I-"))}
    if not required.issubset(observed):
        raise RuntimeError(f"Checkpoint label inventory differs from inspected model card: {sorted(observed)}")
    if model.config.model_type != "roberta" or model.config.hidden_size != 768:
        raise RuntimeError("Checkpoint architecture is not compatible with the PhoBERT-base-v2 pilot assumptions")
    if tokenizer.bos_token_id != 0 or tokenizer.eos_token_id != 2:
        raise RuntimeError("Checkpoint tokenizer special-token IDs differ from the expected PhoBERT layout")
    torch.set_num_threads(min(4, os.cpu_count() or 1))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device); model.eval()

    original_cwd = Path.cwd()
    import py_vncorenlp
    segmenter = py_vncorenlp.VnCoreNLP(annotators=["wseg"], save_dir=str(mvp.ASSET_ROOT.resolve()))
    os.chdir(original_cwd)

    all_chunks = []
    sentence_rows_by_article: dict[str, list[dict[str, Any]]] = {}
    failed_articles = []
    for article in articles:
        article["domainGroup"] = urlparse(article["url"]).netloc.lower().removeprefix("www.")
        if article["domainGroup"].endswith("cafef.vn"):
            article["domainGroup"] = "cafef.vn"
        elif article["domainGroup"] not in {"vietstock.vn", "en.vietstock.vn"}:
            article["domainGroup"] = "other"
        try:
            if unicodedata.normalize("NFC", article["bodyText"]) != article["bodyText"]:
                raise ValueError("bodyText is not NFC; source offsets are not emitted for potentially altered spans")
            sentence_rows, chunks = prepare_article(article["bodyText"], segmenter, tokenizer)
            sentence_rows_by_article[article["articleId"]] = sentence_rows
            for chunk in chunks:
                chunk["_words"] = sentence_rows[chunk["sentenceId"]]["words"]
                chunk["articleId"] = article["articleId"]
                chunk["sourceDomain"] = article["domainGroup"]
                all_chunks.append(chunk)
        except Exception as exc:
            failed_articles.append({"articleId": article["articleId"], "error": f"{type(exc).__name__}: {exc}"})
    if failed_articles:
        # Fail closed: never emit a partial pilot while pretending it covers n=20.
        (OUT_DIR / "preflight_failures.json").write_text(json.dumps(failed_articles, ensure_ascii=False, indent=2), encoding="utf-8")
        raise RuntimeError(f"NER input preparation failed for {len(failed_articles)} selected articles; see preflight_failures.json")

    infer_chunks(all_chunks, tokenizer, model, device)
    predictions = []
    alignment_counts = Counter()
    for article in articles:
        sentence_rows = sentence_rows_by_article[article["articleId"]]
        alignment_counts.update(row["alignmentStatus"] for row in sentence_rows)
        predictions.extend(decode_entities(article, sentence_rows, article["bodyText"], MODEL_ID, MODEL_REVISION))
    comparisons = compare_with_kg(predictions, kg_candidates)
    gold_template = build_gold_template(articles, sentence_rows_by_article)

    # Persist inference output as records only; model logits/vectors are not copied to JSON.
    pred_path = OUT_DIR / "phobert_ner_predictions.jsonl"
    write_jsonl(pred_path, predictions)
    compare_fields = ["predictionId", "articleId", "sourceDomain", "sentenceId", "sentence", "entityLabel", "checkpointEntityLabel",
                      "predictedSegmentedMention", "originalText", "startChar", "endChar", "spanStatus",
                      "sentenceAlignmentStatus", "confidence", "comparison", "kgCandidateUris", "kgCandidateGroups",
                      "modelId", "modelRevision"]
    compare_path = OUT_DIR / "ner_vs_kg_candidates.csv"
    write_csv(compare_path, comparisons, compare_fields)
    gold_path = OUT_DIR / "manual_gold_annotation_template.csv"
    write_csv(gold_path, gold_template, ["articleId", "sourceDomain", "url", "sampleId", "sentenceStartChar",
                                          "sentenceEndChar", "sentenceText", "goldEntitySpansJson", "annotator", "adjudicationStatus"])

    with (mvp.CORPUS_PATH).open("rb") as stream:
        corpus_sha = hashlib.sha256(stream.read()).hexdigest()
    with mvp.COHORT_MANIFEST_PATH.open("rb") as stream:
        cohort_sha = hashlib.sha256(stream.read()).hexdigest()
    with mvp.ENRICHMENT_MANIFEST_PATH.open("rb") as stream:
        enrich_sha = hashlib.sha256(stream.read()).hexdigest()
    with mvp.KG_PATH.open("rb") as stream:
        kg_sha = hashlib.sha256(stream.read()).hexdigest()
    status_counts = Counter(row["spanStatus"] for row in predictions)
    label_counts = Counter(row["entityLabel"] for row in predictions)
    comparison_counts = Counter(row["comparison"] for row in comparisons)
    manifest = {
        "runId": f"phobert_ner_pilot_news_100_v1_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "cohortId": cohort["cohortId"], "cohortCount": 100, "pilotArticleCount": len(articles),
        "selection": selection,
        "model": {"modelId": MODEL_ID, "revision": MODEL_REVISION, "architecture": model.config.architectures,
                  "task": "fine-tuned token classification / NER", "id2label": id2label,
                  "baseModel": "vinai/phobert-base", "trainingDataset": "PhoNER_COVID19 (as stated in model card)",
                  "device": str(device), "fineTunedCheckpoint": True},
        "segmenter": {"name": "VnCoreNLP RDRSegmenter", "repositoryCommit": mvp.VNCORPUS_COMMIT,
                      "assets": {str(path.relative_to(ROOT)).replace("\\", "/"): mvp.sha256_file(path) for path in [
                          mvp.ASSET_ROOT / "VnCoreNLP-1.2.jar", mvp.ASSET_ROOT / "models/wordsegmenter/vi-vocab",
                          mvp.ASSET_ROOT / "models/wordsegmenter/wordsegmenter.rdr"]}},
        "versions": {"python": sys.version.split()[0], "torch": torch.__version__,
                     "transformers": __import__("transformers").__version__,
                     "py_vncorenlp": __import__("importlib.metadata", fromlist=["version"]).version("py-vncorenlp"),
                     "java": mvp.java_version()},
        "inputs": {"corpusPath": str(mvp.CORPUS_PATH.relative_to(ROOT)).replace("\\", "/"), "corpusSha256": corpus_sha,
                   "cohortManifestSha256": cohort_sha, "enrichmentManifestSha256": enrich_sha, "kgSha256": kg_sha,
                   "mvpCandidatePath": str(candidate_path.relative_to(ROOT)).replace("\\", "/"),
                   "mvpCandidateSha256": mvp.sha256_file(candidate_path),
                   "mvpInferencePath": str((mvp.OUT_DIR / "phobert_inference_results.jsonl").relative_to(ROOT)).replace("\\", "/"),
                   "mvpInferenceSha256": mvp.sha256_file(mvp.OUT_DIR / "phobert_inference_results.jsonl"),
                   "scriptPath": str(Path(__file__).relative_to(ROOT)).replace("\\", "/"),
                   "scriptSha256": mvp.sha256_file(Path(__file__)),
                   "dependenciesPath": "requirements-phobert-mvp.txt",
                   "dependenciesSha256": mvp.sha256_file(ROOT / "requirements-phobert-mvp.txt")},
        "metrics": {"articleSuccessCount": len(articles), "articleFailureCount": len(failed_articles),
                    "sentenceCount": sum(len(rows) for rows in sentence_rows_by_article.values()),
                    "chunkCount": len(all_chunks), "predictionCount": len(predictions),
                    "verifiedSpanPredictionCount": status_counts["VERIFIED_EXACT_SOURCE_RECONSTRUCTION"],
                    "unverifiedSpanPredictionCount": status_counts["UNVERIFIED_ALIGNMENT"],
                    "labelCounts": dict(label_counts), "comparisonCounts": dict(comparison_counts),
                    "sentenceAlignmentCounts": dict(alignment_counts), "goldTemplateSentenceCount": len(gold_template),
                    "mvpChunkSourceSpanMappingCounts": dict(mvp_alignment_counts),
                    "goldLabelsPresent": False, "precision": None, "recall": None, "f1": None,
                    "runtimeSeconds": round(time.perf_counter() - started, 2)},
        "processing": {"maxSequenceTokensIncludingSpecialTokens": MAX_TOKENS,
                       "sentenceBoundaryFirst": True, "longSentenceWindowOverlapSubtokens": LONG_SENTENCE_OVERLAP,
                       "truncation": False, "perWordPrediction": "first PhoBERT subtoken logits; argmax softmax confidence",
                       "spanAlignment": "compact NFC/casefold view omitting whitespace and segmenter underscores; exported only after exact normalized source reconstruction",
                       "unverifiedEntitySpanPolicy": "retain prediction with null originalText/startChar/endChar; do not export raw evidence",
                       "kgMatchIsGold": False, "rawCleanKgOntologyShaclDqsModified": False},
        "outputs": {},
    }

    report = make_report(manifest, predictions, comparisons, kg_candidates, alignment_counts, mvp_alignment_counts)
    report_path = OUT_DIR / "phobert_ner_pilot_report.md"
    report_path.write_text(report, encoding="utf-8")
    output_paths = [pred_path, compare_path, gold_path, report_path]
    manifest["outputs"] = {path.name: {"sha256": mvp.sha256_file(path), "bytes": path.stat().st_size} for path in output_paths}
    (OUT_DIR / "phobert_ner_run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"articles": len(articles), "chunks": len(all_chunks), "predictions": len(predictions),
                      "verified": status_counts["VERIFIED_EXACT_SOURCE_RECONSTRUCTION"],
                      "unverified": status_counts["UNVERIFIED_ALIGNMENT"], "labels": dict(label_counts),
                      "comparison": dict(comparison_counts), "runtimeSeconds": manifest["metrics"]["runtimeSeconds"],
                      "output": str(OUT_DIR)}, ensure_ascii=False))
    return 0


def make_report(manifest: dict[str, Any], predictions: list[dict[str, Any]], comparisons: list[dict[str, Any]],
                kg_candidates: list[dict[str, str]], alignment_counts: Counter[str],
                mvp_alignment_counts: Counter[str]) -> str:
    metrics = manifest["metrics"]
    labels = "\n".join(f"- `{label}`: {count}" for label, count in sorted(metrics["labelCounts"].items())) or "- None."
    outcomes = "\n".join(f"- `{label}`: {count}" for label, count in sorted(metrics["comparisonCounts"].items())) or "- None."
    selected = "\n".join(f"- `{aid}`" for aid in manifest["selection"]["selectedArticleIds"])
    unverified = sum(row["spanStatus"] != "VERIFIED_EXACT_SOURCE_RECONSTRUCTION" for row in predictions)
    mvp_alignment_summary = ", ".join(f"{key}={value}" for key, value in sorted(mvp_alignment_counts.items()))
    return f"""# PhoBERT NER Pilot — news_100_v1

## Kết quả

- Bài chạy thành công: **{metrics['articleSuccessCount']}/20**; lỗi bài: **{metrics['articleFailureCount']}**.
- Câu: **{metrics['sentenceCount']}**; chunk: **{metrics['chunkCount']}**; entity prediction: **{metrics['predictionCount']}**.
- Span xác minh được bằng cách đối chiếu lại với chuỗi nguyên văn: **{metrics['verifiedSpanPredictionCount']}**; span chưa xác minh: **{metrics['unverifiedSpanPredictionCount']}**. Prediction chưa xác minh giữ `originalText`, `startChar`, `endChar` là null.
- Không có gold labels; Precision/Recall/F1: **NOT_EVALUATED**. File annotation template có {metrics['goldTemplateSentenceCount']} câu chờ gán nhãn.
- Đây là pilot inference, không phải kết quả đánh giá chất lượng mô hình.

## Checkpoint và phạm vi nhãn

- Checkpoint fine-tuned: [`{MODEL_ID}`](https://huggingface.co/{MODEL_ID}) tại revision `{MODEL_REVISION}`; base model `vinai/phobert-base`; `RobertaForTokenClassification`.
- Nhãn trong config checkpoint: `{', '.join(manifest['model']['id2label'].values())}`.
- Model card ghi checkpoint huấn luyện trên **PhoNER_COVID19**, nên có provenance rõ hơn checkpoint generic đã thăm dò; license không được khai báo trong metadata đã kiểm tra. Trong artifact, nhãn được map `NAME → PERSON`, `DATE → DATETIME`; nhãn y tế đặc thù khác được giữ nguyên. Đây vẫn là lệch miền so với tin tài chính, nên chỉ coi kết quả là pilot kỹ thuật.
- Đã probe thêm [`quocanh944/phoBERT-ner`](https://huggingface.co/quocanh944/phoBERT-ner): checkpoint tương thích và có nhãn PERSON/ORGANIZATION/LOCATION/DATETIME, nhưng model card ghi dataset unknown và probe trên cohort cho 0 entity prediction; vì thế không chọn nó làm checkpoint chính.
- PhoBERT yêu cầu đầu vào đã word-segmented; pilot dùng RDRSegmenter giống khuyến nghị model card gốc của PhoBERT.
- Device: `{manifest['model']['device']}`. Token classification dùng logits subtoken đầu tiên của mỗi từ RDR; confidence là softmax của nhãn argmax.

## Chọn cohort con

Quy tắc: 15 bài CafeF, 3 bài en.Vietstock, 2 bài Vietstock; phân tầng ngắn/vừa/dài theo body length trong từng domain, ưu tiên nhóm candidate KG mới và có bài không có MVP candidate nếu có. Đây là cohort pilot có chủ đích, không phải mẫu ngẫu nhiên đại diện.

{selected}

## Nhãn dự đoán

{labels}

## So sánh với KG matching

{outcomes}

`KG_CANDIDATE_MATCH` chỉ là chồng lấp span và tương thích nhóm thô (PERSON ↔ CorporateLeader; ORGANIZATION ↔ Bank/Company); KG matching không được xem là gold. `POTENTIAL_NEW_ENTITY_OR_KG_ALIAS_GAP` không khẳng định entity mới trong KG.

## Điều tra lỗi token alignment của MVP

MVP `sourceSpanMapping` counts trên output chunk JSONL: **{mvp_alignment_summary}**. Căn nguyên trong code MVP là căn từ segmentation bằng regex trên text NFC đã gộp whitespace: token được tìm theo thứ tự và có word-boundary; các sai khác như RDR gộp/tách khác với spacing/punctuation ở body làm token không khớp. Với chunk dài, một số mapping được hạ xuống coarse để vẫn bảo toàn coverage; coverage ký tự 100% không đồng nghĩa mọi token offset đều chính xác.

Pilot xử lý riêng bằng compact alignment view NFC/casefold, bỏ whitespace và `_` chỉ khi dò vị trí. Input body không sửa. Trước khi xuất mỗi entity span, script lấy substring trực tiếp từ body rồi xác minh lại compact normalized mention bằng mention dự đoán. Các entity không vượt qua bước này được giữ prediction nhưng không có raw evidence/span. Sentence alignment counts trong pilot: `{dict(alignment_counts)}`; số prediction span chưa xác minh: **{unverified}**.

## Gold annotation và metric

`manual_gold_annotation_template.csv` lấy tối đa 2 câu nguyên văn mỗi bài theo thứ tự băm ổn định, không chứa prediction để giảm thiên lệch người gán nhãn. Hãy điền `goldEntitySpansJson` theo schema span half-open `[startChar,endChar)` trong câu/văn bản gốc, label từ nhãn checkpoint, sau đó adjudicate trước khi tính entity-level Precision/Recall/F1. Không tính metric dựa trên matching KG.

## Bảo toàn dữ liệu và tái lập

- Corpus SHA-256: `{manifest['inputs']['corpusSha256']}`; cohort/enrichment/KG hash được ghi trong run manifest.
- MVP output cũ không bị ghi đè; pilot outputs nằm riêng trong `runs/phobert_ner_pilot_news_100_v1/`.
- Không sửa RAW/CLEAN/enrichment, ontology, SHACL, KG hoặc DQS; không suy diễn event/relation.
- Runtime: **{metrics['runtimeSeconds']} giây**; Python `{manifest['versions']['python']}`, torch `{manifest['versions']['torch']}`, transformers `{manifest['versions']['transformers']}`, Java `{manifest['versions']['java']}`.

## Nguồn đối chiếu

- Model/checkpoint: [model card và files/revisions](https://huggingface.co/{MODEL_ID}/tree/{MODEL_REVISION}).
- PhoBERT và yêu cầu word segmentation: [PhoBERT model card](https://huggingface.co/vinai/phobert-base-v2).
- Thông tin nhãn/training dataset trong model card: [checkpoint README](https://huggingface.co/{MODEL_ID}/blob/{MODEL_REVISION}/README.md).
"""


if __name__ == "__main__":
    try:
        code = main()
    except BaseException:
        import traceback
        traceback.print_exc()
        code = 1
    sys.stdout.flush(); sys.stderr.flush()
    os._exit(code)
