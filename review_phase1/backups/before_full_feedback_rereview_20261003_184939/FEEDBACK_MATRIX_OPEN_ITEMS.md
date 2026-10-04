# Feedback matrix — các mục chưa đóng hoàn chỉnh

## Phạm vi và cách hiểu trạng thái

- Bộ artifact được đánh giá: `D:\project\master_thesis\01-10-2026\chỉnh sửa mới nhất - 01-10`.
- Nguồn yêu cầu: `ban_thay_gop_y/gop_y_phase1_truoc_code_phase2.txt`.
- Tài liệu này nằm ngoài folder gửi thầy; không phải một artifact đặc tả thay thế TTL/SHACL.
- Trạng thái đã được đối chiếu lại sau khi tạo `tools/audit_schema_diagram.py` và `tools/README.md`. Fresh audit trên bộ hiện tại trả 336 PASS, 0 FAIL, 57 NOT CHECKED, exit code 0; đây là số assertion, không phải số góp ý đã đóng.
- Phạm vi ablation đã sửa: sourceConfidence = 0.5; chỉ neutralize extractionConfidence/linkingConfidence/relationConfidence.
- Đã đồng bộ DOCX sau khi thêm audit theo phê duyệt người dùng: sửa P20/P116/P143/P306/P309 và evidence cells T30R4–R9. TTL/SHACL/Draw.io không thay đổi. Backup nằm ngoài gói tại `review_phase1/backups/before_audit_report_sync_20261003_182228/`.

## Ưu tiên công việc tiếp theo — trạng thái sau lần đối chiếu mới nhất

Fresh audit vẫn trả 336 PASS, 0 FAIL, 57 NOT CHECKED; 7 test công cụ pass. DOCX ZIP/XML hợp lệ; scan toàn bộ paragraphs/tables không thấy các wording stale hoặc reliance vào file audit ngoài gói đã xác định. Các file chính không đổi hash trong lượt kiểm tra này. Đây là kiểm tra có phạm vi, không phải review semantic/visual toàn bộ báo cáo.

| Ưu tiên | Việc cần xem xét | Có phải lỗi cần sửa ngay? | Cách xử lý/điều kiện đóng |
|---|---|---|---|
| 1 — trước gửi | Mở Word/Draw.io kiểm tra chữ bị cắt, bảng vỡ trang, cỡ chữ và connectors; nhất là những đoạn Word vừa dài hơn sau sửa | Chưa có bằng chứng lỗi layout, nhưng chưa visual-verify | Inspect bản hiển thị/render; chỉ sửa vị trí thực sự có lỗi sau khi duyệt. XML pass không thay thế bước này. |
| 1 — review thủ công | Kiểm tra lại wording route và shared properties ở các tab ngoài appendix; audit không bao phủ các câu diễn giải hoặc connector semantics | Không có FAIL mới trong phạm vi audit; phần ngoài phạm vi chưa được tái review toàn diện trong lượt này | Đối chiếu 4 route, relationPath = impactType, Candidate/Reaction separation và ownership của shared fields. Không thay contract chỉ để làm NOT CHECKED về 0. |
| 2 — quyết định trình bày | Giữ hay rút gọn hình/demo synthetic lịch sử không có CSV/fixture trong gói | Không phải contradiction mới: đã có nhãn lịch sử/chưa tái lập | Có thể giữ để minh họa thiết kế; hoặc chuyển phụ lục/rút gọn để báo cáo gọn hơn. Không phải dựng demo runner mới để chốt Phase 1. Chỉ bắt buộc tái lập nếu muốn dùng làm bằng chứng kiểm thử định lượng. |
| 3 — kiểm chứng bổ sung | Behavioral SHACL valid/invalid fixtures | Thiếu behavioral evidence, không phải lỗi tài liệu đã xác nhận | Làm nếu cần tăng độ tin cậy của constraints; nếu phát hiện lỗi thật mới mở mục sửa. Không claim behavioral conformance khi chỉ parse query. |
| Phase 2 | Calendar/provider thật, immutable snapshots, NLP, dataset/metric/ablation runner và RQ1–RQ3 | Không phải blocker đặc tả Phase 1 | Giữ các rule đã khóa; thực hiện và kiểm chứng khi triển khai. |

**Không còn việc phải sửa đã xác định trong hai mục vừa xử lý F09/E01 hoặc xung đột ablation F08b.** Điều này chỉ nói các gap cụ thể đã đóng, không khẳng định toàn bộ luận văn đã được chứng minh đúng hoặc toàn bộ diagram đã visual/semantic-verified.

