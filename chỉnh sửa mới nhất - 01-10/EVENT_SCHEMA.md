# EVENT_SCHEMA.md

Document version: 1.1.0
Active scoring method: `WFKG-SCORE-V1`
Structural schema: existing `ontology_v1.0.ttl` / `shapes_v1.0.ttl`; no new classes or properties.
Status: algorithm/specification contract for Phase 2; not evidence of pipeline execution. Legacy 1.0.4 numerical policies are inactive for V1. Reports/diagrams/demos may still describe legacy policies; see PHASE1_ACCEPTANCE.md.

## Canonical namespace

`wfkg: = https://example.org/wfkg/v1#`

## Curated flow

```text
NewsArticle -> Evidence -> Event -> EventStockCandidate -> Market observations -> EventStockReaction
```

`EventStockCandidate` is an inference-time relation. `EventStockReaction` is a post-window observation and never creates or changes a historical Candidate.

## Cardinality contract

- `NewsArticle reports Event`: `0..*` in raw/staging. The supplied SHACL shape is staging-safe and does not enforce this link. The curated inference gate, implemented outside generic SHACL, requires at least one Event before an article enters the inference graph.
- `Evidence extractedFrom NewsArticle`: exactly `1`.
- `Evidence supports Event`: `1..*`.
- `Event hasEventStockCandidate`: `0..*`.
- `Candidate forEvent Event`: exactly `1`.
- `Candidate candidateStock Stock`: exactly `1`.
- `Candidate hasReaction Reaction`: `0..*`.
- `Reaction onCandidate Candidate`: exactly `1`.
- `Reaction derivedFromObservation MarketObservation`: `1..*`.
- `Reaction derivedFromIndexObservation MarketIndexObservation`: `1..*`.

## Baseline impactType and relationPath contract

`relationPath` is a stable route code and must equal `impactType` in the Phase 2 V1 baseline. Allowed pairs are `DIRECT`, `INDIRECT_INDUSTRY`, `INDIRECT_SUBSIDIARY` and `INDIRECT_LEADERSHIP`. Their graph paths are:

- `DIRECT`: `Event → Company → Stock`.
- `INDIRECT_INDUSTRY`: `Event → Industry ← IndustryExposure ← Bank → Stock`; this path creates candidates only for a Bank with a selected eligible exposure, not every stock in the industry.
- `INDIRECT_SUBSIDIARY`: `Event → subsidiary Company`; a `SubsidiaryRelation` must identify that subsidiary and a parent Company, and the parent must own the Candidate Stock. Canonical RDF ownership is `parent Company —hasSubsidiaryRelation→ SubsidiaryRelation`; the relation node links back with `parentCompany` and identifies the child with `subsidiaryCompany`. The child does not own `hasSubsidiaryRelation` in this baseline.
- `INDIRECT_LEADERSHIP`: `Event → CorporateLeader → LeadershipPosition → Company → Stock`.

SHACL checks the route code and required graph links; conformance alone does not establish historical eligibility or the numerical method. The curated inference gate additionally applies cutoff availability, identity/version selection and validity rules; IndustryExposure uses the reporting-period selection below. SCORING_SPEC.md is the authoritative producer/aggregation contract for WFKG-SCORE-V1:

| Component | Active V1 rule |
| --- | --- |
| sourceConfidence S | Fixed 0.5, independent of source/evidence multiplicity |
| extractionConfidence A | Selected complete assignment score: min of required trained neural decisions and supported deterministic role conventions; no extraction fallback |
| linkingConfidence L | 1.0 for exact, typed, unique registry resolution on all required route links; ambiguous/fuzzy-only/absent links HOLD or suppress |
| relationConfidence R | Min of required edge supports: AUTOMATIC_EVIDENCED=0.5, CURATED_STRUCTURED=1.0; missing/ineligible fact suppresses path |
| relationStrength T | 1.0 for all four eligible routes; economic strength is not measured in V1 |

All dictionary-required entity links/identity are resolved and checked per complete assignment before Evidence selection; an ambiguous required link excludes that assignment with a reason. The highest-scoring eligible complete assignment is then selected once. Optional route-entry links and propagated route endpoints are checked only after selection; failure suppresses that route without trying another Evidence. All required Event entities and optional route-entry entities use the same selected complete Evidence assignment. Propagated parent/Bank/position-company endpoints use eligible registry/fact mappings, not fabricated direct mentions. Event-entry automatic relation support is 0.5, not A or L. No score threshold or low-score fallback rescues failed gates. Components are conventions/task scores, not calibrated correctness probabilities. Freeze scores and their input/provenance/versions before Reaction.

