# WFKG vertical slice end-to-end Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task, if available and after user approval. This document is a proposal, not authorization to implement, install, train, commit or push.

**Goal hiện tại (phạm vi user chọn):** Chạy end-to-end đơn giản nhưng có crawler, extractor PhoBERT task-trained, registry, bốn route executors và Reaction thật; ưu tiên có artifacts và thấy lỗi trước tối ưu hiệu năng. Có thể debug từ batch nhỏ rồi đạt 100–300 articles theo protocol; không kết luận RQ trên slice.

## Phạm vi đã chọn: đầy đủ chuỗi xử lý, đơn giản ở từng khâu

- Bắt buộc: crawler tối thiểu/lưu raw text + timestamps/availability provenance; PhoBERT event/argument extraction chạy thật; registry linking; bốn relation path executors; market/calendar inputs; AR/CAR; materialize WFKG và run outputs.
- PhoBERT là encoder + trained ED/EAE heads. Chưa cần tối ưu/hyperparameter search, nhưng nếu chỉ có pretrained encoder thì vẫn cần task checkpoint phù hợp hoặc initial development fine-tune. Random/untrained head không phải extractor hợp lệ. Rule/manual fixtures chỉ hỗ trợ integration tests, không thay PhoBERT trong acceptance user chọn.
- Active scoring: WFKG-SCORE-V1, các Markdown spec document version 1.1.0. S=.5, L=1 sau exact-unique typed linking gate, T=1 mọi route; A từ trained required neural/deterministic decisions, không extraction fallback; R=min edge origins automatic .5/curated 1. Full vectors và audit lưu để replay, không gọi là calibrated probability. Direction theo Dictionary và target Stock, thiếu căn cứ => UNKNOWN.
- Registry curated nhỏ, file snapshots và offline batch; chưa cần UI/DB server/crawler đa nguồn. Canonicalization làm hẹp theo exact normalized keys và evidenced occurrence registry; chưa fuzzy clustering, nhưng không dùng URL/ngày bài làm occurrence identity hoặc ghép Events khác nhau. Ambiguous key => HOLD.
- Thực thi đủ bốn routes nhưng không bắt mỗi Event sinh bốn Candidates. Missing/stale/future/unsupported route facts => suppress + reason ledger. Dữ liệu thật chưa cover route nào phải báo thiếu, synthetic tests không thay empirical coverage.
- CrawledAt/ingestedAt/publishedAt lưu riêng; availableAt theo declared observed/proxy mode. Không gán crawl hôm nay vào availability quá khứ hoặc bịa timestamp.
- Giữ offsets, required-role/typed-link gates, immutable earliest cutoff, Company != Stock, calendar/day 0, adjustedClose benchmark/Stock provenance và basic validators. Candidate history không được sửa bằng late Evidence hoặc CAR.
- Hoãn tối ưu PhoBERT, so nhiều models, GAT/TFT/TabTransformer, LLM fusion, deep calibration, KG-RAG/full RAG benchmarks, toàn bộ ablations và confirmatory evaluation. Không tự coi deferred models là yêu cầu tương lai của WFKG.
- Có thể nối DIRECT + [0,0] trước như thứ tự code nội bộ, sau đó mở ba indirect routes trước acceptance phạm vi này. Mini-run không được báo đã hoàn tất bốn-route slice.
- Qua mốc khi batch thật có artifact ở từng stage, WFKG hợp lệ cho records được nhận, rejects/coverage lý do công khai, AR/CAR tính lại được và replay semantic outputs tương đương. Extraction thấp/coverage miss nhiều là diagnostic outcome chấp nhận được; sai contract/dữ liệu bịa không phải "kết quả chưa tốt" chấp nhận được.

Các Task 1–7 là roadmap chi tiết. Basic validation bắt buộc để output đúng; full annotation/evaluator/comparator/ablation acceptance thực hiện theo mốc protocol về sau, không chặn lần debug đầu.

