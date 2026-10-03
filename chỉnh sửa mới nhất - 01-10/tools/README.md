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
- Tab khác appendix chỉ kiểm tra XML structure. Free-form route labels, endpoint ngữ nghĩa của connectors, namespace narrative, layout/readability vẫn cần review thủ công.
- Không audit DOCX, scoring/evaluation, market calendar, dữ liệu thật, inference pipeline hoặc RQ1–RQ3.
- Không chạy SHACL conformance/behavioral tests. SELECT parse thành công không chứng minh constraint phát hiện đúng dữ liệu sai.
- Nếu thay đổi định dạng appendix đáng kể, cần cập nhật parser/tests; không dùng tool như công cụ audit Draw.io tổng quát.

## Kiểm thử công cụ

Bộ test nội bộ nằm ngoài folder gửi thầy, tại `review_phase1/test_audit_schema_diagram.py` trong workspace phát triển. Test tạo các bản sao tạm có lỗi cố ý, không sửa artifact chuẩn. Các trường hợp gồm real-bundle read-only, range/owner/cardinality sai, cardinality sai cú pháp, datatype property bị typo/missing và chạy từ working directory khác.

Khi phát hiện FAIL, đọc vị trí và nội dung rồi sửa thủ công artifact được duyệt. Tool không có chế độ auto-fix.
