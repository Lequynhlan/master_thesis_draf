# Feedback matrix — review lại từng góp ý của thầy sau khi bổ sung audit

## Phạm vi và cách đọc

- Nguồn yêu cầu: `ban_thay_gop_y/gop_y_phase1_truoc_code_phase2.txt`, đúng 9 mục được đánh số trong file.
- Artifact review: chỉ `chỉnh sửa mới nhất - 01-10/`. Không lấy sibling folder, demo cũ hoặc backup làm bằng chứng bộ hiện hành đã chạy.
- TTL/SHACL là source of truth. Audit phụ lục không chứng minh toàn bộ DOCX/Draw.io tương đương về ngữ nghĩa.
- Matrix này nằm ngoài gói gửi thầy. Lượt review chỉ cập nhật tài liệu nội bộ và trích ảnh phục vụ review; không sửa artifact gửi.
- `P…` là paragraph và `T…R…` là table/row, đánh số 1-based bằng python-docx; không phải số trang.
- Phân biệt: **đặc tả/schema**, **đồng bộ artifact**, **machine-check**, **behavioral validation**, **visual verification**, **runtime Phase 2**.
- Trạng thái vòng review này thay thế kết luận quá rộng của vòng trước: không thể nói toàn bộ gói đã đồng bộ khi DOCX còn stale table hoặc query không parse.

## Kết luận hiện tại

1. Luồng đặc tả chính vẫn nhất quán: Article/Evidence → canonical Event → Candidate tại cutoff → market window → Reaction hậu nghiệm. Chưa phát hiện nhu cầu mở rộng ontology từ các kiểm tra trong vòng này.
2. Không kết luận toàn bộ 9 góp ý đã đóng ở mọi artifact: góp ý 1 và 9 còn hai ô DOCX mô tả sai trạng thái Draw.io; Query 4 trong DOCX bị đảo thứ tự dòng và không parse.
3. Góp ý 2–8 phần lớn có contract Phase 1, nhưng mục 6/8 còn gap semantics/protocol về hướng của `contradicts` (D03), và mục 5 có câu chữ optional/mandatory returnValue cần thống nhất (D04). Việc thiếu provider/calendar thật, snapshot runner, gold set hoặc kết quả RQ không tự biến thành lỗi đặc tả Phase 1.
4. Có **năm nhóm việc tài liệu/contract cần xử lý**: D01 (hai ô stale), D02 (Query 4), D03 (graph/inference semantics của contradicts), D04 (wording returnValue), D05 (bảng đặt ablation dưới reactionWeight). D01/D02 là lỗi artifact xác nhận; D03 là gap protocol đã tái hiện; D04/D05 là wording lệch/gây hiểu sai. Ngoài ra E02 ghi hai gap Reaction enforcement đã tái hiện, không mặc định buộc thay schema. Chưa sửa artifact gửi trong lượt review này.
5. Gap visual và behavioral SHACL vẫn mở. Không dùng parse/audit assertion count để đóng các gap đó.

## A. Ma trận theo đúng 9 góp ý

