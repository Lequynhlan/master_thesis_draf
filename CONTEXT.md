# Bối cảnh project

## Mục tiêu

Đề tài xây dựng đồ thị tri thức tài chính có trọng số từ tin tức tiếng Việt và dữ liệu giao dịch trên thị trường chứng khoán Việt Nam. Thiết kế ontology và Phase 1 đã được chốt với giảng viên. Phase 2 tập trung hiện thực pipeline và chứng minh pipeline chạy xuyên suốt, có thể tái lập và trình bày được.

## Luồng xử lý dự kiến

### 1. Khởi tạo dữ liệu nền

Thu thập và nạp các thực thể/dữ liệu nền: `NewsSource`, `GovernmentOrganization`, `Company`/`Bank`, `Stock`, `CompanyAlias`, `IndustryGroup`, `Industry`, `CorporateLeader`, `LeadershipPosition`, `MarketIndex`, `IndexMembership`, `SubsidiaryRelation`, `FinancialMetric` và `IndustryExposure`. Các thực thể này cung cấp danh mục và quan hệ để nhận diện thực thể trong tin tức, tạo ứng viên Event–Stock và làm benchmark cho phân tích thị trường.

### 2. Nạp dữ liệu hằng ngày

- Thu thập bài viết thành `NewsArticle` từ các `NewsSource`.
- Thu thập giá/khối lượng theo phiên thành `MarketObservation` cho `Stock`.
- Thu thập dữ liệu chỉ số theo phiên thành `MarketIndexObservation` cho `MarketIndex`.
- Cập nhật `FinancialMetric` và `IndustryExposure` khi có dữ liệu mới.

### 3. Xử lý bài báo và sự kiện

Trích xuất đoạn văn bằng chứng thành `Evidence`, sau đó nhận diện và chuẩn hóa `Event`. Gắn sự kiện với các thực thể liên quan như `Company`, `Stock` và `Industry`; xử lý bài trùng, bài cập nhật hoặc bài làm rõ để nhiều bài có thể cùng cung cấp bằng chứng cho một canonical Event. Vertical slice dùng PhoBERT tạm thời cho bước trích xuất.

### 4. Sinh ứng viên Event–Stock

Tại `inferenceCutoff`, tìm cổ phiếu liên quan qua các route baseline: `DIRECT`, `INDIRECT_INDUSTRY`, `INDIRECT_SUBSIDIARY` và `INDIRECT_LEADERSHIP`. Tạo `EventStockCandidate`, lưu route và lý do liên kết, các thành phần confidence, `confidenceScore` và `candidateScore`. Candidate biểu diễn suy luận Event–Stock trước khi xét phản ứng giá.

### 5. Đánh giá phản ứng sau sự kiện

Sau khi event window đóng và dữ liệu cần thiết đã khả dụng, đối chiếu `MarketObservation` với `MarketIndexObservation`, kiểm tra provenance và tính AR/CAR. Lưu kết quả thành `EventStockReaction`, liên kết về Candidate và các quan sát đầu vào để có thể truy vết, tái tính toán.

## Các quyết định Phase 2 hiện tại

- Vertical slice cố định ở **100 bài báo** và **13 cổ phiếu ngân hàng VN30**: ACB, BID, CTG, HDB, LPB, MBB, SHB, SSB, STB, TCB, VCB, VIB, VPB. Candidate universe phải giới hạn ở 13 mã này.
- Cấu hình slice đang dùng danh sách VN30 sau kỳ rà soát tháng 7/2026, hiệu lực từ 03/08/2026; nếu thời gian nghiên cứu khác mốc này thì cần xác nhận lại membership theo thời điểm.
- Đây là vertical slice để kiểm tra và trình diễn pipeline end-to-end, không phải quy mô của final evaluation dataset.
- PhoBERT chỉ là model trích xuất tạm thời cho vertical slice; cần lưu model/config/version để có thể tái lập lần chạy.
- Candidate và Reaction là hai khái niệm riêng: candidate score phục vụ xếp hạng tại inference time; reaction weight phục vụ phân tích hậu nghiệm sau event window.
- Dữ liệu nền sẽ được triển khai và chạy theo từng loại entity để phát hiện sớm lỗi nguồn. Entity đầu tiên đang thử là `Stock`; nguồn được giới hạn ở VietstockFinance và CafeF.
- Entity `Stock` đã crawl đủ 13 mã trong universe. Crawler lấy mã/sàn công khai từ VietstockFinance và đối chiếu mã từ CafeF, ghi snapshot chuẩn hóa cùng URL và thời điểm lấy dữ liệu tại `data/snapshots/stocks/`.
- Entity `Company/Bank` cũng đã crawl đủ 13 hồ sơ CafeF, nối mỗi ngân hàng với `Stock` tương ứng và lưu tại `data/snapshots/companies/`.
- Trang CafeF của HDB và TCB dùng route hồ sơ `/hose/`; trên hai trang này crawler đối chiếu mã qua tiêu đề trang do CafeF cung cấp khi phần tử `.symbol` không có.
- Dữ liệu dùng cho pipeline phải được lấy từ các lượt crawl của project và lưu thành raw data/snapshot có provenance phù hợp; không thay bằng bộ dữ liệu dựng sẵn, fixture hay file tải sẵn không qua crawler. Với `Stock`, snapshot đã crawl hiện được lưu tại `data/snapshots/stocks/`.
- Crawler không dùng phiên đăng nhập Edge, không lưu HTML và không cố lấy trường bị giới hạn quyền xem. Nếu trang đổi cấu trúc hoặc trường cần thiết không hiển thị, dừng lượt crawl và ghi nhận vướng mắc trước khi mở rộng.
- `schema/ontology.ttl` và `schema/shapes.ttl` là nguồn đặc tả chính cho ontology và ràng buộc dữ liệu. Sơ đồ chỉ minh họa luồng; tránh duy trì một danh sách schema thủ công thứ hai.

