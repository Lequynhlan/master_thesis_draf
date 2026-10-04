# Pre-send review — presentation hiện hành DOCX / PDF / Draw.io

## 1. Kết luận trực tiếp

**Chưa nên mô tả cả gói là đã đồng bộ với WFKG-SCORE-V1.** DOCX và PDF hiện thống nhất rất tốt với nhau về text, nhưng cùng giữ scoring legacy 1.0.4 trong các bảng và đoạn được trình bày như quy tắc đang chốt. Markdown hiện hành đã chuyển sang document version 1.1.0 / WFKG-SCORE-V1. Đây là lỗi đồng bộ **presentation với current specification**, không phải bằng chứng rằng toàn bộ ontology hoặc pipeline sai.

**Không thể đóng cả 9 góp ý thầy ở mức whole-current-package.** Nhiều nội dung temporal, cardinality, provenance, route và protocol đã được xử lý rõ; structural appendix audit hiện chạy lại không có FAIL. Tuy nhiên các mục 1/3/4 và diễn giải baseline của mục 7 còn vướng scoring/version drift; mục 8 cần cập nhật tóm tắt adapter/evaluation profiles. PHASE1_ACCEPTANCE.md hiện tự phân biệt V1 với historical 1.0.4 đúng, nhưng chính DOCX/PDF chưa mang cùng ranh giới ấy.

Không yêu cầu có final metrics, NLP checkpoint hoặc crawler đang chạy để gửi **specification trước code**. Chỉ các claim acceptance/runtime mới cần bằng chứng đó; presentation hiện đã nói rõ giới hạn synthetic và Phase 2.

## 2. Phạm vi và bằng chứng mới

- Chỉ review đúng `D:\project\master_thesis\01-10-2026\chỉnh sửa mới nhất - 01-10` và feedback `ban_thay_gop_y/gop_y_phase1_truoc_code_phase2.txt`.
- Đã đọc EVENT_SCHEMA, SCORING_SPEC, EVALUATION_PROTOCOL, PHASE1_ACCEPTANCE hiện hành; đọc ontology TTL, parse SHACL và kiểm tra cấu trúc property shapes/SELECT. Không dùng historical matrix ngoài gói làm current truth.
- DOCX: kiểm tra **332 body paragraphs**, **30 tables**, tổng **1,236 paragraph/cell text units**. Locator `Pxxx` đếm direct body paragraphs; `TxxRxxCxxPxx` chỉ table/row/cell/paragraph (1-based), không phải số trang Word. Empty P332 không xuất hiện trong text dump do không có text.
- Kiểm tra **168 printed property rows** bằng direct class/property SHACL cardinalities; không phát hiện cardinality mismatch hoặc missing direct-shape property trong bảng 22 lớp. So sánh này không chứng minh mọi mô tả free-form, OWL inference hoặc constraints phức hợp tương đương.
- PDF: **47 physical pages**, extraction đầy đủ. Tất cả text units có nội dung được tìm thấy sau whitespace normalization và bỏ đúng footer lặp. 8 apparent mismatches ban đầu đều là đoạn qua trang bị footer chèn giữa, không phải stale PDF. `final_docx_pdf_text_comparison.json` ghi missing=[]; không suy ra visual equivalence từ text.
- Draw.io: đọc XML labels và connectors của **toàn bộ 7 tabs**; artifact extraction giữ tab/cell/source/target/style locators. Các business-process arrows không mặc nhiên là RDF triple direction.
- Đọc source audit trước khi chạy: script stdout-only, không sửa input, đường mặc định relative to script; đã chạy `python -B .../tools/audit_schema_diagram.py --json` và lưu stdout ngoài gói. Kết quả mới: **337 PASS / 0 FAIL / 57 NOT CHECKED**, exit 0; **44 SHACL SELECT syntax parses**. Đây không phải SHACL behavioral run hoặc V1 acceptance.
- Extract **9 referenced embedded PNG cards**, map OOXML relationships tới paragraph; render **47 PDF page PNGs** ngoài gói; tạo đúng **3 contact sheets**. Đã xem pixels các contact sheets, không gọi XML inspection là visual review.
- Tất cả submission-file SHA256 trước/sau probes không đổi. Không sửa canonical artifact, old matrix, hoặc output có sẵn trong submission.

## 3. Phát hiện cần xử lý trước khi nói “current V1 synchronized”

### P-01 — HIGH: current-version authority trong DOCX/PDF vẫn là legacy

