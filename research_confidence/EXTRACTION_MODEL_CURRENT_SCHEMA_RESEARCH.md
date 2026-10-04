# Chọn extractor theo mô hình dữ liệu WFKG hiện hành — nghiên cứu và brainstorm có giới hạn

**Trạng thái:** research/design options, chưa phê duyệt đổi phương pháp; không phải kết quả chạy NLP. Chỉ đọc nguồn, tải paper và viết note. Không gọi API inference, không tải checkpoint, không train/chạy model; không sửa live specification, glossary hoặc ADR.

## 1. Kết luận trước: không bắt đầu bằng câu hỏi «PhoBERT hay LLM mạnh hơn?»

Câu hỏi phù hợp hơn là: **extractor nào tạo được các event-instance có trigger, vai trò gắn đúng assertion, Evidence truy về văn bản gốc, rồi giao cho code/registry kiểm định identity và cutoff?** Trọng tâm luận văn theo yêu cầu người dùng là Weighted KG từ tin tức + giá và ứng dụng/so sánh KG-RAG với vector RAG, không phải fusion nhiều model. Các heads ED/EAE của một encoder không phải GAT/TFT/TabTransformer fusion; preprocessing + một model + validator cũng không phải ensemble.

Có ba phương án thực tế, chưa phương án nào được literature chứng minh thắng trên schema tài chính tiếng Việt này:

- **A. Giữ supervised PhoBERT ED/EAE** nếu ưu tiên tuân thủ hợp đồng slice đang viết, học được nhãn địa phương và có người gán train/development. Đây là phương án ít đổi contract nhất; không phải đã có checkpoint sẵn.
- **B. Một generative extractor, schema/guideline-guided và constrained khi backend hỗ trợ**, nếu ưu tiên giảm engineering task heads và thử xử lý contextual arguments. Đây là phương án nghiên cứu hợp lệ, không phải default tốt hơn; không tự tương thích scoring V1.
- **C. Preprocessing + dictionary/registry/code + một LLM chỉ làm semantic extraction**, nếu bottleneck chính là thiếu dữ liệu train và muốn khoanh trách nhiệm model. Không để regex xác lập sự kiện rồi LLM tự chấm mình thành gold. Đây cũng là method variant cần approval, không phải tự động được gọi V1.

**Đề xuất hiện tại:** chưa bỏ PhoBERT chỉ vì schema có nhiều role; cũng chưa bắt đầu train tất cả dictionary types. Đầu tiên kiểm kê tính biểu diễn được của dữ liệu ở EARNINGS/DIVIDEND/cụm M&A, annotation feasibility và availability/identity. Nếu vẫn phải chạy đúng automatic reference slice hiện hành, chọn A. Nếu người dùng quyết định đổi phương pháp để tập trung KG/RAG và giảm chi phí xây ED/EAE, đưa B/C vào pilot có protocol riêng sau approval. Nếu không có dữ liệu train lẫn gold đánh giá, chưa phương án nào đủ căn cứ acceptance.

### Điểm mới quan trọng khi đọc live docs

Live Markdown **không còn để extractor hoàn toàn mở**. `EVENT_SCHEMA.md` L134–143 và `SCORING_SPEC.md` L69–75 đã ghi **trained PhoBERT ED/EAE, V1-SENTENCE-TRIGGER-BIO**, Evidence nguyên một câu, không ghép required-role fragments giữa câu/window. `EVALUATION_PROTOCOL.md` L9–26 cũng ghi initial PhoBERT task training và automatic slice trained reference inference. Đây là **đặc tả**, chưa là chứng cứ đã train/implement, cũng không chứng minh thầy đã phê duyệt riêng lựa chọn checkpoint. Note này không tự sửa quyết định đó. Phương án generative là đề xuất thay thế cần phê duyệt/version, không phải implementation drop-in.

Góp ý thầy yêu cầu dictionary trước NLP, taxonomy gọn, bốn routes, freeze scores/cutoff, provenance và kiểm thử; **không yêu cầu dùng LLM hoặc bỏ PhoBERT**. Locators: feedback L92–108, L16–24, L38–56, L120–137, L156–171.

## 2. Những nguồn địa phương đã đọc và phiên bản thực sự dùng

Root chính xác: `D:\project\master_thesis\01-10-2026`. Trong bảng dưới, `current/` viết tắt **chỉ trong note** cho `chỉnh sửa mới nhất - 01-10/`; không phải thư mục khác.

| Nguồn | Version/trạng thái đọc | Locators chi phối quyết định |
|---|---|---|
| `current/EVENT_DICTIONARY.yaml` | 1.0.4, đọc toàn bộ | L4–13 identity; L32–79 normalization/typed registry; L157–196 period qualifiers; L198–258 EARNINGS/DIVIDEND/M&A; L259–339 phần còn lại |
| `current/EVENT_SCHEMA.md` | document 1.1.0, WFKG-SCORE-V1, đọc toàn bộ | L12–31 flow/cardinality; L35–54 routes/components; L94–103 cutoff; L126–143 identity/reference adapter; L145–147 direction |
| `current/ANNOTATION_GUIDELINE.md` | document 1.1.0, đọc toàn bộ | L13–40 gold/relations; L44–50 assignment/cutoff; L52–64 independent gold/anchors; L66–79 agreement/sealing |
| `current/SCORING_SPEC.md` | document 1.1.0, đọc toàn bộ | L12–27 legacy boundary; L44–65 gates; L69–125 trained heads/accessors/min/selection; L129–176 S/link/support; L225–244 audit; L290–315 evaluation/acceptance |
| `current/EVALUATION_PROTOCOL.md` | document 1.1.0, đọc toàn bộ | L9–43 split/profiles; L71–81 common universe; L93–105 exact matching; L133–145 shared extractor; L159–173 weighting; L179–195 freeze/metrics |
| `ban_thay_gop_y/gop_y_phase1_truoc_code_phase2.txt` | đọc toàn bộ; supervisor feedback | L3–5, L16–24, L38–74, L92–108, L120–137, L156–171 |
| `research_confidence/phobert_fit.md` | đọc toàn bộ, note lịch sử | L5 đề xuất LLM-first; L23–27 supervised heads; L42–60 preprocessing/benchmark limits |
| `research_confidence/RESEARCH_CONFIDENCE_WFKG.md` | đọc toàn bộ, note lịch sử | L7 và L230–232 lấy contract 1.0.4; L183–228 rubric adaptation, không phải active V1 |

