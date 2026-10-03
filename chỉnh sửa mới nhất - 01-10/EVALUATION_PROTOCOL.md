# EVALUATION_PROTOCOL.md

Version: 1.0.4

## Dataset separation

- `vertical_slice`: 100–300 articles; end-to-end smoke/debug only, no RQ conclusion.
- `development`: labeled data used to tune extraction, linking, staleness, tau, epsilon, event windows and score variants.
- `validation`: held-out data used once to lock the method configuration.
- `final_evaluation`: sealed chronological test set, read only after all methods and thresholds are frozen.

The same canonical Event must not appear across splits. Articles reporting the same Event stay in one split. The split manifest records article IDs, Event IDs, dates, class counts and hashes.

## Phase 1 source-reliability control

All sources in the initial registry are assigned `reliabilityScore=0.5`, and every Candidate
uses `sourceConfidence=0.5`. This fixed value is an experimental control, not a conclusion
that the sources are equally reliable in the real world. Source-quality measurement,
calibration and source-specific ablations are outside the Phase 1 evaluation and are reserved
for a future method version. The same fixed source baseline is used across development,
validation and final evaluation.

## Annotation and freeze

`ANNOTATION_GUIDELINE.md` governs the gold set. At least 25% is independently double-labeled. Agreement and adjudication are completed before final-evaluation sealing. The final set is not used to tune ontology, extraction, linking, score, event window or staleness.

### Immutable baseline cutoff and eligibility

For every canonical Event, baseline `inferenceCutoff == Event.availableAt` exactly, using the immutable earliest factual availability recorded under EVENT_SCHEMA.md; it must be strictly before the opening instant of that Event's daily `effectiveTradingDate` (day 0). Availability at or after an opening maps day 0 to the next eligible session. All methods use this same cutoff snapshot. Evidence, role/link assignments and relation/reporting-period facts used for inference must be supportable from information factually available at or before that instant. A later `generatedAt` is allowed for historical replay, but never expands eligibility or permits a later complete assignment to repair the earliest snapshot. Such results are cutoff-constrained retrospective replay, not observed live predictions.

Predeclare gold Event inclusion/exclusion in the sealed reporting manifest, independently of compared extraction/linking outputs. Failure to produce a complete cutoff-eligible assignment is an algorithmic coverage miss, not a reason to remove an independently resolved gold Event from primary RQ2/RQ3. Record its gold ID, missing predicted Event/assignment reason and earliest/late complete-Evidence availability; retain an empty ranking for that method and count missed gold positives as false negatives. Do not move cutoff, exclude difficult Events using a method's completeness flag, or cherry-pick later favorable labels. Publish source-frame counts, common independently adjudicated eligible Events, unresolved exclusions and each method's coverage misses. Gold adjudication may be performed later, but must judge support at the frozen cutoff, not use future facts to create unavailable gold support. Truly unresolved gold identity/relevance is excluded identically under the annotation contract, never inferred from missing model output. Reaction-only missingness (including unavailable benchmark or market observations) excludes only the separately reported Reaction analysis, not an otherwise eligible RQ2/RQ3 inference/ranking case. Missing required sessions invalidate that Reaction task run; they do not redefine the ranking population.

### Method-independent Event–Stock sampling frame

Freeze a versioned Stock sampling frame before predictions: exchange/listing scope, effective listing dates, identifiers, snapshot ID/hash, chronological Event interval, and inclusion/exclusion rules. Derive each Event's candidate evaluation universe `U_e` from this frame using a predeclared method-independent census or sampling design. If sampling is used, retain selection rules, seeds, inclusion probabilities, selected pair IDs and common sampled negatives; conclusions apply to that sampled universe unless a separately declared population estimator is used. Never construct `U_e` from returned Candidates, method-specific links or final market reactions.

Fully adjudicate every selected `(Event, Stock)` for overall relevance and each baseline route's support, including negatives. Resolve disagreements, remove/report UNRESOLVED pairs identically across methods, then seal the resolved `U_e`, labels, exclusions and hashes before generating predictions; labels remain unavailable to methods. All methods must generate and rank on exactly this resolved `U_e`, without padding with unreturned Stocks. An Event–Stock prediction outside `U_e` invalidates that task run; post-hoc filtering of predictions into the universe is prohibited. Restricting the allowed universe is a predeclared evaluation input, not a gold-dependent retrieval rule. Report frame size, selected/resolved pair counts, negative counts and exclusions per Event and overall.

## RQ1 — extraction and linking

Report precision, recall, F1 and support for:

