#!/usr/bin/env python
"""Read-only, format-specific audit of WFKG Draw.io appendix vs TTL/SHACL.
No output files, rewriting, inference, or automatic fixes.
"""
import argparse
import hashlib
import html
import json
import re
import sys
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

from rdflib import Graph, RDF, RDFS, OWL, SH, URIRef
from rdflib.plugins.sparql.parser import parseQuery


def label_text(value):
    # This bundle uses explicit <br> separators in property panels.
    value = html.unescape(value)
    value = re.sub(r'<(?:br\b[^>]*|/(?:div|p|li))>', '\n', value, flags=re.I)
    return html.unescape(re.sub(r'<[^>]+>', '', value)).replace('\xa0', ' ')


def audit(ontology, shapes, drawio):
    results = []
    def add(status, where, message):
        results.append({'status': status, 'where': where, 'message': message})
    files = [ontology, shapes, drawio]
    before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    graph = Graph().parse(ontology, format='turtle')
    constraints = Graph().parse(shapes, format='turtle')
    root = ET.parse(drawio).getroot()
    add('PASS', 'inputs', 'TTL, SHACL and Draw.io XML parse successfully')
    ontologies = list(graph.subjects(RDF.type, OWL.Ontology))
    if len(ontologies) != 1:
        raise ValueError('Expected exactly one owl:Ontology')
    namespace = str(ontologies[0]).rstrip('#') + '#'
    def iri(name):
        return URIRef(namespace + name)
    def local(term):
        return str(term).rsplit('#', 1)[-1]
    classes = set(graph.subjects(RDF.type, OWL.Class))
    objects = set(graph.subjects(RDF.type, OWL.ObjectProperty))
    datatypes = set(graph.subjects(RDF.type, OWL.DatatypeProperty))
    props = objects | datatypes

    def ancestors(term, predicate):
        seen = {term}
        todo = [term]
        while todo:
            for parent in graph.objects(todo.pop(), predicate):
                if parent not in seen:
                    seen.add(parent)
                    todo.append(parent)
        return seen

    def property_values(prop, predicate):
        return {v for parent in ancestors(prop, RDFS.subPropertyOf)
                for v in graph.objects(parent, predicate)}

    def compatible(name, restriction):
        if (restriction, OWL.unionOf, None) in graph:
            head = graph.value(restriction, OWL.unionOf)
            return any(compatible(name, x) for x in graph.items(head))
        return restriction in ancestors(iri(name), RDFS.subClassOf)

    # Direct property shapes only, including targetClass inheritance.
    def property_shapes(owner, prop):
        owners = ancestors(iri(owner), RDFS.subClassOf)
        return [ps for shape in set(constraints.subjects(SH.targetClass, None))
                if any(c in owners for c in constraints.objects(shape, SH.targetClass))
                for ps in constraints.objects(shape, SH.property)
                if constraints.value(ps, SH.path) == prop]

    def check_domain(prop, owner, where):
        expected = property_values(prop, RDFS.domain)
        if not expected:
            add('NOT CHECKED', where, f'{local(prop)}: no explicit/inherited OWL domain; shared ownership not inferred')
        elif all(compatible(owner, x) for x in expected):
            add('PASS', where, f'{owner}.{local(prop)} domain matches TTL (subclass accepted)')
        else:
            add('FAIL', where, f'{owner}.{local(prop)} domain differs from TTL: {sorted(local(x) for x in expected)}')

    appendix = []
    diagrams = root.findall('diagram')
    if not diagrams:
        raise ValueError('No Draw.io diagram found')
    for diagram in diagrams:
        tab = diagram.get('name', '?')
        model = diagram.find('mxGraphModel')
        if model is None:
            raise ValueError(f'{tab}: compressed/unsupported diagram; export uncompressed XML')
        cells = model.findall('.//mxCell')
        ids = [c.get('id') for c in cells]
        duplicate = [x for x, count in Counter(ids).items() if count > 1]
        if None in ids or duplicate:
            add('FAIL', tab, f'Missing or duplicate cell IDs: {duplicate}')
        else:
            add('PASS', tab, f'{len(cells)} unique cell IDs')
        known = set(ids)
        broken = [(c.get('id'), attr, c.get(attr)) for c in cells
                  for attr in ('parent', 'source', 'target')
                  if c.get(attr) is not None and c.get(attr) not in known]
        add('FAIL' if broken else 'PASS', tab, f'Broken references: {broken}')
        if tab.startswith('06-'):
            appendix.extend((f'{tab}/cell={c.get("id")}', label_text(c.get('value', ''))) for c in cells)
    if not appendix:
        raise ValueError('Expected appendix tab whose name starts with 06-')

    all_text = '\n'.join(t for _, t in appendix)
    for term in sorted(classes | props, key=str):
        name = local(term)
        present = re.search(r'(?<![\w])' + re.escape(name) + r'(?![\w])', all_text) is not None
        add('PASS' if present else 'FAIL', 'appendix inventory', f'{name}: ' + ('name present only (not semantic proof)' if present else 'MISSING'))
    checked_properties = set()
    arrow_count = 0
    for cell, text in appendix:
        for line_no, line in enumerate(text.splitlines(), 1):
            line = line.strip()
            where = f'{cell}/label-line={line_no}: {line}'
            # Object entries: Owner —property [cardinality] (annotation)→ Range
            match = re.fullmatch(r'(\w+)\s*—(.+?)→\s*(\w+)', line)
            if match:
                arrow_count += 1
                owner, middle, target = match.groups()
                if iri(owner) not in classes:
                    add('FAIL', where, f'Unknown owner class: {owner}')
                card = re.search(r'\[(\d+)(?:\.\.(\d+|\*))?\]', middle)
                bracket = re.search(r'\[[^]]*\]', middle)
                if ('[' in middle or ']' in middle) and (not card or not bracket or card.group() != bracket.group()):
                    add('FAIL', where, 'Invalid cardinality syntax; expected [1], [0..*] or [1..*]')
                if card and card[2] not in (None, '*') and int(card[2]) < int(card[1]):
                    add('FAIL', where, 'Invalid cardinality: maximum is smaller than minimum')
                names = re.sub(r'\([^)]*\)|\[[^]]*\]', '', middle).strip().split('/')
                for name in map(str.strip, names):
                    prop = iri(name)
                    checked_properties.add(prop)
                    if prop not in objects:
                        add('FAIL', where, f'{name}: not an OWL ObjectProperty')
                        continue
                    check_domain(prop, owner, where)
                    ranges = property_values(prop, RDFS.range)
                    if ranges:
                        ok = iri(target) in classes and all(compatible(target, x) for x in ranges)
                        add('PASS' if ok else 'FAIL', where, f'{name} range: Draw.io={target}; TTL={sorted(local(x) for x in ranges)}')
                    elif target == 'IRI':
                        ps = property_shapes(owner, prop)
                        kinds = [constraints.value(x, SH.nodeKind) for x in ps]
                        if SH.IRI in kinds:
                            add('PASS', where, f'{name}: IRI matches SHACL nodeKind')
                        else:
                            add('NOT CHECKED', where, f'{name}: IRI not directly specified by OWL range/SHACL nodeKind')
                    else:
                        add('NOT CHECKED', where, f'{name}: no explicit/inherited OWL range')
                    if card:
                        lo = int(card[1]); hi = lo if card[2] is None else (None if card[2] == '*' else int(card[2]))
                        ps = property_shapes(owner, prop)
                        if not ps:
                            add('NOT CHECKED', where, f'{name}: no direct SHACL property shape for {owner}')
                        else:
                            mins = [int(x) for s in ps for x in constraints.objects(s, SH.minCount)]
                            maxs = [int(x) for s in ps for x in constraints.objects(s, SH.maxCount)]
                            slo, shi = max(mins, default=0), min(maxs) if maxs else None
                            add('PASS' if (lo, hi) == (slo, shi) else 'FAIL', where,
                                f'{name} cardinality: Draw.io={(lo, hi)}; SHACL={(slo, shi)} (None=unbounded)')
                continue
            # Datatype list: Owner[/Subclass]: property, property...
            match = re.fullmatch(r'([\w/]+):\s*(.+)', line)
            if match:
                owners, names = match.groups()
                for owner in owners.split('/'):
                    if iri(owner) not in classes:
                        add('FAIL', where, f'Unknown owner class: {owner}')
                    for name in map(str.strip, names.split(',')):
                        prop = iri(name)
                        checked_properties.add(prop)
                        if prop not in datatypes:
                            add('FAIL', where, f'{name}: not an OWL DatatypeProperty')
                        else:
                            check_domain(prop, owner, where)
                # These panels do not show datatypes, so do not invent a comparison.
                add('NOT CHECKED', where, 'Datatype range not printed in this label; only ownership/property kind compared')
    if not arrow_count:
        add('FAIL', 'appendix', 'No structured object-property arrows parsed')
    for prop in sorted(props - checked_properties, key=str):
        add('NOT CHECKED', 'appendix', f'{local(prop)}: mentioned only in shared/narrative text; no structured entry compared')
    for q in constraints.objects(None, SH.select):
        parseQuery(str(q))
    add('PASS', 'SHACL', f'{len(list(constraints.objects(None, SH.select)))} SELECT constraints parse (not behavioral execution)')
    for where, message in (
        ('appendix', 'Only printed cardinalities and direct SHACL property shapes compared; qualified/logical/SPARQL constraints not equated to cardinality labels'),
        ('diagram', 'Other tabs: structure only; route semantics, free-form labels, connector class semantics and layout require human review'),
        ('validation', 'No SHACL conformance execution, runtime, calendar, scoring/evaluation or DOCX audit'),
    ):
        add('NOT CHECKED', where, message)
    after = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    add('PASS' if before == after else 'FAIL', 'read-only', 'SHA256 before/after ' + ('unchanged' if before == after else 'CHANGED'))
    return {'inputs_sha256': before, 'results': results, 'counts': dict(Counter(r['status'] for r in results))}


def main():
    base = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ontology', type=Path, default=base / 'ontology_v1.0.ttl')
    parser.add_argument('--shapes', type=Path, default=base / 'shapes_v1.0.ttl')
    parser.add_argument('--drawio', type=Path, default=base / 'master_thesis_v1_synced_01-10.drawio.xml')
    parser.add_argument('--json', action='store_true', help='JSON to stdout only, no file creation')
    parser.add_argument('--verbose', action='store_true', help='Print PASS details as well')
    args = parser.parse_args()
    try:
        report = audit(args.ontology, args.shapes, args.drawio)
    except Exception as exc:
        print(f'ERROR: {type(exc).__name__}: {exc}', file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for row in report['results']:
            if args.verbose or row['status'] != 'PASS':
                print(f"{row['status']} | {row['where']} | {row['message']}")
        print('SUMMARY:', json.dumps(report['counts']))
        print('Scope-limited result; NOT CHECKED items require manual review.')
    return 1 if report['counts'].get('FAIL', 0) else 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    sys.exit(main())