**Architecture:** Offline artifact pipeline. Tách model predictions/staging, typed registry/canonical Event graph, immutable cutoff Candidate snapshot, post-window Reaction và evaluator độc lập. Không để giá/gold đi vào inference, không mở rộng ontology.

**Tech Stack:** Đề xuất Python; VnCoreNLP + PhoBERT-base với task heads đã fine-tune; RDFLib/pySHACL/OWL-RL; JSONL/CSV/Turtle. Package versions, hardware feasibility, model checkpoint, sources, license và training budget chưa chốt; không khẳng định đã cài/chạy.

---

## Nguồn và trạng thái

- Source of truth: `chỉnh sửa mới nhất - 01-10/{EVENT_SCHEMA.md,SCORING_SPEC.md,EVALUATION_PROTOCOL.md,ANNOTATION_GUIDELINE.md,EVENT_DICTIONARY.yaml,ontology_v1.0.ttl,shapes_v1.0.ttl}`.
- Đã đọc kế hoạch `phase2/2026-10-04_102105-wfkg-phase2.md`. Kế hoạch cũ dòng 77 đề xuất spike rule/LLM chưa fine-tune; user hiện chọn PhoBERT và bốn routes cho slice đơn giản. Checkpoint/nguồn/budget chưa chốt, chưa implementation. Không âm thầm sửa kế hoạch cũ.
- Đây là work breakdown/flow, chưa là implementation spec API/hyperparameters. Paths mới bên dưới là đề xuất, không phải files đã tồn tại.
- 22 classes, 14 eventType, bốn route giữ nguyên. Có thể triển khai từng type/route để tích hợp, nhưng phải báo unsupported types và empirical coverage; mini-run không thay acceptance 100–300 articles.
- Giả định bước đầu replay dữ liệu lịch sử; availability mode phải ghi rõ observed acquisition hay publication-time proxy. Không giả live hoặc tự tạo timestamps.

## Domain flow

`NewsArticle -> Evidence + raw Event/role predictions -> typed entity/reference resolution + normalization -> canonical Event -> selected complete assignment at exact cutoff -> eligible four paths -> EventStockCandidate + ranking -> market/calendar snapshots -> EventStockReaction -> validation + diagnostic evaluation + replay report`.

Hai nhánh dữ liệu đi vào giữa flow:
1. Company/Stock/Industry/CorporateLeader/GovernmentOrganization registry và Company–Stock, SubsidiaryRelation, LeadershipPosition, IndustryExposure historical facts.
2. Exchange sessions, Stock/benchmark adjustedClose, source/availability metadata.

Gold đi vào train chỉ trong declared training split, và evaluator trong declared evaluation split. Không dùng gold IDs/labels để generate automatic inference predictions. Occurrence/role metadata không tự thêm RDF classes/properties.

## Task 1: Freeze input contract và nguồn

**Objective:** Có inputs tái lập trước model/code.
**Proposed files:** `wfkg-pipeline/config/vertical_slice.yaml`, `docs/phase2/data-source-register.md`, `docs/phase2/spec-lock.md`; input manifest trong `wfkg-pipeline/data/`.

- Ghi spec hashes, methodVersion, sources/rights, article interval, benchmark, exchange/calendar version và price adjustment convention.
- Chọn Stock frame/common evaluation universe độc lập outputs/CAR.
- Snapshot text nguyên gốc, hash, Article ID, URL/source, publishedAt/availableAt với timezone. Không sửa text sau gán offsets.
- Đủ dữ liệu historical registry/facts, không lấy trạng thái hiện tại rồi gán hiệu lực quá khứ.
**Acceptance:** Một Article/fact/price đều truy về source và snapshot; thiếu calendar hoặc adjustedClose thật là blocker, không fabricate.

## Task 2: Gold và nhãn development

**Objective:** Train extractor và kiểm output trên gold độc lập.
**Proposed files:** `wfkg-pipeline/data/gold/`, `docs/phase2/annotation-report.md`, `wfkg-pipeline/data/splits.json`.