**Không reuse mù hai note cũ:** lời khuyên LLM-first trong `phobert_fit.md` L5 chưa dựa vào reference adapter live hiện tại; tổng hợp confidence cũ đọc scoring 1.0.4. Không dùng chúng để khẳng định active extraction fallback 0.5. V1 **S=0.5 giữ nguyên**, automatic relation support 0.5 là convention, nhưng **không extraction fallback**; A lấy task-trained decisions. L accepted=1.0 và T=1.0 trên bốn routes là controls, không probabilities (`SCORING_SPEC.md` L12–25, L44, L97–111, L129–149, L170–176, L195–206).

### Dấu vân tay snapshot đã đọc

Files đang được cập nhật song song; số dòng/nhận định này gắn với bytes có SHA256 dưới đây, không coi ngày tên folder là version nội dung. mtime dưới là thời gian filesystem địa phương, không phải approved-at hoặc thời gian availability của tin tức.

| File | SHA256 | mtime được kiểm tra |
|---|---|---|
| EVENT_DICTIONARY.yaml | `b01e6cfda780360061f5efd29c83a7369584ce766ad880d32bf64516d080e91d` | 2026-10-04T10:55:36.717050 |
| EVENT_SCHEMA.md | `e8e7bd4f05bd8b1865c28cf0d7be061c84284803493ca62937516334e78f866f` | 2026-10-04T20:27:25.264617 |
| ANNOTATION_GUIDELINE.md | `c2ef21854ff3636ab7d86352ba0117a5a3fac1213220a985ab828d4d0b5bcea2` | 2026-10-04T20:27:01.094513 |
| SCORING_SPEC.md | `fcd60f30d3ce86b2764a896e3f1200046477d61ea31d83198bc34946729f85a3` | 2026-10-04T20:33:15.389543 |
| EVALUATION_PROTOCOL.md | `d7937d6f69fdf8626bb778b0f2ff5dc36cfd721a86d1d110da9c8f1e675efe0e` | 2026-10-04T20:26:58.887864 |
| Supervisor feedback | `d1296c61fd132c5ff83417f58d064c70721aafab88761ee1f2e44ee94a97d7e9` | 2026-09-24T15:19:58.191881 |

## 3. Extraction target: từng tầng quyết định riêng, không gọi chung NER

Ví dụ tự tạo để stress-test schema, **không phải tin đã crawl/gold/kết quả model**:

> Công ty An Bình công bố lợi nhuận sau thuế quý I năm 2026 hợp nhất giảm so với cùng kỳ. Doanh thu cùng kỳ tăng. Công ty dự kiến kết quả quý tới sẽ cải thiện.

NER có thể tìm «An Bình». Nhưng bài toán cần hơn thế:

1. ED: tìm assertion kết quả đã công bố; phân biệt forecast-only ngoài baseline, không biến «dự kiến» thành EARNINGS đã xảy ra.
2. Instance/type: không lấy một nhãn EARNINGS cả bài rồi dùng mọi con số/metric làm role của cùng prediction.
3. EAE: gắn company, reporting_period và metric vào đúng trigger/claim; scope CONSOLIDATED không được bỏ. Trường hợp nhiều metric phải giữ assignment riêng/được adjudicate về business occurrence, không tự gom mọi metric vào một canonical key chỉ vì cùng company/quý.
4. Identity: cần original assertion/document identity cho occurrence_id; «quý I 2026» không thay thế occurrence. Báo lại và substantive restatement khác nhau.
5. Direction: revenue tăng không tự POSITIVE; profit giảm có comparative base mới đủ xét. Một article sentiment score không thay expectedDirection per Event–Stock. Conflicting coherent signals cần UNKNOWN theo rule, không đo bằng giá tương lai.
6. Gate: literal chuẩn hóa + entity registry + business identity + availability phải qua trước Candidate. Schema pass không chứng minh đúng role attachment.

Locators: dictionary L208–217, L140–145, L171–185; schema L126–147; scoring L65, L73, L97–123. Paper PhoBERT [P1] chỉ chứng minh encoder dùng được cho những benchmark nó thử; **NER tốt không đồng nghĩa event/argument/identity tốt**.

### Cross-sentence Evidence là lựa chọn hợp đồng, không chỉ lựa chọn model

> An Bình công bố báo cáo số BC-17. Báo cáo ghi lợi nhuận sau thuế quý I năm 2026 hợp nhất giảm so với cùng kỳ.

Thông tin company/original document ở câu trước, metric/period ở câu sau. Một encoder/generative model có thể đọc cả hai câu, nhưng **reference assignment V1 hiện tại không được ghép roles/Evidence giữa câu**, và phải có toàn câu Evidence fit vào một input window. Context lớn hoặc coreference tốt không tự biến output này thành complete V1 assignment. Schema L139–143 quy định cross-sentence unsupported => staging/coverage reason; scoring L117–125 không fragment merge; annotation L56 bảo toàn gold khó thay vì loại để đẹp F1.

Do đó cần ghi hai kết quả riêng: (i) semantic gold Event có thật theo văn bản/cutoff; (ii) reference adapter biểu diễn được/đã emit được không. Trước khi chọn model lớn hơn, đo tỷ lệ các **loại lỗi/nhóm support** này trên dữ liệu gán nhãn; hiện chưa có đo đạc để nói cross-sentence là phổ biến nhất.

Nếu muốn alternative document adapter: phải phê duyệt Evidence boundary/support-set và instance-anchor/score contract trước test; một assignment được model tạo từ context xác định khác với hậu kỳ chắp fragments từ các partial outputs. Không đổi offset sau khi thấy gold, không tự thêm ontology properties. Multiple-sentence support có thể ở sidecar nhưng cần contract rõ cho RDF Evidence, evaluator và cutoff. `EVENT_SCHEMA.md` L141 và `EVALUATION_PROTOCOL.md` L95 yêu cầu adapter/method riêng.

## 4. Sáu paper sơ cấp đã truy cập và đọc trực tiếp

