# Các quyết định trước khi khóa final evaluation

Các đặc tả Phase 1 đã được đồng bộ để thầy review. Trước khi chạy final evaluation, người làm luận văn cần đưa các giá trị thực vào manifest và khóa chúng trước khi đọc tập test.

1. **Universe/thời gian:** thành phần Stock theo từng ngày hiệu lực, phạm vi thời gian và có dùng VN30 làm benchmark hay không. Sơ đồ ghi ngân hàng VN30 là pilot dự kiến; đây chưa phải final frame.
2. **Thị trường/provenance:** vendor/snapshot cho giá stock và index, quy ước adjusted close/corporate action, exchange, timezone và phiên bản lịch giao dịch. Thiếu các mục này thì không thể tái lập day 0 hoặc AR/CAR.
3. **Gold corpus/annotation:** danh sách corpus final, annotator độc lập và adjudicator. Protocol đã ấn định tối thiểu 25% double-label nhưng chưa thể tự nêu người/corpus từ tài liệu.
4. **Chốt định danh Candidate:** bản 1.0.5 quy định Candidate riêng cho mỗi đường cụ thể, keyed by stable Event URI + `concretePathKey`; đây là lựa chọn đã áp dụng để bảo toàn khác biệt đường/con điểm, không thêm ontology property. Đưa quy tắc này vào review của thầy trước Phase 2. Nếu thầy yêu cầu một Candidate mỗi route thay vào đó, cần sửa lại thuật toán/audit và metric trước khi code.
5. **Xuất PDF:** bản Word 1.0.5 cần được mở/xuất bằng Microsoft Word và kiểm tra lại trang/bảng/ảnh. PDF cũ đã được đổi tên có nhãn superseded 1.0.4, không ghép với Word mới.
