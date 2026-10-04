# Phase 1 package review and acceptance boundaries

Document version: 1.1.0
Active method: WFKG-SCORE-V1 (SCORING_SPEC.md 1.1.0)
Structural schema contract: ontology/SHACL 1.0.5
Review date: 2026-10-04

## Status

The Phase 1 specification and report/diagram route-strength wording have been synchronized. The active rule is **T=relationStrength: DIRECT=1.0; INDIRECT_INDUSTRY=0.5; INDIRECT_SUBSIDIARY=0.5; INDIRECT_LEADERSHIP=0.5**. These values are separate from **S=sourceConfidence=0.5** and **R=min(required edge supports)** (automatic evidenced support=0.5; eligible curated support=1.0).

The HDBank fixture contains one dividend Event, three Article resources and four Evidence resources; it intentionally has no Candidate or Reaction. Its SHACL/SPARQL record is useful for article/event/evidence queries, but it does not exercise relationStrength T, Candidate scoring, market reactions, or Phase 2 pipeline execution.

The current PDF has not been exported from the updated DOCX. The only PDF in this folder is marked superseded 1.0.4 and must not be sent as if it matched the current Word file. Therefore the package is **not yet a complete DOCX/PDF submission pair**. Export and inspect the current DOCX in Word, then update tools/phase1_package_manifest_1.1.0.json.

## Teacher-feedback crosswalk

| Feedback | Phase 1 artifact state and location | What is actually verified / remains |
| --- | --- | --- |
| 1. Align PDF, Draw.io and TTL; restrict the baseline to four paths | Four route identities remain in EVENT_SCHEMA.md; route topology is illustrated in Draw.io tab 05; ontology/SHACL remain the structural authority. Score labels distinguish WFKG-SCORE-V1 spec 1.1.0 from structural contract 1.0.5. | Draw.io XML parse passed. Dedicated property audit is blocked by missing rdflib; PDF render is pending. Diagram visual layout and full semantic review are not verified here. |
| 2. Daily effectiveTradingDate | EVENT_SCHEMA.md effective-trading-date rule and ontology effectiveTradingDate comments: first session whose open is strictly after Event.availableAt; cutoff remains earliest supporting Evidence availability. | Existing synthetic timestamp checks do not validate a real exchange calendar. Calendar/session validation belongs to Phase 2. |
| 3. Confidence components and freeze | SCORING_SPEC.md component/selection sections; EVENT_SCHEMA.md component table; ANNOTATION_GUIDELINE.md scoring note. S, A, L and R have separate producers and freeze at cutoff. Extraction/linking fallback scores are not used in V1. | SHACL rules specify structural score constraints, but the post-edit rerun is blocked by missing rdflib. They do not establish model calibration, registry correctness, Evidence-selection implementation or immutable pipeline snapshots. |
| 4. candidateScore versus reactionWeight | SCORING_SPEC.md sections 8–9; EVALUATION_PROTOCOL.md RQ3; Draw.io tabs 04–05. candidateScore is inference-time; reactionWeight is post-window. The T route map is explicit. | HDBank has no Candidate/Reaction; no score ranking or market response is claimed as tested. |
| 5. Reproducible market returns | ontology_v1.0.ttl, shapes_v1.0.ttl, and EVENT_SCHEMA.md Reaction/observation rules preserve close/return provenance and window inputs. | Synthetic SHACL regression is not vendor-data validation; exchange-calendar and market-source provenance remain Phase 2 checks. |
| 6. Event Dictionary before NLP | EVENT_DICTIONARY.yaml (14 event types) and ANNOTATION_GUIDELINE.md. | Dictionary checks are recorded in historical contract 1.0.5. No NLP extractor is implemented or validated by this package. |
| 7. Article cardinality and IndustryExposure selection | EVENT_SCHEMA.md staging/curated cardinality and temporal/IndustryExposure sections; SCORING_SPEC.md four-route inputs. V1 T remains INDIRECT_INDUSTRY=0.5; exposureStrength=exposureRatio is a separate Phase 2 comparison. | Structural rules do not prove production selects the latest eligible reporting-period record or applies calendar/staleness gates correctly. |
| 8. Freeze evaluation protocol | EVALUATION_PROTOCOL.md distinguishes integration diagnostic, automatic vertical slice and final RQ; ANNOTATION_GUIDELINE.md specifies independent annotation and relevance/direction. | No 100–300 article slice, double-label agreement, final metrics, bootstrap or RQ result is claimed here. Those are Phase 2 work. |
| 9. Draw.io property appendix | tools/audit_schema_diagram.py and tools/test_schema_diagram_audit.py compare the editable diagram inventory with TTL/SHACL, with explicit NOT CHECKED rows. | A passing structural audit is not a full semantic/visual review. Fresh audit status is recorded in the package manifest. |

## Verification boundaries

- tools/test_phase1_scoring_sync.py is a new standard-library regression for the active T map, S/R distinction, Word/Draw.io wording and unchanged HDBank fixture hashes. It is a document/arithmetic consistency check, not SHACL or pipeline evidence.
- tools/verification_contract_1.0.5.json is historical evidence from before this specification synchronization. Its recorded 32/32 SHACL tests, 8/8 diagram tests, 337 PASS / 0 FAIL / 57 NOT CHECKED and six HDBank queries are not fresh reruns after this update.
- In the current execution environment rdflib, pyshacl, python-docx and a Word/PDF exporter were unavailable. Current SHACL/HDBank validation and PDF layout inspection remain pending; see tools/phase1_package_manifest_1.1.0.json.
- No Phase 2 candidate-generation, real market-reaction, calendar, NLP, gold-set or RQ result is asserted.

## Advisor packet

Use submission_files and excluded_from_submission in tools/phase1_package_manifest_1.1.0.json; do not send the folder indiscriminately. The superseded PDF and old 1.0.4 verification record remain historical local artifacts, not current acceptance evidence. The current DOCX/PDF pair must be completed before calling the packet final.
