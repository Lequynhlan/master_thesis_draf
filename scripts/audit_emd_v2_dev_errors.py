"""Error taxonomy/examples for the three EMD configurations on BKEE dev only."""
from __future__ import annotations
import json, sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from wfkg.event_processing.phobert_detector import PhoBERTEventDetector
RUN=ROOT/"runs/news_event_vertical_slice_20261019/emd_v2_experiment"
DEV=ROOT/"data/external/BKEE_official_20261019/processed/dev.json"
def main():
 rows=[json.loads(x) for x in DEV.read_text(encoding="utf-8").splitlines() if x.strip()]
 results={}
 segmenter=None
 for name,checkpoint,threshold in [("v1_unfiltered",ROOT/"models/phobert_bkee_emd_v1",None),("v1_threshold_065",ROOT/"models/phobert_bkee_emd_v1",0.65),("v2",ROOT/"models/phobert_bkee_emd_v2",None)]:
  model=PhoBERTEventDetector(checkpoint,device="cuda")
  if segmenter is not None: model._segmenter=segmenter
  counts=Counter(); examples=[]; gold_n=pred_n=tp=0
  for i,row in enumerate(rows,1):
   sentence=str(row["sentence"]); sid=str(row.get("sent_id",i))
   gold={(int(e["start_char"]),int(e["end_char"]),str(e["entity_type"])) for e in row.get("entity_mentions",[])}
   predrows=model.predict(sentence)
   if segmenter is None: segmenter=model._segmenter
   if threshold is not None: predrows=[p for p in predrows if float(p["confidence"])>=threshold]
   pred={(int(p["triggerSpan"]["startChar"]),int(p["triggerSpan"]["endChar"]),str(p["eventType"])):float(p["confidence"]) for p in predrows}
   gs=set(gold); ps=set(pred); exact=gs&ps; tp+=len(exact); gold_n+=len(gs); pred_n+=len(ps)
   fns=gs-ps; fps=ps-gs; counts["exactTP"]+=len(exact); counts["FN"]+=len(fns); counts["FP"]+=len(fps)
   for a in fns:
    b,e,t=a
    same_type=[q for q in fps if q[2]==t and max(b,q[0])<min(e,q[1])]
    same_span_wrong_type=[q for q in ps if q[0]==b and q[1]==e and q[2]!=t]
    kind="boundaryMiss" if same_type else ("typeMiss" if same_span_wrong_type else "missedEntity")
    counts[kind]+=1
    if len(examples)<80: examples.append({"kind":kind,"sentId":sid,"text":sentence,"goldSpan":[b,e],"goldType":t,"goldText":sentence[b:e],"relatedPrediction":[{"span":[q[0],q[1]],"type":q[2],"text":sentence[q[0]:q[1]],"confidence":pred.get(q)} for q in (same_type or same_span_wrong_type)]})
   for a in fps:
    b,e,t=a
    same_type=[q for q in gs if q[2]==t and max(b,q[0])<min(e,q[1])]
    same_span_wrong_type=[q for q in gs if q[0]==b and q[1]==e and q[2]!=t]
    kind="boundaryFP" if same_type else ("typeFP" if same_span_wrong_type else "falsePositive")
    counts[kind]+=1
    if len(examples)<120: examples.append({"kind":kind,"sentId":sid,"text":sentence,"predictedSpan":[b,e],"predictedType":t,"predictedText":sentence[b:e],"confidence":pred[a],"relatedGold":[{"span":[q[0],q[1]],"type":q[2],"text":sentence[q[0]:q[1]]} for q in (same_type or same_span_wrong_type)]})
   if i%1000==0: print(name,i,"/",len(rows),flush=True)
  p=tp/pred_n if pred_n else 0; r=tp/gold_n if gold_n else 0
  results[name]={"precision":p,"recall":r,"f1":2*p*r/(p+r) if p+r else 0,"gold":gold_n,"predicted":pred_n,"counts":dict(counts),"examples":examples}
  del model
  print(name,json.dumps({k:v for k,v in results[name].items() if k!="examples"}),flush=True)
 (RUN/"dev_error_analysis.json").write_text(json.dumps(results,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
if __name__=="__main__":main()
