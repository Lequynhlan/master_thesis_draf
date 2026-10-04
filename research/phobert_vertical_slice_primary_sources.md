# PhoBERT cho vertical slice trích xuất sự kiện tài chính tiếng Việt

## Kết luận

**PhoBERT phù hợp làm encoder ứng viên cho một thử nghiệm có giám sát nhỏ, nhưng không phải bộ phát hiện sự kiện/trích xuất tham số dùng ngay.** Bằng chứng trực tiếp: bài PhoBERT đánh giá POS, dependency parsing, NER và NLI, không đánh giá sự kiện tài chính [1]; bài BKEE thực sự dùng PhoBERT làm encoder trong mô hình event detection (ED) và event argument extraction (EAE), với head riêng và fine-tuning [4, §3]. Điều này hỗ trợ tính khả thi kỹ thuật, **không chứng minh chất lượng trên ontology, nguồn tin hay miền tài chính của WFKG**. Ghi chú này không đọc/diễn giải lại đặc tả WFKG và không tải trọng số, huấn luyện hoặc chạy mô hình.

## 1. Encoder tiền huấn luyện ≠ mô hình tác vụ

- `vinai/phobert-base` được tiền huấn luyện theo RoBERTa trên văn bản Wikipedia và tin tức; README chính thức nêu 135M tham số, giới hạn đầu vào 256 token và giấy phép MIT [1–3]. Cấu hình checkpoint khai báo `RobertaForMaskedLM`, không có head hay hệ nhãn sự kiện tài chính [3]. `AutoModel` trong ví dụ chính thức trả về **features**, không trả về sự kiện/role/confidence có ý nghĩa nghiệp vụ [2].
- Cần huấn luyện head nhận diện trigger + loại sự kiện (ví dụ BIO/token hoặc span classification), và head dự đoán span/role của tham số có điều kiện theo từng sự kiện. NER đơn thuần không quyết định được tổ chức nào là bên mua/bên bán, hay con số nào thuộc sự kiện nào. BKEE dùng biểu diễn trigger–entity và feed-forward network cho role; encoder cũng được fine-tune [4, §3.1–3.2]. Chỉ khởi tạo head mới rồi gọi inference không tạo ra năng lực đã học.
- Đối với slice nhỏ, ưu tiên phạm vi một vài loại sự kiện có định nghĩa rõ, trong câu/đoạn ngắn; dùng `base` là lựa chọn thử nghiệm hợp lý, không phải kết luận rằng nó tốt hơn `large`. Cross-sentence linking, chuẩn hóa doanh nghiệp/mã cổ phiếu, tiền tệ/thời gian và hợp nhất sự kiện cần xử lý riêng, không mặc nhiên do PhoBERT giải quyết.

## 2. Dữ liệu gold và phép đo cần có

**Khuyến nghị thiết kế, chưa phải kết quả thực nghiệm:** chốt ontology và guideline trước; gán nhãn trigger span, loại sự kiện, argument span, role và liên kết argument→event trên văn bản gốc. Có câu âm tính, nhiều sự kiện/cùng thực thể, phủ định, dự kiến/chưa xảy ra và số liệu dễ nhầm. Nhãn thiếu phải phân biệt với nhãn “không có”. Rà soát chéo và phân xử bất đồng trên một phần dữ liệu.

Tách train/dev/test theo bài và, khi có thể, nhóm các bài cùng sự kiện vào cùng split để tránh rò rỉ; không dùng test để chọn threshold. Không có căn cứ từ các nguồn dưới đây để ấn định số mẫu đủ cho miền tài chính: phải báo số mẫu/nhãn, độ phủ và learning curve thực tế. Gold test của miền đích vẫn cần dù dùng dữ liệu silver hoặc pretrained checkpoint.

Báo precision/recall/F1 cho **trigger+type** và **argument span+role gắn đúng event**; tách EAE với gold trigger/entity (oracle) khỏi end-to-end với đầu vào dự đoán. BKEE huấn luyện EAE bằng gold mentions nhưng đánh giá pipeline bằng mentions dự đoán [4, §3.2]—không được đánh đồng hai chế độ. Với ít nhãn nên báo support từng loại và độ bất định, so sánh rule baseline trên cùng test, không hứa F1.

## 3. Tách từ, subword và offset bằng chứng

PhoBERT yêu cầu đầu vào **đã tách từ**; VinAI khuyến nghị RDRSegmenter/VnCoreNLP như tiền huấn luyện, bao gồm chuẩn hóa dấu và tách câu/từ [2]. BKEE cũng dùng VnCoreNLP và kiểm tra thủ công [4]. Tách từ kiểu `Nguyễn_Khắc_Chúc`, thay whitespace, chuẩn hóa Unicode/dấu rồi BPE khiến vị trí token **không phải** offset trên bản tin gốc.

Cần giữ văn bản gốc bất biến và ánh xạ có kiểm chứng `original char span ↔ normalized/segmented word ↔ subword`; quy định chỉ số ký tự và khoảng `[start,end)`, kiểm tra lại substring bằng chứng. Không dùng tìm chuỗi lần đầu để phục hồi offset khi tên/số lặp lại. README chính thức mô tả tokenizer chậm và nhánh fast tokenizer riêng [2]; không được giả định `return_offsets_mapping` luôn có hay ánh xạ thẳng về raw text. Với giới hạn 256 token, phải ghi nhận chunk/truncation và bảo đảm trigger–argument không bị cắt; số token BPE không phải số từ.

