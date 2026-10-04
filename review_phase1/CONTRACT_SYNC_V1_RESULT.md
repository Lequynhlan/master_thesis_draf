# Kết quả đồng bộ đặc tả Phase 2 với WFKG-SCORE-V1

## Scope

Đã thực hiện plan `.hermes/plans/2026-10-04_194436-sync-phase2-vertical-slice-v1.md`. Không triển khai crawler/model/metric executor hoặc chạy dữ liệu thật; không sửa ontology/dictionary/SHACL, không regenerate DOCX/PDF/Draw.io và không commit/push preexisting user edits.

Backups exact bytes + SHA256: `review_phase1/backups/before_contract_sync_V1_20261004_194436/`.

## Artifacts đã sửa

- `chỉnh sửa mới nhất - 01-10/EVENT_SCHEMA.md`: V1 component crosswalk, legacy boundary, sentence/trigger Evidence producer, per-target direction, Candidate/window-task lifecycle.
- `chỉnh sửa mới nhất - 01-10/EVALUATION_PROTOCOL.md`: V1 constants/origins, three execution profiles, training/diagnostic ownership, slice acceptance ledger, ablation no-op reporting, scheduled exposure variant.
- `chỉnh sửa mới nhất - 01-10/ANNOTATION_GUIDELINE.md`: gold độc lập model scores, trained-score prediction audit, exact registry linking, relation-origin convention, independent trigger/sentence gold and profile scope.
- `chỉnh sửa mới nhất - 01-10/SCORING_SPEC.md`: updated synchronization boundary, named trained reference adapter/mandatory trigger score; existing V1 numerical formulas unchanged.
- `chỉnh sửa mới nhất - 01-10/PHASE1_ACCEPTANCE.md`: current spec crosswalk distinct from historical 1.0.4 PDF/diagram/tests, no false whole-bundle readiness claim.
- Hai active vertical-slice plans: loại fallback/indirect-strength legacy khỏi active instructions, đồng bộ Evidence adapter/profile/score/lifecycle/gold ownership.

## Finding → đặc tả xử lý → required implementation evidence

| Review finding | Đã xử lý ở mức specification | Chưa thể kết luận runtime |
| --- | --- | --- |
| F1 strength/version mismatch | All four eligible V1 routes T=1; legacy/exposure tách riêng | Method-aware constants/config gate và real ranking vẫn cần implementation |
| F2 annotation producer mismatch | No A fallback; accepted exact L=1; automatic entry relation=.5, R=min origins | Decoder/registry/edge-origin audit tests chưa hiện thực trong pipeline |
| F3 thiếu slice acceptance | Integration / automatic slice / final profiles, outputs/coverage/replay gates | Chưa có 100–300 article automatic run hoặc real four-route coverage |
| F4 training/split ambiguity | train/dev_tuning, lock-validation, debug vs held-out diagnostics; Event/family leak protection | Chưa tạo labels/checkpoint/split dataset thực |
| F5 non-informative ablation | L no-op, R constant diagnostics; no unsupported importance claim | Chưa chạy RQ3/ablation thực |
| F6 direction/lifecycle | Dictionary per-target else UNKNOWN; readiness ANY linked valid window, per-window sidecar | Rule adapter/status transition executor chưa hiện thực |
| F7 calibration wording | Provenance/status, no calibrated probability prerequisite | Không có calibration experiment/results |
| F8 Evidence-anchor producer | V1-SENTENCE-TRIGGER-BIO; frozen original sentence table, mandatory trigger min, conditioned EAE and no fragment merging | Sentence splitter/checkpoint/offsets thực vẫn cần freeze/test; unsupported cross-sentence gold retained as miss |

## Execution thực tế

