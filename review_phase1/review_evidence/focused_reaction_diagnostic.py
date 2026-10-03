"""Synthetic, isolated Reaction-shape diagnostic; no input rewriting.
This is not full-bundle acceptance or factual market data.
"""
from pathlib import Path
from rdflib import Graph, Namespace, RDF, BNode, Literal, XSD
from pyshacl import validate

ROOT = Path(__file__).resolve().parents[2]
W = Namespace('https://example.org/wfkg/v1#')
D = Namespace('urn:synthetic-focused-reaction-review:')
all_shapes = Graph().parse(ROOT / 'chỉnh sửa mới nhất - 01-10/shapes_v1.0.ttl', format='turtle')
shape = Graph()
queue, seen = [W.EventStockReactionShape], set()
while queue:
    node = queue.pop()
    if node in seen:
        continue
    seen.add(node)
    for prop, value in all_shapes.predicate_objects(node):
        shape.add((node, prop, value))
        if isinstance(value, BNode):
            queue.append(value)


def literal(value, datatype):
    return Literal(value, datatype=datatype)


def add_values(graph, node, values):
    for prop, value in values:
        graph.add((node, prop, value))


g = Graph()
for node, cls in [(D.r, W.EventStockReaction), (D.c, W.EventStockCandidate),
                  (D.e, W.Event), (D.stock, W.Stock), (D.idx, W.MarketIndex)]:
    g.add((node, RDF.type, cls))
add_values(g, D.c, [(W.forEvent, D.e), (W.candidateStock, D.stock),
    (W.confidenceScore, literal('.5', XSD.decimal)),
    (W.relationStrength, literal('1', XSD.decimal)),
    (W.availableAt, literal('2026-08-26T14:16:00+07:00', XSD.dateTime))])
g.add((D.e, W.effectiveTradingDate, literal('2026-08-27', XSD.date)))
add_values(g, D.r, [(W.reactionId, literal('synthetic-r', XSD.string)),
    (W.onCandidate, D.c), (W.benchmarkIndex, D.idx),
    (W.windowStartOffset, literal(0, XSD.integer)),
    (W.windowEndOffset, literal(0, XSD.integer)),
    (W.abnormalReturn, literal('0', XSD.decimal)),
    (W.cumulativeAbnormalReturn, literal('0', XSD.decimal)),
    (W.marketReactionDirection, literal('NEUTRAL', XSD.string)),
    (W.impactScore, literal('0', XSD.decimal)),
    (W.reactionWeight, literal('0', XSD.decimal)),
    (W.signedWeight, literal('0', XSD.decimal)),
    (W.methodVersion, literal('synthetic-1.0.2', XSD.string)),
    (W.availableAt, literal('2026-08-27T16:17:00+07:00', XSD.dateTime))])
for label, cls, owner, owner_edge, reaction_edge in [
    ('stock', W.MarketObservation, D.stock, W.hasMarketObservation, W.derivedFromObservation),
    ('index', W.MarketIndexObservation, D.idx, W.hasIndexObservation, W.derivedFromIndexObservation)]:
    for day in ['2026-08-26', '2026-08-27']:
        node = D[label + day]
        add_values(g, node, [(RDF.type, cls), (W.tradingDate, literal(day, XSD.date)),
            (W.adjustedClose, literal('100', XSD.decimal)),
            (W.returnValue, literal('0', XSD.decimal)),
            (W.availableAt, literal(day + 'T15:10:00+07:00', XSD.dateTime))])
        g.add((owner, owner_edge, node))
        g.add((D.r, reaction_edge, node))


def check(label, data):
    conforms, _, text = validate(data, shacl_graph=shape, inference='none')
    print(label, 'conforms=', conforms)
    if not conforms:
        print(text)
    return conforms


assert check('POSITIVE_CONTROL_ISOLATED_REACTION_SHAPE', g)
mutation = Graph()
mutation += g
mutation.set((D.r, W.marketReactionDirection, literal('POSITIVE', XSD.string)))
assert check('WRONG_DIRECTION_CAR_ZERO', mutation)
mutation = Graph()
mutation += g
mutation.set((D.r, W.impactScore, literal('.9', XSD.decimal)))
mutation.set((D.r, W.reactionWeight, literal('.45', XSD.decimal)))
assert check('WRONG_IMPACT_SCORE_CAR_ZERO', mutation)
print('ENFORCEMENT_GAPS_REPRODUCED; isolated Reaction shape only, not full-bundle acceptance')
