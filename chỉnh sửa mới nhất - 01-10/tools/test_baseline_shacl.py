"""Contract 1.0.4 synthetic structural regressions, NOT a demo pipeline or RQ evidence.
Run: py -3.13 -B tools/test_baseline_shacl.py
Dependencies: rdflib, pyshacl. Input artifacts are read-only.
"""
from pathlib import Path
import unittest

from rdflib import Graph, Literal, Namespace, RDF, SH, XSD
from pyshacl import validate

BASE = Path(__file__).resolve().parent.parent
W = Namespace('https://example.org/wfkg/v1#')
FIXTURE = '''
@prefix wfkg: <https://example.org/wfkg/v1#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
wfkg:source a wfkg:NewsSource ; wfkg:sourceId "s" ; wfkg:sourceName "SYNTHETIC_TEST_ONLY" ; wfkg:reliabilityScore 0.5 .
wfkg:article a wfkg:NewsArticle ; wfkg:articleId "a" ; wfkg:title "SYNTHETIC_TEST_ONLY" ;
 wfkg:url <urn:synthetic:structural-test> ; wfkg:publishedBy wfkg:source ; wfkg:reports wfkg:event ;
 wfkg:publishedAt "2026-08-26T14:16:00+07:00"^^xsd:dateTime ; wfkg:availableAt "2026-08-26T14:16:00+07:00"^^xsd:dateTime .
wfkg:evidence a wfkg:Evidence ; wfkg:evidenceId "ev" ; wfkg:evidenceText "SYNTHETIC_TEST_ONLY" ;
 wfkg:extractedFrom wfkg:article ; wfkg:supports wfkg:event ; wfkg:availableAt "2026-08-26T14:16:00+07:00"^^xsd:dateTime .
wfkg:event a wfkg:Event ; wfkg:eventId "e" ; wfkg:canonicalKey "synthetic|review" ; wfkg:eventType "EARNINGS" ;
 wfkg:description "SYNTHETIC_TEST_ONLY" ; wfkg:availableAt "2026-08-26T14:16:00+07:00"^^xsd:dateTime ;
 wfkg:effectiveTradingDate "2026-08-27"^^xsd:date ; wfkg:involvesCompany wfkg:company ; wfkg:hasEventStockCandidate wfkg:candidate .
wfkg:company a wfkg:Company ; wfkg:companyId "c" ; wfkg:companyType "NON_BANK" ; wfkg:fullName "synthetic" ; wfkg:hasStock wfkg:stock .
wfkg:stock a wfkg:Stock ; wfkg:stockId "st" ; wfkg:tickerSymbol "TEST" ; wfkg:exchange "FIXTURE" ; wfkg:hasMarketObservation wfkg:s0, wfkg:s1 .
wfkg:index a wfkg:MarketIndex ; wfkg:indexId "i" ; wfkg:indexCode "FIXTURE" ; wfkg:indexName "synthetic" ; wfkg:hasIndexObservation wfkg:i0, wfkg:i1 .
wfkg:candidate a wfkg:EventStockCandidate ; wfkg:candidateId "ca" ; wfkg:forEvent wfkg:event ; wfkg:candidateStock wfkg:stock ;
 wfkg:impactType "DIRECT"^^xsd:string ; wfkg:relationPath "DIRECT"^^xsd:string ; wfkg:candidateReason "synthetic" ; wfkg:expectedDirection "UNKNOWN"^^xsd:string ;
 wfkg:relationStrength 1.0 ; wfkg:sourceConfidence 0.5 ; wfkg:extractionConfidence 0.5 ; wfkg:linkingConfidence 0.5 ;
 wfkg:relationConfidence 0.5 ; wfkg:confidenceScore 0.5 ; wfkg:candidateScore 0.5 ; wfkg:candidateStatus "REACTION_READY"^^xsd:string ;
 wfkg:inferenceCutoff "2026-08-26T14:16:00+07:00"^^xsd:dateTime ; wfkg:generatedAt "2026-08-26T14:17:00+07:00"^^xsd:dateTime ;
 wfkg:availableAt "2026-08-26T14:17:00+07:00"^^xsd:dateTime ; wfkg:methodVersion "SYNTHETIC_TEST_ONLY" ; wfkg:hasReaction wfkg:reaction .
wfkg:reaction a wfkg:EventStockReaction ; wfkg:reactionId "r" ; wfkg:onCandidate wfkg:candidate ; wfkg:benchmarkIndex wfkg:index ;
 wfkg:derivedFromObservation wfkg:s0, wfkg:s1 ; wfkg:derivedFromIndexObservation wfkg:i0, wfkg:i1 ;
 wfkg:windowStartOffset 0 ; wfkg:windowEndOffset 0 ; wfkg:abnormalReturn 0.01 ; wfkg:cumulativeAbnormalReturn 0.01 ;
 wfkg:marketReactionDirection "POSITIVE"^^xsd:string ; wfkg:impactScore 0.1 ; wfkg:reactionWeight 0.05 ; wfkg:signedWeight 0.05 ;
 wfkg:methodVersion "SYNTHETIC_TEST_ONLY" ; wfkg:availableAt "2026-08-27T16:01:00+07:00"^^xsd:dateTime .
'''


