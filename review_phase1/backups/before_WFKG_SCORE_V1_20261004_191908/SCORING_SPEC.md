# SCORING_SPEC.md

Version: 1.0.4
Namespace: `https://example.org/wfkg/v1#`

## 1. Candidate-time score

### Phase 1 source-reliability baseline

Phase 1 intentionally holds source reliability constant so that the experiment evaluates
event extraction, entity linking, relation-path logic and temporal cutoff behavior rather
than an unvalidated source-quality model.

- Every source participating in the initial source registry is assigned
  `NewsSource.reliabilityScore = 0.5`.
- For every cutoff-eligible Candidate, `sourceConfidence = 0.5`, regardless of the number
  of supporting sources or articles. Repeated reports from the same source never increase it.
- Source reliability measurement, source ranking, calibration and source-specific ablations
  are explicitly deferred to a future extension. They require a new `methodVersion` and
  must not be mixed with the Phase 1 baseline results.

For every valid Candidate at cutoff `c`:

```text
confidenceScore = 0.25 * (
  sourceConfidence + extractionConfidence + linkingConfidence + relationConfidence
)
candidateScore = confidenceScore * relationStrength
```

All four confidence components, `confidenceScore`, `relationStrength` and `candidateScore` are in `[0,1]`, stored on the Candidate, and frozen with `inferenceCutoff` and `methodVersion`. `methodVersion` identifies the exact component formulas, calibration model and fallback values used for that snapshot.

### Component rules

- `sourceConfidence`: fixed baseline value `0.5` for every cutoff-eligible supporting source set. The Phase 1 baseline does not use `max(reliabilityScore)` to differentiate sources; all initial source records are deliberately equal. A future source-quality variant may use a documented aggregation of evaluated source scores, but it is a separate method version.
- `extractionConfidence`: the maximum eligible Evidence-level score for the Candidate's Event/required-role assignment at cutoff, using the frozen selection contract below. A score is a calibrated probability only when calibration provenance exists; otherwise apply the declared fallback.
- `linkingConfidence`: the minimum required entity/link decision score in the four-route table below. Event entity decisions come only from the chosen complete Evidence assignment; route-derived endpoint and terminal Company–Stock mappings are scored separately from eligible registry/fact provenance. A score is a calibrated probability only where the corresponding calibration is documented.
- `relationConfidence`: a conservative path-support heuristic, the minimum of the required path-link scores below. DIRECT uses the selected Evidence assignment score for Event–Company and the terminal Company–Stock mapping score. This is not a calibrated relation probability.
- `relationStrength`: use the frozen path-strength table below, independent of confidence and market reaction. Missing/stale facts suppress the path rather than manufacturing a relation.

### Frozen strength and extraction aggregation contract

| impactType | Baseline relationStrength | Industry-strength variant |
| --- | --- | --- |
| DIRECT | 1.0 | 1.0 |
| INDIRECT_INDUSTRY | 0.5 | selected eligible exposureStrength |
| INDIRECT_SUBSIDIARY | 0.5 | 0.5 |
| INDIRECT_LEADERSHIP | 0.5 | 0.5 |

These constants are experimental heuristics, not measured economic effects. The industry variant changes only INDUSTRY strength and uses exactly the same eligible exposure population and frozen reporting-period selection as baseline.

For this variant, `exposureStrength = exposureRatio`. Normalize a percentage to a decimal fraction once at ingestion (e.g. 12% becomes 0.12); retain the source unit, numerator/denominator and reporting-category mapping in the ingestion audit record. Do not guess whether an unlabelled number is a percentage or fraction, clip out-of-range values, infer a missing ratio, or invent a nonlinear transform. Unknown units/denominators/mappings remain staging. Both values must be in [0,1]. Alternative transforms require a separate method version frozen on development/validation data, not a retrospective change.

For extraction aggregation, first select Evidence supporting the same canonical Event, available no later than cutoff, whose versioned extraction assignment supports all dictionary-required roles and agrees with the selected normalized role/identity assignment. Each eligible Evidence has one Event/required-role assignment score; if the extractor produces only per-role scores, use their minimum as that Evidence's assignment score. Present, evidenced assignments without calibration use the declared 0.5 fallback; missing required roles do not receive a fallback and are ineligible. Choose the largest Evidence assignment score, with Evidence URI ascending as the tie-break (case-sensitive Unicode codepoint order). Do not combine incomplete Evidence to manufacture a complete assignment in this baseline. No eligible Evidence means no curated Candidate. Extra articles do not sum or average confidence. Freeze the eligible Evidence IDs, component scores, selected Evidence URI, role assignments, model/calibration versions and fallback flags in the inference audit record. Component-neutralization variants retain this baseline evidence selection and original scores; they change only the declared component value.

