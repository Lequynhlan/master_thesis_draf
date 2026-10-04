# Review lại đủ 9 góp ý — bản hiện hành contract 1.0.4

## Phạm vi và kết luận

Nguồn yêu cầu: `ban_thay_gop_y/gop_y_phase1_truoc_code_phase2.txt`.
Bộ được review: đúng `chỉnh sửa mới nhất - 01-10/`, gồm ontology/SHACL, schema/scoring/evaluation/annotation/dictionary, Draw.io `.drawio`, báo cáo DOCX/PDF `_hieu_dinh`, tools và acceptance note. Không dùng bản đã gửi thầy hoặc backup làm nguồn chuẩn. HEAD được kiểm tra: `7786e98`, branch `docs/phase1-contract-1.0.4`.

Đây là review chỉ đọc các artifact nguồn; file này là kết quả review mới nằm ngoài gói gửi thầy. Không sửa bộ đặc tả, không commit/push.

**Luồng chính đúng và nhất quán ở mức thiết kế Phase 1:** Article/Evidence → canonical Event → Candidate ở cutoff → candidateScore/ranking → đủ market window → Reaction/AR/CAR/reactionWeight. Không phát hiện lý do phải mở rộng ontology.

**Chưa nên nói toàn bộ đã fix hoàn toàn.** Các yêu cầu chính, đặc biệt nhóm thầy ưu tiên 1/2/3/4/5/9, đã được xử lý ở mức specification. Nhưng còn hai lựa chọn annotation/agreement chưa khóa đủ chi tiết, một hạn chế logic của query minh họa và các tài liệu phụ bị cũ. Những điểm này không đồng nghĩa pipeline Phase 2 đã sai hoặc toàn bộ schema phải sửa.

## Ma trận theo nguồn góp ý

Đường dẫn dưới đây tương đối với `chỉnh sửa mới nhất - 01-10/`, trừ khi ghi rõ. P là paragraph thân bài DOCX, 1-based; số trang là trang vật lý PDF.