| Mục / dòng nguồn | Yêu cầu thầy | Bằng chứng bộ hiện tại | Machine-check / giới hạn | Kết luận và việc còn lại |
|---|---|---|---|---|
| **1 — L7–24** | Cùng WFKG/namespace; đúng bốn route baseline; không suy ngược parent→child hoặc lan tới mọi Stock cùng ngành; TTL/SHACL chuẩn | `EVENT_SCHEMA.md` L5–7, L30–39. DOCX P20/P28/P319; Draw.io tab 01 cell `mZ28CVNe_N0uJWWchiWa-46` ghi INDUSTRY chỉ Bank có exposure hợp lệ, SUBSIDIARY chỉ child→parent. Tab 05 cell `weTA0hvWxfCujyoZNfAk-11` ghi `relationPath=impactType` | TTL/SHACL parse; route/code constraints đọc tại shapes L148–317; audit appendix PASS trong phạm vi hỗ trợ. Không có PDF hiện hành trong package để review | **Schema/route đã sửa; đồng bộ toàn bộ báo cáo còn partially fixed** vì T30R2 vẫn nói tab 05 có câu trái ngược, dù label đã đúng. Xem D01. Nếu xuất PDF, xuất từ DOCX sau khi sửa, không tái dùng PDF cũ |
| **2 — L26–36** | Daily: trước mở cửa dùng phiên đó; từ khi mở cửa trở đi dùng phiên tiếp theo | `EVENT_SCHEMA.md` L80–88: strict-open, timezone, calendar coverage, proxy availability; DOCX P131–132/P168/P194. Các ảnh Q1/Q3/Q5 ghi t0=2026-08-27; Q8 Reaction available 27/08 | Đã đọc các ảnh nhúng hiện hành và text, không chỉ correction note. Không execute calendar/provider thật hoặc fixture query demo | **Fixed ở mức đặc tả và ngày hiển thị trong ảnh liên quan**. Exact-open cũng đã chốt. Runtime calendar là Phase 2; render layout vẫn NOT CHECKED |
| **3 — L38–56** | Lưu bốn component; rule source nhiều Evidence, entity linking, DIRECT; freeze tại cutoff | `SCORING_SPEC.md` L14–47; `EVENT_SCHEMA.md` L60–69. DOCX T20R17–R19/P121/P126. Shapes L194–198 (required/range), L235–242 (mean), L262–268 (source fixed). Có linkingConfidence trong TTL/appendix | Property/schema checks và SHACL SELECT syntax có bằng chứng. Không kiểm thử behavior confidence, calibration hoặc immutable snapshot | **Fixed ở mức contract**. Source=0.5 là control, không dùng maximum source quality; linker minimum, DIRECT minimum links, fallback có provenance. Ba component ablations giữ source=0.5; không làm source ablation trong baseline |
| **4 — L58–74** | candidateScore dùng inference; reactionWeight chỉ sau window; không leakage | `SCORING_SPEC.md` L24–31/L49–76; `EVENT_SCHEMA.md` L41–48; `EVALUATION_PROTOCOL.md` L56–64/L72–80; DOCX P121/P126, T20/T21 | Formulas và ownership có ở schema/SHACL; chưa chạy ranker chống leakage. **Query 4 hỗ trợ minh họa cutoff không parse theo thứ tự đang có trong DOCX** | **Scoring/anti-leakage spec chính fixed; còn D02/D05 ở DOCX**. Hai gap Reaction enforcement được tái hiện trong E02. Không nhầm lỗi trình bày query hoặc bảng với bằng chứng pipeline đã leak |
| **5 — L76–90** | Stock/index adjustedClose đủ t−1 và t, toàn bộ window; AR/CAR tính lại được | `EVENT_SCHEMA.md` L50–58/L75–76/L88; `SCORING_SPEC.md` L51–65. Shapes MarketIndexObservation L854–879, MarketObservation L898–927; Reaction có ownership/date/arithmetic constraints. DOCX T17/T19/T21 và P279–289 | Đã đọc image11: mỗi Reaction có Stock và benchmark 26/08 và 27/08, adjustedClose được hiển thị. Đây là ảnh fixture lịch sử, không phải thực thi mới; không có CSV/graph để xác nhận đầy đủ URI/provenance. Calendar-aware exact sessions vẫn ngoài SHACL | **Provenance contract đã fixed; wording còn D04**: SCORING_SPEC L61 dùng “may be stored as a cache”, nhưng EVENT_SCHEMA L75/SHACL bắt buộc returnValue. Behavioral recomputation/date coverage của toàn gói NOT CHECKED; dữ liệu/provider thật thuộc Phase 2 |
| **6 — L92–108** | Dictionary machine-readable 10–15 types: roles, canonical key, direction, examples/confusables | `EVENT_DICTIONARY.yaml` version 1.0.2, 14 entries; identity_policy/direction_policy L4–24. `EVENT_SCHEMA.md` L97–103 và `ANNOTATION_GUIDELINE.md` L29–36 cùng quy tắc identity | YAML parse PASS; cả 14 entries có field yêu cầu, canonical-key fields có trong roles, confusables tham chiếu declared type hoặc declared out-of-scope. Không chạy NLP/extraction hoặc đánh giá chất lượng gán nhãn thực tế | **Dictionary/identity fixed ở mức machine-readable**. Missing optional key có HOLD/MATCH policy; article dates không tạo identity; updates/clarifies không union duplicate clusters. Semantics của related Event label `contradicts` còn D03, không phải lỗi thiếu dictionary |
| **7 — L110–118** | reports staging; exposure reporting period/latest available/staleness; exposureStrength variant | `EVENT_SCHEMA.md` L17–28/L77–78/L90–95; `SCORING_SPEC.md` L39/L85. DOCX T5R8/P100/P102/P322–324. Shapes reports L930–956 không bắt minCount; exposure L723–779 có period/strength contract | Audit đối chiếu reports [0..*]. YEAR/latest periodEnd/availableAt/URI/staleness đọc trong spec; curated gate/selection chưa execute | **Ba phần đã fixed ở mức đặc tả**. Không fabricate exposure để dùng baseline 0.5; variant đo trên cùng eligible cohort. Query 7 parse nhưng kết quả fixture chưa tái lập (P255 ghi rõ) |
| **8 — L120–137** | Tách vertical slice/final; annotation Evidence/type/link/identity/relevance/direction; double label; theo impactType và macro Event | `EVALUATION_PROTOCOL.md` L5–12/L23–25/L41–84; `ANNOTATION_GUIDELINE.md` L5–51. 25% double-label; resolved 0/1/2, UNKNOWN direction tách uncertainty; paired Event bootstrap và frozen metric edge cases | Review nội dung contract; không chạy metric runner, split/gold/adjudication hoặc RQ. Audit schema không kiểm chứng các bước này | **Protocol chính đã chốt nhưng overall partially fixed**: D03 chưa phân biệt directed asserted-pair label với symmetric entailed relation; D05 còn một dòng bảng đặt comparison/ablation dưới reactionWeight. Support floor và CI không hứa đủ power. Final data/actual evaluation là Phase 2 |
| **9 — L139–154** | Appendix property đúng TTL/SHACL; tool generation hoặc audit tự động | Có `tools/audit_schema_diagram.py`, `tools/README.md`; portable/read-only. Property endpoint/cardinality structured appendix được đối chiếu; shared/unstructured thiếu thông tin báo NOT CHECKED | Fresh audit 336 PASS / 0 FAIL / 57 NOT CHECKED; 7 tests công cụ pass trên canonical/copies mutation. Audit không đọc DOCX, không inspect mọi narrative tab hoặc render | **Cơ chế và appendix audit đã fixed trong scope; report integration còn partially fixed** vì T30R10 vẫn nói Draw.io chưa sửa/còn mâu thuẫn. Xem D01; 0 FAIL không đóng toàn bộ mục 1/9 |

