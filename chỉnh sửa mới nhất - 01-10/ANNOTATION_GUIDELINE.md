# ANNOTATION_GUIDELINE.md

Version: 1.0.1

## Annotation units

Each annotation is tied to `articleId`, text offsets, annotator id, guideline version and timestamp. Never annotate only from a title or URL.

## Required labels

1. Evidence span: exact start/end offsets and supporting text.
2. Event type: one value from `EVENT_DICTIONARY.yaml`.
3. Event roles: required and optional roles with linked entity IDs.
4. Canonical Event ID and canonical key.
5. Entity links: Company, Stock, Industry, CorporateLeader and GovernmentOrganization.
6. Duplicate cluster membership; separately, directed Event relation: updates, clarifies, contradicts, supersedes or NONE. `updates` is the RDF-aligned label, not an eventType.
7. Event–Stock relevance: `0=irrelevant`, `1=limited but supported relevance`, `2=substantial supported relevance`. Annotate uncertainty separately as `RESOLVED` or `UNRESOLVED`; `impactType` and direct mention are separate fields.
8. Expected direction: POSITIVE, NEGATIVE, NEUTRAL or UNKNOWN.

## Decisions

- A sentence is Evidence only when it supports the Event claim; background context is not Evidence.
- A rumor remains a rumor event; do not convert it to a completed transaction.
- Two articles with no new business fact share a canonical Event and add Evidence/Article provenance.
- A clarification creates a new Event only when it adds a business-relevant clarification; otherwise it is duplicate coverage.
- Company and Stock are separate entities; a ticker mention does not replace the Company link.
- When evidence cannot support a relevance decision, leave relevance unset, set `UNRESOLVED` and record an adjudication note; never encode uncertainty as `1`. Direction may be UNKNOWN even when relevance is resolved at `2`.

## Relevance, identity and direction decision rules

- Relevance is judged at cutoff on an economic/business link supported by Evidence, never on candidateScore, CAR, realized return or directness alone. `0` means no supported material link (including incidental mentions); `1` means a supported but limited/peripheral channel; `2` means a substantial channel central to the issuer's operations, cash flows, assets, liabilities or governance. A direct incidental mention can be `0` or `1`; a substantial indirect credit exposure can be `2`.
- Both `1` and `2` are binary positives. Annotators record the channel and materiality justification, using the same rubric for all four impact types. If materiality cannot be adjudicated, keep UNRESOLVED rather than force a weaker label.
- UNRESOLVED items stay in the audit/coverage report and are excluded from sealed resolved gold and metric denominators, not recoded to zero. Report excluded counts by Event/impactType and reasons. Resolve them before sealing when possible; do not use method predictions to choose exclusions.
- Use dictionary `direction_rule` and `direction_policy` per Event–Stock. Missing/conflicting directional evidence => UNKNOWN. NEUTRAL means supported no material directional change, not uncertainty. Direction and relevance are independent; a highly relevant M&A rumor may have UNKNOWN direction.
- Follow dictionary `identity_policy` including optional-key missing rules and original `occurrence_id`. `positive_examples`/`negative_examples` mean examples/non-examples of the event type, not positive/negative market direction. Out-of-scope confusables are review labels only, not additional ontology classes.
- Substantive updates/clarifications keep different Event URIs and link newer to older. Duplicate coverage alone joins a cluster; a relation link never merges it. Directed relation labels may be multi-label when the evidence independently supports e.g. both clarifies and contradicts; NONE applies only when no relation is supported.

## Independent double-labeling

At least 25% of the gold set is labeled independently by two annotators. Agreement is reported separately for Evidence span overlap, event type macro-F1, entity-link exact match, relation type accuracy and Event–Stock relevance weighted kappa. Disagreements are adjudicated by a third reviewer; the adjudicated label becomes the final gold label and the original labels remain in the audit file.

## Quality gates

No gold item is final without an Evidence span, canonical Event ID, event type, required roles, entity IDs where applicable and annotator/version metadata. The final test set is sealed after adjudication and is not used to tune extraction, linking, score weights or event windows.
