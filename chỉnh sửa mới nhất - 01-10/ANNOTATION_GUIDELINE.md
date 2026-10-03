# ANNOTATION_GUIDELINE.md

Version: 1.0.4

## Annotation units

Each annotation is tied to `articleId`, text offsets, annotator id, guideline version and timestamp. Never annotate only from a title or URL.

## Required labels

1. Evidence span: exact start/end offsets and supporting text.
2. Event type: one value from `EVENT_DICTIONARY.yaml`.
3. Event roles: required and optional roles with linked entity IDs.
4. Canonical Event ID and canonical key.
5. Entity links: Company, Stock, Industry, CorporateLeader and GovernmentOrganization.
6. Duplicate cluster membership; separately, direct asserted Event-relation labels: updates, clarifies, contradicts, supersedes or NONE. Updates/clarifies/supersedes are directed; contradicts is symmetric, with a chronological storage convention only. `updates` is the RDF-aligned label, not an eventType. Keep assertion provenance separate from OWL-inferred edges.
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
- Substantive updates/clarifications keep different Event URIs and link newer to older. Duplicate coverage alone joins a cluster; a relation link never merges it. Direct asserted labels may be multi-label when Evidence independently supports e.g. both clarifies and contradicts. NONE is exclusive within its declared view/universe, not semantic absence in every graph view.
- Annotate contradicts only when the claims concern the same business context and cannot both hold as stated; changed business state or wording alone is not contradiction. Keep both Events/Evidence; newer does not automatically mean true. Store the direct assertion newer-to-older using original Evidence chronology. Tied/unresolved chronology uses ascending canonical Event URI and a recorded flag, not fabricated dates. Other directed labels require supported direction; unresolved items are adjudicated or excluded with reasons before sealing.
- Record endpoint IDs, supporting Evidence IDs/availability, assertion orientation and adjudication metadata. Freeze identical cutoffs/gold Event IDs across both stages; later Evidence never alters an earlier snapshot. Independently adjudicate semantic contradiction pairs without predictions. Their unordered key is the lexicographically sorted pair of canonical Event URI strings; self-pairs are invalid. Reverse OWL edges are not new independent annotations.

## Frozen baseline and normalization instructions

