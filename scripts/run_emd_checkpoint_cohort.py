"""Controlled EMD-only cohort inference for an explicitly selected checkpoint."""
from __future__ import annotations
import argparse,copy,hashlib,json,sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; RUN=ROOT/"runs/news_event_vertical_slice_20261019"
sys.path.insert(0,str(ROOT/"src"))
from wfkg.event_processing.phobert_detector import PhoBERTEventDetector
from wfkg.event_processing.text_input import prepare_extraction_input
def read_jsonl(p):return [json.loads(x) for x in p.read_text(encoding="utf8").splitlines() if x.strip()]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--checkpoint',type=Path,required=True);ap.add_argument('--output-dir',type=Path,required=True);ap.add_argument('--min-confidence',type=float,default=None);a=ap.parse_args()
 checkpoint=a.checkpoint.resolve();out=a.output_dir.resolve()
 if out.exists() and any(out.iterdir()):raise SystemExit(f"Refusing to overwrite {out}")
 articles=read_jsonl(ROOT/"data/cleaned/news_100_v1/clean_articles.jsonl"); enriched={str(x['articleId']):x for x in read_jsonl(ROOT/"data/enriched_cleaned/news_100_v1/articles.jsonl")}
 prepared={str(x['articleId']):prepare_extraction_input(x,enriched.get(str(x['articleId']))).text for x in articles}
 model=PhoBERTEventDetector(checkpoint,device='cuda'); predictions={};
 for i,(aid,txt) in enumerate(prepared.items(),1):
  rows=model.predict(txt)
  if a.min_confidence is not None:rows=[r for r in rows if float(r['confidence'])>=a.min_confidence]
  predictions[aid]=rows
  if i%10==0:print(f"inference {checkpoint.name}: {i}/{len(prepared)}",flush=True)
 base=json.loads((RUN/"staging_review.json").read_text(encoding='utf8'));staged=copy.deepcopy(base);counts=Counter()
 for ev in staged:
  aid=str(ev['articleId']);evd=ev.get('evidence') or {};s,e=evd.get('startOffset'),evd.get('endOffset'); selected=[]
  for p in predictions.get(aid,[]):
   sp=p.get('triggerSpan',{});x,y=sp.get('startChar'),sp.get('endChar')
   if not isinstance(x,int) or not isinstance(y,int):continue
   if isinstance(s,int) and isinstance(e,int) and not (s<=x<y<=e):continue
   typ=p.get('eventType');mkey=f"{aid}|{x}|{y}|{typ}"
   selected.append({"mentionId":"EMD_COHORT:"+hashlib.sha256(mkey.encode()).hexdigest()[:20],"text":p.get('trigger'),"entityType":typ,"startChar":x,"endChar":y,"confidence":p.get('confidence'),"sourceMethod":"PHOBERT_BKEE_"+checkpoint.name.upper(),"entityMatchStatus":"UNRESOLVED"})
  ev['entities']=selected;ev['arguments']=[];ev['entityLinkSuggestions']=[];ev['emdModel']=checkpoint.name
  counts['eventRows']+=1;counts['eventEvidenceMentions']+=len(selected)
 out.mkdir(parents=True,exist_ok=True);(out/'cohort_emd_predictions.json').write_text(json.dumps(predictions,ensure_ascii=False,indent=2)+'\n',encoding='utf8');(out/'staging_review.json').write_text(json.dumps(staged,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 summary={"articleCount":len(articles),"articlesWithAnyMention":sum(bool(x) for x in predictions.values()),"articleLevelMentionCount":sum(map(len,predictions.values())),"stagedEventCount":len(staged),"eventEvidenceMentionRows":counts['eventEvidenceMentions'],"checkpoint":str(checkpoint.relative_to(ROOT)),"minConfidence":a.min_confidence,"edRerun":False,"eaeRerun":False,"crawlRun":False,"rawKgOntologyShaclAnnotationModified":False}
 (out/'emd_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
