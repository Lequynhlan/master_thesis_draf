from pathlib import Path
import zipfile, xml.etree.ElementTree as E, re, html, json, hashlib, subprocess
import fitz
from PIL import Image, ImageOps, ImageDraw
base=Path(r'D:\project\master_thesis\01-10-2026'); pkg=base/'chỉnh sửa mới nhất - 01-10'; out=base/'review_phase1/presend_current_presentation_assets'
def save(name,s):
 p=out/name
 if p.exists(): raise RuntimeError('Refuse overwrite '+str(p))
 p.write_text(s,encoding='utf-8')
files=[p for p in pkg.rglob('*') if p.is_file()]; before={str(p.relative_to(pkg)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
z=zipfile.ZipFile(next(pkg.glob('*.docx'))); root=E.fromstring(z.read('word/document.xml')); body=root.find('w:body',ns)
rows=[]; paras=[]; images=[]; rels={x.get('Id'):x.get('Target') for x in E.fromstring(z.read('word/_rels/document.xml.rels'))}; pi=ti=0
for child in body:
 if child.tag.endswith('}p'):
  pi+=1; text=''.join(child.itertext()) if False else ''.join(t.text or '' for t in child.findall('.//w:t',ns)); loc=f'P{pi:03}'
  rows.append((loc,text)); paras.append((loc,text))
  for b in child.findall('.//a:blip',ns): images.append((loc,rels[b.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')]))
 elif child.tag.endswith('}tbl'):
  ti+=1
  for ri,row in enumerate(child.findall('w:tr',ns),1):
   for ci,cell in enumerate(row.findall('w:tc',ns),1):
    for k,p in enumerate(cell.findall('.//w:p',ns),1): rows.append((f'T{ti:02}R{ri:02}C{ci:02}P{k}', ''.join(t.text or '' for t in p.findall('.//w:t',ns))))
save('docx_all_text.txt','\n'.join(f'{a}\t{b}' for a,b in rows))
save('docx_image_locations.json',json.dumps(images,ensure_ascii=False,indent=2))
for n in z.namelist():
 if n.startswith('word/media/'):
  p=out/Path(n).name
  if p.exists(): raise RuntimeError('exists')
  p.write_bytes(z.read(n))
pdf=fitz.open(next(pkg.glob('*.pdf'))); pages=[p.get_text() for p in pdf]; save('pdf_all_pages.txt','\n'.join(f'\n=== PDF PHYSICAL PAGE {i+1} ===\n{t}' for i,t in enumerate(pages)))
def norm(s):return re.sub(r'\s+','',s)
full=norm(''.join(pages)); missing=[(a,b) for a,b in rows if b.strip() and norm(b) not in full]; save('docx_pdf_unmatched.json',json.dumps(missing,ensure_ascii=False,indent=2))
d=E.parse(next(pkg.glob('*.drawio'))); labels=[]
for tab in d.findall('diagram'):
 cells=tab.findall('.//mxCell'); mp={c.get('id'):c for c in cells}
 for c in cells:
  v=html.unescape(c.get('value',''));v=re.sub(r'<(?:br\b[^>]*|/(?:div|p|li))>','\n',v);v=html.unescape(re.sub('<[^>]+>','',v))
  labels.append(f"TAB {tab.get('name')} CELL {c.get('id')} EDGE {c.get('source','')} -> {c.get('target','')} STYLE {c.get('style','')}\n{v}")
save('drawio_all_tabs_cells.txt','\n\n'.join(labels))
audit=subprocess.run(['python','-B',str(pkg/'tools/audit_schema_diagram.py'),'--json'],capture_output=True,text=True,encoding='utf-8');save('schema_diagram_audit.json',audit.stdout);save('schema_diagram_audit_stderr.txt',audit.stderr)
# All PDF pages, individually available, overview contact sheet
thumbs=[]
for i,p in enumerate(pdf):
 pix=p.get_pixmap(matrix=fitz.Matrix(1.25,1.25)); path=out/f'pdf_page_{i+1:02}.png';pix.save(path)
 im=Image.open(path);im.thumbnail((240,340)); thumbs.append((f'PDF p{i+1}',im.copy()))
def sheet(name,items,cols,w,h):
 rows=(len(items)+cols-1)//cols; canvas=Image.new('RGB',(cols*w,rows*h),'#ddd'); dr=ImageDraw.Draw(canvas)
 for i,(label,im) in enumerate(items):
  im=im.copy();im.thumbnail((w-12,h-32));x=(i%cols)*w;y=(i//cols)*h; canvas.paste(im,(x+6,y+26));dr.text((x+6,y+5),label,fill='black')
 canvas.save(out/name)
sheet('contact_pdf_all_47.png',thumbs,7,250,370)
ims=[(f'{loc} {Path(t).name}',Image.open(out/Path(t).name).convert('RGB')) for loc,t in images];sheet('contact_docx_embedded.png',ims,3,650,470)
selected=[(f'PDF p{i}',Image.open(out/f'pdf_page_{i:02}.png')) for i in [2,12,13,14,24,25,26,27,28]];sheet('contact_pdf_scoring_eval.png',selected,3,650,900)
after={str(p.relative_to(pkg)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files};assert before==after
save('source_hashes.json',json.dumps(before,ensure_ascii=False,indent=2)); print(json.dumps({'body_paragraphs':pi,'tables':ti,'text_units':len(rows),'images':images,'pdf_pages':len(pdf),'unmatched':len(missing),'audit_exit':audit.returncode},ensure_ascii=False))
