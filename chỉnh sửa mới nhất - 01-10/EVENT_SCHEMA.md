# EVENT_SCHEMA.md

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

## Scoring timing

```text
candidateScore = confidenceScore * relationStrength
reactionWeight = impactScore * confidenceScore * relationStrength
```

`candidateScore` is allowed at `inferenceCutoff`. `reactionWeight` is allowed only after the complete event window and all required observations are available. The canonical property is `reactionWeight`; the legacy bare property `weight` is not part of v1.0.

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
- `MarketIndexObservation` must contain `adjustedClose` sufficient to recompute benchmark returns. The generic `adjustedClose` OWL property is domain-neutral, while SHACL constrains it separately for stock and index observations.
- Reaction provenance includes every observation in the window and the `t-1` observation needed for the first return.
- `LeadershipPosition`, `SubsidiaryRelation`, `IndexMembership`: `validFrom` required, `validTo` optional. Eligibility is `availableAt <= cutoff AND validFrom <= date(cutoff) AND (validTo absent OR date(cutoff) <= validTo)`; dates are inclusive. Missing start is ineligible, not an unbounded tenure.
- `IndustryExposure` uses reporting-period selection below; `validFrom`/`validTo` are optional metadata, not the baseline eligibility filter.

## Frozen cutoff and daily calendar contract (1.0.1)

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

New material facts create distinct Events linked by `updates`, `clarifies`, `contradicts` or `supersedes` from newer assertion to older assertion. They never union duplicate clusters, even for the same company/period/deal. Mere wording changes or repeated statements are duplicates, not updates. A later correction to identity metadata alone preserves URI with alias history; a substantive earnings restatement has a new assertion/occurrence ID and an `updates`/`supersedes` relation. An unspecified occurrence time requires original-document identity or adjudication; it is not replaced by the article date.