### 57 NOT CHECKED nên được hiểu thế nào?

- 30 assertion ownership không có explicit/inherited OWL domain: shared fields không được tự gán domain để ép audit PASS.
- 19 assertion datatype range không được in trong label: tool không có giá trị Draw.io để so sánh xsd datatype.
- 5 properties chỉ có shared/narrative mention: dataQualityFlag, involves, sourceReference, validFrom, validTo chưa có structured entry được đối chiếu endpoint.
- Các mục còn lại là giới hạn tổng quát về logical/SPARQL constraints, tab ngoài appendix, layout và runtime.
- Đây là số assertion chưa kiểm tra, không phải 57 defect và không phải 57 feedback unresolved. Có thể review thủ công các phần quan trọng mà không mở rộng script.

### Minh họa lịch sử cần quyết định trình bày

DOCX P153/P164/P175/P190/P205/P214/P264/P275/P289 vẫn ghi CSV nguồn không có trong gói và chưa xác minh lại. P143 phân biệt competency queries/demo với audit; P13 nêu synthetic không phải kết quả RQ. Hiện chưa đề xuất xóa các hình/query hoặc đổi số dòng: đó là quyết định trình bày cần người dùng duyệt. Các hình/query không được dùng để chứng minh pipeline đã chạy end-to-end.

## Quy ước đọc trạng thái

- `partially fixed`: đã xử lý nội dung nhưng còn thiếu một phần yêu cầu hoặc bằng chứng kiểm tra.
- `unresolved`: chưa thực hiện phần kiểm tra/công việc tương ứng; không mặc định là lỗi logic của đặc tả.
- Phân biệt thiếu cơ chế kiểm tra theo yêu cầu reviewer với những việc thuộc Phase 2. Không coi thiếu implementation/dữ liệu thật là lỗi Phase 1.
- Không dùng correction note hoặc token presence để thay thế việc sửa contradiction tại bảng/query/constraint/diagram gốc.

## A. Trạng thái các mục đã xử lý trong lượt đồng bộ

### F09 — Cơ chế đồng bộ/audit property giữa TTL/SHACL và Draw.io

| Trường | Nội dung |
|---|---|
| Feedback ID | F09; liên quan F01 về source of truth |
| Nội dung góp ý | Draw.io lấy thông tin từ TTL hoặc ít nhất có script audit so sánh tự động; tránh duy trì hai property list thủ công. |
| Contract/rule | TTL/SHACL là nguồn chuẩn. Không chỉ khớp tên property mà còn phải kiểm tra vị trí class, endpoint và cardinality trong phạm vi đã đặc tả. |
| DOCX cần có | Tham chiếu đúng cơ chế audit thực sự đi kèm; phân biệt phạm vi kiểm tra, kết quả thực thi và phần chưa kiểm tra. Không mô tả script vắng mặt như công cụ đã chạy trong gói. |
| Draw.io cần có | Giữ appendix đúng TTL/SHACL; sửa trực tiếp label sai nếu audit phát hiện. Không thêm một chú thích đúng để che label/bảng cũ sai. |
| TTL cần có | Không đề xuất thêm class/property. Dùng ontology hiện tại làm đầu vào audit. |
| SHACL cần có | Dùng class-specific constraints/cardinality làm đầu vào audit; không coi OWL domain và SHACL cardinality là cùng một loại ràng buộc. |
| Scoring/evaluation cần có | Không cần đổi; audit hiện tại không kiểm tra scoring/evaluation hoặc phạm vi ablation. Đây là giới hạn đã ghi rõ, không thêm việc ngoài phạm vi user duyệt. |
| Machine-check đã chạy | Fresh run `python tools/audit_schema_diagram.py --json`: 336 PASS, 0 FAIL, 57 NOT CHECKED, exit 0. Đối chiếu appendix inventory, structured property ownership/range và cardinality được in; ID/reference mọi tab; parse 38 SELECT constraints. SHA256 trước/sau không đổi. Bộ test công cụ ngoài gói: 7 tests pass, gồm mutation sai owner/range/cardinality/tên property, malformed cardinality và chạy từ working directory khác. |
| Machine-check còn cần | Không còn thiếu script so sánh trong phạm vi đã duyệt. Shared/narrative properties, datatype ranges không được in, route semantics ở tab khác và layout vẫn cần review thủ công. Không tuyên bố tool đã audit DOCX, scoring, enum/equality route hoặc thực thi SHACL. |
| Trạng thái | **fixed trong phạm vi audit được duyệt và tích hợp DOCX**. Không đồng nghĩa toàn bộ diagram semantics hoặc layout đã verified; các NOT CHECKED vẫn giữ ở mục B. |
| Evidence | `tools/audit_schema_diagram.py`, `tools/README.md`; test `review_phase1/test_audit_schema_diagram.py`. Appendix tab `06-Phụ lục Entity Property`, cells `bRsWfqp-iSm1W4H_WVv9-3` đến `-7`. DOCX P20/P116/P143/P306/P309 đã cập nhật công cụ và phân biệt audit với demo/runtime tests. |
| Điều kiện đóng | Có audit hoặc generation mechanism thực tế, chạy được trên bộ artifact, trả kết quả thật; giới hạn kiểm tra được ghi rõ; DOCX tham chiếu đúng công cụ. |
| Phê duyệt | Người dùng đã duyệt tool chỉ đọc và lượt đồng bộ báo cáo sau khi thêm audit. |

