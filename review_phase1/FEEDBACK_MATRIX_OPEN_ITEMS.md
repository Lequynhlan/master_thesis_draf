# Feedback matrix — review lại từng góp ý của thầy sau khi bổ sung audit

## Phạm vi và cách đọc

- Nguồn yêu cầu: `ban_thay_gop_y/gop_y_phase1_truoc_code_phase2.txt`, đúng 9 mục được đánh số trong file.
- Artifact review: chỉ `chỉnh sửa mới nhất - 01-10/`. Không lấy sibling folder, demo cũ hoặc backup làm bằng chứng bộ hiện hành đã chạy.
- TTL/SHACL là source of truth. Audit phụ lục không chứng minh toàn bộ DOCX/Draw.io tương đương về ngữ nghĩa.
- Matrix nằm ngoài gói gửi thầy. Sau review, user đã duyệt và hoàn tất D01–D05 trong scope tài liệu/contract. D03 giữ TTL đối xứng, tách assertion/suy luận và final unordered projection. E02 chưa sửa.
- `P…` là paragraph và `T…R…` là table/row, đánh số 1-based bằng python-docx; không phải số trang.
- Phân biệt: **đặc tả/schema**, **đồng bộ artifact**, **machine-check**, **behavioral validation**, **visual verification**, **runtime Phase 2**.
- Trạng thái hiện tại cập nhật sau sửa D01–D05. Các phát hiện review được lưu như lịch sử; không coi các lỗi đã sửa vẫn đang tồn tại.

## Kết luận hiện tại

1. Luồng đặc tả chính vẫn nhất quán: Article/Evidence → canonical Event → Candidate tại cutoff → market window → Reaction hậu nghiệm. Chưa phát hiện nhu cầu mở rộng ontology từ các kiểm tra trong vòng này.
2. D01/D02/D04/D05 đã FIXED trong phạm vi được duyệt: hai ô stale đã sửa, Query 4 đúng thứ tự và 10/10 query parse, returnValue mandatory derived/cache, bảng ablation quy đúng candidateScore.
3. D03 đã chốt và đồng bộ contract, có 8 regression synthetic PASS; E02 (nơi enforce hai luật Reaction) vẫn cần chốt. Thiếu calendar/provider thật, snapshots, gold hoặc kết quả RQ không tự là lỗi Phase 1.
4. Không sửa ontology/SHACL/Draw.io, công thức, nguồn dữ liệu hoặc ảnh demo. Backup trước sửa D01/D02/D04/D05: `review_phase1/backups/before_D01_D02_D04_D05_20261003_191448/`; trước D03: `review_phase1/backups/before_D03_20261003_195336/`. Visual chưa kiểm chứng; soffice/pdftoppm không khả dụng trong PATH.
5. Gap visual và behavioral SHACL vẫn mở. Không dùng parse/audit assertion count để đóng các gap đó.

## A. Ma trận theo đúng 9 góp ý