**Locator:** DOCX P020; PDF p4; DOCX P028/P104/P116/P123/P322; PDF p5/p21/p24/p25/p45. Draw.io tab `01-Tổng quan đề tài`, cell `mZ28CVNe_N0uJWWchiWa-45`; tab `05-4 Đường liên hệ chính`, cell `weTA0hvWxfCujyoZNfAk-11`.

**Literal:** P020 nói “Phiên bản contract hiện hành là 1.0.4”; P123 dẫn “SCORING_SPEC.md 1.0.4”. Diagrams dùng “Baseline 1.0.4”. Báo cáo không có current V1 producer/method boundary để giải thích vì sao included Markdown khác nó.

**Current authority:** SCORING_SPEC L3–6/L14–29, EVENT_SCHEMA L3–6, EVALUATION_PROTOCOL L3–5; PHASE1_ACCEPTANCE L3–23 ghi active WFKG-SCORE-V1 và historical boundary. TTL ontology version 1.0.4 là **structural version được chủ ý giữ**, không phải tự thân lỗi.

**Tác hại:** người đọc có hai numerical baselines với cùng “hiện hành”, dễ code legacy rồi nói đã theo V1.

**Minimal remedy:** thêm scope/version map ngắn ngay đầu DOCX/PDF; đổi current numerical prose sang V1, hoặc tách report/diagram thành rõ ràng historical illustration và không dùng nó làm current implementation spec. Không đổi namespace, tên file, classes hoặc nâng TTL version chỉ để giống document version. Diagrams nên ghi structural schema 1.0.4 / active scoring method V1 thay vì đánh đồng hai version dimensions.

### P-02 — HIGH: relationStrength của cả ba INDIRECT paths vẫn .5

**Locator:** DOCX `T20R07C04P1`, PDF p13; DOCX P122, PDF p25; `T30R08C02P1`, PDF p44 (“thử exposureStrength thay hằng số 0,5”).

**Observed:** DIRECT=1, ba INDIRECT=.5; câu “Scoring đã khóa”.

**Expected current:** SCORING_SPEC L193–206, EVENT_SCHEMA L44–54: **T=1 cho cả bốn eligible routes**. Exposure comparison được version riêng sau automatic slice (EVALUATION_PROTOCOL L169), chỉ thay INDUSTRY T với population/Evidence/other components giữ V1.

**Minimal remedy:** sửa đúng table cell và P122, đồng bộ appendix variant baseline từ .5 sang 1. Nếu giữ số .5 lịch sử phải ghi legacy method riêng. Không tự đổi structural range `[0,1]`, exposure fields hoặc ownership.

### P-03 — HIGH: extraction fallback thiếu calibration trái với trained V1 accessor

**Locator:** DOCX `T20R18C04P1`, PDF p14; DOCX P123, PDF p25; P319, PDF p45 (generic future extractor/linker/calibration wording).

**Observed:** assignment có căn cứ nhưng chưa calibrated nhận fallback .5. Bảng và prose vẫn dẫn 1.0.4.

**Expected current:** SCORING_SPEC L67–111/L113–125: pretrained PhoBERT chưa phải extractor; cần trained ED/EAE adapter, min scores của trigger/type/required roles và mandatory neural decisions; **không extraction fallback**, calibration không prerequisite của slice. Missing/invalid neural score là producer error, missing required role là coverage miss/HOLD.

**Minimal remedy:** thay trọn câu fallback, không chỉ đổi từ “calibration”; tóm tắt task-trained scores và dẫn đúng SCORING_SPEC 1.1.0. Giữ historical synthetic images labeled, không dựng số output mới khi chưa chạy V1.

### P-04 — HIGH: DIRECT relation confidence lấy A; automatic mapping có calibrated/fallback values

**Locator:** DOCX `T20R20C04P1`, PDF p14; DOCX P124, PDF p25; linking cell `T20R19C04P1` cũng chưa nêu current exact-registry gate/L=1.

**Observed:** Event–Company dùng assignment score từ Evidence; Company–Stock automatic dùng calibrated score hoặc fallback .5.

**Expected current:** SCORING_SPEC L138–160/L166–191: accepted exact typed unique registry links L=1; fuzzy-only/ambiguous/absent links HOLD/suppress. **R=min required edge support origins**, automatic evidenced=.5, curated structured eligible=1; **không copy A hoặc linker score sang Event-entry R**. Relation support và entity identity là hai kiểm tra khác nhau.

