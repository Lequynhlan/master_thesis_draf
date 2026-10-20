"""PhoBERT chunk-embedding and KG entity-mention MVP for news_100_v1.

This is not a trained NER, event-extraction, or relation-extraction model.
Entity outputs are deterministic string-match candidates grounded in KG labels.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch
import transformers
from rdflib import Graph, Namespace, RDF, RDFS
from transformers import AutoModel, AutoTokenizer


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config/vertical_slice.yaml"
COHORT_MANIFEST_PATH = ROOT / "data/output/news_article_selection_manifest.json"
ENRICHMENT_MANIFEST_PATH = ROOT / "data/enriched_cleaned/news_100_v1/enrichment_manifest.json"
CORPUS_PATH = ROOT / "data/enriched_cleaned/news_100_v1/articles.jsonl"
KG_PATH = ROOT / "data/gold/knowledge_graph.ttl"
ONTOLOGY_PATH = ROOT / "schema/ontology.ttl"
ASSET_ROOT = ROOT / "runs/phobert_mvp_news_100_v1/vncorenlp"
OUT_DIR = ROOT / "runs/phobert_mvp_news_100_v1"
MODEL_ID = "vinai/phobert-base-v2"
MODEL_REVISION = "86cd7fd4c148980922ac11a2cf5e257f2ba639e1"
VNCORPUS_COMMIT = "62bbc58fe5d113c898eae112656be97dcf50b3a0"
MAX_SEQUENCE_TOKENS = 256
OVERLAP_SUBTOKENS = 32
BATCH_SIZE = 8
WFKG = Namespace("https://example.org/wfkg/v1#")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_corpus() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    """Read only the explicit cohort/enrichment artifacts; never discover by mtime."""

    import yaml

    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    configured_model = config.get("extractor", {}).get("model_id")
    if configured_model != MODEL_ID:
        raise RuntimeError(f"Config model {configured_model!r} differs from requested {MODEL_ID!r}")
    cohort = load_json(COHORT_MANIFEST_PATH)
    enrichment_manifest = load_json(ENRICHMENT_MANIFEST_PATH)
    records = [
        json.loads(line)
        for line in CORPUS_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    cohort_rows = cohort.get("articles", [])
    cohort_ids = [str(row["articleId"]) for row in cohort_rows]
    manifest_rows = enrichment_manifest.get("articles", [])
    manifest_ids = [str(row["articleId"]) for row in manifest_rows]
    corpus_ids = [str(row.get("articleId", "")) for row in records]
    expected = set(cohort_ids)
    if len(cohort_ids) != 100 or len(expected) != 100:
        raise RuntimeError(f"Expected exactly 100 unique cohort IDs, found {len(cohort_ids)}")
    if enrichment_manifest.get("cohortId") != cohort.get("cohortId") or enrichment_manifest.get("articleCount") != 100:
        raise RuntimeError("Enrichment manifest cohort identity/count does not match locked cohort")
    if len(manifest_ids) != 100 or set(manifest_ids) != expected or len(set(manifest_ids)) != 100:
        raise RuntimeError("Enrichment manifest articleId set does not exactly match locked cohort")
    if len(corpus_ids) != 100 or set(corpus_ids) != expected or len(set(corpus_ids)) != 100:
        raise RuntimeError("Full-text corpus articleId set does not exactly match locked cohort")

    manifest_by_id = {row["articleId"]: row for row in manifest_rows}
    for row in records:
        aid = row["articleId"]
        meta = manifest_by_id[aid]
        body = row.get("bodyText")
        if meta.get("status") != "FULLTEXT" or row.get("status") != "FULLTEXT":
            raise RuntimeError(f"{aid}: enrichment status is not FULLTEXT")
        if not isinstance(body, str) or not body.strip():
            raise RuntimeError(f"{aid}: missing bodyText; summary fallback is disabled")
        actual_body_hash = sha256_bytes(body.encode("utf-8"))
        expected_hash = meta.get("cleanBodySha256") or meta.get("bodySha256")
        if expected_hash and actual_body_hash != expected_hash:
            raise RuntimeError(f"{aid}: bodyText checksum differs from pinned enrichment manifest")
        if row.get("url") and meta.get("url") and row["url"] != meta["url"]:
            raise RuntimeError(f"{aid}: corpus URL differs from enrichment manifest")
    return cohort, enrichment_manifest, records, config


def object_values(graph: Graph, subject: Any, predicate: Any) -> list[str]:
    return [str(value).strip() for value in graph.objects(subject, predicate) if str(value).strip()]


def build_entity_catalog() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Read real KG entity URIs, labels, aliases, and group metadata."""

    graph = Graph()
    graph.parse(KG_PATH, format="turtle")
    graph.parse(ONTOLOGY_PATH, format="turtle")
    entity_classes = (WFKG.Company, WFKG.Bank, WFKG.CorporateLeader)
    entities: dict[str, dict[str, Any]] = {}
    subsidiary_uris = {str(uri) for uri in graph.objects(None, WFKG.subsidiaryCompany)}

    for entity_class in entity_classes:
        for uri in set(graph.subjects(RDF.type, entity_class)):
            uri_text = str(uri)
            if uri_text not in entities:
                types = {str(t) for t in graph.objects(uri, RDF.type)}
                group = (
                    "BANK" if str(WFKG.Bank) in types else
                    "CORPORATE_LEADER" if str(WFKG.CorporateLeader) in types else
                    "SUBSIDIARY_COMPANY" if uri_text in subsidiary_uris else "COMPANY"
                )
                entities[uri_text] = {"entityUri": uri_text, "entityGroup": group, "entityTypes": set(), "aliases": {}}
            entities[uri_text]["entityTypes"].add(str(entity_class).rsplit("#", 1)[-1])
            for predicate, origin in (
                (WFKG.fullName, "KG_FULL_NAME"),
                (WFKG.shortName, "KG_SHORT_NAME"),
                (WFKG.tickerSymbol, "KG_TICKER"),
                (RDFS.label, "KG_RDFS_LABEL"),
            ):
                for label in object_values(graph, uri, predicate):
                    entities[uri_text]["aliases"].setdefault(label, set()).add(origin)
            for alias_uri in graph.objects(uri, WFKG.hasAlias):
                for alias in object_values(graph, alias_uri, WFKG.aliasName):
                    entities[uri_text]["aliases"].setdefault(alias, set()).add("KG_LINKED_ALIAS")

    # Also resolve alias nodes back to their actual entity owners in the graph.
    for alias_uri in graph.subjects(RDF.type, WFKG.CompanyAlias):
        for alias in object_values(graph, alias_uri, WFKG.aliasName):
            for owner in graph.subjects(WFKG.hasAlias, alias_uri):
                owner_text = str(owner)
                if owner_text in entities:
                    entities[owner_text]["aliases"].setdefault(alias, set()).add("KG_COMPANY_ALIAS_NODE")

    alias_index: dict[str, list[dict[str, str]]] = defaultdict(list)
    catalog = []
    for uri_text in sorted(entities):
        item = entities[uri_text]
        public = {
            "entityUri": uri_text,
            "entityGroup": item["entityGroup"],
            "entityTypes": sorted(item["entityTypes"]),
            "aliases": sorted(item["aliases"]),
        }
        catalog.append(public)
        for alias, origins in item["aliases"].items():
            normalized = normalize_alias(alias)
            if len(normalized) < 2:
                continue
            alias_index[normalized].append({
                "entityUri": uri_text,
                "entityGroup": item["entityGroup"],
                "entityTypes": ",".join(sorted(item["entityTypes"])),
                "matchedAlias": alias,
                "aliasSource": ";".join(sorted(origins)),
            })
    return catalog, {key: values for key, values in alias_index.items()}