- Annotate baseline relevance/direction and eligible paths at exactly `inferenceCutoff = Event.availableAt` (earliest supporting Evidence availability), never a later extraction/run time. Record availability/proxy assumptions and immutable snapshot ID; a later `generatedAt` records offline replay, not live prediction. Use the first exchange session whose open is strictly after availability for day 0. At-open/intraday news goes to the next session. Record calendar/exchange/version; do not infer sessions from weekdays.
- Check LeadershipPosition/SubsidiaryRelation/IndexMembership validity at the Asia/Ho_Chi_Minh cutoff date, inclusively, not day 0. For IndustryExposure, use YEAR records, periodEnd no later than cutoff, inclusive 365-day staleness and newest periodEnd / newest availableAt / ascending URI selection. Record the reporting scope and chosen record. Missing/invalid mappings or relations suppress the path; do not manufacture an edge with a confidence fallback.
- Identify complete Evidence assignments independently: every required dictionary role must be supported by that one assignment. Record all original role/link decisions, scores, calibration/fallback flags and Evidence URI. Select the highest assignment score (minimum per-role scores when needed), then ascending Evidence URI for ties. Freeze it once for the Event. Do not combine partial assignments, maximize entity linking over alternative Evidence, or reselect an assignment to rescue an optional route entry. A missing predicted complete assignment at earliest cutoff means `NO_COMPLETE_EVIDENCE_AT_CUTOFF`: keep staging/coverage with no Candidate, not delayed cutoff or a forced negative gold label. Independently resolved gold Events remain in RQ2/RQ3 with empty method rankings and missed positives; only independently adjudicated unresolved identity/relevance follows the common exclusion rules. Annotate binary support for each of the four routes on every resolved Event–Stock pair, including common negatives, before predictions; overall relevance remains a separate 0/1/2 label under EVALUATION_PROTOCOL.md.
- Use SCORING_SPEC.md's four-route input table. All required Event entity roles and any route-entry entity use the chosen Evidence assignment. Propagated parent, leadership-company and exposure-Bank endpoints use the selected eligible typed registry/fact mapping; they need not be directly mentioned in that Evidence. Freeze terminal Company–Stock mapping provenance as well. Curated verified mappings use `1.0`; present evidenced automatic uncalibrated decisions/path facts use the declared `0.5`; absent links never receive a fallback. Event–Company/Industry/Leader support uses the original chosen complete assignment score, not a separately maximized linker score. Do not label heuristic relation/aggregate confidence as calibrated probability or claim component independence.
- Normalize every canonical-key field using the dictionary's versioned `key_normalization`/`normalization_vocabulary`. Keep raw span/value, role, normalized token or typed registry ID, mapping version and qualifier context in the annotation audit. Controlled synonyms are role-specific; no fuzzy guessing, stemming or translation to invent tokens. Unknown/unmapped/ambiguous values => HOLD_FOR_REVIEW and no curated key. Resolve identity from evidenced registry/context, never article dates. Missing optional key fields still follow MATCH_EXISTING_ELSE_HOLD; a present but unmapped optional value is not silently dropped.
- Reporting periods use `YEAR2026`, `QUARTER2026-Q1`, `HALF2026-H1`, `MONTH2026-01` or the dictionary's exact evidenced interval grammar, with stated scope/basis qualifiers retained in fixed order. Never infer a year from publication date or merge consolidated/standalone or original/restated contexts. Preserve distinctions such as cash/stock dividend, metric identity, capital instrument and leadership title through the declared role tokens; enum/action equivalence never implies equal market direction.
- Reprints add provenance to the same Event but do not revise its earliest availability, cutoff, selected assignment or baseline day 0. Late Evidence for the same assertion is a separately versioned retrospective reconstruction outside baseline, not a delayed baseline prediction; genuinely new substantive assertions get distinct Event URIs and their own earliest availability/day 0. `[0,0]`, `[0,+1]`, `[0,+3]` are daily post-availability analyses; `[-1,+1]` is retrospective robustness. Prices/CAR from any window never determine gold relevance, expected direction or Candidate ranking.

## Independent double-labeling and agreement

At least 25% of the gold set is labeled independently by two annotators. Compute agreement before adjudication, report support and confusion tables, then adjudicate disagreements with a third reviewer. Preserve both original labels and the adjudicated label in the audit file.

- Evidence spans use half-open character offsets `[start,end)`. For each article, compare the union of covered character positions and report micro precision, recall and F1; also report exact-boundary span-match F1.
- Event type and expected direction are nominal labels: report Cohen's kappa, raw agreement and confusion matrices. Event type macro-F1 is also reported to expose class imbalance.
- Entity links report exact match by role. Duplicate canonicalization reports pairwise precision/recall/F1 on unordered mention pairs, plus false-merge and missed-merge counts.
- Direct asserted Event relations are multi-label on a frozen ordered pair universe: per-label precision/recall/F1, micro/macro-F1 and exact-set accuracy, with exclusive NONE in that asserted view. Final semantic contradicts agreement uses a separate frozen unordered pair universe and binary CONTRADICTS/NONE labels, deduplicating reverse pairs. Both annotators use identical universes, orientation rules and adjudicated sampled negatives; unjudged is not NONE. Follow the two-stage EVALUATION_PROTOCOL.md contract; do not pool ordered/unordered sample counts.
- Event–Stock relevance uses quadratic weighted Cohen's kappa on resolved ordinal labels 0/1/2, with weight `w(i,j)=1-((i-j)/2)^2`. Report agreement on `RESOLVED`/`UNRESOLVED` separately; never convert `UNRESOLVED` to 0. Report relevance agreement by impactType as well as overall.
- If kappa is undefined because a label has no variation, report `N/A`, the raw agreement and the full label distribution; do not replace it with zero.

## Quality gates

No gold item is final without an Evidence span, canonical Event ID, event type, required roles, entity IDs where applicable and annotator/version metadata. The final test set is sealed after adjudication and is not used to tune extraction, linking, score weights or event windows.