Legacy 1.0.4 DIRECT=1.0/INDIRECT=0.5 and exposure-strength policies are not active V1 rules. The supervisor-requested industry exposure comparison remains a separately versioned Phase 2 research experiment after automatic slice acceptance, not a prerequisite of the first integration run. Define and freeze its protocol/config before evaluation; never mix it into a V1 ranking.

## Scoring timing

```text
candidateScore = confidenceScore * relationStrength
reactionWeight = impactScore * confidenceScore * relationStrength
```

`candidateScore` is allowed at `inferenceCutoff = Event.availableAt` for baseline prospective-information ranking. `reactionWeight` is allowed only after the complete event window and all required observations are available. Candidate inputs satisfy input.availableAt <= inferenceCutoff; Reaction observations satisfy observation.availableAt <= Reaction.availableAt, not <= inferenceCutoff. The canonical property is `reactionWeight`; the legacy bare property `weight` is not part of the active contract.

## Structural validation boundary and V1 method gates

The graph submitted for baseline validation must contain both directions of hasEventStockCandidate/forEvent and hasReaction/onCandidate, either explicitly materialized by the writer or already derived before submission with recorded inference provenance. SHACL does not repair missing inverse links; tests run with inference=none. Every linked Reaction requires REACTION_READY on its exact Candidate, including a Reaction discoverable only through onCandidate. A REJECTED Candidate cannot have a Reaction. Incomplete/mismatched inverse assertions fail validation rather than disappearing from lifecycle queries.

SHACL validates impactScore=min(1,abs(CAR)/0.10), marketReactionDirection from the exact sign of CAR with epsilon=0, and the existing weight equations. Calendar/session coverage, daily effectiveTradingDate, dictionary membership, model/role score provenance and declared calibration status, frozen Evidence aggregation, V1 strength/origin assignment and immutable snapshots still require curated pipeline gates. Uncalibrated trained task scores are allowed in V1; calibration is not a slice prerequisite. Synthetic regression tests in tools/test_baseline_shacl.py exercise structural rules only; they do not recreate historical report figures or demonstrate NLP/RQ performance.

## AR/CAR source and provenance contract (unchanged structural rules)

- `adjustedClose` is the authoritative input for both `MarketObservation` and `MarketIndexObservation`; each value must be positive and retain its `sourceReference`. `returnValue` is a derived/cache field, never the sole source for recomputing a reaction.
- Window offsets are exchange-session offsets relative to `Event.effectiveTradingDate` (`t0`). For a window `[a,b]`, the Reaction must link one Stock observation and one benchmark observation for every session `t_(a-1), t_a, ..., t_b`. The predecessor `t_(a-1)` supplies the denominator for the first in-window return.
- Linked Stock observations must belong to `Candidate.candidateStock`; linked index observations must belong to `Reaction.benchmarkIndex`. The two sets must have the same unique `tradingDate` values, with exactly one selected observation per asset and session.
- All supported windows contain offset `0`. `EventStockReaction.abnormalReturn` stores `AR(i,0)`; `cumulativeAbnormalReturn` stores `sum(AR(i,t), t=a..b)`. Each daily AR is recomputed from adjusted closes, not copied from a cached return.
- For each in-window session `t`, recompute `R(i,t)=adjustedClose(i,t)/adjustedClose(i,t-1)-1` and the corresponding benchmark return from the immediately preceding exchange session, then `AR(i,t)=R(i,t)-R(m,t)`. Validate cached `returnValue`, `abnormalReturn`, and `cumulativeAbnormalReturn` against these recomputations with absolute tolerance `1e-9`.
- SHACL validates observation ownership, date pairing, unique-date counts, required positive adjusted closes, daily return arithmetic, and the CAR sum. A calendar-aware validator must additionally compare the linked dates with the exact session sequence from the frozen exchange calendar; SHACL alone cannot infer holidays or session offsets from dates.
- The run manifest records market-data provider/dataset snapshot, adjusted-price and corporate-action adjustment convention, benchmark URI, exchange, and calendar identifier/version/hash so the close series can be reproduced.

## V1 source baseline

