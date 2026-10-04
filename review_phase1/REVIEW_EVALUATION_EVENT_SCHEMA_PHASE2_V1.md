# Review EVALUATION_PROTOCOL / EVENT_SCHEMA cho vertical slice Phase 2

## Phạm vi và kết luận

Review read-only hai đặc tả; không sửa submission, không chạy pipeline hoặc tuyên bố implementation/RQ results. `evaluation.md` được hiểu là `chỉnh sửa mới nhất - 01-10/EVALUATION_PROTOCOL.md`, vì không tìm thấy file evaluation.md riêng trong phạm vi discovery.

Không có skill tên brainstorming trong catalog hiện có; sử dụng document-driven-planning và domain-modeling để đối chiếu yêu cầu, phân loại mâu thuẫn và thử tình huống biên.

Kết luận: lõi domain/temporal/provenance và protocol RQ đã khá chặt, nhưng hai file vẫn ở contract 1.0.4, chưa đồng bộ active SCORING_SPEC 1.1.0 / WFKG-SCORE-V1. Chưa thể gọi bộ đặc tả đã chốt thống nhất để acceptance Phase 2. Không cần thêm rubric scoring hoặc mở rộng ontology; cần đồng bộ numerical policy, tách slice acceptance khỏi full research evaluation và bổ sung các producer/manifest còn thiếu.

## Nguồn đã đọc

- ban_thay_gop_y/gop_y_phase1_truoc_code_phase2.txt: toàn bộ 171 dòng.
- chỉnh sửa mới nhất - 01-10/EVALUATION_PROTOCOL.md: toàn bộ 147 dòng.
- chỉnh sửa mới nhất - 01-10/EVENT_SCHEMA.md: toàn bộ 132 dòng.
- chỉnh sửa mới nhất - 01-10/SCORING_SPEC.md: toàn bộ nội dung qua các lượt đọc hiện tại; 315 dòng.
- chỉnh sửa mới nhất - 01-10/ANNOTATION_GUIDELINE.md: toàn bộ 69 dòng.
- .hermes/plans/2026-10-04_182458-wfkg-vertical-slices-model-flow-effort.md: toàn bộ 112 dòng; là secondary plan, không ghi đè current scoring contract.
- ontology_v1.0.ttl, shapes_v1.0.ttl, PHASE1_ACCEPTANCE.md: chỉ kiểm tra các đoạn liên quan bằng targeted inspection, không audit toàn bundle/PDF/Draw.io.

Luồng người dùng chốt: crawl/lưu text + availableAt → task-trained PhoBERT ED/EAE → Evidence/required roles → normalization/identity/registry linking → bốn route executors → Candidate V1/audit → calendar/Stock+benchmark adjustedClose → AR/CAR/Reaction → WFKG/validation/replay. Direction dùng Dictionary rules; canonicalization đủ đúng để chạy. Hoãn calibration sâu, multi-model/fusion, toàn bộ ablations và KG-RAG benchmark.

## Ma trận yêu cầu của thầy

| Góp ý | Evidence hiện có | Đánh giá trong phạm vi review |
|---|---|---|
| 1/9. Bốn routes, source of truth và đồng bộ artifacts | EVENT_SCHEMA 30–39; SCORING 27,315 | Routes đúng phạm vi. Numerical policy đang lệch; không kết luận PDF/Draw.io/TTL đồng bộ toàn bộ. |
| 2. Daily day 0 | EVENT_SCHEMA 86–95; EVALUATION 29 | Đúng strict-after-open, đúng open chuyển phiên sau; calendar thật vẫn phải triển khai. |
| 3. Score breakdown và freeze | SCORING 31–44,208–244; EVALUATION 121–125 | Breakdown/audit V1 rõ; evaluation/annotation còn policy legacy. |
| 4. Candidate vs Reaction | EVENT_SCHEMA 41–48; EVALUATION 115 | Đúng tách inference ranking và post-window analysis. |
| 5. Recompute AR/CAR | EVENT_SCHEMA 56–64; EVALUATION 147 | Đủ nguyên tắc adjustedClose, predecessor, ownership, full sessions và snapshot. |
| 6. Event Dictionary | EVENT_SCHEMA 118–124; EVALUATION 51–56 | Có tham chiếu roles/identity. Review này không audit toàn Dictionary. |
| 7. Raw cardinality/exposure/variant | EVENT_SCHEMA 19,111–116; EVALUATION 121 | Raw 0..* và exposure selection đúng hướng. Exposure variant của góp ý phải giữ riêng, không silently bỏ hoặc trộn V1. |
| 8. Slice vs final evaluation | EVALUATION 7–12,25,101–103,139 | Có dataset separation, 25% double-label, per-route/macro. Thiếu acceptance package riêng cho slice. |

