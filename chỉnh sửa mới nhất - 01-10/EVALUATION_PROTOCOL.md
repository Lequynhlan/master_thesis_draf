# EVALUATION_PROTOCOL.md

Version: 1.0.2

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

## RQ3 — weighting and ranking

Compare unweighted score `1` against `candidateScore` at inference cutoff. `reactionWeight` is reported only as post-window descriptive analysis and is never used as a ranking feature for the cutoff evaluation. Report nDCG@5/@10, Precision@K, paired Event-level comparison, component ablations and confidence intervals. Labels are independent of score and CAR.

## Baseline component ablation contract

Run exactly three separate confidence-component ablations: set only `extractionConfidence`, only `linkingConfidence`, or only `relationConfidence` to `1`. Keep `sourceConfidence=0.5` in every variant; source-confidence ablation is outside this baseline. This is component neutralization, not a claim of perfect confidence and not removal of extraction, linking or route validation. Recompute `confidenceScore` and `candidateScore` with the formulas in SCORING_SPEC.md. Preserve original scores in the audit record and store each variant under its own `methodVersion` and Candidate URI without rewriting baseline Candidates.

Use the same canonical Event/Stock universe, cutoff, eligible paths, relationStrength, gold labels and tie-break rules for the three paired comparisons against weighted baseline. Aggregate paths independently within each method version; never mix variants in a single ranking. Freeze the three variants before final evaluation and use the same Event-level bootstrap draws across methods. IndustryExposure-strength and event-window comparisons remain separate from these three confidence-component ablations.

## Reproducibility

Freeze the ontology, SHACL shapes, dictionary, annotation guideline, market/calendar inputs and scoring configuration before final evaluation. Retain the immutable input/output manifests, validator logs, validation report and hashes. A final result is reproducible only if the same versioned inputs and calendar/reporting-period selections regenerate the same Candidate and Reaction data.

## Frozen metric and sampling contract

- Gold relevance is 0/1/2 by degree of supported relevance, independent of `impactType` and direct mention. Binary positive means `relevance >= 1`. UNKNOWN direction is not uncertain relevance. UNRESOLVED relevance is excluded before scoring from the common gold/ranking universe for every method and reported separately; unjudged pairs must not be silently treated as negative. Construct the same fully adjudicated Stock universe per Event, independently of the compared method outputs; report its coverage and exclusions.
- Aggregate paths to one `(Event, Stock)` with maximum pre-cutoff score. Use score descending, Stock URI ascending for all methods, including constant score=1; tied representative paths use Candidate URI ascending. No CAR or reactionWeight tie-break. Do not pad rankings with unreturned Stocks; absent returned slots score zero.
- Fixed K is 5 or 10. `Precision@K = relevant_returned_in_top_K / K` even when fewer than K Candidates exist. `Recall@K = relevant_returned_in_top_K / total_gold_positives` in that Event's fixed resolved universe; not merely positives among retrieved Candidates.
- `DCG@K = sum((2**relevance - 1) / log2(rank + 1))` for ranks starting at 1; unreturned slots have zero gain. IDCG uses the ideal ordering of the full resolved gold universe, not just retrieved Candidates. nDCG = DCG/IDCG.
- An Event with zero gold positives still contributes Precision@K (0) and false-positive counts; Recall@K and nDCG are N/A and excluded from those macro means, with excluded Event counts reported. An Event with no resolved pairs is excluded from all metrics and counted separately. An Event with positives but no returned Candidates has P@K=R@K=nDCG=0. For pair-level metrics: no returned positives => precision=0; no gold positives => recall/F1=N/A; otherwise F1=0 if P+R=0. Report micro counts plus per-Event macro; never average undefined values as zero.
- Macro means give equal weight to each eligible canonical Event, not to paths, articles or number of candidates. Per-impactType results use independently annotated supported path strata; a pair may occur in multiple strata, but counts once in overall metrics. Report overlaps and support; strata totals are not additive. Direct-mention strata use text labels, not automatically `impactType=DIRECT`.
- Confidence intervals: paired bootstrap of canonical Events with replacement, 2000 replicates, seed 20260930; keep all Stocks, paths, mentions and labels of a sampled Event together and use the same draws across methods. Report 2.5/97.5 percentile intervals and paired metric differences. Recompute micro counts/eligible macro means within each draw; undefined draws are omitted and their count reported. If no eligible draw exists, CI=N/A. Never bootstrap individual Candidate rows as independent observations.
- For ordered asserted/directed-final relations, bootstrap by source canonical Event with all outgoing pairs together. Each unordered contradicts pair has one frozen owner: newer assertion Event when chronology is established, otherwise lexicographically smaller canonical Event URI. Record owners before predictions; reverse edges never create another bootstrap unit. Duplicate mention pairs use lexicographically smaller gold Event URI (same-Event pairs belong to that Event). Report dependence conventions and paired draws separately from RQ2/RQ3; ownership does not prove shared-endpoint pairs statistically independent.
- Split by canonical Event and time; known connected updates/clarifies/contradicts/supersedes families that would cross chronological boundaries are quarantined from final evaluation rather than leaking a story across splits. Record quarantined IDs. Final-evaluation inference always uses immutable cutoff snapshots and the calendar/reporting-period selection contract in EVENT_SCHEMA.md.

## Run manifest

Every run records ontology version, SHACL version, dictionary version, annotation guideline version, methodVersion, cutoff timezone, market calendar, staleness threshold, tau, epsilon, event windows, random seed, input manifest hash and output hash. For AR/CAR reproducibility, also record the market-data provider and dataset/snapshot ID or hash, adjusted-price/corporate-action adjustment convention and version, exchange, calendar ID/version/hash, benchmarkIndex URI, and reaction-validator version. For `IndustryExposure`, record `periodType` (baseline `YEAR`) and reporting scope (`consolidated` or `standalone`). Record the final chronological interval, target sample size, minimum support by `impactType`, and actual per-type support. Store validation totals and failures for observation ownership, date coverage/pairing, daily return recomputation, AR and CAR recomputation. A run with a missing or mismatched required session is invalid, not a partial-window result. Synthetic demo results are structural tests only and are excluded from RQ conclusions.
