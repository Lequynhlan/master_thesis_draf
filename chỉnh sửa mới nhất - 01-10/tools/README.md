# Audit chỉ đọc: TTL/SHACL — phụ lục Draw.io

## Mục đích

Kiểm tra tự động các khác biệt có thể đối chiếu được giữa ontology TTL, SHACL và tab `06-Phụ lục Entity Property` của Draw.io. Không sửa bất kỳ file đầu vào nào, không tự vẽ lại diagram và không tạo report file khi chạy mặc định.

Đây là audit theo định dạng label hiện tại của bộ WFKG, không phải công cụ hiểu mọi sơ đồ Draw.io hay bộ chứng minh ontology tương đương.

## Cài đặt và chạy

Python 3.11 trở lên; dependency: rdflib (bao gồm SPARQL parser). Dùng pip của đúng Python interpreter:

```text
python -m pip install "rdflib>=7,<8"
```

Từ folder chứa ontology/SHACL/Draw.io:

```text
python tools/audit_schema_diagram.py
```

Hiển thị cả các dòng PASS:

```text
python tools/audit_schema_diagram.py --verbose
```

JSON chỉ in ra stdout, không tự ghi file:

```text
python tools/audit_schema_diagram.py --json
```

Script lấy đường dẫn mặc định tương đối từ vị trí của chính nó, không hardcode ổ D: và không phụ thuộc working directory. Có thể chạy bằng đường dẫn đầy đủ từ nơi khác.

So sánh một bản sao khác mà không đổi file mặc định:

```text
python tools/audit_schema_diagram.py --ontology "path/ontology.ttl" --shapes "path/shapes.ttl" --drawio "path/diagram.xml"
```

Draw.io phải là XML không nén có `mxGraphModel` trong từng tab và có tab tên bắt đầu bằng `06-`. Nếu định dạng khác, script trả ERROR thay vì báo PASS giả.

## Các kiểm tra thực hiện

1. Parse ontology TTL, SHACL TTL và Draw.io XML.
2. Mỗi tab Draw.io: cell ID không thiếu/trùng, parent/source/target không trỏ tới cell không tồn tại.
3. Tên OWL classes/ObjectProperties/DatatypeProperties trong TTL có mặt trong appendix. Kết quả này chỉ là name coverage, không phải semantic proof.
4. Dòng dạng `Owner —property [cardinality]→ Target`:
   - Property là ObjectProperty.
   - Owner đúng domain TTL; chấp nhận subclass và kế thừa domain/range qua subPropertyOf.
   - Target tương thích range TTL; đây là kiểm tra tương thích, không chứng minh hai mô hình OWL tương đương.
   - Nếu Target là IRI và TTL không có range: kiểm tra direct SHACL nodeKind nếu có.
   - Nếu label có cardinality: đối chiếu direct SHACL minCount/maxCount theo targetClass và superclass. Không suy cardinality từ OWL functional property hay query SPARQL.
5. Dòng dạng `Owner: prop1, prop2` hoặc `Company/Bank: ...`:
   - Property là DatatypeProperty.
   - Owner tương thích domain TTL nếu domain được khai báo.
6. Parse cú pháp mọi SHACL SELECT constraint; không thực thi validation graph.
7. So sánh SHA256 của ba file đầu vào trước/sau; script không có đường ghi lại các artifact.
8. Tab `00-`: với từng cạnh `hasSubsidiaryRelation`, source phải là đúng target của `parentCompany` trên cùng relation node. Kiểm tra vai trò mẹ/con bằng identity của endpoint, không chỉ dựa vào việc cả hai endpoint đều là Company.

FAIL có vị trí tab, cell ID và số dòng text trong label, không phải số dòng XML. Dòng FAIL nêu giá trị Draw.io và giá trị kỳ vọng khi có thể đối chiếu.

## PASS / FAIL / NOT CHECKED

- PASS: một assertion cụ thể đã khớp, trong phạm vi được ghi trong dòng đó.
- FAIL: thiếu tên, sai property kind, domain/range/cardinality không khớp, label cardinality sai cú pháp hoặc XML reference hỏng.
- NOT CHECKED: không đủ thông tin để đối chiếu hoặc ngoài phạm vi tool. Không được diễn giải thành PASS.
- ERROR: file thiếu/hỏng, định dạng không hỗ trợ hoặc parser lỗi.

Exit codes:

- `0`: không có FAIL trong các kiểm tra hỗ trợ; vẫn có thể có NOT CHECKED.
- `1`: có ít nhất một FAIL.
- `2`: không hoàn thành được audit do lỗi input/định dạng/parser.

Các con số PASS/NOT CHECKED là số assertion, không phải số reviewer comments hay coverage percentage.

## Giới hạn quan trọng

