# SCORING_SPEC.md

Phiên bản tài liệu: 1.1.0
Phương pháp chấm điểm hiện hành: `WFKG-SCORE-V1`
Không gian tên: `https://example.org/wfkg/v1#`
Trạng thái: đã chốt đặc tả chấm điểm cơ sở cho lát cắt chức năng xuyên suốt; chưa xác nhận việc triển khai hoặc hiệu chuẩn.

## 1. Phạm vi, ý nghĩa và ranh giới phiên bản

Tài liệu này đặc tả cách sinh từng điểm, chọn đầu vào, tổng hợp và lưu đủ dữ liệu để tái lập phép tính. Không chứa ví dụ số hoặc kết quả thực nghiệm.

`WFKG-SCORE-V1` là quy ước cơ sở của dự án, không phải chuẩn độ tin cậy phổ quát. Điểm softmax/sigmoid, giá trị `1.0` của dữ liệu đã được kiểm duyệt, mức hỗ trợ quan hệ tự động `0.5` (giá trị thay thế của phiên bản cũ được tách ở mục 1.1), phép lấy giá trị nhỏ nhất và trung bình bốn thành phần không phải xác suất đúng đã được hiệu chuẩn. Các thành phần có thể phụ thuộc nhau; không giả định độc lập.

### 1.1. Thay đổi so với SCORING_SPEC 1.0.4

| Nội dung | Phiên bản cũ 1.0.4 | WFKG-SCORE-V1 hiện hành |
| --- | --- | --- |
| Trích xuất chưa được hiệu chuẩn | Bộ gán đầy đủ nhận giá trị thay thế 0.5 | Dùng điểm tác vụ của bộ trích xuất đã được tinh chỉnh, lấy giá trị nhỏ nhất trong các quyết định bắt buộc |
| Liên kết thực thể tự động | Cho phép điểm đã được hiệu chuẩn hoặc giá trị thay thế 0.5 | Chỉ xác định thực thể một cách tất định qua sổ đăng ký; trường hợp mơ hồ hoặc chỉ khớp gần đúng phải HOLD |
| Mức hỗ trợ từ Event đến điểm vào tuyến | Dùng điểm bộ gán trích xuất gốc A | Quan hệ tự động có bằng chứng hỗ trợ dùng 0.5; dữ kiện quan hệ đã được kiểm duyệt dùng 1.0 |
| Cường độ DIRECT | 1.0 | 1.0 |
| Cường độ của ba tuyến INDIRECT | 0.5 | 1.0 |
| So sánh cường độ theo mức độ phơi nhiễm ngành | Có trong phương pháp cơ sở cũ | Không thuộc V1; phải dùng phương pháp khác |

Các Candidate của phiên bản cũ không được tính lại hoặc ghi đè bằng V1. Không trộn kết quả xếp hạng của hai phương pháp.

**Ranh giới đồng bộ:** EVENT_SCHEMA.md, EVALUATION_PROTOCOL.md và ANNOTATION_GUIDELINE.md phiên bản tài liệu 1.1.0 cùng dùng WFKG-SCORE-V1. Quy tắc định danh, bốn tuyến, cách chọn dữ kiện theo thời gian và lịch được giữ nguyên; chính sách số của V1 thay thế phiên bản cũ theo bảng trên. TTL/SHACL vẫn là nguồn chuẩn về cấu trúc; việc kiểm tra tuân thủ chung không tự kiểm tra đầy đủ các hằng số, nguồn xác lập và cách chọn đặc thù của phương pháp. `methodVersion` không tự vượt qua các ràng buộc của shape. Báo cáo DOCX/PDF, sơ đồ, bản trình diễn và mã quy trình chưa được xác nhận đồng bộ V1; PHASE1_ACCEPTANCE.md tách bằng chứng lịch sử 1.0.4 khỏi mức độ sẵn sàng của đặc tả hiện hành. Không tuyên bố nghiệm thu toàn bộ bộ tài liệu hoặc phần triển khai chỉ vì các tệp Markdown đã đồng bộ.

Bản cũ được lưu tại `../review_phase1/backups/before_WFKG_SCORE_V1_20261004_191908/SCORING_SPEC.md`.

### 1.2. Công thức bắt buộc

```text
S = sourceConfidence
A = extractionConfidence
L = linkingConfidence
R = relationConfidence
T = relationStrength

confidenceScore = (S + A + L + R) / 4
candidateScore = confidenceScore * T
```

Tất cả thành phần thuộc `[0,1]`. V1 cố định `S=0.5`, `L=1.0` cho đường đi vượt qua điều kiện liên kết, `T=1.0`. A biến thiên theo mô hình; R nhận `0.5` hoặc `1.0` theo nguồn xác lập các cạnh. Không áp dụng ngưỡng điểm để loại Candidate trong V1. Tính đủ điều kiện được quyết định bằng các điều kiện kiểm tra, không bằng điểm tổng.

## 2. Các điều kiện hợp lệ và kết quả khi không đạt

Mọi Candidate phải vượt qua các điều kiện kiểm tra sau; dữ liệu chưa đủ không được thay bằng điểm thấp hoặc giá trị thay thế.

