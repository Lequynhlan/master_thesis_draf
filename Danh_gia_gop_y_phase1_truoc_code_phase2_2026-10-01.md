# Đánh giá mức độ đáp ứng góp ý Phase 1 trước khi code Phase 2

Ngày đánh giá: 01/10/2026

## Phạm vi

Đối chiếu tệp góp ý `ban_thay_gop_y/gop_y_phase1_truoc_code_phase2.txt` với các tài liệu trong `chỉnh sửa mới nhất - 01-10`. Đã đọc 8 tệp không phải Word: `ANNOTATION_GUIDELINE.md`, `EVALUATION_PROTOCOL.md`, `EVENT_DICTIONARY.yaml`, `EVENT_SCHEMA.md`, `master_thesis_v1_synced_01-10.drawio.xml`, `ontology_v1.0.ttl`, `SCORING_SPEC.md`, `shapes_v1.0.ttl`. Không mở hai tệp `.docx` hoặc file khóa Word; vì vậy phần đối chiếu báo cáo Word/PDF nằm ngoài phạm vi kết luận.

> Các mục đánh giá bên dưới ghi nhận trạng thái trước lượt chỉnh sửa tài liệu. Kết quả cập nhật, kiểm thử và giới hạn còn lại được ghi ở cuối tệp.

## Kết luận điều hành tại thời điểm rà soát trước chỉnh sửa

Bộ tài liệu đã xử lý phần lớn yêu cầu về cutoff, scoring, event dictionary và protocol, nhưng chưa đáp ứng đầy đủ để freeze. Các điểm chặn chính là: mô tả `INDIRECT_INDUSTRY` ở tab tổng quan Draw.io vẫn rộng hơn đường baseline; SHACL chưa bảo đảm provenance đủ toàn event window; phụ lục property Draw.io còn thiếu/sai phân loại; version giữa ontology và các đặc tả chưa thống nhất. Chưa nên coi gói specification đã sẵn sàng để bắt đầu code Phase 2 trước khi xử lý các điểm này và gửi thầy kiểm tra lại.

## Đánh giá theo từng góp ý

### 1. Đồng bộ namespace, baseline và nguồn đặc tả — Chưa đạt hoàn toàn

Trong các tệp đã xem, namespace `https://example.org/wfkg/v1#` thống nhất giữa schema, scoring spec, TTL, SHACL và Draw.io. Các tài liệu cũng dùng đúng bốn `impactType`. Tuy nhiên:

- Draw.io tab `01-Tổng quan đề tài` (tìm câu “Một sự kiện ảnh hưởng đến toàn ngành”) vẫn mô tả sự kiện có thể lan tới “các cổ phiếu cùng nhóm ngành”. Cách nói này rộng hơn baseline cụ thể ở tab `05-4 Đường liên hệ chính`: `Event → Industry ← IndustryExposure ← Bank → Stock`. Nên sửa mô tả tổng quan để nêu rõ chỉ tạo đường qua `IndustryExposure` đủ điều kiện, không suy rộng tới mọi cổ phiếu cùng ngành.
- `ontology_v1.0.ttl` ghi `owl:versionInfo "1.0.0"`; `SCORING_SPEC.md`, `EVENT_DICTIONARY.yaml`, `EVALUATION_PROTOCOL.md` và `ANNOTATION_GUIDELINE.md` ghi `1.0.1`. Cần thống nhất version của cả gói; SHACL cũng nên có version xác định.
- SHACL chỉ giới hạn `impactType` trong bốn giá trị, còn `relationPath` chỉ cần là chuỗi (`shapes_v1.0.ttl`, `EventStockCandidateShape`). Chưa có ràng buộc để xác nhận `impactType` và đường đi thực tế khớp nhau.
- Chưa đối chiếu được namespace trong báo cáo Word/PDF theo giới hạn phạm vi đã nêu.

### 2. `effectiveTradingDate` với dữ liệu daily — Đạt ở mức đặc tả; chưa xác minh thực thi