**Minimal remedy:** sửa table và P124 cùng lúc; thêm distinction A/L/R với support-origin record/provenance. Không suy curated từ việc import vào structured registry. Không cần lớp/property mới, audit sidecar đã được current specification cho phép.

### P-05 — MEDIUM: adapter/instance-aware evaluation hiện hành chưa được reflected trong report

**Locator:** DOCX P127, PDF p26; P130, PDF p27–28; P296–P306, PDF p41; P319, PDF p45. Toàn bộ paragraph/table dump **không có PhoBERT hoặc LLM**.

**Observed:** P127 nói exact matching trên articleId/offsets/eventType mà không nêu **trigger anchor**; vertical-slice plan là generic extraction → linking → Candidate, rồi “thực hiện đánh giá RQ1–RQ3”. Điều này không đồng nghĩa model đã chạy, nhưng chưa truyền đạt revised automatic method và milestones.

**Expected current:** EVENT_SCHEMA L134–143: `V1-SENTENCE-TRIGGER-BIO`, automatic original-text sentence splitter, trigger-conditioned EAE, multiple event instances, no fragment merge; EVALUATION_PROTOCOL L18–56/L93–105: three profiles, instance key có sentence + trigger + type, separate automatic/ASSISTED outputs; final full RQ metrics không chặn first integration.

**Minimal remedy:** thêm một đoạn tóm tắt trained PhoBERT ED/EAE/reference adapter và exact typed-match key có trigger, dẫn protocol; cập nhật plan rõ INTEGRATION_DIAGNOSTIC → AUTOMATIC_VERTICAL_SLICE → FINAL_RQ. Không gọi pretrained PhoBERT là automatic ED/EAE checkpoint; không yêu cầu calibration/full RQ trước first integration. Nếu định dùng LLM, hiện presentation **không cho bằng chứng có hay không implementation**; LLM variant không được tự thay current trained adapter contract. Đây là omission/summary drift, không phát hiện câu “LLM đã chạy” hay “PhoBERT đã fine-tune” sai.

### P-06 — MEDIUM: L neutralization không được nói là informative confidence ablation

**Locator:** DOCX P012/P129, PDF p2–3/p27; `T30R09C03P1`, PDF p44.

**Observed:** report trình bày ba component ablations nhưng chưa báo L là constant 1 và R có thể constant .5 trong automatic population. Công thức/ba variants bản thân vẫn đúng.

**Expected current:** SCORING_SPEC L290–300, EVALUATION_PROTOCOL L167–173: L ablation no-op/non-informative, không chứng minh linking unimportant; fixed S/T không measured source/path magnitude.

**Minimal remedy:** thêm caveat ngay cạnh ba ablations. Không xóa L gate, không invent variation hoặc đánh đồng non-informative score ablation với bỏ linker.

### P-07 — MEDIUM wording risk: market join “theo cutoff” trong kế hoạch

**Locator:** DOCX P302; PDF p41: “Ghép dữ liệu thị trường ... theo đúng phiên giao dịch và cutoff”.

**Why bounded:** P105, p21–22 và Draw.io tab01 cell `mZ28CVNe_N0uJWWchiWa-32` đã giải thích rõ hậu nghiệm observations không giới hạn bởi Candidate cutoff. Vì vậy đây là câu mơ hồ, **không phải confirmed contract reversal**.

**Minimal remedy:** nói cụ thể theo configured window/calendar và `observation.availableAt <= Reaction.availableAt`, không theo Candidate inferenceCutoff. Không thay Candidate/Event cutoff/day-0 rules vốn đang đúng.

## 4. Literal embedded SPARQL — actual document order

Đã đọc theo numbered Query headings, không chỉ quét PREFIX. **10/10 queries parse PASS trong saved DOCX paragraph order**; không cần repair/reverse in-memory. Kết quả này đóng lỗi query order/syntax trong artifact hiện tại, không xác nhận query behaviors trên original fixture.

