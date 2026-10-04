# Synchronize Phase 2 vertical-slice contracts Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task if available; otherwise execute directly and request independent review. User explicitly authorizes plan followed by execution in this turn.

**Goal:** Đồng bộ EVENT_SCHEMA, EVALUATION_PROTOCOL, ANNOTATION_GUIDELINE và các producer seams của SCORING_SPEC với WFKG-SCORE-V1 và luồng automatic four-route vertical slice.

**Architecture:** Không thêm ontology class/property hoặc model chấm rubric. Scoring spec là numerical method authority; TTL/SHACL vẫn là structural source of truth. Gate, score production, independent gold và research evaluation được tách. Slice acceptance khác full RQ evaluation; legacy/exposure variants giữ riêng.

**Tech Stack:** Markdown specifications, existing Python unittest/pySHACL regression tools; read-only verification and immutable backups.

---

## Scope and assumptions

Workspace: D:/project/master_thesis/01-10-2026.
Submission folder: chỉnh sửa mới nhất - 01-10.
Primary sources: supervisor feedback, current SCORING_SPEC 1.1.0/WFKG-SCORE-V1, preceding review REVEW findings F1–F8 and the user's chosen pipeline.

Current scoring file is already modified relative to git HEAD; preserve it and do not revert other user edits. Save before-edit backups/hash manifest. No crawler execution, training, data collection, full metric executor, PDF/DOCX/diagram regeneration or silent full-bundle acceptance. Do not auto-commit preexisting user scoring edits.

## Task 1: Baseline and backups

Files: all targeted Markdown sources; old active slice plans; PHASE1_ACCEPTANCE.md.
1. Inspect git status and tool commands.
2. Save exact-byte backups outside submission with SHA256 before/after tracking.
3. Run existing SHACL and diagram regression as baseline. Distinguish baseline failure from introduced failure.

## Task 2: Numerical/version crosswalk

Modify: EVENT_SCHEMA.md, EVALUATION_PROTOCOL.md, ANNOTATION_GUIDELINE.md.
- Version 1.1.0, active WFKG-SCORE-V1; structural ontology/shape stay separately versioned.
- S=.5, L=1 for eligible exact unique linking, T=1 for all routes; A from trained task decisions, no extraction fallback; R=min edge origin scores .5/1.
- No calibrated probability prerequisite; no threshold or alternate Evidence reselection.
- Legacy 1.0.4 and exposure-strength comparison remain separately versioned. Supervisor-requested exposure comparison scheduled after automatic slice; not claimed implemented or erased.
- V1 A/L/R ablations and constant/non-informative reporting; no change to shared population/gates.

## Task 3: Evaluation profiles and model data ownership

Modify: EVALUATION_PROTOCOL.md, ANNOTATION_GUIDELINE.md.
- Define INTEGRATION_DIAGNOSTIC, AUTOMATIC_VERTICAL_SLICE, FINAL_RQ profiles.
- 100–300 article diagnostic scope does not impose final support floors/full ablations/OWL relation metrics/calibration on first automatic integration.
- Maintain final gold, route projection, exact matching, double-label and CI contracts.
- Development train/dev-tuning subsets, separate lock validation, debug versus held-out diagnostic membership and leak prevention.
- Gold independent of model scores; train checkpoint/manifest provenance and supported type scope.
- Slice artifact/checklist, real route coverage versus executor regression, coverage/HOLD/market exclusions and replay.

## Task 4: Producer seams

Modify: EVENT_SCHEMA.md, SCORING_SPEC.md, ANNOTATION_GUIDELINE.md.
- Reference Evidence policy: frozen sentence boundary table from exact original text, trigger/event anchor selects containing sentence; roles must be supported within that complete sentence/window assignment. Record splitter version/table, original half-open offsets. Cross-sentence fragment mixing unsupported by reference adapter; separate adapter required. Unsupported diagnostic gold remains miss, never shrink population from model failures.
- Direction per Candidate: Dictionary rule and evidenced roles/selected facts; target-specific sign only when supported, else UNKNOWN; no CAR or generic type sign.
- Lifecycle transition table consistent with current shapes: terminal ready means at least one actual complete inverse-linked Reaction; per-window states in sidecar tasks. Candidate scores immutable; status changes in timestamped snapshots/logs.

## Task 5: Plans and acceptance boundary

Modify: existing two vertical-slice plans and PHASE1_ACCEPTANCE.md.
- Replace active fallback/indirect-strength descriptions with V1 references, retaining current scope.
- Mark old 1.0.4 report/diagram/demo evidence historical; add active contract crosswalk without pretending those artifacts regenerated.
- Add requirement→artifact→verification matrix; diagnostic failure is reportable, not final RQ evidence.

## Task 6: Verification and independent review

- Parse ontology/shapes/dictionary and preserve their hashes.
- Run `python -B -m unittest discover -s 'chỉnh sửa mới nhất - 01-10/tools' -p 'test_*.py' -v` from workspace using installed dependencies.
- Run structural diagram audit following tools/README.md, save output outside submission.
- Check git diff whitespace, read complete changed specs, inspect policy coherence and acceptance conditions.
- Use separate read-only reviewer for supervisor/scope compliance; fix concrete findings and re-run checks.
- Save execution verification report with commands/exit codes, before/after hashes, changed paths, checked versus not checked. Document tests do not prove pipeline/model performance.

## Risks and decisions

- Reference sentence-only Evidence reduces initial coverage; report misses and do not retrofit gold to predictions. Cross-sentence adapter is deferred/versioned.
- Industry exposure variant is deferred from slice, retained in Phase 2 research roadmap.
- Ready status applies any completed window; per-window sidecar is authoritative for each configured window.
- Structural shape may accept values without enforcing V1 constant/origin policy; method-aware runtime gates remain an implementation requirement.
- PDF/Draw.io/DOCX and demo code still may state legacy policies; explicit boundary remains until a separately scoped synchronization.