PDF và text thực tế nằm ở `research_confidence/sources_extraction/`; `fetch_manifest.json` giữ URL/hash/pages. Đây là focused review, không systematic search, không chạy lại experiments. Các method được đọc dưới đây; kết quả các paper không thể xếp hạng trực tiếp vì task, gold input và metric khác nhau.

### [P1] Nguyen & Nguyen (2020), PhoBERT: Pre-trained language models for Vietnamese

Nguồn: https://aclanthology.org/2020.findings-emnlp.92.pdf ; metadata https://aclanthology.org/2020.findings-emnlp.92/

**Đã đọc:** PDF pp2–4, §2 architecture/pretraining, §3 datasets/fine-tuning, §4 results; text `phobert.txt`, markers PDF PAGE 2–4.

- RoBERTa-style encoder, pretraining Vietnamese Wikipedia + news; RDR word segmentation rồi BPE; bản paper đặt tối đa 256 subword tokens (§2).
- POS/NER thêm linear prediction layer và task fine-tuning; paper dùng first subword per word cho những tasks đó (§3). Reference V1 score trên selected subwords là quy ước **của dự án**, không một cách reproduction nguyên xi NER paper.
- Evaluation gồm POS, dependency parsing, NER, NLI; không tài chính-Việt ED/EAE, occurrence linking hay cross-article canonicalization.

**Ứng dụng:** một encoder tiếng Việt hợp lý cho A, nhưng phải xây/train heads, label task và original-text offset map. Không phải instruction extractor/judge sẵn; news pretraining không chứng minh hiểu metric/qualifier tài chính.

### [P2] Wadden et al. (2019), Entity, Relation, and Event Extraction with Contextualized Span Representations — DyGIE++

Nguồn: https://aclanthology.org/D19-1585.pdf ; metadata https://aclanthology.org/D19-1585/

**Đã đọc:** PDF pp2–3, §2.1 task definitions, §2.2 architecture, §3 datasets/evaluation/Table 1; `dygiepp.txt` PAGE 2–3.

- Enumerate within-sentence spans; contextual BERT sliding multi-sentence neighborhood; feedforward scoring cho trigger và trigger–argument span pairs. Task graph/coreference propagation hỗ trợ context.
- **Giới hạn thường bị bỏ qua:** §2.1 argument candidates nằm **trong cùng câu với trigger** trong task paper, dù representations dùng cross-sentence context. Không được viện DyGIE++ như proof giải đầy đủ cross-sentence argument extraction.
- Paper thử ACE05, SciERC, GENIA, WLPC. Table 1 đánh dấu trigger ensemble và tách single-model result; note này mượn cấu trúc task, **không đề xuất ensemble hoặc dynamic span-graph stack** cho luận văn.

**Ứng dụng:** củng cố rằng event extraction khác NER: argument roles conditioned on trigger/instance. Có thể thiết kế một PhoBERT encoder với task heads giản dị hơn; không gọi adaptation đó là DyGIE++ reproduction. Không có benchmark schema tài chính tiếng Việt ở đây.

### [P3] Li, Ji & Han (2021), Document-Level Event Argument Extraction by Conditional Generation

Nguồn đã tải: https://arxiv.org/pdf/2104.05919 ; metadata https://arxiv.org/abs/2104.05919

**Đã đọc:** PDF pp2–5, §2.1 conditional generation/Eq(1)–(4), §2.2 trigger module, §3.1 metrics, §3.2 dataset creation; `doc_eae.txt` PAGE 2–5. Dùng bản PDF arXiv đã truy cập, không mặc nhận mọi version giống camera-ready.

- EAE input gồm unfilled ontology template + document, target trigger được đánh dấu; seq2seq BART/T5 fill arguments, missing args còn placeholder, multiple args hỗ trợ.
- Eq(2) hạn chế generated vocabulary tới tokens trong input; Eq(3) supervised negative log likelihood. Có type clarification/reranking để giảm sai filler, cho thấy copy/input constraint vẫn có thể điền **sai vai trò**.
- EAE module cần trigger/type input; end-to-end zero-shot phần khác có keyword-supervised trigger module và pseudo-label training. Không phải một generic chat prompt miễn training.
- WikiEvents lấy English Wikipedia-reference news; đánh giá Head F1/Coref F1 và informative mention. Coreferential/head matching paper **khác exact full span + sentence/trigger matching V1**.

**Ứng dụng:** precedent trực tiếp cho document context/arguments vượt câu, templates theo roles; không giải original occurrence registry, financial period qualifiers hoặc earliest historical availability. Contextual extraction vẫn cần validator/identity layer.

### [P4] Lu et al. (2022), Unified Structure Generation for Universal Information Extraction — UIE

Nguồn: https://aclanthology.org/2022.acl-long.395.pdf ; metadata https://aclanthology.org/2022.acl-long.395/

**Đã đọc:** PDF pp2–7, §2.1 SEL, §2.2 SSI, §3 pretraining/fine-tuning, §4.1–4.3 tasks/evaluation/low-resource; `uie.txt` PAGE 2–7.

- Structured Extraction Language biểu diễn **spotting + associating**, không chỉ danh sách named entities. Structural Schema Instructor mô tả targets/roles; encoder–decoder generates record structures.
- T5-based text-to-structure pretraining từ web/KB, sau đó supervised on-demand fine-tuning; có rejection/noise mechanism. **Schema prompt không đồng nghĩa generic LLM chỉ cần YAML là đủ.**
- §4.1 map generated text spans tới offsets bằng first eligible matching occurrence theo hierarchy. Trên WFKG có repeated text/duplicate metrics, không được tự dùng first occurrence để chứng minh attachment đúng.
- Benchmarks gồm ACE/CoNLL/SciERC/NYT/CASIE và sentiment datasets, không dictionary Vietnamese finance. Paper không đánh giá occurrence_id, issuer registry/cutoff như dự án.

**Ứng dụng:** schema là input có ích cho B/C; output cần record/instance roles. Không lấy universal IE làm bằng chứng universal semantic correctness hoặc performance tiếng Việt.

### [P5] Sainz et al. (ICLR 2024), GoLLIE: Annotation Guidelines improve Zero-Shot Information-Extraction

Nguồn: https://arxiv.org/pdf/2310.03668 ; metadata https://arxiv.org/abs/2310.03668

