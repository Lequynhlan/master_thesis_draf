# WFKG vertical slices: model, flow and effort Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task if available and after explicit implementation approval. This document authorizes no installation, training, crawling or code modification.

**Goal:** Làm rõ mốc tích hợp đầu tiên, slice đủ bốn routes và batch diagnostic; không đồng nhất với final evaluation luận văn.

**Architecture:** Python offline batch, snapshots JSONL/CSV và RDF Turtle; pretrained PhoBERT + task-trained ED/EAE heads cho extraction, registry/rules cho identity và routes, market-adjusted AR/CAR cho Reaction. Candidate snapshot tách Reaction hậu nghiệm.

**Tech Stack:** Đề xuất vinai/phobert-base, VnCoreNLP, PyTorch/Transformers, RDFLib/pySHACL; JSONL/CSV. Chưa cài/chạy stack hoặc kiểm GPU trong lượt này.

---

## Nguồn thực tế đã đọc

Workspace: D:/project/master_thesis/01-10-2026.
- ban_thay_gop_y/gop_y_phase1_truoc_code_phase2.txt (toàn bộ).
- chỉnh sửa mới nhất - 01-10/{EVENT_SCHEMA.md,SCORING_SPEC.md,EVENT_DICTIONARY.yaml} (toàn bộ), version 1.0.4.
- D:/project/master_thesis/code/vn30_bank_news/{README.md,src/vn30_bank_news/models.py,src/vn30_bank_news/extract.py}.
- Official README https://github.com/VinAIResearch/PhoBERT (raw fetch HTTP 200).

Crawler có code SQLite/raw HTML/JSONL và Article published_at/fetched_at/hash. extract.py là HTML->article parser, không phải ED/EAE. Chưa chạy lại crawler/tests, chưa audit toàn code hoặc chứng minh dataset hiện có đủ contract. Config ontology/taxonomy cũ không được thay source 1.0.4.

## Active scope và assumptions

Người dùng giữ PhoBERT extraction, bốn route executors, market alignment, AR/CAR và WFKG. Rule-only/DIRECT-only không thay delivery scope. DIRECT là thứ tự tích hợp.

Đề xuất một người làm, Python/ML cơ bản, agent hỗ trợ coding, có GPU dùng được cho fine-tuning, một số nguồn text/registry/giá/calendar truy cập hợp lệ. Không UI/server/distributed stack hoặc train model từ đầu. Ước lượng ban đầu tập trung batch 100–150 articles, vài eventTypes đủ tạo real coverage các paths; support cả 14 types và 300 bài không được tự coi đã nằm trong effort này. Cần user duyệt empirical type coverage; taxonomy/schema vẫn nguyên.

## Model quyết định đề xuất

- Family: Vietnamese pretrained transformer encoder PhoBERT.
- Variant/checkpoint: vinai/phobert-base (135M, 256 tokens, MIT). Không khẳng định tốt hơn base-v2; chọn để giảm biến số.
- VnCoreNLP chỉ segmentation. Giữ alignment segmentation/subwords->original immutable text.
- ED: event/trigger detection; phải cho phép zero/multiple events, không one-label-per-article.
- EAE: conditioned theo event instance/type/trigger, tìm argument spans. Có thể dùng token classification baseline, không cần CRF ngay.
- Fine-tune shared encoder + task heads từ development labels; xuất trained task checkpoint. Pretrained encoder nguyên bản không phải ready Event extractor; untrained heads không acceptance.
- Normalized dates/actions/periods, typed linking, occurrence ID, canonical key và route traversal không giao tất cả cho neural model.
- Evidence anchors là span thật có offsets; không mặc định attention=Evidence.
- Không train GAT/TFT/TabTransformer, sentiment/fusion model hoặc relation classifier mới. Confidence fallback theo contract, raw model scores lưu riêng.

## Flow