| Query | DOCX code locator | PDF page | Literal scope và giới hạn |
|---|---|---|---|
| Q1 | P150–P155 | 31 | Article/Evidence/Event mandatory join, ORDER BY publishedAt/articleId. Article availableAt được projected; không phải full Evidence/Event availability validator. |
| Q2 | P162–P166 | 32 | Event–Company–Stock–Candidate linking illustration. Không tự kiểm toàn bộ route/original linking decisions. |
| Q3 | P173–P177 | 33 | Candidate components/status/day đủ projected; neither V1 constants nor trained producer được validate bằng SELECT. |
| Q4 | P184–P192 | 34 | Two hard-coded cutoffs; Article + Evidence + Event availability đều filtered. Đây là information-retrieval at named instants, không tự validate Candidate equality/frozen fact inputs. |
| Q5 | P199–P207 | 35 | Snapshot prerequisite đúng. Benchmark variable `?index` không bind tới selected benchmark; group không có Candidate ID, có thể gộp paths cùng Event/status/day. |
| Q6 | P214–P216 | 36 | Clarifies direct assertions; không chứng minh canonicalization/OWL correctness. |
| Q7 | P223–P257 | 37 | YEAR baseline, latest-before-validity; VALUES lặp trong mỗi UNION branch. Identity-correction và scope-prefilter caveats được ghi P221; query không general correction-aware executor. |
| Q8 | P262–P266 | 38 | Completed reaction values; score/time selection không enforced bởi query. |
| Q9 | P273–P277 | 39 | Mandatory hasEventStockCandidate nên bỏ zero-Candidate Events. Chỉ duplicate-cardinality diagnostic trong demo có Candidates, không full coverage metric. |
| Q10 | P284–P291 | 40 | Full price/provenance SELECT cần dataQualityFlag, queries both Stock/benchmark. Không tự kiểm đúng asset, dates/calendar, arithmetic hoặc original CSV 8 rows. |

### Bounded query issues, LOW trong historical illustration / MEDIUM nếu tái dùng như gate

- **Q5**, P205: independent benchmark count có thể false-positive “có benchmark”. Synthetic isolated diagnostic với một index không liên quan và không có Stock observation trả `day0Stock=0, day0Benchmark=1, reactions=0`. Không phải original demo output. Minimal remedy: bind benchmark từ frozen run configuration/selected task; group theo Candidate nếu mục đích per-path; thêm availability cutoff nếu không dùng immutable snapshot.
- **Q9**, P276: isolated diagnostic có Event `ZERO_CANDIDATE_DIAGNOSTIC` with article/no Candidate; query chỉ trả Event còn lại. Minimal remedy nếu dùng coverage: start from Event/articles, OPTIONAL Candidate/Reaction, bổ sung eligible Event denominator. Không dùng query này thay independent gold universe.
- **Q7**: hardcoded oldestPeriod phù hợp hai fixture cutoff cùng ngày; không general rolling-staleness implementation. Existing narrative đã giới hạn fixture/scope/identity correction, nên không mở lại thành blocker mới.
- Không có demo snapshots, CSV/JSON hay runner trong current package; **không tái lập row counts gốc**, không fabricating dữ liệu để gọi chúng đã verified. P146/P156…P294 đã disclose history và missing files. Do đó thiếu runtime không phải blocker gửi spec, nhưng không được nâng “Executed RDFLib result” trong ảnh lên current V1 execution evidence.

## 5. Draw.io — all-tab literal semantic audit

| Tab | Đã kiểm tra | Kết luận / limit |
|---|---|---|
| 00-WFKG Ontology | Actual RDF connector source/target + child edge-label association. publishedBy/extractedFrom/supports/reports, Event-entry properties, Candidate/Reaction edges, market provenance, Bank subclass, temporal roles. | Parent owns hasSubsidiaryRelation: edge `2411blnfpnkDnIr3tklR-3` starts parent cell `...-5`, targets relation `_9t47sVXSXdLGc_MMRv3-1`; parentCompany edge `...-6` points back same parent; subsidiaryCompany edge `...-9` points child `R3vZ3JpwLF3V6DxzlldD-2`. No reverse parent→child inference claim found. Overview intentionally omits some inverse/endpoint connectors; complete vocabulary in tab06, not contradiction by omission alone. |
| 01-Tổng quan đề tài | Business flow, output inventory, scope note, all four paths, availability vs Reaction timing. | Correct separation of Candidate/Reaction and no causal claim; legacy 1.0.4 label needs method-version boundary (P-01). |
| 02-Tin tức đến sự kiện | Source/Article/Evidence/Event arrows, label grammar, GovernmentOrganization, datatype availableAt note. | `Source → Article` with label `Article publishedBy Source`, and `Article → Evidence` with `Evidence extractedFrom Article`, are explicitly **business reading direction**, not RDF direction error; cell `...-2` says so. No reason to reverse these process arrows. |
| 03-Chuẩn hóa thực thể | Alias/ticker string vs separate Stock URI; registry process vs hasStock; parent-owned relation and child endpoint; tenure selection vs IndustryExposure. | Ownership and YEAR/staleness selection literal text match current structural/temporal contract. Cell `A1VN0XJZ2zYTKMQ9EYZ1-37` explicitly separates validity from reporting-period rule. |
| 04-Event-Stock trực tiếp | Candidate component inventory, market observations include adjustedClose/provenance, Reaction inverse narrative and completed-window equations. | Formulas and timing current-compatible. **No numeric INDIRECT=.5 assertion found in this tab**; do not invent numerical diagram defect because report is stale. Minor `candidateStatuscandidateStatus:` duplication in cell `izqzSf6VaLfidQc68PAD-19` is LOW presentation cleanup, not model error. |
| 05-4 Đường liên hệ chính | Four topology templates incl. child→parent and industry exposure; timing note. | Route semantics match. `weTA0hvWxfCujyoZNfAk-11` legacy version label needs boundary. Diagram traversal arrows are explanatory route codes, not new forward RDF property from child to relation. |
| 06-Phụ lục Entity Property | Object owner/target, printed cardinals, datatype ownership, complete inventory incl. subsidiaryCompany/memberStock/exposureBank/exposureIndustry/forEvent and four scores. | Fresh audit 337 PASS/0 FAIL/57 NOT CHECKED. Unprinted datatype ranges/shared provenance/free-form labels are not certified by tool. No detected structural property contradiction in inspected literal labels. |