| Nhóm kiểm tra | Điều kiện | Mã lý do khi không đạt |
| --- | --- | --- |
| Mô hình | ED/EAE đã được huấn luyện theo tác vụ, có bản lưu mô hình và bản kê bộ chuyển đổi; các eventTypes được hỗ trợ đã được khai báo | UNSUPPORTED_EXTRACTOR |
| Từ điển | EventType hợp lệ và thuộc phạm vi mô hình; đủ các vai trò bắt buộc theo phiên bản từ điển | UNSUPPORTED_EVENT_TYPE / MISSING_REQUIRED_ROLE |
| Bằng chứng | Các vai trò bắt buộc có bằng chứng hỗ trợ; vị trí bắt đầu tính từ 0, vị trí kết thúc không được tính vào đoạn, truy về đúng phiên bản/mã băm văn bản nguồn; không vượt giới hạn | INVALID_EVIDENCE |
| Chuẩn hóa | Kiểu dữ liệu, từ vựng và ràng buộc nghiệp vụ hợp lệ; không tự bịa thông tin thiếu | INVALID_NORMALIZATION |
| Định danh | Xác định lần xảy ra nghiệp vụ chuẩn theo từ điển/sổ đăng ký định danh; không lấy URL/ngày bài làm ID của lần xảy ra | UNRESOLVED_OCCURRENCE |
| Liên kết | Mọi thực thể bắt buộc và điểm vào tuyến tùy chọn được xác định duy nhất, đúng kiểu, trong sổ đăng ký hợp lệ tại thời điểm chốt | HOLD_LINKING |
| Thời điểm chốt | Mọi đầu vào có thời điểm sẵn có hợp lệ và availableAt <= inferenceCutoff | INPUT_AFTER_CUTOFF / MISSING_AVAILABILITY |
| Tuyến | Một trong bốn đường đi hợp lệ, đúng các đầu mút và Stock đích, đủ dữ kiện hỗ trợ | UNSUPPORTED_PATH / MISSING_ROUTE_FACT |
| Dữ kiện theo thời gian | Chọn đúng phiên bản trước khi kiểm tra hiệu lực; mức độ phơi nhiễm đúng phạm vi/kỳ/độ cũ | INELIGIBLE_TEMPORAL_FACT |
| Điểm | Đủ điểm bắt buộc, hữu hạn, trong [0,1] | INVALID_MODEL_SCORE / INVALID_SCORE_INPUT |

Lỗi ở Event/bộ gán giữ bản ghi trong vùng tạm/HOLD, không tạo Candidate. Lỗi chỉ thuộc một tuyến thì loại tuyến đó; các tuyến hợp lệ khác vẫn được xét. `INVALID_MODEL_SCORE` là lỗi của bộ sinh/bộ chuyển đổi phải điều tra, không được âm thầm bỏ qua như dự đoán chất lượng thấp. Các Event chuẩn mà hệ thống bỏ sót vẫn thuộc tập đánh giá chung nếu quy trình độc lập không loại chúng.

Vượt qua kiểm tra cấu trúc/chuẩn hóa không chứng minh tính đúng đắn về ngữ nghĩa. Việc gắn chủ thể, ranh giới sự kiện, trạng thái khẳng định và tính đúng đắn của vai trò phải được đánh giá bằng dữ liệu chuẩn độc lập; không báo tự kiểm đúng chỉ vì các đoạn xuất hiện trong văn bản.

## 3. Bộ sinh điểm trích xuất

### 3.1. Bản lưu mô hình và bộ chuyển đổi

PhoBERT tiền huấn luyện nguyên bản không phải bộ trích xuất ED/EAE. V1 tự động yêu cầu bản lưu mô hình đã được tinh chỉnh, lưu các phiên bản mô hình/đầu tác vụ/bộ tách token/phân đoạn/bộ giải mã. Dữ liệu mẫu cố định hoặc dữ liệu gán tay ghi `ASSISTED`, không dùng làm kết quả tự động.

Bộ chuyển đổi tham chiếu `V1-SENTENCE-TRIGGER-BIO` của lát cắt chức năng đầu tiên dùng ED để phát hiện từ kích hoạt theo BIO, phân loại EventType đơn nhãn cho từng từ kích hoạt/thể hiện sự kiện và EAE BIO có điều kiện theo thể hiện. Điểm từ kích hoạt là giá trị nhỏ nhất trong các điểm token BIO đã chọn, bắt buộc tham gia phép lấy giá trị nhỏ nhất của bộ gán cùng với EventType và các vai trò bắt buộc. Nếu có các quyết định liên kết bằng mạng nơ-ron bắt buộc khác thì cũng đưa vào phép lấy giá trị nhỏ nhất. Không dùng phân loại cả bài để phân biệt nhiều lần xảy ra. Thể hiện/từ kích hoạt và bộ gán vai trò có các ID riêng. EVENT_SCHEMA.md khóa bộ sinh Evidence theo câu của văn bản gốc, ánh xạ từ kích hoạt tới thể hiện và chính sách cửa sổ; ANNOTATION_GUIDELINE.md khóa các mốc chuẩn độc lập. Bộ tách câu không nhận ranh giới chuẩn; các mảnh xuyên câu không được ghép trong bộ chuyển đổi tham chiếu.

Bộ chuyển đổi khác, gồm bộ phân loại đa nhãn hoặc phân loại đoạn, phải có ID/phiên bản bộ chuyển đổi và được khóa trước khi kiểm thử trên tập giữ riêng; không trộn đầu ra của các bộ chuyển đổi/bản lưu mô hình trong cùng một lượt xếp hạng. Bản kê ánh xạ mọi quyết định bắt buộc tới bộ sinh, cách giải mã và cách truy xuất điểm.