## B. Các lỗi/gap mới xác nhận — đề nghị xử lý tối thiểu, chờ duyệt

### D01 / E01-reopened — Hai ô DOCX vẫn báo sai trạng thái Draw.io

- **T30R2, ô evidence** còn câu: “Draw.io hiện vẫn có câu trái ngược ở tab 05-4; file sơ đồ cần được sửa riêng.”
- **T30R10, ô evidence** còn câu: “Draw.io chưa được sửa trong lượt này và vẫn còn câu mâu thuẫn về relationPath.”
- Đối chiếu XML tab 05 cell `weTA0hvWxfCujyoZNfAk-11`: hiện đã nói relationPath phải bằng impactType, Candidate ranking dùng candidateScore, Reaction chỉ sau window.
- Đây là contradiction về trạng thái artifact, không phải ontology/diagram defect. Các đoạn P20/P116/P143/P306/P309 đã đúng; việc sửa các đoạn đó trước đây không đồng nghĩa đã sửa cả bảng.
- **Sửa đề xuất:** sửa trực tiếp hai ô thành mô tả trạng thái hiện tại + audit scope/limits, không thêm correction note hoặc sửa Draw.io thêm cho khớp lời báo cáo cũ.
- **Machine-check sau sửa:** exact old sentences absent ở paragraphs và tables; hai ô mới đúng XML; audit và DOCX ZIP/XML pass; chỉ `word/document.xml` được phép đổi.
- **Trạng thái:** OPEN, chưa sửa. Thu hồi kết luận E01 đóng toàn bộ của vòng trước.

### D02 — Query 4 trong DOCX có thứ tự dòng đảo ngược

