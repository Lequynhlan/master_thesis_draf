# Bàn giao đặc tả Phase 1 và đối chiếu góp ý

Contract **1.0.5**. Giữ namespace `https://example.org/wfkg/v1#`, 22 lớp, 14 loại Event và bốn route. TTL/SHACL là nguồn chuẩn về schema; Markdown/YAML quy định thuật toán và protocol; Draw.io minh họa các quy tắc đó. Lần hiệu đính này chốt định danh Candidate cho từng đường cụ thể và thêm kiểm tra miền của `severityScore`; chưa chạy pipeline hay kết quả RQ.

## Đối chiếu 9 góp ý của thầy

| # | Trạng thái đặc tả | Nội dung và nơi đã thống nhất | Còn ở giai đoạn sau |
|---|---|---|---|
| 1. PDF–Draw.io–TTL | Đáp ứng ở mức đặc tả | Namespace/WFKG và bốn route nhất quán; đường ngoài baseline được ghi FUTURE EXTENSION. TTL/SHACL là nguồn chuẩn; Draw.io là minh họa. `ontology_v1.0.ttl`, `shapes_v1.0.ttl`, tab 00/05/06, `EVENT_SCHEMA.md` và báo cáo mục ontology/phụ lục. | Audit có phạm vi giới hạn; không chứng minh toàn bộ ngữ nghĩa của sơ đồ. |
| 2. Daily effectiveTradingDate | Đáp ứng quy tắc | Day 0 là phiên có giờ mở strictly later `Event.availableAt`; cutoff bằng đúng `Event.availableAt`, không lùi cutoff khi thiếu assignment. `EVENT_SCHEMA.md` và báo cáo mục temporal/cutoff. | Calendar phiên thật và timezone/exchange cần khóa trong manifest Phase 2. |
| 3. Confidence components | Đáp ứng ở mức đặc tả | Bốn thành phần và điểm tổng được lưu/freeze; cùng Evidence assignment hoàn chỉnh; bảng confidence bốn route và provenance/fallback được nêu trong `SCORING_SPEC.md`, `ANNOTATION_GUIDELINE.md` và báo cáo. | Thực thi entity linker, calibration và audit snapshot chưa được kiểm chứng. |
| 4. candidateScore/reactionWeight | Đáp ứng | `candidateScore` chỉ xếp hạng tại cutoff; `reactionWeight` chỉ tính sau window. Đặc tả khóa score tổng hợp theo max, không cộng CAR trùng; `SCORING_SPEC.md`, `EVALUATION_PROTOCOL.md`, Draw.io và báo cáo RQ3. | Chưa có metric/ranking executor chạy trên dữ liệu thật. |
| 5. Market return provenance | Đáp ứng ở mức schema/protocol | Stock và benchmark observation lưu adjusted close; Reaction tham chiếu mọi phiên cần thiết, kể cả predecessor; return/AR/CAR tính lại được theo công thức trong `EVENT_SCHEMA.md`, `SCORING_SPEC.md` và TTL. | Provider, adjustment convention, calendar và snapshot dữ liệu thật còn phải khóa. |
| 6. Event Dictionary | Đáp ứng | 14 eventType có roles, key/identity policy, direction, ví dụ và confusables trong `EVENT_DICTIONARY.yaml`; annotation quy định nhãn. | Chất lượng NLP/chuẩn hóa/identity chưa được đo trên corpus thật. |
| 7. Data rules | Đáp ứng ở mức đặc tả | Staging `NewsArticle reports Event` cho phép 0..*; quan hệ có phiên bản chọn latest available trước khi kiểm validity; IndustryExposure có period/scope và staleness 365 ngày riêng; có exposure-strength variant. `EVENT_SCHEMA.md`, `SCORING_SPEC.md`, `EVALUATION_PROTOCOL.md`. | Registry/selection gate cần triển khai và kiểm trên dữ liệu thật. |
| 8. Evaluation protocol | Đáp ứng protocol; chưa có kết quả | Vertical slice 100–300 bài chỉ smoke/debug; final evaluation tách riêng, sealed; tối thiểu 25% gold double-label, agreement/adjudication; metric chia route và macro Event được định nghĩa trong `ANNOTATION_GUIDELINE.md` và `EVALUATION_PROTOCOL.md`. | Chưa chốt manifest corpus cuối, chưa gán nhãn/đo agreement hoặc chạy RQ. |
| 9. Draw.io property appendix | Đáp ứng trong phạm vi audit | Property appendix có các quan hệ được yêu cầu; audit XML/TTL/SHACL trong `tools/audit_schema_diagram.py` và test của nó. | 337 assertion PASS, 0 FAIL, 57 NOT CHECKED; phần NOT CHECKED cần rà bằng mắt, không phải PASS. |