### 3.2. Chuyển logits thành điểm

- Phân loại đơn nhãn: softmax ổn định số học trên toàn bộ tập nhãn; lấy điểm của nhãn bộ giải mã đã chọn.
- Phân loại đa nhãn độc lập: sigmoid của logit nhãn đã chọn; hàm kích hoạt phải đúng mục tiêu huấn luyện, không tùy ý chọn để tăng điểm.
- Phân loại token BIO: softmax ổn định số học theo tập nhãn BIO tại từng token; lấy điểm của nhãn BIO bộ giải mã đã chọn.
- Bộ phân loại đoạn–vai trò: lấy điểm softmax/sigmoid của đoạn–vai trò được chọn theo mục tiêu huấn luyện đã khóa trong bộ chuyển đổi.
- Không dùng logits thô, độ chênh, entropy hoặc điểm trung bình thay cho các cách truy xuất điểm trên trong V1.

Softmax ổn định số học: `p_j = exp(z_j - max(z)) / sum_k exp(z_k - max(z))`. Sigmoid: `p = 1 / (1 + exp(-z))`, tính bằng cách triển khai ổn định số học.

Đối với BIO, bộ giải mã chạy độc lập cho từng thể hiện sự kiện. Chỉ giải mã token văn bản có ánh xạ vị trí; bỏ các token đặc biệt/đệm. Chuỗi BIO vi phạm cấu trúc hoặc không căn chỉnh được về văn bản gốc phải bị từ chối, không sửa nhãn âm thầm. Nếu bộ giải mã dùng giải mã có ràng buộc/CRF thì cách truy xuất điểm phải khai báo rõ là điểm phát xạ hay xác suất biên; bộ chuyển đổi tham chiếu dùng điểm phát xạ softmax, không tự đổi sang xác suất chuỗi.

### 3.3. Điểm đoạn vai trò và tính đầy đủ của quyết định

```text
roleSpanScore = min(điểm của nhãn BIO đã chọn trên mọi token thuộc đoạn)
```

Tính tất cả token dưới mức từ thuộc đoạn; không lấy token đầu hoặc chỉ token có điểm cao. Phân đoạn từ, vị trí từ token dưới mức từ về văn bản gốc và ranh giới đoạn phải được lưu trong đầu ra bộ chuyển đổi. Vai trò có nhiều giá trị điền bắt buộc: tính mọi giá trị điền đã chọn trong bộ gán; điểm vai trò là giá trị nhỏ nhất trong các điểm giá trị điền. Không đưa mọi dự đoán thay thế vào một bộ gán.

Vai trò giá trị nguyên thủy bắt buộc được sinh từ trích xuất bằng mạng nơ-ron dùng điểm của quyết định/đoạn tương ứng. Một vai trò được chuẩn hóa tất định từ đoạn không nhận thêm điểm độc lập; giữ điểm của đoạn đầu vào. Vai trò bắt buộc/ID của lần xảy ra được xác định tất định qua sổ đăng ký có bằng chứng hỗ trợ nhận `1.0` theo quy ước `DETERMINISTIC_SUPPORTED`, sau khi vượt qua điều kiện kiểm tra; không coi đó là độ tin cậy của mạng nơ-ron. Xác định lần xảy ra từ Event chuẩn có sẵn không thay thế bằng chứng hỗ trợ bộ gán hiện tại.

Mỗi vai trò bắt buộc trong từ điển phải có mục trong bản kê quyết định, dù được sinh bằng mạng nơ-ron hay tất định. Không có bộ sinh cho vai trò bắt buộc thì bộ gán chưa được hỗ trợ, không bỏ vai trò đó khỏi phép lấy giá trị nhỏ nhất. Nếu định danh/đối sánh còn mơ hồ phải HOLD, không cấp 1.0 để hoàn tất bản kê.

### 3.4. Điểm bộ gán

```text
assignmentScore = min(
    eventTypeScore,
    mọi requiredRoleScore,
    mọi decisionScore của quyết định nơ-ron bắt buộc về thể hiện/từ kích hoạt/liên kết nếu có
)
```

Vai trò tùy chọn không tham gia A. Thực thể tùy chọn được dùng làm điểm vào tuyến vẫn bắt buộc có Evidence/quyết định liên kết và mức hỗ trợ quan hệ cho tuyến đó. Thiếu bất cứ điểm nơ-ron bắt buộc nào là lỗi của bộ sinh; V1 không dùng giá trị trích xuất thay thế 0.5. Mọi điểm phải hữu hạn, trong [0,1]; không cắt ngưỡng sai số đầu vào để che lỗi.

## 4. Chọn Evidence và extractionConfidence

