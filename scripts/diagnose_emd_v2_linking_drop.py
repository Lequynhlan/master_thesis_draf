"""Trace cohort EMD v1->v2 mention, URI and KG path losses without mutating inputs."""
from __future__ import annotations
import csv, hashlib, json, sys
from collections import Counter, defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/"runs/news_event_vertical_slice_20261019"
BASE=RUN/"emd_v2_experiment/fair_baseline_v1/eae_trigger_conditioned_v1/staging_review_eae.json"
V2=RUN/"emd_v2_experiment/eae_trigger_conditioned_v2/staging_review_eae.json"
AUD=RUN/"emd_v2_experiment/path_audits_fair"
OUT=RUN/"emd_v2_experiment/diagnosis"
sys.path.insert(0,str(ROOT/"src"))
from wfkg.event_processing.text_input import prepare_extraction_input
from wfkg.event_processing.phobert_detector import _sentence_spans
def read(p): return json.loads(p.read_text(encoding="utf-8"))
def csvout(path, rows, fields=None):
 path.parent.mkdir(parents=True,exist_ok=True)
 if fields is None: fields=list(rows[0]) if rows else []
 with path.open("w",encoding="utf-8-sig",newline="") as f:
  w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)
def key(m): return (str(m.get("articleId","")),m.get("startChar"),m.get("endChar"),str(m.get("text","")),str(m.get("entityType","")))
def sentence_id(text,s,e):
 for i,(a,b) in enumerate(_sentence_spans(text)):
  if a<=s and e<=b:return i
 return None
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 b,v=read(BASE),read(V2)
 byid=lambda evs:{str(e["eventId"]):e for e in evs}
 bm,vm=byid(b),byid(v)
 articles={str(x["articleId"]):x for x in (json.loads(l) for l in (ROOT/"data/cleaned/news_100_v1/clean_articles.jsonl").read_text(encoding="utf8").splitlines() if l.strip())}
 enriched={str(x["articleId"]):x for x in (json.loads(l) for l in (ROOT/"data/enriched_cleaned/news_100_v1/articles.jsonl").read_text(encoding="utf8").splitlines() if l.strip())}
 texts={aid:prepare_extraction_input(a,enriched.get(aid)).text for aid,a in articles.items()}
 # Same frozen Event/ED rows and evidence coordinates must be used on both sides.
 ed_equal=all((e.get("articleId"),e.get("eventType"),e.get("trigger"),e.get("evidence"))==(vm[e["eventId"]].get("articleId"),vm[e["eventId"]].get("eventType"),vm[e["eventId"]].get("trigger"),vm[e["eventId"]].get("evidence")) for e in b)
 base_a=list(csv.DictReader((AUD/"fair_baseline_v1/entity_linking_audit.csv").open(encoding="utf-8-sig")))
 v2_a=list(csv.DictReader((AUD/"emd_v2/entity_linking_audit.csv").open(encoding="utf-8-sig")))
 bp=list(csv.DictReader((AUD/"fair_baseline_v1/event_path_coverage.csv").open(encoding="utf-8-sig")))
 vp=list(csv.DictReader((AUD/"emd_v2/event_path_coverage.csv").open(encoding="utf-8-sig")))
 def mentmap(rows):
  out=defaultdict(list)
  for r in rows:
   if r.get("recordKind")=="ARGUMENT":continue
   out[(r["eventId"],int(r["startChar"] or -1),int(r["endChar"] or -1),r["mentionText"],r["predictedEntityType"])].append(r)
  return out
 bm_a,vm_a=mentmap(base_a),mentmap(v2_a)
 b_unique={key({**m,"articleId":e["articleId"]}):[] for e in b for m in e.get("entities",[])}
 v_unique={key({**m,"articleId":e["articleId"]}):[] for e in v for m in e.get("entities",[])}
 for e in b:
  for m in e.get("entities",[]):b_unique[key({**m,"articleId":e["articleId"]})].append((e,m))
 for e in v:
  for m in e.get("entities",[]):v_unique[key({**m,"articleId":e["articleId"]})].append((e,m))
 diff=[]
 for k in sorted(set(b_unique)|set(v_unique),key=str):
  aid,s,en,text,typ=k; bs=b_unique.get(k,[]);vs=v_unique.get(k,[])
  e=(bs or vs)[0][0]; tx=texts.get(aid,"")
  diff.append({"articleId":aid,"eventIdsV1":"|".join(sorted({x[0]["eventId"] for x in bs})),"eventIdsV2":"|".join(sorted({x[0]["eventId"] for x in vs})),"sentenceId":sentence_id(tx,s,en) if isinstance(s,int) and isinstance(en,int) else None,"startChar":s,"endChar":en,"text":text,"entityType":typ,"v1Present":bool(bs),"v2Present":bool(vs),"change":"UNCHANGED" if bs and vs else ("V1_ONLY" if bs else "V2_ONLY"),"sourceUrl":articles.get(aid,{}).get("url"),"evidenceText":e.get("evidence",{}).get("evidenceText")})
 csvout(OUT/"mention_diff.csv",diff)
 # Match old/new mentions within event: exact type+span, same-type overlap, exact boundary wrong type.
 lost_links=[]; lostpaths=[]; added=[]; cause_counts=Counter()
 for old in base_a:
  if old.get("recordKind")=="ARGUMENT" or old.get("entityLinkStatus")!="MATCHED":continue
  ev=old["eventId"]; s=int(old["startChar"] or -1); en=int(old["endChar"] or -1); typ=old["predictedEntityType"]
  exact=[r for r in v2_a if r.get("eventId")==ev and int(r.get("startChar") or -1)==s and int(r.get("endChar") or -1)==en and r.get("predictedEntityType")==typ]
  if exact and any(r.get("entityLinkStatus")=="MATCHED" and r.get("matchedUris")==old.get("matchedUris") for r in exact):continue
  all_new=[r for r in v2_a if r.get("eventId")==ev and r.get("recordKind")!="ARGUMENT"]
  same_type=[r for r in all_new if r.get("predictedEntityType")==typ and max(s,int(r.get("startChar") or -1))<min(en,int(r.get("endChar") or -1))]
  same_span=[r for r in all_new if int(r.get("startChar") or -1)==s and int(r.get("endChar") or -1)==en and r.get("predictedEntityType")!=typ]
  if not exact: cause="MISSED_ENTITY" if not same_type and not same_span else ("WRONG_BOUNDARY" if same_type else "WRONG_TYPE")
  else:
   nr=exact[0]
   if nr.get("entityLinkStatus")=="MISSING_ALIAS":cause="RESOLVER_ALIAS_MISMATCH"
   elif nr.get("entityLinkStatus")=="MATCHED":cause="URI_CANDIDATE_CHANGED"
   else:cause="ENTITY_LINK_CONTEXT_OR_SCOPE"
  cause_counts[cause]+=1
  lost_links.append({**old,"lossCause":cause,"v2ExactLinkStatus":"|".join(r.get("entityLinkStatus","") for r in exact),"v2ExactMatchedUris":"|".join(r.get("matchedUris","") for r in exact),"v2OverlapMentions":" | ".join(f"{r.get('mentionText')}[{r.get('predictedEntityType')},{r.get('startChar')}:{r.get('endChar')},{r.get('entityLinkStatus')}]" for r in (same_type or same_span))})
 # path losses, with per-event stage counts and path-specific blocking reason
 b_status=defaultdict(dict);v_status=defaultdict(dict)
 for r in bp:b_status[r["eventId"]][r["path"]]=r
 for r in vp:v_status[r["eventId"]][r["path"]]=r
 for eid,paths in b_status.items():
  if not any(x.get("pathStatus")=="MATCHED" for x in paths.values()):continue
  now=v_status.get(eid,{})
  oldev= bm[eid]; newev=vm[eid]
  oldms=[m for m in base_a if m.get("eventId")==eid and m.get("recordKind")!="ARGUMENT"]
  newms=[m for m in v2_a if m.get("eventId")==eid and m.get("recordKind")!="ARGUMENT"]
  oldargs=oldev.get("arguments",[]);newargs=newev.get("arguments",[])
  for path,oldpath in paths.items():
   if oldpath.get("pathStatus")!="MATCHED":continue
   newpath=now.get(path,{})
   if newpath.get("pathStatus")=="MATCHED":continue
   candidate_uris={u for m in oldms if m.get("entityLinkStatus")=="MATCHED" for u in m.get("matchedUris","").split("|")}
   lost_link=(not any(m.get("entityLinkStatus")=="MATCHED" and set(m.get("matchedUris","").split("|"))&candidate_uris for m in newms)) if candidate_uris else True
   oldarg={(a.get("startChar"),a.get("endChar"),a.get("role")) for a in oldargs if a.get("roleCompatibilityAccepted")}
   newarg={(a.get("startChar"),a.get("endChar"),a.get("role")) for a in newargs if a.get("roleCompatibilityAccepted")}
   role_lost=bool(oldarg-newarg)
   cause="EMD_OR_ENTITY_RESOLUTION" if lost_link else ("EAE_ROLE_LINK_LOST" if role_lost else "KG_PATH_EVIDENCE_OR_TEMPORAL_BLOCKER")
   path_lost_matches=[x for x in lost_links if x.get("eventId")==eid and oldpath.get("entityUri") in x.get("matchedUris","").split("|")]
   detailed_cause=path_lost_matches[0].get("lossCause") if path_lost_matches else cause
   event_has_another_path=any(p2!=path and now.get(p2,{}).get("pathStatus")=="MATCHED" for p2 in paths)
   lostpaths.append({"articleId":oldev["articleId"],"eventId":eid,"sourceUrl":articles.get(str(oldev["articleId"]),{}).get("url"),"eventType":oldev.get("eventType"),"trigger":oldev.get("trigger",{}).get("text"),"evidenceText":oldev.get("evidence",{}).get("evidenceText"),"path":path,"v1Status":oldpath.get("pathStatus"),"v1EntityUri":oldpath.get("entityUri"),"v1CandidateStocks":oldpath.get("candidateStockUris"),"v2Status":newpath.get("pathStatus"),"v2EntityUri":newpath.get("entityUri"),"v2MissingRelationships":newpath.get("missingRelationships"),"v2Reason":newpath.get("reason"),"eventHasAnotherPathV2":event_has_another_path,"lossCause":detailed_cause,"v1Entities":" | ".join(f"{m.get('mentionText')}:{m.get('entityLinkStatus')}:{m.get('matchedUris')}" for m in oldms),"v2Entities":" | ".join(f"{m.get('mentionText')}:{m.get('entityLinkStatus')}:{m.get('matchedUris')}" for m in newms),"v1Roles":" | ".join(f"{a.get('text')}:{a.get('role')}:{a.get('roleCompatibilityAccepted')}" for a in oldargs),"v2Roles":" | ".join(f"{a.get('text')}:{a.get('role')}:{a.get('roleCompatibilityAccepted')}" for a in newargs)})
 csvout(OUT/"lost_uri_matches.csv",lost_links)
 csvout(OUT/"lost_event_paths.csv",lostpaths)
 # Added v2 mentions, after the exact same resolver, categorized without assuming correctness.
 diff_idx={(r["articleId"],r["startChar"],r["endChar"],r["text"],r["entityType"]):r for r in diff}
 added_unique={}
 for m in v2_a:
  if m.get("recordKind")=="ARGUMENT":continue
  k=(m["articleId"],int(m["startChar"] or -1),int(m["endChar"] or -1),m["mentionText"],m["predictedEntityType"])
  if diff_idx.get(k,{}).get("change")!="V2_ONLY":continue
  status=m.get("entityLinkStatus")
  bucket="IN_KG_URI_MATCHED_REVIEW" if status=="MATCHED" else ("OUT_OF_SCOPE_FOR_FOUR_PATHS" if status=="OUT_OF_SCOPE" else ("KG_ENTITY_OR_ALIAS_GAP" if status in {"MISSING_KG_ENTITY","MISSING_ALIAS"} else "UNRESOLVED_RELEVANCE_OR_AMBIGUITY"))
  kk=(m["articleId"],int(m["startChar"] or -1),int(m["endChar"] or -1),m["mentionText"],m["predictedEntityType"])
  if kk not in added_unique:added_unique[kk]={**m,"addedMentionAssessment":bucket,"verifiedFalsePositive":"NO_GOLD_LABEL","affectedEventIds":set()}
  added_unique[kk]["affectedEventIds"].add(m["eventId"])
 added=[{**row,"affectedEventIds":"|".join(sorted(row["affectedEventIds"]))} for row in added_unique.values()]
 csvout(OUT/"v2_added_mentions.csv",added)
 # config/data parity summary
 article_hashes={aid:hashlib.sha256(txt.encode("utf-8")).hexdigest() for aid,txt in texts.items()}
 ev1=read(RUN/"emd_v2_experiment/fair_baseline_v1/eae_trigger_conditioned_v1/summary.json")
 ev2=read(RUN/"emd_v2_experiment/eae_trigger_conditioned_v2/summary.json")
 path_uris=defaultdict(set)
 for row in bp:
  if row.get("pathStatus")=="MATCHED" and row.get("entityUri"):path_uris[(row["eventId"],row["entityUri"])].add(row["path"])
 lost_uri_path_counts=Counter()
 for row in lost_links:
  for uri in row.get("matchedUris","").split("|"):
   for path in path_uris.get((row["eventId"],uri),set()):lost_uri_path_counts[path]+=1
 add_bucket_counts=Counter(x["addedMentionAssessment"] for x in added)
 add_type_counts=Counter(x.get("predictedEntityType","") for x in added)
 possible_fp=sum(not x.get("argumentRoles") and x.get("eventRelevance")=="NOT_ESTABLISHED" for x in added)
 v1_gate=Counter(r.get("mentionOccursInEvidence") for r in base_a if r.get("recordKind")!="ARGUMENT")
 v2_gate=Counter(r.get("mentionOccursInEvidence") for r in v2_a if r.get("recordKind")!="ARGUMENT")
 # Existing v1 snapshot should exactly match a fresh unfiltered v1 pass on the same cohort.
 prior_v1=read(RUN/"eae_trigger_conditioned_v1/staging_review_eae.json")
 prior_set={(e["articleId"],m.get("startChar"),m.get("endChar"),m.get("text"),m.get("entityType")) for e in prior_v1 for m in e.get("entities",[])}
 rerun_set=set(b_unique)
 v1_reproduction={"historicalUniqueMentions":len(prior_set),"freshV1UniqueMentions":len(rerun_set),"exactOverlap":len(prior_set&rerun_set),"historicalOnly":len(prior_set-rerun_set),"freshOnly":len(rerun_set-prior_set)}
 cp1=json.loads((ROOT/"models/phobert_bkee_emd_v1/label_mapping.json").read_text(encoding="utf8"));cp2=json.loads((ROOT/"models/phobert_bkee_emd_v2/label_mapping.json").read_text(encoding="utf8"))
 def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest().upper()
 tokenizer_parity={f:sha(ROOT/f"models/phobert_bkee_emd_v1/{f}")==sha(ROOT/f"models/phobert_bkee_emd_v2/{f}") for f in ("vocab.txt","bpe.codes","added_tokens.json")}
 lost_unique=len({(x["articleId"],x["startChar"],x["endChar"],x["mentionText"],x["predictedEntityType"]) for x in lost_links})
 summary={"articleCount":len(texts),"preparedTextSha256SetSize":len(set(article_hashes.values())),"allPreparedTextsNonempty":all(texts.values()),"frozenEventAndEvidenceEqual":ed_equal,"v1EventCount":len(b),"v2EventCount":len(v),"edSourceMethodEqual":all(e.get("sourceMethod")==vm[e["eventId"]].get("sourceMethod") for e in b),"eaeCheckpointEqual":ev1["checkpoint"]==ev2["checkpoint"],"eaeCheckpoint":ev1["checkpoint"],"eaeRoleCompatibleParticipants":{"v1":ev1["eventsWithPredictedCompatibleParticipant"],"v2":ev2["eventsWithPredictedCompatibleParticipant"]},"mentionCounts":{"v1Unique":len(b_unique),"v2Unique":len(v_unique),"commonUnique":len(set(b_unique)&set(v_unique)),"v1Rows":sum(map(len,b_unique.values())),"v2Rows":sum(map(len,v_unique.values())),"v1OnlyUnique":sum(bool(b_unique.get(k)) and not v_unique.get(k) for k in set(b_unique)|set(v_unique)),"v2OnlyUnique":sum(bool(v_unique.get(k)) and not b_unique.get(k) for k in set(b_unique)|set(v_unique))},"historicalV1ExactReproduction":v1_reproduction,"checkpointAndInferenceParity":{"sameBaseModelRevision":cp1.get("modelRevision")==cp2.get("modelRevision"),"sameEntityTypes":cp1.get("entityTypes")==cp2.get("entityTypes"),"v1MaxLength":cp1.get("max_length"),"v2MaxLength":cp2.get("max_length"),"v1Stride":cp1.get("inference_stride"),"v2Stride":cp2.get("inference_stride"),"sameTokenizerFiles":tokenizer_parity,"v1Threshold":None,"v2Threshold":None,"onlyIntendedParameterDifference":"fine-tuned token-classifier weights (plus training metadata in label_mapping.json); both unfiltered argmax decode"},"evidenceContainmentGate":{"v1":dict(v1_gate),"v2":dict(v2_gate),"bothUseSameAuditPredicate":all(r.get("mentionOccursInEvidence")=="True" for r in base_a+v2_a if r.get("recordKind")!="ARGUMENT")},"lostUriMatchCauseCounts":dict(cause_counts),"lostUriMatchRows":len(lost_links),"lostUriMatchUniqueSpans":lost_unique,"lostUriMatchedPathAssociations":dict(lost_uri_path_counts),"v1PathMatchedEvents":len({r["eventId"] for r in bp if r["pathStatus"]=="MATCHED"}),"v2PathMatchedEvents":len({r["eventId"] for r in vp if r["pathStatus"]=="MATCHED"}),"lostPathRows":len(lostpaths),"lostPathDistinctEvents":len({x["eventId"] for x in lostpaths}),"lostPathEventsWithNoRemainingV2Path":len({x["eventId"] for x in lostpaths if not x["eventHasAnotherPathV2"]}),"lostPathStatusCountsByPath":{p:dict(Counter(x["v2Status"] for x in lostpaths if x["path"]==p)) for p in ("DIRECT","INDIRECT_SUBSIDIARY","INDIRECT_LEADERSHIP","INDIRECT_INDUSTRY")},"lostPathCauseCounts":dict(Counter(x["lossCause"] for x in lostpaths)),"v2AddedMentionUniqueCount":len(added),"v2AddedMentionBuckets":dict(add_bucket_counts),"v2AddedMentionTypeCounts":dict(add_type_counts),"v2AddedNoRoleNoEventRelevanceReviewCount":possible_fp,"v2AddedCorrectButUnlinkedCount":"unknown: no financial-domain human gold labels; KG/alias-gap is only a review candidate", "resolverAndPathCode":"scripts/audit_vertical_slice_entity_paths.py (same code + same KG file schema/ontology 1.0.5)","evidenceFiltering":"All mention rows in both path audits pass mentionOccursInEvidence=True and spanVerified=True; same audit predicate is applied. Cohort generation for both requires full-span containment in the exact same Event evidence offsets.","threshold":"v1 unfiltered cohort inference is reproduced exactly; example confidence 0.606748 is below 0.65. v2 is also unfiltered. No threshold applied.","preprocessing":"same prepare_extraction_input, same 100 source articles, same current PhoBERT detector/VnCoreNLP segmented-text offset decoder; fresh v1 predictions exactly reproduce all 259 unique mentions in the prior baseline. Frozen ED/Event/evidence is identical.","rawKgOntologyShaclCheckpointModified":False}
 tc1=json.loads((ROOT/"models/phobert_bkee_emd_v1/tokenizer_config.json").read_text(encoding="utf8"));tc2=json.loads((ROOT/"models/phobert_bkee_emd_v2/tokenizer_config.json").read_text(encoding="utf8"))
 summary["checkpointAndInferenceParity"]["tokenizerConfigIsLocal"]={"v1":tc1.get("is_local"),"v2":tc2.get("is_local"),"note":"serialization metadata only; vocab/bpe/added-token files match"}
 (OUT/"parity_and_cause_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