| Mục / dòng nguồn | Yêu cầu thầy | Bằng chứng bộ hiện tại | Machine-check / giới hạn | Kết luận và việc còn lại |
|---|---|---|---|---|
| **1 — L7–24** | Cùng WFKG/namespace; đúng bốn route baseline; không suy ngược parent→child hoặc lan tới mọi Stock cùng ngành; TTL/SHACL chuẩn | `EVENT_SCHEMA.md` L5–7, L30–39. DOCX P20/P28/P319; Draw.io tab 01 cell `mZ28CVNe_N0uJWWchiWa-46` ghi INDUSTRY chỉ Bank có exposure hợp lệ, SUBSIDIARY chỉ child→parent. Tab 05 cell `weTA0hvWxfCujyoZNfAk-11` ghi `relationPath=impactType` | TTL/SHACL parse; route/code constraints đọc tại shapes L148–317; audit appendix PASS trong phạm vi hỗ trợ. Không có PDF hiện hành trong package để review | **Schema/route và hai ô status D01 đã sửa trong scope đã kiểm tra**. Không suy ra toàn bộ narrative/visual đã verify. Nếu xuất PDF, dùng DOCX hiện tại, không tái dùng PDF cũ |
| **2 — L26–36** | Daily: trước mở cửa dùng phiên đó; từ khi mở cửa trở đi dùng phiên tiếp theo | `EVENT_SCHEMA.md` L80–88: strict-open, timezone, calendar coverage, proxy availability; DOCX P131–132/P168/P194. Các ảnh Q1/Q3/Q5 ghi t0=2026-08-27; Q8 Reaction available 27/08 | Đã đọc các ảnh nhúng hiện hành và text, không chỉ correction note. Không execute calendar/provider thật hoặc fixture query demo | **Fixed ở mức đặc tả và ngày hiển thị trong ảnh liên quan**. Exact-open cũng đã chốt. Runtime calendar là Phase 2; render layout vẫn NOT CHECKED |
| **3 — L38–56** | Lưu bốn component; rule source nhiều Evidence, entity linking, DIRECT; freeze tại cutoff | `SCORING_SPEC.md` L14–47; `EVENT_SCHEMA.md` L60–69. DOCX T20R17–R19/P121/P126. Shapes L194–198 (required/range), L235–242 (mean), L262–268 (source fixed). Có linkingConfidence trong TTL/appendix | Property/schema checks và SHACL SELECT syntax có bằng chứng. Không kiểm thử behavior confidence, calibration hoặc immutable snapshot | **Fixed ở mức contract**. Source=0.5 là control, không dùng maximum source quality; linker minimum, DIRECT minimum links, fallback có provenance. Ba component ablations giữ source=0.5; không làm source ablation trong baseline |
| **4 — L58–74** | candidateScore dùng inference; reactionWeight chỉ sau window; không leakage | `SCORING_SPEC.md` L24–31/L49–76; `EVENT_SCHEMA.md` L41–48; `EVALUATION_PROTOCOL.md` các mục RQ3, Baseline component ablation contract và Frozen metric and sampling contract; DOCX P121/P126, T20/T21 | Formulas và ownership có ở schema/SHACL; chưa chạy ranker chống leakage. **Query 4 hiện đã parse sau sắp xếp lại đúng thứ tự; cả 10 query syntax PASS** | **Scoring/anti-leakage spec và D02/D05 fixed**. E02 về Reaction enforcement vẫn OPEN; query syntax không chứng minh runtime chống leakage |
| **5 — L76–90** | Stock/index adjustedClose đủ t−1 và t, toàn bộ window; AR/CAR tính lại được | `EVENT_SCHEMA.md` L50–58/L75–76/L88; `SCORING_SPEC.md` L51–65. Shapes MarketIndexObservation L854–879, MarketObservation L898–927; Reaction có ownership/date/arithmetic constraints. DOCX T17/T19/T21 và P279–289 | Đã đọc image11: mỗi Reaction có Stock và benchmark 26/08 và 27/08, adjustedClose được hiển thị. Đây là ảnh fixture lịch sử, không phải thực thi mới; không có CSV/graph để xác nhận đầy đủ URI/provenance. Calendar-aware exact sessions vẫn ngoài SHACL | **Provenance contract và D04 wording đã fixed**: SCORING_SPEC L61 ghi mandatory derived/cache, thống nhất EVENT_SCHEMA/SHACL. Full behavioral coverage NOT CHECKED; dữ liệu/provider thật thuộc Phase 2 |
| **6 — L92–108** | Dictionary machine-readable 10–15 types: roles, canonical key, direction, examples/confusables | `EVENT_DICTIONARY.yaml` version 1.0.2, 14 entries; identity_policy/direction_policy L4–24. `EVENT_SCHEMA.md` L97–103 và `ANNOTATION_GUIDELINE.md` L29–36 cùng quy tắc identity | YAML parse PASS; cả 14 entries có field yêu cầu, canonical-key fields có trong roles, confusables tham chiếu declared type hoặc declared out-of-scope. Không chạy NLP/extraction hoặc đánh giá chất lượng gán nhãn thực tế | **Dictionary/identity fixed ở mức machine-readable**. Missing optional key có HOLD/MATCH policy; article dates không tạo identity; updates/clarifies không union duplicate clusters. Semantics `contradicts` đã đồng bộ D03: đối xứng, assertion convention khác final unordered projection; không đổi dictionary |
| **7 — L110–118** | reports staging; exposure reporting period/latest available/staleness; exposureStrength variant | `EVENT_SCHEMA.md` L17–28/L77–78/L90–95; `SCORING_SPEC.md` L39/L85. DOCX T5R8/P100/P102/P322–324. Shapes reports L930–956 không bắt minCount; exposure L723–779 có period/strength contract | Audit đối chiếu reports [0..*]. YEAR/latest periodEnd/availableAt/URI/staleness đọc trong spec; curated gate/selection chưa execute | **Ba phần đã fixed ở mức đặc tả**. Không fabricate exposure để dùng baseline 0.5; variant đo trên cùng eligible cohort. Query 7 parse nhưng kết quả fixture chưa tái lập (P255 ghi rõ) |
| **8 — L120–137** | Tách vertical slice/final; annotation Evidence/type/link/identity/relevance/direction; double label; theo impactType và macro Event | `EVALUATION_PROTOCOL.md` Dataset separation/Annotation and freeze/Two-stage Event-relation evaluation/Frozen metric and sampling contract; `ANNOTATION_GUIDELINE.md` Required labels/decision rules/agreement. 25% double-label; resolved 0/1/2, UNKNOWN direction tách uncertainty; paired Event bootstrap và frozen metric edge cases | Review nội dung contract; không chạy metric runner, split/gold/adjudication hoặc RQ. Audit schema không kiểm chứng các bước này | **Protocol/annotation và D03/D05 đã fixed ở mức contract**: chấm asserted assignment, kiểm tra OWL-RL và graph cuối; final contradicts unordered, các relation còn lại directed. 8 test synthetic không thay thực nghiệm RQ. Support floor và CI không hứa đủ power. Final data/actual evaluation là Phase 2 |
| **9 — L139–154** | Appendix property đúng TTL/SHACL; tool generation hoặc audit tự động | Có `tools/audit_schema_diagram.py`, `tools/README.md`; portable/read-only. Property endpoint/cardinality structured appendix được đối chiếu; shared/unstructured thiếu thông tin báo NOT CHECKED | Fresh audit 336 PASS / 0 FAIL / 57 NOT CHECKED; 7 tests công cụ pass trên canonical/copies mutation. Audit không đọc DOCX, không inspect mọi narrative tab hoặc render | **Cơ chế/appendix audit và report integration D01 fixed trong scope**; 0 FAIL không chứng minh narrative/visual equivalence |

