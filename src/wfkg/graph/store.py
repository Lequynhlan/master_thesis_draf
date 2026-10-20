"""Load, serialize and validate RDF data against the project schema."""

from __future__ import annotations

from pathlib import Path

from pyshacl import validate
from rdflib import Graph


class GraphStore:
    def __init__(self, ontology_path: Path, shapes_path: Path) -> None:
        self.ontology_path = ontology_path
        self.shapes_path = shapes_path
        self.graph = Graph()
        self.graph.parse(ontology_path, format="turtle")

    def load(self, data_path: Path) -> None:
        self.graph.parse(data_path)

    def validate(self) -> tuple[bool, str]:
        conforms, _, report = validate(
            data_graph=self.graph,
            shacl_graph=str(self.shapes_path),
            inference="rdfs",
            abort_on_first=False,
            allow_infos=False,
            allow_warnings=False,
        )
        return bool(conforms), str(report)

    def save(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.graph.serialize(destination=output_path, format="turtle")
