"""Read-only KG entity index and SHACL-gated RDF artifacts for news predictions."""
import hashlib, json, re, subprocess, sys
from pathlib import Path
from rdflib import Graph, Namespace, URIRef, Literal, RDF, XSD
ROOT=Path(__file__).resolve().parents[1]; W=Namespace('https://example.org/wfkg/v1#')
BASE=ROOT/'data/gold/knowledge_graph.ttl'; SHAPES=ROOT/'schema/shapes.ttl'; VALIDATOR=ROOT/'.venv/Scripts/python.exe'; VALIDATE=ROOT/'scripts/validate_event_slice.py'
def index(out):
    graph=Graph().parse(BASE); articles={str(value):str(subject) for subject,value in graph.subject_objects(W.articleId)}; entities=[]
    for subject in set(graph.subjects(RDF.type,None)):
        kind=next((str(obj).rsplit('#',1)[-1] for obj in graph.objects(subject,RDF.type) if str(obj).startswith(str(W))), '')
        if kind not in {'Company','Bank','GovernmentOrganization','CorporateLeader','Industry'}: continue
        names={str(obj) for predicate in (W.fullName,W.shortName,W.aliasName,W.ticker,W.companyId,W.stockSymbol,W.name) for obj in graph.objects(subject,predicate) if str(obj).strip()}
        if names: entities.append({'uri':str(subject),'type':kind,'names':sorted(names)})
    Path(out).write_text(json.dumps({'articles':articles,'entities':entities},ensure_ascii=False)+'\n',encoding='utf8')
def validate(candidate, report):
    result=subprocess.run([str(VALIDATOR),str(VALIDATE),str(BASE),str(candidate),str(SHAPES),str(report)],capture_output=True,text=True,encoding='utf8')
    if result.returncode: raise RuntimeError(result.stderr or result.stdout)
    return json.loads(result.stdout)
def build(out):
    out=Path(out); records=json.loads((out/'staging_review.json').read_text(encoding='utf8')); review=Graph(); review.bind('wfkg',W)
    for rec in records:
        ev=URIRef(rec['eventUri']); evid=URIRef('https://example.org/wfkg/staging/evidence/'+rec['evidence']['evidenceId'].split(':',1)[1]); article=URIRef(rec['articleUri']) if rec.get('articleUri') else None
        review.add((ev,RDF.type,W.Event)); review.add((ev,W.eventId,Literal(rec['eventId'],datatype=XSD.string))); review.add((ev,W.canonicalKey,Literal(rec['canonicalKey'],datatype=XSD.string)))
        review.add((ev,W.eventType,Literal(rec['eventType'],datatype=XSD.string))); review.add((ev,W.description,Literal(rec['description'],datatype=XSD.string))); review.add((ev,W.availableAt,Literal(rec['availableAt'],datatype=XSD.dateTime)))
        if rec.get('effectiveTradingDate'):
            review.add((ev,W.effectiveTradingDate,Literal(rec['effectiveTradingDate'],datatype=XSD.date)))
        if article: review.add((article,W.reports,ev))
        review.add((evid,RDF.type,W.Evidence)); review.add((evid,W.evidenceId,Literal(rec['evidence']['evidenceId'],datatype=XSD.string))); review.add((evid,W.evidenceText,Literal(rec['evidence']['evidenceText'],datatype=XSD.string)))
        review.add((evid,W.availableAt,Literal(rec['evidence']['availableAt'],datatype=XSD.dateTime)))
        if article: review.add((evid,W.extractedFrom,article))
        review.add((evid,W.supports,ev))
        if isinstance(rec['evidence'].get('startOffset'),int) and isinstance(rec['evidence'].get('endOffset'),int):
            review.add((evid,W.startOffset,Literal(rec['evidence']['startOffset'],datatype=XSD.integer))); review.add((evid,W.endOffset,Literal(rec['evidence']['endOffset'],datatype=XSD.integer)))
    review_path=out/'event_evidence_review_candidate.ttl'; review.serialize(review_path,format='turtle'); review_check=validate(review_path,out/'review_candidate_shacl_report.ttl')
    official=Graph(); official.bind('wfkg',W)
    eligible=[rec for rec in records if rec.get('effectiveTradingDateStatus')=='RESOLVED' and rec.get('effectiveTradingDate')]
    eligible_ids={rec['eventUri'] for rec in eligible}
    for triple in review:
        if str(triple[0]) in eligible_ids or (str(triple[0]).startswith('https://example.org/wfkg/staging/evidence/') and any(triple[0]==URIRef('https://example.org/wfkg/staging/evidence/'+rec['evidence']['evidenceId'].split(':',1)[1]) for rec in eligible)) or (triple[1]==W.reports and str(triple[2]) in eligible_ids):
            official.add(triple)
    official_path=out/'event_evidence_candidate.ttl'; official.serialize(official_path,format='turtle')
    official_check=validate(official_path,out/'shacl_validation.ttl')
    if official_check['conforms']:
        official_path.replace(out/'validated_event_evidence.ttl')
    else:
        empty=Graph(); empty.serialize(out/'validated_event_evidence.ttl',format='turtle'); official_path.unlink()
    return {'reviewCandidateShaclConforms':review_check['conforms'],'reviewCandidateRdfTripleCount':len(review),'reviewCandidateShaclReport':review_check['text'],'shaclConforms':official_check['conforms'],'validatedRdfTripleCount':len(official) if official_check['conforms'] else 0,'validatedEventCount':len(eligible) if official_check['conforms'] else 0,'validatedEvidenceCount':len(eligible) if official_check['conforms'] else 0,'shaclReport':official_check['text']}
if __name__=='__main__':
    if sys.argv[1]=='index': index(sys.argv[2])
    elif sys.argv[1]=='build': print(json.dumps(build(sys.argv[2]),ensure_ascii=False))
    else: raise SystemExit('usage: news_event_rdf.py index <path> | build <output-dir>')