All participating NewsSource records use reliabilityScore=0.5 and every V1 Candidate stores sourceConfidence=0.5. This is a constant experimental control, not measured equality of real source quality. Supporting-source multiplicity does not increase it. Source-specific measurement/calibration requires a separately versioned method/configuration and compatible validation, never rewriting historical Candidates.

## Temporal/provenance rules

- `availableAt <= inferenceCutoff` for Candidate inputs.
- `effectiveTradingDate` uses the availability/calendar rule below, not the repost's publication day.
- Both `MarketObservation` and `MarketIndexObservation` require `adjustedClose > 0`; `returnValue`, `availableAt` and `sourceReference` are mandatory. `returnValue` may be negative and is only a derived/cache field; `adjustedClose` is authoritative for recomputation. See the AR/CAR contract above.
- Reaction provenance contains exactly the predecessor session plus every session in the configured event window for both the Candidate stock and benchmark; the calendar-aware validator checks the exact session dates.
- `LeadershipPosition`, `SubsidiaryRelation`, `IndexMembership`: select the latest available version under the business-key contract below **before** testing validity. `validFrom` is required, `validTo` optional; dates are inclusive. Missing start is ineligible, not an unbounded tenure.
- `IndustryExposure` uses reporting-period selection below; `validFrom`/`validTo` are optional metadata, not the baseline eligibility filter.

## Frozen cutoff and daily calendar contract (V1; temporal rules retained)

- Use timezone-aware instants; compare instants in UTC and derive dates in `Asia/Ho_Chi_Minh`. A naive timestamp is rejected. Equality at cutoff is eligible (`<=`).
- Event availability is the earliest supporting Evidence availability; Evidence availability must be no earlier than both its Article's `publishedAt` and actual first system availability. Do not invent crawler latency. Missing acquisition timestamps require a declared publication-time proxy dataset, not a claim of observed historical availability.
- For a frozen Event snapshot let `a = Event.availableAt`. Select the first exchange session whose opening instant is **strictly later** than `a`: `a < session.open`. Thus before open uses that session; exactly at open, intraday or after close uses the next session; weekends/holidays use the next scheduled opening. Calendar/version, exchange and session opening times belong in the run manifest; do not use weekday arithmetic. Missing calendar coverage blocks calculation.
- Example with a declared 09:00 +07 opening: 26/08/2026 08:59 uses 26/08; 09:00 and 14:16 use 27/08 when that is the next calendar session. Both demo Events available after open on 26/08 use 27/08.
- Baseline locks `inferenceCutoff = Event.availableAt` exactly, not an arbitrary later run time. Every Evidence, reference mapping and temporal fact used is available no later than that instant. `generatedAt` may be later for an offline replay; it is the existing Candidate execution/audit field, not permission to use later information. Describe this as replayed prospective-information ranking, not verified live prediction. Freeze input IDs/versions, the selected complete Evidence assignment, entity/route decisions, calendar decision and all original scores in the immutable cutoff snapshot.
- If the earliest availability has no complete eligible Evidence assignment, retain the extraction record in staging/coverage with `NO_COMPLETE_EVIDENCE_AT_CUTOFF` and produce no baseline Candidate. This algorithmic miss is not an evaluation exclusion: independently resolved gold Events remain in the common RQ2/RQ3 universe with an empty ranking, so missed gold positives count as false negatives. Only independently adjudicated unresolved identity/relevance or predeclared source-frame exclusions may remove a gold item, identically for all methods. Do not silently delay cutoff until a complete assignment arrives, combine incomplete assignments, or change earliest Event availability. Late Evidence/reprints may add current provenance but cannot enrich the historical snapshot. A later-evidence reconstruction for the same assertion is a separately versioned retrospective analysis outside baseline, explicitly retaining the original Event availability; it is not a new baseline Event or a delayed prediction. A genuinely new substantive assertion receives a distinct Event URI, its own earliest supporting availability and recomputed effectiveTradingDate. Newly discovered earlier Evidence likewise requires separately versioned correction/reconstruction outside the frozen baseline, never mutation of its cutoff or day 0.
- Historical lifecycle queries read an immutable graph snapshot or timestamped status log. Filtering a current mutable `candidateStatus` by observation dates is not historical reconstruction.
- A Reaction requires completed window and complete Stock + benchmark prices for each session including the predecessor. Windows `[0,0]`, `[0,+1]`, `[0,+3]` are post-availability daily windows under the strict-opening rule; `[-1,+1]` is a retrospective robustness window, not wholly post-event. Its negative session prices never enter Candidate ranking. Temporal facts are selected at `date(inferenceCutoff)`, not at day 0, generation time or the window end: a future-effective `validFrom` remains ineligible even if it begins before day 0. All dates here use Asia/Ho_Chi_Minh.

