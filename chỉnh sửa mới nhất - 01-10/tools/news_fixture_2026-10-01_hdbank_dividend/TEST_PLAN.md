# Fixture tin HDBank: cổ tức bằng cổ phiếu, 2026-10-01

## Nguồn và thời điểm

- Bài đăng sớm nhất trong nhóm báo cáo: VietnamPlus, [bài về cổ tức/cổ phiếu thưởng HDBank](https://www.vietnamplus.vn/ngan-hang-hdbank-chot-chia-co-tuc-va-co-phieu-thuong-ty-le-30-post1139459.vnp). Trang ghi `01/10/2026 16:06` nhưng không ghi múi giờ; fixture tạm giả định giờ Việt Nam UTC+07. Bài được giữ làm provenance Article, không trích Evidence trong fixture.
- Nguồn cung cấp Evidence cho Event: Hiệp hội Ngân hàng Việt Nam (VNBA), [bài về phương án phát hành cổ phiếu HDBank](https://vnba.org.vn/vi/hdbank-phat-hanh-hon-1-5-ty-co-phieu-tra-co-tuc-va-tang-von--chot-danh-sach-co-dong-ngay-12-10-2026-23749.htm). Trang ghi `01/10/2026 lúc 10:11 (GMT)`; earliest Evidence/cutoff trong graph là `2026-10-01T10:11:00Z`.
- Các dữ kiện được bài nêu: HDBank/mã HDB; cổ tức năm 2025 bằng cổ phiếu tỷ lệ 25%; ngày đăng ký cuối cùng 12/10/2026; riêng phương án phát hành từ quỹ dự trữ tỷ lệ 5%; tổng hai cấu phần 30%; các văn bản 2318/2026/CV-HDBank, 2319/2026/CV-HDBank và nghị quyết 17/2026/NQ-ĐHĐCĐ.
- Bài [Tin nhanh chứng khoán ngày 02/10](https://m.tinnhanhchungkhoan.vn/hdbank-hdb-chot-quyen-chia-co-tuc-va-phat-hanh-co-phieu-thuong-ty-le-30-post398709.amp) ghi `02/10/2026 11:22` (giờ Việt Nam được giả định từ ngữ cảnh trang) và nêu rõ `HDB – sàn HOSE`; bài này được thêm như một bài báo cáo/corroboration đến sau, không làm thay đổi cutoff sớm nhất ở VietnamPlus.

## Phạm vi và giả định được đánh dấu

- Đây là fixture kiểm thử có Event theo taxonomy `DIVIDEND`; chỉ mô hình hóa hành động trả cổ tức bằng cổ phiếu `DECLARE_STOCK` ở mức 25%. Phần phát hành 5% từ quỹ dự trữ được giữ riêng trong mô tả để tránh biến tổng tỷ lệ 30% thành tỷ lệ cổ tức.
- Phạm vi là một Event cổ tức HDBank gắn với ba tài nguyên Article: VietnamPlus (provenance, không tạo Evidence), VNBA (nguồn Evidence) và Tin nhanh chứng khoán (corroboration). Q1 vì vậy kỳ vọng 3 hàng Article; ba bài không được diễn giải thành ba Event.
- `availableAt` của từng bài đặt bằng giờ xuất bản làm proxy, vì không có log crawler/first-seen. Nó chưa chứng minh thời điểm hệ thống ingestion thật sự biết tin. VietnamPlus Article sớm hơn nhưng không phải nguồn Evidence được chọn; Event availability là thời điểm Evidence sớm nhất trong graph.
- `occurrence_id` lấy từ số Thông báo 2319/2026/CV-HDBank mà VNBA dẫn làm tài liệu cho ngày chốt quyền. Chưa đối chiếu trực tiếp bản thông báo gốc do HDBank phát hành; trước khi coi đây là identity adjudication đã khóa, cần kiểm tra số hiệu này trong hồ sơ gốc.
- Company, Stock và cạnh `hasStock` biểu diễn mapping HDBank—HDB được bài VNBA nêu để query kiểm tra. Đây là liên kết nguồn trong fixture, không phải hồ sơ Company–Stock bất biến/versioned theo contract Candidate.
- `effectiveTradingDate=2026-10-02` dựa trên timestamp Evidence sớm nhất `10:11Z` = 17:11 giờ Việt Nam (sau phiên ngày 1/10) và thông báo lịch nghỉ giao dịch 2026 chính thức của HOSE: [HOSE holiday schedule (PDF)](https://staticfile.hsx.vn/Uploads/UploadDocuments/2428610/20251209%20-%20HOSE%20-%20Notice%20of%20trading%20holiday%20schedule%20for%202026%20-%20PV.pdf). Ngày 2/10 không nằm trong các đợt nghỉ được thông báo. Đây là phép xác định lịch cho fixture; vẫn cần lịch phiên/nguồn exchange chính thức có version ID để khóa curated baseline.
- `NewsSource.reliabilityScore=0.5` chỉ là giá trị cấu trúc theo fixture/baseline; không phải đánh giá độ tin cậy đo lường của VNBA.

## Câu hỏi, query và kết quả kỳ vọng

| ID | Câu hỏi kiểm thử | Kết quả kỳ vọng |
|---|---|---|
| Q1 | Các bài báo cáo cùng Event và thời điểm công bố là gì? | 3 hàng theo thời gian: VietnamPlus `2026-10-01T16:06:00+07:00` (múi giờ +07 giả định), VNBA `2026-10-01T10:11:00Z` (GMT ghi trên trang), Tin nhanh chứng khoán `2026-10-02T11:22:00+07:00` (+07 giả định). |
| Q2 | Bài có Event cổ tức canonical nào và cutoff/effective date nào? | 1 hàng: `DIVIDEND`, `DECLARE_STOCK`, record date `2026-10-12`, cutoff `2026-10-01T10:11:00Z`, effective date `2026-10-02`. |
| Q3 | Event nối tới issuer/ticker nào và các con số nào được mô tả? | 1 hàng: HDBank, HDB; cổ tức cổ phiếu 25%, ngày chốt quyền 12/10, riêng phần tăng vốn 5%, tổng 30%. |
| Q4 | Có bao nhiêu Evidence từ bài VNBA được liên kết tới Event? | 4 Evidence: phát hành/cổ tức, tỷ lệ 100:25, ngày chốt quyền và số hiệu thông báo. Đây là các trích đoạn chính xác; fixture chưa có adjudication audit cho assignment vai trò hoàn chỉnh. |
| Q5 | Có Candidate nào đã đủ contract để sinh chưa? | 0 Candidate. Fixture chưa có Company–Stock mapping record ID bất biến, concretePathKey, frozen path/snapshot audit hay complete assignment audit; không được suy Candidate chỉ từ cạnh `hasStock`. |
| Q6 | Có Reaction/market result nào được xác nhận không? | 0 Reaction. Không có chuỗi giá điều chỉnh, chỉ số benchmark, market observations hay cửa sổ hậu sự kiện đã hoàn tất. |

Query thực tế ở `queries.rq`, kết quả đối chiếu ở `expected.json`. Câu Q1/Q2/Q3/Q4 cho kết quả nghiệp vụ khác 0; Q5/Q6 bằng 0 có chủ đích vì thiếu điều kiện contract, không phải dữ liệu giả lập.

## Ranh giới kiểm chứng

`run_checks.py` chạy SHACL 1.0.5 không suy diễn (`inference=none`) và thực thi sáu query trên đúng `data.ttl`. SHACL chỉ kiểm cấu trúc RDF; nó không kiểm tra taxonomy/dictionary membership, sự thật của canonical key, occurrence adjudication, hồ sơ mapping bất biến, phiên giao dịch hay tính đúng của nguồn. Kết quả pass vì thế không được diễn giải thành Candidate, phản ứng giá hay kết luận tác động đầu tư đã được xác nhận.

Chạy trong môi trường có `rdflib` và `pyshacl`:

```bash
python3 "master_thesis_draf/chỉnh sửa mới nhất - 01-10/tools/news_fixture_2026-10-01_hdbank_dividend/run_checks.py"
```