- 100–300 articles cho slice cuối theo protocol; bắt đầu mini-batch nhỏ để debug không gọi là complete acceptance.
- Nhãn Evidence anchors, eventType, role spans/normalized literals, typed entities, business occurrence identity và duplicate/Event relations.
- Có no-event, multi-event, rumor/completion, duplicates và missing-information cases; selection không chỉ successes.
- Development train/tune tách diagnostic held-out articles/Event clusters. Không fine-tune trên chính labels rồi báo output ấy là held-out.
- Gold dùng cho báo cáo automatic quality: ít nhất 25% độc lập hai annotator/adjudication theo guideline, chốt unit/subset/alignment trước thực hiện. Assisted plumbing không có gold gate chỉ là INTEGRATION_DIAGNOSTIC. Train/dev-tuning, lock-validation và held-out diagnostic/final tách theo Event/family; thiếu nhân lực thì ghi rõ quality gate chưa đạt.
**Acceptance:** Labels có offsets/hash/version và provenance, outputs không nhận gold labels. Support mỗi type công khai; không tuyên bố cỡ slice đủ train cả 14 types.

## Task 3: PhoBERT extraction adapter

**Objective:** Sinh raw predictions thực sự từ trained task checkpoint.
**Proposed files:** `wfkg-pipeline/src/wfkg_pipeline/extract.py`, `wfkg-pipeline/tests/test_extract_alignment.py`; `runs/<run_id>/predictions.jsonl`.

- VnCoreNLP segmentation, word/subword alignment về Unicode codepoint offsets [start,end) trên text gốc.
- PhoBERT-base + ED head + event-conditioned EAE head; fine-tune development labels hoặc kiểm task checkpoint phù hợp. Random/untrained head không đạt acceptance.
- Reference V1-SENTENCE-TRIGGER-BIO: frozen automatic original-text sentence table; ED BIO trigger + instance EventType, conditioned EAE; trigger score bắt buộc trong min. Evidence là whole containing sentence, không trigger span/attention. Không ghép required roles giữa windows/sentences; test sentence overflow/cross-sentence coverage misses theo EVENT_SCHEMA.
- Xuất eventType, Evidence span, role values/spans, raw logits/scores, model/tokenizer/segmenter versions. Không gọi embeddings/MLM scores là event confidence.
- Có thể tích hợp first EARNINGS hoặc DIVIDEND dễ kiểm, nhưng dùng đúng required roles và canonical-key rules; không mặc định DIVIDEND record_date vắng thì được mint key mới.
**Tests:** Duplicate strings offsets, subword split, no event, two events, cut window, unsupported type, missing roles. Viết failing fixture -> minimal code -> passing test cho từng behavior.
**Acceptance:** Model inference chạy thật và output artifact; không sửa predictions thủ công rồi báo automatic metrics. Assisted run nếu có phải lưu riêng.

## Task 4: Normalization, linking, identity và complete assignment

**Objective:** Từ prediction tạo domain Event hợp lệ, không chỉ JSON đủ field.
**Proposed files:** `wfkg-pipeline/src/wfkg_pipeline/{link.py,identity.py}`, `wfkg-pipeline/tests/test_identity.py`; `runs/<run_id>/{staging.jsonl,asserted.ttl,assignment_audit.jsonl}`.

