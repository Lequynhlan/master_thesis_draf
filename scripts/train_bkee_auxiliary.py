"""Train BKEE entity mention and argument-role BIO heads without touching ED v2."""
from __future__ import annotations
import argparse, json, random, sys, math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from train_bkee_event_detection import IndexedJsonl, batch_examples, make_class_weights, token_classification_loss, spans_from_labels, save_checkpoint, VNCORP_ASSETS, MODEL_ID, MODEL_REVISION, DATASET_DIR, MAX_LENGTH

def labels_for(row, task):
    tags=['O']*len(row['tokens'])
    if task=='emd':
        spans=[(e['start'],e['end'],e['entity_type']) for e in row.get('entity_mentions',[])]
    else:
        spans=[]
        entities={e['id']:e for e in row.get('entity_mentions',[])}
        for event in row.get('event_mentions',[]):
            for arg in event.get('arguments',[]):
                ent=entities.get(arg.get('entity_id'))
                if ent: spans.append((ent['start'],ent['end'],arg['role']))
    for s,e,t in spans:
        if any(tags[i]!='O' for i in range(s,e)): continue
        tags[s]='B-'+t
        for i in range(s+1,e): tags[i]='I-'+t
    return tags

def encode(row, tok, l2i, task):
    words=[tok.tokenize(str(w).replace(' ','_')) for w in row['tokens']]
    pieces=[p for w in words for p in w]
    labs=[]
    for word, tag in zip(words,labels_for(row,task)):
        labs += [l2i[tag]] + [l2i['I-'+tag[2:]]]*(len(word)-1) if tag.startswith('B-') else ([l2i[tag]]*len(word))
    ids=[tok.cls_token_id]+tok.convert_tokens_to_ids(pieces)+[tok.sep_token_id]
    labs=[-100]+labs+[-100]
    if len(ids)>MAX_LENGTH: return None
    return {'input_ids':ids,'labels':labs,'piece_count':len(pieces)}

def run(task, epochs, limit):
    import torch
    from transformers import AutoTokenizer,AutoModelForTokenClassification
    d=Path('data/external/BKEE_official_20261019/processed'); tr=IndexedJsonl(d/'train.json'); dv=IndexedJsonl(d/'dev.json')
    tok=AutoTokenizer.from_pretrained(MODEL_ID,use_fast=False,revision=MODEL_REVISION)
    field='entity_type' if task=='emd' else 'role'
    labels_seen=set()
    n=min(len(tr),limit) if limit else len(tr)
    with tr.path.open('rb') as f:
        for i in range(n):
            r=tr.get(i,f)
            if task=='emd': labels_seen.update(e[field] for e in r['entity_mentions'])
            else:
                labels_seen.update(a[field] for e in r['event_mentions'] for a in e['arguments'])
    ts=['O']+[x for t in sorted(labels_seen) for x in ('B-'+t,'I-'+t)]; l2i={x:i for i,x in enumerate(ts)}; i2l={i:x for x,i in l2i.items()}
    ck=ROOT/'models'/f'phobert_bkee_{task}_v1'; rd=ROOT/'runs'/f'phobert_bkee_{task}_v1'
    if ck.exists() and any(ck.iterdir()): raise SystemExit(f'refusing overwrite {ck}')
    if rd.exists() and any(rd.iterdir()): raise SystemExit(f'refusing overwrite {rd}')
    ck.mkdir(parents=True,exist_ok=True); rd.mkdir(parents=True,exist_ok=True)
    dev=torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    if dev.type!='cuda': raise RuntimeError('CUDA required')
    counts=[0]*len(ts); unknown=0
    with tr.path.open('rb') as f:
        for i in range(n):
            x=encode(tr.get(i,f),tok,l2i,task)
            if x:
                for y in x['labels']:
                    if y>=0: counts[y]+=1
    weights,_=make_class_weights(counts,torch,dev)
    model=AutoModelForTokenClassification.from_pretrained(MODEL_ID,num_labels=len(ts),id2label=i2l,label2id=l2i,ignore_mismatched_sizes=True,revision=MODEL_REVISION).to(dev)
    model.gradient_checkpointing_enable(); model.config.use_cache=False
    opt=torch.optim.AdamW(model.parameters(),lr=2e-5,weight_decay=.01); scaler=torch.amp.GradScaler('cuda',enabled=True)
    losses=[]
    for ep in range(epochs):
        model.train(); order=list(range(n)); random.Random(42+ep).shuffle(order); opt.zero_grad(set_to_none=True); total=[]
        with tr.path.open('rb') as f:
            for j,ix in enumerate(order):
                ex=encode(tr.get(ix,f),tok,l2i,task)
                if not ex: continue
                b=batch_examples([ex],tok.pad_token_id,dev,torch)
                with torch.autocast(device_type='cuda',dtype=torch.float16): out=model(input_ids=b['input_ids'],attention_mask=b['attention_mask']); loss=token_classification_loss(out.logits,b['labels'],weights,torch)/8
                scaler.scale(loss).backward(); total.append(loss.item()*8)
                if (j+1)%8==0 or j+1==n:
                    scaler.unscale_(opt); torch.nn.utils.clip_grad_norm_(model.parameters(),1); scaler.step(opt); scaler.update(); opt.zero_grad(set_to_none=True)
                if j%500==0: print(f'{task} epoch={ep+1} row={j}/{n}',flush=True)
        losses.append(sum(total)/max(1,len(total))); print(f'{task} epoch {ep+1} loss={losses[-1]:.5f}',flush=True)
    metadata={'task':f'BKEE_{task.upper()}_BIO_TOKEN_CLASSIFICATION','modelId':MODEL_ID,'modelRevision':MODEL_REVISION,'entityTypes':sorted(labels_seen) if task=='emd' else None,'roles':sorted(labels_seen) if task=='eae' else None,'label2id':l2i,'id2label':{str(k):v for k,v in i2l.items()},'max_length':MAX_LENGTH,'inference_stride':48,'trainingSplit':'train','selectionSplit':'dev','testSplitUsed':False,'vncorenlp_assets':'vncorenlp_assets','losses':losses,'trainRows':n}
    save_checkpoint(model,tok,ck,metadata); (rd/'training_report.json').write_text(json.dumps(metadata,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    print('saved',ck,flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('task',choices=['emd','eae']); ap.add_argument('--epochs',type=int,default=1); ap.add_argument('--limit',type=int,default=0); a=ap.parse_args(); run(a.task,a.epochs,a.limit)