### E01 — Claim/reference verification đã xử lý; demo lịch sử vẫn chưa tái lập

| Trường | Nội dung |
|---|---|
| Feedback ID | E01 — gap về evidence liên quan F01/F05/F09; không phải một góp ý đánh số mới của thầy |
| Nội dung gap trước sửa | DOCX viện dẫn file audit ngoài gói/số synthetic 9/9, 7/7; một số đoạn phủ nhận sự tồn tại tools dù audit đã được thêm. |
| Contract/rule | Claim verification phải truy vết tới input, assertion, công cụ và kết quả. Historical evidence không được trình bày như fresh verification của gói hiện tại. |
| DOCX đã sửa | P20/P116/P143/P306/P309 và T30R4–R9 đã sửa trực tiếp. Đã bỏ reliance vào file đánh giá ngoài gói, số test lịch sử không tái lập và danh sách lệnh script vắng mặt. P309 hướng dẫn lệnh audit thực tế. Các demo/hình synthetic còn lại được giữ có nhãn lịch sử/chưa tái lập. |
| Draw.io cần có | N/A, trừ khi phát hiện claim kiểm thử tương tự trong labels. |
| TTL cần có | N/A. |
| SHACL cần có | Không sửa constraints chỉ để hợp thức hóa claim kiểm thử. |
| Scoring/evaluation cần có | Giữ rule synthetic tests không phải kết quả RQ. |
| Machine-check đã chạy | Scan toàn bộ paragraphs/tables cho wording stale, tên file đánh giá ngoài gói, số 9/9 và 7/7, old tool paths; kiểm tra DOCX ZIP/XML và phạm vi ZIP parts thay đổi. Đối chiếu kết quả P306 với fresh audit; chưa render layout. |
| Trạng thái | **fixed về contradiction/reference/claim đã xác định**. Không tuyên bố đã tái lập demo, behavioral SHACL hoặc end-to-end pipeline. |
| Evidence | P20: công cụ có trong gói, chỉ đọc; P116: phạm vi appendix và NOT CHECKED; P143: demo queries chưa tái lập, audit không chạy query; P306: 336/0/57 và giới hạn; P309: lệnh/cách chạy/exit codes thực tế. T30R4–R9 không còn “File đánh giá ghi nhận kiểm thử tổng hợp”. |
| Điều kiện đóng | Bằng chứng chính của báo cáo chỉ dùng claim có thể kiểm tra, hoặc có nhãn lịch sử rõ ràng và không được dùng để kết luận gói tái lập đầy đủ. |
| Phê duyệt | Người dùng đã duyệt lượt đồng bộ sau khi thêm audit; claim/reference đã được sửa trong phạm vi đề xuất. |

## B. Các gap verification — không đồng nghĩa đặc tả sai

- F01/F09-VIS: nên hoàn tất trước khi gửi.
- F03-VAL/F04-VAL/F05-VAL/F07a-VAL: kiểm chứng bổ sung cho SHACL; hiện chưa được thực thi. Không còn claim 9/9, 7/7 cần bảo vệ trong báo cáo, nên không bắt buộc dựng test suite để hợp thức hóa con số lịch sử.
- F08b-VAL: hành vi runner thuộc Phase 2; xung đột đặc tả đã đóng.
- Các trạng thái “unresolved về evidence/runtime” dưới đây không phải trạng thái reviewer comment chưa sửa ở mức đặc tả.

