# EVENT_SCHEMA.md

Version: 1.0.2

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

`relationPath` is a stable route code and must equal `impactType` in the Phase 1 baseline. Allowed pairs are `DIRECT`, `INDIRECT_INDUSTRY`, `INDIRECT_SUBSIDIARY` and `INDIRECT_LEADERSHIP`. Their graph paths are:

- `DIRECT`: `Event → Company → Stock`.
- `INDIRECT_INDUSTRY`: `Event → Industry ← IndustryExposure ← Bank → Stock`; this path creates candidates only for a Bank with a selected eligible exposure, not every stock in the industry.
- `INDIRECT_SUBSIDIARY`: `Event → subsidiary Company`; a `SubsidiaryRelation` must identify that subsidiary and a parent Company, and the parent must own the Candidate Stock.
- `INDIRECT_LEADERSHIP`: `Event → CorporateLeader → LeadershipPosition → Company → Stock`.

SHACL 1.0.2 checks the route code and required graph links. The curated inference gate must additionally apply cutoff availability and validity rules to route facts; for `IndustryExposure`, it must use the frozen reporting-period selection below. Phase 1 `sourceConfidence` remains fixed at `0.5`; changing that baseline requires a new method/shape version.

## Scoring timing

```text
candidateScore = confidenceScore * relationStrength
reactionWeight = impactScore * confidenceScore * relationStrength
```

`candidateScore` is allowed at `inferenceCutoff`. `reactionWeight` is allowed only after the complete event window and all required observations are available. The canonical property is `reactionWeight`; the legacy bare property `weight` is not part of the 1.0.2 contract.

## AR/CAR source and provenance contract (1.0.2)

- `adjustedClose` is the authoritative input for both `MarketObservation` and `MarketIndexObservation`; each value must be positive and retain its `sourceReference`. `returnValue` is a derived/cache field, never the sole source for recomputing a reaction.
- Window offsets are exchange-session offsets relative to `Event.effectiveTradingDate` (`t0`). For a window `[a,b]`, the Reaction must link one Stock observation and one benchmark observation for every session `t_(a-1), t_a, ..., t_b`. The predecessor `t_(a-1)` supplies the denominator for the first in-window return.
- Linked Stock observations must belong to `Candidate.candidateStock`; linked index observations must belong to `Reaction.benchmarkIndex`. The two sets must have the same unique `tradingDate` values, with exactly one selected observation per asset and session.
- All supported windows contain offset `0`. `EventStockReaction.abnormalReturn` stores `AR(i,0)`; `cumulativeAbnormalReturn` stores `sum(AR(i,t), t=a..b)`. Each daily AR is recomputed from adjusted closes, not copied from a cached return.
- For each in-window session `t`, recompute `R(i,t)=adjustedClose(i,t)/adjustedClose(i,t-1)-1` and the corresponding benchmark return from the immediately preceding exchange session, then `AR(i,t)=R(i,t)-R(m,t)`. Validate cached `returnValue`, `abnormalReturn`, and `cumulativeAbnormalReturn` against these recomputations with absolute tolerance `1e-9`.
- SHACL validates observation ownership, date pairing, unique-date counts, required positive adjusted closes, daily return arithmetic, and the CAR sum. A calendar-aware validator must additionally compare the linked dates with the exact session sequence from the frozen exchange calendar; SHACL alone cannot infer holidays or session offsets from dates.
- The run manifest records market-data provider/dataset snapshot, adjusted-price and corporate-action adjustment convention, benchmark URI, exchange, and calendar identifier/version/hash so the close series can be reproduced.

## Phase 1 source baseline

All initial `NewsSource` records use `reliabilityScore = 0.5`, and every Phase 1
`EventStockCandidate` stores `sourceConfidence = 0.5`. This is an intentionally neutral
control so the Phase 1 pipeline can evaluate Event extraction, entity linking, relation
paths, cutoff eligibility and Candidate logic without claiming that one source is more
reliable than another. Supporting-source multiplicity does not increase the value.
Source reliability assessment and source-specific calibration are future extensions with a
new `methodVersion`; they must not rewrite Phase 1 Candidate snapshots or alter the baseline
evaluation retrospectively.

## Temporal/provenance rules

- `availableAt <= inferenceCutoff` for Candidate inputs.
- `effectiveTradingDate` uses the availability/calendar rule below, not the repost's publication day.
- Both `MarketObservation` and `MarketIndexObservation` require `adjustedClose > 0`; `returnValue`, `availableAt` and `sourceReference` are mandatory. `returnValue` may be negative and is only a derived/cache field; `adjustedClose` is authoritative for recomputation. See the AR/CAR contract above.
- Reaction provenance contains exactly the predecessor session plus every session in the configured event window for both the Candidate stock and benchmark; the calendar-aware validator checks the exact session dates.
- `LeadershipPosition`, `SubsidiaryRelation`, `IndexMembership`: `validFrom` required, `validTo` optional. Eligibility is `availableAt <= cutoff AND validFrom <= date(cutoff) AND (validTo absent OR date(cutoff) <= validTo)`; dates are inclusive. Missing start is ineligible, not an unbounded tenure.
- `IndustryExposure` uses reporting-period selection below; `validFrom`/`validTo` are optional metadata, not the baseline eligibility filter.

## Frozen cutoff and daily calendar contract (1.0.2)