Crawl/reuse snapshot -> Article and timestamp policy -> segmentation/windows -> ED/EAE raw predictions -> original-text Evidence/role spans -> typed registry linking + normalization -> occurrence identity + canonical Event -> complete assignment at exact cutoff -> four eligible routes -> Candidate score + immutable audit -> exchange calendar + adjustedClose snapshots -> AR/CAR -> Reaction -> Turtle validation + report + replay.

Gold chỉ dùng development training/evaluator theo split; không truyền gold answers vào inference.

## Slice 0: Plumbing xuyên toàn luồng, assisted diagnostic

**Objective:** chứng minh seams và output trước khi model sẵn sàng, không báo ML result.
**Proposed files:** wfkg-pipeline/config/slice.yaml; wfkg-pipeline/src/wfkg_pipeline/{contracts.py,identity.py,candidates.py,calendar.py,reaction.py,writer.py}; wfkg-pipeline/tests/test_direct_integration.py.
- Chọn một case thật đủ required roles/identity, Company–Stock mapping và giá + calendar thật; EARNINGS là candidate đầu tiên nếu đủ occurrence identity.
- Input extraction gán tay chỉ ở fixture riêng, provenance ASSISTED; không trộn automatic run.
- DIRECT + [0,0] -> Candidate -> Reaction -> RDF -> recomputation.
- Fail tests cho thiếu required/identity, late fact, thiếu price; implement minimal seam rồi verify fixture pass.
**Acceptance:** real article/market inputs, valid artifact + independent arithmetic; chưa là ML end-to-end hoặc four-route acceptance.
**Budget indicative:** 18–30 giờ cho integration đầu tiên khi input đã đủ; là phần lồng trong total, không cộng thêm.

## Slice 1: Thay extraction fixture bằng PhoBERT trained output

**Objective:** automatic end-to-end đầu tiên.
**Proposed files:** wfkg-pipeline/src/wfkg_pipeline/{preprocess.py,extract.py,link.py}; wfkg-pipeline/training/{prepare.py,train.py}; wfkg-pipeline/tests/{test_offsets.py,test_multi_event.py,test_complete_assignment.py}.
- Freeze text, annotate initial supported types + negatives; split theo Event/duplicate cluster, không shuffle reprints sang test.
- Test repeated strings, segmented words, truncation/window overlap, multi-event association và missing role trước implementation.
- Train initial ED/EAE heads; chọn checkpoint bằng development validation, không held-out diagnostic.
- Integrate predictions và preserve raw scores/model versions. Một Article có thể không tạo Event/Candidate.
**Acceptance:** real trained inference artifact không sửa tay, held-out examples và failure ledger; không hứa F1/coverage.
**Indicative elapsed cumulative effort:** 50–90 giờ tới first automatic run, có thể kéo dài nếu label/identity/hardware không đủ. Không cộng vào total riêng.

## Slice 2: Đủ bốn route executors và temporal logic

**Proposed files:** wfkg-pipeline/src/wfkg_pipeline/{relations.py,snapshot.py}; wfkg-pipeline/tests/test_routes.py; wfkg-pipeline/data/registry/.
- Implement DIRECT trước; rồi subsidiary child->parent Stock, leadership leader->eligible position Company->Stock, industry->eligible Bank exposure->Stock.
- Một Event không phải chạy ra đủ bốn paths. Route thiếu fact hợp lệ phải empty.
- Latest available version before validity; no older-version rescue. Industry YEAR/scope/newest period/staleness riêng.
- Curated historical facts có original source/availability, không tạo giả facts để coverage.
- Positive/negative regression mỗi route. Synthetic tests tách real empirical coverage; thiếu case/fact thật thì báo route coverage chưa đạt.
**Acceptance:** four executors tested, real-case ledger cho mỗi path available; missing coverage explicit.

## Slice 3: Batch diagnostic và replay

