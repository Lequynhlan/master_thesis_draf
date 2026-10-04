# PhoBERT có phù hợp với WFKG không?

## Kết luận ngắn

**Có, nếu dùng làm encoder tiếng Việt cho một bộ trích xuất có giám sát hoặc baseline NLP; không phải bản thay thế trực tiếp cho LLM chấm rubric.** Với phạm vi luận văn hiện tại (ontology, trích xuất tin tức, EventStock và so sánh ontology RAG với vector RAG), nên hoàn thành một lát cắt end-to-end bằng LLM trước; chỉ thêm PhoBERT khi có dữ liệu gán nhãn và ngân sách đánh giá. Đây là khuyến nghị về phạm vi, không phải kết quả thực nghiệm.

## 1. Encoder khác với LLM chấm rubric

PhoBERT là mô hình theo kiến trúc BERT/RoBERTa, cung cấp biểu diễn ngữ cảnh; paper dùng thêm tầng dự đoán và fine-tune riêng cho các tác vụ. NER trong paper được thực hiện bằng tầng tuyến tính trên biểu diễn subword đầu của từng từ, không phải bằng prompt trò chuyện. [1, §2–3; 2]

Vì vậy, checkpoint PhoBERT tiền huấn luyện **không tự đọc danh sách tiêu chí rồi chấm, giải thích và xuất JSON như một LLM instruction-tuned**. Cần phân biệt:

- **Thay extractor:** khả thi nếu xây dựng các đầu dự đoán và dữ liệu tác vụ phù hợp.
- **Thay rubric assessor:** phải chuyển từng tiêu chí thành bài toán phân loại/hồi quy có nhãn và huấn luyện, rồi kiểm định; không phải đổi tên model trong prompt. Những tiêu chí dựa vào nguồn, provenance hay ràng buộc ontology vẫn cần dữ liệu và logic ngoài encoder.

Phần ánh xạ sang WFKG dưới đây là đề xuất thiết kế, không phải các khả năng đã được paper chứng minh.

## 2. PhoBERT có thể nằm ở đâu trong pipeline WFKG?

| Thành phần | Cách dùng encoder có giám sát | Điều kiện và giới hạn |
|---|---|---|
| NER | Đầu token/span classification nhận diện doanh nghiệp, người, địa điểm… | Cần nhãn theo schema WFKG và căn chỉnh span giữa văn bản gốc, từ đã segment và subword. |
| Event | Đầu nhận diện trigger/span và phân loại loại sự kiện | Cần nhãn sự kiện tài chính; không suy ra khả năng này từ kết quả NER. |
| Roles/arguments | Đầu phân loại cặp event–entity/span thành vai trò | Cần gold labels cho vai trò; phải xử lý ngữ cảnh ngoài câu và trường hợp thiếu bằng chứng. |
| Entity/stock linking | Sinh ứng viên bằng danh mục công ty/mã cổ phiếu, rồi dùng đầu phân loại/reranking có giám sát nếu cần | Encoder không chứa sẵn bộ ánh xạ chính xác tới mã chứng khoán; cần xử lý alias, ứng viên sai và trường hợp không liên kết được. Rule/dictionary có thể là baseline, không bắt buộc mọi bước đều học máy. |

**Không cần pre-train lại PhoBERT từ đầu.** Có thể bắt đầu từ checkpoint công bố, huấn luyện đầu tác vụ trên encoder đóng băng hoặc fine-tune encoder cùng đầu dự đoán. Muốn đánh giá một bộ trích xuất có giám sát cho WFKG thì cần tập gold gán nhãn tương ứng, cùng train/validation/test tách biệt. Paper minh họa fine-tuning trên các dataset tác vụ, không cung cấp sẵn bộ extractor tài chính WFKG. [1, §3]

PhoBERT không tự thay thế ontology, provenance, công thức EventStock hoặc cơ chế ontology RAG. Nó chỉ có thể hỗ trợ một số khâu NLP trong pipeline.

## 3. Confidence: phải hiệu chuẩn riêng

Đây là khuyến nghị phương pháp cho WFKG, **không phải kết luận calibration của paper PhoBERT**:

- Softmax cao không tự đồng nghĩa với xác suất dự đoán đúng đã được hiệu chuẩn. Confidence của NER, event, role và linking phải được kiểm tra riêng trên nhãn thật; confidence token cũng không tự là confidence của toàn span/event.
- Nếu cần diễn giải score như xác suất, dùng tập calibration/validation độc lập với tập test, thử phương pháp như temperature scaling khi phù hợp, kiểm tra reliability/ECE hoặc Brier score và chọn ngưỡng chấp nhận/abstain. Sau đó đánh giá lại khi phân phối tin tức thay đổi.
- Không lấy một score của encoder để đại diện đồng thời cho độ đúng của trích xuất, độ tin cậy nguồn, mức đầy đủ bằng chứng và mức phù hợp ontology. Các thành phần này cần định nghĩa và bằng chứng riêng.
- Điểm rubric do LLM tự chấm cũng không mặc nhiên là xác suất calibrated. **Confidence trích xuất khác trọng số tác động EventStock**; cần giữ hai khái niệm tách biệt.

## 4. Segmentation và giới hạn theo phiên bản

README chính thức yêu cầu đầu vào đã **word-segmented**, ví dụ `nghiên_cứu_viên`; với văn bản thô, VinAI khuyến nghị RDRSegmenter của VnCoreNLP, cùng cách tiền xử lý đã dùng khi pre-train. Tokenizer BPE không thay thế bước word segmentation. [2, mục Example usage và Notes; 3]

| Checkpoint | Max length theo tài liệu chính thức | Dữ liệu pre-training |
|---|---|---|
| `vinai/phobert-base` | 256 token | Wikipedia và news, 20GB |
| `vinai/phobert-large` | 256 token | Wikipedia và news, 20GB |
| `vinai/phobert-base-v2` | 256 token | 20GB trên + 120GB OSCAR-2301 |

Bảng checkpoint dựa trên README/model card [2, 3]; paper mô tả giới hạn **256 subword tokens** cho các bản gốc [1, §2]. Không hiểu đây là 256 từ, ký tự hay âm tiết; v2 cũng không tự tăng context length. Khi dùng tokenizer phải tính cả special tokens trong ngân sách đầu vào.

Với bài báo dài, cần chia cửa sổ theo token, ưu tiên ranh giới câu, cân nhắc overlap và hợp nhất kết quả/khử trùng lặp. Không nên cắt cụt im lặng: có thể mất câu chứng cứ, quan hệ event–argument hoặc đồng tham chiếu. Đây là hệ quả thiết kế từ giới hạn context, chưa được kiểm nghiệm trên WFKG.

Ghi chú lựa chọn phiên bản: README nêu base/large dùng MIT, base-v2 dùng AGPLv3; cần kiểm tra nghĩa vụ giấy phép nếu phân phối hoặc triển khai. [2, 3]

## 5. Có thể khẳng định gì từ nguồn?

Paper đánh giá POS tagging, dependency parsing, NER trên benchmark tiếng Việt và NLI; **không đánh giá trích xuất sự kiện tài chính tiếng Việt, vai trò theo ontology WFKG, stock linking, calibration hay EventStock**. [1, §3–4] Có dữ liệu news trong pre-training là lý do hợp lý để cân nhắc baseline, không phải bằng chứng về hiệu năng tài chính.

**Chốt:** dùng PhoBERT là ổn nếu mục tiêu là một extractor/baseline có giám sát và có dữ liệu đánh giá. Nếu mục tiêu hiện tại là chấm một rubric nhiều tiêu chí bằng prompt, PhoBERT không phải drop-in replacement. Chưa có cơ sở từ ba nguồn này để tuyên bố PhoBERT tốt hơn LLM hoặc đạt bất kỳ mức performance nào trên tin tài chính WFKG.

## Nguồn sơ cấp đã truy cập thành công

1. Nguyen & Nguyen (2020), *PhoBERT: Pre-trained language models for Vietnamese*, Findings of EMNLP, tr. 1037–1042. Đã đọc toàn văn PDF: https://aclanthology.org/2020.findings-emnlp.92.pdf — trang bibliographic: https://aclanthology.org/2020.findings-emnlp.92/
2. VinAI Research, README chính thức PhoBERT: https://github.com/VinAIResearch/PhoBERT/blob/master/README.md — đã đọc nội dung raw: https://raw.githubusercontent.com/VinAIResearch/PhoBERT/master/README.md
3. VinAI, model card `phobert-base-v2`: https://huggingface.co/vinai/phobert-base-v2 — đã đọc nội dung raw: https://huggingface.co/vinai/phobert-base-v2/raw/main/README.md

Phạm vi thực hiện: chỉ tra cứu và viết note này; không tải/chạy model, không implement/train, không sửa spec. Các gợi ý heads, calibration và phạm vi luận văn là nhận định thiết kế được phân biệt với bằng chứng trong nguồn.
