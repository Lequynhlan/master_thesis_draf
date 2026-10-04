# Kết luận tổng hợp review trước khi gửi thầy

Ngày review: 2026-10-04. Phạm vi được người dùng yêu cầu: `D:\project\master_thesis\01-10-2026\chỉnh sửa mới nhất - 01-10`. Đây là review các artifact hiện hành, không phải review git diff. Tài liệu chuẩn model/schema: TTL/SHACL; Markdown định nghĩa scoring/evaluation; DOCX/PDF và Draw.io là phần cần đồng bộ. Không sửa các file nộp.

## 1. Verdict

**Chưa gửi trọn bộ như thể đây là một gói đã thống nhất và sẵn sàng triển khai.** Gói có nền tảng ontology/schema tốt và các tài liệu Markdown V1 đặc tả khá chi tiết, nhưng DOCX/PDF vẫn trình bày scoring của 1.0.4 trong khi Markdown đã đổi sang `WFKG-SCORE-V1` 1.1.0. Draw.io đã thay đổi trong lúc review; kiểm tra phiên bản mới cho thấy audit cấu trúc còn pass nhưng một test của chính gói hiện fail vì đang khẳng định nhãn legacy đã bị bỏ.

Nếu chỉ gửi để xin thầy chọn/duyệt hướng phương pháp, nên nói rõ đó là bản đang chuyển đổi và chỉ gửi sau khi sửa hoặc khoanh riêng mâu thuẫn phiên bản. Đừng mô tả nó là “đã đồng bộ PDF–Draw.io–TTL” hoặc “pipeline đã chạy”.

### Điều đã tốt

- Cấu trúc `EventStockCandidate` ở cutoff và `EventStockReaction` hậu cửa sổ giá tách đúng mục đích; không lấy phản ứng thị trường để ranking cutoff.
- TTL/SHACL không có mâu thuẫn domain/property lớn được tái hiện trong audit. Bốn đường đi chính, phân biệt Company với Stock, identity/provenance, temporal constraints và các giới hạn của SHACL được mô tả rõ.
- `EVENT_DICTIONARY.yaml` có 14 loại sự kiện, required/optional roles, canonical key, hướng tác động/confusables và normalization vocabulary. Đây là đóng góp mạnh cho data modeling.
- Không có căn cứ buộc thầy phải yêu cầu LLM hoặc cấm LLM. Thầy yêu cầu ML/NLP phục vụ pipeline KG, không yêu cầu PhoBERT là bắt buộc.
- Đặc tả mới phân biệt rõ PhoBERT pretrained với extractor phải fine-tune; uncalibrated task score không bị gọi là xác suất đã hiệu chỉnh; gold độc lập không lấy từ model/judge.

## 2. Các mục ưu tiên phải giải quyết trước khi tuyên bố gói đã sẵn sàng

### P1 — HIGH: phiên bản scoring trong DOCX/PDF lệch hợp đồng Markdown

Bằng chứng ở `PRESEND_CURRENT_PRESENTATION_REVIEW.md` P-01–P-04: DOCX/PDF còn ghi `SCORING_SPEC 1.0.4`, extraction fallback `0.5`, ba đường INDIRECT có `relationStrength=0.5`, DIRECT `relationConfidence` dùng assignment score và automatic linking có fallback. Trong khi đó các Markdown active là V1 1.1.0:

- extractor PhoBERT đã fine-tune ED/EAE; A là min các task decisions; không extraction fallback;
- links exact/typed/unique được nhận theo convention L=1, trường hợp mơ hồ HOLD;
- R là min các edge supports theo origin, automatic evidence support `0.5` hoặc curated eligible `1.0`;
- T=1 trên cả bốn routes.

DOCX/PDF có ghi ảnh minh họa cũ là historical/synthetic ở một số chỗ; điều đó không sửa các đoạn prose/table đang nêu 1.0.4 là baseline hiện hành. Chọn một trong hai hướng trước khi gửi: đồng bộ báo cáo theo V1, hoặc ghi rõ V1 là đề xuất mới chưa được duyệt và 1.0.4 mới là nội dung bản báo cáo. Không đổi TTL version để giải quyết khác nhau giữa structural schema version với method version.

### P1 — HIGH: hiện tại V1 không thể tạo khác biệt xếp hạng cổ phiếu trong cùng một Event