## B. Trạng thái các lỗi/gap — D01–D05 đã sửa trong scope; E02 chờ duyệt

### D01 / E01 — FIXED: hai ô trạng thái Draw.io

- Trước sửa T30R2/T30R10 còn báo sơ đồ có contradiction; hiện đã thay trực tiếp hai ô bằng trạng thái đúng và giới hạn audit.
- Tab 05 cell `weTA0hvWxfCujyoZNfAk-11` không sửa trong lượt này.
- Verified old sentences absent trên toàn paragraphs/tables; DOCX ZIP/XML hợp lệ, chỉ word/document.xml thay đổi.
- **Trạng thái:** FIXED trong scope được duyệt; không tự đóng visual/narrative review.

### D02 — FIXED: Query 4 đúng thứ tự

- P181–P189 trước sửa đảo ngược. Đã sắp xếp lại các paragraph nguyên vẹn thành PREFIX → SELECT → VALUES → patterns → FILTER → closing brace/ORDER BY.
- Chỉ đổi thứ tự, giữ nguyên nội dung FILTER cutoff, fields và values. Không tạo fixture/CSV/kết quả demo mới.
- Trích literal order từ DOCX hiện tại: **10/10 query syntax PASS**.
- **Trạng thái:** FIXED syntax; query execution và anti-leakage runtime vẫn chưa verify.

### D03 — FIXED contract: đối xứng, hai tầng kiểm tra, final cặp không thứ tự