## Trạng thái crawl dữ liệu nền (2026-10-16)

Đã có 7 quan hệ công ty con được nguồn xác nhận tại các mốc quan sát; ngày bắt đầu chính xác chưa xác định. Chi tiết mốc và nguồn nằm trong `doc/initial_data_load_status.md`.

Initial data load still lacks FinancialMetric coverage for 12/13 banks. IndustryExposure currently has 128 KG records across 10/13 banks (ACB, BID, CTG, HDB, MBB, SHB, STB, TCB, VCB, VPB); LPB, SSB, and VIB are missing. See doc/industry_exposure_collection_plan.md for reporting periods and comparison limits.

## Cách dùng tài liệu

File này ghi mục tiêu, luồng và các quyết định nghiên cứu để giữ nhất quán khi triển khai. Chi tiết lớp, thuộc tính, công thức, cutoff và validation phải đối chiếu với `schema/ontology.ttl` và `schema/shapes.tt`; cập nhật đặc tả tại nguồn tương ứng thay vì chép toàn bộ sang đây. Cấu trúc trong `doc/structure_project.txt` mô tả khung vertical slice; module scaffold chưa đồng nghĩa với pipeline đã triển khai hoàn chỉnh.

## Trạng thái IndustryExposure mới nhất (2026-10-16)

KG có 128 `IndustryExposure` thuộc 10/13 ngân hàng: ACB, BID, CTG, HDB, MBB, SHB, STB, TCB, VCB và VPB. Còn thiếu LPB, SSB và VIB. Lượt build gần nhất báo `SHACL_CONFORMS`. Chi tiết nguồn/kỳ xem `doc/industry_exposure_collection_plan.md`.


## Quan hệ sở hữu

**`SubsidiaryRelation`**: Quan hệ giữa công ty mẹ và công ty con được nguồn xác nhận. `validFrom` là ngày bắt đầu khi nguồn nêu rõ; `observedAsOf` là ngày nguồn xác nhận quan hệ đang tồn tại, không hàm ý ngày bắt đầu.

## Chỉ tiêu ngân hàng

**`FinancialMetric`**: Một giá trị tài chính gắn với một doanh nghiệp, kỳ báo cáo và nguồn cụ thể. Giá trị số dư tại ngày chốt kỳ cần được phân biệt với giá trị dòng phát sinh trong cả kỳ.

**`IndustryExposure`**: Snapshot dư nợ cho vay khách hàng của một ngân hàng gắn với một ngành tại ngày/kỳ báo cáo. Với dữ liệu trích từ bảng phân bổ dư nợ theo ngành, `exposureRatio = dư nợ ngành / tổng dư nợ cho vay khách hàng` trên cùng phạm vi hợp nhất và cùng kỳ; `exposureStrength` trong vertical slice lấy bằng `exposureRatio` để làm trọng số đường liên kết gián tiếp. `relationConfidence` mô tả độ tin cậy của bằng chứng/ánh xạ ngành, không thay cho tỷ trọng. Lưu nguyên nhãn báo cáo vào `reportedCategory`; chỉ dùng chung một `Industry` khi phân loại có thể ánh xạ rõ. Không suy ra tỷ trọng từ tổng dư nợ, không coi phần ngành không công bố là 0, và không ép các nhãn không tương đương vào cùng taxonomy.