def normalize_alias(value: str) -> str:
    value = unicodedata.normalize("NFC", value).casefold()
    return re.sub(r"\s+", " ", value).strip()


def normalized_view(text: str) -> tuple[str, list[int], list[int]]:
    """Casefold/collapse whitespace while preserving a map to original offsets."""

    output: list[str] = []
    starts: list[int] = []
    ends: list[int] = []
    in_space = False
    for index, character in enumerate(text):
        if character.isspace():
            if output and not in_space:
                output.append(" ")
                starts.append(index)
                ends.append(index + 1)
            elif output and in_space:
                ends[-1] = index + 1
            in_space = True
            continue
        for folded in character.casefold():
            output.append(folded)
            starts.append(index)
            ends.append(index + 1)
        in_space = False
    return "".join(output), starts, ends


def _token_pattern(token: str) -> list[re.Pattern[str]]:
    alternatives = [token]
    if "_" in token:
        alternatives.append(token.replace("_", " "))
    patterns = []
    for alternative in dict.fromkeys(alternatives):
        normalized = normalize_alias(alternative)
        if not normalized:
            continue
        body = r"\s+".join(re.escape(part) for part in normalized.split(" "))
        left = r"(?<!\w)" if normalized[0].isalnum() or normalized[0] == "_" else ""
        right = r"(?!\w)" if normalized[-1].isalnum() or normalized[-1] == "_" else ""
        patterns.append(re.compile(left + body + right))
    return patterns


def align_segmented_tokens(text: str, segmented_sentence: str, cursor: int) -> tuple[list[dict[str, Any]], int, list[str]]:
    """Align VnCoreNLP words to source spans without jumping across distant text.

    RDRSegmenter can merge words when the crawled HTML has missing spaces. A
    failed token is retained as an alignment miss; it must not cause the next
    token to match somewhere much later in the article and shift every span.
    """

    view, starts, ends = normalized_view(text)
    aligned: list[dict[str, Any]] = []
    errors: list[str] = []
    search_at = cursor
    for token in segmented_sentence.split():
        found = None
        # Bound look-ahead so a missing/merged token cannot jump into a later
        # paragraph or sentence. Ordinary spaces and punctuation fit easily in
        # this window; missed tokens remain visible in alignment diagnostics.
        search_end = min(len(view), search_at + max(512, len(normalize_alias(token)) * 12))
        for pattern in _token_pattern(token):
            found = pattern.search(view, search_at, search_end)
            if found:
                break
        if found is None:
            errors.append(token)
            aligned.append({"word": token, "start": None, "end": None})
            continue
        start_index, end_index = found.span()
        original_start = starts[start_index]
        original_end = ends[end_index - 1]
        aligned.append({"word": token, "start": original_start, "end": original_end})
        search_at = end_index
    return aligned, search_at, errors


def make_sentence_units(body: str, segmenter: Any) -> list[dict[str, Any]]:
    if unicodedata.normalize("NFC", body) != body:
        raise ValueError("bodyText is not NFC; refusing to emit potentially incorrect source offsets")
    segmented_sentences = segmenter.word_segment(body)
    if not segmented_sentences:
        raise ValueError("RDRSegmenter returned no sentences for non-empty bodyText")
    cursor = 0
    staged = []
    token_alignment_errors = []
    for index, segmented in enumerate(segmented_sentences):
        words, cursor, errors = align_segmented_tokens(body, segmented, cursor)
        valid_words = [word for word in words if word["start"] is not None]
        if not valid_words:
            # Keep the source sentence and model input. Its exact token offsets
            # are unavailable, so use the current monotonic source cursor as a
            # coarse boundary; subsequent chunk spans are marked as coarse.
            view, starts, _ = normalized_view(body)
            boundary = starts[cursor] if cursor < len(starts) else len(body)
            staged.append({"sentenceId": index, "segmentedText": segmented, "words": words,
                           "anchorStart": boundary, "anchorEnd": boundary,
                           "alignmentStatus": "COARSE_NO_TOKEN_ALIGNMENT"})
            token_alignment_errors.extend(f"sentence={index},token={token}" for token in errors)
            continue
        staged.append({"sentenceId": index, "segmentedText": segmented, "words": words,
                       "anchorStart": valid_words[0]["start"], "anchorEnd": valid_words[-1]["end"],
                       "alignmentStatus": "PARTIAL_TOKEN_ALIGNMENT" if errors else "TOKEN_ALIGNED"})
        token_alignment_errors.extend(f"sentence={index},token={token}" for token in errors)

    # Sentence boundaries come from RDRSegmenter's sentence list. Include all
    # source whitespace and punctuation between sentence anchors in one span.
    for index, unit in enumerate(staged):
        unit["sourceStartChar"] = 0 if index == 0 else unit["anchorStart"]
        unit["sourceEndChar"] = staged[index + 1]["anchorStart"] if index + 1 < len(staged) else len(body)
        if unit["sourceEndChar"] < unit["sourceStartChar"]:
            raise ValueError(f"RDRSegmenter sentence offsets are out of order at sentence {index}")
    return staged