- User duyệt giữ `contradicts` đối xứng. Assertion lưu mới→cũ để truy vết; chronology lấy từ Evidence gốc. Tied/unresolved chronology có URI tie-break và audit flag, không tạo ngày giả.
- Tầng 1 chấm assignment trực tiếp trên ordered assertion universe. Tầng 2 kiểm tra OWL-RL trên ontology/cutoff snapshot đóng băng, rồi chấm graph cuối với semantic gold độc lập.
- Final contradicts dùng khóa hai URI được sắp xếp, deduplicate hai chiều; reverse không là semantic NONE, không đếm lặp TP/FP/FN. Updates/clarifies/supersedes giữ directed metrics riêng; không trộn ordered/unordered denominator.
- NONE được định nghĩa theo view/universe; negatives phải adjudicate, không suy từ thiếu triple. Assertion sai không được reasoner hợp thức hóa; tính đúng suy luận khác tính đúng graph nghiệp vụ cuối.
- Đã sửa EVENT_SCHEMA, ANNOTATION_GUIDELINE, EVALUATION_PROTOCOL và DOCX P13/P111/P124, T7R19C4/T27R5C2. Không sửa TTL/SHACL/diagram/formulas/images.
- `python review_phase1/test_contradicts_contract.py`: 8 synthetic regression tests PASS với ontology hiện tại. Có positive/counterexample cho reverse, dedup, direction/orientation, wrong input/final, no transitivity/self, cutoff và universe/tie convention.
- **Trạng thái:** FIXED về đặc tả/đồng bộ và focused synthetic contract regression. Chưa có Phase 2 extraction/metric service, adjudicated factual gold hoặc RQ performance; không claim runtime đã chạy.

### D04 — FIXED: returnValue mandatory derived/cache

- `SCORING_SPEC.md` L61 hiện ghi `returnValue is required in the baseline as a derived/cache field`, thống nhất EVENT_SCHEMA L75 và SHACL minCount=1.
- adjustedClose vẫn authoritative; tolerance và công thức không đổi.
- Verified SCORING_SPEC chỉ thay đúng câu được duyệt; không nới SHACL/thêm property.
- **Trạng thái:** FIXED wording.

### D05 — FIXED: ablation áp dụng candidateScore

- T29R5 hiện: “Chỉ phân tích hậu nghiệm sau window. Ranking và ba component ablations áp dụng candidateScore tại cutoff, giữ sourceConfidence = 0,5.”
- ReactionWeight không được mô tả như inference ranking/ablation target. P126, source=0.5 và ba variant đã duyệt giữ nguyên.
- Verified chỉ ô cuối T29R5 đổi trong bảng này.
- **Trạng thái:** FIXED wording/placement, không thay công thức.

### E02 — Hai gap Reaction enforcement đã tái hiện, cần xác định nơi kiểm tra

- Đã chạy `review_phase1/review_evidence/focused_reaction_diagnostic.py` với đúng EventStockReactionShape và các blank-node constraints của shape, trong bộ nhớ. Không sửa input; chỉ isolated shape, không full shapes graph/canonical fixture suite.
- Positive control CAR=0, impactScore=0, direction=NEUTRAL conform=True.
- Mutation CAR=0, direction=POSITIVE vẫn conform=True: shape chỉ enum direction, signedWeight constraint không kiểm tra direction field.
- Mutation CAR=0, impactScore=0.9, reactionWeight=0.45 khi confidence=0.5 và strength=1 vẫn conform=True: downstream multiplication được kiểm tra nhưng chưa kiểm tra impactScore=min(1,abs(CAR)/tau).
- **Ý nghĩa:** spec công thức không mâu thuẫn; không được claim SHACL hiện bắt mọi scoring violation.
- **Cần quyết định:** thêm hai SHACL constraints baseline nhỏ, hoặc quy định rõ reaction-validator Phase 2 bắt buộc enforce các luật này, có valid/invalid regression test. Không tự mở rộng ontology/lớp mới.
- NewsSource.reliabilityScore chỉ được range-check [0,1], không shape-fixed=0.5; registry baseline=0.5 cần ingestion/config check. Candidate sourceConfidence=0.5 đã được shape enforce. Đây là enforcement boundary, không phải thiếu Candidate component.
- **Trạng thái:** OPEN enforcement ownership/evidence; focused diagnostics đã có, full behavioral suite vẫn chưa có.

## C. Kết quả kiểm tra thực tế trong vòng review này

