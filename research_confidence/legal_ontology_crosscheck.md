# Đối chiếu nguồn gốc: ontology pháp luật không đồng nghĩa numeric confidence

Phạm vi: nghiên cứu tài liệu, không thay đổi SCORING_SPEC hoặc ontology. Các nguồn dưới đã được truy cập trực tiếp bằng HTTP 200 trong phiên nghiên cứu. Không gọi đây là systematic review; mẫu tài liệu có chủ đích.

## 1. Hoekstra, Breuker, Di Bello, Boer — The LKIF Core Ontology of Basic Legal Concepts (LOAIT 2007)

Nguồn primary: https://ceur-ws.org/Vol-321/paper3.pdf
Proceedings/title/authors đối chiếu: https://ceur-ws.org/Vol-321/

Đã tải và trích toàn bộ PDF 21 trang; đọc phần introduction, methodology, attitudes/qualification và use-case evaluation. PDF p1 nêu LKIF core kết hợp OWL-DL và SWRL để interchange/formalize legal knowledge. PDF p13–14 mô hình Proposition, Propositional_Attitude, Belief, Assertion, Evaluative_Attitude, Qualification. PDF p15 đánh giá bằng formalization EU Directive 2006/126 driving licences.

Không tìm được công thức pipeline extraction/linking/source confidence kiểu weighted average trong bài này. Kết luận giới hạn ở bài đã đọc: legal conceptual schema này không cung cấp công thức có thể sao chép thành extractionConfidence WFKG. Không suy rộng rằng mọi legal ontology đều không có numeric uncertainty.

## 2. Athan, Governatori, Palmirani, Paschke, Wyner — LegalRuleML: Design Principles and Foundations (2015)

DOI đã đối chiếu qua Crossref: 10.1007/978-3-319-21768-0_6
Publisher primary: https://link.springer.com/chapter/10.1007/978-3-319-21768-0_6

Đọc publisher abstract, notes và references; full chapter có subscription, CHƯA đọc full text. Abstract mô tả syntactic/semantic/pragmatic foundations, modelling norms và legal reasoning. Không suy diễn numeric confidence từ abstract.

Nguồn primary bổ trợ đọc toàn văn: OASIS LegalRuleML Core Specification Version 1.0, §4.2.1 Defeasibility:
https://docs.oasis-open.org/legalruleml/legalruleml-core-spec/v1.0/os/legalruleml-core-spec-v1.0-os.html

Chuẩn giải thích strict rule, defeasible rule, defeater, conflict resolution bằng specificity/salience/preference/superiority. Override thể hiện rule nào ưu tiên rule nào; strength có thể là loại rule/qualification. Chuẩn cũng thảo luận weights trong argumentation nhưng không biến các loại rule thành calibrated extraction probability. Ví dụ lex superior/lex posterior là ưu tiên pháp lý, không phải extractor confidence.

Bài học: relationStrength, priority và confidence of extracted fact là các đại lượng khác nhau. Không lấy rule thắng trong conflict làm bằng chứng nguồn/trích xuất chắc chắn đúng.

## 3. Lenci, Montemagni, Pirrelli, Venturi — NLP-based ontology learning from legal texts. A case study. (LOAIT 2007)

Nguồn primary full PDF 17 trang: https://ceur-ws.org/Vol-321/paper7.pdf
Proceedings đối chiếu: https://ceur-ws.org/Vol-321/

Hệ T2K dùng NLP/statistical text analysis để học term/proto-ontology từ văn bản lập pháp tiếng Ý về môi trường.

Phương pháp scoring quan trọng, PDF p8: log-likelihood ratio đo association giữa lexical-semantic heads của adjacent chunks, không đơn thuần giữa từ kề nhau. Điểm này là association strength phục vụ term acquisition, KHÔNG phải calibrated P(role correctly extracted).

Đánh giá PDF p12–14: đối chiếu glossary/term bank với reference dictionaries, xét full/partial matches và manual assessment; tác giả nêu không thể kết luận recall từ reference có phạm vi rộng hơn corpus. Vì vậy tỷ lệ term match không phải per-item confidence và không thể thay thế precision/recall/required-role accuracy của WFKG.

Bài học: ontology-learning có thể dùng statistical score để lựa chọn candidate concepts, sau đó đo chất lượng bằng tài nguyên/gold bên ngoài. Việc gọi mọi statistical score là confidence probability sẽ sai.

## 4. W3C OWL 2 Primer, Second Edition — §8.1 Annotating Axioms and Entities

Nguồn primary standard đọc trực tiếp: https://www.w3.org/TR/owl2-primer/#Annotating_Axioms_and_Entities

Nguyên văn: “Annotation information is not really part of the logical meaning of an ontology.”

Lưu annotation score trên axiom không tự làm OWL reasoner thực hiện probabilistic inference. Muốn numeric uncertainty có semantics cần method/mô hình riêng; OWL consistency và SHACL conformance không chứng minh fact đúng ngoài đời.

## Kết luận cho luận văn

Các nguồn pháp luật trên hữu ích để phân biệt schema/logic/priority/term association; không phải evidence để khẳng định average source/extraction/linking/relation là công thức chuẩn của legal ontologies. Để sinh confidence component nên xem thêm information extraction, entity linking, probabilistic knowledge fusion và LLM evaluator. Để đánh giá score phải dùng correctness target và gold độc lập, không chỉ reasoner pass.
