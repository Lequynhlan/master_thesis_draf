# EVALUATION_PROTOCOL.md

Version: 1.0.1

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
- separately, directed Event relation classification for `updates`, `clarifies`, `contradicts`, `supersedes`, `NONE`: per-label precision/recall/F1, micro/macro-F1 and exact-set accuracy over a frozen ordered Event-pair universe, including sampled NONE negatives recorded in the manifest. Multi-label relations are allowed; NONE is exclusive. Evaluate with gold canonical Event IDs to isolate relation classification; any end-to-end result is separately labeled.

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

## RQ3 — weighting and ranking

Compare unweighted score `1` against `candidateScore` at inference cutoff. `reactionWeight` is reported only as post-window descriptive analysis and is never used as a ranking feature for the cutoff evaluation. Report nDCG@5/@10, Precision@K, paired Event-level comparison, component ablations and confidence intervals. Labels are independent of score and CAR.

## Reproducibility

## Frozen metric and sampling contract

- Gold relevance is 0/1/2 by degree of supported relevance, independent of `impactType` and direct mention. Binary positive means `relevance >= 1`. UNKNOWN direction is not uncertain relevance. UNRESOLVED relevance is excluded before scoring from the common gold/ranking universe for every method and reported separately; unjudged pairs must not be silently treated as negative. Construct the same fully adjudicated Stock universe per Event, independently of the compared method outputs; report its coverage and exclusions.
- Aggregate paths to one `(Event, Stock)` with maximum pre-cutoff score. Use score descending, Stock URI ascending for all methods, including constant score=1; tied representative paths use Candidate URI ascending. No CAR or reactionWeight tie-break. Do not pad rankings with unreturned Stocks; absent returned slots score zero.
- Fixed K is 5 or 10. `Precision@K = relevant_returned_in_top_K / K` even when fewer than K Candidates exist. `Recall@K = relevant_returned_in_top_K / total_gold_positives` in that Event's fixed resolved universe; not merely positives among retrieved Candidates.
- `DCG@K = sum((2**relevance - 1) / log2(rank + 1))` for ranks starting at 1; unreturned slots have zero gain. IDCG uses the ideal ordering of the full resolved gold universe, not just retrieved Candidates. nDCG = DCG/IDCG.
- An Event with zero gold positives still contributes Precision@K (0) and false-positive counts; Recall@K and nDCG are N/A and excluded from those macro means, with excluded Event counts reported. An Event with no resolved pairs is excluded from all metrics and counted separately. An Event with positives but no returned Candidates has P@K=R@K=nDCG=0. For pair-level metrics: no returned positives => precision=0; no gold positives => recall/F1=N/A; otherwise F1=0 if P+R=0. Report micro counts plus per-Event macro; never average undefined values as zero.
- Macro means give equal weight to each eligible canonical Event, not to paths, articles or number of candidates. Per-impactType results use independently annotated supported path strata; a pair may occur in multiple strata, but counts once in overall metrics. Report overlaps and support; strata totals are not additive. Direct-mention strata use text labels, not automatically `impactType=DIRECT`.
- Confidence intervals: paired bootstrap of canonical Events with replacement, 2000 replicates, seed 20260930; keep all Stocks, paths, mentions and labels of a sampled Event together and use the same draws across methods. Report 2.5/97.5 percentile intervals and paired metric differences. Recompute micro counts/eligible macro means within each draw; undefined draws are omitted and their count reported. If no eligible draw exists, CI=N/A. Never bootstrap individual Candidate rows as independent observations.
- For cross-Event relation classification, bootstrap by the newer/source canonical Event, keeping all its outgoing labeled pairs together; for duplicate mention-pair metrics, assign each pair to a deterministic owner (lexicographically smaller gold Event URI; same-Event pairs to that Event) and keep that block together. Report these dependence conventions separately from RQ2/RQ3 Event bootstrap.
- Split by canonical Event and time; known connected updates/clarifies/contradicts/supersedes families that would cross chronological boundaries are quarantined from final evaluation rather than leaking a story across splits. Record quarantined IDs. Final-evaluation inference always uses immutable cutoff snapshots and the calendar/reporting-period selection contract in EVENT_SCHEMA.md.

## Run manifest

Every run records ontology version, SHACL version, dictionary version, annotation guideline version, methodVersion, cutoff timezone, market calendar, staleness threshold, tau, epsilon, event windows, random seed, input manifest hash and output hash. Synthetic demo results are structural tests only and are excluded from RQ conclusions.
