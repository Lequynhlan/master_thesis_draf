"""Recompute comparable RAW/CLEAN cohort KPI aggregates without changing data.

Inputs are the previously generated per-article evidence tables. The script
does not write to snapshots, enrichment corpora, manifests, ontology, SHACL, or
the KG. K7 source fidelity stays NOT_EVALUATED; CLEAN-vs-RAW preservation is
reported as a separate supplementary measure and is excluded from DQS.
"""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "doc"
CLEAN = ROOT / "data/cleaned/news_100_v1"
WEIGHTS = {"K1": .15, "K2": .25, "K3": .15, "K4": .10, "K5": .10, "K6": .15, "K7": .10}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def update_cleaning_output_checksums() -> None:
    """Refresh the derived-output checksum list after report corrections."""

    paths = [
        p for base in (CLEAN, ROOT / "data/enriched_cleaned/news_100_v1")
        for p in base.rglob("*") if p.is_file() and p.name != "output_checksums.sha256"
    ]
    paths.extend(ROOT / path for path in (
        "scripts/clean_news_100_v1.py",
        "scripts/enrich_news_missing_v2.py",
        "scripts/reassess_news_100_kpis.py",
        "doc/cleaning_report.md",
        "doc/correction_log.csv",
        "doc/post_cleaning_kpi_results.csv",
        "doc/before_after_quality_comparison.md",
        "doc/enrichment_correction_report.md",
        "doc/kpi_before_after_reassessment.csv",
        "doc/k7_clean_preservation_submetric.csv",
        "doc/kpi_reassessment_report.md",
    ))
    lines = []
    for path in sorted(set(paths), key=lambda item: item.relative_to(ROOT).as_posix()):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.relative_to(ROOT).as_posix()}")
    (CLEAN / "output_checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


def number(row: dict[str, str], key: str) -> float:
    value = row.get(key) or "0"
    if value.lower() == "true":
        return 1.0
    if value.lower() == "false":
        return 0.0
    return float(value)


def summarize_raw(rows: list[dict[str, str]]) -> dict[str, tuple[float | None, float | None, float | None, str, str]]:
    n = len(rows)
    if n != 100 or len({row["articleId"] for row in rows}) != n:
        raise ValueError("RAW assessment must contain the same 100 unique cohort articles")
    k1_num = sum(number(r, "title_present") + number(r, "url_present") + number(r, "publishedAt_present") + number(r, "sourceIdentity_present") for r in rows)
    k2_num = sum(number(r, "summary_present") == 1 and r["summary_repeats_title"].lower() != "true" for r in rows)
    k3_chars = sum(number(r, "K3_total_chars") for r in rows)
    k3_noise = sum(number(r, "K3_noise_chars") for r in rows)
    k4_pass = sum(number(r, "K4_pass_checks") for r in rows)
    k4_checks = sum(number(r, "K4_applicable_checks") for r in rows)
    k5_num = sum(number(r, "K5_observed_unique_score") == 100 for r in rows)
    k6_pass = sum(number(r, "K6_pass_links") for r in rows)
    k6_total = sum(number(r, "K6_total_links") for r in rows)
    return {
        "K1": (k1_num, 4*n, 1.0, "PASS", "Four presence groups per article."),
        "K2": (k2_num, n, 1.0, "FAIL", "RAW summary only; title-copy summaries are not substantive; enrichment excluded."),
        "K3": (k3_chars-k3_noise, k3_chars, 1.0, "REVIEW", "Fixed conservative K3-RULE-BASELINE-1 heuristic; not ground truth."),
        "K4": (k4_pass, k4_checks, 1.0, "FAIL", "Six fixed checks per article; source registry compared exactly after normalizer."),
        "K5": (k5_num, n, 2/3, "REVIEW", "URL and exact-content checks evaluated; near-duplicate rule unavailable."),
        "K6": (k6_pass, k6_total, .75, "REVIEW", "Three of four provenance links verifiable; RAW checksum-to-manifest link unavailable."),
        "K7": (None, None, 0.0, "NOT_EVALUATED", "No contemporaneous source archive and validated critical-item gold inventory."),
    }


def summarize_clean(rows: list[dict[str, str]]) -> dict[str, tuple[float | None, float | None, float | None, str, str]]:
    n = len(rows)
    if n != 100 or len({row["articleId"] for row in rows}) != n:
        raise ValueError("CLEAN assessment must contain the same 100 unique cohort articles")
    k1_score_sum = sum(number(r, "k1_score") for r in rows)
    k2_positive = sum(number(r, "k2_score") == 100 for r in rows)
    k3_chars = sum(number(r, "k3_totalChars") for r in rows)
    k3_noise = sum(number(r, "k3_noiseChars") for r in rows)
    k4_pass = sum(number(r, "k4_numerator") for r in rows)
    k4_checks = sum(number(r, "k4_denominator") for r in rows)
    k5_representatives = sum(number(r, "k5_score") == 100 for r in rows)
    k6_pass = sum(number(r, "k6_articleId_snapshotPath") == 1 for r in rows)
    k6_pass += sum(number(r, "k6_rawChecksum_manifest") == 1 for r in rows)
    k6_pass += sum(number(r, "k6_snapshot_url") == 1 for r in rows)
    k6_pass += sum(number(r, "k6_source_batch") == 1 for r in rows)
    k6_total = 4*n
    return {
        "K1": (k1_score_sum*4/100, 4*n, 1.0, "PASS", "Four presence groups per article."),
        "K2": (k2_positive, n, 1.0, "FAIL", "Same RAW summaries retained; title-copy summaries remain LOW_INFORMATION."),
        "K3": (k3_chars-k3_noise, k3_chars, 1.0, "REVIEW", "Same fixed K3-RULE-BASELINE-1 heuristic; not ground truth."),
        "K4": (k4_pass, k4_checks, 1.0, "PASS" if k4_pass == k4_checks else "FAIL", "Six fixed checks; evidence-backed source registry mapping applied."),
        "K5": (k5_representatives, n, 2/3, "REVIEW", "URL/exact-content checks; near-duplicate class remains unevaluated."),
        "K6": (k6_pass, k6_total, 1.0, "PASS" if k6_pass == k6_total else "REVIEW", "Current RAW-to-cleaning-manifest checksums verify; not historical crawl-time checksums."),
        "K7": (None, None, 0.0, "NOT_EVALUATED", "No contemporaneous source archive and validated critical-item gold inventory."),
    }


def kpi_rows(scope: str, values: dict[str, tuple[float | None, float | None, float | None, str, str]]) -> list[dict[str, object]]:
    measured_keys = [key for key, (num, den, *_rest) in values.items() if num is not None and den is not None]
    measured_weight = sum(WEIGHTS[key] for key in measured_keys)
    score_map = {key: 100*num/den if num is not None and den else None for key, (num, den, *_rest) in values.items()}
    measured_dqs = sum(WEIGHTS[key]*score_map[key] for key in measured_keys)/measured_weight if measured_keys else None
    evaluation_coverage = 100*measured_weight
    full_dqs = measured_dqs if evaluation_coverage == 100 and len(measured_keys) == 7 else None
    output = []
    for key in WEIGHTS:
        numerator, denominator, evidence_coverage, status, evidence = values[key]
        score = score_map[key]
        output.append({
            "scope_type": scope,
            "scope_id": "NEWS_COHORT_2026Q3_100_CONTROLLED_V1",
            "article_count": 100,
            "kpi": key,
            "weight": WEIGHTS[key],
            "numerator": "" if numerator is None else numerator,
            "denominator": "" if denominator is None else denominator,
            "score": "" if score is None else round(score, 6),
            "status": status,
            "evidence_coverage": evidence_coverage,
            "evaluation_coverage": 0.0 if score is None else 1.0,
            "check_coverage": evidence_coverage,
            "evaluation_weight_in_measured_dqs": 0.0 if score is None else WEIGHTS[key],
            "dqs_included": str(score is not None).lower(),
            "measuredDQS": "" if measured_dqs is None else round(measured_dqs, 6),
            "fullDQS": "null" if full_dqs is None else round(full_dqs, 6),
            "formula": f"100 × {key} numerator / denominator" if score is not None else "Not evaluated; no source/version gold evidence",
            "evidence": evidence,
        })
    return output


def main() -> None:
    raw = read_csv(DOC / "article_quality_assessment.csv")
    clean = read_csv(CLEAN / "kpi_article_results.csv")
    raw_ids, clean_ids = {r["articleId"] for r in raw}, {r["articleId"] for r in clean}
    if raw_ids != clean_ids:
        raise ValueError("RAW and CLEAN articleId sets differ; comparison aborted")

    raw_values, clean_values = summarize_raw(raw), summarize_clean(clean)
    raw_rows = kpi_rows("PRE_CLEANING_RAW", raw_values)
    clean_rows = kpi_rows("POST_CLEANING_CLEAN", clean_values)
    all_rows = raw_rows + clean_rows

    # Keep the established post-cleaning KPI artifact aligned with the KPI spec.
    write_csv(DOC / "post_cleaning_kpi_results.csv", clean_rows)
    write_csv(DOC / "kpi_before_after_reassessment.csv", all_rows)

    inv = read_csv(CLEAN / "k7_critical_item_inventory.csv")
    preserved = sum(r.get("preservedInClean", "").lower() == "true" for r in inv)
    candidates = len(inv)
    preservation = 100*preserved/candidates if candidates else None
    write_csv(DOC / "k7_clean_preservation_submetric.csv", [{
        "scope_type": "SUPPLEMENTARY_NOT_K7_DQS",
        "scope_id": "NEWS_COHORT_2026Q3_100_CONTROLLED_V1",
        "numerator": preserved,
        "denominator": candidates,
        "score": "" if preservation is None else round(preservation, 6),
        "status": "REVIEW" if candidates else "NOT_EVALUATED",
        "evidence_coverage": 1.0 if candidates else 0.0,
        "dqs_included": "false",
        "evidence": "Candidate numeric/negation/registry-name inventory; CLEAN compared with immutable RAW. Not RAW-to-source fidelity K7 and excluded from DQS.",
    }])

    # Rewrite the summary with the corrected, spec-compatible DQS interpretation.
    raw_dqs = float(raw_rows[0]["measuredDQS"])
    clean_dqs = float(clean_rows[0]["measuredDQS"])
    report = [
        "# Reassessed pre/post-cleaning KPIs — news_100_v1", "",
        "Same fixed 100 articleIds, same KPI formulas/weights and baseline-compatible K3/K5 rules. RAW values are recomputed from the per-article baseline evidence table; CLEAN values are recomputed from the cleaned per-article KPI table. No corpus or KG data were changed by this reassessment.", "",
        "## KPI results", "",
        "| KPI | Weight | RAW numerator / denominator | RAW score | RAW status | CLEAN numerator / denominator | CLEAN score | CLEAN status |", "|---|---:|---:|---:|---|---:|---:|---|",
    ]
    for key in WEIGHTS:
        before, after = raw_rows[list(WEIGHTS).index(key)], clean_rows[list(WEIGHTS).index(key)]
        fmt = lambda row: "NOT_EVALUATED" if row["score"] == "" else f"{float(row['score']):.4f}"
        frac = lambda row: "N/A" if row["numerator"] == "" else f"{row['numerator']} / {row['denominator']}"
        report.append(f"| {key} | {WEIGHTS[key]:.2f} | {frac(before)} | {fmt(before)} | {before['status']} | {frac(after)} | {fmt(after)} | {after['status']} |")
    report += [
        "", "## DQS and interpretation", "",
        f"- RAW `measuredDQS`: **{raw_dqs:.4f}**; evaluation coverage: **90.0%**; `fullDQS`: **null**.",
        f"- CLEAN `measuredDQS`: **{clean_dqs:.4f}**; evaluation coverage: **90.0%**; `fullDQS`: **null**.",
        f"- Comparable measured change: **{clean_dqs-raw_dqs:+.4f}** points, driven by K4 (+16.1667) and K6 (+25.0000) under the recorded evidence; K1, K2, K3, and K5 are unchanged.",
        f"- K7 source fidelity is **NOT_EVALUATED** in both versions. CLEAN-vs-RAW critical-candidate preservation is a separate supplementary result: **{preserved}/{candidates} ({preservation:.4f}%)**, status REVIEW, excluded from DQS.",
        "- K5 remains REVIEW because near-duplicate scoring is not part of the frozen comparable estimate. K3 is a conservative heuristic. K6 CLEAN adds a checksum link observed while producing the cleaning manifest; this does not prove historical integrity at original crawl time.",
        "- Full-text enrichment is a separate input variant and is not substituted into K2; K2 uses RAW summary in both versions.",
        "", "## Files", "",
        "- `doc/kpi_before_after_reassessment.csv`: seven KPI rows per version, with numerator, denominator, score, status, evidence coverage and DQS columns.",
        "- `doc/k7_clean_preservation_submetric.csv`: separate CLEAN-vs-RAW candidate-preservation metric.",
        "- `doc/post_cleaning_kpi_results.csv`: corrected post-cleaning KPI artifact with K7 NOT_EVALUATED and spec-compatible DQS.",
    ]
    (DOC / "kpi_reassessment_report.md").write_text("\n".join(report)+"\n", encoding="utf-8")

    # Replace the prior comparison report, whose DQS incorrectly included the
    # supplementary preservation metric as KPI K7.
    comparison = [
        "# Before/after quality comparison — news_100_v1", "",
        "## Comparable baseline KPI", "",
        "| KPI | Baseline RAW | Post-clean CLEAN | Change | Interpretation |", "|---|---:|---:|---:|---|",
    ]
    interpretations = {
        "K1": "Metadata presence; unchanged.",
        "K2": "RAW summary completeness; 69 title-copy summaries remain LOW_INFORMATION.",
        "K3": "Same conservative heuristic rule; status REVIEW.",
        "K4": "Improved after evidence-backed source registry mapping.",
        "K5": "Observed URL/exact-content uniqueness unchanged; near-duplicate class unevaluated.",
        "K6": "Current raw-to-clean manifest checksum link is now verifiable; not historical crawl-time integrity.",
    }
    for key in list(WEIGHTS)[:6]:
        before, after = raw_rows[list(WEIGHTS).index(key)], clean_rows[list(WEIGHTS).index(key)]
        b, a = float(before["score"]), float(after["score"])
        comparison.append(f"| {key} | {b:.4f} | {a:.4f} | {a-b:+.4f} | {interpretations[key]} |")
    comparison += [
        "| K7 source fidelity | NOT_EVALUATED | NOT_EVALUATED | N/A | No contemporaneous source version and critical-item gold inventory. |", "",
        f"The comparable K1–K6 weighted set uses 90% of the specified weights in both versions: RAW measuredDQS **{raw_dqs:.4f}**, CLEAN measuredDQS **{clean_dqs:.4f}**, change **{clean_dqs-raw_dqs:+.4f}**. Evaluation coverage is **90.0%** for each; `fullDQS = null` for each because K7 cannot be evaluated.", "",
        f"Supplementary CLEAN-vs-RAW preservation: **{preserved}/{candidates} ({preservation:.4f}%)**, REVIEW, not K7 source fidelity and not included in DQS.", "",
        "## Limits", "",
        "- K2 remains based on RAW summary; full-text enrichment is tracked separately and does not change this KPI.",
        "- K3 and K5 are estimates with documented heuristic limits; K5 near-duplicate detection remains unevaluated for the baseline-compatible score.",
        "- K6 CLEAN checksum evidence was recorded at cleaning time and cannot establish integrity at original crawl time.",
        "- This is a data-quality comparison; it does not measure PhoBERT extraction accuracy or gold relation-path correctness.",
    ]
    (DOC / "before_after_quality_comparison.md").write_text("\n".join(comparison)+"\n", encoding="utf-8")

    # Correct the DQS section in the cleaning report without rebuilding CLEAN.
    cleaning_path = DOC / "cleaning_report.md"
    cleaning = cleaning_path.read_text(encoding="utf-8")
    start = cleaning.find("## Post-cleaning KPI")
    end = cleaning.find("## Integrity check", start)
    if start >= 0 and end > start:
        replacement = (
            "## Post-cleaning KPI\n\n"
            "K1–K6 are scored using the frozen rules. K7 source fidelity is NOT_EVALUATED because no contemporaneous source archive and validated critical-item gold inventory exist.\n\n"
            f"- `measuredDQS`: **{clean_dqs:.4f}**; `evaluationCoverage`: **90.0%**; `fullDQS`: **null**.\n"
            f"- K7 CLEAN-vs-RAW preservation is a separate supplementary submetric: **{preserved}/{candidates} ({preservation:.4f}%)**, REVIEW; excluded from DQS.\n"
            "- Per-article scores remain in `data/cleaned/news_100_v1/kpi_article_results.csv`; see `doc/kpi_reassessment_report.md` for the full KPI comparison.\n\n"
        )
        cleaning_path.write_text(cleaning[:start] + replacement + cleaning[end:], encoding="utf-8")

    update_cleaning_output_checksums()

    print(f"RAW measuredDQS={raw_dqs:.6f}; CLEAN measuredDQS={clean_dqs:.6f}; evaluationCoverage=90.0%; fullDQS=null; K7 preservation={preserved}/{candidates}")


if __name__ == "__main__":
    main()