| Feedback ID | Yêu cầu/rule | Artifact và evidence | Machine-check còn thiếu | Trạng thái | Phân loại và điều kiện đóng |
|---|---|---|---|---|---|
| F01/F09-VIS | Đồng bộ cả nội dung nhìn thấy, không chỉ XML tokens | Draw.io tab 01/05/06; DOCX report và property tables | Render Word/Draw.io, kiểm tra text overflow, chữ nhỏ, đường nối/overlap, bảng vỡ trang; so khớp phần hiển thị với canonical rules | unresolved về visual verification | Kiểm tra chất lượng gói trước gửi; chưa có bằng chứng lỗi layout. Chỉ đóng khi đã inspect bản render. |
| F03-VAL | Required component/range/mean/source = 0.5 phải thực sự được validator từ chối khi sai | shapes_v1.0.ttl dòng 194–198, 235–242, 262–267; SCORING_SPEC.md mục 1 | Fresh behavioral SHACL probes có valid control và invalid mutations: thiếu component, ngoài range, sai mean, source != 0.5 | unresolved về behavioral evidence | Constraints có trong đặc tả; parse/query syntax không chứng minh behavior. Không lấy số test lịch sử làm fresh result. |
| F04-VAL | candidateScore/reactionWeight đúng công thức và ownership | shapes_v1.0.ttl CandidateShape/ReactionShape; SCORING_SPEC.md mục 1–3 | Valid control và mutation sai candidateScore/reactionWeight; ghi inference mode chính xác | unresolved về behavioral evidence | Có thể kiểm tra cấu trúc tổng hợp trước Phase 2; chưa chạy lại trong lượt feedback matrix. |
| F05-VAL | Ownership, date pairing, predecessor/window coverage, adjustedClose, return/AR/CAR | EVENT_SCHEMA.md mục AR/CAR; SCORING_SPEC.md mục 2; shapes_v1.0.ttl ReactionShape | Fresh valid/invalid graphs: thiếu phiên, sai owner, ngày lệch, close thiếu/không dương, sai return/AR/CAR. Tách data-only mode và ontology/RDFS mode nếu áp dụng | unresolved về behavioral evidence | Contract đã có; không khẳng định 9/9 từ gói hiện tại khi chưa có fixture/script để chạy lại. Exact market sessions vẫn cần calendar-aware validator. |
| F07a-VAL | Raw article không có reports vẫn staging-safe | EVENT_SCHEMA.md dòng 19; DOCX T5R8; NewsArticleShape | Validate staging article đủ trường nhưng không có reports; kiểm tra curated gate riêng, không nhập nhằng hai profile | unresolved về behavioral evidence | Không đề xuất đổi raw cardinality. Curated gate implementation thuộc Phase 2. |
| F08b-VAL | Ba component ablations, giữ source = 0.5, variant snapshot riêng | SCORING_SPEC.md mục 5; EVALUATION_PROTOCOL.md mục Baseline component ablation contract; DOCX RQ3 và bảng evaluation | Phase 2 test: một lần chỉ neutralize một component, tính lại score, giữ path/cutoff/strength/gold, không ghi đè baseline và không trộn method versions | unresolved về runtime verification | Xung đột tài liệu đã sửa; test implementation chỉ đóng khi runner tồn tại. Không phải blocker ontology Phase 1. |

## C. Các yêu cầu đã khóa ở mức đặc tả nhưng chờ implementation Phase 2

Các dòng dưới đây không phải yêu cầu sửa ontology hoặc mở rộng scope. Chúng chỉ ngăn kết luận vượt quá bằng chứng hiện tại.