def token_count(tokenizer: Any, text: str) -> int:
    return len(tokenizer.encode(text, add_special_tokens=False, truncation=False))


def build_chunks(body: str, sentence_units: list[dict[str, Any]], tokenizer: Any) -> list[dict[str, Any]]:
    content_limit = MAX_SEQUENCE_TOKENS - tokenizer.num_special_tokens_to_add(pair=False)
    chunks: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []

    def flush_pending() -> None:
        nonlocal pending
        if not pending:
            return
        segmented = " ".join(unit["segmentedText"] for unit in pending)
        count = token_count(tokenizer, segmented)
        if count > content_limit:
            raise RuntimeError("sentence-packed chunk exceeded content token budget")
        chunks.append({
            "chunkId": len(chunks),
            "sentenceIds": [unit["sentenceId"] for unit in pending],
            "segmentedText": segmented,
            "sourceStartChar": pending[0]["sourceStartChar"],
            "sourceEndChar": pending[-1]["sourceEndChar"],
            "contentTokenCount": count,
            "overlapFromPreviousSubtokens": 0,
            "chunkingMethod": "SENTENCE_PACKING",
            "sourceSpanMapping": (
                "TOKEN_ALIGNED" if all(unit.get("alignmentStatus") == "TOKEN_ALIGNED" for unit in pending)
                else "COARSE_NO_TOKEN_ALIGNMENT" if any(unit.get("alignmentStatus") == "COARSE_NO_TOKEN_ALIGNMENT" for unit in pending)
                else "PARTIAL_TOKEN_ALIGNMENT"
            ),
        })
        pending = []

    for unit in sentence_units:
        sentence_tokens = token_count(tokenizer, unit["segmentedText"])
        if sentence_tokens <= content_limit:
            proposal = pending + [unit]
            proposed_text = " ".join(part["segmentedText"] for part in proposal)
            if pending and token_count(tokenizer, proposed_text) > content_limit:
                flush_pending()
            pending.append(unit)
            continue

        flush_pending()
        words = [word for word in unit["segmentedText"].split() if word]
        if not words:
            raise ValueError(f"Overlength sentence {unit['sentenceId']} has no segmenter words")
        word_token_counts = [token_count(tokenizer, word) for word in words]
        start_word = 0
        overlap_from_previous = 0
        while start_word < len(words):
            end_word = start_word
            count = 0
            while end_word < len(words) and count + word_token_counts[end_word] <= content_limit:
                count += word_token_counts[end_word]
                end_word += 1
            if end_word == start_word:
                # Extremely long unbroken token (normally a URL/file name): split
                # its spelling into tokenizer-sized fragments rather than truncate.
                word = words[start_word]
                lo, hi = 1, len(word)
                best = ""
                while lo <= hi:
                    mid = (lo + hi) // 2
                    fragment = word[:mid]
                    if token_count(tokenizer, fragment) <= content_limit:
                        best = fragment
                        lo = mid + 1
                    else:
                        hi = mid - 1
                if not best:
                    raise ValueError(f"Cannot split overlength token in sentence {unit['sentenceId']}")
                words[start_word] = word[len(best):]
                if not words[start_word]:
                    start_word += 1
                segment_text = best
                approximate = True
                word_indices = [start_word]
                actual_count = token_count(tokenizer, segment_text)
                chunk_method = "LONG_TOKEN_CHARACTER_SPLIT"
            else:
                segment_text = " ".join(words[start_word:end_word])
                actual_count = token_count(tokenizer, segment_text)
                if actual_count > content_limit:
                    raise RuntimeError("word-window content exceeds tokenizer budget")
                approximate = False
                word_indices = list(range(start_word, end_word))
                chunk_method = "LONG_SENTENCE_WORD_WINDOW"

            relevant = [unit["words"][i] for i in word_indices if i < len(unit["words"])]
            aligned = [word for word in relevant if word["start"] is not None]
            if relevant and len(aligned) != len(relevant) and not approximate:
                source_start, source_end = unit["sourceStartChar"], unit["sourceEndChar"]
                span_mapping = "COARSE_SENTENCE_SPAN_ALIGNMENT_MISS"
            elif aligned:
                source_start = min(word["start"] for word in aligned)
                source_end = max(word["end"] for word in aligned)
                span_mapping = "TOKEN_ALIGNED"
            else:
                source_start, source_end = unit["sourceStartChar"], unit["sourceEndChar"]
                span_mapping = "COARSE_SENTENCE_SPAN_ALIGNMENT_MISS"
            chunks.append({
                "chunkId": len(chunks),
                "sentenceIds": [unit["sentenceId"]],
                "segmentedText": segment_text,
                "sourceStartChar": source_start,
                "sourceEndChar": source_end,
                "contentTokenCount": actual_count,
                "overlapFromPreviousSubtokens": overlap_from_previous,
                "chunkingMethod": chunk_method,
                "sourceSpanMapping": "COARSE_WORD_SPAN" if approximate else span_mapping,
            })
            if end_word >= len(words):
                break
            # Back up whole segmenter tokens to create a <=32-subtoken overlap.
            next_start = end_word
            overlap_count = 0
            while next_start > start_word:
                candidate_count = word_token_counts[next_start - 1]
                if overlap_count + candidate_count > OVERLAP_SUBTOKENS:
                    break
                overlap_count += candidate_count
                next_start -= 1
            if next_start == start_word:
                next_start = end_word
                overlap_count = 0
            start_word = next_start
            overlap_from_previous = overlap_count

    flush_pending()
    if not chunks:
        raise ValueError("No chunks produced")

    # Partition inter-sentence whitespace between adjacent chunks, and include
    # leading/trailing characters so source-span union covers the entire body.
    chunks[0]["sourceStartChar"] = 0
    chunks[-1]["sourceEndChar"] = len(body)
    for index in range(len(chunks) - 1):
        if chunks[index]["sourceEndChar"] < chunks[index + 1]["sourceStartChar"]:
            chunks[index]["sourceEndChar"] = chunks[index + 1]["sourceStartChar"]
    chunks.sort(key=lambda row: (row["sourceStartChar"], row["chunkId"]))
    for index, chunk in enumerate(chunks):
        chunk["chunkId"] = index
        if not (0 <= chunk["sourceStartChar"] <= chunk["sourceEndChar"] <= len(body)):
            raise ValueError(f"Invalid chunk span {chunk['chunkId']}")
        chunk["originalText"] = body[chunk["sourceStartChar"]:chunk["sourceEndChar"]]
        # Add BOS/EOS and make the model tokenizer enforce the declared limit.
        encoded = tokenizer(chunk["segmentedText"], add_special_tokens=True, truncation=False)
        if len(encoded["input_ids"]) > MAX_SEQUENCE_TOKENS:
            raise RuntimeError(f"Chunk {chunk['chunkId']} exceeds {MAX_SEQUENCE_TOKENS} model tokens")
        chunk["sequenceTokenCount"] = len(encoded["input_ids"])

    intervals = sorted((chunk["sourceStartChar"], chunk["sourceEndChar"]) for chunk in chunks)
    covered = 0
    union_end = 0
    for start, end in intervals:
        if end > union_end:
            covered += end - max(start, union_end)
            union_end = end
    coverage = covered / max(1, len(body))
    if coverage < 1.0:
        raise ValueError(f"Chunk source-span coverage incomplete: {coverage:.6%}")
    return chunks