**Đã đọc:** PDF pp2–8, §3.1 schema/guideline representation, §3.3 regularization, §4 data/backbone/train, §5 supervised/zero-shot/ablation, §6 error examples; `gollie.txt` PAGE 2–8.

- Code-style schema/classes, guideline docstrings, representative examples; model **fine-tuned** để attend guidelines, có label dropout/other regularizations. Code-LLaMA backbone + QLoRA training; không phải pretrained PhoBERT, không phải off-the-shelf chat được bảo đảm follow dictionary.
- Seen/unseen schema overlap và different evaluation conventions được paper nêu. CASIE dùng category-based EE/partial argument matching vì span inconsistency (§4.1), không so trực tiếp với exact-match WFKG.
- §5.3 và §6 cho thấy examples/definitions hữu ích nhưng những labels mơ hồ vẫn khó. Không infer từ zero-shot generalization rằng Vietnamese financial extraction đã validated.

**Ứng dụng:** prompt/guideline phải chứa required/optional, confusables, refusal/missing policy và representative negative cases, không chỉ tên eventType. Nếu áp dụng Python-like output, parser phải an toàn: **không exec arbitrary generated code**; JSON/AST allow-list phù hợp hơn với sidecar dự án. Đây là engineering recommendation, không kết quả paper.

### [P6] Geng et al. (2023), Grammar-Constrained Decoding for Structured NLP Tasks without Finetuning

Nguồn đã tải: https://arxiv.org/pdf/2305.13971 ; metadata https://arxiv.org/abs/2305.13971

**Đã đọc:** PDF pp2–7, §2.1–2.3 grammar/parser/token filtering, §3 tasks/datasets/prompting, §4.1–4.3 comparisons; `grammar.txt` PAGE 2–7.

- Formal grammar + incremental parser xác định valid next tokens; input-dependent grammar cho candidate-specific outputs. Đây là **decoding constraint**, khác «prompt yêu cầu JSON» hoặc parse JSON hậu kỳ.
- Experiments gồm closed IE, entity disambiguation, constituency parsing; closed IE dùng synthetic SynthIE-text; entity disambiguation nhận mention/candidates theo task. Không direct end-to-end financial EAE benchmark.
- Grammar cho valid output, không xác lập fact truth/role correctness; input candidate set thiếu gold thì grammar vẫn ép chọn sai nếu không có abstain. Paper cho ví dụ valid parse không nhất thiết correct và parsing vẫn kém bespoke supervised methods.
- §2.2 cần access next-token distribution; nhận xét API services của bản 2023 là giới hạn implementation **thời điểm bài**, không dùng để đoán capabilities API hiện nay. Nếu sau này dùng hosted structured output phải kiểm chính backend/version thực tế, chưa kiểm/chưa gọi API trong nghiên cứu này.

**Ứng dụng:** enum/schema constraints giúp không sinh eventType/role trái vocabulary; cần cho phép missing/HOLD ở staging. Không thiết kế schema bắt model fabricate mọi required field để object trông valid.

### Giới hạn bằng chứng chung

Trong **sáu nguồn đã đọc**, không có benchmark trích xuất tài chính tiếng Việt theo roles, occurrence_id, period scope/basis, cutoff và linking của schema này. Điều đó **không chứng minh toàn literature không có Vietnamese financial dataset**: chưa systematic search mọi benchmark. Không chuyển F1 English/news/NER sang dự đoán F1 WFKG, không tuyên bố PhoBERT hoặc LLM thắng khi chưa có local gold. Đây là method evidence, không empirical selection verdict.

## 5. Owner matrix: model đề xuất nghĩa, code xác lập cấu trúc, curator xác lập mapping/identity mơ hồ

«Curated» ở đây là registry facts có review/provenance, không gold labels được đưa vào inference. Reference registry cũng có thể sai và phải đánh giá. Gold annotation là tầng độc lập.

| Field/decision | Model chịu trách nhiệm | Code chịu trách nhiệm | Curated input/review | Trường hợp phải HOLD / không được suy |
|---|---|---|---|---|
| source text, article ID, hash, offsets | Chọn support/trigger, không viết lại source | Freeze decoded text; codepoint offsets; splitter/mapping/hash; bounds | Review corrupted source/segmentation | Offset trên bản text khác hoặc quote không truy đúng location |
| eventType + trigger + instance attachment | Zero/multiple instances; type conditioned on trigger; giữ phủ định/speculation | Enum/instance IDs; window-copy dedup rule, không semantic merge tùy ý | Label guidelines/confusables; gold độc lập | Type không hỗ trợ, trigger/argument sai attachment |
| company/buyer/target/leader và role spans | Xác định actor/object thuộc assertion nào | Span alignment, typed exact alias/ID resolver | Typed registry/alias/version/cutoff và ambiguous review | Có tên trong bài không đủ chứng minh role; Company≠Stock |
| metric, period, scope/basis; action/instrument/title | Trích exact raw span/qualifiers và attachment | Versioned exact vocab/period grammar; calendar-date validation; giữ score upstream | New alias được review trước freeze | Không lấy publication year, bỏ qualifier hay fuzzy translate để pass |
| occurrence_id | Trích original decision/report/transaction ID/support; chỉ đề xuất same-assertion | Namespacing, registry lookup, record provenance, deterministic mint sau adjudication | Adjudicated stable business occurrence khi không có original identifier | Không dùng URL/article date/UUID model; partial time thiếu identity => HOLD |
| canonicalKey / canonical Event URI / duplicate cluster | Có thể đề xuất candidate comparison, không tự làm authority | Ordered normalized assembly, escaping, key registry, aliases, deterministic match gates | Resolve ambiguous occurrences/corrections | Same company/period/deal không đủ merge; missing không wildcard |
| Evidence sentence hoặc alternative document support | Chọn support cho cùng instance, không gom background | Reference whole sentence; fit window; alternative explicit support manifest | Annotation độc lập, approval adapter boundary | Cross-sentence fragment merge không pass reference V1 |
| factual state: negated/rumored/proposed/completed | Semantic scope, speaker/claim attribution | Map theo existing eventType/action; audit sidecar, không thêm ontology class | Annotation/edge-case adjudication | «Chưa hoàn tất» không COMPLETE; «phủ nhận» có thể là clarification assertion |
| updates/clarifies/contradicts/supersedes | Đề xuất supported relation và endpoints | Chronology/orientation, duplicate separation, asserted/inferred provenance | Adjudicate relation/context; pair gold khác predictions | Không merge clusters vì có updates; OWL reverse không new extracted evidence |
| publishedAt/acquisition/availableAt/cutoff/day 0 | Trích stated business date nếu có, không tự biết crawl history | Source metadata/proxy declaration, earliest Evidence, strict session-open calendar, freeze | Snapshot/calendars/data-source assumptions | Không model đoán timestamp, future input không cứu early assignment |
| entity/Stock linking L và route endpoints | Xác định mention/role, không suy URI bằng world knowledge | Exact typed unique resolution, endpoint ownership/availability | Curated cutoff registry and Company–Stock maps | Fuzzy-only/ambiguous/NIL => HOLD/suppress, không tự score thấp cho pass |
| route facts IndustryExposure/Subsidiary/Leadership | Event-entry semantic support; model không dựng mọi propagated facts từ bài | Bốn route executors, latest-before-validity, exposure reporting-scope selection | Eligible versioned factual datasets with provenance | Không broadcast industry tới mọi Stock; không dùng facts sau cutoff |
| expectedDirection per Event–Stock | Trích comparison/channel antecedents, không article-wide sentiment | Dictionary rule/target context; UNKNOWN on unmet/conflicting antecedents | Business-channel adjudication/gold độc lập | NEUTRAL≠missing; completion/dividend không fixed positive |
| A/extractionConfidence | A: task trained scores đúng accessor ở option A; B/C cần own score producer | Complete manifest/min/selection/replay hoặc alternative method contract | Freeze method; inspect correctness independently | LLM tự viết «0.95» hoặc sequence probability không tự là V1 per-role score |
| S/L/R/T, candidateScore, Reaction | Không tự đánh điểm source/path hay đọc CAR để gắn sign | Active constants/support origins, formula, immutable audit; AR/CAR sau window | Structured fact curation/source-price conventions | Giữ S=.5; không gọi averages calibrated; không future price leakage |