## Hiệu đính đồng bộ

- `EventStockCandidate` có một bản ghi cho **mỗi đường cụ thể**, để không nhập nhằng hai quan hệ lãnh đạo/công ty con có cùng route code nhưng confidence khác. Khóa identity dùng Event URI chuẩn ổn định + Stock URI + route + `concretePathKey` + cutoff + method version. Alias/enrichment của `canonicalKey` không thay Event URI hoặc Candidate lịch sử. Định dạng JSON canonical, SHA-256, thành phần identity, điều kiện suppression và phạm vi audit được định nghĩa ở `EVENT_SCHEMA.md`; đây là pipeline/audit field, không thêm ontology property/lớp. `SCORING_SPEC.md` và protocol giữ quy tắc max hiện hành.
- `Event.severityScore` vẫn optional; SHACL kiểm tra decimal `[0,1]` khi được khai báo. Regression mới xác nhận absent và hai đầu mút hợp lệ, giá trị ngoài miền không hợp lệ.
- Event–Company confidence trong báo cáo nay ghi đúng toàn bộ assignment score `A`, cùng quy tắc trong scoring spec.
- Các câu về VN30 đổi từ phạm vi đã khóa sang pilot dự kiến; benchmark/final universe vẫn phải có manifest.
- Vertical slice và hình/query cũ được ghi là smoke/synthetic/history, không là kết quả RQ. “READY” trong hình cũ chỉ là nhãn lịch sử; trạng thái dữ liệu mới là `REACTION_READY`. Câu kiểm tra runner được chuyển thành gate Phase 2.
- Contract tăng từ 1.0.4 lên 1.0.5 vì thêm ràng buộc SHACL và chốt khóa logic Candidate. Không đổi namespace, tên file ontology hoặc số lớp.

## Kiểm tra đã chạy trên bản 1.0.5

- SHACL regression: **32/32** unittest qua bằng Python 3.12, RDFLib 7.6.0 và pySHACL 0.40.1. Gồm regression miền `severityScore`; dữ liệu đều là fixture tổng hợp.
- Draw.io audit regression: **8/8** test qua sau cập nhật kỳ vọng phiên bản.
- Audit sơ đồ: **337 PASS, 0 FAIL, 57 NOT CHECKED**; 44 SELECT constraint parse được. Không thực thi mọi constraint như behavioral SHACL.
- Các kết quả cũ của contract 1.0.4 được giữ trong `tools/verification_contract_1.0.4.json`; manifest mới `tools/verification_contract_1.0.5.json` chỉ ghi hash/test của gói hiện tại và trạng thái PDF.

## Điểm cần bạn chốt trước khi khóa final evaluation

1. Stock universe cuối: constituent ngân hàng theo VN30, ngày hiệu lực từng mã và khoảng thời gian đánh giá; VN30 có tiếp tục là benchmark không.
2. Nguồn giá/benchmark và điều chỉnh corporate action; sàn, timezone, exchange calendar/version. Các lựa chọn phải có snapshot/hash trong run manifest trước khi mở test.
3. Corpus gold cuối, người gán nhãn độc lập và người phân xử bất đồng; giữ mức double-label tối thiểu 25% như protocol.

Các lựa chọn này không cản trở việc gửi **đặc tả Phase 1** để thầy rà soát, nhưng phải được quyết định trước khi chạy final evaluation. Không có số đo RQ hoặc tuyên bố hiệu quả mô hình trong bộ hiện hành.

## Trạng thái Word/PDF

DOCX đã hiệu đính ở contract 1.0.5. Máy hiện tại không có Microsoft Word; bản LibreOffice giải nén vào scratch không khởi động được, nên tôi chưa thể xuất và kiểm tra PDF mới từ DOCX. Để không đưa PDF cũ vào nhầm như thể đã đồng bộ, PDF trước đó được giữ riêng dưới tên `..._superseded_1.0.4.pdf`; PDF này **không phải bản final**. Cần mở DOCX 1.0.5 bằng Word, xuất PDF, rà số trang/bảng/ảnh và cập nhật hash manifest trước khi gọi cả cặp Word/PDF là final.