- Use timezone-aware instants; compare instants in UTC and derive dates in `Asia/Ho_Chi_Minh`. A naive timestamp is rejected. Equality at cutoff is eligible (`<=`).
- Event availability is the earliest supporting Evidence availability; Evidence availability must be no earlier than both its Article's `publishedAt` and actual first system availability. Do not invent crawler latency. Missing acquisition timestamps require a declared publication-time proxy dataset, not a claim of observed historical availability.
- For a frozen Event snapshot let `a = Event.availableAt`. Select the first exchange session whose opening instant is **strictly later** than `a`: `a < session.open`. Thus before open uses that session; exactly at open, intraday or after close uses the next session; weekends/holidays use the next scheduled opening. Calendar/version, exchange and session opening times belong in the run manifest; do not use weekday arithmetic. Missing calendar coverage blocks calculation.
- Example with a declared 09:00 +07 opening: 26/08/2026 08:59 uses 26/08; 09:00 and 14:16 use 27/08 when that is the next calendar session. Both demo Events available after open on 26/08 use 27/08.
- `inferenceCutoff >= Event.availableAt`; every Evidence, reference mapping and temporal fact used is available no later than cutoff. Newly learned earlier evidence may produce a new version, never rewrite the frozen Candidate or calendar decision.
- Historical lifecycle queries read an immutable graph snapshot or timestamped status log. Filtering a current mutable `candidateStatus` by observation dates is not historical reconstruction.
- A Reaction requires completed window and complete Stock + benchmark prices for each session including the predecessor. Negative-offset windows are retrospective robustness analyses, not wholly post-event responses.

## IndustryExposure selection (separate from validity)

1. Fix `(exposureBank, exposureIndustry, periodType)` and the reporting scope (e.g. consolidated vs standalone) in the dataset/method manifest. Baseline fixes `periodType=YEAR`; alternative period types are separately named variants, never mixed into one latest-period contest. Reporting scope is ingestion metadata, not a new ontology property/class.
2. Require `availableAt <= cutoff` and `periodEnd <= date(cutoff)`; require `0 <= (date(cutoff) - periodEnd).days <= 365` (inclusive calendar-day staleness).
3. Sort eligible records by `periodEnd DESC, availableAt DESC, STR(URI) ASC` and take one per group. URI comparison is ascending Unicode codepoint order, case-sensitive, no locale collation. Do not require `validFrom` or filter on `validTo` for this reporting-period path.
4. No eligible record means no INDUSTRY path (not a fabricated 0.5 exposure). Missing `exposureStrength` remains raw/staging; curated `IndustryExposureShape` requires it. Constant-strength ablation still requires a valid curated exposure; it does not repair missing facts.

## Canonical identity and dictionary roles

The dictionary's roles (including `occurrence_id`) are extraction/identity-registry fields, not new RDF properties or classes. Preserve the 22 ontology classes. Normalize roles before constructing `canonicalKey`; follow `identity_policy` for every entry.

Article publication/availability dates never distinguish business occurrences. A duplicate reprint attaches new Article/Evidence provenance to the same Event URI, including when posted on another day. `occurrence_id` identifies the original business assertion, not each article. Required identity missing => HOLD_FOR_REVIEW. Optional key field missing => MATCH_EXISTING_ELSE_HOLD: reuse an existing key only when positive same-occurrence evidence and all known roles agree; otherwise keep staging without minting a curated key. Never fill missing dates with publication/availability, empty strings or shared UNKNOWN sentinels. Missing non-key optional roles may simply be omitted.

New material facts create distinct Events. `updates`, `clarifies` and `supersedes` are directed from newer assertion to older assertion. `contradicts` means two supported assertions are incompatible in the same business context; it is logically symmetric, as declared in the ontology, and does not identify which assertion is true. For provenance, store its direct assertion newer-to-older; this storage convention does not remove logical symmetry. Establish assertion chronology from original supporting Evidence, not ingestion order or an invented occurrence date. When chronology is tied or cannot be resolved, store `contradicts` using ascending canonical Event URI as a deterministic orientation, flag the tie/unresolved chronology in the audit record, and do not interpret that orientation as temporal precedence. A relation never unions duplicate clusters, even for the same company/period/deal. Mere wording changes or repeated statements are duplicates, not updates. A later correction to identity metadata alone preserves URI with alias history; a substantive earnings restatement has a new assertion/occurrence ID and an `updates`/`supersedes` relation. An unspecified occurrence time requires original-document identity or adjudication; it is not replaced by the article date.

## Asserted and inferred Event relations

Keep direct assertions and inferred triples distinguishable by named graph or immutable audit provenance. An OWL-generated reverse edge is not a second independently extracted fact. Relation-supporting Evidence and both endpoint Events must be available at the evaluated cutoff. Record Evidence IDs, relation availability, assertion chronology/orientation, cutoff and inference regime in the audit manifest; these are provenance metadata, not new ontology classes/properties. Late contradictory Evidence does not rewrite an earlier frozen snapshot.

The inferred baseline uses OWL-RL with the exact frozen ontology and cutoff-eligible asserted snapshot. `B contradicts A` entails `A contradicts B`; this does not license contradiction transitivity or self-relations. Directed relations do not automatically acquire reverse edges. Inference follows rules, not factual truth verification, and does not repair wrongly extracted assertions.

Evaluate both direct Evidence-supported assignment and inference/final graph correctness against independently adjudicated gold. EVALUATION_PROTOCOL.md defines ordered asserted-relation metrics and a separate final unordered contradicts projection. Check the inferred reverse edge, but count each contradictory Event pair once in final semantic metrics. NONE is local to its evaluation view/universe, not an OWL fact or a claim that an unannotated relation is false.
