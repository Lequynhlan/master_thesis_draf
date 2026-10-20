"""Write human-readable fair-cohort diagnosis from audited artifacts."""
import csv,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"runs/news_event_vertical_slice_20261019/emd_v2_experiment/diagnosis"
def j(p):return json.loads(p.read_text(encoding="utf8"))
def rows(p):return list(csv.DictReader(p.open(encoding="utf-8-sig")))
def main():
 s=j(OUT/"parity_and_cause_summary.json")
 v1=j(ROOT/"runs/news_event_vertical_slice_20261019/emd_v2_experiment/path_audits_fair/fair_baseline_v1/entity_linking_report.json")
 v2=j(ROOT/"runs/news_event_vertical_slice_20261019/emd_v2_experiment/path_audits_fair/emd_v2/entity_linking_report.json")
 e1=j(ROOT/"runs/news_event_vertical_slice_20261019/emd_v2_experiment/fair_baseline_v1/eae_trigger_conditioned_v1/summary.json")
 e2=j(ROOT/"runs/news_event_vertical_slice_20261019/emd_v2_experiment/eae_trigger_conditioned_v2/summary.json")
 loss=rows(OUT/"lost_event_paths.csv")
 lines=["# EMD v1 / v2 linking and KG path diagnosis","","## Fair comparison controls","",
 f"- Same {s['articleCount']} saved articles and prepared text input; no crawl. Both passes used current `prepare_extraction_input`, VnCoreNLP segmentation, PhoBERT span decoding, `max_length={s['checkpointAndInferenceParity']['v1MaxLength']}`, `stride={s['checkpointAndInferenceParity']['v1Stride']}`, and no confidence threshold.",
 f"- EMD v1 was rerun on the cohort to remove uncertainty from its old run metadata. Its {s['historicalV1ExactReproduction']['historicalUniqueMentions']} unique spans reproduce the saved v1 set exactly ({s['historicalV1ExactReproduction']['exactOverlap']} shared; 0 removed/added). V2 changed the fine-tuned token-classifier weights; base revision, entity label set, tokenizer files and inference window settings match. The only tokenizer config metadata difference is `is_local` (false/true); it does not alter the matching vocab/BPE assets.",
 f"- Same 155 frozen ED Events, triggers, evidence text and offsets on both sides: `{s['frozenEventAndEvidenceEqual']}`. Same EAE checkpoint: `{s['eaeCheckpoint']}`. Same resolver/path audit code, KG alias registry and ontology/SHACL v1.0.5. All staged mentions on both sides are span-verified and contained in evidence (v1 {s['evidenceContainmentGate']['v1'].get('True',0)}; v2 {s['evidenceContainmentGate']['v2'].get('True',0)}).",
 "- Threshold check: v1 cohort is unfiltered; a saved v1 mention has confidence 0.606748, below the dev threshold 0.65. V2 is also unfiltered. The `0.65` config belongs only to the separate dev comparison.","",
 "## Before / after","","| Measure | Fresh v1 | v2 | Change |","|---|---:|---:|---:|"]
 vals=[("Entity rows attached to Events",s['mentionCounts']['v1Rows'],s['mentionCounts']['v2Rows']),("Unique article/span/type mentions",s['mentionCounts']['v1Unique'],s['mentionCounts']['v2Unique']),("URI MATCHED audit rows",v1['mentionStatusCounts'].get('MATCHED',0),v2['mentionStatusCounts'].get('MATCHED',0)),("EAE compatible role pairs",e1['pairCounts'].get('role_compatible',0),e2['pairCounts'].get('role_compatible',0)),("Events with compatible participant",e1['eventsWithPredictedCompatibleParticipant'],e2['eventsWithPredictedCompatibleParticipant']),("Events with >=1 path",v1['eventsWithAtLeastOneSufficientPath'],v2['eventsWithAtLeastOneSufficientPath'])]
 for label,a,b in vals:lines.append(f"| {label} | {a} | {b} | {b-a:+d} |")
 lines += ["","| Path | v1 MATCHED | v2 MATCHED | Change |","|---|---:|---:|---:|"]
 for p in ("DIRECT","INDIRECT_SUBSIDIARY","INDIRECT_LEADERSHIP","INDIRECT_INDUSTRY"):
  a=v1['candidateCountByPath'].get(p,0);b=v2['candidateCountByPath'].get(p,0);lines.append(f"| {p} | {a} | {b} | {b-a:+d} |")
 lines += ["","Across entity mentions: 106 unique spans are identical; 153 appear only in v1; 78 appear only in v2. The v2 additions are 50 out-of-scope BKEE classes (TIME/MONEY/FAC/JOB/VEH), 20 ORG/PER mentions with a KG entity/alias gap, and 8 ORG/PER mentions whose event relevance remains unresolved. No count of truly correct-but-unlinked mentions can be reported without human financial labels; the 20 KG/alias-gap rows are review candidates only.","",
 "## Why URI links and paths disappeared","",
 f"- {s['lostUriMatchRows']} prior MATCHED mention-event rows ({s['lostUriMatchUniqueSpans']} distinct spans) no longer match the same URI: {s['lostUriMatchCauseCounts'].get('MISSED_ENTITY',0)} are missed in v2 and {s['lostUriMatchCauseCounts'].get('WRONG_BOUNDARY',0)} have a changed boundary. None is an exact-span match that the shared resolver newly rejects as an alias mismatch.",
 f"- {s['lostPathRows']} previously matched path rows disappeared; all are DIRECT and become `NO_ENTITY` ({s['lostPathCauseCounts'].get('MISSED_ENTITY',0)} missed company mention, {s['lostPathCauseCounts'].get('WRONG_BOUNDARY',0)} boundary). {s['lostPathEventsWithNoRemainingV2Path']} Events lose all path coverage; one other Event retains its existing LEADERSHIP path. SUBSIDIARY and INDUSTRY had zero matched paths before, and the one LEADERSHIP path remains matched.",
 "- Chain diagnosis: EMD drops ticker/full Company spans or clips long Company names. EAE is unchanged and can still assign roles to other detected mentions; it cannot propose a pair for an entity span that EMD omitted. For clipped spans, the common resolver sees a different surface and returns `MISSING_ALIAS`/no URI. With no Company URI, DIRECT cannot traverse `Company -> hasStock -> Stock`. Existing stocks and path relations/time rules are unchanged; path loss is not caused by missing KG stock relations or changed temporal validation.",
 f"- EAE candidate pairs fell {e1['pairCounts']['candidatePairs']} -> {e2['pairCounts']['candidatePairs']}; compatible proposals {e1['pairCounts']['role_compatible']} -> {e2['pairCounts']['role_compatible']}; Events with a compatible participant {e1['eventsWithPredictedCompatibleParticipant']} -> {e2['eventsWithPredictedCompatibleParticipant']}. V1 had {e1['pairCounts'].get('OVER_MAX_LENGTH',0)} pairs beyond EAE's length limit; v2 had {e2['pairCounts'].get('OVER_MAX_LENGTH',0)} overlength and {e2['pairCounts'].get('INVALID_OR_OVERLAPPING_SPANS',0)} invalid-overlap pair. This is mainly a changed EMD candidate pool/span, not changed EAE weights. A role may still be proposed for a clipped surface while URI resolution fails.","",
 "## Evidence examples","","| Case | Evidence / source | v1 -> v2 | Interpretation |","|---|---|---|---|"]
 wanted=[("MIG","MIG:"),("VPX","Công ty Cổ phần Chứng khoán VPBank"),("CTS","Công ty Cổ phần Chứng khoán VietinBank"),("BID","Ngân hàng Thương mại Cổ phần Đầu tư và Phát triển Việt Nam")]
 for label,needle in wanted:
  hit=next((r for r in loss if needle in r.get('evidenceText','')),None)
  if hit:
   old=hit['v1EntityUri'].rsplit(':',1)[-1]; new=hit['v2Status']
   excerpt=hit['evidenceText'].replace('|','/')[:115]
   cause=hit['lossCause'].lower().replace('_',' ')
   lines.append(f"| {label} | {excerpt} ([source]({hit['sourceUrl']})) | {old} -> {new} | {cause}; direct path blocked at entity URI. |")
 # Explicit noisy-context control example: v1 path based on incidental sidebar mention.
 acb=next((r for r in loss if '1502321.htm' in r.get('sourceUrl','')),None)
 if acb:
  lines.append(f"| ACB sidebar case | `{acb['evidenceText'][:115]}` ([source]({acb['sourceUrl']})) | v1 matched ACB; v2 does not | The mention is in a related-stock/news sidebar and appears unrelated to the predicted Transfer-money event. This is a likely v1 false Event-participant link candidate, so path coverage loss is not automatically a regression. |")
 lines += ["","Spot-check of v2-only ORG/PER spans found at least 10 strongly suspicious boundary/type candidates, including `con` tagged ORG in “Con số này”, `này` tagged ORG, `KDH)`/`PDR)`/`HDC)` tagged PER, `chứng khoán` and `khối tự doanh` tagged PER, `tự doanh` tagged ORG, a role-only phrase `chủ tịch hội đồng quản trị` tagged PER, and a span beginning mid-token at `lậpCông ty...`. These are review flags, not adjudicated gold. Separately, 20 added spans have no EAE role and no established event relevance; 17 are TIME/MONEY/JOB types (potentially valid mentions but out of scope for the four paths) and 3 are ORG. This is a participant false-positive risk count, not a false entity-detection count. The 50 out-of-scope-class mentions may still be legitimate temporal/amount entities while not supporting the four entity-to-stock paths.","",
 "## Cause classification and minimal next steps","",
 "- **Main measured cause:** EMD v2's cohort predictions replace some v1 financial names/tickers with other spans; most path-losing cases are missed entity mentions, with a smaller long-name boundary issue. BKEE dev F1 gains do not establish Vietnamese financial-name recall.",
 "- **Not the main cause:** alias registry, KG relations, path traversal, event evidence filtering, confidence threshold or EAE weights. These are held constant in the fresh comparison. Resolver failures on clipped names are downstream effects of changed spans.",
 "- **Caveat on v1 quality:** the ACB sidebar example suggests at least one v1 path is likely spurious because ED evidence includes page navigation/sidebar text. EMD v2 can lower coverage while removing an incidental mention. Human review is needed to distinguish true losses from removed false participants.",
 "- **Minimal safe next step:** review the 18 distinct URI-lost spans and a stratified sample of 78 v2-only spans against the source article, marking entity span/type separately from Event role and URI. Prioritize MIG/VPX/CTS/BID and other tickers/full bank names, plus noisy sidebar cases. Use those confirmed labels to decide whether to adjust decoder/mention handling or train later.",
 "- Do not change production checkpoint yet. The cohort has no human-verified financial gold; v2 should remain a staging candidate. Do not compensate by increasing matched count or inserting aliases/relations without source validation.","",
 "## Review artifacts","","- `mention_diff.csv`: every article/span/type mention with sentence index and v1/v2 status.","- `lost_uri_matches.csv`: URI links lost, matched URI, exact/boundary/missed diagnosis, source and overlap mentions.","- `lost_event_paths.csv`: each v1-matched path removed, v2 blocker, EAE proposals and source evidence.","- `v2_added_mentions.csv`: v2-only mentions and resolver/relevance review buckets.","- `parity_and_cause_summary.json`: machine-readable control checks and counts.","- Inputs and checkpoint/KG/ontology remain unchanged; all outputs are audit artifacts only.",""]
 (OUT/"diagnosis_report.md").write_text("\n".join(lines),encoding="utf8")
 print(OUT/"diagnosis_report.md")
if __name__=="__main__":main()