def run_embeddings(chunks: list[dict[str, Any]], tokenizer: Any, model: Any, device: torch.device) -> list[np.ndarray]:
    vectors: list[np.ndarray] = []
    model.eval()
    for offset in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[offset:offset + BATCH_SIZE]
        encoded = tokenizer(
            [chunk["segmentedText"] for chunk in batch],
            padding=True,
            truncation=False,
            add_special_tokens=True,
            return_tensors="pt",
        )
        if encoded["input_ids"].shape[1] > MAX_SEQUENCE_TOKENS:
            raise RuntimeError("Batch tokenizer emitted sequence beyond the explicit limit")
        attention = encoded["attention_mask"].to(device)
        input_ids = encoded["input_ids"].to(device)
        with torch.inference_mode():
            outputs = model(input_ids=input_ids, attention_mask=attention)
        hidden = outputs.last_hidden_state
        valid = attention.bool()
        special_mask = torch.tensor(
            [tokenizer.get_special_tokens_mask(row.tolist(), already_has_special_tokens=True) for row in input_ids.cpu()],
            dtype=torch.bool,
            device=device,
        )
        content_mask = valid & ~special_mask
        counts = content_mask.sum(dim=1, keepdim=True)
        if torch.any(counts == 0):
            raise RuntimeError("Chunk has no non-special attended token for mean pooling")
        pooled = (hidden * content_mask.unsqueeze(-1)).sum(dim=1) / counts
        values = pooled.float().cpu().numpy()
        for vector in values:
            if vector.shape != (int(model.config.hidden_size),):
                raise RuntimeError(f"Unexpected embedding shape {vector.shape}")
            if not np.isfinite(vector).all():
                raise RuntimeError("Embedding contains NaN or infinite values")
            vectors.append(vector.astype(np.float32, copy=False))
    return vectors


