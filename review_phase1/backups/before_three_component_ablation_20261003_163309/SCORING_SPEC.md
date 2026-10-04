# SCORING_SPEC.md

Version: 1.0.2
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
- `extractionConfidence`: calibrated extractor probability for the Candidate's Event/Evidence role assignment at cutoff.
- `linkingConfidence`: calibrated entity-linker score for each linked Company, Stock, Industry or Leader; Candidate uses the minimum required-link score.
- `relationConfidence`: confidence that the selected relation path is valid at cutoff. DIRECT uses the minimum confidence of the Event–Company and Company–Stock links.
- `relationStrength`: path strength, independent of market reaction. INDIRECT_INDUSTRY baseline uses constant `0.5` on an eligible curated exposure; the measured variant uses its required `exposureStrength`. Both follow the same reporting-period selection in EVENT_SCHEMA.md; missing/stale exposure suppresses the path rather than manufacturing a relation.

### Confidence provenance and fallback

Freeze the model/calibration version using development data only. Each extraction/link score is tied to its input Evidence/normalized entity decision in the inference audit record. A verified curated registry Company–Stock mapping uses confidence `1.0` with registry/version provenance; an automatic mapping uses its calibrated linker probability. If a required link or supporting fact is absent, reject that path rather than assign a fallback to an invented edge.

For present, evidenced facts lacking a calibrated confidence, the declared baseline is `0.5` for extraction/linking/Event–Company or other path-link confidence. Record each missing-score fallback in the audit record and `methodVersion`; never present defaults as calibrated probabilities. DIRECT relation confidence is the minimum Event–Company and Company–Stock confidence; indirect relation confidence is the minimum of all required path-link confidences, including the temporal node's `relationConfidence` and terminal Company–Stock mapping. `linkingConfidence` remains the minimum required entity-link score. Shared `relationConfidence` is domain-neutral in OWL; SHACL applies constraints in each class context. The fixed `sourceConfidence=0.5` baseline is not a claim that sources are equally reliable in reality; it is an experimental control until source evaluation is added.

If new Evidence arrives after the cutoff, it creates a new snapshot/Candidate version; it must not mutate the old score.

## 2. Reaction-time score

After all observations for the configured event window are available, including the exchange session immediately before the first in-window session:

```text
R(i,t) = adjustedClose(i,t) / adjustedClose(i,t-1) - 1
AR(i,t) = R(i,t) - R(m,t)
CAR(i,[a,b]) = sum(AR(i,t) for trading sessions t in [a,b])
impactScore = min(1, abs(CAR) / tau)
reactionWeight = impactScore * confidenceScore * relationStrength
```

`adjustedClose` is the source of truth for both the stock and benchmark. `returnValue` may be stored as a cache, but it must be recomputed from consecutive adjusted closes and must agree within absolute tolerance `1e-9`; it is not sufficient provenance by itself. For offsets `[a,b]`, the Reaction links the selected observations for sessions `t_(a-1), t_a, ..., t_b`, one per asset per session, and the stock/index date sets must match. Each linked observation must belong to the Candidate's stock or the Reaction's benchmark, respectively.

Every supported baseline window includes offset `0`. The single `abnormalReturn` field on `EventStockReaction` means `AR(i,0)`; `cumulativeAbnormalReturn` means the sum of daily AR values over the entire inclusive window `[a,b]`. Thus multi-day CAR is independently reproducible even though daily ARs are not separately materialized as RDF nodes. SHACL checks the daily return arithmetic for the window sessions and the CAR sum; a calendar-aware validator checks that the linked dates are precisely the sessions required by the frozen exchange calendar.

The baseline uses `tau=0.10` and `epsilon=0`. `signedWeight` is `reactionWeight` multiplied by `+1`, `-1`, or `0` according to CAR relative to epsilon.

## 3. Anti-leakage rules

- `reactionWeight` must not be used to generate or rank a Candidate at `inferenceCutoff`.
- Candidate ranking uses only `candidateScore` and pre-cutoff inputs.
- Reaction may be calculated only after the complete event window closes.
- Every input observation must have `availableAt` no later than the Reaction availability time.

## 4. Multi-path aggregation

For inference ranking, multiple paths for the same `(Event, Stock)` are aggregated by `max(candidateScore)` after grouping by the locked method version and cutoff. Tied representative paths use Candidate URI ascending; ranked Stocks use score descending then Stock URI ascending (case-sensitive Unicode codepoint order). This includes the all-1 unweighted baseline. CAR is not added across duplicate paths. Post-window analysis may report each path's `reactionWeight`, but must not treat paths as independent events.

## 5. Required ablations

Phase 2 compares:

- unweighted baseline: score `1`;
- weighted candidate ranking: `candidateScore`;
- component ablations: each confidence component replaced by `1`;
- IndustryExposure constant `0.5` versus measured `exposureStrength` on the same eligible curated exposure population;
- event windows `[0,0]`, `[0,+1]`, `[-1,+1]`, `[0,+3]`.

All choices are frozen before the final test set is read.
