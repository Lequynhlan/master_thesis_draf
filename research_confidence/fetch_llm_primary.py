from pathlib import Path
import requests,fitz,json,concurrent.futures
root=Path(r'D:\project\master_thesis\01-10-2026\research_confidence\sources_llm')
root.mkdir(parents=True,exist_ok=True)
ids=['2303.16634','2306.05685','2207.05221','2306.13063','2305.14975']
def fetch(id):
 out={'id':id,'url':'https://arxiv.org/pdf/'+id}
 try:
  r=requests.get(out['url'],timeout=100);r.raise_for_status()
  if not r.content.startswith(b'%PDF'):raise ValueError('not PDF')
  p=root/(id+'.pdf');p.write_bytes(r.content)
  d=fitz.open(p);text='\n'.join(f'\n--- PAGE {i+1} ---\n'+page.get_text() for i,page in enumerate(d))
  (root/(id+'.txt')).write_text(text,encoding='utf-8')
  out.update(pages=len(d),pdf=str(p),text=str(root/(id+'.txt')),first_page=text[:5500])
 except Exception as e:out['error']=str(e)
 return out
results=list(concurrent.futures.ThreadPoolExecutor(max_workers=5).map(fetch,ids))
(root/'fetch_manifest.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(results,ensure_ascii=False,indent=2))