- Normalize actions/periods/dates/references theo Dictionary; occurrence_id đến từ original assertion/document/business-occurrence registry có support, không article URL/publication day.
- Link đúng typed URI; Company != Stock; alias ambiguous => HOLD.
- Kiểm all required roles bằng same Evidence assignment; thiếu/unmapped required => staging, không fallback để invent values.
- Optional-key missing theo MATCH_EXISTING_ELSE_HOLD; reprint giữ Event URI; substantive update là Event mới, không merge theo company/type chung.
- Freeze earliest supporting Evidence availableAt làm cutoff; required entity/identity linking kiểm per assignment trước selection, rồi chọn complete eligible assignment max A, URI/assignment tie-break. Optional route-entry links kiểm sau chọn; không chọn lại Evidence để cứu route. Late Evidence không cứu snapshot; empty Candidate ranking giữ coverage miss.
- Supported deterministic role/occurrence decision 1 là convention; A=min required trained decisions gồm trigger/type/roles. Exact unique typed link => L=1, ambiguous/fuzzy-only => HOLD. S=.5; Event-entry automatic relation support .5, curated eligible fact 1; R=min required edges; T=1 tất cả routes. Không reuse A làm edge support, không extraction/linking fallback.
**Tests:** Reprints, same-company different occurrences, optional-key missing, unmapped action, buyer/target swapped, late complete Evidence, assignment/Evidence score ties.
**Acceptance:** Selected assignment/audit truy vết đủ; trained task score accessors và frozen selection đúng V1; đầy đủ logits/offset/decision manifests để replay.

## Task 5: Temporal graph và bốn Candidate routes

**Objective:** Candidate đúng path và historical eligibility.
**Proposed files:** `wfkg-pipeline/src/wfkg_pipeline/{relations.py,snapshot.py,candidates.py}`, tests tương ứng; `runs/<run_id>/{candidates.ttl,route_audit.jsonl,rankings.csv}`.

- Bắt đầu DIRECT: Event -> Company -> Stock; nối toàn bộ Reaction flow trước khi mở rộng.
- SUBSIDIARY: Event -> child -> selected relation -> parent -> parent's Stock; RDF owner relation là parent.
- LEADERSHIP: Event -> leader -> selected eligible position -> company -> Stock; future-effective appointment không tự tạo eligible position tại cutoff.
- INDUSTRY: Event -> Industry -> eligible IndustryExposure -> Bank -> Stock; không broadcast mọi Company cùng Industry, không thêm government-policy route mới.
- Tenure relations chọn latest cutoff-available version theo business key trước validity; no fallback older. Exposure YEAR/scope/newest period/staleness theo schema.
- Lưu một Candidate/path, four components, strength, cutoff/methodVersion/provenance. Mean components và candidateScore giữ đúng SCORING_SPEC; relationConfidence dùng min input table, không automatically 1 vì rule hợp lệ.
- Aggregate max per Event/Stock/method/cutoff; route projection trước per-type top-K. Giữ inverse graph links; SHACL inference=none không repair graph.
- Asserted updates/clarifies/contradicts/supersedes và OWL-RL là nhánh riêng, không phải bốn Stock routes. Basic identity/duplicate và existing structural relation regression giữ bắt buộc; full relation-classification/OWL semantic performance evaluation hoãn FINAL_RQ, không thêm relation model vào slice.
**Tests:** Pos/neg mỗi route, missing mapping, future fact, ended/future tenure, stale exposure, wrong parent owner, inverse links, tie-break.
**Acceptance:** Four-route regression dương/âm và real coverage ledger. Không đủ facts thật route nào => báo chưa đạt empirical coverage route đó, không fake facts.

## Task 6: Calendar và Reaction

**Objective:** Chứng minh outputs hậu nghiệm tính lại được mà không sửa Candidate.
**Proposed files:** `wfkg-pipeline/src/wfkg_pipeline/{calendar.py,reaction.py}`, tests; `runs/<run_id>/{observations.ttl,reactions.ttl,reaction_audit.jsonl}`.

- Day 0 first exchange session open strictly after Event.availableAt; calendar không weekday approximation.
- Tích hợp [0,0] trước, cần predecessor + t0 Stock và benchmark adjustedClose.
- Thêm [0,+1], [0,+3]; [-1,+1] retrospective robustness riêng.
- Compute returns -> AR(i,0), daily ARs -> window CAR -> impactScore/reactionWeight/signedWeight theo baseline tau/epsilon.
- Verify exact asset/benchmark/date coverage, availability, full completed window, arithmetic tolerance 1e-9; publish inverse links/lifecycle theo shapes. REACTION_READY là có ít nhất một valid linked completed Reaction; trạng thái từng window trong sidecar, pending window khác không sửa score hoặc xóa valid Reaction.
**Tests:** At-open/intraday/holiday, missing predecessor, missing session, wrong benchmark, cache wrong, adjustedClose<=0, available late.
**Acceptance:** Independent recomputation pass, immutable Candidate unchanged. Missing prices fail Reaction task; không xóa ranking gold Event. AR/CAR không chứng minh nhân quả.

