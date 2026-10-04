"""Read-only current-bundle review; output only outside submission. Run python -B review_phase1/presend_machine_probe.py."""
import sys, json, hashlib, subprocess, importlib.util, tempfile, datetime
from pathlib import Path
from rdflib import Graph, RDF, RDFS, OWL, SH, Literal, XSD
from pyshacl import validate
from owlrl import DeductiveClosure, OWLRL_Semantics
import rdflib, pyshacl, yaml
ROOT=Path(__file__).resolve().parent.parent
BASE=ROOT/'chỉnh sửa mới nhất - 01-10'
OUT=ROOT/'review_phase1'
def hashes():
    return {str(p.relative_to(BASE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in BASE.rglob('*') if p.is_file()}
result={'scope':str(BASE),'time':datetime.datetime.now(datetime.timezone.utc).isoformat(),'python':sys.version,'executable':sys.executable,'rdflib':rdflib.__version__,'pyshacl':pyshacl.__version__,'before':hashes(),'commands':[],'probes':[]}
for name,args in [('audit_schema_diagram.py',['--json']),('test_baseline_shacl.py',[]),('test_schema_diagram_audit.py',[])]:
    cmd=[sys.executable,'-B',str(BASE/'tools'/name),*args]
    p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace')
    result['commands'].append({'command':cmd,'cwd':str(ROOT),'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
    print(name,p.returncode, p.stderr[-140:] if p.stderr else '')
    if name.startswith('audit') and p.returncode==0: result['audit_counts']=json.loads(p.stdout)['counts']
spec=importlib.util.spec_from_file_location('fixture',BASE/'tools/test_baseline_shacl.py')
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m.BaselineShapeTests.setUpClass()
W=m.W
shapes=m.BaselineShapeTests.shapes
ontology=m.BaselineShapeTests.ontology
def control():
    t=m.BaselineShapeTests(); t.setUp(); return t.graph

def probe(name, mutate=lambda g:None,inference='none'):
    g=control(); mutate(g)
    with tempfile.TemporaryDirectory(prefix='presend-machine-',dir=OUT) as temp:
        p=Path(temp)/'mutated.ttl'; g.serialize(p,format='turtle')
        g=Graph().parse(p,format='turtle')
        ok,report,text=validate(g,shacl_graph=shapes,ont_graph=ontology,inference=inference,advanced=True)
        messages=sorted({str(v) for v in report.objects(None,SH.resultMessage)})
        result['probes'].append({'name':name,'conforms':bool(ok),'inference':inference,'triples':len(g),'messages':messages,'serialized_fixture':g.serialize(format='turtle')})
        print(name,bool(ok),messages[:2])
def setv(g,n,p,v):g.set((W[n],W[p],v))
probe('positive_control_serialized')
probe('positive_control_owlrl',inference='owlrl')
probe('unknown_event_type',lambda g:setv(g,'event','eventType',Literal('UNDECLARED_EVENT_TYPE')))
probe('malformed_canonical_key',lambda g:setv(g,'event','canonicalKey',Literal('')))
probe('unlinked_DIRECT_stock',lambda g:g.remove((W.company,W.hasStock,W.stock)))
probe('unknown_impact_type',lambda g:setv(g,'candidate','impactType',Literal('FUTURE_ROUTE',datatype=XSD.string)))
probe('mismatched_route_code',lambda g:setv(g,'candidate','relationPath',Literal('INDIRECT_INDUSTRY',datatype=XSD.string)))
probe('source_registry_not_point5',lambda g:setv(g,'source','reliabilityScore',m.decimal('.9')))
def strength(g):
    for n,p,v in [('candidate','relationStrength','.2'),('candidate','candidateScore','.1'),('reaction','reactionWeight','.01'),('reaction','signedWeight','.01')]:setv(g,n,p,m.decimal(v))
probe('compensated_strength_not_V1',strength)
def linking(g):
    for n,p,v in [('candidate','linkingConfidence','.2'),('candidate','confidenceScore','.425'),('candidate','candidateScore','.425'),('reaction','reactionWeight','.0425'),('reaction','signedWeight','.0425')]:setv(g,n,p,m.decimal(v))
probe('compensated_linking_not_V1',linking)
def dup(g):
    for s,p,o in list(g.triples((W.event,None,None))):
        if p!=W.hasEventStockCandidate:g.add((W.event2,p,o))
    g.set((W.event2,W.eventId,Literal('e2')))
    g.add((W.article,W.reports,W.event2));g.add((W.evidence,W.supports,W.event2))
probe('duplicate_event_canonical_key',dup)
def dates(g):
    setv(g,'event','effectiveTradingDate',Literal('2026-08-26',datatype=XSD.date))
    for p,v in [('abnormalReturn','0'),('cumulativeAbnormalReturn','0'),('impactScore','0'),('reactionWeight','0'),('signedWeight','0')]:setv(g,'reaction',p,m.decimal(v))
    setv(g,'reaction','marketReactionDirection',Literal('NEUTRAL',datatype=XSD.string))
    for n,v in [('s1','100'),('i1','1000')]:
        setv(g,n,'adjustedClose',m.decimal(v));setv(g,n,'returnValue',m.decimal('0'))
probe('intraday_same_day_effective_date',dates)
def untyped(g):g.remove((W.evidence,RDF.type,W.Evidence));g.remove((W.evidence,W.extractedFrom,None));g.remove((W.evidence,W.evidenceId,None));g.remove((W.evidence,W.evidenceText,None))
probe('untyped_support_node_without_evidence_fields',untyped)
probe('untyped_support_node_owlrl',untyped,inference='owlrl')
# Additional route controls and adversarial temporal eligibility: all mutations stay in a temp copy.
def relation(g,kind):
    g.remove((W.candidate,W.hasReaction,None));g.remove((W.reaction,None,None))
    setv(g,'candidate','candidateStatus',Literal('VALIDATED',datatype=XSD.string))
    route={'SubsidiaryRelation':'INDIRECT_SUBSIDIARY','LeadershipPosition':'INDIRECT_LEADERSHIP','IndustryExposure':'INDIRECT_INDUSTRY'}[kind]
    for p in ['impactType','relationPath']:setv(g,'candidate',p,Literal(route,datatype=XSD.string))
    g.add((W.rel,RDF.type,W[kind]));setv(g,'rel','availableAt',Literal('2026-08-25T10:00:00+07:00',datatype=XSD.dateTime));setv(g,'rel','sourceReference',W.syntheticSource);setv(g,'rel','dataQualityFlag',Literal('SYNTHETIC'));setv(g,'rel','relationConfidence',m.decimal('.5'))
    if kind!='IndustryExposure':setv(g,'rel','validFrom',Literal('2026-01-01',datatype=XSD.date))
    if kind=='SubsidiaryRelation':
        for p,o in g.predicate_objects(W.company):g.add((W.child,p,o))
        g.remove((W.child,W.hasStock,None));setv(g,'child','companyId',Literal('child'))
        g.remove((W.event,W.involvesCompany,None));g.add((W.event,W.involvesCompany,W.child));g.add((W.company,W.hasSubsidiaryRelation,W.rel));setv(g,'rel','subsidiaryCompany',W.child);setv(g,'rel','parentCompany',W.company)
    elif kind=='LeadershipPosition':
        g.add((W.leader,RDF.type,W.CorporateLeader));setv(g,'leader','personId',Literal('leader'));setv(g,'leader','fullName',Literal('synthetic'));g.add((W.leader,W.hasLeadershipPosition,W.rel));g.add((W.event,W.involvesLeader,W.leader));setv(g,'rel','positionHolder',W.leader);setv(g,'rel','positionAtCompany',W.company);setv(g,'rel','positionTitle',Literal('CEO'))
    else:
        g.add((W.company,RDF.type,W.Bank));g.add((W.industry,RDF.type,W.Industry));g.add((W.group,RDF.type,W.IndustryGroup))
        for n,p in [('industry','industryId'),('industry','industryName'),('group','industryGroupId'),('group','industryGroupName')]:setv(g,n,p,Literal(n))
        g.add((W.industry,W.belongsToGroup,W.group));g.add((W.event,W.relatedToIndustry,W.industry));g.add((W.company,W.hasIndustryExposure,W.rel));setv(g,'rel','exposureBank',W.company);setv(g,'rel','exposureIndustry',W.industry)
        setv(g,'rel','periodType',Literal('YEAR',datatype=XSD.string));setv(g,'rel','periodEnd',Literal('2025-12-31',datatype=XSD.date));setv(g,'rel','exposureRatio',m.decimal('.5'));setv(g,'rel','exposureStrength',m.decimal('.5'))
for kind in ['SubsidiaryRelation','LeadershipPosition','IndustryExposure']:
    probe('positive_'+kind,lambda g,k=kind:relation(g,k))
    def late(g,k=kind):relation(g,k);setv(g,'rel','availableAt',Literal('2026-08-28T10:00:00+07:00',datatype=XSD.dateTime))
    probe('future_input_'+kind,late)

d= yaml.safe_load((BASE/'EVENT_DICTIONARY.yaml').read_text(encoding='utf-8'))
entries=d['entries'];types={x['eventType'] for x in entries}
result['dictionary']={'entries':len(entries),'unique_types':len(types),'unknown_confusables':sorted({v for e in entries for v in e['confusable_cases'] if v not in types and v not in d['out_of_scope_confusables']}),'key_role_errors':[{e['eventType']:v} for e in entries for v in e['canonical_key'].split('|') if v!='eventType' and v not in e['required_roles']+e['optional_roles']]}
result['schema_inventory']={'classes':len(set(ontology.subjects(RDF.type,OWL.Class))),'multiple_domains':{str(p):list(map(str,ontology.objects(p,RDFS.domain))) for p in set(ontology.subjects(RDFS.domain,None)) if len(list(ontology.objects(p,RDFS.domain)))>1},'select_count':len(list(shapes.objects(None,SH.select))),'uncovered_classes':list(map(str,set(ontology.subjects(RDF.type,OWL.Class))-set(shapes.objects(None,SH.targetClass))))}
# Check historical audit hashes raw and LF-normalized without changing either source.
hist=json.loads((BASE/'tools/verification_contract_1.0.4.json').read_text(encoding='utf-8'))
result['historical_hash_comparison']=[]
for name,h in hist['artifact_sha256'].items():
    b=(BASE/name).read_bytes();raw=hashlib.sha256(b).hexdigest()
    lf=hashlib.sha256(b.replace(b'\r\n',b'\n')).hexdigest() if Path(name).suffix not in ['.docx','.pdf'] else None
    result['historical_hash_comparison'].append({'file':name,'historical':h,'current_raw':raw,'current_lf':lf,'raw_matches':raw==h,'lf_matches':lf==h if lf else None})
result['shared_domains']={name:list(map(str,ontology.objects(W[name],RDFS.domain))) for name in ['adjustedClose','returnValue','observationId','relationConfidence','availableAt','fullName','periodType','periodStart','periodEnd','methodVersion','sourceReference','validFrom','validTo','tradingDate','taxonomyName','dataQualityFlag']}
expected_false={'unlinked_DIRECT_stock','unknown_impact_type','mismatched_route_code','untyped_support_node_owlrl'}
result['probe_expectations_met']=all(p['conforms']==(p['name'] not in expected_false) for p in result['probes'])
assert result['probe_expectations_met'], 'Unexpected probe result; inspect log before claiming acceptance'
result['after']=hashes();result['changed_inputs']=[k for k in result['before'] if result['before'][k]!=result['after'].get(k)]
(OUT/'presend_current_machine_execution.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print('FINAL',result['audit_counts'],result['dictionary'],result['schema_inventory'],'changed',result['changed_inputs'])