Đây là finding phương pháp quan trọng, không phải lỗi SHACL. `SCORING_SPEC.md:44, 170–191, 195–206` cố định S=0.5, L=1, T=1; A là một Evidence assignment được chọn cho Event; ở automatic extraction, Event-entry edge support là 0.5. Do R lấy minimum trên toàn đường đi, mọi automatic Candidate của cùng Event có R=0.5, dù cạnh phía sau được gán 0.5 hay 1.0. Do đó mọi Stock của cùng Event nhận chung `candidateScore` và xếp hạng theo tie-break Stock URI. `EVALUATION_PROTOCOL.md:159–173, 182–187` lại tính nDCG/Precision@K theo Event. Weighted V1 vì thế chỉ co giãn điểm theo Event, không thể đổi thứ tự Stock trong bài toán ranking chính của RQ3; các neutralization A/L/R cũng không đổi thứ tự đó.

Đã viết phép kiểm đại số có guard kiểm tra chính sách trong live spec và ba giá trị A tổng hợp. Chạy thật: baseline, unweighted, A/L/R neutralization đều chỉ có một score duy nhất cho mỗi Event; mọi ranking và nDCG@5 giữ nguyên. Đây là **diagnostic tổng hợp, không phải chạy pipeline hay dữ liệu thực nghiệm**.

Cần quyết định trước khi khóa kết luận RQ3: (a) giữ V1 làm plumbing/control và thừa nhận RQ3 chưa kiểm được ranking gain; (b) đưa một tín hiệu có thể khác nhau theo Event–Stock vào một method version riêng—ví dụ exposure-strength mà thầy đã yêu cầu, với protocol khóa trước test; hoặc (c) đổi đơn vị/mục tiêu đánh giá sao cho có lý do phương pháp để so sánh điểm giữa Event khác nhau. Không lấy CAR/future price, không chế nhãn, không thay đổi scoring ngầm để tạo độ phân tán. Trong bản hiện hành, exposure experiment để sau automatic slice nên chưa giải quyết câu hỏi RQ3 của luận văn ngay lúc này.

### P1 — HIGH nếu nộp như gói đáp ứng yêu cầu KG-RAG: chưa có benchmark Vector RAG vs KG-RAG được đóng băng

`EVALUATION_PROTOCOL.md:25` hoãn RAG benchmark khỏi slice; các RQ hiện mô tả extraction, Event–Stock retrieval, weighting chứ chưa có protocol thực thi so sánh Vector RAG với Ontology/KG-RAG. Bản nghiên cứu mới chỉ đề xuất cách cân bằng corpus/cutoff/model/context budget và đánh giá evidence, thời gian, retrieval, câu trả lời; nó **chưa phải protocol active**. Người dùng đã nêu đây là trục luận văn và góp ý ban đầu nói rõ cần so sánh hai hệ.

Trước khi gửi như proposal hoàn chỉnh, cần ghi tối thiểu một mục dự kiến/được duyệt cho RAG: tập câu hỏi và gold, hai retrieval arms, matched input/cutoff/context, metrics truy xuất evidence/entity/time/ranking, human answer-grounding/abstention, paired uncertainty. Nếu cố ý để sau slice thì nói thẳng trạng thái đó với thầy, không gọi RQ hoàn tất.

### P1 — MEDIUM/HIGH: kiểm thử Draw.io hiện fail sau thay đổi trong lúc review

Lúc đầu snapshot review, Draw.io có SHA256 `30da7b...`; lần kiểm tra cuối, SHA256 là `81ad82...` và kích thước/label đã đổi. Không có bằng chứng tác nhân nào trong review đã sửa artifact; do đó ghi nhận nó đã thay đổi trong cửa sổ review, không suy đoán ai sửa. Tôi lấy bản bytes mới nhất làm hiện trạng và chạy lại kiểm tra.

- `audit_schema_diagram.py --json`: exit 0, **337 PASS / 0 FAIL / 57 NOT CHECKED**.
- `test_baseline_shacl.py`: **31/31 PASS**.
- `test_schema_diagram_audit.py`: **7/8 PASS, 1 FAIL**. Lỗi tại `tools/test_schema_diagram_audit.py:97`: test `test_baseline_note_does_not_replace_reaction_cutoff` bắt buộc phải tìm chuỗi `1.0.4` trong cell `weTA0hvWxfCujyoZNfAk-11`, nhưng cell mới đã bỏ nhãn đó và ghi lại đúng ranh giới `candidateScore`/`reactionWeight` theo cutoff/window.