1. Khóa `inferenceCutoff = Event.availableAt`, là thời điểm sẵn có sớm nhất của Evidence hỗ trợ theo EVENT_SCHEMA.md. Không dời thời điểm chốt để chờ trích xuất đầy đủ.
2. Lập tập Evidence hỗ trợ cùng Event chuẩn, sẵn có không muộn hơn thời điểm chốt, có một bộ gán đầy đủ đã vượt qua các điều kiện kiểm tra và đồng thuận với ảnh chụp trạng thái vai trò đã chuẩn hóa/định danh.
3. Tính assignmentScore cho từng bộ gán; không ghép vai trò, cửa sổ hoặc Evidence chưa đầy đủ để tạo bộ gán đầy đủ.
4. Một Evidence có nhiều bộ gán đầy đủ tương đương: chọn theo assignmentScore giảm dần, assignmentId tăng dần theo thứ tự mã Unicode có phân biệt chữ hoa/chữ thường.
5. Trong tập Evidence hợp lệ, chọn assignmentScore cao nhất; khi bằng điểm, chọn theo URI của Evidence tăng dần theo cùng quy tắc.
6. Gán `A = extractionConfidence = assignmentScore đã chọn`.
7. Cố định Evidence và các bộ gán đủ điều kiện/đã chọn cùng quyết định lựa chọn. Không chọn lại Evidence để cứu tuyến hoặc nâng điểm liên kết.

Nếu không có Evidence đầy đủ tại thời điểm chốt: `NO_COMPLETE_EVIDENCE_AT_CUTOFF`, không tạo Candidate. Các bộ gán mâu thuẫn không được dùng điểm để tự hợp nhất thành một khẳng định; giữ riêng các khẳng định/HOLD theo chính sách định danh. Báo cáo đến sau thời điểm chốt không thay đổi ảnh chụp trạng thái.

Suy luận qua nhiều cửa sổ giữ bộ gán riêng cho từng cửa sổ; không ghép các mảnh vai trò giữa các cửa sổ trong bộ chuyển đổi tham chiếu. assignmentId ổn định phải dựa trên định danh/vị trí của đầu ra đã cố định, không dùng số ngẫu nhiên hoặc thứ tự thực thi. Các trường tùy chọn khác nhau vẫn phải cố định chính xác bộ gán đã chọn.

## 5. Độ tin cậy của nguồn

```text
NewsSource.reliabilityScore = 0.5
S = sourceConfidence = 0.5
```

Áp dụng đồng nhất cho nguồn tham gia V1. Evidence đã chọn phải có thông tin nguồn gốc Article/Source. Không tăng điểm theo số bài, số nguồn, bài đăng lại hoặc điểm nguồn lớn nhất. Đánh giá/xếp hạng nguồn là phần mở rộng khác, không thuộc V1.

## 6. Độ tin cậy của liên kết thực thể

### 6.1. Quy tắc xác định thực thể

Chỉ chấp nhận khớp chính xác mã định danh chuẩn, tên chuẩn đã chuẩn hóa hoặc bí danh đã chuẩn hóa được đăng ký. Phải đúng kiểu thực thể, đúng phạm vi/thời gian và xác định duy nhất tại thời điểm chốt. Chuẩn hóa theo sổ đăng ký/từ điển có phiên bản; không đối sánh gần đúng hoặc đoán từ mã giao dịch để tự đồng nhất Company với Stock.

Nếu nhiều khóa khớp cùng xác định tới cùng một thực thể có kiểu, đây vẫn là một quyết định duy nhất. Nếu xác định tới nhiều ID thực thể hoặc các khóa mâu thuẫn, HOLD; không chọn kết quả khớp có vẻ tốt nhất bằng thứ tự tên.

```text
linkDecisionScore = 1.0 cho mỗi quyết định xác định thực thể đạt quy tắc
L = linkingConfidence = min(tất cả linkDecisionScores bắt buộc của tuyến)
```

`1.0` là quy ước cho trường hợp được xác định qua sổ đăng ký, không phải độ chính xác thực tế 100%. Sổ đăng ký phải được đánh giá riêng. Chỉ khớp gần đúng, mơ hồ, thiếu ánh xạ hoặc ánh xạ từ tương lai => HOLD/loại tuyến; không dùng 0.5/0.7/0.8 để cứu liên kết.

### 6.2. Đầu vào liên kết theo tuyến

`E` là các liên kết của tất cả vai trò thực thể bắt buộc theo từ điển từ bộ gán đã chọn, kể cả thực thể ngoài đường đi; thêm điểm vào tuyến tùy chọn nếu tuyến sử dụng. Giá trị nguyên thủy/ngày/ID tài liệu không phải liên kết thực thể. `M` là ánh xạ Company–Stock ở cuối tuyến, đúng Company và Stock của Candidate.

| Tuyến | Đầu vào liên kết bắt buộc |
| --- | --- |
| DIRECT | E; điểm vào Company đã chọn; M ở cuối tuyến |
| INDIRECT_SUBSIDIARY | E; Company con đã chọn; các ánh xạ định danh đầu mút con/mẹ của SubsidiaryRelation đã chọn; M ở cuối tuyến của công ty mẹ |
| INDIRECT_LEADERSHIP | E; CorporateLeader đã chọn; các ánh xạ định danh đầu mút lãnh đạo/công ty của LeadershipPosition đã chọn; M ở cuối tuyến của công ty thuộc vị trí lãnh đạo |
| INDIRECT_INDUSTRY | E; Industry đã chọn; các ánh xạ định danh đầu mút ngành/Bank của IndustryExposure đã chọn; M ở cuối tuyến của Bank |

Công ty mẹ/Bank/công ty thuộc vị trí lãnh đạo được suy ra theo tuyến không cần được nhắc tới trong bài; định danh phải đến từ các dữ kiện có kiểu đủ điều kiện/sổ đăng ký. Không lấy liên kết từ Evidence khác. Một quyết định xuất hiện nhiều lần chỉ ghi một ID quyết định, không tạo thêm bằng chứng độc lập.

## 7. Độ tin cậy của quan hệ