- Evidence span detection;
- event type and required-role extraction;
- Company/Stock/Industry/Leader entity linking;
- duplicate canonicalization pairwise precision/recall/F1: unordered mention pairs are positive iff assigned the same canonical business Event;
- separately, direct asserted Event relation classification for `updates`, `clarifies`, `contradicts`, `supersedes`, `NONE`: per-label precision/recall/F1, micro/macro-F1 and exact-set accuracy over a frozen ordered pair universe. Contradicts uses annotation storage orientation, not asymmetric logical semantics. Multi-label assertions are allowed; NONE is exclusive in this asserted view. Use gold canonical Event IDs to isolate assignment; label end-to-end results separately. Also evaluate inference/final relations below; neither stage is optional.

### Two-stage Event-relation evaluation

1. **Asserted stage:** freeze cutoff-eligible direct prediction assertions before reasoning and an independently adjudicated gold assertion snapshot. Evidence must support each direct relation. Preserve newer-to-older storage orientation, with EVENT_SCHEMA.md tie/unresolved-chronology convention for contradicts. Report assignment metrics and orientation errors on the frozen ordered universe; derived edges are not extracted predictions.
2. **Inferred/final stage:** apply OWL-RL with the same exact frozen ontology to copies of the eligible snapshots, preserving asserted/derived provenance. Record reasoner implementation/version/options. Check rule correctness against closure licensed by the asserted inputs: required reverse contradicts, no unauthorized reverse directed edges, no contradiction transitivity/self-relations and no future-Evidence leakage. Separately score final projections against independently adjudicated semantic gold. A reasoner can follow rules correctly while wrong input still makes the graph wrong. Never construct gold from predictions.

For final `contradicts`, use `tuple(sorted([str(EventA_URI), str(EventB_URI)]))` for distinct gold canonical Events. Project asserted/entailed edges to this unordered key and deduplicate before TP/FP/FN. A true pair has one positive label, never a reverse contradiction-negative; both directions count once. Its negative is adjudicated absence of contradiction within the cutoff/context, not missing RDF triples. Report binary precision/recall/F1, support, negative confusion counts and uncertainty/coverage exclusions on this separate frozen unordered universe.

Final `updates`, `clarifies` and `supersedes` remain ordered. Report their per-label and multi-label metrics separately from unordered contradicts; do not pool unlike units into one micro/macro or exact-set denominator. NONE is scoped to the view/task: no asserted label, no supported directed label, or no semantic contradiction respectively. Thus a reverse edge may be NONE in the asserted view while a valid entailed contradicts edge; it is not a semantic contradiction-negative. Joint metrics need a separately declared projection and are outside this baseline.

Freeze asserted, directed-final and unordered-contradicts universes and fully adjudicated sampled negatives before predictions. Record pair IDs, task/view, orientation convention, support, exclusions and hashes. Unjudged/UNRESOLVED pairs are excluded and reported, not NONE. Self-pair or out-of-universe predictions invalidate that task run rather than being silently dropped. Relation P/R/F1: no predicted positives gives precision=N/A; no gold positives gives recall=N/A; F1=N/A if either constituent is N/A, otherwise zero if both are zero. Always report counts and false/missed relations. Synthetic diagnostics are regression evidence, not RQ performance.

Updates/clarifies never count as duplicate-positive pairs and never union clusters. For duplicate metrics, report pair counts; if predicted-positive or gold-positive pair sets are empty, precision or recall respectively is N/A; F1 is N/A if either constituent is N/A, otherwise 0 when both are 0. Also report missed/false-merge pair counts so empty predictions cannot be mistaken for success.

Report micro and macro averages with bootstrap confidence intervals.

## RQ2 — Event–Stock inference

Compare keyword/co-occurrence, DIRECT-only and the four-path KG on the same Event universe, Stock universe and cutoff. Report:

- pair-level Precision, Recall and F1;
- Precision@5/@10 and Recall@5/@10;
- results separately for each `impactType`;
- macro average by Event so prolific Events do not dominate;
- direct-mention versus non-direct cases;
- error analysis by path and missing provenance.

### Minimum support and final-set freeze

For each `impactType`, target at least 100 adjudicated positive Event–Stock pairs contributed by at least 30 distinct canonical Events. Estimate the total chronological collection interval from development/validation prevalence, then freeze the interval, target sample, per-type support and split manifest before opening final labels or predictions. Do not top up a deficient stratum after inspecting final results. If either support floor is missed for a type, report that stratum as descriptive only and make no confirmatory per-type claim; always report its actual support and confidence interval. This floor is a minimum reporting gate, not a substitute for inspecting interval width or dependence between pairs from the same Event.

### Route projection and common negative universe