`EVENT_SCHEMA.md`, mục “Frozen cutoff and daily calendar contract”, quy định dùng phiên hiện tại nếu thông tin có trước giờ mở cửa; đúng giờ mở cửa hoặc sau đó thì chọn phiên kế tiếp, theo calendar/exchange đã khóa. Ví dụ 09:00 và 14:16 chuyển sang phiên kế tiếp. Đây là cách xử lý phù hợp với góp ý.

Khoảng trống: SHACL chỉ kiểm tra datatype của `effectiveTradingDate` và `availableAt`; không kiểm tra timezone, market calendar hoặc ngày giao dịch được suy ra đúng từ giờ mở cửa. Chưa có dữ liệu/demo để xác minh các ví dụ trên bằng lịch giao dịch thực.

### 3. Các thành phần `confidenceScore` — Gần đạt

`SCORING_SPEC.md` định nghĩa bốn component, cách xử lý nhiều nguồn, `linkingConfidence`, `relationConfidence` của DIRECT, fallback và freeze theo `inferenceCutoff`/`methodVersion`. TTL/SHACL có trường cho các component và SHACL kiểm tra `confidenceScore` là trung bình của bốn giá trị.

Khoảng trống: SHACL không buộc baseline `sourceConfidence = 0.5`, không bảo đảm Candidate lịch sử không bị sửa, và không bắt buộc liên kết component với Evidence/entity decision trong graph. Các điều này hiện mới là quy tắc đặc tả hoặc phụ thuộc audit record/implementation.

### 4. Tách `candidateScore` và `reactionWeight` — Đạt về định nghĩa

`candidateScore` được dùng để xếp hạng tại inference time; `reactionWeight` chỉ dùng sau khi event window đóng. Scoring spec, schema, SHACL và các tab Draw.io về Candidate/Reaction diễn đạt nhất quán hai mục đích. SHACL có kiểm tra công thức score. Việc code thực tế không dùng `reactionWeight` khi ranking chưa thể xác minh vì chưa xem implementation.

### 5. Provenance để tính lại AR/CAR — Chưa đạt

Đã bổ sung `adjustedClose` cho `MarketIndexObservation`; Reaction liên kết tới stock/index observations. Tuy vậy, SHACL hiện chỉ yêu cầu tối thiểu một observation mỗi loại. Nó chưa bảo đảm:

- có đủ mọi phiên trong event window và phiên `t−1`;
- stock observations thuộc đúng Candidate stock, index observations thuộc đúng benchmark;
- `returnValue` khớp với adjusted close; hoặc CAR nhiều ngày bằng tổng các AR theo từng ngày.

Trong probe PySHACL bằng graph tổng hợp, Reaction window `[0,+1]` với chỉ một cặp stock/index observation vẫn `Conforms=True`; bỏ `adjustedClose` khỏi index observation thì bị từ chối. Đây là bằng chứng shape bắt trường bắt buộc nhưng chưa bắt đủ coverage của cửa sổ. Probe là dữ liệu tổng hợp, không phải demo của dự án.

### 6. Event Dictionary trước khi code NLP — Gần đạt

`EVENT_DICTIONARY.yaml` parse được, có 14 eventType và các trường cần thiết: mô tả, required/optional roles, canonical key, hướng tác động, ví dụ và confusables. Tuy nhiên, `updates` xuất hiện trong `confusable_cases` ở hai entry (`M_AND_A_RUMOR_CLARIFICATION`, `LEADERSHIP_CHANGE`). `updates` là quan hệ Event–Event, không phải eventType theo `ANNOTATION_GUIDELINE.md`. Nên tách nhầm lẫn giữa eventType và relation thành hai trường.

### 7. Cardinality và quy tắc IndustryExposure — Gần đạt

`EVENT_SCHEMA.md` quy định `NewsArticle reports Event` là `0..*` ở raw/staging và đặt curated inference gate riêng; IndustryExposure được chọn theo kỳ báo cáo, thời điểm available và staleness tối đa 365 ngày. Đã tách baseline relationStrength 0.5 khỏi biến thể dùng `exposureStrength`.