- **Vị trí:** P181–P189, dưới heading P178 “Query 4 – Thông tin khả dụng tại cutoff”.
- P181 bắt đầu `} ORDER BY ...`; P187 mới có `SELECT ... WHERE {`; PREFIX ở P188–P189.
- RDFLib parse nguyên thứ tự hiện hành: FAIL, `found '}' at char 0`.
- Diagnostic đảo thứ tự trên bản sao trong bộ nhớ: syntax PASS. Không lưu query sửa hoặc sửa DOCX.
- Query đã đảo trong backup trước lượt đồng bộ báo cáo, nên lỗi không do lượt review này tạo ra.
- **Sửa đề xuất:** sắp xếp lại đúng PREFIX → SELECT → VALUES → patterns → FILTER → closing brace/ORDER BY; giữ nội dung filter cutoff, không tự dựng dataset/CSV hoặc thay con số minh họa.
- **Machine-check sau sửa:** trích nguyên query hiện hành từ DOCX theo đúng thứ tự và parse; cả 10 query đều phải parse. Đây là syntax acceptance, không phải executed-result/anti-leakage behavior.
- **Trạng thái:** OPEN, chưa sửa.

### D03 — `contradicts`: OWL đối xứng, protocol chấm ordered/directed pairs chưa định rõ graph semantics

- TTL L88–92 khai báo `wfkg:contradicts` là `owl:SymmetricProperty`.
- `EVENT_SCHEMA.md` L103 mô tả các relation đi mới→cũ; `ANNOTATION_GUIDELINE.md` L16/L36 gom contradicts vào directed relation; `EVALUATION_PROTOCOL.md` L35 chấm trên ordered Event-pair universe với NONE exclusive.
- Diagnostic synthetic, không ghi vào input: assert `new contradicts old`; trước closure không có reverse, sau OWL-RL có `old contradicts new`.
- Vấn đề: nếu gold chấm chỉ chiều mới→cũ nhưng predicted triples lấy từ inferred graph, chiều ngược có thể thành false positive/NONE mismatch. Việc symmetric logical relation và directed storage convention cùng tồn tại không nhất thiết là ontology sai; **contract chưa nói rõ assertion graph/projection/inference regime** để hai phía được chấm giống nhau.
- **Phương án đề xuất ưu tiên:** giữ TTL source truth và nêu rõ annotation assertion direction khác logical symmetry; chọn explicit evaluation projection/asserted graph, hoặc chấm contradicts trên unordered pairs/hai chiều cùng positive. Các relation updates/clarifies/supersedes vẫn directed. Đồng bộ guideline/protocol/schema/report theo lựa chọn.
- Nếu muốn contradicts thật sự chỉ một chiều trong mô hình, cần duyệt thay ontology/SHACL/documentation và bỏ SymmetricProperty; không tự làm ở lượt này.
- **Machine-check sau sửa:** một cặp contradictory Events phải có gold/predicted projection nhất quán trong declared inference regime; không đồng thời labeled contradicts và NONE. Test metric universe/negatives cho reverse pair.
- **Trạng thái:** OPEN semantic/protocol gap, nên chốt trước khi code/evaluation; không phải yêu cầu mở rộng lớp ontology.

### D04 — Wording returnValue optional/mandatory chưa thống nhất

- `SCORING_SPEC.md` L61: “returnValue may be stored as a cache”. Có thể được hiểu là optional.
- `EVENT_SCHEMA.md` L75: returnValue mandatory; MarketObservation/MarketIndexObservation shapes L854–927 có minCount=1.
- Dữ liệu authoritative vẫn là adjustedClose, nên không phát hiện mất provenance từ việc này.
- **Sửa tối thiểu đề xuất:** ghi rõ returnValue bắt buộc trong baseline với vai trò derived/cache, không optional và không authoritative; không nới SHACL hay thêm property.
- **Trạng thái:** OPEN wording inconsistency nhẹ; nên sửa cùng lượt đồng bộ báo cáo/spec.

### D05 — Bảng DOCX đặt mô tả ablation dưới reactionWeight