Đây có vẻ là regression test chứa kỳ vọng wording cũ, không phải bằng chứng diagram mới sai ontology. Nhưng hiện không thể báo cả bộ kiểm thử xanh. Cần người duyệt quyết định cập nhật assertion test cho đúng contract hiện hành (giữ kiểm tra phần cutoff/window), rồi chạy lại. Tôi **không sửa** test trong lượt review.

### M1 — MEDIUM: SHACL có thể nhận một node chưa khai báo/type-valid làm “supporting Evidence” khi validation chạy inference=none

Machine review tái hiện trên bản graph serialized: bỏ type `Evidence` cùng `evidenceId/evidenceText/extractedFrom`, giữ triple `supports Event` và `availableAt`; graph vẫn conforms khi tắt inference. Positive controls hợp lệ pass. Đây là gap ở boundary kiểm chứng, không khẳng định dữ liệu thật đã sai. Cần kiểm input typing bằng curated gate hoặc bổ sung shape/regression phù hợp; không cần mở rộng ontology. Chi tiết bước tái hiện và giới hạn tại `PRESEND_CURRENT_MACHINE_REVIEW.md`, M1.

## 3. Các điểm quan trọng nhưng có thể chốt sau khi làm rõ trạng thái với thầy

- V1 `INDIRECT T=1` hiện khác nội dung báo cáo cũ có `.5`; thí nghiệm dùng exposureStrength là một variant được hứa làm sau slice. Vì RQ3 cùng Event không đổi thứ tự như trên, xin thầy xác nhận vị trí và thời điểm của variant này trước khi bắt đầu implement.
- Reference extractor mới chỉ hỗ trợ Evidence là một câu, không ghép roles giữa câu/window (`EVENT_SCHEMA.md:134–143`). PhoBERT hỗ trợ câu tiếng Việt và token-level tasks, nhưng chưa có bằng chứng nó giải được event/role/occurrence identity cho 14 dictionary types. Đây là giới hạn adapter được công khai, không phải lỗi schema—nhưng cần pilot để biết độ phủ và báo các gold miss.
- `occurrence_id` là required cho mọi Event type; code/registry phải phân biệt reprint, duplicate assertion, clarification và substantive update. Không model nào tự tạo ra business identity đáng tin chỉ bằng dự đoán; không cho dùng URL/ngày đăng hoặc UUID tùy ý để lấp.
- Agreement protocol nêu 25% double-label nhưng trước khi gán gold cần khóa sampling unit/denominator, cách rút mẫu có seed/IDs và xử lý mention/event alignment trước kappa. Hiện đây là quyết định protocol còn mở, không bằng chứng đã annotation sai.
- Mục 2 (daily effectiveTradingDate) được đặc tả nhất quán ở Markdown; không có calendar runtime. Mục 5 (market provenance) có close inputs và công thức để tái tính; chưa chạy market provider thật. Đây là giới hạn trước code được disclose, không phải kết quả đã kiểm lịch/đã tái lập dữ liệu thật.
- Presentation review kiểm 10/10 query trong thứ tự literal của DOCX parse được; không chứng minh được query output lịch sử vì source snapshots/CSV/JSON của demo không nằm trong package. Đã xem hình là synthetic/history, không phải bằng chứng kết quả RQ.

## 4. Brainstorm ML/NLP theo data model hiện hành — phương án nên trình bày

Không có skill mang tên chính xác “brainstorming” trong danh sách skills hiện có. Phần này dùng domain-modeling + literature research, neo vào fields/roles thực tế, không chỉ chọn model theo độ nổi tiếng.

### Bài toán cần giải không phải NER đơn thuần

Ví dụ nhỏ từ schema: một tin về lợi nhuận quý cần nhận đúng Event instance, `company`, `reporting_period` gồm qualifiers, `metric`, và `occurrence_id`; đúng đoạn support; tách forecast với kết quả đã công bố; sau đó registry mới resolve canonical Event/Company/Stock ở cutoff. Tin M&A còn cần buyer/target và rumor/denial/completion, không nhầm chiều hai bên. Tìm đúng chuỗi tên bằng NER nhưng gắn metric/sự kiện sai vẫn sinh KG sai.

### Ba phương án, theo điều kiện dữ liệu

