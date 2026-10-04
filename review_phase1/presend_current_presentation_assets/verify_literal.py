from pathlib import Path
import json,re,fitz,xml.etree.ElementTree as E,html
from rdflib.plugins.sparql.parser import parseQuery
from rdflib import Graph,RDF,RDFS,OWL,SH,URIRef
b=Path(r'D:\project\master_thesis\01-10-2026');p=b/'chỉnh sửa mới nhất - 01-10';o=b/'review_phase1/presend_current_presentation_assets'
def save(n,s):
 f=o/n;assert not f.exists();f.write_text(s,encoding='utf-8')
rows=[x.split('\t',1) for x in (o/'docx_all_text.txt').read_text(encoding='utf-8').splitlines() if '\t' in x]; paras=[x for x in rows if re.fullmatch('P[0-9]+',x[0])]
pdf=fitz.open(next(p.glob('*.pdf'))); pages=[x.get_text() for x in pdf]
# remove repeated table headers/footer only to test cross-page textual equality
norm=lambda s:re.sub(r'\s+','',s)
clean=[]
for page in pages:
 lines=page.splitlines();lines=[x for x in lines if not ('Bao cao' in x and 'Page' in x)];clean.append('\n'.join(lines))
full=norm(''.join(clean)); mism=[]
for loc,text in rows:
 if text.strip() and norm(text) not in full:mism.append((loc,text))
# find each paragraph as sequence split only by known repeating table header/footer lines
locs={}
for loc,text in rows:
 if not text.strip():continue
 needle=norm(text)
 hits=[i+1 for i,pg in enumerate(pages) if needle in norm(pg)]
 if not hits:
  hits=[f'{i+1}-{i+2}' for i in range(len(pages)-1) if needle in norm(clean[i]+clean[i+1])]
 locs[loc]=hits
save('docx_pdf_page_locators.json',json.dumps(locs,ensure_ascii=False,indent=2));save('remaining_pdf_unmatched.json',json.dumps(mism,ensure_ascii=False,indent=2))
queries=[]
for i,(loc,text) in enumerate(paras):
 m=re.match('Query (\d+) –',text)
 if not m:continue
 end=next((j for j in range(i+1,len(paras)) if paras[j][1].startswith('Bản nguồn ghi nhận') or paras[j][1].startswith('Query đã được sửa')),len(paras))
 qrows=[x for x in paras[i+1:end] if not x[1].startswith(('Mục đích','Graph:'))]
 # all literal paragraphs between first query code and commentary
 start=next(j for j,x in enumerate(qrows) if x[1].startswith('PREFIX'))
 qrows=qrows[start:];q='\n'.join(x[1] for x in qrows)
 try:parseQuery(q);status='PARSE_PASS'
 except Exception as e:status='PARSE_FAIL '+str(e)
 queries.append({'id':m[1],'start':qrows[0][0],'end':qrows[-1][0],'status':status,'query':q})
save('literal_queries.json',json.dumps(queries,ensure_ascii=False,indent=2))
# concise all-property edge checks on tab00 (actual RDF diagram); flow arrows on tabs 01/02 are business direction
G=Graph().parse(p/'ontology_v1.0.ttl');ns='https://example.org/wfkg/v1#';root=E.parse(next(p.glob('*.drawio')));res=[]
def txt(c):return re.sub('<[^>]+>',' ',html.unescape(c.get('value',''))).strip()
for tab in root.findall('diagram'):
 cells=tab.findall('.//mxCell');mp={c.get('id'):c for c in cells};edges=[c for c in cells if c.get('edge')=='1']
 for edge in edges:
  label=[txt(edge)]+[txt(c) for c in cells if c.get('parent')==edge.get('id')]
  terms=[m for l in label for m in re.findall(r'wfkg:(\w+)',l)]
  res.append({'tab':tab.get('name'),'edge':edge.get('id'),'source':txt(mp.get(edge.get('source'),E.Element('x'))),'target':txt(mp.get(edge.get('target'),E.Element('x'))),'labels':label,'rdf_properties':terms})
save('all_connector_inventory.json',json.dumps(res,ensure_ascii=False,indent=2))
# property-table ranges/cardinalities vs direct shapes
T={}
for loc,text in rows:
 m=re.match(r'T(\d+)R(\d+)C(\d+)P1$',loc)
 if m:T.setdefault(int(m[1]),{}).setdefault(int(m[2]),{})[int(m[3])]=text
owners={4:'NewsSource',5:'NewsArticle',6:'Evidence',7:'Event',8:'GovernmentOrganization',9:'CorporateLeader',10:'Company',11:'Bank',12:'CompanyAlias',13:'Stock',14:'Industry',15:'IndustryGroup',16:'FinancialMetric',17:'MarketObservation',18:'MarketIndex',19:'MarketIndexObservation',20:'EventStockCandidate',21:'EventStockReaction',22:'LeadershipPosition',23:'SubsidiaryRelation',24:'IndexMembership',25:'IndustryExposure'}
S=Graph().parse(p/'shapes_v1.0.ttl');tr=[]
for ti,owner in owners.items():
 for ri,cols in T[ti].items():
  if ri==1:continue
  name=cols[1]; prop=URIRef(ns+name);ps=[x for sh in S.subjects(SH.targetClass,URIRef(ns+owner)) for x in S.objects(sh,SH.property) if S.value(x,SH.path)==prop]
  mins=[int(v) for x in ps for v in S.objects(x,SH.minCount)]; maxs=[int(v) for x in ps for v in S.objects(x,SH.maxCount)];actual=f'{max(mins,default=0)}..{min(maxs) if maxs else "*"}'
  printed=cols[3];expected=printed+'..'+printed if '..' not in printed else printed
  ranges=[str(v).split('#')[-1] for v in G.objects(prop,RDFS.range)]
  tr.append({'where':f'T{ti:02}R{ri:02}','owner':owner,'property':name,'printed_type':cols[2],'owl_ranges':ranges,'printed_cardinality':printed,'direct_shacl_cardinality':actual,'comparison':'PASS' if ps and expected==actual else ('NOT_CHECKED' if not ps else 'FAIL')})
save('docx_table_structural_comparison.json',json.dumps(tr,ensure_ascii=False,indent=2))
print('QUERY',[(q['id'],q['status']) for q in queries]);print('TABLE FAIL',[r for r in tr if r['comparison']=='FAIL']);print('TABLE NOT CHECKED',[r for r in tr if r['comparison']=='NOT_CHECKED']);print('unmatched',[(x[0]) for x in mism]);
for loc in ['P020','T20R07C04P1','T20R18C04P1','T20R20C04P1','P122','P123','P124','P127','P130','P306','P309','T30R08C02P1']:print(loc,locs.get(loc))
for pat in ['PhoBERT','LLM','GAT','TFT','TabTransformer','calibration','1.0.4']:
 print('MODEL',pat,[(loc,t[:160]) for loc,t in rows if pat in t])
print('AUDIT',json.loads((o/'schema_diagram_audit.json').read_text(encoding='utf-8'))['counts'])
