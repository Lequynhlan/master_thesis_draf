"""Run ED/EMD/EAE on the fixed 100 news articles and create SHACL-gated RDF."""
from __future__ import annotations
import hashlib, json, re, sys, subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from rdflib import Graph
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src'))
from wfkg.config import load_config
from wfkg.event_processing import extractor_from_project_config
from wfkg.event_processing.kg_entity_resolution import build_index, resolve_mention

OUT=ROOT/'runs/news_event_vertical_slice_20261019'
RAW=ROOT/'data/cleaned/news_100_v1/clean_articles.jsonl'; ENR=ROOT/'data/enriched_cleaned/news_100_v1/articles.jsonl'; MAN=ROOT/'data/output/news_article_selection_manifest.json'
def readj(path): return [json.loads(x) for x in path.read_text(encoding='utf8').splitlines() if x.strip()]
def norm(s): return re.sub(r'[^\w]+',' ',s.casefold(),flags=re.UNICODE).strip()

def main():
    if OUT.exists() and any(OUT.iterdir()): raise SystemExit(f'refusing overwrite {OUT}')
    cohort=json.loads(MAN.read_text(encoding='utf8')); ids=[str(a['articleId']) for a in cohort['articles']]
    raw={str(x['articleId']):x for x in readj(RAW)}; enriched={str(x['articleId']):x for x in readj(ENR)}
    if len(ids)!=100 or any(i not in raw or i not in enriched for i in ids): raise RuntimeError('100 article join failed')
    config=load_config(ROOT/'config/vertical_slice.yaml'); extractor=extractor_from_project_config(config)
    OUT.mkdir(parents=True)
    index_path=OUT/'kg_entity_index.json'
    index_result=subprocess.run([str(ROOT/'.venv/Scripts/python.exe'),str(ROOT/'scripts/news_event_rdf.py'),'index',str(index_path)],capture_output=True,text=True,encoding='utf8')
    if index_result.returncode: raise RuntimeError(index_result.stderr or index_result.stdout)
    kg_index=json.loads(index_path.read_text(encoding='utf8')); article_uri=kg_index['articles']
    kg_graph=Graph().parse(ROOT/'data/gold/knowledge_graph.ttl',format='turtle')
    kg_entities,kg_entity_keys=build_index(kg_graph, ROOT/'data/external/verified_entity_aliases.json')
    rows=[]; event_counter=Counter(); statuses=Counter()
    model_records=[]; evidence_records=[]; event_records=[]; accepted=[]
    for n,aid in enumerate(ids,1):
        art=raw[aid]; enr=enriched[aid]
        try:
            preds=extractor.extract(art,enr); status='SUCCESS'
        except Exception as exc:
            preds=[]; status='FAILED'; rows.append({'articleId':aid,'status':status,'error':f'{type(exc).__name__}: {exc}','events':[]}); statuses[status]+=1; print(f'[{n}/100] failed {aid}: {exc}',flush=True); continue
        statuses[status]+=1; rows.append({'articleId':aid,'status':status,'title':art.get('title',''),'events':preds})
        for p in preds:
            event_counter[p['eventType']]+=1
            trigger=p['trigger']['text']; span=p['evidenceSpan']; txt=span['text']; ss=int(span['startChar']); se=int(span['endChar'])
            link_suggestions=[]
            prepared=extractor.prepare_input(art,enr); full=prepared.text
            for m in p.get('entityMentions',[]):
                start,end=m.get('startChar'),m.get('endChar')
                span_ok=isinstance(start,int) and isinstance(end,int) and 0<=start<end<=len(full) and full[start:end]==m.get('text')
                resolution=resolve_mention(m,kg_entities,kg_entity_keys,context=full) if span_ok else {'status':'UNRESOLVED','uri':None,'candidates':[],'method':None,'reason':'Entity span failed exact prepared-text verification.'}
                found=[]
                if resolution.get('uri'):
                    uri=resolution['uri']; found=[{'uri':uri,'type':kg_entities[uri]['types'],'matchedName':m['text'],'sourceReferences':kg_entities[uri]['sourceReferences']}]
                elif resolution['status']=='AMBIGUOUS':
                    found=[{'uri':uri,'type':kg_entities[uri]['types'],'matchedName':m['text'],'sourceReferences':kg_entities[uri]['sourceReferences']} for uri in resolution['candidates']]
                link_suggestions.append({'mention':m,'matches':found,
                    'status':'LINKED_UNIQUE' if resolution['status']=='MATCHED' else ('AMBIGUOUS' if resolution['status']=='AMBIGUOUS' else 'UNLINKED'),
                    'resolverStatus':resolution['status'],'resolutionMethod':resolution.get('method'),
                    'spanVerified':span_ok,'reason':resolution['reason'],
                    'nearMatches':resolution['candidates'] if resolution['status']=='UNRESOLVED' else []})
            eid=p['eventId']; evidence_id='EVIDENCE:'+hashlib.sha256((aid+'|'+str(ss)+'|'+str(se)).encode()).hexdigest()[:20]
            key='PROPOSED:'+norm(p['eventType'])+':'+norm(trigger)+':'+aid
            event_uri='https://example.org/wfkg/staging/event/'+hashlib.sha256(eid.encode()).hexdigest()[:24]
            rec={'articleId':aid,'articleUri':str(article_uri.get(aid,'')),'eventId':eid,'eventUri':event_uri,'reportedBy':str(article_uri.get(aid,'')),'canonicalKey':key,'canonicalKeyStatus':'PENDING_REVIEW','eventType':p['eventType'],'description':f"{p['eventType']} được dự đoán từ trigger ‘{trigger}’.",'availableAt':art.get('availableAt'),'effectiveTradingDate':None,'trigger':p['trigger'],'confidenceScore':p['confidenceScore'],'evidence':{'evidenceId':evidence_id,'evidenceText':txt,'extractedFrom':str(article_uri.get(aid,'')),'supports':event_uri,'availableAt':art.get('availableAt'),'startOffset':ss,'endOffset':se},'entities':p.get('entityMentions',[]),'arguments':p.get('argumentMentions',[]),'entityLinkSuggestions':link_suggestions,'sourceMethod':'PHOBERT_BKEE_ED_EMD_EAE','reviewStatus':'REVIEW_REQUIRED','reviewReasons':['effectiveTradingDate is not established by model outputs','canonical identity across articles is unresolved','BKEE event type has no verified finance ontology mapping']}
            # Evidence offsets point into prepared model input (title + selected body), not the body alone.
            # Persist exact source text offsets only when this exact slice is verifiable.
            prepared=extractor.prepare_input(art,enr)
            if prepared.text[ss:se] != txt: rec['evidence']['startOffset']=None; rec['evidence']['endOffset']=None; rec['reviewReasons'].append('evidence offsets failed exact source alignment')
            else: rec['evidence']['offsetBasis']='preparedTitleAndBodyText'
            # Ontology v1.0.5 SHACL requires effectiveTradingDate. We never substitute publication date.
            event_records.append(rec); evidence_records.append(rec['evidence']); model_records.append(rec)
        print(f'[{n}/100] {aid}: events={len(preds)}',flush=True)
    dedup_groups={}
    for rec in event_records:
        unique_links=sorted({m['matches'][0]['uri'] for m in rec['entityLinkSuggestions'] if len(m['matches'])==1})
        identity='|'.join(unique_links) if unique_links else rec['articleId']
        fingerprint='|'.join((norm(rec['eventType']),norm(rec['trigger']['text']),identity))
        dedup_groups.setdefault(fingerprint,[]).append(rec)
    possible_duplicate_group_count=0
    for fingerprint, group in dedup_groups.items():
        group_key='PENDING:'+hashlib.sha256(fingerprint.encode()).hexdigest()[:20]
        for rec in group:
            rec['canonicalKey']=group_key
            rec['duplicateAuditStatus']='POSSIBLE_DUPLICATE' if len(group)>1 else 'NO_MATCH_IN_COHORT'
        if len(group)>1: possible_duplicate_group_count+=1
    entity_link_counts=Counter(item['status'] for rec in event_records for item in rec['entityLinkSuggestions'])
    argument_link_counts=Counter(item.get('entityMatchStatus','UNRESOLVED') for rec in event_records for item in rec['arguments'])
    (OUT/'model_predictions.json').write_text(json.dumps(rows,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    (OUT/'staging_review.json').write_text(json.dumps(event_records,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    date_result=subprocess.run([str(ROOT/'.venv-phobert-bkee/Scripts/python.exe'),str(ROOT/'scripts/apply_effective_trading_date.py'),str(OUT)],capture_output=True,text=True,encoding='utf8')
    if date_result.returncode: raise RuntimeError(f'effectiveTradingDate resolution failed: {date_result.stderr or date_result.stdout}')
    effective_date_summary=json.loads(date_result.stdout)
    rdf_result=subprocess.run([str(ROOT/'.venv/Scripts/python.exe'),str(ROOT/'scripts/news_event_rdf.py'),'build',str(OUT)],capture_output=True,text=True,encoding='utf8')
    if rdf_result.returncode: raise RuntimeError(f'SHACL/RDF helper failed: {rdf_result.stderr or rdf_result.stdout}')
    validation_result=json.loads(rdf_result.stdout)
    conforms=validation_result['shaclConforms']; report_text=validation_result['shaclReport']
    source_version='1.0.5' if '1.0.5' in (ROOT/'schema/ontology.ttl').read_text(encoding='utf8') else 'unknown'
    auxiliary_training={}
    for task in ('emd','eae'):
        report_path=ROOT/'runs'/f'phobert_bkee_{task}_v1'/'training_report.json'
        if report_path.is_file():
            train_report=json.loads(report_path.read_text(encoding='utf8'))
            auxiliary_training[task]={'trainRows':train_report.get('trainRows'),'epochs':train_report.get('losses'),'devMetrics':None,'testSetUsed':False}
    entity_type_counts=Counter(item['type'] for item in kg_index['entities'])
    summary={'createdAt':datetime.now(timezone.utc).isoformat(),'articleCount':100,'processedSuccessfully':statuses['SUCCESS'],'failed':statuses['FAILED'],'predictedEventCount':sum(event_counter.values()),'articlesWithEvents':sum(1 for r in rows if r['events']),'articlesWithoutEvents':sum(1 for r in rows if not r['events']),'predictedByBkeeType':dict(sorted(event_counter.items())),'eventEvidenceProposalsInReview':len(event_records),'possibleDuplicateGroups':possible_duplicate_group_count,'kgEntityIndexCount':len(kg_index['entities']),'kgEntityIndexByType':dict(sorted(entity_type_counts.items())),'mentionEntityLinkStatusCounts':dict(entity_link_counts),'argumentToMentionSpanMatchCounts':dict(argument_link_counts),'validatedEvidenceCount':validation_result['validatedEvidenceCount'],'validatedEventCount':validation_result['validatedEventCount'],'validatedRdfTripleCount':validation_result['validatedRdfTripleCount'],'shaclConforms':bool(conforms),'reviewCandidateShaclConforms':bool(validation_result['reviewCandidateShaclConforms']),'reviewCandidateRdfTripleCount':validation_result['reviewCandidateRdfTripleCount'],'effectiveTradingDateRuleId':'HOSE_PUBLICATION_CUTOFF_0800_ICT_V1','effectiveTradingDateCutoff':'08:00:00 Asia/Ho_Chi_Minh','effectiveTradingDateStatusCounts':effective_date_summary['statusCounts'],'effectiveTradingDateResolvedByDate':effective_date_summary['resolvedByDate'],'effectiveTradingDateCalendar':'config/hose_trading_calendar_2026.json','effectiveTradingDateTimestampTrustSource':'data/derived/news_timestamp_trust_audit.json','shaclReport':str(report_text),'reviewCandidateShaclReport':str(validation_result['reviewCandidateShaclReport']),'schemaUsed':'schema/ontology.ttl + schema/shapes.ttl','schemaVersion':source_version,'requestedOntologyV1FilesPresent':False,'checkpointPaths':{'ED':'models/phobert_bkee_event_detection_v2','EMD':'models/phobert_bkee_emd_v1','EAE':'models/phobert_bkee_eae_trigger_conditioned_v1'},'auxiliaryTraining':auxiliary_training,'analystAnnotationUsedAsModelOutput':False,'testSplitUsed':False,'limitations':['Exact ontology_v1.0.ttl and shapes_v1.0.ttl files are absent; workspace schema is version 1.0.5.','Unverified publication times remain unresolved and their Event predictions stay in review staging.','Trigger-conditioned EAE uses one predicted Event trigger and one EMD mention span per pair; outputs remain review-only and financial-domain F1 is not measured.','BKEE argument roles and entity types are general-domain; finance-specific semantics are not established.','ED/EMD quality on the financial cohort is unmeasured; trigger-conditioned EAE checkpoint selection uses BKEE dev only.','Canonical keys group only matching type/trigger plus a unique KG link; unresolved identities remain article-scoped review proposals.','Offsets are against the prepared title+body input and are omitted if the exact evidence substring cannot be verified.'],'nextIntegration':['Review date and event identity; map only approved BKEE types to existing ontology eventType values.','Resolve unique entity matches and create Event–Company/Leader/Industry relations only after review.','Add EventStockCandidate generation only for confirmed Event–entity links.']}
    (OUT/'report.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    md = [
        '# NewsArticle → Evidence + Event vertical slice', '',
        f"- Processed: {summary['processedSuccessfully']}/100; failures: {summary['failed']}",
        f"- Predicted event mentions: {summary['predictedEventCount']} across {summary['articlesWithEvents']} articles; no event: {summary['articlesWithoutEvents']}",
        f"- Review staging: {summary['eventEvidenceProposalsInReview']} predictions",
        f"- SHACL valid Evidence/Event in output: {summary['validatedEvidenceCount']}/{summary['validatedEventCount']}; cutoff resolved: {summary['effectiveTradingDateStatusCounts']}.",
        f"- Review candidate RDF triples: {summary['reviewCandidateRdfTripleCount']}; review candidate SHACL conforms: {summary['reviewCandidateShaclConforms']} (see review_candidate_shacl_report.ttl).",
        f'- Validation uses workspace schema v{source_version}; requested v1.0 files are missing.',
        '- BKEE types: '+', '.join(f'{k}={v}' for k,v in sorted(event_counter.items())),
        '', '## Review constraints', '', *('- '+x for x in summary['limitations']), ''
    ]
    (OUT/'report.md').write_text('\n'.join(md),encoding='utf8')
    subprocess.run([sys.executable,str(ROOT/'scripts/finalize_news_event_report.py'),str(OUT)],check=True)
    print(f'complete: {summary["processedSuccessfully"]}/100 events={summary["predictedEventCount"]} staged={len(event_records)} SHACL={conforms}',flush=True)
if __name__=='__main__': main()