## Task 7: Validation, diagnostic evaluation và one-command replay

**Objective:** Deliver working artifacts, not screenshots only.
**Proposed files:** `wfkg-pipeline/src/wfkg_pipeline/{baselines.py,evaluate.py,cli.py}`, integration/replay tests; `docs/phase2/vertical-slice-report.md`.

- Keep existing SHACL/diagram regression; thêm pipeline gates calendar/identity/eligibility mà SHACL chưa cover.
- RQ1 exact matching và missing/duplicate outputs counts; linking oracle diagnostic tách automatic end-to-end.
- Keyword full-text aliases, DIRECT-only, four-path score=1 shared extractor/assignment/Stock universe; weighted Candidate ranking chẩn đoán riêng RQ3. Prices/CAR không đi vào inputs/gold relevance.
- Unit-test metrics dùng independent expected fixtures; report support, failures/coverage/score distributions và real held-out diagnostic metrics. Constant L/R ablation có thể no-op/non-informative, không chứng minh component vô ích hoặc confidence đã calibration. Full comparator/ablation/bootstrap không là prerequisite automatic slice.
- Log article/Evidence/Event/Candidate/Reaction counts từng stage, failures reason, runtime, checkpoints/spec/data hashes.
- Một CLI batch đề xuất `run-vertical-slice` nhưng chưa có command thật; chỉ ghi usage sau implement. Replay fresh run directory; semantic outputs same, volatile generatedAt/runtime audit khác được giải thích.
**Existing verification commands:** từ workspace dùng interpreter có deps: `python -B 'chỉnh sửa mới nhất - 01-10/tools/test_baseline_shacl.py'`, tương tự `test_schema_diagram_audit.py` và `audit_schema_diagram.py`. Đây không phải pipeline commands và chưa chạy lại trong lượt lập plan.
**Acceptance:** Actual run artifacts, validate reports, replay evidence và limits; no final RQ conclusion.

## Trình tự demo nhỏ -> slice đầy đủ

1. Một EARNINGS/DIVIDEND case thật đủ Dictionary identity, DIRECT -> [0,0] Reaction, end-to-end artifacts. Không có checkpoint thì manual/rule integration fixture chỉ là assisted plumbing diagnostic, không gọi ML end-to-end.
2. Negative/duplicate/missing data cases, offsets và evaluator.
3. Mở rộng ba indirect routes với facts lịch sử thật và configured windows; giữ basic identity/regression, full assertion/inference relation evaluation là mốc FINAL_RQ riêng.
4. Batch 100–300 articles, independent gold diagnostics và replay/report; comparator rankings là exploratory optional. Exposure-strength comparison của thầy giữ thành research experiment sau automatic slice, method riêng. Acceptance profiles và ledger theo EVALUATION_PROTOCOL 1.1.0.

## Ngoài phạm vi ngay lúc này

Không UI, distributed infrastructure, source trust model, nhiều encoder search, train PhoBERT from scratch hoặc calibration claim không có labels. KG-RAG vs Vector RAG là một slice/acceptance riêng nếu roadmap luận văn yêu cầu; flow Candidate/Reaction này không tự chứng minh RAG và không tự loại mục tiêu RAG khỏi đề tài.

## Phê duyệt còn cần khi triển khai

Approval spec, nguồn text/market/calendar và availability mode; PhoBERT fine-tuning/checkpoint/data/budget; gold annotators; empirical route coverage. Không hứa deadline hay F1 khi chưa mini-run. Các quyết định này không ngăn việc dùng plan để hiểu flow, nhưng phải giải quyết trước execution.