## Temporal relation version selection (before validity)

Use immutable version nodes and a frozen identity registry; these are existing relation classes, not new ontology properties. Business keys are:

- LeadershipPosition: `(positionHolder, positionAtCompany, normalized positionTitle, original validFrom)`.
- SubsidiaryRelation: `(subsidiaryCompany, parentCompany, original validFrom)`.
- IndexMembership: `(memberStock, memberIndex, original validFrom)`.

`original validFrom` identifies the evidenced tenure/membership occurrence; an identity correction uses an explicit version-registry mapping to that same business key. Do not let a corrected start/entity/title create a second active copy. Distinct evidenced tenures have distinct keys. Unresolved identity or missing required key fields remains staging and cannot supply a path.

For each key, consider only versions with `availableAt <= inferenceCutoff`; order by `availableAt DESC, STR(URI) ASC` (case-sensitive Unicode codepoint order), then select one. Only after selection require `validFrom <= date(cutoff)` and either no `validTo` or `date(cutoff) <= validTo`. A selected ended/future-effective/invalid version suppresses the relation; never fall back to an older open-ended version. Retain the key, eligible version IDs, selected URI and validity decision in the immutable audit record. Missing/mismatched endpoint ownership also suppresses the route. Generic SHACL checks node structure, not this registry-aware version-selection algorithm.

IndustryExposure follows the separate reporting-period rule below, not this tenure filter. Query examples must use a graph already partitioned/prefiltered to the frozen reporting scope; consolidated and standalone records never compete for the same selected exposure.

## IndustryExposure selection (separate from validity)

1. Fix `(exposureBank, exposureIndustry, periodType)` and the reporting scope (e.g. consolidated vs standalone) in the dataset/method manifest. Baseline fixes `periodType=YEAR`; alternative period types are separately named variants, never mixed into one latest-period contest. Reporting scope is ingestion metadata, not a new ontology property/class.
2. Require `availableAt <= cutoff` and `periodEnd <= date(cutoff)`; require `0 <= (date(cutoff) - periodEnd).days <= 365` (inclusive calendar-day staleness).
3. Sort eligible records by `periodEnd DESC, availableAt DESC, STR(URI) ASC` and take one per group. URI comparison is ascending Unicode codepoint order, case-sensitive, no locale collation. Do not require `validFrom` or filter on `validTo` for this reporting-period path.
4. No eligible record means no INDUSTRY path (not a fabricated 0.5 exposure). Missing `exposureStrength` remains raw/staging; curated `IndustryExposureShape` requires it. V1 constant strength still requires a structurally valid exposure with provenance/availability; this does not mean every exposure was manually curated. Support origin remains 0.5 or 1.0 under SCORING_SPEC.md; a constant does not repair missing facts.

## Canonical identity and dictionary roles

The dictionary's roles (including `occurrence_id`) and versioned normalization vocabulary are extraction/identity-registry fields, not new RDF properties or classes. Preserve the 22 ontology classes, eventType names, taxonomy and namespace. Normalize every key field using `key_normalization` and `normalization_vocabulary` before constructing `canonicalKey`; follow `identity_policy` for every entry. Controlled actions/metrics/instruments/titles require an explicit role-specific token/synonym match; periods use the deterministic grammar and preserve stated qualifiers. Entity/context/reference values require typed registry resolution, dates require evidenced ISO dates, and occurrence IDs retain original business-assertion identity. Unmapped/ambiguous values remain HOLD_FOR_REVIEW without a curated key; normalization never guesses or turns missing into a wildcard.

Article publication/availability dates never distinguish business occurrences. A duplicate reprint attaches new Article/Evidence provenance to the same Event URI, including when posted on another day. `occurrence_id` identifies the original business assertion, not each article. Required identity missing => HOLD_FOR_REVIEW. Optional key field missing => MATCH_EXISTING_ELSE_HOLD: reuse an existing key only when positive same-occurrence evidence and all known roles agree; otherwise keep staging without minting a curated key. Never fill missing dates with publication/availability, empty strings or shared UNKNOWN sentinels. Missing non-key optional roles may simply be omitted.