### 7.1. Điểm hỗ trợ cho mỗi cạnh/dữ kiện

| Nguồn xác lập mức hỗ trợ | Điều kiện | edgeSupportScore |
| --- | --- | --- |
| CURATED_STRUCTURED | Dữ kiện đã được kiểm duyệt trong sổ đăng ký/tập dữ liệu có cấu trúc, có thông tin nguồn gốc, phiên bản và tính đủ điều kiện/hiệu lực | 1.0 |
| AUTOMATIC_EVIDENCED | Dữ kiện suy ra tự động, có Evidence, vượt qua kiểm tra hợp lệ, chưa được hiệu chuẩn/kiểm duyệt | 0.5 |
| Thiếu/không được hỗ trợ/không đủ điều kiện | Không đủ dữ kiện, thông tin nguồn gốc, đầu mút hoặc điều kiện thời gian | Không chấm; loại đường đi |

Có cấu trúc dữ liệu không đồng nghĩa đã được kiểm duyệt. Nhập đầu ra tự động vào sổ đăng ký không tự nâng 0.5 lên 1.0. Dữ kiện đã được kiểm duyệt phải có bản ghi/phiên bản kiểm duyệt và thời điểm sẵn có không sau thời điểm chốt; việc rà soát diễn ra sau thời điểm chốt không nâng điểm lịch sử. V1 không dùng giá trị relationConfidence của phiên bản cũ khác hai mức này; giữ giá trị thô của phiên bản cũ trong hồ sơ kiểm toán, nhưng tính điểm hiện hành theo nguồn xác lập mức hỗ trợ V1.

Mức hỗ trợ Event–Company/Event–Leader/Event–Industry của bộ trích xuất tự động dùng 0.5 khi được Evidence đã chọn hỗ trợ. Không sao chép A hoặc điểm bộ liên kết Company sang điểm quan hệ. Dữ liệu mẫu cố định đã được kiểm duyệt không biến lượt trích xuất tự động thành mức hỗ trợ đã được kiểm duyệt. Điểm vào tuyến tùy chọn phải có khẳng định hỗ trợ tường minh và được gắn đúng đối tượng; chỉ có nhắc tới trong văn bản là chưa đủ.

### 7.2. Tổng hợp đường đi

```text
R = relationConfidence = min(mọi edgeSupportScore bắt buộc trên đường đi)
```

| Tuyến | Đầu vào hỗ trợ quan hệ bắt buộc |
| --- | --- |
| DIRECT | Mức hỗ trợ Event–Company; mức hỗ trợ ánh xạ Company–Stock |
| INDIRECT_SUBSIDIARY | Mức hỗ trợ Event–công ty con; mức hỗ trợ dữ kiện nghiệp vụ SubsidiaryRelation đã chọn; mức hỗ trợ ánh xạ cuối tuyến của công ty mẹ |
| INDIRECT_LEADERSHIP | Mức hỗ trợ Event–Leader; mức hỗ trợ dữ kiện nghiệp vụ LeadershipPosition đã chọn; mức hỗ trợ ánh xạ cuối tuyến của công ty thuộc vị trí lãnh đạo |
| INDIRECT_INDUSTRY | Mức hỗ trợ Event–Industry; mức hỗ trợ dữ kiện nghiệp vụ IndustryExposure đã chọn; mức hỗ trợ ánh xạ cuối tuyến của Bank |

Các quyết định định danh đầu mút được kiểm tra ở điều kiện liên kết; các liên kết đầu mút/quyền sở hữu được khẳng định phải có thông tin nguồn gốc và là một phần của kiểm tra hợp lệ dữ kiện quan hệ tương ứng. Ánh xạ định danh đã được kiểm duyệt không tự chứng minh quan hệ kinh tế đã được kiểm duyệt. Không lấy giá trị nhỏ nhất trên các dữ kiện sổ đăng ký không liên quan hoặc lấy điểm quan hệ lớn nhất từ các dữ kiện không được chọn.

## 8. Cường độ quan hệ

```text
T = relationStrength = 1.0 cho mọi tuyến đủ điều kiện
```

| impactType | relationStrength của V1 |
| --- | --- |
| DIRECT | 1.0 |
| INDIRECT_INDUSTRY | 1.0 |
| INDIRECT_SUBSIDIARY | 1.0 |
| INDIRECT_LEADERSHIP | 1.0 |

V1 chưa đo mức độ phơi nhiễm kinh tế/độ lớn tác động theo đường đi và không phân biệt cường độ DIRECT/INDIRECT. Hằng số 1.0 là yếu tố kiểm soát thực nghiệm, không phải tuyên bố các quan hệ có tác động thực tế như nhau. Dữ kiện phơi nhiễm vẫn cần đủ trường và đúng quy tắc lựa chọn để tuyến hợp lệ; không bịa mức độ phơi nhiễm khi cường độ cố định. Các biến thể cường độ theo mức độ phơi nhiễm hoặc suy giảm cần phương pháp/cấu hình/quy trình riêng, không âm thầm dùng trong V1.

## 9. Thứ tự thực thi và hồ sơ kiểm toán bất biến