- **Vị trí:** T29R5: `reactionWeight` | `Chốt công thức heuristic` | `So sánh với baseline không trọng số và ba component ablations: extraction, linking, relation; giữ sourceConfidence = 0,5`.
- Phần prose P126 và SCORING_SPEC/EVALUATION_PROTOCOL đã quy định comparison/ablation ranking trên candidateScore tại cutoff, reactionWeight chỉ hậu nghiệm.
- Dòng bảng này vẫn gây hiểu sai đối tượng ablation; không phải bằng chứng toàn protocol dùng market reaction để ranking.
- **Sửa tối thiểu đề xuất:** đặt mô tả ranking/ablation vào dòng candidateScore hoặc ghi tường minh nó áp dụng candidateScore; dòng reactionWeight chỉ mô tả post-window analysis. Giữ nguyên source=0.5 và ba variants đã duyệt.
- **Trạng thái:** OPEN wording/placement inconsistency; không thay công thức.

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
| DOCX queries literal order | Q1–Q3 và Q5–Q10 syntax PASS; **Q4 FAIL** | Các query được execute và sinh đúng số dòng |
| Dictionary | 14 entries; required field/key-role/confusable checks PASS | Chất lượng extraction hoặc direction calibration |
| Schema–diagram audit | 336 PASS, 0 FAIL, 57 NOT CHECKED, exit 0 | DOCX đồng bộ hoặc narrative/visual equivalence |
| Audit integration/mutation tests | 7/7 PASS | Bộ SHACL fixture tests hoặc toàn bộ repository suite |
| Embedded demo images | Đọc cả 9 ảnh đang được nhúng; dates/provenance liên quan daily rule phù hợp; synthetic/source captions tồn tại | CSV/fixture tái lập được, full raw values đầy đủ, layout toàn báo cáo đã render |
| DOCX stale-table scan | **Hai ô stale được xác nhận** | Chỉ keyword presence đủ kết luận fixed |
| OWL symmetry diagnostic | Synthetic new→old contradicts sinh old→new sau OWL-RL | Metric projection/gold inference regime đã được chốt |
| Isolated Reaction-shape diagnostic | Positive control conform; wrong direction và wrong impactScore cũng conform (E02) | Full shapes bundle hoặc canonical valid/invalid fixture suite đã pass |
| DOCX ablation-table scan | T29R5 vẫn đặt comparison dưới reactionWeight (D05) | Toàn protocol đang ranking bằng reactionWeight |
| Input read-only | 11 file package (9 artifact chính + script/README) giữ nguyên SHA-256 so với manifest trước review | Không đồng nghĩa đã sửa các lỗi tìm thấy |

Evidence trích ảnh và hash manifest nằm ở `review_phase1/review_evidence/`, không đưa vào gói gửi thầy. Các ảnh trích là bản sao từ DOCX, không phải output query mới.

### Cách đọc 57 NOT CHECKED

- 30 assertion ownership: shared property không có domain riêng. Không tự thêm domain để ép audit PASS.
- 19 assertion datatype: appendix không ghi datatype để so sánh trực tiếp.
- 5 assertion sourceReference: chỉ name coverage do thiếu structured entry tương ứng.
- Các mục còn lại là giới hạn tổng quát của semantic/visual/behavioral checks.
- Đây không phải 57 defect, 57 góp ý hoặc coverage percentage.

## D. Các gap evidence và việc xem trước khi gửi

### Nên làm trước khi gửi

- [ ] D01: sửa hai ô T30R2/T30R10 (chờ duyệt).
- [ ] D02: sắp xếp lại Query 4 và parse đủ 10 query (chờ duyệt).
- [ ] D03: duyệt graph/projection semantics cho contradicts rồi đồng bộ schema/guideline/protocol/report.
- [ ] D04: đổi wording returnValue thành mandatory derived/cache theo schema/SHACL.
- [ ] D05: sửa mô tả ablation/ranking ở T29R5 cho đúng candidateScore.
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
- `OPEN defect` cho lỗi tái hiện được như D01/D02; D03 là semantic/protocol gap đã có diagnostic, D04 là wording inconsistency. Không đánh đồng bốn mức này.
- `NOT CHECKED` cho evidence chưa có, không tự coi PASS hoặc FAIL.
- Thầy ưu tiên các mục 1,2,3,4,5,9 trước Phase 2 (nguồn L160–169). Vì D01–D05 và lựa chọn enforcement E02 còn mở, chưa kết luận gói hoàn toàn sẵn sàng chốt/gửi lại.