**Visual limitation:** Draw.io tabs were **not freshly rendered** in this subreview. All-tab XML/connector semantic inspection is real, but does not verify text clipping, routing overlap, font or readability in the actual viewer. Historical render claims in acceptance file are historical only; main agent should visually verify diagram if making a fresh visual approval claim. No Draw.io screenshots were fabricated from XML.

## 6. Embedded images và actual PDF visual review

Đã xem pixels trên `contact_docx_embedded.png`: cả 9 result cards ghi **SYNTHETIC TEST ONLY**, selected-field summaries, “NOT a Fuseki screenshot”, và reference adjacent CSV/JSON (không ở gói). Q1/Q3/Q5 day=2026-08-27; Q10 có predecessor 26/08 và day0 27/08, nên không phát hiện stale 26/08-day0 bằng pixels ở lượt này.

- Q3 image3 (P179/PDF33) có displayed `READY`, confidence .80/candidateScore .800; current caption P180 giải thích READY là display abbreviation, không RDF enum. Đây là **legacy synthetic values**, không current V1 producer output. Không gọi nó lỗi current RDF vì không có exact graph để kiểm.
- Q5 image5 (P209/PDF35) hiển thị PENDING/zero observations/reactions; label PENDING cũng là card display, không xác nhận actual serialized enum.
- Q8 image8 (P268/PDF38) có AR/CAR .04 và reactionWeight .3200; chúng là historical fixture, không measured reaction hoặc V1 execution.
- Q10 image11 (P293/PDF40) thể hiện closes 30/31.50 và 100/101.00 cho hai ngày. Không lấy selected-field card thay full adjusted-price provider/calendar/version evidence.
- DOCX/PDF captions đã disclose historical status rõ, vì vậy **không yêu cầu tái tạo ảnh là mandatory fix** nếu chỉ giữ historical appendix. Cần thay current-version wording ở bên ngoài ảnh; không ghép ảnh cũ vào new acceptance evidence.

Đã xem overview 47 PDF pages: không thấy blank pages thực sự, table bị đẩy ra ngoài page, hoặc overlap lớn ở scale contact sheet. p28 có ít nội dung tiếp đoạn, không là blank. Selected detailed sheet p2/12/13/14/24/25/26/27/28 cho thấy bảng scoring và legacy prose đọc được, không obvious clipping. Property names wrap mạnh trong narrow columns; PDF query code/cards nhỏ nên cần zoom original pages (nhất là p37 và p40). Đây là layout/readability spot check, **không proofreading từng ký tự 47 pages**, và không render lại DOCX độc lập.

## 7. Đối chiếu góp ý thầy riêng với current presentation

