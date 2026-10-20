# Vietnamese Financial Knowledge Graph

Project này hiện là **bộ khung vertical slice** cho đề tài xây dựng đồ thị tri thức tài chính từ tin tức tiếng Việt và dữ liệu giao dịch.

## Phạm vi đã chốt

- 100 bài báo.
- 13 cổ phiếu ngân hàng thuộc VN30: `ACB`, `BID`, `CTG`, `HDB`, `LPB`, `MBB`, `SHB`, `SSB`, `STB`, `TCB`, `VCB`, `VIB`, `VPB`.
- PhoBERT là model trích xuất tạm thời cho lần chạy trình diễn.
- Candidate universe được giới hạn ở 13 mã trên.
- Ontology và SHACL trong `schema/` là nguồn schema duy nhất.

Danh sách ticker được cố định theo thành phần VN30 sau kỳ rà soát tháng 7/2026 (hiệu lực 03/08/2026). Nếu khoảng thời gian vertical slice khác mốc này, cần xác nhận lại membership theo thời điểm nghiên cứu.

## Cài đặt môi trường

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
```

Để chạy các lệnh CLI hiện tại, cài thêm các collector phụ thuộc browser/PDF:

```powershell
pip install -e ".[browser,pdf]"
```

Để cài dependencies cho PhoBERT:

```powershell
pip install -e ".[extractor]"
```

Để crawl thử hồ sơ cổ phiếu bằng browser Chromium:

```powershell
pip install -e ".[browser]"
python -m playwright install chromium
wfkg crawl-stock --ticker ACB
```

Crawler mở trang công khai trong browser profile tạm, chỉ lấy các trường đang hiển thị và lưu JSON chuẩn hóa vào `data/snapshots/stocks/`. Không dùng phiên đăng nhập Edge và không lưu HTML. URL Vietstock và CafeF cho 13 mã trong vertical slice đã được khai báo trong `stock_profile_pages`.

## Crawl tin hằng ngày từ nhiều nguồn

Sau khi danh bạ 7 nguồn đã có trong `data/snapshots/news_sources/`, chạy:

```powershell
wfkg crawl-daily
```

The combined job refreshes adjusted-close observations through the current Vietnam date using the configured Vnstock backend, validates and updates the market graph, then crawls news. Run `wfkg crawl-news-daily` for news only.

Windows Task Scheduler is configured to run this command daily at 00:00 and 07:30 local time (`SE Asia Standard Time`, UTC+07:00; the same time as Ho Chi Minh City). The tasks use the interactive Windows account and `StartWhenAvailable`, so a trigger missed while the laptop is asleep or hibernating runs later when Windows is available; these settings do not guarantee an exact-time run. Keep the laptop connected to AC and awake during the schedule if exact timing matters. Logs include the local timestamp and Windows time-zone ID in `runs/daily_news/`.

Job mở từng trang nguồn, tự phát hiện RSS được khai báo trên trang và thử một số đường dẫn RSS phổ biến. Nếu nguồn không công bố RSS, job lấy link bài viết công khai trên trang chủ. Job đọc metadata bài để lấy URL chuẩn, tiêu đề và ngày đăng; loại URL trùng rồi lưu tối đa 100 bài mới nhất có ngày đăng hợp lệ. Một nguồn lỗi không dừng các nguồn còn lại.

- Batch crawl và trạng thái từng nguồn: `data/raw/daily/news/<run_id>.json`.
- Snapshot từng bài đã chuẩn hóa: `data/snapshots/news_articles/`.
Subsequent runs skip canonical URLs already present in these snapshots, so the two daily runs add new articles instead of duplicating the same batch.
- Nếu chưa crawl danh bạ nguồn, chạy `wfkg crawl-news-sources` trước.

Các snapshot bài báo là đầu vào cho bước PhoBERT/extract tiếp theo; lệnh này chưa tạo `Evidence`/`Event` hay nạp `NewsArticle` vào KG. Để chạy tự động mỗi ngày trên Windows, có thể gọi chính lệnh này từ Task Scheduler trong môi trường đã cài package bằng `pip install -e .`.

Đã crawl entity `Stock` cho cả 13 mã. VietstockFinance cung cấp `tickerSymbol` và `exchange`; CafeF đối chiếu `tickerSymbol`. Mỗi kết quả có provenance của hai nguồn trong `data/snapshots/stocks/<TICKER>.json`.

`Company/Bank`, ticker `CompanyAlias`, phân loại `IndustryGroup`/`Industry`, `MarketIndex` VN30 và VNINDEX, 13 membership VN30, cùng hồ sơ `CorporateLeader`/`LeadershipPosition` cũng đã được crawl/lưu. Leadership hiện có 309 hồ sơ người, 277 vị trí có ngày bổ nhiệm và 66 vị trí đã xác nhận chức danh nhưng thiếu ngày. Hai liên kết cổ đông bị loại khỏi roster lãnh đạo; không còn hồ sơ chưa phân loại. Xem [báo cáo trạng thái initial data load](doc/initial_data_load_status.md) để biết nguồn, đường dẫn và các entity còn phụ thuộc vào tập 100 bài, kỳ báo cáo hoặc khoảng ngày nghiên cứu.

## Dữ liệu thị trường nền

Giá lịch sử của 13 mã ngân hàng VN30 và VNINDEX được crawl qua Vnstock, cố định backend `kbs` (KB Securities Vietnam). Với cổ phiếu, cột `close` của Vnstock đã điều chỉnh sự kiện quyền và được đổi từ nghìn đồng sang đồng; `returnValue` được tính từ hai phiên liên tiếp. Dữ liệu hiện có 63 phiên cho mỗi mã từ 2026-07-16 đến phiên gần nhất đã đóng cửa 2026-10-15. Ngày 2026-10-16 được yêu cầu nhưng chưa có giá đóng cửa tại thời điểm crawl.

- Raw Vnstock: `data/raw/initial_data_load/market_observations_vnstock_kbs/`.
- Snapshot đã chuẩn hóa: `data/snapshots/market_observations/`.
- Snapshot Vietstock trước đó được giữ để đối chiếu tại `data/snapshots/market_observations_vietstock/`; raw Vietstock cũ vẫn ở thư mục raw ban đầu.
- RDF đã nối vào 13 `Stock` và `MarketIndex`, qua SHACL: `data/gold/market_observations.ttl`.

Cài đúng Vnstock thế hệ 5 từ kho phát hành chính thức (không cài gói cùng tên từ PyPI), sau đó chạy lại collector:

```powershell
pip install -r requirements-market.txt
python -m wfkg crawl-market-observations
```

Tài liệu Vnstock ghi nhận backend thực tế trong metadata trả về; Vnstock là thư viện kết nối, không phải đơn vị sở hữu dữ liệu thị trường. Giữ nguyên backend `kbs` giữa các lần crawl để giá điều chỉnh nhất quán.

Baseline event detection dùng checkpoint PhoBERT fine-tuned trên BKEE tại `models/phobert_bkee_event_detection_v2/`. BKEE cung cấp trigger span và 33 event type; baseline chỉ dự đoán BIO trigger/type, không trích argument hay tự tạo Event canonical trong KG.

### Chính sách văn bản đầu vào cho trích xuất

Module `wfkg.event_processing.text_input` chọn văn bản theo thứ tự:

1. `bodyText` từ bản enrichment được ghép theo đúng `articleId` và ưu tiên dùng làm nội dung trích xuất.
2. Chỉ khi body thiếu/rỗng hoặc chỉ lặp lại title, dùng summary RAW nếu summary có nội dung riêng.
3. Nếu summary cũng thiếu hoặc chỉ lặp title, giữ trạng thái `TITLE_ONLY`; không tự tạo nội dung thay thế.

Summary không được nối vào body khi đã chọn `FULL_TEXT`. Kết quả chuẩn bị đầu vào ghi rõ `source`, `status`, `reason`, số ký tự và SHA-256 để biết mỗi bài dùng trường nào. Body dưới `extractor.short_body_review_chars` (mặc định 500 ký tự) vẫn được dùng làm full-text nhưng có cờ rà soát; đây là cảnh báo chất lượng, không phải điều kiện fallback. Hàm chuẩn bị không cắt văn bản. `PhoBERTEventExtractor.extract()` nạp checkpoint và label map theo `config/vertical_slice.yaml`; inference trả trigger, BKEE event type, confidence, evidence span và provenance đầu vào. Cần cài extra `extractor` và Java để chạy VnCoreNLP word segmentation.

### Fine-tune và chạy BKEE Event Detection

BKEE được lưu nguyên bản tại `data/external/BKEE_official_20261019/` theo commit đã ghi trong báo cáo. Dataset dùng giấy phép CC BY-NC 4.0. Môi trường cài đặt riêng `.venv-phobert-bkee` để không thay đổi `.venv` hiện có. Trên GPU NVIDIA Windows, cài PyTorch từ đúng CUDA wheel index cho máy trước, sau đó cài phần còn lại:

```powershell
.\.venv-phobert-bkee\Scripts\python.exe -m pip install torch==2.11.0 --index-url https://download.pytorch.org/whl/cu128
.\.venv-phobert-bkee\Scripts\python.exe -m pip install -r requirements-phobert-bkee.txt
.\.venv-phobert-bkee\Scripts\python.exe scripts\train_bkee_event_detection.py
.\.venv-phobert-bkee\Scripts\python.exe scripts\run_bkee_event_detection_news_100.py
```

Training chạy smoke test nhỏ trước, rồi fine-tune toàn bộ train split; chọn checkpoint theo exact trigger/type micro-F1 trên dev. Loader đọc JSONL theo từng dòng và chỉ giữ byte-offset, mẫu hiện tại cùng batch nhỏ trong RAM; GPU batch là 1, gradient accumulation là 8 và model bật gradient checkpointing. Có thể dùng `--train-limit N` để chạy thử trên N dòng đầu của train split; chế độ mặc định vẫn dùng toàn bộ train split. Test split không tham gia training hay chọn checkpoint. Báo cáo và checkpoint nằm trong `runs/phobert_bkee_event_detection_v2/` và `models/phobert_bkee_event_detection_v2/`. Chạy lại inference trên cohort 100 bài ghi output vào thư mục mới `runs/phobert_bkee_event_detection_v2/news_100_final/`; lệnh từ chối ghi đè thư mục output không rỗng. Có thể gọi `extractor_from_project_config(load_config(...)).extract(article, enriched_article)` cho bài mới sau khi nối enrichment đúng `articleId`.

BKEE là nguồn tổng quát, không phải taxonomy sự kiện tài chính của luận văn. Các nhãn như `Transfer-money`, `Transfer-ownership`, `Declare-bankruptcy`, `Fine`, `Sue`, `Merge-org`, `Start-position` và `End-position` có phần giao nghĩa; thông báo lợi nhuận, cổ tức, phát hành vốn, nợ xấu, lãi suất, kế hoạch đầu tư và biến động giá chưa được BKEE hỗ trợ như event type chuyên biệt. Prediction là ứng viên cần rà soát và ánh xạ sang ontology trước khi tạo Event hoặc EventStockCandidate.

Ví dụ nối cohort RAW với enrichment theo ID:

```python
from wfkg.event_processing import prepare_extraction_input