Select the complete Event assignment once, before route scoring. For every required entity-valued role in the dictionary (including buyer/target, regulator, partner and other non-route participants), its normalized entity ID and linking decision must belong to that same selected Evidence assignment. Any optional entity used as a route entry must also be supported and linked within that assignment. If it is absent, that route is suppressed; do not reselect a lower-scoring Evidence to rescue the route. Do not independently maximize linker scores across other Evidence, swap entity decisions, or join partial assignments. An existing canonical identity is not proof that the selected Evidence contains its missing roles.

### Required entity/link confidence inputs by route

Let `A` be the original chosen complete Evidence assignment score; `E` is the set of linking decision scores for **all dictionary-required entity roles**, plus the selected assignment's route-entry entity when optional. Dates, action tokens and other literal roles contribute to extraction assignment completeness/score, not entity-link scores. Registry references that denote an entity must retain its type and decision provenance; non-entity document/occurrence IDs are not extra entity links. Let `M` be the terminal Company–Stock mapping score. Mapping endpoints must match the exact selected route and be available at cutoff; never minimize unrelated registry facts.

| impactType | Required inputs to linkingConfidence (minimum) | Required inputs to relationConfidence (minimum) |
| --- | --- | --- |
| DIRECT | `E`, route-entry Company decision, `M` for that Company and Candidate Stock | Event–Company support `A`, `M` |
| INDIRECT_SUBSIDIARY | `E`, selected child Company decision, child/parent endpoint mapping decisions from selected SubsidiaryRelation/registry, `M` for that parent | Event–child support `A`, selected SubsidiaryRelation.relationConfidence, child/parent endpoint mapping scores, `M` |
| INDIRECT_LEADERSHIP | `E`, selected CorporateLeader decision, leader/company endpoint mapping decisions from selected LeadershipPosition/registry, `M` for that position's Company | Event–Leader support `A`, selected LeadershipPosition.relationConfidence, leader/company endpoint mapping scores, `M` |
| INDIRECT_INDUSTRY | `E`, selected Industry decision, industry/Bank endpoint mapping decisions from selected eligible IndustryExposure/registry, `M` for that Bank | Event–Industry support `A`, selected IndustryExposure.relationConfidence, industry/Bank endpoint mapping scores, `M` |

Repeated references to the same decision do not create independent evidence. A propagated parent, position-company or Bank need not be mentioned in the input Evidence: its confidence comes from the eligible typed route mapping, not a new direct entity extraction. For any route, the terminal Company–Stock mapping includes the Candidate Stock identity decision; do not omit Stock or treat a ticker-only mention as the Company link. Required Event participants still use selected Evidence decisions even when they are not on the propagated route. If an entry has no supported route-entry entity (e.g. a policy with no eligible baseline route), emit no path; the dictionary does not expand the four baseline routes.

### Confidence provenance and fallback

Freeze the model/calibration version using development data only. Each extraction/link score is tied to its input Evidence/normalized entity decision in the inference audit record. A verified typed curated registry mapping (including Company–Stock and route endpoint identity mappings) uses confidence `1.0` with registry/version/availability provenance; this is a curated decision convention, not statistical calibration. An automatic mapping uses its own calibrated decision score, or `0.5` when present and evidenced but uncalibrated. Curated entity resolution does not make the economic relation itself certain: temporal node relationConfidence is separate. If a required link or supporting fact is absent, unresolved, mismatched, unavailable or temporally ineligible, suppress that path rather than assign a fallback to an invented edge.

For present, evidenced facts lacking a calibrated confidence, the declared baseline is `0.5` for extraction, automatic linking and unscored path facts. Record each fallback in the audit record and `methodVersion`; never present defaults as calibrated probabilities. Event–Company link-support confidence originates **exactly from `A`**, the same selected complete Evidence required-role assignment score, not the Company linker score, a separate Evidence maximum or an invented relation classifier; Event–Industry and Event–Leader support use that same convention. Preserve `A` even when an extraction-neutralization ablation replaces Candidate.extractionConfidence with `1`; it does not alter relationConfidence or route selection. Indirect relationConfidence follows the table, including the selected temporal node's original relationConfidence and terminal mapping `M`. Shared `relationConfidence` is domain-neutral in OWL; SHACL applies constraints in each class context. Scores reused across components are dependent support signals; neither their minimum nor the equal-weight average is a calibrated joint probability or an independence assumption. The fixed source baseline is an experimental control, not a real-world reliability claim.

Baseline cutoff is exactly `Event.availableAt`, its earliest supporting Evidence availability, and is immutable. Replay `generatedAt` may be later but must use only the frozen cutoff-eligible inputs; do not describe offline replay as live prediction. No complete assignment at that instant means no baseline Candidate (`NO_COMPLETE_EVIDENCE_AT_CUTOFF`, reported coverage miss), not permission to move cutoff or exclude an independently resolved gold Event from RQ2/RQ3. Retain its empty method ranking and count missed positives under EVALUATION_PROTOCOL.md. Later Evidence for the same assertion may be analyzed only in a separately versioned retrospective reconstruction outside baseline; it cannot mutate the historical Event, selected assignment, day 0 or Candidate. A genuinely new substantive assertion has a distinct Event URI and its own earliest availability/day 0 under EVENT_SCHEMA.md.