## 4. Score, calibration và fallback cố định 0,5

Logit là điểm thô; softmax/sigmoid tạo score theo head nhưng **không tự bảo đảm xác suất đúng đã hiệu chỉnh**. Nghiên cứu calibration gốc chỉ ra neural classifiers có thể lệch calibration, và đề xuất temperature scaling [7]; không chứng minh PhoBERT tài chính đã calibrated. Cần gold held-out riêng hoặc phân hoạch dev phù hợp để fit/check calibration; báo reliability, Brier/ECE cùng cách tính và support, không diễn giải ECE nhỏ trên ít mẫu như bảo đảm. Score token/role không tự bằng độ tin cậy toàn bộ event; công thức gộp phải minh bạch.

Nếu mọi candidate đều nhận fallback `0.5`, đó là **placeholder/unknown**, không phải chứng cứ mô hình. Với lọc `score >= threshold`: threshold ≤ 0.5 nhận tất cả candidate, threshold > 0.5 loại tất cả; thứ hạng cũng toàn hòa. Vì vậy sweep threshold không còn kiểm tra khả năng phân biệt. Nếu đo nhị phân trên cùng tập candidate với cả hai lớp gold, constant score cho ROC-AUC 0.5 theo quy ước xử lý hòa; nếu gold chỉ một lớp thì ROC-AUC không xác định. F1 vẫn có thể khác 0 nhờ generator/rule, nhưng không chứng minh hiệu quả score/PhoBERT. Khuyến nghị lưu `score_status=unavailable`/null và provenance fallback; đánh giá extraction riêng, không trộn score giả vào phép đo calibration. Đây là phân tích điều kiện, không phải khẳng định hệ thống hiện tại dùng comparator nào.

## 5. Nguồn EE tiếng Việt có thể tái sử dụng, và giới hạn

- **BKEE (2024)**: bài gốc ghi 1.066 tài liệu, 8 loại lớn/33 loại con, 28 role, đa miền tin tức; có nhóm Business như Start-Org, Merge-Org, Declare-Bankruptcy, End-Org [4, §2]. Repo của nhóm tác giả có `data.gz`, thư mục `processed` và công bố CC BY-NC 4.0 [5]. Phù hợp tham khảo schema/guideline/baseline và khả năng chuyển giao; không thể coi nhãn BKEE là ontology tài chính đích. Không kiểm định toàn bộ dataset trong nhiệm vụ này; README có ví dụ `pieces` khác định dạng BPE PhoBERT, cần tokenize/alignment lại thay vì tái dùng mù quáng.
- **VietEE2 / EEUCA 2026**: bài gốc xây corpus **silver** bằng pseudo-labeling và lọc quan hệ n-ary xuyên tài liệu, đánh giá trên BKEE [6]. Repo được truy cập, README mô tả JSONL và các phiên bản enrichment; listing `final_data/processed` kiểm tra được có train/dev, không đủ để xác nhận mọi split hay giấy phép dữ liệu. Có thể tham khảo weak supervision, nhưng silver không thay thế gold test miền tài chính và có thể kế thừa sai lệch bộ gán nhãn.

## Nguồn sơ cấp đã truy cập

1. Nguyen & Nguyen (2020), *PhoBERT: Pre-trained language models for Vietnamese*: https://aclanthology.org/2020.findings-emnlp.92/ ; PDF đã đọc: https://aclanthology.org/2020.findings-emnlp.92.pdf
2. VinAI, repo/README chính thức: https://github.com/VinAIResearch/PhoBERT ; raw: https://raw.githubusercontent.com/VinAIResearch/PhoBERT/master/README.md
3. VinAI, model card và config `phobert-base`: https://huggingface.co/vinai/phobert-base ; https://huggingface.co/vinai/phobert-base/raw/main/README.md ; https://huggingface.co/vinai/phobert-base/raw/main/config.json
4. Nguyen et al. (2024), *BKEE: Pioneering Event Extraction in the Vietnamese Language*: https://aclanthology.org/2024.lrec-main.217/ ; PDF đã đọc: https://aclanthology.org/2024.lrec-main.217.pdf ; trang nhà xuất bản: https://doi.org/10.63317/3nw5gx8fnhu8
5. BKEE, repo công bố: https://github.com/nhungnt7/BKEE ; README đã đọc: https://raw.githubusercontent.com/nhungnt7/BKEE/main/README.md
6. Hiệu et al. (2026), *Constructing a Silver Corpus for Weakly Supervised Vietnamese Event Extraction using Cross-Document N-ary Relation Filtering*: https://aclanthology.org/2026.eeuca-1.4/ ; PDF đã đọc: https://aclanthology.org/2026.eeuca-1.4.pdf ; dataset repo: https://github.com/Larken1612/VietEE2
7. Guo et al. (2017), *On Calibration of Modern Neural Networks*, bài gốc/abstract: https://proceedings.mlr.press/v70/guo17a.html

**Giới hạn khảo sát:** không phải systematic review; tìm kiếm dùng OpenAlex/GitHub để khám phá nhưng các kết luận dựa trên nguồn sơ cấp trên. Host PDF cũ `www.lrec-conf.org` từ chối kết nối; đã đọc bản BKEE tại ACL thay thế. Chưa xác nhận một checkpoint sẵn có chuyên financial ED/EAE khớp schema đích; không suy ra rằng checkpoint/dataset như vậy không tồn tại. Không có số hiệu năng miền đích, kết quả chạy mô hình hay cam kết triển khai trong ghi chú này.
