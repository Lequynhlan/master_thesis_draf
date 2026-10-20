import importlib.util
import sys
from datetime import date
from pathlib import Path

from rdflib import Graph, Literal, Namespace, RDF

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wfkg.event_processing.kg_entity_resolution import build_index, resolve_mention, normalize_surface, repair_mojibake
from wfkg.event_processing.extraction import _argument_role_type_compatible, _nearest_trigger_ids

SPEC = importlib.util.spec_from_file_location("audit_entity_linking_v2", ROOT / "scripts/audit_entity_linking_v2.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)
W = Namespace("https://example.org/wfkg/v1#")


def test_vietnamese_full_bank_name_ticker_and_accentless_surface_resolve_same_uri():
    graph = Graph().parse(ROOT / "data/gold/knowledge_graph.ttl")
    index, key_index = build_index(graph)
    vcb = str(next(s for s, o in graph.subject_objects(W.shortName) if str(o) == "VCB"))
    assert resolve_mention({"text": "VCB", "entityType": "ORG"}, index, key_index)["uri"] == vcb
    full_name = str(next(graph.objects(__import__("rdflib").URIRef(vcb), W.fullName)))
    assert resolve_mention({"text": full_name, "entityType": "ORG"}, index, key_index)["uri"] == vcb
    unaccented = " ".join("".join(c for c in __import__("unicodedata").normalize("NFD", full_name)
                                if __import__("unicodedata").category(c) != "Mn").split())
    assert resolve_mention({"text": unaccented, "entityType": "ORG"}, index, key_index)["uri"] == vcb
    tcb = str(next(s for s, o in graph.subject_objects(W.shortName) if str(o) == "TCB"))
    assert resolve_mention({"text": "Techcombank", "entityType": "ORG"}, index, key_index)["uri"] == tcb


def test_vietcombank_requires_explicit_document_equivalence_and_does_not_create_alias():
    graph = Graph().parse(ROOT / "data/gold/knowledge_graph.ttl")
    index, key_index = build_index(graph)
    vcb = str(next(s for s, o in graph.subject_objects(W.shortName) if str(o) == "VCB"))
    unresolved = resolve_mention({"text": "Vietcombank", "entityType": "ORG"}, index, key_index, context="Vietcombank mua thêm cổ phần.")
    assert unresolved["status"] == "UNRESOLVED"
    explicit = resolve_mention({"text": "Vietcombank", "entityType": "ORG"}, index, key_index, context="Vietcombank (VCB) công bố thông tin.")
    assert explicit["status"] == "MATCHED"
    assert explicit["method"] == "DOCUMENT_EXPLICIT_EQUIVALENCE"
    assert explicit["uri"] == vcb


def test_duplicate_label_stays_ambiguous_unless_unique_kg_label_occurs_in_context():
    graph = Graph()
    a, b = W["A"], W["B"]
    for uri, full in ((a, "Alpha Holdings Ltd"), (b, "Beta Holdings Ltd")):
        graph.add((uri, RDF.type, W.Company))
        graph.add((uri, W.fullName, Literal(full)))
        graph.add((uri, W.shortName, Literal("ABC")))
    index, key_index = build_index(graph)
    mention = {"text": "ABC", "entityType": "ORG"}
    assert resolve_mention(mention, index, key_index)["status"] == "AMBIGUOUS"
    result = resolve_mention(mention, index, key_index, context="ABC, Alpha Holdings Ltd announced.")
    assert result["status"] == "MATCHED" and result["uri"] == str(a)


def test_ambiguous_leader_can_resolve_only_via_active_position_to_linked_company():
    graph = Graph()
    l1, l2, c1, c2 = (W[x] for x in ("leader1", "leader2", "company1", "company2"))
    for leader in (l1, l2):
        graph.add((leader, RDF.type, W.CorporateLeader))
        graph.add((leader, W.fullName, Literal("Alex Nguyen")))
    for uri, company in ((W.pos1, c1), (W.pos2, c2)):
        graph.add((uri, W.positionAtCompany, company))
        graph.add((uri, W.validFrom, Literal("2020-01-01")))
    graph.add((l1, W.hasLeadershipPosition, W.pos1))
    graph.add((l2, W.hasLeadershipPosition, W.pos2))
    selected = audit.disambiguate_leader_by_linked_company(graph, [str(l1), str(l2)], {str(c1)}, date(2026, 1, 1), None)
    assert selected == str(l1)


def test_clipped_entity_argument_can_align_to_one_nested_emd_span():
    text = "Công ty Cổ phần Chứng khoán VPBank công bố thông tin."
    start = text.index("Cổ phần Chứng khoán VPBank")
    end = start + len("Cổ phần Chứng khoán VPBank")
    mention_start, mention_end = 0, text.index(" công bố")
    mention = {"mention": {"text": text[mention_start:mention_end], "entityType": "ORG"}}
    aligned, method = audit.align_argument_span(
        {"text": text[start:end], "startChar": start, "endChar": end, "role": "Entity"},
        {(mention_start, mention_end): mention}, "Transfer-ownership", 0, len(text))
    assert aligned is mention and method == "UNIQUE_NESTED_SPAN"
    assert audit.align_argument_span(
        {"text": text[start:end], "startChar": start, "endChar": end, "role": "Entity"},
        {(mention_start, mention_end): mention,
         (mention_start, mention_end + 1): {"mention": {"text": "overlapping ORG", "entityType": "ORG"}}},
        "Transfer-ownership", 0, len(text)) == (None, "")
    assert audit.event_role_compatible("Transfer-ownership", "Entity")
    assert not audit.event_role_compatible("Transfer-ownership", "Position")


def test_two_triggers_in_one_sentence_assign_argument_only_to_nearest_trigger():
    text = "VPB mua cổ phần, còn XYZ bán tài sản."
    triggers = [
        {"eventId": "E1", "trigger": {"startChar": 4, "endChar": 7}, "sentence": audit.sentence_bounds(text, 4, 7)},
        {"eventId": "E2", "trigger": {"startChar": 27, "endChar": 30}, "sentence": audit.sentence_bounds(text, 27, 30)},
    ]
    assert audit.nearest_trigger_event_ids(text, 0, 3, triggers) == ["E1"]
    assert audit.nearest_trigger_event_ids(text, 23, 26, triggers) == ["E2"]
    assert _nearest_trigger_ids(text, 0, 3, [x["trigger"] | {"eventId": x["eventId"]} for x in triggers]) == ["E1"]


def test_resolved_but_unrelated_entity_is_not_promoted_to_event_participant():
    assert audit.participants_from_linked_arguments([]) == {"Company": [], "CorporateLeader": [], "Industry": []}


def test_government_and_industry_uris_keep_their_types():
    graph = Graph().parse(ROOT / "data/gold/knowledge_graph.ttl")
    index, key_index = build_index(graph)
    gov_uri = next(graph.subjects(RDF.type, W.GovernmentOrganization))
    gov_label = next(graph.objects(gov_uri, W.organizationName), None) or next(graph.objects(gov_uri, W.fullName), None)
    if gov_label:
        result = resolve_mention({"text": str(gov_label), "entityType": "ORG"}, index, key_index)
        assert result["uri"] == str(gov_uri)
        assert audit.participants_from_linked_arguments([{"argument": {"role": "Entity"}, "types": ["GovernmentOrganization"]}])["Company"] == []


def test_argument_role_and_mention_type_are_checked_before_event_linking():
    assert not _argument_role_type_compatible("Person", "JOB")
    assert _argument_role_type_compatible("Person", "PER")
    assert _argument_role_type_compatible("Entity", "ORG")
    assert _argument_role_type_compatible("Money", "")


def test_unknown_and_non_event_entity_do_not_get_forced_to_kg_uri():
    graph = Graph()
    uri = W["VNP"]
    graph.add((uri, RDF.type, W.Company))
    graph.add((uri, W.shortName, Literal("VNP")))
    index, key_index = build_index(graph)
    assert resolve_mention({"text": "Unlisted Widgets Ltd", "entityType": "ORG"}, index, key_index)["status"] == "UNRESOLVED"
    # A valid URI is still only an entity resolution; absent argument evidence does not create a participant.
    assert resolve_mention({"text": "VNP", "entityType": "ORG"}, index, key_index)["status"] == "MATCHED"


def test_mojibake_repair_is_reversible_and_does_not_touch_valid_vietnamese():
    damaged = "Ph\u00c3\u00b9ng"  # UTF-8 text mistakenly decoded as Windows-1252.
    assert repair_mojibake(damaged) == "Ph\u00f9ng"
    assert repair_mojibake("Ho\u00e0ng Ng\u00e2n") == "Ho\u00e0ng Ng\u00e2n"
    assert normalize_surface("  NGÂN   HÀNG ") == normalize_surface("ngân hàng")
