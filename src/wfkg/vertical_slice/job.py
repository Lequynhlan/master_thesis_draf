"""Run the reviewed vertical slice from its checksum-pinned release snapshot."""

from __future__ import annotations

import hashlib
import ast
import csv
import json
import re
import subprocess
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from rdflib import Graph, Namespace

from wfkg.event_processing.candidates import generate_candidates
from wfkg.event_processing.canonicalization import canonicalize
from wfkg.event_processing.linking import link_entities
from wfkg.market_reaction.job import calculate_car, reaction_weights


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_release_snapshot(manifest_path: Path) -> dict[str, Any]:
    """Verify every frozen input and replay runner before executing anything."""
    manifest_path = manifest_path.resolve()
    release_root = manifest_path.parent
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    benchmark_snapshot = str(manifest.get("snapshotSelection", {}).get("benchmarkSnapshotId", ""))
    if not benchmark_snapshot.startswith("VN30_"):
        raise ValueError(f"Release benchmark is not the pinned VN30 snapshot: {benchmark_snapshot or 'missing'}")
    snapshot = release_root / "snapshot"
    failures = []
    for item in manifest["inputs"]["snapshotFiles"]:
        path = snapshot / item["path"]
        if not path.is_file():
            failures.append(f"MISSING:{item['path']}")
        elif sha256(path) != item["sha256"]:
            failures.append(f"HASH_MISMATCH:{item['path']}")
    scripts = {item["path"]: item for item in manifest["execution"]["scripts"]}
    runner = release_root / "replay_vertical_slice_release.py"
    expected = scripts.get("replay_vertical_slice_release.py")
    if not expected or not runner.is_file() or sha256(runner) != expected["sha256"]:
        failures.append("RUNNER_HASH_MISMATCH_OR_MISSING")
    if failures:
        raise ValueError("Frozen release verification failed: " + ", ".join(failures))
    return {"manifest": manifest, "releaseRoot": release_root, "snapshotRoot": snapshot,
            "runner": runner, "verifiedInputCount": len(manifest["inputs"]["snapshotFiles"])}