| Mục và dòng góp ý | Yêu cầu | Bằng chứng hiện hành | Kết luận |
|---|---|---|---|
| 1 — L7–24 | Đồng bộ tên/namespace, bốn route, không mở rộng baseline; TTL/SHACL chuẩn | `EVENT_SCHEMA.md:5–7,30–39`; `shapes_v1.0.ttl:291–338`; Draw.io tab 00 namespace, tab 01 cell `mZ28CVNe_N0uJWWchiWa-46`, tab 03 temporal note, tab 05 route note; DOCX/PDF hiện hành dùng WFKG và cùng namespace | **Đã xử lý yêu cầu chính.** Industry chỉ tới Bank có exposure hợp lệ; SUBSIDIARY chỉ con→mẹ. Việc company mẹ giữ hasSubsidiaryRelation không có nghĩa baseline suy mẹ→con. Các query minh họa vẫn cần giới hạn nêu bên dưới; không suy audit appendix chứng minh toàn bộ báo cáo. |
| 2 — L26–36 | Daily: trước open dùng phiên đó, từ open dùng phiên sau | `EVENT_SCHEMA.md:86–95`; `SCORING_SPEC.md:77,102–106`; `ANNOTATION_GUIDELINE.md:42`; SHACL kiểm cutoff/timestamp; ảnh Q1/Q3/Q5 hiển thị day 0 là 27/08 thay vì 26/08 | **Fixed ở mức contract.** Chốt strict-opening, timezone, calendar, exact cutoff; replay muộn không lấy input tương lai. Calendar/session executor thật thuộc Phase 2. |
| 3 — L38–56 | Lưu đủ components; source nhiều Evidence, linking, DIRECT, freeze | `SCORING_SPEC.md:24–38,54–77`; `EVENT_SCHEMA.md:66–75`; Candidate có bốn components; appendix tab 06 có linkingConfidence | **Fixed ở mức contract/schema.** Source cố định 0.5 là experimental control; extraction chọn complete assignment, linking/relation theo bảng bốn route, provenance/fallback rõ. Calibration và immutable storage thực phải triển khai ở Phase 2. |
| 4 — L58–74 | candidateScore inference; reactionWeight hậu nghiệm, không leakage | `SCORING_SPEC.md:24–31,79–110,112–124`; `EVENT_SCHEMA.md:41–54`; `EVALUATION_PROTOCOL.md:113–125`; Draw.io tab 04/05 | **Fixed.** Ranking chỉ dùng candidateScore; max path theo Event–Stock/method/cutoff; reactionWeight báo hậu nghiệm từng path, không cộng CAR lặp. E02 cũ đã được bổ sung constraint và regression. |
| 5 — L76–90 | Có stock/index close t−1/t và đầy đủ window để tính lại AR/CAR | `EVENT_SCHEMA.md:56–64`; `SCORING_SPEC.md:81–97`; `shapes_v1.0.ttl:417–635`; observations đều có adjustedClose/sourceReference; ảnh Q10 hiển thị giá stock/index ở 26 và 27/08 | **Fixed ở mức nguồn dữ liệu/schema và arithmetic contract.** Đã chạy tests cho close/cache/CAR/impact/direction. Exact exchange sessions, vendor adjustment và version selection thật vẫn là gate Phase 2. Query 5 không phải bằng chứng benchmark-specific đầy đủ. |
| 6 — L92–108 | Dictionary machine-readable 10–15 types, roles/key/direction/examples/confusables | `EVENT_DICTIONARY.yaml`: version 1.0.4, 14 entries; có đủ fields; normalization/identity rules; `EVENT_SCHEMA.md:118–124`; `ANNOTATION_GUIDELINE.md:35,46–47` | **Fixed ở mức đặc tả.** YAML parse được và kiểm tra cấu trúc entries không báo lỗi. Chưa có NLP/normalization executor thực. |
| 7 — L110–118 | reports raw/curated; exposure theo kỳ/latest/staleness; biến thể strength thực | `EVENT_SCHEMA.md:19,97–116`; `SCORING_SPEC.md:41–54`; `ANNOTATION_GUIDELINE.md:43`; Draw.io tab 03 tách tenure và exposure | **Fixed ở mức contract.** Raw reports 0..*; curated gate bắt Event. Exposure YEAR/scope/periodEnd/availability/365 ngày/tie-break; variant dùng exposureStrength=exposureRatio trên cùng eligible cohort. Query 7 là minh họa có prerequisite, không phải correction-aware executor. |
| 8 — L120–137 | Tách vertical slice/final, annotation labels, double-label/agreement, theo impactType và macro Event | `EVALUATION_PROTOCOL.md:5–12,23–37,49–70,76–147`; `ANNOTATION_GUIDELINE.md:9–18,29–69`; double-label 25%, các metric/route projection/ablation/bootstrap/missed gold được mô tả | **Đã xử lý phần lớn, còn cần chốt hai rule để protocol thực thi tái lập:** đơn vị/cách chọn double-label subset; alignment các annotation độc lập trước tính kappa/agreement. Không đòi có final dataset hay kết quả RQ để đóng thiết kế Phase 1. |
| 9 — L139–154 | Property appendix đủ và có script generation/audit | Draw.io tab 06 có subsidiaryCompany/memberStock/exposureBank/exposureIndustry/forEvent; `tools/audit_schema_diagram.py`; `tools/README.md:45–89` | **Fixed trong phạm vi hỗ trợ của audit.** Fresh audit 337 PASS, 0 FAIL, 57 NOT CHECKED. NOT CHECKED không phải 57 lỗi và không được nâng thành full semantic equivalence. |

## Các điểm còn lại — phân biệt lỗi, lựa chọn protocol và tài liệu phụ

### R01 — Quy tắc chọn subset double-label chưa đủ cụ thể

Vị trí: `ANNOTATION_GUIDELINE.md:58`, `EVALUATION_PROTOCOL.md:25`.

Đã quy định ít nhất 25% gold set, hai người gán độc lập, agreement trước adjudication và reviewer thứ ba. Nhưng gold có nhiều đơn vị: Article, Event mention, entity-role mention, Event–Stock pair, Event-relation pair. Chưa khóa 25% tính trên đơn vị nào và subset được chọn thế nào/seed/strata/IDs.

Tác động: hai implementation có thể double-label các tập rất khác nhau và vẫn nói đã đạt 25%; agreement chưa tái lập chính xác. Đây là **lựa chọn protocol cần chốt**, không phải bằng chứng đã gán nhãn sai.