## 2. Reaction-time score

After all observations for the configured event window are available, including the exchange session immediately before the first in-window session:

```text
R(i,t) = adjustedClose(i,t) / adjustedClose(i,t-1) - 1
AR(i,t) = R(i,t) - R(m,t)
CAR(i,[a,b]) = sum(AR(i,t) for trading sessions t in [a,b])
impactScore = min(1, abs(CAR) / tau)
reactionWeight = impactScore * confidenceScore * relationStrength
```

`adjustedClose` is the source of truth for both the stock and benchmark. `returnValue` is required in the baseline as a derived/cache field, but it must be recomputed from consecutive adjusted closes and must agree within absolute tolerance `1e-9`; it is not sufficient provenance by itself. For offsets `[a,b]`, the Reaction links the selected observations for sessions `t_(a-1), t_a, ..., t_b`, one per asset per session, and the stock/index date sets must match. Each linked observation must belong to the Candidate's stock or the Reaction's benchmark, respectively.

Every supported baseline window includes offset `0`. The single `abnormalReturn` field on `EventStockReaction` means `AR(i,0)`; `cumulativeAbnormalReturn` means the sum of daily AR values over the entire inclusive window `[a,b]`. Thus multi-day CAR is independently reproducible even though daily ARs are not separately materialized as RDF nodes. SHACL checks the daily return arithmetic for the window sessions and the CAR sum; a calendar-aware validator checks that the linked dates are precisely the sessions required by the frozen exchange calendar.

The baseline uses `tau=0.10` and `epsilon=0`. `signedWeight` is `reactionWeight` multiplied by `+1`, `-1`, or `0` according to CAR relative to epsilon.

SHACL checks baseline impact normalization and marketReactionDirection against CAR, in addition to return/AR/CAR arithmetic and reactionWeight/signedWeight. Arithmetic comparisons use absolute tolerance 1e-9; direction uses the exact sign of CAR with epsilon=0. A tau/epsilon variant requires a separately versioned shape/configuration; changing only methodVersion does not bypass baseline constraints. Candidate strength assignment, Evidence aggregation, calendar and frozen input eligibility remain curated-pipeline gates, not implied by SHACL conformance.

## 3. Anti-leakage rules

- `reactionWeight` must not be used to generate or rank a Candidate at `inferenceCutoff`.
- Candidate ranking uses only `candidateScore` and inputs with `availableAt <= inferenceCutoff = Event.availableAt`.
- LeadershipPosition/SubsidiaryRelation/IndexMembership first select the latest cutoff-available version per business key under EVENT_SCHEMA.md's temporal version-selection contract, then test inclusive validity at the local cutoff date, not effectiveTradingDate or replay time. Never fall back to an older open-ended version. IndustryExposure uses the separate scope-partitioned YEAR/newest-period rule with inclusive 365-day staleness and deterministic availableAt/URI ties in EVENT_SCHEMA.md.
- Day 0 is the first exchange session with `Event.availableAt < session.open` strictly; equality at open moves to the next session. `[0,0]`, `[0,+1]`, `[0,+3]` are post-availability daily windows; `[-1,+1]` is retrospective robustness and never supplies ranking inputs.
- Reaction may be calculated only after the complete event window closes.
- Every input observation must have `availableAt` no later than the Reaction availability time.

## 4. Multi-path aggregation

For inference ranking, multiple paths for the same `(Event, Stock)` are aggregated by `max(candidateScore)` after grouping by the locked method version and cutoff. Tied representative paths use Candidate URI ascending; ranked Stocks use score descending then Stock URI ascending (case-sensitive Unicode codepoint order). This includes the all-1 unweighted baseline. CAR is not added across duplicate paths. Post-window analysis may report each path's `reactionWeight`, but must not treat paths as independent events.

## 5. Required ablations

Phase 2 compares:

- unweighted baseline: score `1`;
- weighted candidate ranking: `candidateScore`;
- three separate component-neutralization ablations: replace only `extractionConfidence`, only `linkingConfidence`, or only `relationConfidence` by `1`; keep `sourceConfidence = 0.5` in all baseline variants;
- IndustryExposure constant `0.5` versus measured `exposureStrength` on the same eligible curated exposure population;
- event windows `[0,0]`, `[0,+1]`, `[-1,+1]`, `[0,+3]`.

A component-neutralization ablation removes that component's score variation by setting it to `1`; it does not assert perfect extraction/linking/relation confidence and does not remove the underlying extraction, entity-linking or route-eligibility checks. Recompute `confidenceScore` and `candidateScore` using the unchanged formulas for each variant. Store each variant as a separate immutable Candidate snapshot with its own `methodVersion` and Candidate URI; never overwrite the baseline snapshot. Use the same Event/Stock universe, cutoff, eligible paths, relationStrength and tie-break rules for these three comparisons. Preserve original component values and neutralization settings in the inference audit record. Source-confidence ablation is outside this baseline and requires a separately specified future protocol.

All choices are frozen before the final test set is read.
