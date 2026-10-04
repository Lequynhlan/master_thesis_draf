from pathlib import Path
import requests, fitz, hashlib, json
from concurrent.futures import ThreadPoolExecutor
root=Path(__file__).parent/'sources_extraction'; root.mkdir(exist_ok=True)
sources={
 'phobert':'https://aclanthology.org/2020.findings-emnlp.92.pdf',
 'dygiepp':'https://aclanthology.org/D19-1585.pdf',
 'doc_eae':'https://arxiv.org/pdf/2104.05919',
 'uie':'https://aclanthology.org/2022.acl-long.395.pdf',
 'gollie':'https://arxiv.org/pdf/2310.03668',
 'grammar':'https://arxiv.org/pdf/2305.13971'}
def fetch(item):
 name,url=item
 try:
  r=requests.get(url,timeout=90); r.raise_for_status(); data=r.content
  if not data.startswith(b'%PDF'): raise ValueError('not PDF')
  (root/(name+'.pdf')).write_bytes(data)
  doc=fitz.open(stream=data,filetype='pdf'); text='\n'.join(f'\n=== PDF PAGE {i+1} ===\n'+p.get_text() for i,p in enumerate(doc))
  (root/(name+'.txt')).write_text(text,encoding='utf-8')
  return {'id':name,'url':url,'sha256':hashlib.sha256(data).hexdigest(),'pages':len(doc),'preview':text[:1600]}
 except Exception as e: return {'id':name,'url':url,'error':str(e)}
results=list(ThreadPoolExecutor(max_workers=6).map(fetch,sources.items()))
(root/'fetch_manifest.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(results,ensure_ascii=False,indent=2))