| Kiểm tra | Kết quả | Không chứng minh |
|---|---|---|
| Ontology Turtle | Parse PASS, 455 triples, 22 classes, 44 object / 85 datatype properties | Ontology hoàn toàn đúng hoặc runtime hoạt động |
| SHACL Turtle | Parse PASS, 1064 triples | Behavioral conformance trên valid/invalid fixture |
| SHACL SELECT syntax | 38 SELECT constraints parse PASS, 0 syntax failure | Constraint bắt mọi business violation hoặc calendar coverage |
| DOCX queries literal order | **10/10 syntax PASS**, Q4 đúng thứ tự literal hiện hành | Các query được execute và sinh đúng số dòng |
| Dictionary | 14 entries; required field/key-role/confusable checks PASS | Chất lượng extraction hoặc direction calibration |
| Schema–diagram audit | 336 PASS, 0 FAIL, 57 NOT CHECKED, exit 0 | DOCX đồng bộ hoặc narrative/visual equivalence |
| Audit integration/mutation tests | 7/7 PASS | Bộ SHACL fixture tests hoặc toàn bộ repository suite |
| Embedded demo images | Đọc cả 9 ảnh đang được nhúng; dates/provenance liên quan daily rule phù hợp; synthetic/source captions tồn tại | CSV/fixture tái lập được, full raw values đầy đủ, layout toàn báo cáo đã render |
| DOCX stale-table scan | Hai ô T30R2/T30R10 đã sửa; old sentences absent | Chỉ keyword presence đủ kết luận fixed |
| D03 contract regressions | 8/8 synthetic PASS: symmetry/provenance, dedup/reverse-negative, orientation, wrong input, non-transitivity/directedness, cutoff, tie convention, universe checks | NLP/reasoner service/metric runner trên dữ liệu thật hoặc full-bundle SHACL đã verify |
| Isolated Reaction-shape diagnostic | Positive control conform; wrong direction và wrong impactScore cũng conform (E02) | Full shapes bundle hoặc canonical valid/invalid fixture suite đã pass |
| DOCX ablation-table scan | T29R5 ghi ranking/ba ablations áp dụng candidateScore tại cutoff (D05 fixed) | Toàn protocol đang ranking bằng reactionWeight |
| Edit scope vs D03 backup | Lượt D03 chỉ đổi EVENT_SCHEMA, ANNOTATION_GUIDELINE, EVALUATION_PROTOCOL và DOCX. TTL/SHACL/Draw.io/dictionary/SCORING/tools giữ hash; DOCX chỉ đổi word/document.xml và 5 vị trí được xác định | Visual layout hoặc E02 đã đóng |

Evidence nằm ở `review_phase1/review_evidence/`, ngoài gói gửi. `feedback_rereview_checks.json` và `submission_hashes_before_rereview.json` là snapshot TRƯỚC sửa, không dùng như kết quả hiện tại. `approved_document_fixes_checks.json` là snapshot sau D01/D02/D04/D05, trước D03. `D03_contract_checks.json` là evidence sau D03. Ảnh trích không phải output query mới.

### Cách đọc 57 NOT CHECKED

- 30 assertion ownership: shared property không có domain riêng. Không tự thêm domain để ép audit PASS.
- 19 assertion datatype: appendix không ghi datatype để so sánh trực tiếp.
- 5 assertion sourceReference: chỉ name coverage do thiếu structured entry tương ứng.
- Các mục còn lại là giới hạn tổng quát của semantic/visual/behavioral checks.
- Đây không phải 57 defect, 57 góp ý hoặc coverage percentage.

## D. Các gap evidence và việc xem trước khi gửi

### Nên làm trước khi gửi