```text
kiểm tra tính đủ điều kiện tại thời điểm chốt
→ kiểm tra hợp lệ/chấm điểm các bộ gán trích xuất đầy đủ
→ chọn bộ gán Evidence một lần
→ xác định các liên kết thực thể bắt buộc
→ chọn dữ kiện theo thời gian và các tuyến đủ điều kiện
→ gán nguồn xác lập/điểm hỗ trợ cạnh
→ S, A, L, R, T
→ confidenceScore
→ candidateScore
→ ảnh chụp trạng thái Candidate bất biến
→ cửa sổ thị trường đã hoàn tất
→ Reaction
```

### 9.1. Bản ghi kiểm toán bắt buộc

Lưu ngoài RDF trong tệp kèm JSON/JSONL bất biến; không mặc nhiên thêm thuộc tính/lớp vào ontology. Candidate trong RDF giữ các thành phần hiện có, thời điểm chốt và methodVersion. ID của Candidate phải truy tới đúng bản ghi kiểm toán/mã băm trong bản kê lượt chạy.

- Định danh: candidateId, eventId, canonicalKey, stockId, impactType, relationPath, assignmentId đã chọn.
- Phiên bản: documentVersion, methodVersion, adapterVersion, mã băm mô hình/bản lưu mô hình, các đầu tác vụ, bộ tách token, phân đoạn, bộ giải mã, từ vựng nhãn, từ điển, bộ chuẩn hóa, sổ đăng ký, dữ kiện theo thời gian, ontology/shape, mã băm cấu hình.
- Thời gian: Event.availableAt, inferenceCutoff, generatedAt, chế độ thời điểm sẵn có quan sát được/đại diện; các thời điểm có thông tin múi giờ; ID ảnh chụp trạng thái/lượt chạy.
- Bằng chứng: các ID Article/Source nguồn, văn bản nguồn/mã băm, các ID Evidence đủ điều kiện, URI đã chọn, vị trí, giá trị vai trò, giá trị đã chuẩn hóa, các ID bộ gán đủ điều kiện/đã chọn, khóa sắp xếp lựa chọn, mã lý do loại trừ.
- Quyết định của mô hình: decisionId, vai trò/kiểu/thể hiện, nhãn đã chọn, toàn bộ logits hữu hạn hoặc toàn bộ vectơ điểm được lưu không mất mát, các ID token, ánh xạ vị trí, token/nhãn đã chọn, hàm kích hoạt, decisionScore và cách tổng hợp. Lưu điểm để tái lập phép tính không có nghĩa chạy lại suy luận trên GPU sẽ cho đầu ra giống từng bit.
- Quyết định tất định: bộ sinh vai trò, đoạn/ID sổ đăng ký hỗ trợ, quy tắc chuẩn hóa/định danh, kết quả, cờ quy ước.
- Liên kết: tập quyết định bắt buộc E và M, chế độ đối sánh, khóa đã chuẩn hóa, các ID thực thể ứng viên khớp, ID có kiểu đã chọn, thời điểm sẵn có/phiên bản, điểm quyết định.
- Quan hệ: dữ kiện/khóa nghiệp vụ/phiên bản đã chọn, các đầu mút, quyết định về thời điểm sẵn có/hiệu lực, bản ghi kiểm duyệt/nguồn gốc, nguồn xác lập mức hỗ trợ, điểm thô của phiên bản cũ nếu có, edgeSupportScore hiện hành.
- Điểm: S/A/L/R/T gốc, confidenceScore, candidateScore, các hằng số, chính sách chuyển đổi/làm tròn số, thiết lập loại bỏ ảnh hưởng từng thành phần.
- Cố định dữ liệu: mã băm nội dung của đúng các đầu vào và bản ghi kiểm toán; mọi sửa chữa tạo ảnh chụp trạng thái/phiên bản riêng, không bao giờ ghi đè.

### 9.2. Quy tắc tính toán số

Tính hàm kích hoạt và truy xuất điểm mô hình bằng float64; từ chối logits/điểm không hữu hạn. Chuyển từng điểm quyết định nơ-ron cuối cùng sang Decimal thông qua chuỗi thập phân cho phép chuyển đổi khứ hồi không mất giá trị. Tổng hợp bằng phép lấy giá trị nhỏ nhất, cộng, chia và nhân với Decimal có độ chính xác 50, ROUND_HALF_EVEN. Tuần tự hóa số thập phân thành chuỗi biểu diễn số, không làm tròn để hiển thị. Xếp hạng dùng candidateScore đã lưu với đầy đủ độ chính xác, không dùng giá trị làm tròn trên giao diện. Tái lập từ các điểm quyết định đã cố định phải tái tạo chính xác các giá trị điểm đã tuần tự hóa; các phép so sánh số học RDF/SHACL độc lập dùng dung sai tuyệt đối 1e-9.

Không cắt ngưỡng đầu vào ngoài miền giá trị. Làm tròn để hiển thị chỉ áp dụng cho đầu ra và không được dùng để chọn Evidence/đường đi. Giữ cố định các đầu vào đã chấm điểm khi chạy lại phép tổng hợp; huấn luyện lại mô hình không phải tái lập phép tính.

## 10. Điểm tại thời điểm phản ứng (giữ công thức hiện hành)

Chỉ tính sau khi toàn bộ cửa sổ sự kiện đã cấu hình đóng và mọi quan sát cần thiết đã sẵn có, bao gồm phiên ngay trước phiên đầu tiên trong cửa sổ.