For every resolved pair in `U_e`, independently annotate binary gold support `s_t(e, stock)` for each `impactType` `t` in DIRECT, INDIRECT_INDUSTRY, INDIRECT_SUBSIDIARY and INDIRECT_LEADERSHIP. Multiple supported routes are allowed; missing RDF edges are not adjudicated negatives. For type `t`, evaluate on all of `U_e`, with positives `s_t=1` and common negatives `s_t=0`, not only on pairs with that gold route. A returned type-t prediction on a common negative is a false positive even if the pair is relevant by another route. A pair gold-supported by INDIRECT_INDUSTRY but predicted only by DIRECT is an INDIRECT_INDUSTRY false negative; the DIRECT prediction does not satisfy another route's recall.

Project each method's predictions to type `t` first, then aggregate eligible type-t paths by maximum score to one `(Event, Stock)`, apply the common tie-break and take top K. Never aggregate all routes or select overall top K before this projection. RQ2 pair-level P/R/F1 uses this binary support; per-type Precision@K/Recall@K uses the same type-specific positive set and all common negatives. Overall RQ2 relevance remains `relevance >= 1` on `U_e`, independent of route and with each pair counted once.

Use the identical eligible Event set for every method within each type, including Events without type-t positives. DIRECT-only abstains on every indirect type; do not omit these Events or substitute its overall ranking. Apply the existing empty-prediction/zero-gold rules separately to each type: positives with no returns score P@K=R@K=nDCG=0 and pair P=F1=0; zero-positive Events contribute P@K=0 and false-positive counts but have R@K/nDCG and pair recall/F1=N/A. Metric-defined Event denominators depend only on the frozen gold universe, never on a method's returned positives; report these denominators and exclusions identically across methods.

## RQ3 — weighting and ranking

Compare unweighted score `1` against `candidateScore` at inference cutoff. `reactionWeight` is reported only as post-window descriptive analysis and is never used as a ranking feature for the cutoff evaluation. Report nDCG@5/@10, Precision@K, paired Event-level comparison, component ablations and confidence intervals. Labels are independent of score and CAR.

Overall RQ3 uses independently adjudicated overall relevance `r(e, stock) in {0,1,2}`, regardless of route. For type-t RQ3, use the same prediction-first route projection as RQ2 and reuse graded overall relevance gated by independent route support: `r_t = r * s_t`. Compute DCG and IDCG using `r_t` on the full common resolved `U_e`; binary relevance for type-t Precision@K/Recall@K is `r_t >= 1`. Gold must be consistent (`s_t=1` implies `r>=1`) before sealing. This is route-conditioned reuse of overall relevance, not a newly invented per-route 0/1/2 annotation scale. Report route-support RQ2 metrics, gated-relevance RQ3 metrics and overall any-route metrics as separate views; gains, ranks and denominators are not interchangeable.

## Baseline component ablation contract

The baseline path-strength table, exposureStrength=exposureRatio normalization, and maximum eligible complete-Evidence extraction aggregation are frozen in SCORING_SPEC.md 1.0.4. The industry-strength variant changes only INDUSTRY strength; its population, Evidence selection and other path strengths remain identical to baseline. Record the exact strength/aggregation configuration and selected Evidence IDs in each run's audit manifest. Baseline Reaction validation uses tau=0.10 and epsilon=0; any alternative requires a separately versioned shape/configuration rather than silently bypassing baseline SHACL.

Run exactly three separate confidence-component ablations: set only `extractionConfidence`, only `linkingConfidence`, or only `relationConfidence` to `1`. Keep `sourceConfidence=0.5` in every variant; source-confidence ablation is outside this baseline. This is component neutralization, not a claim of perfect confidence and not removal of extraction, linking or route validation. Recompute `confidenceScore` and `candidateScore` with the formulas in SCORING_SPEC.md. Preserve original scores in the audit record and store each variant under its own `methodVersion` and Candidate URI without rewriting baseline Candidates.

Use the same canonical Event/Stock universe, cutoff, eligible paths, relationStrength, gold labels and tie-break rules for the three paired comparisons against weighted baseline. Aggregate paths independently within each method version; never mix variants in a single ranking. Freeze the three variants before final evaluation and use the same Event-level bootstrap draws across methods. IndustryExposure-strength and event-window comparisons remain separate from these three confidence-component ablations.

## Reproducibility

Freeze the ontology, SHACL shapes, dictionary, annotation guideline, market/calendar inputs and scoring configuration before final evaluation. Retain the immutable input/output manifests, validator logs, validation report and hashes. A final result is reproducible only if the same versioned inputs and calendar/reporting-period selections regenerate the same Candidate and Reaction data.

## Frozen metric and sampling contract