New material facts create distinct Events. `updates`, `clarifies` and `supersedes` are directed from newer assertion to older assertion. `contradicts` means two supported assertions are incompatible in the same business context; it is logically symmetric, as declared in the ontology, and does not identify which assertion is true. For provenance, store its direct assertion newer-to-older; this storage convention does not remove logical symmetry. Establish assertion chronology from original supporting Evidence, not ingestion order or an invented occurrence date. When chronology is tied or cannot be resolved, store `contradicts` using ascending canonical Event URI as a deterministic orientation, flag the tie/unresolved chronology in the audit record, and do not interpret that orientation as temporal precedence. A relation never unions duplicate clusters, even for the same company/period/deal. Mere wording changes or repeated statements are duplicates, not updates. A later correction to identity metadata alone preserves URI with alias history; a substantive earnings restatement has a new assertion/occurrence ID and an `updates`/`supersedes` relation. An unspecified occurrence time requires original-document identity or adjudication; it is not replaced by the article date.

## Extraction adapter and original-text Evidence producer

The reference adapter is `V1-SENTENCE-TRIGGER-BIO`, pinned by adapterVersion in each run. It is a trained PhoBERT ED/EAE adapter, not an article classifier or a rubric assessor. Freeze exact decoded text/hash before preprocessing. An automatic, versioned sentence splitter produces a non-overlapping sentence table `(sentenceId,start,end)` on original Unicode-codepoint half-open offsets, preserving source characters. Record splitter implementation/version/config, abbreviation rules, output table/hash and segmentation/subword offset mapping; no gold boundaries or IDs are supplied to the splitter/inference. Leading/trailing separator whitespace is excluded by the declared splitter rule; never reconstruct Evidence by joining token strings.

1. ED decodes supported event triggers within a sentence, permitting zero/multiple instances. Each selected trigger has an instance ID and a selected BIO-label score for every token in its span; `triggerScore=min(selected token scores)`. Invalid BIO/offsets reject the instance. The EventType head assigns one supported type to that instance using its selected-label score. Distinct triggers remain distinct predictions until identity resolution; same-type mentions are not automatically merged.
2. Evidence anchor is the complete frozen sentence containing that trigger: exact `[sentence.start,sentence.end)` on original text. The EAE BIO decoder is conditioned on the selected event instance/trigger/type, not shared blindly across Events in the sentence. The entire Evidence sentence, including trigger and all required span/literal supports, must fit without truncation within one model-input window including its reserved special/conditioning tokens. Freeze max input length, reserved-token accounting, window start/stride and overflow policy in the adapter manifest. A support subset fitting a truncated sentence does not make that assignment eligible. Deterministic evidenced identity resolution retains its supporting sentence/registry provenance; it cannot invent a missing assertion.
3. Overlapping windows retain separate raw assignment IDs and scores. No fragments/roles are merged across windows or sentences. Raw outputs are not directly the RQ1 inventory: group predictions by exact `(articleId,sentenceStart,sentenceEnd,triggerStart,triggerEnd,eventType)`, retain all raw assignments and choose one representative before gold is opened. If the group has complete required-decision outputs, choose the greatest assignmentScore then ascending assignmentId. If every output lacks a required role/value, retain the ascending assignmentId representative as an incomplete predicted mention with missing-field reasons and no fabricated assignmentScore. For every emitted neural decision its score must be finite and present; missing/invalid scores are producer errors, not a missing-role fallback. Representative selection checks offset/BIO/model-output completeness, not downstream registry success: deterministic identity/link failures remain predicted errors and must not erase the mention. Emit one model mention per exact instance key and one Evidence item per unique `(articleId,sentenceStart,sentenceEnd)`; same-span alternative types remain separate predictions. This removes window copies only, not distinct triggers, wrong types or partially overlapping spans; remaining duplicate emitted items are FP under the evaluator. Freeze inventory representative and raw group membership; Candidate selection separately uses cutoff-eligible complete assignments and never changes RQ1 inventory to hide link/identity failures. Trigger detection/type/required roles and any additional mandatory neural association decisions enter the assignment min under SCORING_SPEC.md. Optional route entries need their own explicit attachment/support even though they do not enter A.
4. Sentence longer than model coverage, unsupported cross-sentence arguments or missing identity/required role remain staging with reason; do not silently truncate support, broaden Evidence after seeing gold, or exclude independently valid gold Events. Alternative multi-sentence/span adapters require their own frozen manifest/version/score accessors and separately labeled evaluation; they are not the reference automatic slice adapter.