Khoảng trống: curated gate và chọn kỳ là logic ngoài SHACL, chưa có dữ liệu/code để xác nhận. Schema khóa baseline `periodType=YEAR` và reporting scope, nhưng `IndustryExposureShape` vẫn chấp nhận nhiều periodType; run manifest trong `EVALUATION_PROTOCOL.md` chưa ghi periodType/reporting scope để tái lập lựa chọn.

### 8. Freeze protocol đánh giá — Gần đạt

Protocol tách vertical slice 100–300 bài khỏi development, validation và final evaluation; cấm trùng canonical Event qua split. `ANNOTATION_GUIDELINE.md` yêu cầu double-label tối thiểu 25%, báo agreement và adjudicate; Evaluation yêu cầu RQ2 theo từng impactType và macro theo Event.

Khoảng trống: chưa chốt quy mô final gold/test set hay ngưỡng support tối thiểu theo impactType, nên chưa có tiêu chí nhận biết kết quả quá ít positive để diễn giải. Agreement cũng chưa đủ tái lập: “Evidence span overlap” chưa có công thức, weighted kappa chưa nêu weighting, và relation agreement chưa làm rõ cách xử lý multi-label như protocol quy định. Heading `Reproducibility` trong `EVALUATION_PROTOCOL.md` đang để trống; run manifest đặt ở phần sau.

### 9. Phụ lục property Draw.io — Chưa đạt

Đối chiếu tab `06-Phụ lục Entity Property` với ontology/SHACL cho thấy:

- Thiếu object properties: `hasFinancialMetric`, `hasLeadershipPosition`, `relatedEvent`.
- Thiếu datatype properties: `exposureRatio`, `exposureStrength`, `reportedCategory`, `indexCode`, `indexId`, `indexName`.
- `url` được xếp vào nhóm DatatypeProperty trong Draw.io nhưng ontology khai báo ObjectProperty và SHACL yêu cầu IRI.
- `periodEnd`/`periodType` được liệt kê cho FinancialMetric nhưng chưa được thể hiện cho IndustryExposure, dù IndustryExposureShape yêu cầu hai trường này.

Vì vậy, ví dụ property thầy nêu đã được bổ sung phần lớn, nhưng phụ lục chưa đủ tin cậy để dùng làm bảng tra khi code. TTL/SHACL có thể làm nguồn chính, nhưng cần cập nhật phụ lục hoặc có kiểm tra tự động để phát hiện lệch.

## Kiểm chứng và giới hạn

- RDFLib 7.6.0 parse được ontology (455 triples) và shapes (992 triples); ontology có 22 class, 44 object property, 85 datatype property; SHACL có 129 đường `sh:path`. PyYAML 6.0.2 parse được Dictionary; Draw.io XML parse được và có 7 tab.
- PySHACL 0.40.0 báo `Conforms=True` khi dùng chính ontology làm data graph. Đây chỉ là smoke check cấu trúc, không phải kiểm định graph demo.
- Probe `[0,+1]` là graph tổng hợp và cho thấy coverage nhiều ngày chưa được SHACL cưỡng chế. Không có demo graph, gold set, run manifest, query/result hoặc implementation trong tập được rà, nên không thể xác nhận pipeline chạy end-to-end.
- Trong probe hiện tại, các literal `xsd:string` tường minh cho trường có `sh:in` phát sinh lỗi so khớp, trong khi literal chuỗi không ghi datatype thì qua. Chưa có graph do serializer thực tế tạo ra để kết luận đây là lỗi production; cần thử bằng đúng serializer/validator trước khi freeze.

## Việc nên xử lý trước khi gửi thầy

Ưu tiên cao:
1. Sửa mô tả INDIRECT_INDUSTRY ở tab tổng quan cho đúng route qua IndustryExposure; làm rõ bốn `impactType` khớp với bốn route, không để route rộng bị hiểu là baseline.
2. Hoàn thiện phụ lục property: bổ sung các property còn thiếu, sửa phân loại `url`, thể hiện `periodEnd`/`periodType` cho IndustryExposure.
3. Bổ sung SHACL hoặc verifier/test có thể chứng minh Reaction có đủ observation từng phiên, cả phiên `t−1`, đúng stock/benchmark, và tính lại được AR/CAR của window nhiều ngày.