## 6. Stress-test bằng đúng dictionary, không bằng ví dụ NER dễ

Các câu sau **tự tạo** từ confusables/role constraints hiện có. Không phải dataset observations.

### 6.1 EARNINGS: kỳ/metric/assertion khác nhau

> An Bình công bố lợi nhuận sau thuế quý I năm 2026 hợp nhất. Bài khác dẫn lại số liệu ấy. Sau đó doanh nghiệp công bố báo cáo điều chỉnh lại cho cùng quý.

- Required: company, reporting_period, metric, occurrence_id (dictionary L208–212). Reprint cùng occurrence, không article URL riêng. Restatement substantive khác assertion/occurrence, thêm updates/supersedes chứ không overwrite Event (schema L130–132).
- `QUARTER2026-Q1;scope=CONSOLIDATED` khác standalone/không stated scope; basis RESTATED phải giữ (dictionary L175–192). Normalizer không được bỏ qualifiers để tăng duplicate recall.
- Forecast-only «dự báo lợi nhuận năm tới» là out-of-scope confusable FORECAST L14–16, không forced EARNINGS.
- A dễ sai do trigger «công bố» và period ở nhiều câu; B/C dễ bịa missing year hoặc combine original/restated figures. Cả hai có thể extract spans hợp lệ nhưng attach sai metric/assertion.

### 6.2 DIVIDEND: role optional không có nghĩa identity optional

> An Bình chia cổ tức bằng tiền. Bài chỉ nêu ngày giao dịch không hưởng quyền, chưa có ngày đăng ký cuối cùng. Một thông báo khác chốt ngày đăng ký cuối cùng.

- Required: company, dividend_action, occurrence_id; **record_date optional role nhưng có trong canonical key** (dictionary L218–226). Missing record_date ⇒ MATCH_EXISTING_ELSE_HOLD; không mint empty key hoặc dùng ex_date thay record_date.
- `DECLARE_CASH`, `DECLARE_STOCK`, `SET_RECORD_DATE`, `CANCEL_DIVIDEND` là actions khác (L88–92), không một «cổ tức» label chung. Mỗi assertion phải xét business occurrence, không automatically gộp hoặc tách chỉ bằng article ngày khác.
- Stock dividend confusable CAPITAL_RAISE không giải bằng NER. Cash dividend không tự expected POSITIVE nếu thiếu comparable distribution; ex-date adjustment không evidence kinh tế cho sign (L223).
- B constrained JSON có thể đầy required fields nhưng sai original identity; A BIO có thể đúng date span nhưng sai ex_date/record_date role. Registry/normalizer phải giữ khác biệt này.

### 6.3 M&A: phủ định không đơn giản là «không có event»

> Một nguồn nói An Bình đang đàm phán mua cổ phần. An Bình ra thông báo: «chưa có đàm phán cụ thể». Một bài khác nói doanh nghiệp đang xem xét mua lại. Sau đó bên mua xác nhận đã hoàn tất mua cổ phần.

- REPORTED_NEGOTIATION chỉ khi supported reported negotiation; RUMOR/PROPOSAL chưa completion; CLARIFICATION có clarification_target/action và original statement occurrence; COMPLETION có buyer/target/completion_action/occurrence (dictionary L198–207, L228–258).
- «Chưa có đàm phán cụ thể» là example clarification L245, không bỏ luôn vì negated trigger và không convert thành confirmed negotiation. «Chưa hoàn tất mua...» không completion chỉ vì có string «hoàn tất mua».
- Need link target assertion/deal theo reference registry, không merely target Company; clarification_target là EVENT_ASSERTION_REFERENCE/TRANSACTION_REFERENCE (L60–67).
- Buyer và target phải đúng bên. Completion status đơn độc chưa định directional economic benefit; đánh riêng hai issuers (L254).
- Relations/new assertions khác duplicate clusters. Contradiction cần incompatible same business context, không chỉ khác trạng thái theo thời gian; giữ assertions và Evidence, không chọn «bài mới đúng» bằng model confidence.

### 6.4 Dictionary edge cần review chứ không âm thầm «sửa cho model»