Sửa tối thiểu đề xuất: khóa đơn vị lấy mẫu, quy tắc chọn/version/seed và lưu subset IDs; nêu phạm vi downstream annotations của đơn vị đã chọn. Đồng bộ guideline/protocol và mô tả liên quan trong báo cáo; không sửa ontology.

### R02 — Alignment trước agreement chưa khóa

Vị trí: `ANNOTATION_GUIDELINE.md:60–65`.

Evidence span agreement đã có union-character và exact-boundary F1. Event type/expectedDirection có kappa, entity links có exact match theo role. Tuy nhiên hai người gán độc lập có thể tách Event mentions hoặc boundaries khác nhau; chưa chốt cách ghép annotation units và xử lý unmatched mentions trước tính các agreement này. Rules prediction–gold ở `EVALUATION_PROTOCOL.md:49–59` không tự động thành annotator–annotator alignment nếu không có dẫn chiếu rõ.

Sửa tối thiểu đề xuất: định nghĩa shared/aligned units, tie-break và cách báo unmatched/detection disagreements; khóa denominator và không dùng adjudicated labels thay original labels khi đo agreement.

### R03 — Query 5 không gắn observation với benchmark đã chọn

Vị trí: DOCX P205, PDF trang 35:

`OPTIONAL {?index wfkg:hasIndexObservation ?i . ?i wfkg:tradingDate ?day}`

`?index` không bị ràng buộc vào benchmark của Candidate/method configuration. Diagnostic dùng query literal hiện hành, trên graph nhỏ tổng hợp riêng: Candidate không có stock day-0 observation; chỉ một index không liên quan có observation ngày đó. Query vẫn trả `day0Stock=0, day0Benchmark=1, reactions=0`.

Đây là **hạn chế logic query đã tái hiện**, không phải kết quả của fixture thị trường hay bằng chứng Reaction validator sai. Query đang nằm trong phần minh họa lịch sử, không thay thế production validator. Không được dùng nó chứng minh “đủ/thiếu đúng benchmark đã khóa”.

Sửa tối thiểu đề xuất: bind benchmark từ frozen configuration/VALUES hoặc graph đã prefilter rõ theo benchmark; nếu giữ lịch sử nguyên trạng, thu hẹp purpose/caption đúng phạm vi query. Không tự sửa hoặc bịa fixture/CSV lịch sử.

### R04 — Query 9 chỉ bao phủ Event đã có Candidate

Vị trí: DOCX P276: mandatory `?e wfkg:hasEventStockCandidate ?c`.

Diagnostic Event có Article nhưng không có Candidate không xuất hiện trong result. Điều này hợp lệ nếu chỉ minh họa hai fixture Events vốn có Candidate; **không phải lỗi schema/canonicalization đã xác nhận**. Nó không audit toàn bộ no-Candidate cases hoặc tự chứng minh duplicate không làm mất coverage. Nếu muốn audit coverage tổng quát, cần OPTIONAL/count-zero view riêng hoặc giới hạn claim rõ.

### R05 — Ma trận nội bộ cũ chưa cập nhật theo bản mới

`review_phase1/FEEDBACK_MATRIX_OPEN_ITEMS.md:17–19,25,75–84,123–126,162` vẫn ghi E02 mở, chưa có full behavioral suite/PDF/visual evidence trong vòng cũ.

Hiện tại shapes đã có impactScore constraint tại `shapes_v1.0.ttl:417–425`, direction constraint tại `:426–434`; fresh behavioral tests bắt sai direction và sai impact ngay cả khi weights khớp. PDF hiện hành có 47 trang. Do đó không dùng ma trận cũ kết luận bản mới còn E02 hoặc chưa có PDF.

Đây là trạng thái tài liệu nội bộ cũ, **không phải schema còn thiếu hai constraints**. File review mới này không ghi đè matrix cũ.

### R06 — Bản diễn giải tiếng Việt chưa theo contract 1.0.4

`BAN_TIENg_VIET_DE_DOC/03_EVENT_SCHEMA_TIENg_VIET.md:4,175–179` còn version 1.0.2 và `inferenceCutoff >= Event.availableAt`, trong khi nguồn chuẩn khóa equality tại `EVENT_SCHEMA.md:92` và SHACL kiểm equality. Các bản dịch khác cũng gắn version 1.0.2, nên không mặc định chúng phản ánh các clarification mới nhất.