1. **PhoBERT supervised ED/EAE — lựa chọn hợp đồng hiện hành, nếu sẵn sàng gán train/dev.** PhoBERT chỉ là encoder; phải fine-tune task heads. Reference V1 quy định trigger detection, EventType theo instance, role spans. Ưu: score accessors và replay đã được SCORING_SPEC định nghĩa; ít lệch hợp đồng nhất. Nhược: tốn annotation theo task, hiếm eventType/role, một câu có thể thiếu ngữ cảnh; single-sentence rule làm mất các assertion mà company/period/metric nằm khác câu. Không nên train toàn bộ 14 loại cùng lúc nếu dữ liệu mỏng; bắt đầu từ subset được khai báo, giữ loại khác là coverage/HOLD.
2. **Một model generative, schema-guided — phương án thay thế nếu ưu tiên ngữ cảnh/giảm tự viết nhiều task heads.** Input cho biết schema, positive/negative/confusable examples; output structured events, triggers/evidence/roles; code giữ offsets/validation/identity/cutoff. UIE và GoLLIE cho thấy schema/guidelines là đầu vào hữu ích, nhưng các phương pháp paper được task-trained; JSON hợp lệ không chứng minh role đúng. Nếu đổi sang LLM/API thì đổi adapter/method/score producer đã duyệt; không reuse xác suất chuỗi, self-rated confidence hoặc fallback `.5` làm V1 A.
3. **Một LLM + dictionary/typed registry/code gates — hybrid một extractor, không phải fusion.** Code chuẩn bị candidate aliases/typed vocabulary; LLM phân biệt assertion/role; code kiểm tra evidence và nguồn gốc identity; trường hợp mơ hồ HOLD/review. Dễ khoanh scope KG hơn, nhưng cần giám sát alias coverage và tránh model tự hợp thức hóa output sai bằng quote liên quan.

**Khuyến nghị thực tế:** vì active contract đã chọn PhoBERT, nếu gửi gói theo V1 thì cứ trình PhoBERT là *reference candidate*, nhưng chưa tuyên bố đã có model/train data hoặc hiệu quả. Trước khi đầu tư train đủ 14 loại, xin thầy duyệt subset + reference sentence adapter, làm pilot representability/evidence/occurrence trên dữ liệu thật và gold. Nếu annotation train khó hoặc mất ngữ cảnh nhiều, trình thầy lựa chọn có kiểm soát giữa giữ A hay mở method B/C; không đổi trong cùng protocol âm thầm. PhoBERT/LLM đều không giải linking identity/timestamp/market reaction thay cho code và provenance.

### Các nguồn gốc đã đọc

- Nguyen & Nguyen (2020), *PhoBERT: Pre-trained language models for Vietnamese*, EMNLP Findings. Paper thử POS, dependency parsing, NER, NLI—không thử event extraction tài chính Việt Nam: https://aclanthology.org/2020.findings-emnlp.92/ .
- Lu et al. (2022), *Unified Structure Generation for Universal Information Extraction* (UIE), ACL: schema-guided text-to-structure và task fine-tuning; không phải model Việt tài chính cài là chạy: https://aclanthology.org/2022.acl-long.395/ .
- Zheng et al. (2019), *Doc2EDAG: An End-to-End Document-level Framework for Chinese Financial Event Extraction*: có arguments phân tán qua câu, nhiều event trong văn bản; domain tiếng Trung và dataset/architecture riêng, không benchmark WFKG Việt: https://arxiv.org/abs/1904.07535 ; repository/tóm tắt của tác giả: https://github.com/dolphin-zs/Doc2EDAG .
- Du & Cardie (2020), *Document-Level Event Role Filler Extraction using Multi-Granularity Contextualized Encoding*, ACL: nhấn mạnh lỗi khi required roles trải qua nhiều câu; task/data MUC-4 khác WFKG: https://aclanthology.org/2020.acl-main.714/ .
- Li, Ji & Han (2021), *Document-Level Event Argument Extraction by Conditional Generation*: https://arxiv.org/abs/2104.05919 .
- Sainz et al. (2024), *GoLLIE: Annotation Guidelines improve Zero-Shot Information-Extraction*: schema/guideline fine-tuning, không chứng minh generic prompt tuân thủ rubric: https://arxiv.org/abs/2310.03668 .
- Đọc thêm grammar-constrained decoding (Geng et al., 2023), giúp hợp lệ cấu trúc/enum chứ không bảo đảm ngữ nghĩa đúng: https://arxiv.org/abs/2305.13971 .