```text
R(i,t) = adjustedClose(i,t) / adjustedClose(i,t-1) - 1
AR(i,t) = R(i,t) - R(m,t)
CAR(i,[a,b]) = sum(AR(i,t), t thuộc mọi phiên giao dịch [a,b])
impactScore = min(1, abs(CAR) / tau)
reactionWeight = impactScore * frozenCandidate.confidenceScore * frozenCandidate.relationStrength
signedWeight = reactionWeight * sign(CAR)
```

Khóa `tau=0.10`, `epsilon=0`; marketReactionDirection theo đúng dấu của CAR. Reaction dùng các thành phần Candidate V1 đã cố định; không tính lại A/R/T từ dữ liệu mới. R(i,t) trong mục này là lợi suất tài sản, không phải ký hiệu R của relationConfidence ở mục 1.

`adjustedClose` > 0 là nguồn chuẩn cho Stock và chỉ số tham chiếu; `returnValue` là giá trị lưu đệm phải tính lại và khớp với dung sai tuyệt đối 1e-9. Cửa sổ `[a,b]` liên kết một quan sát mỗi tài sản/phiên cho `t_(a-1), t_a, ..., t_b`. Tài sản phải thuộc đúng Stock của Candidate/chỉ số tham chiếu của Reaction; các tập ngày phải giống nhau, không trùng lặp, đủ các phiên liên tiếp của sở giao dịch.

Các cửa sổ được hỗ trợ `[0,0]`, `[0,+1]`, `[0,+3]`, `[-1,+1]` đều chứa 0. `abnormalReturn=AR(i,0)`; `cumulativeAbnormalReturn` là tổng AR cho toàn cửa sổ, bao gồm cả hai đầu mút. Không dùng CAR của cửa sổ chưa đầy đủ làm kết quả cuối. `[-1,+1]` dùng để kiểm tra độ vững hồi cứu, không cung cấp đầu vào xếp hạng Candidate.

Bản kê lượt chạy lưu ảnh chụp trạng thái nhà cung cấp/tập dữ liệu, quy ước giá điều chỉnh/hành động doanh nghiệp, chỉ số tham chiếu, sở giao dịch và phiên bản/mã băm lịch. Bộ kiểm tra hợp lệ có xét lịch kiểm tra chính xác các phiên; vượt qua kiểm tra số học SHACL không chứng minh độ bao phủ đúng lịch. Các quan sát Reaction có availableAt <= Reaction.availableAt, không bắt buộc <= thời điểm chốt của Candidate.

## 11. Chống rò rỉ dữ liệu và lựa chọn theo thời gian

- `inferenceCutoff = Event.availableAt` chính xác; chỉ dùng đầu vào có availableAt <= thời điểm chốt. generatedAt của lượt tái lập muộn hơn không cho phép dùng đầu vào từ tương lai.
- Thời điểm sẵn có sớm nhất thiếu bộ gán đầy đủ => không có Candidate cơ sở, ghi nhận trường hợp thiếu bao phủ; không đẩy thời điểm chốt tới bài sau hoặc bỏ các trường hợp dương tính chuẩn mà hệ thống bỏ sót khỏi tập đánh giá.
- LeadershipPosition/SubsidiaryRelation/IndexMembership chọn phiên bản mới nhất sẵn có tại thời điểm chốt theo khóa nghiệp vụ rồi mới kiểm tra hiệu lực bao gồm cả hai đầu mút tại ngày địa phương của thời điểm chốt; không quay về phiên bản cũ không có ngày kết thúc.
- IndustryExposure chọn theo phạm vi cố định và quy tắc YEAR/kỳ mới nhất, giới hạn độ cũ 365 ngày bao gồm cả mốc giới hạn, cách phân xử theo thời điểm sẵn có/URI của EVENT_SCHEMA.md; không lan truyền tới toàn ngành.
- Các dấu thời gian có thông tin múi giờ; so sánh theo UTC, suy ra ngày địa phương theo Asia/Ho_Chi_Minh. Khi thiếu thời điểm thu nhận, chỉ được dùng chế độ đại diện đã khai báo, không giả thành thời điểm sẵn có lịch sử đã quan sát được.
- Ngày 0 là phiên đầu tiên của sở giao dịch có Event.availableAt < session.open với bất đẳng thức nghiêm ngặt; bằng thời điểm mở cửa thì chuyển sang phiên tiếp theo. Không dùng phép tính theo thứ trong tuần thay lịch sở giao dịch.
- Evidence đến muộn không sửa Event/thời điểm chốt/ngày 0 hoặc Candidate lịch sử. Khẳng định mới có nội dung thực chất có Event riêng; các sửa chữa/tái dựng phải có phiên bản riêng.
- `reactionWeight`, CAR, lợi suất tương lai, kiểm duyệt trong tương lai hoặc nhãn chuẩn không dùng để chọn Evidence, tính Candidate hoặc tinh chỉnh trên tập kiểm thử giữ riêng.

## 12. Tổng hợp nhiều đường đi và xếp hạng

Chấm từng đường đi đủ điều kiện riêng. Nhóm theo đúng phương pháp/cấu hình, thời điểm chốt và `(Event, Stock)`:

```text
stockRankingScore = max(candidateScore của các đường đi đủ điều kiện)
```

Khi bằng điểm, chọn đường đi đại diện theo URI của Candidate tăng dần; xếp hạng Stock theo điểm giảm dần rồi URI của Stock tăng dần. Thứ tự URI theo mã Unicode có phân biệt chữ hoa/chữ thường, không theo quy tắc đối chiếu của ngôn ngữ địa phương. Không cộng/lấy trung bình nhiều đường đi hoặc bài viết. CAR không cộng qua các đường đi trùng lặp; các đường đi không phải sự kiện độc lập.