prepared = prepare_extraction_input(raw_article, enriched_article)
print(prepared.source, prepared.status, prepared.sha256)
model_text = prepared.text
```

Caller cần bảo toàn đúng quan hệ `articleId` khi nối hai tập; hàm sẽ từ chối nếu hai ID hiện diện nhưng không khớp.

## Kiểm tra cấu hình

```powershell
wfkg validate-config --config config/vertical_slice.yaml
```

Lệnh này kiểm tra cấu hình slice và kiểm tra sự hiện diện của schema files. Các bước crawl, trích xuất, sinh Candidate và tính Reaction là các phần triển khai tiếp theo; cây thư mục chưa hàm ý rằng chúng đã chạy được.

## Luồng dự kiến

1. `initial_data_load`: crawl danh mục công ty/cổ phiếu, quan hệ nền và dữ liệu lịch sử cần thiết.
2. `daily_ingest`: nạp 100 bài báo đã chọn cùng quan sát giá cổ phiếu và benchmark.
3. `event_processing`: tạo Evidence/Event canonical, liên kết thực thể, sinh và chấm điểm EventStockCandidate.
4. `market_reaction`: sau khi event window đóng, tạo EventStockReaction và provenance AR/CAR.
5. Lưu graph/output và manifest/log vào `runs/<run_id>/`.

Chi tiết ontology và ràng buộc xem `schema/ontology.ttl` và `schema/shapes.ttl`. Quyết định nghiên cứu xem `CONTEXT.md`.

Các lệnh initial data load đã triển khai hiện tại có thể xem bằng `python -m wfkg --help`. Snapshot được ghi vào `data/snapshots/`; những entity chưa có collector không được thay bằng dữ liệu dựng sẵn.

NewsArticle records are exported to the KG from the latest crawl batch (up to 100 articles). Event/Evidence extraction remains a separate pipeline step.

## Exporting the KG from crawled snapshots

Initial data load jobs write JSON snapshots. This command merges eligible entities with the market graph, validates SHACL, and saves the KG and manifest:

```powershell
python -m wfkg build-kg
```

The merged KG is saved at `data/gold/knowledge_graph.ttl`; counts and SHACL status are in `data/gold/knowledge_graph_manifest.json`. Original snapshots remain in `data/snapshots/`.