- [x] D01: sửa trực tiếp hai ô T30R2/T30R10; verified old sentences absent.
- [x] D02: sắp xếp lại Query 4; 10/10 query syntax PASS.
- [x] D03: giữ đối xứng; đồng bộ schema/guideline/protocol/report; kiểm tra asserted và OWL/final, final unordered projection; 8 regression synthetic PASS.
- [x] D04: wording returnValue mandatory derived/cache, chỉ một câu SCORING_SPEC.
- [x] D05: T29R5 quy ranking/ba ablations về candidateScore tại cutoff.
- [ ] E02: chốt nơi enforce impactScore và marketReactionDirection; không claim full scoring SHACL validation.
- [ ] Render/mở Word và Draw.io: font, bảng vỡ trang, chữ cắt, connectors, cỡ chữ. Chưa full visual verification; việc đã đọc pixels của các ảnh demo không đóng mục layout.
- [ ] Narrative/shared properties ngoài structured appendix: chỉ đóng sau review thủ công đủ phạm vi, không dùng audit 0 FAIL thay thế.
- [ ] Nếu gửi PDF: export từ DOCX đã sửa và kiểm tra PDF đó; không có PDF hiện hành để kết luận ở vòng này.

### Quyết định trình bày, không phải lỗi schema đã xác nhận

- Demo hiện có hình/query synthetic với caption source/CSV không đi kèm/chưa tái lập (P153/P164/P175/P190/P205/P214/P264/P275/P289; Query 7 P255).
- Có thể giữ để minh họa hoặc rút gọn/chuyển phụ lục. Không tự xóa chúng; chờ quyết định người dùng.
- Các ảnh selected-field có cách trình bày rút gọn; chúng không thay thế raw query bindings hoặc component breakdown. Không suy từ ảnh confidence=0.80 rằng sourceConfidence khác 0.5 khi ảnh không hiển thị các component.

### Behavioral SHACL evidence còn mở

E02 đã có focused synthetic diagnostic cho isolated Reaction shape. Các dòng dưới đây nói về canonical/full valid–invalid suite chưa có; không phủ nhận các diagnostic đã chạy. Gap enforcement E02 khác với contradiction formula/spec.

| ID cũ | Phạm vi chưa chạy | Cách kiểm chứng nếu chọn bổ sung |
|---|---|---|
| F03-VAL | Mean/confidence range/fixed source | Valid graph + mutation ngoài range/source!=0.5/wrong mean; kiểm tra specific violation |
| F04-VAL | Candidate/reaction scores và post-window constraints | Mutation wrong score/missing component/early Reaction; ranker leakage kiểm tra riêng ở Phase 2 |
| F05-VAL | Ownership/date pairing/return/AR/CAR | Mutation missing predecessor/swap Stock hoặc benchmark/duplicate date/wrong cache/CAR; lịch exact session cần validator riêng |
| F07a-VAL | Raw vs curated lifecycle | Raw Article không Event hợp lệ staging; inference gate không phát sinh Candidate khi chưa đủ Event |
| F08b-VAL | Variant isolation | Schema metadata có thể kiểm tra; overwrite baseline/mixed ranking là behavior runner Phase 2 |

Không còn claim behavioral 9/9, 7/7 cần bảo vệ. Bổ sung tests tăng độ tin cậy, nhưng không đòi dựng lại demo cũ để hợp thức hóa con số lịch sử.

## E. Chưa đóng ở Phase 2 — không dùng để chặn đặc tả Phase 1

- Calendar/provider/adjusted-price conventions thật; input/output snapshots và immutable status history.
- Crawler/extraction/linking/canonicalization và curated gate chạy end-to-end 100–300 articles.
- Gold/adjudication/agreement, sealed chronological splits/support floor, actual metric runner.
- RQ1–RQ3, three component ablations, measured exposure variant và window robustness.
- Reproducible AR/CAR/Reaction với đầy đủ close series/calendar và run manifests.

## Quy ước trạng thái

- `Fixed ở mức đặc tả` không có nghĩa implemented/tested.
- `Partially fixed` khi contract đã đúng nhưng artifact dẫn xuất còn contradiction.
- `OPEN defect` cho lỗi tái hiện được như D01/D02; D03 là semantic/protocol gap đã được chốt, đồng bộ và test synthetic, D04 là wording inconsistency. Không đánh đồng bốn mức này.
- `NOT CHECKED` cho evidence chưa có, không tự coi PASS hoặc FAIL.
- Thầy ưu tiên các mục 1,2,3,4,5,9 trước Phase 2 (nguồn L160–169). D01–D05 đã đóng trong scope được duyệt. E02 và visual/full behavioral review còn mở; runtime Phase 2 chưa verify.