## Findings

### F1 — P0, mâu thuẫn confirmed: relationStrength

- EVENT_SCHEMA:39 khóa DIRECT=1.0, ba indirect=0.5.
- SCORING:44,193–206 khóa T=1.0 cho mọi eligible route của V1.
- EVALUATION:121 gọi bảng strength của SCORING 1.0.4 là frozen baseline.

Ví dụ cùng một INDIRECT_SUBSIDIARY Candidate: route vẫn hợp lệ nhưng hai spec cho hai strengths khác nhau, kéo theo candidateScore và reactionWeight khác nhau.

Đề xuất: ghi active method WFKG-SCORE-V1 và T=1.0 trong schema/evaluation; đưa legacy strength và industry-strength comparison sang method riêng. Không chỉ đổi số version ở đầu file. Góp ý thầy:118 vẫn yêu cầu ít nhất một exposure-strength comparison trong Phase 2; có thể hoãn sau slice, nhưng phải ghi rõ milestone/variant và xác nhận thay đổi scope nếu loại hẳn.

### F2 — P0, mâu thuẫn confirmed: annotation/scoring producer

- ANNOTATION:45 còn automatic decision/path fact fallback 0.5 và Event-entry support dùng original assignment score.
- SCORING:111 không extraction fallback; :140–149 chỉ exact unique linking, L=1; :176 automatic Event-entry edge support=0.5, không copy A.
- EVALUATION:25,89 phụ thuộc annotation/selected scoring assignment nên mâu thuẫn ảnh hưởng gold audit và comparator manifest.

Đề xuất: đồng bộ annotation policy với V1; phân biệt gold labels do người gán độc lập với score audit của method. Không đưa model confidence vào tiêu chí để người gán quyết định gold correctness/relevance.

### F3 — P1, thiếu operational contract: slice acceptance

- EVALUATION:7 chỉ mô tả 100–300 articles smoke/debug.
- Các phần :47,64,70 yêu cầu asserted/inferred Event-relation evaluation không optional; :103 support floors và :115–125 full ablations là research contracts.
- Luồng người dùng muốn initial ED/EAE training, bốn routes, đơn giản confidence/direction/canonicalization, chưa full evaluation.

Đề xuất thêm ba profiles trong cùng protocol: integration diagnostic; vertical-slice acceptance; final RQ evaluation. Không xóa các full RQ contracts, không bắt chạy đủ chúng mới được chứng minh integration.

Slice acceptance cần manifest: raw/usable articles, supported types, automatic Event/role outputs, no-event/unsupported/HOLD counts, complete assignments tại cutoff, per-route candidates/suppress reasons, Reaction-ready/pending/missing counts, validators và replay. Không đặt F1 tối thiểu chưa có cơ sở, không ép mỗi Event sinh đủ bốn routes. Regression cho bốn executors là bắt buộc; real-case coverage theo route phải báo riêng, synthetic không thay empirical coverage. Chưa có real case của route thì không claim empirical acceptance cho route đó.

### F4 — P1, thiếu rõ: train/development/validation/diagnostic split

- EVALUATION:8–10 định nghĩa development để tune và validation dùng once lock; không nêu training split/subsplit cho initial PhoBERT ED/EAE task training.
- :12,141 đã bảo vệ canonical Event/story families; cần giữ.

Đề xuất: development có train và dev-tuning subsets; validation riêng để khóa config; vertical_slice phân tách assisted/debug cases và held-out automatic diagnostic. Lưu checkpoint hash, heads, tokenizer/segmentation/decoder/adapter, supported eventTypes, train/dev/validation Event IDs và text hashes. Nếu debug/tune trên slice thì ghi đúng là debug, không gọi held-out performance. Không dùng 100–300 articles như mặc định đủ huấn luyện toàn taxonomy.

### F5 — P1, ablation non-informative và variant scope

- EVALUATION:123 yêu cầu A/L/R neutralization, chưa nói V1 linking L luôn 1.
- SCORING:295–298 nói L ablation không đổi; R có thể constant 0.5 ở automatic population; S và T constant.

Đề xuất: thêm constant-component diagnostics; L neutralization là reproducibility/no-op check, không bằng chứng linker vô ích. R ablation không đổi ranking khi R constant trên cùng population phải báo non-informative. Không yêu cầu các ablations này cho initial slice; giữ cho final comparison và separate methodVersion.

