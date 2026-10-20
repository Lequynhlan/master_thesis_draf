"""Validate the immutable base KG plus generated event slice with project SHACL."""
import json, sys
from rdflib import Graph
from pyshacl import validate
base, additions, shapes, report = sys.argv[1:]
data=Graph().parse(base); data.parse(additions)
shape_graph=Graph().parse(shapes)
conforms, report_graph, text=validate(data_graph=data,shacl_graph=shape_graph,inference='none',abort_on_first=False,allow_infos=False,allow_warnings=False)
report_graph.serialize(report,format='turtle')
print(json.dumps({'conforms':bool(conforms),'text':str(text)},ensure_ascii=False))
