"""Fresh model-only inference for the small Financial KG vertical slice MVP."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wfkg.config import load_config
from wfkg.event_processing.extraction import ExtractorConfig, PhoBERTEventExtractor

ARTICLE_IDS = [
    "NEWS_ARTICLE:64427a6e8c606384dd4f",
    "NEWS_ARTICLE:959096d14783f1fcfc54",
    "NEWS_ARTICLE:0e308974b690bdc73a47",
    "NEWS_ARTICLE:d87a5dfa9094c5f7491f",
    "NEWS_ARTICLE:6d66836ff8d2987de058",
    "NEWS_ARTICLE:1085d2e41732b8aaf2fb",
    "NEWS_ARTICLE:869eb0b3510bc6d03163",
    "NEWS_ARTICLE:f4f98543e6f8131c4572",
]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--output", default="runs/phobert_vertical_slice_mvp_20261020_v1")
    args = parser.parse_args()
    if not 1 <= args.limit <= len(ARTICLE_IDS):
        parser.error(f"--limit must be 1..{len(ARTICLE_IDS)}")
    out = (ROOT / args.output).resolve()
    if ROOT not in out.parents:
        raise ValueError("Output must be inside the project.")
    out.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter()
    cohort_path = ROOT / "data/output/news_article_selection_manifest.json"
    raw_path = ROOT / "data/cleaned/news_100_v1/clean_articles.jsonl"
    enriched_path = ROOT / "data/enriched_cleaned/news_100_v1/articles.jsonl"
    raw = {str(row["articleId"]): row for row in read_jsonl(raw_path)}
    enriched = {str(row["articleId"]): row for row in read_jsonl(enriched_path)}
    cohort = json.loads(cohort_path.read_text(encoding="utf-8-sig"))
    cohort_ids = {str(row["articleId"]) for row in cohort["articles"]}
    selected = [article_id for article_id in ARTICLE_IDS[:args.limit]
                if article_id in raw and article_id in enriched and article_id in cohort_ids]
    if len(selected) != args.limit:
        raise RuntimeError(f"Expected {args.limit} selected articles; found {len(selected)}")

    config = load_config(ROOT / "config/vertical_slice.yaml")
    settings = config.values.get("extractor", {})
    extractor = PhoBERTEventExtractor(ExtractorConfig(
        model_id=str(settings.get("model_id", "vinai/phobert-base-v2")),
        checkpoint_path=ROOT / "models/phobert_bkee_event_detection_v2",
        label_mapping_path=ROOT / "models/phobert_bkee_event_detection_v2/label_mapping.json",
        model_version=str(settings.get("model_version", "bkee-bio-dev-selected-v2")),
        short_body_review_chars=int(settings.get("short_body_review_chars", 500)),
        device=args.device,
        entity_checkpoint_path=ROOT / "models/phobert_bkee_emd_v2",
        trigger_conditioned_argument_checkpoint_path=ROOT / "models/phobert_bkee_eae_trigger_conditioned_v1",
    ))
    rows: list[dict[str, Any]] = []
    for pos, article_id in enumerate(selected, 1):
        article = raw[article_id]
        enriched_article = enriched[article_id]
        prepared = extractor.prepare_input(article, enriched_article)
        row: dict[str, Any] = {
            "articleId": article_id,
            "title": article.get("title", ""),
            "sourceUrl": article.get("url", ""),
            "publishedAtRaw": article.get("publishedAt", ""),
            "inputSource": prepared.source,
            "inputStatus": prepared.status,
            "inputReason": prepared.reason,
            "inputSha256": prepared.sha256,
            "inputCharCount": prepared.char_count,
            "deviceRequested": args.device,
        }
        try:
            row["events"] = extractor.extract(article, enriched_article)
            row["status"] = "SUCCESS"
        except Exception as exc:
            row["events"] = []
            row["status"] = "FAILED"
            row["error"] = f"{type(exc).__name__}: {exc}"
        rows.append(row)
        print(f"[{pos}/{len(selected)}] {article_id}: {row['status']}, events={len(row['events'])}", flush=True)

    checkpoint_files = {
        "ED": ("models/phobert_bkee_event_detection_v2", ["config.json", "model.safetensors", "label_mapping.json"]),
        "EMD": ("models/phobert_bkee_emd_v2", ["config.json", "model.safetensors", "label_mapping.json"]),
        "EAE": ("models/phobert_bkee_eae_trigger_conditioned_v1", ["config.json", "model.safetensors"]),
    }
    checkpoint_hashes = {}
    for name, (directory, filenames) in checkpoint_files.items():
        checkpoint_hashes[name] = {
            filename: digest(ROOT / directory / filename)
            for filename in filenames if (ROOT / directory / filename).is_file()
        }
    artifact = {
        "schemaVersion": "phobert_mvp_fresh_inference_v1",
        "selectionReason": "Fixed 100-article cohort; selected by bank references in title/body for a small execution sample, not as gold or a relevance judgment.",
        "deviceRequested": args.device,
        "deviceActual": str(extractor._detector.device) if extractor._detector is not None else "NOT_LOADED",
        "checkpoints": {name: directory for name, (directory, _) in checkpoint_files.items()},
        "checkpointSha256": checkpoint_hashes,
        "inputFiles": {
            str(path.relative_to(ROOT)): digest(path)
            for path in (cohort_path, raw_path, enriched_path)
        },
        "elapsedSeconds": round(time.perf_counter() - start, 2),
        "articles": rows,
    }
    inference_path = out / "fresh_phobert_inference.json"
    inference_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(inference_path),
        "articles": len(rows),
        "success": sum(row["status"] == "SUCCESS" for row in rows),
        "events": sum(len(row["events"]) for row in rows),
        "device": artifact["deviceActual"],
        "elapsedSeconds": artifact["elapsedSeconds"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
