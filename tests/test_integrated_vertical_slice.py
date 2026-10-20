from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from rdflib import Graph
import json

from wfkg.event_processing.canonicalization import canonicalize
from wfkg.event_processing.candidates import generate_candidates
from wfkg.event_processing.extraction import ReviewedAnnotationExtractor
from wfkg.event_processing.linking import link_entities
from wfkg.market_reaction.job import calculate_car, day0_from_sessions, reaction_weights
from wfkg.vertical_slice.job import verify_release_snapshot

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "runs/wfkg_vertical_slice_news_100_release_v1"


def test_event_canonicalization_merges_only_same_explicit_key():
    rows = canonicalize([
        {"canonicalKey": "K", "eventId": "E1", "articleIds": ["A"], "evidence": ["X"]},
        {"canonicalKey": "K", "eventId": "E2", "articleIds": ["B"], "evidence": ["Y"]},
        {"eventId": "E3"},
    ])
    assert len(rows) == 2
    assert rows[0]["sourceArticles"] == ["A", "B"]
    assert rows[0]["canonicalizationStatus"] == "MERGED_REVIEWED_DUPLICATE"
    assert rows[1]["canonicalizationStatus"] == "NOT_EVALUATED"


def test_reviewed_extraction_keeps_human_provenance():
    extractor = ReviewedAnnotationExtractor([{"articles": ["A"], "eventId": "E", "reviewer": "analyst"}])
    row = extractor.extract("A")[0]
    assert row["extractionMethod"] == "ANALYST_REVIEWED"
    assert row["modelPrediction"] is False
    assert extractor.extract("missing") == []


def test_entity_linking_exact_and_ambiguous_alias():
    events = [{"participants": [{"text": "MBB"}, {"text": "MB"}, {"text": "unknown"}]}]
    entities = [
        {"uri": "urn:mbb", "name": "MBBank", "aliases": ["MBB", "MB"]},
        {"uri": "urn:other", "name": "Other", "aliases": ["MB"]},
    ]
    linked = link_entities(events, entities)[0]["participants"]
    assert linked[0]["linkingStatus"] == "LINKED_EXACT_ALIAS"
    assert linked[0]["entityUri"] == "urn:mbb"
    assert linked[1]["linkingStatus"] == "REVIEW_AMBIGUOUS"
    assert linked[2]["linkingStatus"] == "UNLINKED"


def test_candidate_score_uses_confidence_times_strength_only():
    result = generate_candidates([{"eventId": "E", "relationPaths": [{
        "ticker": "TCB", "impactType": "DIRECT", "confidenceScore": .85,
        "relationStrength": .8, "evidence": {"uri": "urn:e"}, "reactionWeight": 99,
    }]}], ("TCB",))
    assert result[0]["candidateScore"] == pytest.approx(.68)
    assert result[0]["scoreUsesReaction"] is False


def test_day0_uses_strictly_later_0900_ict_open():
    sessions = [date(2026, 10, 13), date(2026, 10, 14), date(2026, 10, 15)]
    # 02:00 UTC is exactly 09:00 ICT; strict-later means next session.
    assert day0_from_sessions(datetime(2026, 10, 13, 2, tzinfo=timezone.utc), sessions) == date(2026, 10, 14)
    assert day0_from_sessions(datetime(2026, 10, 13, 1, 59, tzinfo=timezone.utc), sessions) == date(2026, 10, 13)
    with pytest.raises(ValueError, match="timezone-aware"):
        day0_from_sessions(datetime(2026, 10, 13, 2), sessions)


def test_ar_car_and_reaction_weights():
    d = [date(2026, 10, 12), date(2026, 10, 13), date(2026, 10, 14)]
    stock = dict(zip(d, map(Decimal, (100, 101, 103))))
    bench = dict(zip(d, map(Decimal, (100, 100.5, 101))))
    value = calculate_car(stock, bench, d[1], (0, 1), sessions=d)
    assert value["status"] == "EVALUATED"
    expected = Decimal(".005") + Decimal(103) / Decimal(101) - 1 - (Decimal(101) / Decimal("100.5") - 1)
    assert value["car"] == expected
    weights = reaction_weights(value["car"], ".85", "1")
    assert weights["reactionWeight"] == weights["impactScore"] * Decimal(".85")


def test_missing_market_window_is_not_evaluated():
    day0 = date(2026, 10, 14)
    out = calculate_car({day0: 100}, {day0: 100}, day0, (0, 1), sessions=[day0])
    assert out == {"status": "NOT_EVALUATED", "reason": "INCOMPLETE_TRADING_WINDOW", "car": None}


def test_snapshot_integrity_and_deterministic_release_identity():
    verified = verify_release_snapshot(RELEASE / "release_manifest.json")
    assert verified["verifiedInputCount"] == 44
    assert verified["manifest"]["snapshotSelection"]["benchmarkSnapshotId"] == "VN30_KBS_20261016T120713Z"


def test_shacl_baseline_full_graph_and_focused_staging_reference_scopes():
    # These are machine-readable results emitted by the frozen release and
    # evaluation validators; the CLI replay runs the SHACL engine anew.
    release = json.loads((RELEASE / "release_validation.json").read_text(encoding="utf-8"))
    replay = json.loads((RELEASE / "replay_1/shacl_validation.json").read_text(encoding="utf-8"))
    eval_results = json.loads((ROOT / "runs/wfkg_post_correction_evaluation_v1/shacl_validation_results.json").read_text(encoding="utf-8"))
    assert release["checks"]["shaclWholeGraph"]["violationCount"] == 0
    assert replay["conforms"] and replay["violationCount"] == 0
    assert len(eval_results["checks"]) == 4
    assert all(item["conforms"] and item["violationCount"] == 0 for item in eval_results["checks"])


def test_sparql_reference_has_three_unique_reactions_and_stable_uris():
    import csv
    output = ROOT / "runs/wfkg_integrated_vertical_slice_v1"
    with (output / "integrated_replay_1/sparql_results.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 6
    assert len({row["reactionId"] for row in rows}) == 3
    assert {row["reactionId"] for row in rows} == {
        row["reactionId"] for row in csv.DictReader(
            (output / "integrated_replay_2/sparql_results.csv").open(encoding="utf-8", newline="")
        )
    }


def test_integrated_replays_are_deterministic_and_match_poc():
    import hashlib
    from rdflib.compare import isomorphic
    output = ROOT / "runs/wfkg_integrated_vertical_slice_v1"
    reference = RELEASE / "replay_1"
    for filename in ("reaction_results.csv", "sparql_results.csv", "staging_kg.ttl", "shacl_validation.json"):
        digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest(output / "integrated_replay_1" / filename) == digest(output / "integrated_replay_2" / filename)
        assert digest(output / "integrated_replay_1" / filename) == digest(reference / filename)
    assert isomorphic(
        Graph().parse(output / "integrated_replay_1/staging_kg.ttl"),
        Graph().parse(output / "integrated_replay_2/staging_kg.ttl"),
    )
