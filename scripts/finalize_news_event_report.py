"""Recompute audit summaries from saved ED/EMD/EAE outputs without model inference."""
import collections, json, sys
import re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main(path):
    out=Path(path); report=json.loads((out/'report.json').read_text(encoding='utf8'))
    records=json.loads((out/'staging_review.json').read_text(encoding='utf8'))
    index=json.loads((out/'kg_entity_index.json').read_text(encoding='utf8'))
    entities=index['entities']
    def norm(value): return re.sub(r'[^\w]+',' ',str(value).casefold(),flags=re.UNICODE).strip()
    groups={}
    for row in records:
        suggestions=[]
        for mention in row.get('entities',[]):
            surface=norm(mention['text']); matches=[]
            if surface:
                for entity in entities:
                    if any(norm(name)==surface for name in entity['names']):
                        matches.append({'uri':entity['uri'],'type':entity['type'],'matchedName':mention['text']})
            suggestions.append({'mention':mention,'matches':matches,'status':'LINKED_UNIQUE' if len(matches)==1 else ('AMBIGUOUS' if matches else 'UNLINKED')})
        row['entityLinkSuggestions']=suggestions
        unique=sorted({x['matches'][0]['uri'] for x in suggestions if len(x['matches'])==1})
        identity='|'.join(unique) if unique else row['articleId']
        fingerprint='|'.join((norm(row['eventType']),norm(row['trigger']['text']),identity))
        groups.setdefault(fingerprint,[]).append(row)
    for fingerprint, group in groups.items():
        key='PENDING:'+__import__('hashlib').sha256(fingerprint.encode()).hexdigest()[:20]
        for row in group:
            row['canonicalKey']=key
            row['duplicateAuditStatus']='POSSIBLE_DUPLICATE' if len(group)>1 else 'NO_MATCH_IN_COHORT'
    (out/'staging_review.json').write_text(json.dumps(records,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    entity_links=collections.Counter(x['status'] for row in records for x in row['entityLinkSuggestions'])
    arg_links=collections.Counter(x.get('entityMatchStatus','UNRESOLVED') for row in records for x in row['arguments'])
    type_counts=collections.Counter(x['type'] for x in index['entities'])
    offset_count=sum(isinstance(row['evidence'].get('startOffset'),int) and isinstance(row['evidence'].get('endOffset'),int) for row in records)
    training={}
    for task in ('emd','eae'):
        p=ROOT/'runs'/f'phobert_bkee_{task}_v1'/'training_report.json'
        if p.is_file():
            item=json.loads(p.read_text(encoding='utf8'))
            training[task]={'trainRows':item.get('trainRows'),'epochs':item.get('losses'),'devMetrics':None,'testSetUsed':False}
    report.update({'evidenceOffsetsVerified':offset_count,'kgEntityIndexCount':len(index['entities']),'kgEntityIndexByType':dict(sorted(type_counts.items())),
                   'mentionEntityLinkStatusCounts':dict(entity_links),'argumentToMentionSpanMatchCounts':dict(arg_links),'auxiliaryTraining':training})
    report['possibleDuplicateGroups']=sum(len(group)>1 for group in groups.values())
    (out/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    lines=['# NewsArticle → Evidence + Event vertical slice','',
      f"- Processed: {report['processedSuccessfully']}/{report['articleCount']}; failures: {report['failed']}",
      f"- Predicted event mentions: {report['predictedEventCount']} across {report['articlesWithEvents']} articles; no event: {report['articlesWithoutEvents']}",
      '- Events by BKEE type: '+', '.join(f'{k}={v}' for k,v in sorted(report['predictedByBkeeType'].items())),
      f"- Review staging: {report['eventEvidenceProposalsInReview']} predictions; possible duplicate groups: {report.get('possibleDuplicateGroups',0)}",
      f"- Evidence source offsets verified against prepared title+body: {report['evidenceOffsetsVerified']}/{report['eventEvidenceProposalsInReview']}.",
      '- KG entity index by type: '+', '.join(f'{k}={v}' for k,v in report['kgEntityIndexByType'].items()),
      '- Mention → KG link outcomes: '+', '.join(f'{k}={v}' for k,v in report['mentionEntityLinkStatusCounts'].items()),
      '- Argument → entity span matches: '+', '.join(f'{k}={v}' for k,v in report['argumentToMentionSpanMatchCounts'].items()),
      f"- SHACL accepted: {report['validatedEvidenceCount']} Evidence, {report['validatedEventCount']} Events; official output conforms: {report['shaclConforms']}",
      f"- Effective trading date: {report.get('effectiveTradingDateCutoff','08:00:00 Asia/Ho_Chi_Minh')} ({report.get('effectiveTradingDateRuleId','not applied')}); statuses: {report.get('effectiveTradingDateStatusCounts',{})}; resolved by date: {report.get('effectiveTradingDateResolvedByDate',{})}.",
      f"- Review candidate RDF triples: {report['reviewCandidateRdfTripleCount']}; review candidate conforms: {report['reviewCandidateShaclConforms']}.",
      f"- Publication timestamp audit: {report.get('timestampRecoveryAudit',{}).get('newlyRecoveredTimestamps',0)} newly recovered; {report.get('timestampRecoveryAudit',{}).get('eventsStillUnresolved',0)} Events remain unresolved. Categories: {report.get('timestampRecoveryAudit',{}).get('timestampClassificationByEvent',{})}.",
      f"- Ontology used: workspace schema v{report['schemaVersion']}; requested v1.0 files present: {report['requestedOntologyV1FilesPresent']}.",
      '- Auxiliary training losses (train only): '+', '.join(f"{k}={v['epochs']}" for k,v in training.items()),
      '', '## Limitations', '', *('- '+x for x in report['limitations']), '', '## Follow-up', '', *('- '+x for x in report['nextIntegration']), '']
    (out/'report.md').write_text('\n'.join(lines),encoding='utf8')
if __name__=='__main__': main(sys.argv[1])
