from pathlib import Path
import json,re,fitz,hashlib
from rdflib import Graph,Namespace,RDF,Literal,XSD,SH
b=Path(r'D:\project\master_thesis\01-10-2026');p=b/'chỉnh sửa mới nhất - 01-10';o=b/'review_phase1/presend_current_presentation_assets'
def save(n,v):
 q=o/n;assert not q.exists();q.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
rows=[x.split('\t',1) for x in (o/'docx_all_text.txt').read_text(encoding='utf-8').splitlines() if '\t' in x]; norm=lambda s:re.sub(r'\s+','',s)
d=fitz.open(next(p.glob('*.pdf')));clean=[re.sub(r'Bản chỉnh sửa theo góp ý[^\n]*Page\s*\d+\s*of\s*47','',pg.get_text()) for pg in d];full=norm(''.join(clean));missing=[loc for loc,t in rows if t.strip() and norm(t) not in full];save('final_docx_pdf_text_comparison.json',{'method':'whitespace normalization and exact known repeated footer removal; not layout equivalence','missing':missing,'units':len(rows),'nonempty':sum(bool(t.strip()) for _,t in rows)})
tr=json.loads((o/'docx_table_structural_comparison.json').read_text(encoding='utf-8'));s=Graph().parse(p/'shapes_v1.0.ttl');w=Namespace('https://example.org/wfkg/v1#');coverage=[]
for owner in sorted(set(x['owner'] for x in tr)):
 printed={w[x['property']] for x in tr if x['owner']==owner}
 for sh in s.subjects(SH.targetClass,w[owner]):
  for ps in s.objects(sh,SH.property):
   path=s.value(ps,SH.path)
   if str(path).startswith(str(w)) and path not in printed:coverage.append({'owner':owner,'missing':str(path).split('#')[-1],'min':str(s.value(ps,SH.minCount)),'max':str(s.value(ps,SH.maxCount))})
save('docx_missing_direct_shape_properties.json',coverage)
qs={x['id']:x['query'] for x in json.loads((o/'literal_queries.json').read_text(encoding='utf-8'))};g=Graph();g.add((w.e,RDF.type,w.Event));g.add((w.e,w.eventId,Literal('DIAGNOSTIC_ONLY')));g.add((w.e,w.effectiveTradingDate,Literal('2026-08-27',datatype=XSD.date)));g.add((w.c,RDF.type,w.EventStockCandidate));g.add((w.c,w.forEvent,w.e));g.add((w.c,w.candidateStock,w.stock));g.add((w.c,w.candidateStatus,Literal('PENDING_MARKET_WINDOW')));g.add((w.e,w.hasEventStockCandidate,w.c));g.add((w.a,w.reports,w.e));g.add((w.unrelated_index,w.hasIndexObservation,w.unrelated_observation));g.add((w.unrelated_observation,w.tradingDate,Literal('2026-08-27',datatype=XSD.date)))
def result(n):
 r=g.query(qs[n]);return {'columns':[str(x) for x in r.vars],'rows':[[str(v) if v is not None else None for v in row] for row in r]}
q5=result('5');g.add((w.no_candidate_event,w.eventId,Literal('ZERO_CANDIDATE_DIAGNOSTIC')));g.add((w.a2,w.reports,w.no_candidate_event));q9=result('9');save('isolated_query_diagnostics.json',{'synthetic_diagnostic_not_original_fixture':True,'q5_unrelated_benchmark_count':q5,'q9_zero_candidate_event_omitted':q9})
# exact package hash verification after all probes
orig=json.loads((o/'source_hashes.json').read_text(encoding='utf-8'));changed=[name for name,h in orig.items() if hashlib.sha256((p/name).read_bytes()).hexdigest()!=h];save('final_source_preservation.json',{'changed':changed,'unchanged':not changed})
print('PDF missing',missing);print('missing table props',coverage);print('diagnostic',q5,q9);print('sources changed',changed);print('table rows',len(tr))