1. Baseline trước sửa: `python -B -m unittest discover -s 'chỉnh sửa mới nhất - 01-10/tools' -p 'test_*.py' -v`: 39 tests PASS (31 SHACL + 8 diagram), exit 0.
2. Sau sửa: cùng lệnh, 39 tests PASS, exit 0. Existing suites dùng fixtures synthetic trong bộ nhớ; không là real-data/model acceptance.
3. `python -B 'chỉnh sửa mới nhất - 01-10/tools/audit_schema_diagram.py' --json`: exit 0; 337 PASS, 0 FAIL, 57 NOT CHECKED, 44 SELECT parse. Audit không kiểm scoring prose/whole diagram semantics hoặc PDF.
4. `git diff --check`: exit 0, no whitespace errors tại lần kiểm tra.
5. Synthetic DIRECT compatibility check: required decision inputs giả định min A=.76, S=.5/L=1/R=.5/T=1 ⇒ confidence/candidate=.69, reactionWeight=.069 ở impact=.1; generic SHACL conformance PASS. Đây là arithmetic/shape diagnostic, không PhoBERT inference.
6. Negative method-policy control: đổi L=.5 và giữ arithmetic nhất quán vẫn generic SHACL PASS. Xác nhận shape không enforce V1 L=1; vì vậy method-aware runtime gate là bắt buộc, không claim shape pass đủ V1 correctness.
7. RDF/SHACL và Dictionary parse thành công; ontology giữ 22 OWL classes. Before/after hashes xác nhận ontology_v1.0.ttl, shapes_v1.0.ttl và EVENT_DICTIONARY.yaml không đổi.

Raw execution logs: `verification_contract_sync_V1_execution.json`. Before/after hashes: `verification_contract_sync_V1_hashes.json`.

## Review độc lập và hiệu đính tiếp

Một reviewer không tìm blocker về numerical crosswalk/scope; reviewer thứ hai phát hiện các producer/evaluator ambiguities. Đã tiếp tục xử lý:

- Typed mention matching dùng thêm exact triggerStartOffset/triggerEndOffset, không ghép hai Events cùng sentence/type theo arbitrary ID.
- Tách raw window assignments, emitted model mention inventory và Evidence inventory. Dedup theo exact sentence/trigger/type trước gold; complete output chọn max score/tie ID, all-incomplete group giữ một representative có missing-field ledger, không bịa score. Downstream registry failures không xóa prediction khỏi RQ1.
- Reference adapter yêu cầu toàn Evidence sentence nằm trong một window kể cả reserved tokens; subset supports nằm trong truncated window không cứu assignment.
- Required entity/identity links kiểm per assignment trước Evidence selection; optional route-entry/propagated links kiểm sau selection, route failure không chọn lại Evidence.
- Plan dùng đúng dev_tuning để chọn checkpoint, validation là lock set riêng.

Đã chạy Python contract scenario diagnostics cho same-sentence distinct triggers, overlapping windows/tie, required-link exclusion và sentence overflow: assertions PASS. Đây là kiểm tra tình huống của đặc tả, không production metric/model code. User correction: người dùng yêu cầu review ngôn ngữ/độ đồng nhất trước khi gửi thầy, không yêu cầu Việt hóa. Bản Việt hóa tự ý đã hoàn tác nguyên byte về SCORING_SPEC trước translation. Khuyến nghị English technical prose và các phần cần hiệu đính được ghi tại REVIEW_MD_SUPERVISOR_READINESS_LANGUAGE.md. Thứ tự required-link trước selection ở SCORING_SPEC vẫn cần đồng bộ với các đặc tả liên quan; không gọi bộ hoàn toàn nhất quán khi điểm này còn tồn tại.

## Boundary

Đây là đồng bộ specification Markdown và active plans, không xác nhận approval của thầy, model quality, observed live prediction, calibration, full-bundle graphical/report synchronization hoặc RQ conclusions. Supervisor-requested exposure-strength experiment vẫn giữ ở research milestone sau slice. Không cần rubric chấm mới hay additional ML models để chạy slice đã chọn.