URI của Candidate/ID bộ gán phải được tạo tất định từ định danh ngữ nghĩa đã cố định và phương pháp/cấu hình; không dùng dấu thời gian thực thi/ID ngẫu nhiên để phân xử khi bằng điểm. Không có ngưỡng điểm trong V1; các trường hợp bị từ chối do không đủ điều kiện vẫn được ghi vào sổ theo dõi.

## 13. Đánh giá và các phép loại bỏ ảnh hưởng thành phần của V1

- Giữ tập Event/Stock chung, thời điểm chốt, các đường đi đủ điều kiện và dữ liệu chuẩn được phân xử độc lập; không đánh giá chỉ trên đầu ra được chấp nhận.
- Phương án đối chiếu không trọng số: điểm 1 trên cùng tập đối tượng đủ điều kiện; không thay các điều kiện kiểm tra.
- Xếp hạng có trọng số V1: candidateScore theo tài liệu này.
- Ba biến thể trung hòa thành phần: thay riêng A, L hoặc R bằng 1; giữ cách chọn Evidence/bộ gán/đường đi, điểm cạnh gốc, S=0.5 và T=1.0. Tính lại tổng, dùng methodVersion/URI của Candidate riêng.
- Liên kết đã có giá trị cố định 1 trong V1 nên trung hòa L không thay xếp hạng; phải báo đây là phép loại bỏ ảnh hưởng thành phần không cung cấp thông tin, không tuyên bố đã chứng minh bộ liên kết không quan trọng.
- R có thể cố định 0.5 trong tập đối tượng tự động; nếu không có biến thiên phải báo rõ. Nguồn/cường độ đều cố định, không tuyên bố đã đo độ tin cậy của nguồn hay cường độ kinh tế của đường đi.
- So sánh cường độ theo mức độ phơi nhiễm của 1.0.4 không thuộc V1 hiện hành. Cần giữ dưới phương pháp cũ riêng hoặc định nghĩa biến thể mới và đồng bộ quy trình trước khi chạy.
- Báo tính đúng đắn của ED/EAE, lỗi đối số/định danh/liên kết/đường đi, độ bao phủ/các trường hợp từ chối và mối liên hệ giữa điểm với tính đúng đắn trên dữ liệu chuẩn. Không dùng việc vượt qua SHACL thay cho chất lượng ngữ nghĩa hoặc gọi phép lấy giá trị nhỏ nhất/trung bình là xác suất đã được hiệu chuẩn.
- Khóa mọi công thức, bộ chuyển đổi, phiên bản nhãn/từ vựng và lựa chọn/cấu hình trước kiểm thử cuối cùng. Thay đổi hiệu chuẩn/chấm điểm tạo phương pháp mới, chọn trên tập phát triển/xác thực.

## 14. Danh sách kiểm tra nghiệm thu phần triển khai

1. Cùng đầu vào/phiên bản đã cố định => cùng lựa chọn, thành phần, xếp hạng và điểm đã tuần tự hóa.
2. Thiếu vai trò/định danh bắt buộc, vị trí không hợp lệ, liên kết mơ hồ hoặc dữ kiện chưa sẵn có => không có Candidate/đường đi tương ứng, có mã lý do.
3. Điểm nơ-ron không hợp lệ => lỗi của bộ sinh; không dùng giá trị trích xuất thay thế hoặc cắt ngưỡng.
4. Chọn bộ gán đầy đủ theo điểm lớn nhất và phân xử bằng URI/ID bộ gán; không trộn vai trò/Evidence/cửa sổ hoặc chọn lại để cứu tuyến.
5. Liên kết được chấp nhận => đúng thực thể có kiểu được khớp chính xác/thông tin nguồn gốc từ sổ đăng ký và L=1.0.
6. Nguồn xác lập cạnh => đúng 1.0/0.5; thiếu dữ kiện thì loại đường đi; không dùng lại điểm bộ liên kết/A làm độ tin cậy quan hệ.
7. S=0.5, T=1.0 cho cả bốn tuyến; tổng và candidateScore đúng công thức.
8. Bài đăng lại/nhiều đường đi không cộng điểm; nhóm và phân xử khi bằng điểm theo cách tất định.
9. Hồ sơ kiểm toán đủ để tái lập không cần sổ đăng ký hiện tại có thể thay đổi; đầu vào đến muộn không sửa các ảnh chụp trạng thái.
10. Reaction có đủ phiên, đúng chỉ số tham chiếu, thông tin nguồn gốc adjustedClose, tau/epsilon và giá trị Candidate đã cố định; không có kết quả từ cửa sổ chưa đầy đủ.
11. Đầu ra tự động/ASSISTED và V1/phiên bản cũ được tách; báo độ bao phủ và các phép loại bỏ ảnh hưởng thành phần có giá trị cố định/không cung cấp thông tin đúng thực tế.
12. Trước nghiệm thu toàn bộ: đối chiếu EVENT_SCHEMA, TTL/SHACL, hướng dẫn gán nhãn/quy trình đánh giá, bản trình diễn và sơ đồ/báo cáo; chạy kiểm thử trên đúng phương pháp/shape/cấu hình. Việc hoàn tất tài liệu này không có nghĩa các sản phẩm đó hoặc phần triển khai đã được cập nhật.