| Feedback ID | Rule | Artifact liên quan | Kiểm tra cần có ở Phase 2 | Trạng thái verification |
|---|---|---|---|---|
| F02 | Daily effectiveTradingDate theo opening instant, timezone và lịch phiên thật | EVENT_SCHEMA.md mục Frozen cutoff and daily calendar contract; DOCX ví dụ 14:16/16:16 → 27/08 | Boundary trước/đúng/sau mở cửa, weekend/holiday, calendar thiếu coverage; provider/calendar manifest thật | unresolved runtime; đặc tả đã chốt |
| F03/F04 | Frozen Candidate, toàn bộ input trước cutoff, reaction không lọt vào ranking | EVENT_SCHEMA.md temporal/freeze rules; SCORING_SPEC.md anti-leakage | Input boundary tests, historical snapshot tests, late evidence tạo version mới, không overwrite score | unresolved runtime; không kết luận từ graph tĩnh |
| F07b | Latest eligible exposure, YEAR, staleness ≤365, deterministic tie-break | EVENT_SCHEMA.md IndustryExposure selection | Boundary 365/366 ngày, future availableAt, latest record/tie-break, missing exposure, reporting scope | unresolved runtime; rule đã đặc tả |
| F07c | Constant strength versus exposureStrength trên cùng eligible population | SCORING_SPEC.md mục 5; EVALUATION_PROTOCOL.md manifest | Chỉ đổi strength, giữ cohort/eligibility; missing fact không được repair bằng hằng số | unresolved thực nghiệm; không cần kết quả để khóa Phase 1 |
| F08a | Split disjoint, annotation 25%, sealed test, per-type support, paired Event bootstrap | EVALUATION_PROTOCOL.md; ANNOTATION_GUIDELINE.md | Dataset/split manifest, annotation audit, metric fixtures, support report, paired bootstrap với seed và shared draws | unresolved dữ liệu/runner; protocol đã đặc tả |

## D. Mục đã đóng ở mức sửa tài liệu — không đưa lại vào danh sách lỗi mở

**F08b: xung đột phạm vi ablation đã được sửa sau khi người dùng duyệt.**

- SCORING_SPEC.md: bỏ câu `each confidence component replaced by 1`; chỉ neutralize extractionConfidence, linkingConfidence hoặc relationConfidence; sourceConfidence = 0.5.
- EVALUATION_PROTOCOL.md: thêm contract ba variants, cohort/cutoff/path/strength/gold/tie-break giữ nguyên; aggregate riêng theo methodVersion.
- DOCX: thay hai câu `ablation từng thành phần`, sửa bảng tóm tắt và bổ sung protocol trong RQ3.
- TTL/SHACL không đổi; source constraint vẫn `FILTER (?source != 0.5)`.
- Kiểm tra sau sửa đã pass: wording cũ không còn tại các vị trí được sửa; DOCX ZIP hợp lệ; chỉ `word/document.xml` đổi; các ZIP parts khác giữ nguyên; targeted Markdown `git diff --check` pass.
- Chưa visual-render và chưa chạy ablation implementation. Hai việc này không được gộp vào kết quả document-consistency pass.

## Checklist đóng các mục mở

- [x] Người dùng duyệt phương án thêm audit so sánh tự động chỉ đọc vào gói.
- [x] Implement và chạy audit; README ghi đúng scope PASS/FAIL/NOT CHECKED.
- [x] Đối chiếu structured endpoint/domain và cardinality được in trong appendix; các phần ngoài phạm vi giữ NOT CHECKED.
- [x] Cập nhật DOCX về script hiện có và kết quả audit có phạm vi; không trộn với behavioral SHACL tests.
- [x] Người dùng duyệt lượt đồng bộ gồm reference/claim verification.
- [x] Sửa reference/claim trực tiếp trong paragraphs và tables, không chỉ thêm correction note.
- [ ] Tùy chọn: nếu cần bổ sung claim behavioral SHACL trong tương lai, phải có fixture/test và fresh valid/invalid probes; hiện không còn dùng số 9/9, 7/7 làm verification chính.
- [ ] Render và inspect Word/Draw.io; nếu tool không khả dụng, ghi visual unverified.
- [ ] Review thủ công nội dung các tab ngoài appendix và shared/narrative properties mà audit không kiểm tra.
- [ ] Người dùng quyết định giữ minh họa synthetic lịch sử như hiện tại hay rút gọn/chuyển phụ lục; chưa tự sửa phần này.
- [x] Cập nhật matrix bằng fresh audit output và fresh DOCX extraction.
- [x] Runtime/calendar/evaluation Phase 2 vẫn được ghi chưa verify, không đưa thành lỗi đặc tả Phase 1.

## Ghi chú evidence

- DOCX P/T/R được đánh số theo python-docx, không phải page number; cần đối chiếu lại sau các lần chèn/xóa đoạn.
- Những line numbers của TTL/SHACL nêu ở đây dùng snapshot đã review; line numbers của Markdown có thể đổi sau khi bổ sung contract ablation. Section name là locator ổn định hơn.
- Lượt cập nhật này có fresh audit tự động theo phạm vi appendix và fresh DOCX text/table extraction; không phải review lại toàn bộ semantic nội dung, không visual-render và không chạy behavioral SHACL validation.
