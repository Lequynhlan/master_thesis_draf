import requests, fitz, pathlib, concurrent.futures
BASE=pathlib.Path(__file__).parent/'confidence_sources'; BASE.mkdir(exist_ok=True)
urls={
'amie':'https://suchanek.name/work/publications/www2013.pdf',
'problog':'https://www.ijcai.org/Proceedings/07/Papers/396.pdf',
'psl':'https://arxiv.org/pdf/1505.04406',
'lkif':'https://ceur-ws.org/Vol-321/paper3.pdf',
'legal_nlp':'https://ceur-ws.org/Vol-321/paper7.pdf',
'disponte':'https://www.ijcai.org/papers15/Papers/IJCAI15-613.pdf',
}
def fetch(pair):
 name,url=pair
 try:
  r=requests.get(url,timeout=60);r.raise_for_status()
  if not r.content.startswith(b'%PDF'):return name,r.status_code,r.text[:200]
  (BASE/(name+'.pdf')).write_bytes(r.content)
  doc=fitz.open(stream=r.content,filetype='pdf');text='\n'.join(f'\n--- PAGE {i+1} ---\n'+p.get_text() for i,p in enumerate(doc))
  (BASE/(name+'.txt')).write_text(text,encoding='utf-8')
  return name,len(doc),text[:2200]
 except Exception as e:return name,str(e)
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
 for result in pool.map(fetch,urls.items()):print(result)
for q in ['DISPONTE A novel approach for probabilistic description logics','LKIF Core ontology basic legal concepts','Pronto probabilistic description logic reasoner']:
 try:
  j=requests.get('https://api.crossref.org/works',params={'query.title':q,'rows':3},timeout=30).json()
  print('SEARCH',q,[(x.get('title'),x.get('DOI'),x.get('link')) for x in j['message']['items']])
 except Exception as e: print(e)