- Shared properties không có OWL domain riêng được báo NOT CHECKED cho ownership. Không tự gán domain vì có thể làm thay đổi ngữ nghĩa ontology.
- Appendix hiện liệt kê tên datatype property nhưng không ghi datatype range; tool không tuyên bố đã so sánh xsd:string/decimal/dateTime nếu diagram không biểu diễn chúng.
- Properties chỉ xuất hiện trong shared/narrative text, chẳng hạn involves/sourceReference/validFrom/validTo/dataQualityFlag, chỉ được kiểm tra name coverage; endpoint/ownership của chúng được báo NOT CHECKED nếu không có structured entry.
- Chỉ cardinality được in trực tiếp trong object-arrow labels được đối chiếu. Không bao phủ qualified constraints, sh:or/sh:and hoặc cardinality ẩn trong SPARQL.
- Ngoài appendix, audit kiểm tra XML structure và invariant owner mẹ/con vừa nêu ở tab `00-`. Những free-form route labels, connector semantics khác, namespace narrative và layout/readability vẫn cần review thủ công; một invariant không chứng minh toàn bộ semantics.
- Không audit DOCX, scoring/evaluation, market calendar, dữ liệu thật, inference pipeline hoặc RQ1–RQ3.
- Không chạy SHACL conformance/behavioral tests. SELECT parse thành công không chứng minh constraint phát hiện đúng dữ liệu sai.
- Nếu thay đổi định dạng appendix đáng kể, cần cập nhật parser/tests; không dùng tool như công cụ audit Draw.io tổng quát.

## Kiểm thử công cụ

Trong gói có `tools/test_schema_diagram_audit.py`: 8 unittest với XML mutation trong bộ nhớ để bắt owner mẹ/con sai, thiếu parent connector, parent thuộc relation khác, và kiểm tra các nhãn/schema đã hiệu đính. Chạy `py -3.13 -B tools/test_schema_diagram_audit.py`; không sửa artifact chuẩn.

Bộ test legacy tại `review_phase1/test_audit_schema_diagram.py` trong workspace phát triển không thuộc acceptance set của gói này. Bộ đó kiểm tra range/owner/cardinality, typo/missing và working directory; không phải dependency để chạy các test được bàn giao.

Khi phát hiện FAIL, đọc vị trí và nội dung rồi sửa thủ công artifact được duyệt. Tool không có chế độ auto-fix.

## Kiểm thử hành vi SHACL baseline 1.0.5

`test_baseline_shacl.py` là bộ regression test riêng, không thay đổi chức năng của audit ở trên. Test dùng fixture tổng hợp trong bộ nhớ; không tạo lại demo, CSV hoặc hình lịch sử trong báo cáo và không phải kết quả RQ.

Dependency bổ sung: `pyshacl`. Trong môi trường Windows đã kiểm tra, Python 3.13 có RDFLib 7.6.0 và pySHACL 0.40.0; lệnh chạy từ thư mục chứa TTL/SHACL:

```text
py -3.13 -B tools/test_baseline_shacl.py
py -3.13 -B tools/test_schema_diagram_audit.py
py -3.13 -B tools/audit_schema_diagram.py
```

Ở môi trường khác, dùng đúng interpreter có `rdflib` và `pyshacl`; không dùng `pip` của một Python khác. Cờ `-B` tránh tạo `__pycache__` trong bộ bàn giao. Không cần cài thêm gói trong môi trường hiện tại.

Bộ hiện tại có 32 unittest (test severity có 5 subtest cho giá trị thiếu, hai biên và hai giá trị ngoài miền). Giữ 19 regression ban đầu về confidence/score, giá benchmark, daily return/CAR, impactScore, direction, inverse, self-link và thời điểm Reaction; bổ sung REACTION_READY không có Reaction với cả plain/typed string, status ngoài enum, các trạng thái non-ready có/không Reaction, cutoff sớm/muộn hơn Event và thứ tự generatedAt/availableAt. Positive control xác nhận replay chạy muộn vẫn dùng cutoff gốc. Inference bị tắt khi validate để không che lỗi thiếu inverse. Đây là dữ liệu synthetic, không phải pipeline thật.

SHACL baseline khóa `inferenceCutoff = Event.availableAt`, tau=0.10 và epsilon=0. Lifecycle chấp nhận plain hoặc typed xsd:string với cùng giá trị enum, không chấp nhận status ngoài enum. Thay cutoff regime/tau/epsilon phải dùng specification/shape/configuration được định phiên bản riêng. Calendar, daily effectiveTradingDate, dictionary membership/vocabulary, Evidence selection, strength assignment và snapshot immutability vẫn cần curated gate/validator Phase 2; 32 test không chứng minh các phần đó đã triển khai. Mã thoát 0 nghĩa là tất cả test đã qua; mã khác 0 là thất bại hoặc lỗi môi trường.

Kết quả kiểm tra contract 1.0.5: 32/32 SHACL unittest, 8/8 diagram-audit unittest; audit 337 PASS, 0 FAIL, 57 NOT CHECKED và 44 SELECT parse được. Ma trận 9 góp ý, trạng thái PDF và giới hạn xác minh được ghi ở `../PHASE1_ACCEPTANCE.md`. Không diễn giải các con số này thành coverage percentage hoặc kết quả RQ.