Normalization `completion_action` có `COMPLETE_ASSET_PURCHASE` (L101–104), nhưng M_AND_A_COMPLETION required `target` và role type `target:[Company]` (L48, L251), trong khi `transaction_target` mới hỗ trợ ASSET_REFERENCE (L62). Tin mua một tài sản không phải Company có thể không biểu diễn được theo required target hiện tại. **Flag representability/HOLD và xin adjudication; không tự cast asset thành Company hoặc đổi taxonomy.** Đây là phát hiện từ live dictionary, chưa sửa live spec. Ngoài ra period qualifiers không có biểu diễn hiện hành thì HOLD đúng contract, không chấp nhận output vì LLM hiểu gần đúng.

## 7. Ba alternative thiết kế — data effort, score fit và điều kiện chọn

### A. Supervised encoder pipeline: một PhoBERT + ED/type/EAE heads + deterministic registry/gates

**Flow:** original text/splitter → segment/BPE with offset map → ED trigger BIO (zero/multiple) → EventType per instance → trigger-conditioned EAE BIO → raw inventory → normalization/occurrence/typed links → complete assignment selection → routes/scoring → frozen Candidate → prices/Reaction.

**Phù hợp nhất khi:** supported type subset ổn định, có annotation time; muốn automatic slice tuân reference contract và task-score audit. Không cần pretrain PhoBERT từ đầu. Không bắt buộc thêm graph propagation/coreference model từ P2; multi-head một encoder vẫn đơn giản hơn multi-model fusion.

**Nhãn cần:** train/dev có independently adjudicated sentence/trigger/type/role spans; literal normalized values; negative no-event/background/forecast-only; multiple instances cùng câu; M&A assertion-state confusables; gold identity riêng để kiểm gate. Required roles và literals cần đủ variety, không chỉ entity NER. Development phải cover các patterns của supported types; chưa có số liệu nên không nói bao nhiêu bài là đủ. Kiểm learning curves/held-out errors khi được phép thực nghiệm; không coi 100–300 slice articles tự đủ train toàn dictionary.

**Điểm mạnh dự kiến, chưa đo:** logits/vectors và task scores theo V1 dễ lưu/replay; bounded output, ít format engineering. **Rủi ro:** label cost, unsupported cross-sentence assignments, long sentence/token budget, rare types, segmentation/offset corruption, exact span lỗi; cascade ED→type→EAE→identity. Chọn A không giải missing occurrence bằng encoder.

**Score fit:** giữ S=.5, reference A=min trained required decisions, deterministic supported conventions theo contract, L/R/T unchanged. Raw pretrained encoder scores hoặc NER heads không đủ. Calibration không prerequisite V1; min softmax scores không P(all-correct).

### B. Một generative schema-guided extractor với structured/constrained decoding

**Flow:** frozen text + compiled schema/type roles/guidelines/confusables + train/dev examples khi được phép → one model generates instance records/trigger/support/role attachment → safe parse + source-span resolution → same deterministic normalization/identity/linking/cutoff/route gates.

**Phù hợp nhất khi:** annotation-for-training chưa sẵn, nhưng người dùng cho phép model/inference và vẫn có budget làm independent gold; schema nhiều literal/contextual roles và task-head engineering là bottleneck. Có thể dùng one instruction model hoặc task-tuned seq2seq; đây là hai implementations của family, không được gộp nhãn «zero-shot» nếu đã task-trained như P3–P5.

**Nhãn cần:** dictionary compile và representative positives/near negatives; development prompt cases; **held-out gold vẫn đầy đủ** typed mentions, roles/identity/state, failure/abstention, time/cutoff. Few-shot examples là development/training input, không final labels. Nếu chọn fine-tune generative extractor cũng cần supervised records; ít/no local training không có nghĩa không annotation/evaluation.

**Điểm mạnh dự kiến:** thuận schema-as-input, document contextual interpretation, giảm hand-coded task-head decisions. **Rủi ro:** output hợp grammar nhưng bịa identity/date, exact offset/repeated span sai, wrong actor, instruction leakage giữa schema/input, forgetting roles trong long context, forecast/negation bị flatten, nondeterminism/cost. P6 chỉ cho structural constraint; backend phải thật sự hỗ trợ, không gọi prompt-only JSON là constrained decoding.

**Score fit:** V1 A đòi required trained task decision accessors. Next-token logprob/sequence probability/self-rating không tự equivalent per-role correctness. Cần separate approved method/manifest/producer; có thể nghiên cứu heuristic score nhưng phải gọi heuristic và kiểm utility với gold. Không tái dùng extraction fallback .5 từ legacy để làm output generative «V1». Nếu nghiên cứu extractor trước scoring, báo extraction-only diagnostics, chưa Candidate V1 acceptance.

### C. Hybrid «curated schema + deterministic candidate/support scaffolding + one LLM semantic parser»

**Flow:** exact original text và sentence table → versioned dictionary/typed alias/date candidates cho model như hints → one LLM quyết định event/actor/action/negation/roles/support trong declared context → code validates quote offsets, normalizes roles, resolves identity/links; registry curator xử ambiguous only → same KG/price stages under own approved method.

**Khác B:** cố ý thu hẹp output/ownership; code tạo candidates/allowed vocab và evidence IDs, model không mint key/URI, không tính score/time, không đặt source trust. Candidate scaffolding không authoritative gold. Có thể giữ model đọc mọi frozen text và cấp hints; nếu lexical prefilter loại câu/tin thì phải audit filter recall và misses, không giấu losses.

**Phù hợp nhất khi:** mục tiêu chính WFKG/RAG, registry có thể curate, muốn hạn chế model tự sinh business identity; cần nhánh inference semantic nhưng không muốn huấn luyện nhiều heads lúc đầu. **Không phải encoder+LLM ensemble hoặc weighted model fusion**, cũng không «regex làm semantics xong LLM chỉ làm đẹp JSON».

**Nhãn cần:** gold kiểm riêng candidate/prefilter coverage và semantic attachment; near-matches aliases, literal ambiguity, no-event, same-article multiple claims, missing original IDs; reviewer policy/timing. Dictionaries/candidates chỉ cần annotation nhẹ hơn task-train spans ở mặt huấn luyện, nhưng final span/role/identity gold không nhẹ đi.