**Proposed files:** wfkg-pipeline/src/wfkg_pipeline/{cli.py,evaluate.py}; wfkg-pipeline/tests/test_replay.py; docs/phase2/vertical-slice-run-report.md.
- Chạy batch 100–150 trước; 300 là mở rộng không tự đóng acceptance.
- [0,0] đầu tiên, sau đó [0,+1]/[0,+3]; retrospective [-1,+1] separate nếu làm.
- Report stages counts, exact field/link correctness trên held-out gold, unsupported types, HOLD reasons, route/Reaction coverage, confidence fallbacks.
- Validate using frozen TTL/SHACL inference=none + extra calendar/cutoff/identity gates.
- Replay fresh run folder: immutable inputs same -> semantic outputs same; volatile runtime/generatedAt metadata separated.
- Output proposed runs/<run_id>/{manifest.json,predictions.jsonl,staging.jsonl,candidates.ttl,reactions.ttl,wfkg.ttl,score_audit.jsonl,validation_report.json,run_report.md}.
- CLI usage chỉ publish sau implement; chưa có command run-vertical-slice thật trong lượt này.
**Acceptance:** batch artifacts/replay; chưa final RQ conclusions, calibration claim hoặc KG-RAG benchmark.

## Mandatory correctness gates

availableAt observed acquisition khác publishedAt. Historical snapshot lacking original acquisition phải declared publication-time proxy; không crawl hôm nay rồi giả fetchedAt lịch sử. Cutoff=earliest Event availability; late Evidence không cứu snapshot. Required roles cùng complete assignment; dates/identity không fabricate. Optional key missing MATCH_EXISTING_ELSE_HOLD. sourceConfidence=.5; uncalibrated evidenced extraction/link/fact=.5; verified curated typed mapping=1 convention; missing!=fallback. Candidate score average four confidence components times strength DIRECT1/indirect.5. Direction Event–Stock supported economic context else UNKNOWN; không eventType->fixed sign. Strict session-open day0/calendar thật. Stock/benchmark adjustedClose đủ predecessor và window; CAR không đưa vào ranking và không chứng minh causal impact. RDF writer preserve inverse links/lifecycle và provenance, không dùng SHACL repair.

## Rough effort estimate, not benchmark or commitment

Human focused effort, includes agent-assisted implementation/review; not GPU training wall time or external waiting.
- Contract/data/source audit + crawler adapter: 8–14 h.
- Initial labels + gold review, restricted empirical types: 24–40 h.
- PhoBERT preprocessing, ED/EAE, first fine-tuning/integration: 30–50 h.
- Linking/normalization/canonicalization: 8–14 h.
- Four routes + cutoff/provenance: 10–18 h.
- Calendar/market ingestion + AR/CAR: 10–18 h.
- RDF/SHACL/pipeline gates/audit: 14–22 h.
- Batch/replay/error report: 12–20 h.
Total computed 116–196 h. Planning buffer 25% ->145–245 h. At 6 focused h/day -> approximately24–41 workdays, about5–9 five-day workweeks. At15 h/week -> approximately10–17 weeks.

Không phải interval thống kê; không benchmark trên project. Các workstreams overlap (labels/registry/market cùng model integration), không cộng cumulative milestone estimates thêm lần nữa. Budget chỉ hợp lý nếu reuse crawler, limited initial label coverage, GPU accessible và market/registry sources ready. Labeling all14 types, full300 reviewed articles, two-annotator full protocol, no viable price provider, Windows stack incompatibility hoặc insufficient training data cần re-estimate. 100–300 articles slice không mặc nhiên đủ huấn luyện14 eventTypes. Chốt giờ thực tế sau initial mini-run.

## Open decisions before implementation

Nguồn adjustedClose/benchmark/calendar và availability mode; supported eventTypes đầu vòng (schema không đổi); training labels/annotators/GPU; tái sử dụng crawler qua adapter thay port ontology config cũ. Không cần mở rộng ontology hoặc triển khai RAG ngay để nối Candidate/Reaction slice. Full evaluation/ablation/KG-RAG là mốc sau.