### F6 — P1, thiếu explicit producer ở schema: direction và lifecycle

- ontology:140–142 đặt expectedDirection trên Candidate; shapes yêu cầu nó (:188).
- EVENT_SCHEMA nhắc dictionary nhưng không có mục mô tả producer cho expectedDirection theo Event–Stock.
- EVENT_SCHEMA:52 nêu Reaction-ready/rejected boundary; shapes:208 liệt kê GENERATED/VALIDATED/REJECTED/PENDING_MARKET_WINDOW/REACTION_READY, chưa thành transition table trong schema.

Đề xuất: direction từ dictionary rule + selected assignment + eligible route/business context; thiếu directional evidence => UNKNOWN, không lấy CAR hoặc mặc định eventType sign. Lưu rule version/input/reason. Thêm bảng lifecycle xác định gate, trạng thái và lý do; missing market data giữ Candidate và pending/reason, không tự REJECTED relevance. Với nhiều windows, khóa ready là window-specific sidecar task hoặc any-ready Candidate semantics nhất quán với existing shape; không tự thêm ontology class. Một window có Reaction không chứng minh mọi window đã hoàn tất.

### F7 — P2, wording không nhất quán về calibration

EVENT_SCHEMA:54 nói calibrated model/role provenance vẫn cần curated pipeline gates. V1 cho uncalibrated task scores và hoãn calibration.

Đề xuất đổi thành model/role score provenance + scoreOrigin/calibration status; không hiểu calibrated probability là prerequisite của slice. Đây là wording risk, không kết luận toàn bộ schema bắt buộc calibration.

### F8 — P1, Evidence anchor producer cần chốt ở adapter

- EVALUATION:51–55 có exact one-to-one matching contract.
- SCORING:73 có instance anchor/conditioned BIO nhưng chưa tự xác định Evidence boundary từ token predictions.

Đề xuất khóa cách extractor/adapter tạo Evidence start/end trên original text: sentence/window/span selection, trigger-to-instance assignment và offsets; test repeated strings, multiple events, subwords, truncation và windows. Không đồng nhất token trigger span với gold supporting Evidence sentence hoặc attention với Evidence. Nếu pipeline thiết kế anchor khác gold definition thì exact metric có thể báo toàn mismatch dù role predictions có vẻ tốt. Đây là producer/interface definition cần bổ sung trước implementation, không đổi gold theo predictions.

## Các tình huống tối thiểu cần thành regression/diagnostic

1. AvailableAt trước open, đúng open, intraday, cuối tuần/ngày nghỉ: đúng calendar strict opening.
2. Earliest Evidence thiếu role, bài sau đủ: no Candidate tại original cutoff, coverage miss retained.
3. Alias khớp hai companies: HOLD, không score fallback để cứu.
4. Subsidiary selected newer version đã ended: không quay về older open-ended record.
5. IndustryExposure khác reporting scope/stale: không broadcast/sai period.
6. Hai Events trong một bài: không ghép company/metric/period giữa instances.
7. Automatic Event-entry support và curated terminal mapping: R theo support origins, không lấy A thay edge score.
8. Missing benchmark session/predecessor: no final Reaction cho window, ranking case vẫn retained.
9. Late facts/curation/reprints: frozen score/selection không bị sửa.
10. Replay frozen inputs: same selection/components/ranking/serialized score; volatile execution metadata separate.
11. Constant L/R ablation: báo no-op đúng ý nghĩa.
12. Existing ready Reaction cho [0,0] nhưng [0,+3] chưa đóng: không claim tất cả windows ready.

## Thứ tự chỉnh tối thiểu đề xuất (chưa thực hiện)

1. Đồng bộ active V1 numerical/producer policies trong EVENT_SCHEMA, EVALUATION và ANNOTATION; legacy variants tách rõ.
2. Bổ sung slice profile + acceptance outputs và supported model/type scope.
3. Chốt training/diagnostic split, Evidence adapter, direction producer và lifecycle/window semantics.
4. Lập matrix rule → implementation test → run artifact; cập nhật PHASE1_ACCEPTANCE/plan và audit TTL/SHACL/diagrams/reports trước bundle acceptance.

Targeted SHACL inspection chỉ thấy strength range [0,1] và arithmetic checks, chưa thấy route-strength numerical table được enforce. Vì vậy không kết luận V1 indirect T=1 chắc chắn fail SHACL, nhưng SHACL pass cũng không chứng minh đã tuân thủ scoring method; method-aware gate/test vẫn cần. Không chạy full SHACL/diagram/market/metric tests trong review này.
