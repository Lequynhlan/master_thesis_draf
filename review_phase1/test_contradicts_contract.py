"""D03 synthetic contract regression, not a Phase 2 extraction/metric runner.
Uses the exact submission ontology. All Events/labels here are synthetic.
"""
from datetime import datetime
from pathlib import Path
import unittest

from rdflib import Graph, Namespace, URIRef
from owlrl import DeductiveClosure, OWLRL_Semantics

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "chỉnh sửa mới nhất - 01-10"
WF = Namespace("https://example.org/wfkg/v1#")
SYN = Namespace("urn:synthetic:d03:")
RELATIONS = (WF.contradicts, WF.updates, WF.clarifies, WF.supersedes)


def pair(a, b):
    if a == b:
        raise ValueError("self-pair")
    return tuple(sorted((str(a), str(b))))


def projection(edges):
    return {pair(a, b) for a, p, b in edges if p == WF.contradicts}


def counts(predicted, gold, universe):
    if not predicted <= universe or not gold <= universe:
        raise ValueError("outside frozen task universe")
    return {"TP": len(predicted & gold), "FP": len(predicted - gold),
            "FN": len(gold - predicted), "TN": len(universe - (predicted | gold))}


def close(asserted):
    g = Graph().parse(BUNDLE / "ontology_v1.0.ttl")
    for edge in asserted:
        g.add(edge)
    DeductiveClosure(OWLRL_Semantics).expand(g)
    return {(a, p, b) for p in RELATIONS for a, b in g.subject_objects(p)}


def eligible(records, endpoint_available, cutoff):
    """Availability belongs to audit metadata; no new RDF predicates added."""
    if cutoff.tzinfo is None:
        raise ValueError("naive cutoff")
    result = set()
    for edge, evidence_available in records:
        a, _, b = edge
        times = (endpoint_available[a], endpoint_available[b], evidence_available)
        if any(t.tzinfo is None for t in times):
            raise ValueError("naive input time")
        if all(t <= cutoff for t in times):
            result.add(edge)
    return result


def orientation(a, b, chronology):
    """Original assertion chronology, not ingestion or fabricated occurrence time."""
    if a == b:
        raise ValueError("self-pair")
    ta, tb = chronology.get(a), chronology.get(b)
    if ta is not None and tb is not None and ta != tb:
        return ((a, b) if ta > tb else (b, a)), "CHRONOLOGY"
    return tuple(URIRef(x) for x in pair(a, b)), "TIED_OR_UNRESOLVED"


class ContradictsContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.A, cls.B, cls.C = SYN.A, SYN.B, SYN.C
        cls.direct = {(cls.B, WF.contradicts, cls.A)}
        cls.closed = close(cls.direct)

    def test_symmetry_and_asserted_derived_provenance(self):
        before = set(self.direct)
        self.assertIn((self.A, WF.contradicts, self.B), self.closed - self.direct)
        self.assertEqual(self.direct, before)
        self.assertEqual(projection(self.closed), {pair(self.A, self.B)})

    def test_two_directions_count_once_and_reverse_not_none(self):
        key = pair(self.A, self.B)
        gold, universe = {key}, {key, pair(self.A, self.C)}
        actual = counts(projection(self.closed), gold, universe)
        self.assertEqual(actual, {"TP": 1, "FP": 0, "FN": 0, "TN": 1})
        self.assertEqual(pair(self.B, self.A), key)
        self.assertNotIn(pair(self.B, self.A), universe - gold)

    def test_wrong_assertion_orientation_not_hidden_by_semantic_projection(self):
        reversed_direct = {(self.A, WF.contradicts, self.B)}
        self.assertNotEqual(reversed_direct, self.direct)
        self.assertEqual(projection(reversed_direct), projection(self.direct))
        # Stage-one orientation error still exists despite final semantic match.

    def test_correct_reasoning_from_wrong_input_is_still_wrong_final_graph(self):
        independently_adjudicated_gold = {pair(self.A, self.C)}
        universe = {pair(self.A, self.B), pair(self.A, self.C)}
        self.assertIn((self.A, WF.contradicts, self.B), self.closed)
        self.assertEqual(counts(projection(self.closed), independently_adjudicated_gold,
                                universe), {"TP": 0, "FP": 1, "FN": 1, "TN": 0})

    def test_not_transitive_no_self_and_no_reverse_directed(self):
        edges = {(self.A, WF.contradicts, self.B),
                 (self.B, WF.contradicts, self.C),
                 (self.B, WF.updates, self.A),
                 (self.B, WF.clarifies, self.A),
                 (self.B, WF.supersedes, self.A)}
        closed = close(edges)
        self.assertNotIn((self.A, WF.contradicts, self.C), closed)
        self.assertFalse(any(a == b for a, p, b in closed))
        for relation in (WF.updates, WF.clarifies, WF.supersedes):
            self.assertNotIn((self.A, relation, self.B), closed)
        self.assertIn((self.B, WF.clarifies, self.A), closed)
        self.assertIn(pair(self.A, self.B), projection(closed))

    def test_cutoff_blocks_late_relation_evidence_and_endpoint(self):
        at = datetime.fromisoformat
        cutoff = at("2026-08-26T16:00:00+07:00")
        early = at("2026-08-26T14:00:00+07:00")
        late = at("2026-08-27T14:00:00+07:00")
        availability = {self.A: early, self.B: early, self.C: late}
        records = [((self.B, WF.contradicts, self.A), late),
                   ((self.C, WF.contradicts, self.A), early)]
        frozen = eligible(records, availability, cutoff)
        self.assertEqual(frozen, set())
        self.assertEqual(projection(close(frozen)), set())
        later = eligible(records, availability, late)
        self.assertEqual(len(projection(close(later))), 2)
        self.assertEqual(frozen, set())
        # Equality at cutoff is eligible; naive timestamps are rejected.
        self.assertEqual(eligible([(next(iter(self.direct)), early)], availability,
                                  early), self.direct)
        with self.assertRaises(ValueError):
            eligible(records, availability, datetime(2026, 8, 26))

    def test_chronology_orientation_tie_owner_is_deterministic(self):
        at = datetime.fromisoformat
        newer = {self.A: at("2026-08-26T10:00:00+07:00"),
                 self.B: at("2026-08-27T10:00:00+07:00")}
        self.assertEqual(orientation(self.A, self.B, newer),
                         ((self.B, self.A), "CHRONOLOGY"))
        tied = {self.A: newer[self.A], self.B: newer[self.A]}
        self.assertEqual(orientation(self.B, self.A, tied),
                         ((self.A, self.B), "TIED_OR_UNRESOLVED"))
        self.assertEqual(orientation(self.B, self.A, {}),
                         ((self.A, self.B), "TIED_OR_UNRESOLVED"))

    def test_self_outside_universe_and_unjudged_not_silent_negatives(self):
        with self.assertRaises(ValueError):
            pair(self.A, self.A)
        with self.assertRaises(ValueError):
            counts({pair(self.A, self.C)}, set(), {pair(self.A, self.B)})
        # Only an explicitly adjudicated pair belongs in this task universe.
        self.assertNotIn(pair(self.B, self.C), {pair(self.A, self.B)})


if __name__ == "__main__":
    unittest.main(verbosity=2)