Ưu tiên tiếp theo: đồng bộ version của ontology/SHACL/spec; ghi periodType và reporting scope trong manifest; chốt ngưỡng dữ liệu/support final set và cách tính agreement. Sau đó chạy validation trên graph demo thực cùng negative mutation tests rồi gửi gói specification cho thầy review.

## Kết luận trước chỉnh sửa

Trong phạm vi tám tệp không phải Word, góp ý đã được xử lý đáng kể nhưng chưa đầy đủ. Các điểm 1, 5 và 9 còn khoảng trống trực tiếp; các điểm 3, 6, 7 và 8 còn phần cần khóa/kiểm chứng. Không nên kết luận gói đã freeze hoặc bắt đầu code Phase 2 trước khi xử lý các điểm ưu tiên cao và xin thầy kiểm tra lại.

## Cập nhật sau lượt chỉnh sửa — 01/10/2026

### Tài liệu đã cập nhật

Đã sửa tám tài liệu nguồn: `EVENT_SCHEMA.md`, `SCORING_SPEC.md`, `shapes_v1.0.ttl`, `master_thesis_v1_synced_01-10.drawio.xml`, `ontology_v1.0.ttl`, `EVENT_DICTIONARY.yaml`, `ANNOTATION_GUIDELINE.md` và `EVALUATION_PROTOCOL.md`. Đồng bộ contract lên 1.0.2; khóa cặp `impactType`/`relationPath` và bốn đường đi; bổ sung kiểm tra route, baseline `sourceConfidence=0.5`, timestamp có timezone, provenance/coverage AR-CAR; sửa phụ lục property, reporting-period metadata, ngưỡng support và quy tắc agreement. Báo cáo đánh giá này cũng được cập nhật để phân biệt trạng thái ban đầu với trạng thái hiện tại.

### Kiểm chứng đã chạy

- RDFLib parse ontology (455 triples) và SHACL (1,064 triples); PyYAML parse Dictionary; XML parser đọc Draw.io thành công với 7 tab. Version ontology, SHACL, Dictionary và bốn Markdown spec được kiểm tra là 1.0.2.
- PySHACL smoke test trên ontology cho `Conforms=True`; đây chỉ là kiểm tra cấu trúc, không phải graph pipeline.
- Bộ test Reaction trên graph tổng hợp: 9/9 kết quả khớp kỳ vọng (cửa sổ đầy đủ hợp lệ; cửa sổ thiếu phiên, ownership sai, lệch ngày, thiếu adjustedClose, sai return/AR/CAR và timestamp không timezone đều bị từ chối).
- Bộ test Candidate trên graph tổng hợp: 7/7 kết quả khớp kỳ vọng (4 route hợp lệ; route code sai, thiếu evidence của route và sourceConfidence khác baseline đều bị từ chối).
- `git diff --check` không báo lỗi.

### Giới hạn còn lại

Các graph dùng để test là graph tổng hợp, không phải dữ liệu hay output pipeline của luận văn. Chưa có xác minh end-to-end bằng serializer/validator của ứng dụng, market-data provider thật hoặc exchange calendar đã khóa. SHACL kiểm tra số lượng/ngày ghép và công thức từ các observation được link; verifier có market calendar vẫn phải xác nhận chính xác danh sách phiên giao dịch. Hai tệp Word không được mở hoặc sửa.

## Kết luận hiện tại

Các khoảng trống tài liệu đã nêu trong lần rà soát được xử lý ở contract và có kiểm thử cấu trúc tổng hợp; có thể gửi gói tài liệu 1.0.2 cho thầy rà soát. Chưa được tuyên bố pipeline Phase 2 đã đáp ứng hoặc AR/CAR đã xác minh trên dữ liệu thật; phần đó cần chờ implementation, market calendar và graph thực.