def entity_matches(body: str, sentence_units: list[dict[str, Any]], chunks: list[dict[str, Any]],
                   alias_index: dict[str, list[dict[str, str]]], article_id: str) -> list[dict[str, Any]]:
    view, starts, ends = normalized_view(body)
    matches_by_span: dict[tuple[int, int], dict[str, Any]] = {}
    for normalized_alias, candidates in alias_index.items():
        escaped = r"\s+".join(re.escape(part) for part in normalized_alias.split(" "))
        pattern = re.compile(r"(?<!\w)" + escaped + r"(?!\w)")
        for found in pattern.finditer(view):
            start, end = starts[found.start()], ends[found.end() - 1]
            surface = body[start:end]
            for candidate in candidates:
                key = (start, end)
                record = matches_by_span.setdefault(key, {"surface": surface, "candidates": {}})
                entity_uri = candidate["entityUri"]
                previous = record["candidates"].get(entity_uri)
                matched = {**candidate, "matchMethod": "EXACT" if surface == candidate["matchedAlias"] else "NORMALIZED_ALIAS"}
                if previous is None or (previous["matchMethod"] != "EXACT" and matched["matchMethod"] == "EXACT"):
                    record["candidates"][entity_uri] = matched

    output = []
    for (start, end), match in sorted(matches_by_span.items()):
        sentence = next((unit for unit in sentence_units if unit["sourceStartChar"] <= start and end <= unit["sourceEndChar"]), None)
        sentence_id = sentence["sentenceId"] if sentence else None
        sentence_start = sentence["sourceStartChar"] if sentence else start
        sentence_end = sentence["sourceEndChar"] if sentence else end
        evidence = body[sentence_start:sentence_end]
        candidate_values = sorted(match["candidates"].values(), key=lambda row: row["entityUri"])
        ambiguous = len(candidate_values) > 1
        containing_chunks = [c for c in chunks if c["sourceStartChar"] <= start and end <= c["sourceEndChar"]]
        chunk_id = min((c["chunkId"] for c in containing_chunks), default="")
        group_id = sha256_bytes(f"{article_id}:{start}:{end}".encode("utf-8"))[:16] if ambiguous else ""
        for candidate in candidate_values:
            if normalize_alias(match["surface"]) != normalize_alias(candidate["matchedAlias"]):
                raise RuntimeError("Entity candidate surface failed normalized alias verification")
            output.append({
                "articleId": article_id,
                "chunkId": chunk_id,
                "sentenceId": sentence_id if sentence_id is not None else "",
                "entityUri": candidate["entityUri"],
                "entityGroup": candidate["entityGroup"],
                "entityTypes": candidate["entityTypes"],
                "mention": match["surface"],
                "matchedAlias": candidate["matchedAlias"],
                "aliasSource": candidate["aliasSource"],
                "matchMethod": candidate["matchMethod"],
                "candidateStatus": "REVIEW_AMBIGUOUS_ALIAS" if ambiguous else "CANDIDATE_EXACT_MATCH",
                "ambiguousGroupId": group_id,
                "candidateEntityUris": "|".join(row["entityUri"] for row in candidate_values) if ambiguous else candidate["entityUri"],
                "startChar": start,
                "endChar": end,
                "sentenceStartChar": sentence_start,
                "sentenceEndChar": sentence_end,
                "evidenceSentence": evidence,
                "chunkSpanStatus": "CONTAINED" if chunk_id != "" else "REVIEW_SPAN_CROSSES_CHUNK_BOUNDARY",
                "candidateSource": "KG_STRING_MATCH_NOT_PHOBERT_NER",
            })
    return output


def process_article(article: dict[str, Any], tokenizer: Any, model: Any, device: torch.device,
                    segmenter: Any, alias_index: dict[str, list[dict[str, str]]]) -> dict[str, Any]:
    aid = article["articleId"]
    body = article["bodyText"]
    started = time.perf_counter()
    sentences = make_sentence_units(body, segmenter)
    chunks = build_chunks(body, sentences, tokenizer)
    vectors = run_embeddings(chunks, tokenizer, model, device)
    if len(chunks) != len(vectors):
        raise RuntimeError(f"{aid}: chunk/embedding count mismatch")
    candidates = entity_matches(body, sentences, chunks, alias_index, aid)
    for candidate in candidates:
        if not (0 <= int(candidate["startChar"]) < int(candidate["endChar"]) <= len(body)):
            raise RuntimeError(f"{aid}: invalid mention offsets")
        if normalize_alias(body[candidate["startChar"] : candidate["endChar"]]) != normalize_alias(candidate["mention"]):
            raise RuntimeError(f"{aid}: mention span does not reconstruct the surface text")
        if candidate["mention"] not in candidate["evidenceSentence"]:
            raise RuntimeError(f"{aid}: evidence sentence does not contain mention")
    token_total = sum(chunk["sequenceTokenCount"] for chunk in chunks)
    for chunk, vector in zip(chunks, vectors, strict=True):
        chunk.update({
            "articleId": aid,
            "modelId": MODEL_ID,
            "modelRevision": MODEL_REVISION,
            "embeddingDim": int(vector.shape[0]),
            "embeddingDtype": str(vector.dtype),
        })
    return {
        "articleId": aid,
        "status": "SUCCESS",
        "bodyChars": len(body),
        "sentenceCount": len(sentences),
        "chunkCount": len(chunks),
        "tokenCountWithSpecialTokens": token_total,
        "sourceSpanCoverage": 1.0,
        "entityCandidateCount": len(candidates),
        "elapsedSeconds": time.perf_counter() - started,
        "chunks": chunks,
        "vectors": vectors,
        "candidates": candidates,
    }