def decimal(value):
    return Literal(str(value), datatype=XSD.decimal)


def set_value(graph, node, prop, value):
    graph.set((W[node], W[prop], value))


class BaselineShapeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shapes = Graph().parse(BASE / 'shapes_v1.0.ttl', format='turtle')
        cls.ontology = Graph().parse(BASE / 'ontology_v1.0.ttl', format='turtle')

    def setUp(self):
        self.graph = Graph().parse(data=FIXTURE, format='turtle')
        for name, kind, date, close, ret in (
            ('s0', 'MarketObservation', '2026-08-26', 100, 0),
            ('s1', 'MarketObservation', '2026-08-27', 102, '.02'),
            ('i0', 'MarketIndexObservation', '2026-08-26', 1000, 0),
            ('i1', 'MarketIndexObservation', '2026-08-27', 1010, '.01'),
        ):
            self.graph.add((W[name], RDF.type, W[kind]))
            fields = {
                'observationId': Literal(name, datatype=XSD.string),
                'tradingDate': Literal(date, datatype=XSD.date),
                'adjustedClose': decimal(close), 'returnValue': decimal(ret),
                'availableAt': Literal(date + 'T16:00:00+07:00', datatype=XSD.dateTime),
                'sourceReference': W.syntheticSource,
            }
            if kind == 'MarketObservation':
                fields['volume'] = decimal(100)
            for prop, value in fields.items():
                set_value(self.graph, name, prop, value)

    def check(self, expected, message=None):
        # No inference: missing inverse assertions must not be silently repaired.
        conforms, report, text = validate(
            self.graph, shacl_graph=self.shapes, ont_graph=self.ontology,
            inference='none', advanced=True,
        )
        self.assertEqual(bool(conforms), expected, text)
        if message:
            messages = '\n'.join(str(v) for v in report.objects(None, SH.resultMessage))
            self.assertIn(message, messages)

    def test_valid_control(self):
        self.check(True)

    def test_typed_reaction_ready_without_reaction(self):
        self.graph.remove((W.candidate, W.hasReaction, None))
        self.graph.remove((W.reaction, None, None))
        set_value(self.graph, 'candidate', 'candidateStatus', Literal('REACTION_READY', datatype=XSD.string))
        self.check(False, 'REACTION_READY requires an inverse-linked Reaction')

    def test_cutoff_later_than_event_is_rejected(self):
        # This is still before generatedAt: only exact baseline cutoff is violated.
        set_value(self.graph, 'candidate', 'inferenceCutoff', Literal('2026-08-26T14:16:30+07:00', datatype=XSD.dateTime))
        self.check(False, 'Baseline inferenceCutoff must equal Event.availableAt')

    def test_plain_reaction_ready_without_reaction(self):
        self.graph.remove((W.candidate, W.hasReaction, None))
        self.graph.remove((W.reaction, None, None))
        set_value(self.graph, 'candidate', 'candidateStatus', Literal('REACTION_READY'))
        self.check(False, 'REACTION_READY requires an inverse-linked Reaction')

    def test_plain_reaction_ready_with_reaction(self):
        set_value(self.graph, 'candidate', 'candidateStatus', Literal('REACTION_READY'))
        self.check(True)

    def test_unknown_lifecycle_status_is_rejected(self):
        self.graph.remove((W.candidate, W.hasReaction, None))
        self.graph.remove((W.reaction, None, None))
        for datatype in (None, XSD.string):
            with self.subTest(datatype=datatype):
                set_value(self.graph, 'candidate', 'candidateStatus', Literal('UNKNOWN_STATUS', datatype=datatype))
                self.check(False)

    def test_valid_nonready_statuses_without_reaction(self):
        self.graph.remove((W.candidate, W.hasReaction, None))
        self.graph.remove((W.reaction, None, None))
        for status in ('GENERATED', 'VALIDATED', 'REJECTED', 'PENDING_MARKET_WINDOW'):
            for datatype in (None, XSD.string):
                with self.subTest(status=status, datatype=datatype):
                    set_value(self.graph, 'candidate', 'candidateStatus', Literal(status, datatype=datatype))
                    self.check(True)

    def test_nonready_statuses_with_reaction_are_rejected(self):
        for status in ('GENERATED', 'VALIDATED', 'REJECTED', 'PENDING_MARKET_WINDOW'):
            for datatype in (None, XSD.string):
                with self.subTest(status=status, datatype=datatype):
                    set_value(self.graph, 'candidate', 'candidateStatus', Literal(status, datatype=datatype))
                    self.check(False, 'Candidate có Reaction phải ở trạng thái REACTION_READY')

    def test_cutoff_earlier_than_event_is_rejected(self):
        set_value(self.graph, 'candidate', 'inferenceCutoff', Literal('2026-08-26T14:15:00+07:00', datatype=XSD.dateTime))
        self.check(False, 'Baseline inferenceCutoff must equal Event.availableAt')

    def test_generated_at_equal_cutoff_is_valid(self):
        set_value(self.graph, 'candidate', 'generatedAt', self.graph.value(W.candidate, W.inferenceCutoff))
        self.check(True)

    def test_later_replay_generation_keeps_original_cutoff(self):
        # Deliberate replay time; input cutoff is the literal in FIXTURE, not derived here.
        replay_at = Literal('2026-08-28T10:00:00+07:00', datatype=XSD.dateTime)
        set_value(self.graph, 'candidate', 'generatedAt', replay_at)
        set_value(self.graph, 'candidate', 'availableAt', replay_at)
        set_value(self.graph, 'reaction', 'availableAt', Literal('2026-08-28T10:01:00+07:00', datatype=XSD.dateTime))
        self.check(True)

    def test_generated_at_before_cutoff_is_rejected(self):
        set_value(self.graph, 'candidate', 'generatedAt', Literal('2026-08-26T14:15:00+07:00', datatype=XSD.dateTime))
        self.check(False, 'generatedAt/availableAt must be ordered')

    def test_candidate_available_before_generation_is_rejected(self):
        set_value(self.graph, 'candidate', 'availableAt', Literal('2026-08-26T14:16:30+07:00', datatype=XSD.dateTime))
        self.check(False, 'generatedAt/availableAt must be ordered')

    def test_missing_linking_confidence(self):
        self.graph.remove((W.candidate, W.linkingConfidence, None))
        self.check(False)

    def test_wrong_candidate_score(self):
        set_value(self.graph, 'candidate', 'candidateScore', decimal('.9'))
        self.check(False, 'candidateScore must equal')

    def test_wrong_confidence(self):
        set_value(self.graph, 'candidate', 'confidenceScore', decimal('.9'))
        self.check(False, 'mean of its four frozen components')

    def test_missing_benchmark_close(self):
        self.graph.remove((W.i1, W.adjustedClose, None))
        self.check(False)

    def test_wrong_daily_return(self):
        set_value(self.graph, 's1', 'returnValue', decimal('.03'))
        self.check(False, 'Daily stock returnValue')

    def test_wrong_car(self):
        set_value(self.graph, 'reaction', 'cumulativeAbnormalReturn', decimal('.02'))
        self.check(False, 'sum of daily AR')

    def test_wrong_impact_even_when_weights_agree(self):
        for prop, value in [('impactScore', '.9'), ('reactionWeight', '.45'), ('signedWeight', '.45')]:
            set_value(self.graph, 'reaction', prop, decimal(value))
        self.check(False, 'impactScore must equal')

    def test_wrong_direction(self):
        set_value(self.graph, 'reaction', 'marketReactionDirection', Literal('NEGATIVE', datatype=XSD.string))
        self.check(False, 'marketReactionDirection must follow')

    def test_missing_event_candidate_inverse(self):
        self.graph.remove((W.event, W.hasEventStockCandidate, W.candidate))
        self.check(False, 'forEvent requires')

    def test_missing_candidate_event_inverse(self):
        self.graph.remove((W.candidate, W.forEvent, W.event))
        self.check(False, 'hasEventStockCandidate requires')

    def test_missing_candidate_reaction_inverse(self):
        self.graph.remove((W.candidate, W.hasReaction, W.reaction))
        self.check(False, 'onCandidate requires')

    def test_missing_reaction_candidate_inverse(self):
        self.graph.remove((W.reaction, W.onCandidate, W.candidate))
        self.check(False, 'hasReaction requires')

    def test_rejected_candidate_with_reverse_only_reaction(self):
        self.graph.remove((W.candidate, W.hasReaction, W.reaction))
        set_value(self.graph, 'candidate', 'candidateStatus', Literal('REJECTED', datatype=XSD.string))
        self.check(False, 'onCandidate requires')

    def test_event_self_link(self):
        self.graph.add((W.event, W.contradicts, W.event))
        self.check(False, 'must not self-reference')

    def test_early_reaction(self):
        set_value(self.graph, 'reaction', 'availableAt', Literal('2026-08-26T16:00:00+07:00', datatype=XSD.dateTime))
        self.check(False, 'must not precede')

    def set_market_case(self, close, ret, car, impact, direction, weight, signed):
        for node, prop, value in [('s1', 'adjustedClose', close), ('s1', 'returnValue', ret),
                                  ('reaction', 'abnormalReturn', car), ('reaction', 'cumulativeAbnormalReturn', car),
                                  ('reaction', 'impactScore', impact), ('reaction', 'reactionWeight', weight),
                                  ('reaction', 'signedWeight', signed)]:
            set_value(self.graph, node, prop, decimal(value))
        set_value(self.graph, 'reaction', 'marketReactionDirection', Literal(direction, datatype=XSD.string))

    def test_valid_negative_car(self):
        self.set_market_case(100, 0, '-.01', '.1', 'NEGATIVE', '.05', '-.05')
        self.check(True)

    def test_valid_zero_car(self):
        self.set_market_case(101, '.01', 0, 0, 'NEUTRAL', 0, 0)
        self.check(True)

    def test_valid_impact_saturation(self):
        self.set_market_case(121, '.21', '.20', 1, 'POSITIVE', '.5', '.5')
        self.check(True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