| # | Verdict trong phạm vi presentation | Evidence / việc tối thiểu |
|---|---|---|
| 1 Sync PDF–Drawio–TTL | **PARTIAL: structural vocabulary tốt, active-version/numerical sync chưa xong** | namespace, class/property và four routes literal phù hợp; P-01–04 ngăn whole-current-V1 verdict. |
| 2 Daily effective date | **ADDRESSED at specification/presentation level** | DOCX P104/P134/P135, p21/p29; strict opening, equality moves next session, cutoff earliest Evidence, no delaying missing assignment; images now 27/08. Real calendar runtime not verified and disclosed. |
| 3 Confidence components | **STRUCTURAL ADDRESSED / CURRENT NUMERICAL DRIFT** | Candidate scores all in table/tab06; source .5/freeze compatible; extraction/linking/relation policies P-03/P-04 remain legacy. |
| 4 Candidate vs Reaction score | **TIMING/FORMULAS ADDRESSED / CURRENT STRENGTH DRIFT** | P012/P097/P129 and tab04/05 separate inference ranking vs post-window; P-02 persists. |
| 5 Market provenance | **ADDRESSED at schema/presentation level** | Stock/index adjustedClose, predecessor/full window, sources/availability; Q10 exposes inputs. Provider/calendar/recomputation real runtime explicitly pending. P-07 is narrow wording fix. |
| 6 Event Dictionary | **PRESENT, not NLP-executed** | report P330/appendix, current package YAML; review does not claim independent completeness of every dictionary example or normalization rule. |
| 7 Data rules | **Temporal/reporting/staging addressed; numerical comparison baseline needs sync** | reports 0..*, selected latest before validity, YEAR/scope/staleness; P-02 appendix still compares .5 baseline, active V1 uses 1. Experiment retained separately in current MD. |
| 8 Frozen evaluation | **CORE ADDRESSED / NEW ADAPTER/PROFILE SUMMARY DRIFT** | common universe, no outcome-ranked Candidate, independent gold, route projection/macro and 25% double-label present; P-05/P-06 updates needed. Final performance not claimed. |
| 9 Drawio appendix | **ADDRESSED within supported structural comparison; visual NOT CHECKED here** | actual property inventory and fresh 337/0/57 audit. Do not reinterpret 57 NOT CHECKED as 57 defects or reviewer coverage %. |

Đây không thay independent review của logic/NLP literature. Các verdict về dictionary/gold/protocol nằm trong scope presentation synchrony, không toàn bộ method adequacy.

## 8. Artifacts, reproducibility và limits

External output root: `D:\project\master_thesis\01-10-2026\review_phase1\presend_current_presentation_assets`.

- `docx_all_text.txt`: full paragraphs/table text với stable locators.
- `pdf_all_pages.txt`: full text với physical page delimiters.
- `docx_pdf_page_locators.json`: exact within-page/cross-page anchors; 8 apparent failures ban đầu phải đọc cùng final footer-normalized result, không dùng intermediate empty locators làm stale-PDF finding.
- `final_docx_pdf_text_comparison.json`: final no missing text units.
- `drawio_all_tabs_cells.txt`, `all_connector_inventory.json`: all-tab XML literal/connector provenance, **not visual render**.
- `schema_diagram_audit.json`, stderr file: actual stdout/stderr of existing safe audit.
- `docx_table_structural_comparison.json`, `docx_missing_direct_shape_properties.json`: all 168 rows checked, no detected direct cardinal mismatch/missing direct shape fields.
- `literal_queries.json`: ten complete queries in actual order, parse outcomes.
- `isolated_query_diagnostics.json`: Q5/Q9 fresh synthetic counterexamples, not original fixture results.
- `docx_image_locations.json`, image1.png…image6.png/image8.png/image9.png/image11.png; `pdf_page_01.png`…`pdf_page_47.png`.
- Exactly three contact sheets: `contact_docx_embedded.png`, `contact_pdf_all_47.png`, `contact_pdf_scoring_eval.png`.
- `source_hashes.json`, `final_source_preservation.json`: source snapshot/check that all package files unchanged.
- Probe scripts only external: `extract_presentation.py`, `verify_literal.py`, `final_checks.py`; scripts refuse overwriting outputs. A nonfatal Python SyntaxWarning on a query-heading regex in the external verify script did not prevent execution or parsing; no package amendment made.
- `artifact_hashes.json`: SHA256 manifest for report plus external assets (manifest does not hash itself).

Không chạy suite behavioral SHACL 31 tests trong subreview này; historical PASS không được coi là rerun. Không train model, run crawler/market provider, calculate real ranking/RQ, verify all feedback behavioral constraints, hoặc export/render Draw.io. No canonical edits, no commits, no altered old matrices. Minimal remedies nêu trên là đề nghị để main agent trình user; **chưa được thực hiện/không suy approval từ read-only review**.