def save_outputs(out_dir: Path, article_results: list[dict[str, Any]], smoke: bool = False) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    flat_chunks = []
    flat_vectors = []
    result_rows = []
    candidates = []
    for result in article_results:
        if result["status"] != "SUCCESS":
            result_rows.append({key: value for key, value in result.items() if key not in {"chunks", "vectors", "candidates"}})
            continue
        for chunk, vector in zip(result["chunks"], result["vectors"], strict=True):
            chunk = dict(chunk)
            chunk["vectorIndex"] = len(flat_vectors)
            flat_chunks.append(chunk)
            flat_vectors.append(vector)
        candidates.extend(result["candidates"])
        result_rows.append({key: value for key, value in result.items() if key not in {"chunks", "vectors", "candidates"}})

    embeddings = np.stack(flat_vectors).astype(np.float32) if flat_vectors else np.empty((0, 768), dtype=np.float32)
    stem = "smoke" if smoke else "phobert"
    npz_path = out_dir / f"{stem}_embeddings.npz"
    jsonl_path = out_dir / f"{stem}_inference_results.jsonl"
    candidates_path = out_dir / f"{stem}_entity_candidates.csv"
    np.savez_compressed(
        npz_path,
        embeddings=embeddings,
        article_ids=np.asarray([chunk["articleId"] for chunk in flat_chunks], dtype=str),
        chunk_ids=np.asarray([chunk["chunkId"] for chunk in flat_chunks], dtype=np.int32),
        model_revisions=np.asarray([MODEL_REVISION] * len(flat_chunks), dtype=str),
    )
    write_jsonl(jsonl_path, [
        {**chunk, "embeddingFile": npz_path.name}
        for chunk in flat_chunks
    ] + [
        {"articleId": row["articleId"], "status": row["status"], "error": row.get("error", "")}
        for row in result_rows if row["status"] != "SUCCESS"
    ])
    candidate_fields = [
        "articleId", "chunkId", "sentenceId", "entityUri", "entityGroup", "entityTypes",
        "mention", "matchedAlias", "aliasSource", "matchMethod", "candidateStatus",
        "ambiguousGroupId", "candidateEntityUris", "startChar", "endChar",
        "sentenceStartChar", "sentenceEndChar", "evidenceSentence", "chunkSpanStatus", "candidateSource",
    ]
    write_csv(candidates_path, candidates, candidate_fields)

    # Read-back smoke checks exercise the exact persisted representation.
    with np.load(npz_path, allow_pickle=False) as loaded:
        loaded_vectors = loaded["embeddings"]
        loaded_article_ids = loaded["article_ids"]
        loaded_chunk_ids = loaded["chunk_ids"]
        if loaded_vectors.shape != embeddings.shape or loaded_vectors.dtype != np.float32:
            raise RuntimeError("Saved NPZ embedding shape/dtype did not round-trip")
        if not np.isfinite(loaded_vectors).all():
            raise RuntimeError("Saved NPZ contains non-finite embedding values")
        if len(loaded_article_ids) != len(flat_chunks) or len(loaded_chunk_ids) != len(flat_chunks):
            raise RuntimeError("Saved NPZ index arrays did not round-trip")
    persisted_rows = [
        json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    if len(persisted_rows) != len(flat_chunks) + sum(row["status"] != "SUCCESS" for row in result_rows):
        raise RuntimeError("Saved inference JSONL row count did not round-trip")
    with candidates_path.open("r", encoding="utf-8-sig", newline="") as stream:
        persisted_candidates = list(csv.DictReader(stream))
    if len(persisted_candidates) != len(candidates):
        raise RuntimeError("Saved entity-candidate CSV row count did not round-trip")
    for row in persisted_rows:
        if "vectorIndex" in row:
            vector_index = int(row["vectorIndex"])
            if str(loaded_article_ids[vector_index]) != row["articleId"] or int(loaded_chunk_ids[vector_index]) != int(row["chunkId"]):
                raise RuntimeError("Saved JSONL chunk metadata does not align with NPZ index arrays")
    for row in persisted_candidates:
        if int(row["startChar"]) >= int(row["endChar"]) or row["mention"] not in row["evidenceSentence"]:
            raise RuntimeError("Persisted candidate lost valid span/evidence during CSV round-trip")
    return {
        "articleResults": result_rows,
        "chunkMetadata": flat_chunks,
        "candidateRows": candidates,
        "embeddingArrayShape": list(embeddings.shape),
        "embeddingArrayDtype": str(embeddings.dtype),
        "files": [npz_path, jsonl_path, candidates_path],
    }


def version_or_missing(package: str) -> str:
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return "NOT_INSTALLED"


def java_version() -> str:
    result = subprocess.run(["java", "-version"], capture_output=True, text=True, check=False)
    return (result.stderr or result.stdout).splitlines()[0] if result.returncode == 0 else f"ERROR: {result.stderr.strip()}"


def write_report(out_dir: Path, manifest: dict[str, Any], final_rows: list[dict[str, Any]],
                 candidates: list[dict[str, Any]], failures: list[dict[str, str]], smoke_stats: dict[str, Any]) -> None:
    successful = sum(row["status"] == "SUCCESS" for row in final_rows)
    failed = len(final_rows) - successful
    groups = Counter(row["entityGroup"] for row in candidates)
    ambiguous = [row for row in candidates if row["candidateStatus"] == "REVIEW_AMBIGUOUS_ALIAS"]
    total_chunks = sum(int(row.get("chunkCount", 0)) for row in final_rows)
    total_tokens = sum(int(row.get("tokenCountWithSpecialTokens", 0)) for row in final_rows)
    body_chars = sum(int(row.get("bodyChars", 0)) for row in final_rows)
    covered = sum(int(row.get("bodyChars", 0)) for row in final_rows if row["status"] == "SUCCESS")
    span_mapping_counts = Counter(
        chunk.get("sourceSpanMapping", "UNSPECIFIED")
        for row in final_rows if row["status"] == "SUCCESS"
        for chunk in row.get("chunks", [])
    )
    failure_lines = "\n".join(f"- `{row['articleId']}`: {row['error']}" for row in failures) or "- None."
    group_lines = "\n".join(f"- {name}: {count}" for name, count in sorted(groups.items())) or "- None."
    ambiguous_lines = "\n".join(
        f"- `{row['articleId']}` mention `{row['mention']}` at [{row['startChar']}, {row['endChar']}): {row['candidateEntityUris']}"
        for row in ambiguous
    ) or "- None."
    report = f"""# PhoBERT MVP run report — news_100_v1

## Result

- Articles succeeded: **{successful}/100**; failed: **{failed}**.
- Total chunks embedded: **{total_chunks}**; token count including special tokens: **{total_tokens}**.
- Full-text span coverage among successful articles: **{100.0 if successful == 100 else (100.0 * covered / max(1, sum(int(r.get('bodyChars', 0)) for r in final_rows))):.2f}%** ({covered}/{sum(int(r.get('bodyChars', 0)) for r in final_rows)} source characters).
- Entity mention candidates: **{len(candidates)}**; ambiguous candidate rows: **{len(ambiguous)}**.
- Chunk-to-source span mapping: {", ".join(f"{name}={count}" for name, count in sorted(span_mapping_counts.items()))}.
- Run duration: **{manifest['runtimeSeconds']:.2f} seconds** (model loading plus smoke and full-corpus inference).

## Runtime and model

- Python: `{manifest['versions']['python']}`; PyTorch: `{manifest['versions']['torch']}`; Transformers: `{manifest['versions']['transformers']}`; NumPy: `{manifest['versions']['numpy']}`.
- Java: `{manifest['versions']['java']}`; `py-vncorenlp`: `{manifest['versions']['py_vncorenlp']}`; RDRSegmenter commit: `{manifest['segmenter']['repositoryCommit']}`.
- Model: `{manifest['model']['modelId']}` at immutable revision `{manifest['model']['revision']}`; device `{manifest['model']['device']}`; hidden size `{manifest['model']['hiddenSize']}`.
- Embedding: last hidden state mean-pooling over attended non-special tokens; saved as float32. This is an embedding run, not NER/event extraction.
- Hugging Face emitted a missing `pooler.dense` initialization warning while loading `AutoModel`; the MVP uses mean-pooled `last_hidden_state`, so the pooler is not used.

## Smoke test

- Status: **{smoke_stats['status']}**; articles: **{smoke_stats['articleCount']}**; chunks: **{smoke_stats['chunkCount']}**; embeddings: **{smoke_stats['embeddingCount']}**; validated candidate rows: **{smoke_stats['candidateCount']}**.
- Checks: model/tokenizer loaded at pinned revision; RDRSegmenter ran; source spans covered each body; all chunk sequences fit 256 tokens; embeddings passed shape/dtype/finite checks; NPZ/JSONL/CSV read-back checks passed.

## Candidates by KG-derived entity group

{group_lines}

All rows are deterministic exact/normalized alias matches against KG labels. They are candidates only and are not PhoBERT NER predictions or asserted relations.

### Ambiguous aliases

{ambiguous_lines}

## Article failures

{failure_lines}

## Reproducibility inputs

- Cohort manifest: `{manifest['inputs']['cohortManifestPath']}` SHA-256 `{manifest['inputs']['cohortManifestSha256']}`.
- Enrichment manifest: `{manifest['inputs']['enrichmentManifestPath']}` SHA-256 `{manifest['inputs']['enrichmentManifestSha256']}`.
- Corpus: `{manifest['inputs']['corpusPath']}` SHA-256 `{manifest['inputs']['corpusSha256']}`.
- KG: `{manifest['inputs']['kgPath']}` SHA-256 `{manifest['inputs']['kgSha256']}`; ontology: `{manifest['inputs']['ontologySha256']}`.
- Cohort/enrichment/corpus each resolved to the same 100 articleIds. No summary fallback, DQS changes, ontology/SHACL edits, or KG writes occurred.

## Output files

`phobert_inference_results.jsonl`, `phobert_embeddings.npz`, `phobert_entity_candidates.csv`, `phobert_run_manifest.json`.
"""
    (out_dir / "phobert_run_report.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-only", action="store_true", help="Run and persist only the first three article smoke test")
    args = parser.parse_args()
    run_started = time.perf_counter()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cohort, enrichment_manifest, records, config = read_corpus()
    cohort_order = [row["articleId"] for row in cohort["articles"]]
    by_id = {row["articleId"]: row for row in records}
    records = [by_id[aid] for aid in cohort_order]
    entity_catalog, alias_index = build_entity_catalog()

    expected_assets = [ASSET_ROOT / "VnCoreNLP-1.2.jar", ASSET_ROOT / "models/wordsegmenter/vi-vocab",
                       ASSET_ROOT / "models/wordsegmenter/wordsegmenter.rdr"]
    missing_assets = [str(path) for path in expected_assets if not path.is_file()]
    if missing_assets:
        raise FileNotFoundError("Missing RDRSegmenter assets; run scripts/setup_phobert_mvp_assets.py: " + ", ".join(missing_assets))

    torch.set_num_threads(min(4, os.cpu_count() or 1))
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, revision=MODEL_REVISION, use_fast=False)
    model = AutoModel.from_pretrained(MODEL_ID, revision=MODEL_REVISION)
    model.to(device)
    model.eval()

    # py_vncorenlp changes process cwd during initialization; resolve all paths
    # first and restore cwd immediately after the JVM starts.
    import py_vncorenlp

    original_cwd = Path.cwd()
    segmenter = py_vncorenlp.VnCoreNLP(annotators=["wseg"], save_dir=str(ASSET_ROOT.resolve()))
    os.chdir(original_cwd)

    smoke_records = records[:3]
    smoke_results = []
    for article in smoke_records:
        try:
            smoke_results.append(process_article(article, tokenizer, model, device, segmenter, alias_index))
        except Exception as exc:
            smoke_results.append({"articleId": article["articleId"], "status": "FAILED", "bodyChars": len(article.get("bodyText", "")), "error": f"{type(exc).__name__}: {exc}"})
    if any(row["status"] != "SUCCESS" for row in smoke_results):
        save_outputs(OUT_DIR / "smoke", smoke_results, smoke=True)
        failures = [row for row in smoke_results if row["status"] != "SUCCESS"]
        write_jsonl(OUT_DIR / "smoke_failures.jsonl", failures)
        print(json.dumps({"smoke":"FAIL","failures":failures},ensure_ascii=False))
        return 2
    smoke_saved = save_outputs(OUT_DIR / "smoke", smoke_results, smoke=True)
    smoke_stats = {
        "status": "PASS",
        "articleCount": len(smoke_results),
        "chunkCount": len(smoke_saved["chunkMetadata"]),
        "embeddingCount": smoke_saved["embeddingArrayShape"][0],
        "candidateCount": len(smoke_saved["candidateRows"]),
    }
    if args.smoke_only:
        print(json.dumps({"smoke":"PASS", **smoke_stats}, ensure_ascii=False))
        return 0

    results = list(smoke_results)
    failures: list[dict[str, str]] = []
    for article in records[3:]:
        try:
            results.append(process_article(article, tokenizer, model, device, segmenter, alias_index))
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            results.append({"articleId": article["articleId"], "status": "FAILED", "bodyChars": len(article.get("bodyText", "")), "error": error})
            failures.append({"articleId": article["articleId"], "error": error})

    saved = save_outputs(OUT_DIR, results)
    result_rows = saved["articleResults"]
    flat_chunks = saved["chunkMetadata"]
    candidates = saved["candidateRows"]
    asset_hashes = {str(path.relative_to(ROOT)).replace("\\", "/"): sha256_file(path) for path in expected_assets}
    revisions = {
        "python": sys.version.split()[0],
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "numpy": np.__version__,
        "rdflib": importlib.metadata.version("rdflib"),
        "py_vncorenlp": version_or_missing("py-vncorenlp"),
        "java": java_version(),
    }
    manifest = {
        "runId": f"phobert_mvp_news_100_v1_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "cohortId": cohort.get("cohortId"),
        "cohortCount": len(records),
        "articleSuccessCount": sum(row["status"] == "SUCCESS" for row in result_rows),
        "articleFailureCount": sum(row["status"] != "SUCCESS" for row in result_rows),
        "chunkCount": len(flat_chunks),
        "tokenCountWithSpecialTokens": sum(int(row["sequenceTokenCount"]) for row in flat_chunks),
        "embeddingShape": saved["embeddingArrayShape"],
        "embeddingDtype": saved["embeddingArrayDtype"],
        "entityCandidateCount": len(candidates),
        "ambiguousCandidateCount": sum(row["candidateStatus"] == "REVIEW_AMBIGUOUS_ALIAS" for row in candidates),
        "entityCatalogCount": len(entity_catalog),
        "runtimeSeconds": time.perf_counter() - run_started,
        "smokeTest": smoke_stats,
        "model": {
            "modelId": MODEL_ID,
            "revision": MODEL_REVISION,
            "device": str(device),
            "hiddenSize": int(model.config.hidden_size),
            "maxSequenceTokensIncludingSpecialTokens": MAX_SEQUENCE_TOKENS,
            "fineTuned": False,
            "taskHead": None,
            "pooling": "attention-mask mean of last_hidden_state excluding all special tokens",
        },
        "segmenter": {
            "name": "VnCoreNLP RDRSegmenter",
            "annotators": ["wseg"],
            "repository": "https://github.com/vncorenlp/VnCoreNLP",
            "repositoryCommit": VNCORPUS_COMMIT,
            "assetSha256": asset_hashes,
        },
        "versions": revisions,
        "inputs": {
            "cohortManifestPath": str(COHORT_MANIFEST_PATH.relative_to(ROOT)).replace("\\", "/"),
            "cohortManifestSha256": sha256_file(COHORT_MANIFEST_PATH),
            "enrichmentManifestPath": str(ENRICHMENT_MANIFEST_PATH.relative_to(ROOT)).replace("\\", "/"),
            "enrichmentManifestSha256": sha256_file(ENRICHMENT_MANIFEST_PATH),
            "corpusPath": str(CORPUS_PATH.relative_to(ROOT)).replace("\\", "/"),
            "corpusSha256": sha256_file(CORPUS_PATH),
            "kgPath": str(KG_PATH.relative_to(ROOT)).replace("\\", "/"),
            "kgSha256": sha256_file(KG_PATH),
            "ontologySha256": sha256_file(ONTOLOGY_PATH),
        },
        "processingPolicy": {
            "textField": "bodyText",
            "summaryFallback": False,
            "sentenceSegmentation": "VnCoreNLP word_segment sentence output",
            "chunking": "sentence packing; long sentence word-window with up to 32 subtoken overlap; no truncation",
            "sourceOffsets": "0-based Unicode code-point half-open [start,end) over exact bodyText",
            "entityMatching": "exact-case or NFC/casefold/whitespace-normalized aliases with Unicode word boundaries",
            "relationOrEventInferred": False,
            "dqsModified": False,
        },
        "outputs": {},
        "articleResults": result_rows,
        "failures": failures,
    }
    # Hash final artifacts before the manifest is written; manifest self-hash is omitted.
    output_paths = [OUT_DIR / "phobert_inference_results.jsonl", OUT_DIR / "phobert_embeddings.npz",
                    OUT_DIR / "phobert_entity_candidates.csv"]
    manifest["outputs"] = {
        path.name: {"sha256": sha256_file(path), "bytes": path.stat().st_size}
        for path in output_paths
    }
    (OUT_DIR / "phobert_run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_report(OUT_DIR, manifest, result_rows, candidates, failures, smoke_stats)
    manifest["outputs"]["phobert_run_report.md"] = {
        "sha256": sha256_file(OUT_DIR / "phobert_run_report.md"),
        "bytes": (OUT_DIR / "phobert_run_report.md").stat().st_size,
    }
    # Add report checksum in the final manifest.
    (OUT_DIR / "phobert_run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "smoke": "PASS",
        "articlesSucceeded": manifest["articleSuccessCount"],
        "articlesFailed": manifest["articleFailureCount"],
        "chunks": manifest["chunkCount"],
        "entityCandidates": manifest["entityCandidateCount"],
        "ambiguousCandidates": manifest["ambiguousCandidateCount"],
        "runtimeSeconds": round(manifest["runtimeSeconds"], 2),
        "outputs": str(OUT_DIR),
    }, ensure_ascii=False))
    return 0 if manifest["articleFailureCount"] == 0 else 1


if __name__ == "__main__":
    # pyjnius leaves a non-daemon JVM thread alive after Python work completes.
    # Flush outputs and terminate this one-shot CLI process explicitly so smoke
    # and corpus runs return control to the caller instead of hanging.
    try:
        exit_code = main()
    except BaseException:
        import traceback
        traceback.print_exc()
        exit_code = 1
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(exit_code)