def run_vertical_slice(manifest_path: Path, output_dir: Path, config_path: Path) -> dict[str, Any]:
    """Run one isolated PoC replay after strict config and SHA-256 checks."""
    config = _read_config(config_path)
    if config.get("benchmark_index") != "VN30":
        raise ValueError("Integrated PoC is pinned to VN30; benchmark override is not permitted.")
    verified = verify_release_snapshot(manifest_path)
    package_audit = _audit_reviewed_domain_logic(verified["runner"], verified["snapshotRoot"])
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"Output directory must be new or empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    process = subprocess.run(
        [sys.executable, str(verified["runner"]), str(output_dir)],
        cwd=verified["releaseRoot"], capture_output=True, text=True, check=False,
    )
    if process.returncode:
        raise RuntimeError(f"Frozen replay failed ({process.returncode}): {process.stderr[-4000:]}")
    result_path = output_dir / "run_manifest.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    reaction_audit = _audit_reaction_outputs(output_dir / "reaction_results.csv")
    if len(reaction_audit) != 3 or any(item["status"] != "PASS" for item in reaction_audit):
        raise ValueError("Package AR/CAR/weight audit did not match all calculated reactions.")
    candidate_rows = list(csv.DictReader((output_dir / "candidate_results.csv").open(encoding="utf-8-sig", newline="")))
    if len(candidate_rows) != len(package_audit["candidates"]):
        raise ValueError("Package candidate generation count differs from frozen runner output.")
    package_candidates = {str(row["candidateId"]): row for row in package_audit["candidates"]}
    for row in candidate_rows:
        package_row = package_candidates.get(row["candidateId"])
        if package_row is None or abs(float(row["candidateScore"]) - float(package_row["candidateScore"])) > 1e-12:
            raise ValueError(f"Package candidate score parity failed: {row['candidateId']}")
    run_manifest = {
        "integrationId": "WFKG_VERTICAL_SLICE_INTEGRATED_POC_V1",
        "releaseManifest": str(Path(manifest_path).resolve()),
        "releaseId": verified["manifest"]["releaseId"],
        "inputSha256Verified": True,
        "verifiedSnapshotFiles": verified["verifiedInputCount"],
        "runnerSha256": sha256(verified["runner"]),
        "benchmark": config["benchmark_index"],
        "extractionMode": config.get("extraction_mode", "analyst_reviewed_snapshot"),
        "automaticNer": bool(config.get("automatic_ner", False)),
        "packageDomainAudit": package_audit,
        "packageReactionAudit": reaction_audit,
        "resultCounts": {key: result.get(key) for key in
                         ("events", "candidates", "computedReactions", "notEvaluatedWindows",
                          "shaclConforms", "shaclViolations", "sparqlRows")},
        "stdout": process.stdout.strip(),
    }
    (output_dir / "integrated_run_manifest.json").write_text(
        json.dumps(run_manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return run_manifest


def _audit_reviewed_domain_logic(runner: Path, snapshot: Path) -> dict[str, Any]:
    """Run package extraction/canonicalization/linking/candidate APIs on reviewed inputs."""
    tree = ast.parse(runner.read_text(encoding="utf-8"))
    annotations = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "annotations" for target in node.targets
        ):
            annotations = ast.literal_eval(node.value)
            break
    if not isinstance(annotations, list) or len(annotations) != 4:
        raise ValueError("Pinned reviewed annotation records are missing or changed shape.")

    events = [
        {"eventId": item["eventId"], "canonicalKey": item["key"], "articleIds": item["articles"],
         "confidenceScore": 0.85, "participants": [{"text": item["ticker"]}], "relationPaths": []}
        for item in annotations
    ]
    canonical = canonicalize(events)
    base = Graph().parse(snapshot / "data/gold/knowledge_graph.ttl", format="turtle")
    wfkg = Namespace("https://example.org/wfkg/v1#")
    entities = []
    for item in annotations:
        entities.append({"uri": str(wfkg[item["company"]]), "name": item["company"], "aliases": [item["ticker"]]})
        company, stock = wfkg[item["company"]], wfkg[f"HOSE:{item['ticker']}"]
        if (company, wfkg.hasStock, stock) not in base:
            raise ValueError(f"Direct company-stock KG path missing for {item['ticker']}.")
        item_event = next(x for x in canonical if x["eventId"] == item["eventId"])
        item_event["relationPaths"].append({
            "candidateId": str(wfkg["CANDIDATE:V3:" + item["ticker"] + ":" + item["key"].replace(":", "_")]),
            "ticker": item["ticker"], "impactType": "DIRECT", "confidenceScore": 0.85,
            "relationStrength": 1.0, "evidence": {"companyUri": str(company), "stockUri": str(stock),
                                                       "predicate": str(wfkg.hasStock)},
        })
    linked = link_entities(canonical, entities)
    link_statuses = [mention.get("linkingStatus") for event in linked for mention in event["participants"]]
    if len(link_statuses) != 4 or any(status != "LINKED_EXACT_ALIAS" for status in link_statuses):
        raise ValueError(f"Unexpected reviewed entity-link outcomes: {link_statuses}")
    candidates = generate_candidates(linked, ("TCB", "MBB", "SHB"))
    return {"reviewedEventCount": len(canonical), "linkedMentionCount": len(link_statuses),
            "linkStatuses": link_statuses, "candidateCount": len(candidates), "candidates": candidates}


def _audit_reaction_outputs(path: Path) -> list[dict[str, Any]]:
    """Recalculate each emitted CAR/weight from its listed close observations."""
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig", newline="")))
    audited = []
    for row in rows:
        dates = [date.fromisoformat(value.rsplit(":", 1)[-1]) for value in row["stockObservationUris"].split(";")]
        stock_values = [Decimal(value) for value in row["stockAdjustedClose"].split(";")]
        benchmark_values = [Decimal(value) for value in row["vn30Close"].split(";")]
        if len(dates) != len(stock_values) or len(dates) != len(benchmark_values):
            raise ValueError(f"Market close/provenance arity mismatch: {row['reactionId']}")
        stock = dict(zip(dates, stock_values)); benchmark = dict(zip(dates, benchmark_values))
        day0 = date.fromisoformat(row["day0"])
        lo, hi = map(int, re.findall(r"-?\d+", row["window"]))
        calculated = calculate_car(stock, benchmark, day0, (lo, hi), sessions=dates)
        if calculated["status"] != "EVALUATED":
            raise ValueError(f"Package CAR audit not evaluable for {row['reactionId']}: {calculated['reason']}")
        car = Decimal(row["CAR"])
        weights = reaction_weights(car, row["confidenceScore"], row["relationStrength"])
        diff = abs(calculated["car"] - car)
        weight_diff = max(abs(weights["impactScore"] - Decimal(row["impactScore"])),
                          abs(weights["reactionWeight"] - Decimal(row["reactionWeight"])),
                          abs(weights["signedWeight"] - Decimal(row["signedWeight"])))
        audited.append({"reactionId": row["reactionId"], "carDifference": str(diff),
                        "weightDifference": str(weight_diff), "status": "PASS" if diff <= Decimal("1e-12") and weight_diff <= Decimal("1e-12") else "FAIL"})
    return audited


def _read_config(path: Path) -> dict[str, Any]:
    import yaml
    values = yaml.safe_load(path.resolve().read_text(encoding="utf-8")) or {}
    integration = values.get("integration", {})
    if integration.get("id") != "WFKG_VERTICAL_SLICE_INTEGRATED_POC_V1":
        raise ValueError("Unexpected integrated PoC configuration id.")
    return integration
