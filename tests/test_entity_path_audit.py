import importlib.util
from pathlib import Path

from rdflib import Graph, Namespace

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("entity_path_audit", ROOT / "scripts/audit_vertical_slice_entity_paths.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def test_normalization_repairs_accents_legal_prefixes_and_honorifics():
    assert audit.norm("Ngân hàng TMCP Sài Gòn") == audit.norm("ngan hang thuong mai co phan sai gon")
    assert audit.variants("ông Nguyễn Xuân Vũ") & audit.variants("Nguyễn Xuân Vũ")


def test_kg_parenthetical_alias_resolves_but_unlisted_brand_does_not():
    g = Graph().parse(ROOT / "data/gold/knowledge_graph.ttl")
    index, by_key = audit.build_entity_index(g)
    linked = audit.resolve_mention({"text": "Techcombank", "entityType": "ORG"}, index, by_key, True)
    assert linked["status"] == "MATCHED"
    assert audit.resolve_mention({"text": "Vietcombank", "entityType": "ORG"}, index, by_key, True)["status"] in {"MISSING_ALIAS", "MISSING_KG_ENTITY"}


def test_observed_as_of_is_not_treated_as_effective_interval():
    g = Graph()
    W = Namespace("https://example.org/wfkg/v1#")
    relation = W["relation"]
    g.add((relation, W.observedAsOf, __import__("rdflib").Literal("2025-01-01")))
    status, reason = audit.active_for_event(g, relation, __import__("datetime").date(2025, 1, 2), None, snapshot_only=True)
    assert status == "INSUFFICIENT_EVIDENCE"
    assert "snapshot" in reason


def test_audit_paths_are_exactly_four_schema_paths():
    assert audit.PATHS == ("DIRECT", "INDIRECT_SUBSIDIARY", "INDIRECT_LEADERSHIP", "INDIRECT_INDUSTRY")