Bản dịch tự ghi là bản đọc dễ hiểu, English source là contract chính. Vì thế không kết luận ontology đang dùng rule sai; nhưng nếu gửi cả folder hoặc đọc bản dịch để code sẽ dễ hiểu lệch. Cần cập nhật bản đọc hoặc tách/đánh dấu historical, không chỉ đổi số version.

## Kết quả tool chạy mới

- Python hiện có dependency trên máy này là `C:\Python314\python.exe` (`python`). `py -3.13` thiếu rdflib nên lần đầu không chạy được; đã chuyển interpreter, không cài thêm package.
- `python -B "chỉnh sửa mới nhất - 01-10/tools/test_baseline_shacl.py"`: **31 tests, OK**, inference=none; synthetic fixture, không phải pipeline/RQ.
- `python -B "chỉnh sửa mới nhất - 01-10/tools/test_schema_diagram_audit.py"`: **8 tests, OK**.
- `python -B "chỉnh sửa mới nhất - 01-10/tools/audit_schema_diagram.py"`: **337 PASS, 0 FAIL, 57 NOT CHECKED**, exit 0; **44 SHACL SELECT** parse được.
- `python -B review_phase1/test_contradicts_contract.py`: **8 synthetic contract tests, OK**; reference diagnostics ngoài acceptance set, không phải production reasoner/evaluator.
- Ontology: 457 triples, 22 OWL classes. Shapes: 1092 triples. Dictionary: 14 entries; Draw.io: 7 tabs.
- DOCX ZIP testzip trả None (không có corrupt member); 332 body paragraphs, 30 tables. **10/10 SPARQL query literal blocks** khớp nguyên văn với DOCX và parse thành công. Query syntax PASS không chứng minh behavioral correctness.
- PDF hiện hành: **47 trang**. Đối chiếu prose/tables và các rule trọng yếu; review độc lập so text DOCX/PDF sau xử lý header/line breaks không thấy body segment bị thiếu. Không render lại toàn bộ Word/Draw.io trong lượt này.
- Đã xem contact sheet của 9 ảnh demo đang nhúng: daily day 0 là 27/08, pending chưa có observation/Reaction, Reaction available sau window; Q10 có stock và benchmark adjusted closes. Ảnh là historical synthetic selected fields; không có full CSV/fixture trong folder để tái lập toàn bộ bindings. READY/PENDING là labels rút gọn trong ảnh, không dùng như RDF enum hiện hành.
- Core artifact hashes (TTL/SHACL/spec/dictionary/Draw.io/DOCX/PDF) khớp manifest. Ba byte-hash lệch ở acceptance và hai test scripts đã được chẩn đoán: **chỉ LF→CRLF khi checkout**, cả ba khớp stored hash sau normalize về LF; `git config core.autocrlf=true`. Không gọi đây là schema/score bị đổi. Byte-level checksum toàn bundle vẫn cần quy ước checkout/line-ending nếu dùng làm delivery gate.
- `git diff --check`: qua; không có thay đổi tracked do các phép kiểm tra. Không chạy generator ghi đè báo cáo/diagram/demo.

## Kết luận gửi người dùng

1. **Logic flow chính đã ổn ở mức Phase 1 trước code.** Các vấn đề lớn thầy nêu về timing, components, ranking/reaction, giá benchmark và appendix đã có contract tương ứng và kiểm tra phù hợp.
2. **Chưa kết luận “fix hết, mọi file hoàn toàn đồng bộ”.** Cần chốt R01/R02 trong protocol; xử lý hoặc giới hạn đúng claim của R03; cập nhật/loại khỏi package các tài liệu phụ R05/R06. R04 là giới hạn coverage, không tự thành bug blocking.
3. Không cần mở rộng ontology. Phương án tối thiểu là sửa nhỏ annotation/protocol/query wording và metadata/tài liệu phụ, sau khi người dùng duyệt. Việc actual calendar/provider, immutable snapshots, NLP, gold/agreement và RQ1–RQ3 vẫn thuộc Phase 2, không coi thiếu runtime là lỗi thiết kế Phase 1.
