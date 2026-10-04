#!/usr/bin/env python3
"""Validate this separate real-news fixture with unchanged 1.0.5 SHACL and SPARQL."""
from __future__ import annotations

import json
import re
from pathlib import Path

from pyshacl import validate
from rdflib import Graph, SH


HERE = Path(__file__).resolve().parent
CONTRACT = HERE.parents[1]
DATA = Graph().parse(HERE / "data.ttl", format="turtle")
SHAPES = Graph().parse(CONTRACT / "shapes_v1.0.ttl", format="turtle")
ONTOLOGY = Graph().parse(CONTRACT / "ontology_v1.0.ttl", format="turtle")
EXPECTED = json.loads((HERE / "expected.json").read_text(encoding="utf-8"))


def named_queries() -> list[tuple[str, str]]:
    chunks = re.split(r"(?m)^# QUERY-ID: ([A-Za-z0-9_]+)\s*$", (HERE / "queries.rq").read_text(encoding="utf-8"))
    return [(chunks[i], chunks[i + 1].strip()) for i in range(1, len(chunks), 2)]


conforms, report_graph, _ = validate(
    DATA, shacl_graph=SHAPES, ont_graph=ONTOLOGY, inference="none", advanced=True
)
violations = []
for result in report_graph.subjects(SH.resultSeverity, None):
    violations.append({
        "focus": str(next(report_graph.objects(result, SH.focusNode), "")),
        "path": str(next(report_graph.objects(result, SH.resultPath), "")),
        "message": str(next(report_graph.objects(result, SH.resultMessage), "")),
    })
print(f"SHACL conforms (unchanged 1.0.5 shapes, inference=none): {bool(conforms)}")
print(f"SHACL results: {len(violations)}")
for violation in violations:
    print("  ", violation)

failures = []
for query_id, query in named_queries():
    actual = [[str(value) for value in row] for row in DATA.query(query)]
    expected = EXPECTED[query_id]
    ok = actual == expected
    print(f"{query_id}: {'PASS' if ok else 'FAIL'} {actual}")
    if not ok:
        failures.append({"query": query_id, "expected": expected, "actual": actual})

if not conforms or failures:
    raise SystemExit(1)