**Điểm mạnh dự kiến:** responsibilities audit rõ, deterministic failure reasons; model focus vào semantics. **Rủi ro:** dictionaries narrow miss paraphrase, curation lao động hidden, mistaken alias candidate anchor dẫn model, fabricated justification hợp quote; human review sau cutoff không được upgrade baseline lịch sử. Nếu curator chỉnh predictions, đó là ASSISTED run khác, không automatic output.

**Score fit:** giống B, cần explicit alternative. Registry deterministic pass không cấp neural confidence=1; curated facts khác automatic facts, no automatic import upgrade. Tách extractor/judge/curator, không model self-score thành acceptance.

### Decision table, không xếp hạng bằng model popularity

| Tình huống được kiểm chứng ở data audit | Hướng hợp lý | Cần chấp nhận trade-off |
|---|---|---|
| Phải giữ reference slice hiện tại, có train labels tốt | A | Annotation/task heads và deliberate sentence coverage misses |
| Nhiều gold Events cần document support, contract có thể đổi | B hoặc C document adapter | Evidence/scoring/evaluator manifest phải được sửa và approved trước test; không «context bigger» là đủ |
| Annotation train thiếu nhưng có registry + independent eval budget | C hoặc B extraction-only pilot | Không claim V1 automatic Candidate khi A producer chưa tương thích |
| Names/occurrence/availability thiếu trong source | Không model nào cứu được | Cải thiện registry/source acquisition hoặc HOLD/common coverage report |
| Luận văn cần giữ scope KG/RAG hơn tối ưu NLP | Một pipeline được chốt sau pilot, không ensemble ba phương án | Extractor comparison phụ trợ, không xây whole benchmark factory |

## 8. Pilot bounded, chỉ là đề xuất chưa được thực thi

### 8.1 Trước pilot model: audit annotation/representability

Khóa source frame một lần, chọn supported subset **EARNINGS, DIVIDEND và các existing M&A labels liên quan** để có cả literals/identity và confusables; không rename eventTypes hoặc thêm lớp. Tập có no-event/out-of-scope, same-type multiple triggers, reprints, new substantive assertion, original-document IDs và IDs missing, sentence-complete versus cross-sentence, long/repeated text, exact/ambiguous typed aliases. Sampling dựa vào raw source/topic/review, không chỉ model-accepted predictions.

Gán độc lập exact text/trigger/Evidence/roles/normalized literals/business occurrence và assertion state audit; note unsupported reference representation, không exclude gold difficult. Kiểm source availability/proxy và registry có sẵn ở cutoff. Nếu metadata không đủ, xử lý data assumptions trước khi xin model budget. Không đặt target annotation count/F1/cost tự bịa; lượng train labels chọn theo role/pattern coverage và dev stability, không số articles chung.

### 8.2 Nếu người dùng phê duyệt thực nghiệm

Chỉ triển khai **một reference option và tối đa một alternative được chọn theo bottleneck đã audit**, không phải ba production systems hay fusion. Giữ raw sources, registry, cutoff, role vocabulary/gold/splits giống nhau; differences về adapter/Evidence và score producer phải ghi version và report denominator. Có oracle-mention/identity diagnostics **riêng**, không đưa gold IDs vào primary inference. Không claim causal KG benefit khi extractor/identity input khác giữa RAG baselines.

Freeze train/dev_tuning/lock-validation/held-out diagnostic/final theo canonical Event và connected assertion families, chronological quarantine khi cần. Reprints không ở hai splits. Once case dùng chỉnh prompt/model/rules thì chuyển thành debug, không còn held-out cho version ấy. Không tune final hoặc reuse judge ratings làm test gold.

### 8.3 Acceptance kế thừa contract, không invented success rate

- **INTEGRATION_DIAGNOSTIC:** plumbing có fixture/assisted riêng, sources real/synthetic declared; không NLP-quality acceptance.
- **AUTOMATIC_VERTICAL_SLICE hiện hành:** 100–300 articles frozen, task-trained reference adapter, all four route executors/test pos-neg, independent gold, V1 audit/replay, ít nhất một real automatic completed valid Reaction để end-to-end claim. Real route thiếu cases => empirical acceptance route chưa đủ, synthetic test không bù. Đây là requirements live protocol L24–43, **không số mẫu train khuyến nghị bởi paper**.
- Ít nhất 25% gold dùng reported diagnostic/final quality double-label/adjudicate theo annotation L54/L68; feedback nói 20–30%, live protocol chốt 25%. Không tự tạo minimum F1; low F1 là reportable diagnostic, fabricated fields/future leakage/invalid scoring thì không accept.
- B/C chỉ có thể claim tương ứng separate extraction diagnostic/approved method acceptance, không lén đổi reference definition. Final RQ support floors/metrics có sẵn ở protocol nhưng không áp lên first plumbing pilot.
- Technical hard tests: offsets/codepoints/text hash, invalid BIO/score producer, zero/multi-event, duplicate wrong merge/split, required identity/date missing, invalid optional key, negation/speculation, exact typed linking, early cutoff incomplete assignment, late Evidence, newest-before-validity, future facts, calendar at-open/holiday, complete predecessor/benchmark/adjusted prices, immutable scores và replay.

## 9. Evaluation: semantic gold, score/judge audit và RAG utility là ba thứ khác nhau

### 9.1 Extraction quality (RQ1)

Báo trigger detection, Evidence exact match, typed event exact sentence/trigger/type match, per-required-role P/R/F1, exact required-role-set accuracy trên **all gold**, linking end-to-end typed URI, canonical coverage, duplicate pair P/R/F1/false merge/missed merge. Unmatched predictions FP, missing/unresolved prediction FN; downstream linking failure không erase RQ1 emitted inventory. Optional roles báo riêng. State confusion theo existing M&A labels/actions + negation/speculation audit là diagnostic bổ trợ, không tự thêm ontology taxonomy. Protocol L93–105 và annotation L56–64 là comparator hiện hành.

Document alternative cần freeze adapter anchors và boundary contract; nếu primary exact matching khác, không pool F1 vào một bảng vô điều kiện. Head/Coref F1 của P3 hoặc partial matching của P5 có thể là supplemental diagnostic được predeclare, không thay exact WFKG denominator hậu kỳ. Mỗi error cần stage attribution: ED/type, attachment, literal normalization, occurrence registry, linking, availability, unsupported reference support, route facts.