- Gold relevance is 0/1/2 by degree of supported relevance, independent of `impactType` and direct mention. Binary positive means `relevance >= 1`. UNKNOWN direction is not uncertain relevance. UNRESOLVED relevance is excluded before scoring from the common gold/ranking universe for every method and reported separately; unjudged pairs must not be silently treated as negative. Construct the same fully adjudicated Stock universe per Event, independently of the compared method outputs; report its coverage and exclusions.
- For overall metrics, aggregate all eligible paths to one `(Event, Stock)` with maximum cutoff-eligible score; for per-type metrics, project routes first as specified above. Use score descending, Stock URI ascending for all methods, including constant score=1; tied representative paths use Candidate URI ascending. No CAR or reactionWeight tie-break. Do not pad rankings with unreturned Stocks; absent returned slots score zero.
- Fixed K is 5 or 10. `Precision@K = relevant_returned_in_top_K / K` even when fewer than K Candidates exist. `Recall@K = relevant_returned_in_top_K / total_gold_positives` in that Event's fixed resolved universe; not merely positives among retrieved Candidates.
- `DCG@K = sum((2**relevance - 1) / log2(rank + 1))` for ranks starting at 1; unreturned slots have zero gain. IDCG uses the ideal ordering of the full resolved gold universe, not just retrieved Candidates. nDCG = DCG/IDCG.
- An Event with zero gold positives still contributes Precision@K (0) and false-positive counts; Recall@K and nDCG are N/A and excluded from those macro means, with excluded Event counts reported. An Event with no resolved pairs is excluded from all metrics and counted separately. An Event with positives but no returned Candidates has P@K=R@K=nDCG=0. For pair-level metrics: no returned positives => precision=0; no gold positives => recall/F1=N/A; otherwise F1=0 if P+R=0. Report micro counts plus per-Event macro; never average undefined values as zero.
- Macro means give equal weight to each eligible canonical Event, not to paths, articles or number of candidates. Per-impactType positive strata use independently annotated route support, with predictions projected before aggregation and negatives from the full common `U_e`; they are not gold-positive-only evaluation subsets. A pair may support multiple strata, but counts once in overall metrics. Report overlaps and support; strata totals are not additive. Direct-mention strata use text labels, not automatically `impactType=DIRECT`.
- Confidence intervals: paired bootstrap of canonical Events with replacement, 2000 replicates, seed 20260930; keep all Stocks, paths, mentions and labels of a sampled Event together and use the same draws across methods. Report 2.5/97.5 percentile intervals and paired metric differences. Recompute micro counts/eligible macro means within each draw; undefined draws are omitted and their count reported. If no eligible draw exists, CI=N/A. Never bootstrap individual Candidate rows as independent observations.
- For ordered asserted/directed-final relations, bootstrap by source canonical Event with all outgoing pairs together. Each unordered contradicts pair has one frozen owner: newer assertion Event when chronology is established, otherwise lexicographically smaller canonical Event URI. Record owners before predictions; reverse edges never create another bootstrap unit. Duplicate mention pairs use lexicographically smaller gold Event URI (same-Event pairs belong to that Event). Report dependence conventions and paired draws separately from RQ2/RQ3; ownership does not prove shared-endpoint pairs statistically independent.
- Split by canonical Event and time; known connected updates/clarifies/contradicts/supersedes families that would cross chronological boundaries are quarantined from final evaluation rather than leaking a story across splits. Record quarantined IDs. Final-evaluation inference always uses immutable cutoff snapshots and the calendar/reporting-period selection contract in EVENT_SCHEMA.md.

## Run manifest

Record contract version 1.0.4, per-Event immutable `availableAt`/cutoff, day-0 opening/calendar selection, actual `generatedAt` and replay status; the sealed eligibility/reporting manifest and coverage misses; Stock-frame version/hash and sampling design; per-Event resolved universe/label hashes, negative counts and UNRESOLVED exclusions; route-projection view, metric-defined Event denominators and minimum-support gate status. Record Reaction-only exclusions separately from ranking exclusions. These are evaluation contracts only; no Phase 2 metric executor or pipeline implementation is introduced here.

Every run records ontology version, SHACL version, dictionary version, annotation guideline version, methodVersion, cutoff timezone, market calendar, staleness threshold, tau, epsilon, event windows, random seed, input manifest hash and output hash. For AR/CAR reproducibility, also record the market-data provider and dataset/snapshot ID or hash, adjusted-price/corporate-action adjustment convention and version, exchange, calendar ID/version/hash, benchmarkIndex URI, and reaction-validator version. For `IndustryExposure`, record `periodType` (baseline `YEAR`) and reporting scope (`consolidated` or `standalone`). Record the final chronological interval, target sample size, minimum support by `impactType`, and actual per-type support. Store validation totals and failures for observation ownership, date coverage/pairing, daily return recomputation, AR and CAR recomputation. A Reaction task run with a missing or mismatched required session is invalid, not a partial-window result; this does not exclude an otherwise eligible inference/ranking case. Synthetic demo results are structural tests only and are excluded from RQ conclusions.