The splitter sentence table defines candidate anchors, not gold relevance. Annotators independently decide which whole sentence supports each Event under ANNOTATION_GUIDELINE.md; trigger presence/text alignment alone is not proof of correct Event/argument attachment.

## Candidate expectedDirection producer

`expectedDirection` belongs to each EventStockCandidate, not one article-wide sentiment label. The producer uses the frozen Dictionary direction_rule/direction_policy, selected Evidence assignment's evidenced roles/comparisons and eligible route facts/target context, without gold labels, CAR or future prices. Record rule ID/version, target Stock, input role/fact IDs, supporting spans and decision reason in the sidecar. Apply a POSITIVE/NEGATIVE/NEUTRAL rule only when all declared antecedents and target-specific channel are supported. No matching rule, missing comparison, conflicting signals or unsupported propagation to an indirect target => UNKNOWN. NEUTRAL requires explicit supported no-material-directional-change semantics, not missing data. Do not map EARNINGS/DIVIDEND or route type to a fixed sign. Rule-based direction is allowed; no new direction classifier or calibration is required for the slice.

## Candidate lifecycle and window-task contract

Candidate scoring inputs/values stay immutable. Lifecycle evolves only through versioned snapshots or timestamped status logs; historical queries must not read current status as past status. Invalid Event/link/route outputs remain staging/HOLD and are not rescued by lifecycle states.

| Candidate state | Entry condition and allowed next step |
| --- | --- |
| GENERATED | Eligible assignment/route and finite V1 score snapshot produced; writer/validation pending. Next VALIDATED or REJECTED. |
| VALIDATED | Structural SHACL plus method/cutoff/identity/route gates pass. Next PENDING_MARKET_WINDOW or, atomically with at least one valid completed Reaction, REACTION_READY. |
| REJECTED | Candidate writer/validation failure recorded with reason; no Reaction. Correction creates a separate corrected snapshot/run, not mutation of the scored historical record. |
| PENDING_MARKET_WINDOW | No completed valid Reaction yet; waiting for closing/availability or complete market inputs. Missing prices/calendar/benchmark do not mean irrelevant or delete ranking coverage. |
| REACTION_READY | At least one validated complete configured-window Reaction exists, with both hasReaction/onCandidate links. Other windows may still be pending/blocked. Never publish REACTION_READY without a linked Reaction. |

For every configured window, a separate sidecar task keyed by `(candidateId,benchmarkId,window,marketSnapshot,configVersion)` records WAITING_WINDOW, WAITING_INPUTS, INVALID_INPUTS or COMPLETE, required sessions, reasons and observation IDs. COMPLETE requires window closure, every required observation available, exact calendar coverage and independent arithmetic checks. Candidate readiness is ANY completed linked window, not ALL windows; publish Reaction and ready status atomically after validation. A Candidate with an existing valid Reaction never returns to PENDING merely because another window is pending. A failed Reaction validation creates no final Reaction for that task; preserve its failure report without deleting valid other-window Reactions or an eligible ranking case. Neither state transitions nor market tasks change selected Evidence, scores, cutoff or day 0.

## Asserted and inferred Event relations

Keep direct assertions and inferred triples distinguishable by named graph or immutable audit provenance. An OWL-generated reverse edge is not a second independently extracted fact. Relation-supporting Evidence and both endpoint Events must be available at the evaluated cutoff. Record Evidence IDs, relation availability, assertion chronology/orientation, cutoff and inference regime in the audit manifest; these are provenance metadata, not new ontology classes/properties. Late contradictory Evidence does not rewrite an earlier frozen snapshot.

The inferred baseline uses OWL-RL with the exact frozen ontology and cutoff-eligible asserted snapshot. `B contradicts A` entails `A contradicts B`; this does not license contradiction transitivity or self-relations. Directed relations do not automatically acquire reverse edges. Inference follows rules, not factual truth verification, and does not repair wrongly extracted assertions.

Evaluate both direct Evidence-supported assignment and inference/final graph correctness against independently adjudicated gold. EVALUATION_PROTOCOL.md defines ordered asserted-relation metrics and a separate final unordered contradicts projection. Check the inferred reverse edge, but count each contradictory Event pair once in final semantic metrics. NONE is local to its evaluation view/universe, not an OWL fact or a claim that an unannotated relation is false.