### 9.2 Scores và optional judge

**Primary semantic gold = independent annotators + adjudication**, không model confidence, SHACL, CAR, extractor self-evaluation hoặc LLM judge. Nếu có judge (chưa cần thêm ở pilot), nó nhận original text/schema/predicted record, không gold/future prices. Báo agreement với sealed human gold, high-score wrong role/identity errors, abstention/coverage và stability; không lấy judge filter bỏ hard gold cases. Same model extractor/assessor có shared bias, không «independent checker». Structural validity, supported quote và semantic correctness tách rõ.

PhoBERT selected-label scores là uncalibrated task signals; LLM self-ratings/generation likelihood là signals khác. Không so trị số A raw như ngang scale giữa producers hoặc chọn model vì A lớn hơn. Cần so quality/coverage/ranking utility theo gold và explicit methods; nếu muốn probability calibration phải có target binary correctness, separate calibration data, không final tuning. V1 không bắt calibration hay dùng score threshold; giữ S=.5 control.

### 9.3 WFKG ranking và news+price

RQ2 retrieval: shared extractor inventory/selected complete assignments giữa keyword, DIRECT-only và four-route KG (`EVALUATION_PROTOCOL.md` L133–145). RQ3 weighting: weighted vs score=1 trên same eligible path population, component variants không thay selection, same gold/Stock universe (L159–173). Independently resolved gold Events thiếu predicted complete early assignment giữ empty ranking/missed positives (L73–81), không chỉ tính trên accepted outputs. Reaction missing prices loại riêng Reaction analysis, không xóa eligible inference case. CAR/reactionWeight chỉ hậu nghiệm, không dạy model phân loại relevant, chọn Evidence hay làm RAG cutoff relevance gold.

### 9.4 KG-RAG vs vector RAG — đề xuất protocol cần duyệt, không giả vờ live docs đã khóa

Live protocol L25 defer KG-RAG benchmark; note này đề nghị thiết kế sau slice, chưa thực thi/chưa thêm live RQ.

**So sánh chính:** cùng query set được curator viết/adjudicate từ frozen nguồn, cùng model trả lời và generation settings, same cutoff corpus/source availability, same answer-context budget và registry/entity scope. Vector lấy news chunks; KG/weighted KG lấy event/entity/path/Evidence records và trỏ source text. Nếu KG có structured price observations thì **vector comparator cũng được representation cùng thông tin giá** hoặc đặt riêng news-only matched-input view; không cho KG thêm price/facts rồi quy mọi improvement cho retrieval structure. Freeze indexing/chunking/query rewrite/ranking config trước final.

Bộ query nên phủ: báo cáo nào/metric kỳ nào; cổ tức action/record_date; rumor versus denial versus completion và chronology; relevant Stock gián tiếp có route provenance; sự kiện chưa đủ support tại cutoff; hỏi không có câu trả lời. Query/answer gold không lấy từ successful KG outputs. Reference answers phải cited-source, time-valid và giữ uncertainty; ground truth giá/CAR lấy frozen inputs/phép tính độc lập, không từ LLM giải thích.

Báo **retrieval** gold support recall/precision hoặc ranked retrieval utility theo query, graph path correctness/coverage, source/time-validity và evidence sufficiency; **answer** factual support, correct company/Stock/period/action/state, citation grounding, temporal errors, justified abstention, unsupported claims. Exact/structured answers dùng deterministic comparator khi có thể; semantic answers chấm blinded human rubric, optional judge là auxiliary có measured agreement, không primary gold. Trace thất bại retrieval versus extraction/identity versus answer generation. Query-level paired comparisons/uncertainty cần freeze thiết kế trước chạy; không copy Event-level RQ2 bootstrap một cách máy móc sang queries có dependence.

**Tách hai view:** end-to-end automatically extracted KG so với vector cùng inputs để đo pipeline thực; optional oracle curated/gold-KG view chỉ upper-bound diagnostic được gắn tên, không main result. Có thể hỏi ít case chậm và cụ thể trước: «Tại cutoff trước thông báo phủ nhận, An Bình đã hoàn tất mua chưa?» — hệ đúng không được dùng completion tương lai để trả lời. Đây là test temporal semantics, không đo sentiment.

## 10. Chốt lựa chọn để trao đổi với người dùng/thầy

1. Giữ domain model đủ chặt: **Event assertion/occurrence**, **Event mention/instance**, **Evidence support**, **canonical business identity**, **Candidate at cutoff** và **Reaction after window** khác nhau. Không đổi glossary/spec trong research này.
2. PhoBERT hợp nếu nhiệm vụ là supervised event extraction có labels và chấp nhận reference sentence limitation. Paper NER không đủ, nhưng supervised trigger-conditioned EAE có primary method precedent.
3. Generative/schema-guided hợp nếu trade-off annotation training versus prompt/validation/identity engineering phù hợp. Constraint chỉ bảo vệ format/vocab, không đảm bảo interpretation; P3–P5 nhiều phần đã task-trained, không proof «LLM đọc YAML là xong».
4. Hybrid một LLM + deterministic/curated infrastructure là cách khoanh scope, không multi-model fusion. Không dùng model để tạo original identity, future time hoặc price-grounded semantic gold.
5. **Chưa chốt đổi active method.** Decision nhỏ cần approval: giữ reference A cho slice hay phê duyệt B/C extraction-only/document pilot với method manifest riêng? Quyết định dựa vào audit representation/labels/registry/cutoff, không preference tên model.

## Artifacts và reproducibility nghiên cứu

- Note này: `research_confidence/EXTRACTION_MODEL_CURRENT_SCHEMA_RESEARCH.md`.
- Fetch script (network literature only): `research_confidence/fetch_extraction_primary.py`.
- Sáu primary PDFs + extracted page-marked text + URL/hash manifest: `research_confidence/sources_extraction/`.
- Không chạy training/inference/evaluation của WFKG; không claim score/metric hoặc dataset support đã đo. Search tool file-list trả rỗng dù path tồn tại; đã fallback pathlib trên đúng Windows root và đọc live files bằng read_file. Mọi paper fetch đều HTTP thành công và kiểm PDF header/title; sections thực tế đã đọc như bibliography ở mục 4.