Bằng chứng tập trung này không phải systematic review và không tái chạy các benchmark trên WFKG. Không tìm thấy bằng chứng trong các bài đọc để kết luận PhoBERT thắng LLM, hoặc ngược lại, trên data model/tin tài chính tiếng Việt này.

## 5. Ma trận góp ý thầy (theo đúng file feedback)

| Mục | Review hiện trạng trước gửi |
|---|---|
| 1. PDF–Draw.io–TTL | Partial: schema/diagram vocab đạt audit; DOCX/PDF score/method vẫn legacy, Draw.io đang mới hơn và một test kỳ vọng nhãn cũ. Chưa claim all synchronized. |
| 2. effectiveTradingDate daily | Spec addressed; runtime calendar/session chưa kiểm chứng. |
| 3. component confidence | Cấu trúc và audit sidecar tốt; current score producers/prose DOCX/PDF chưa cùng version; min softmax uncalibrated, không probability—đã viết đúng ở active MD. |
| 4. candidateScore/reactionWeight | Tách công thức/thời gian đúng ở active MD; report legacy strength còn sai với V1. RQ3 ranking utility cần giải do điểm hằng theo Event. |
| 5. Market provenance | Có adjusted close, benchmark, predecessor/full-window contract; chưa kiểm trên source/market thật/calendar-aware runtime. |
| 6. Event dictionary | Machine-readable, 14 entries; chưa chạy normalizer/extractor trên annotation/gold. |
| 7. Data rules | Temporal version/exposure/reporting scope mô tả; expose-strength variant V1 chưa chạy và hẹn sau slice; chốt lịch thực hiện với thầy. |
| 8. Evaluation | Nhiều chi tiết RQ1–RQ3, splits/gold/universe/metrics; chưa benchmark RAG baseline/proposed path; freeze annotation sampling; RQ3 V1 degeneracy. |
| 9. Draw.io appendix | Audit mới nhất PASS/0 FAIL/57 NOT CHECKED; test suite 1 lỗi cũ. Visual render Draw.io ở lượt cuối **chưa kiểm**. |

## 6. Verification và tính bất biến

- Ở đầu review chụp SHA256 của 16 file trong package. Chụp lại trước khi kết thúc: 15 file giữ nguyên; riêng `master_thesis_v1_synced_01-10.drawio` thay đổi (`30da7b…` → `81ad82…`). Tôi đã chạy lại audit và cả hai test scripts trên bản Draw.io mới nhất; kết quả ghi ở P1 phía trên. Không quy việc đổi đó cho bất kỳ ai.
- DOCX/PDF review bao gồm toàn bộ paragraph/table text, 47 PDF pages, 10 query syntax/order, 7 tab XML/connector, 9 ảnh embedded và kiểm tra contact sheet PDF. Text DOCX/PDF khớp sau chuẩn hóa whitespace/footer; điều đó không chứng minh toàn bộ visual proofreading.
- Draw.io XML đã được audit; renderer/visual check mới cho diagram chưa thực hiện. Không nhận report cũ là “đã render diagram” cho bytes mới.
- Không train/infer model, không crawl news/market, không kiểm performance/candidate ranking trên dữ liệu thật, không sửa canonical source, không commit/push. Synthetic nDCG/probe không phải kết quả RQ.

## 7. Artifact

Báo cáo review machines/ontology: `review_phase1/PRESEND_CURRENT_MACHINE_REVIEW.md`
Báo cáo presentation DOCX/PDF/Draw.io: `review_phase1/PRESEND_CURRENT_PRESENTATION_REVIEW.md`
Note nghiên cứu ML/NLP hiện schema: `research_confidence/EXTRACTION_MODEL_CURRENT_SCHEMA_RESEARCH.md`
Diagnostic tái hiện ranking V1: `review_phase1/PRESEND_CURRENT_DESIGN_DIAGNOSTIC.json`
Snapshot SHA256 trước review: `review_phase1/PRESEND_CURRENT_SOURCE_HASHES_BEFORE.json`

Lượt này là read-only đối với bộ hồ sơ gửi thầy. Mọi remedy trong báo cáo đều là đề xuất, chưa được thay đổi vào bộ nộp.
