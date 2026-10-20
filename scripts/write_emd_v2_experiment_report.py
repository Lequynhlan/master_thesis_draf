"""Assemble final tables/report from the controlled EMD v2 run artifacts."""
from __future__ import annotations
import csv, hashlib, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/news_event_vertical_slice_20261019/emd_v2_experiment"
TRAIN = ROOT / "runs/phobert_bkee_emd_v2/training_report.json"
def read(p): return json.loads(p.read_text(encoding="utf-8"))
def write_csv(p, rows, fields):
    with p.open("w", encoding="utf-8-sig", newline="") as f:
        w=csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
def main():
    tr=read(TRAIN); err=read(RUN/"dev_error_analysis.json"); bas=read(RUN/"path_audits/baseline_v1/entity_linking_report.json"); v2=read(RUN/"path_audits/emd_v2/entity_linking_report.json")
    cohort=read(RUN/"emd_cohort_summary.json"); eae1=read(ROOT/"runs/news_event_vertical_slice_20261019/eae_trigger_conditioned_v1/summary.json"); eae2=read(RUN/"eae_trigger_conditioned_v2/summary.json")
    m1=tr["baseline"]; m2=tr["epochMetrics"][tr["bestEpoch"]-1]["dev"]
    rows=[]
    for name, m in [("EMD v1 unfiltered",m1["v1NoFilter"]),("EMD v1 threshold 0.65",m1["v1Threshold065"]),("EMD v2 best epoch 2",m2)]:
        rows.append({"configuration":name,"precision":m["precision"],"recall":m["recall"],"exact_span_type_f1":m["f1"],"TP":m["tp"],"FP":m["fp"],"FN":m["fn"]})
    write_csv(RUN/"dev_comparison.csv",rows,list(rows[0]))
    example_rows=[]
    for config, result in err.items():
        for item in result["examples"]:
            example_rows.append({"configuration":config,"errorKind":item["kind"],"sentId":item["sentId"],"sentence":item["text"],"goldText":item.get("goldText"),"predictedText":item.get("predictedText"),"goldType":item.get("goldType"),"predictedType":item.get("predictedType"),"goldSpan":item.get("goldSpan"),"predictedSpan":item.get("predictedSpan"),"related":json.dumps(item.get("relatedPrediction",item.get("relatedGold",[])),ensure_ascii=False)})
    write_csv(RUN/"dev_error_examples.csv",example_rows,list(example_rows[0]))
    v1hash=hashlib.sha256((ROOT/"models/phobert_bkee_emd_v1/model.safetensors").read_bytes()).hexdigest().upper()
    summary={"train": {"trainRows":tr["trainRows"],"devRows":tr["devRows"],"bestEpoch":tr["bestEpoch"],"bestDevF1":tr["bestDevF1"],"peakAllocatedGpuBytes":tr["peakAllocatedGpuBytes"],"checkpoint":tr["selectedCheckpoint"],"alignmentAudit":tr["alignmentAudit"]},
      "devComparison":rows,"v1CheckpointSha256":v1hash,"v1CheckpointPreserved":v1hash=="7B9AB543DDF252E549E7189F4AA3CABB09FBC3D46FA8A559F99B3514E62E9F18",
      "cohort":cohort,"entityLinking":{},"eae":{},"pathCoverage":{},
      "limits":["BKEE dev is the only scored split; BKEE test was not used.","No human-reviewed financial-domain gold labels are available, so financial-domain precision/F1 is unmeasured.","Cohort entity-link and path numbers are coverage/proposal counts, not accuracy evidence.","Only entity mentions contained within a staged Event evidence span are passed to the downstream EAE/path audit; all 273 article-level EMD outputs remain in cohort_emd_predictions.json."]}
    for label,obj in [("baselineV1",bas),("emdV2",v2)]:
        summary["entityLinking"][label]={"mentions":obj["mentionCount"],"statusCounts":obj["mentionStatusCounts"]}
        summary["pathCoverage"][label]={"eventsWithPath":obj["eventsWithAtLeastOneSufficientPath"],"eventsWithoutPath":obj["eventsWithoutSufficientPath"],"candidateCountByPath":obj["candidateCountByPath"],"eventPathStatusCounts":obj["eventPathStatusCounts"]}
    for label,obj in [("baselineV1",eae1),("emdV2",eae2)]: summary["eae"][label]={"eventsWithPredictedCompatibleParticipant":obj["eventsWithPredictedCompatibleParticipant"],"pairCounts":obj["pairCounts"]}
    (RUN/"experiment_metrics.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    def pct(x): return f"{x*100:.2f}%"
    lines=["# PhoBERT EMD v2 controlled experiment","","## Setup","",f"- Base: `vinai/phobert-base-v2`, initialized from preserved EMD v1 checkpoint; train split only ({tr['trainRows']:,} BKEE rows), dev ({tr['devRows']:,}) used for checkpoint selection.","- GPU: NVIDIA T1200, 4 GiB VRAM; peak allocated: {:.2f} GiB.".format(tr["peakAllocatedGpuBytes"]/1024**3),"- Config: 3 epochs, batch 1, accumulation 8, FP16, gradient checkpointing, max length 192, stride 48, LR 5e-6; best epoch selected by exact span + entity type micro F1.","- BIO/subword audit: {rows:,} train sentences, {entities:,} entities; overlap={overlaps}, invalid spans={invalid}, all {labels:,} BIO subword labels aligned; CLS/SEP ignored; no train rows dropped for length.".format(rows=tr['alignmentAudit']['rows'],entities=tr['alignmentAudit']['entities'],overlaps=tr['alignmentAudit']['overlappingEntityPairs'],invalid=tr['alignmentAudit']['invalidTokenSpans'],labels=tr['alignmentAudit']['bioLabelsChecked']),"", "## BKEE dev comparison", "", "| Configuration | Precision | Recall | Exact span/type F1 | TP / FP / FN |","|---|---:|---:|---:|---:|"]
    for r in rows: lines.append(f"| {r['configuration']} | {pct(r['precision'])} | {pct(r['recall'])} | {pct(r['exact_span_type_f1'])} | {r['TP']} / {r['FP']} / {r['FN']} |")
    lines += ["", "## Dev error breakdown", "", "Boundary categories count unmatched gold/prediction spans that overlap an entity of the same type. Type categories count identical boundaries with a different type. Missed/false positive are the remaining cases.", "", "| Configuration | Boundary FN | Missed entity | Type FN | Boundary FP | False positive | Type FP |", "|---|---:|---:|---:|---:|---:|---:|"]
    for key,label in [("v1_unfiltered","EMD v1 unfiltered"),("v1_threshold_065","EMD v1 threshold 0.65"),("v2","EMD v2")]:
        c=err[key]["counts"]; lines.append(f"| {label} | {c.get('boundaryMiss',0)} | {c.get('missedEntity',0)} | {c.get('typeMiss',0)} | {c.get('boundaryFP',0)} | {c.get('falsePositive',0)} | {c.get('typeFP',0)} |")
    lines += ["", "V2 reduces residual missed entities versus raw v1 (1,081 vs 1,170) and boundary false positives (530 vs 730), while finding more gold spans (recall 0.623). It still has 2,342 unmatched predictions without an overlapping same-type gold span, so precision remains limited. The thresholded v1 suppresses false positives but misses substantially more entities (1,688 FN). Reviewable dev examples are in `dev_error_examples.csv`."]
    lines += ["",f"Best checkpoint: [`models/phobert_bkee_emd_v2`](../../../../models/phobert_bkee_emd_v2), epoch {tr['bestEpoch']}; train loss fell {tr['epochMetrics'][0]['trainLoss']:.4f} → {tr['epochMetrics'][-1]['trainLoss']:.4f}. EMD v1 model SHA-256 is unchanged: `{v1hash}`.","", "## Frozen 100 article cohort: downstream coverage", "", "ED predictions were reused unchanged. EMD v2 detected {n} mentions across {a}/100 articles; {inside} mentions were wholly contained in existing Event evidence and used for EAE/path review.".format(n=cohort['emdMentionCount'],a=cohort['articlesWithAnyEmdMention'],inside=cohort['mentionsContainedInEventEvidence']),"", "| Measure | EMD v1 baseline | EMD v2 | Change |","|---|---:|---:|---:|"]
    pairs=[("Staged entity mentions",bas['mentionCount'],v2['mentionCount']),("URI MATCHED",bas['mentionStatusCounts'].get('MATCHED',0),v2['mentionStatusCounts'].get('MATCHED',0)),("Events with compatible EAE participant",eae1['eventsWithPredictedCompatibleParticipant'],eae2['eventsWithPredictedCompatibleParticipant']),("Events with ≥1 sufficient KG path",bas['eventsWithAtLeastOneSufficientPath'],v2['eventsWithAtLeastOneSufficientPath'])]
    for label,x,y in pairs: lines.append(f"| {label} | {x} | {y} | {y-x:+d} |")
    lines += ["", "| Path candidates | EMD v1 | EMD v2 |","|---|---:|---:|"]
    for path in ("DIRECT","INDIRECT_SUBSIDIARY","INDIRECT_LEADERSHIP","INDIRECT_INDUSTRY"): lines.append(f"| {path} | {bas['candidateCountByPath'].get(path,0)} | {v2['candidateCountByPath'].get(path,0)} |")
    lines += ["", "The downstream counts are review-stage coverage, not correctness. V2 yielded fewer staged mentions, URI matches, EAE participant proposals, and complete paths in this cohort. This can reflect changed detection and the evidence-containment gate; it does not establish whether the removed/additional spans were right. The 273 article-level detections (including mentions outside existing Event evidence) are preserved separately and were not promoted to other Events.","", "## Recommendation", "", "Use EMD v2 for a manually reviewed staging trial, not as a production replacement yet. Its exact span/type F1 improves +0.03496 over v1@0.65 and +0.07876 over unfiltered v1 on BKEE dev. However, precision is 0.376 and cohort link/path coverage falls, with no reviewed financial gold set to resolve the trade-off. Review a stratified sample of added, removed, and unchanged mentions before any production switch; keep EMD v1 active until that review demonstrates financial-domain quality.","", "## Artifacts and boundaries", "", "- `dev_comparison.csv`, `dev_error_examples.csv`, `experiment_metrics.json` — comparable metrics and inspectable dev errors.","- `cohort_emd_predictions.json` — all article-level EMD v2 outputs with offsets and confidence.","- `staging_review.json` and `eae_trigger_conditioned_v2/` — review-only downstream outputs.","- `path_audits/` — same resolver/path audit for baseline and v2.","- No crawl, ED rerun, ontology/SHACL/RAW/annotation changes, or main KG writes were performed. EAE checkpoint remained v1.",""]
    (RUN/"report.md").write_text("\n".join(lines),encoding="utf-8")
    print(json.dumps({"report":str(RUN/"report.md"),"v1CheckpointPreserved":summary['v1CheckpointPreserved']},ensure_ascii=False))
if __name__=="__main__": main()
