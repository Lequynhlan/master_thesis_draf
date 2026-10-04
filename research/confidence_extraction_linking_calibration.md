# Confidence trong extraction, entity linking và knowledge fusion

Phạm vi: nghiên cứu có mục tiêu phục vụ WFKG contract 1.0.4, không phải systematic review; không thay đổi contract hiện tại. Các PDF dưới đây được tải và đọc trực tiếp bằng text extraction; kết luận chỉ gắn với những hệ thống đã khảo sát, không đại diện mọi ontology.

## 1. Kết luận nền tảng

Ontology/schema không tự sinh độ tin cậy thực nghiệm. Cần phân biệt: (a) điều kiện hợp lệ logic/kiểu/cardinality; (b) model score; (c) xác suất correctness đã kiểm tra calibration; (d) confidence của luật học từ KG; (e) fuzzy truth/support score; (f) rubric/checklist do người thiết kế định nghĩa. Cùng nằm trong [0,1] không khiến các đại lượng này có cùng ngữ nghĩa.

Một score phải có target cụ thể: trích đúng assertion từ văn bản, link đúng URI, source báo đúng fact, hay kết luận đúng theo gold. Trích đúng một câu sai vẫn có thể là extraction tốt nhưng source/fact correctness thấp. Bài Knowledge-Based Trust thực sự mô hình hóa sự tách biệt đó [S5].

## 2. REVERB: tiêu chí quan sát được + trọng số học từ nhãn

[S1] Anthony Fader, Stephen Soderland, Oren Etzioni (2011). *Identifying Relations for Open Information Extraction*. EMNLP, 1535–1545.
- Primary metadata: https://aclanthology.org/D11-1142/
- Full text: https://aclanthology.org/D11-1142.pdf
- Locator: mục 4.2, Table 4, trang in 1540 / PDF trang 6.

Hệ thống dùng constraints cú pháp/lexical để sinh extraction, sau đó logistic regression gán confidence cho extraction `(x,r,y)` từ câu `s`. Confidence function học từ extraction correct/incorrect được người gán nhãn trên 1.000 câu Web/Wikipedia; đây là số câu, không khẳng định là 1.000 extraction.

Table 4 có các features cụ thể và learned weights, ví dụ:
- Extraction phủ hết câu: +1.16.
- Câu có <=10 từ: +0.43.
- Câu bắt đầu bằng argument x: +0.21.
- y là proper noun: +0.16.
- Có NP bên phải y: -0.81.
- Có coordinating conjunction bên trái relation: -0.93.

Dạng logistic chuẩn diễn giải cơ chế: `score = sigmoid(b + sum(w_j * feature_j))`. Không dùng những weights tiếng Anh này trực tiếp cho tiếng Việt hoặc event financial extraction. Bài không chứng minh hậu kiểm calibration cho WFKG.

Điểm phù hợp với nhu cầu checklist: confidence có thể xuất phát từ danh sách tiêu chí/features rõ ràng, nhưng nghiên cứu này **học trọng số từ correct/incorrect labels**, không chia đều theo số tiêu chí đạt.

## 3. DyGIE++: score riêng cho trigger, entity, argument và relation

[S2] David Wadden, Ulme Wennberg, Yi Luan, Hannaneh Hajishirzi (2019). *Entity, Relation, and Event Extraction with Contextualized Span Representations*. EMNLP-IJCNLP, 5784–5789.
- https://aclanthology.org/D19-1585/
- https://aclanthology.org/D19-1585.pdf
- Locator: Multi-task classification, PDF trang 3 / trang in 5786.

Span representation được đưa vào FFNN hai lớp:
- Trigger/named entity: `FFNN_task(g_i)`.
- Relation/argument role: `FFNN_task([g_i,g_j])`.

Khảo sát ACE05, SciERC, GENIA và WLPC: event/general news, scientific, biomedical và wet-lab protocol contexts. Cần tránh hiểu rằng mọi task đều có nhãn trên mọi corpus.

Ứng dụng WFKG: có thể lưu raw score cho eventType/trigger và từng required argument thay vì một số confidence do LLM tự khai báo. Bài cung cấp scoring architecture, **không cung cấp công thức chuẩn `min(required roles)` hay bộ bốn component của WFKG**, cũng không chứng minh những raw scores đã calibrated.

## 4. BLINK: confidence linking từ mention context và entity description

[S3] Ledell Wu, Fabio Petroni, Martin Josifoski, Sebastian Riedel, Luke Zettlemoyer (2020). *Scalable Zero-shot Entity Linking with Dense Entity Retrieval*. EMNLP, 6397–6407.
- https://aclanthology.org/2020.emnlp-main.519/
- https://aclanthology.org/2020.emnlp-main.519.pdf
- Locator: mục 4.1–4.3, PDF trang 3–4, equations 3/6/7.

Hai tầng:
1. Bi-encoder: `s(m,e) = y_m dot y_e`, retrieve candidate entities.
2. Cross-encoder: encode mention/context và entity description cùng nhau; linear layer sinh `s_cross(m,e)`; tối ưu softmax loss trên candidates.

Không đồng nhất dot product với confidence probability. Softmax trên retrieved candidates là relative distribution trên tập đó; nếu entity đúng không được retrieve, score cao vẫn có thể chọn sai. Cần đo candidate recall, linking correctness, abstention/NIL behavior và calibration riêng trong miền Việt Nam.

Bài dùng temperature trong **knowledge distillation**. Không được gọi phần đó là đã làm post-hoc confidence calibration: đây là hai mục đích khác nhau.

## 5. Calibration: đo score có phản ánh xác suất đúng hay không

[S4] Chuan Guo, Geoff Pleiss, Yu Sun, Kilian Q. Weinberger (2017). *On Calibration of Modern Neural Networks*. ICML, PMLR 70, 1321–1330.
- https://proceedings.mlr.press/v70/guo17a.html
- https://proceedings.mlr.press/v70/guo17a/guo17a.pdf
- Locator: mục 2, PDF trang 2–3; mục 4, PDF trang 5–6.

Calibration target: `P(prediction correct | predicted confidence=p) = p`.

Temperature scaling: `q_k = softmax(z/T)_k`; T dương được fit bằng NLL trên hold-out calibration/validation labels. Không thay đổi argmax khi chỉ scale logits bằng cùng T dương.

Các phương án được bài khảo sát: Platt scaling (`sigmoid(a*z+b)`), histogram binning và isotonic regression. Không có kết luận một method luôn tốt cho mọi domain/dataset.

Đo bằng reliability diagram và ECE:
`ECE = sum_b (n_b/N) * abs(accuracy_b - mean_confidence_b)`.
NLL bổ sung đánh giá chất lượng probabilistic predictions. ECE phụ thuộc bins và mẫu; không đủ một scalar để tuyên bố confidence đúng cho từng trường hợp.

Đối với WFKG, phải dùng **nhãn component correctness**, không phải CAR/market direction, làm calibration target cho extraction/linking. Fit calibration trong development với dedicated hold-out/cross-fitting phù hợp protocol, lock cấu hình trên validation, final test không dùng fit. Dataset tiếng Anh/corpus khác không chứng minh calibration cho tin tài chính tiếng Việt.

## 6. Knowledge-Based Trust: tách nguồn sai và extractor sai

[S5] Xin Luna Dong et al. (2015). *Knowledge-Based Trust: Estimating the Trustworthiness of Web Sources*. PVLDB 8(9), 938–949.
- Primary author manuscript: https://arxiv.org/abs/1502.03519
- Full text: https://arxiv.org/pdf/1502.03519
- Publisher PDF đã kiểm tra title/venue: https://www.vldb.org/pvldb/vol8/p938-dong.pdf
- Locator: mục 2.3–3.5, PDF trang 3–6; equations 5–9, 27–30.

Các đại lượng khác nhau:
- `A_w`: accuracy của web source.
- `C_wdv`: source có thực sự cung cấp triple hay không.
- `V_d`: giá trị đúng của data item.
- `R_e`: extractor recall.
- `Q_e`: xác suất extractor xuất một triple không được source cung cấp.

Joint model: `p(X,Z,theta)=p(theta)*p(V)*p(C|V,theta_source)*p(X|C,theta_extractor)`.

Source quality equation 28 là weighted average của posterior fact truth, trọng số là posterior source thực sự cung cấp fact:
`A_w = sum(p(C_wdv=1|X)*p(V_d=v|X)) / sum(p(C_wdv=1|X))` trên items hợp lệ trong estimation.

Các tham số source/extractor được estimate lặp theo EM-like procedure; không phải người chọn nhãn báo lớn = 0.9, báo nhỏ = 0.5. Bài cũng nêu giả định single truth và conditional independence, và khó khăn copying/correlation giữa sources. Không tự động chuyển mô hình Web-scale này thành score đáng tin cho vài nguồn/bài financial của vertical slice.

Ứng dụng tốt nhất hiện tại: lý do khoa học để giữ source quality và extraction correctness riêng. WFKG source=0.5 đang là experimental control, không phải kết quả KBT.

## 7. Nguồn metadata bổ sung, không suy rộng chi tiết chưa đọc

### Entity linking có nhiều evidence channels, không chỉ string matching

[S7] Octavian-Eugen Ganea, Thomas Hofmann (2017). *Deep Joint Entity Disambiguation with Local Neural Attention*. EMNLP, 2619–2629.
- https://aclanthology.org/D17-1277/
- https://aclanthology.org/D17-1277.pdf
- Đã đọc full-text sections 4–5, PDF trang 3–6.

Local score kết hợp attention-weighted context score với log mention–entity prior qua neural function: `Psi(e,m,c)=f(Psi(e,c),log p_hat(e|m))`, equation 6. Global model bổ sung pairwise entity coherence qua CRF. Học local model bằng max-margin loss, không phải đếm số tiêu chí PASS bằng nhau. Bài mô tả final local score là unnormalized; không gọi score này là calibrated probability.

Nguồn phù hợp để thiết kế linking checklist/features: alias/name evidence, context compatibility và document coherence là các kênh khác nhau. Type/cutoff correctness của WFKG vẫn là hard gates riêng; bài không quy định rubric financial Việt Nam.

[S6] Xin Luna Dong et al. (2014). *Knowledge Vault: A Web-Scale Approach to Probabilistic Knowledge Fusion*. KDD, 601–610.
- https://research.google/pubs/knowledge-vault-a-web-scale-approach-to-probabilistic-knowledge-fusion/

Đã đọc trang publication của Google: kết hợp extractions từ text/table/page structure/human annotations với prior knowledge, dùng supervised learning để fusion và tính calibrated fact-correctness probabilities. Link PDF trên trang Google dẫn đến nội dung không đúng bài khi fetch; alternate storage trả 403. Vì vậy **chưa xác minh full-text của bài này, không dùng nó làm căn cứ cho phương trình/feature weights cụ thể**. Các diễn giải kỹ thuật source/extractor ở trên dựa vào full-text S5, không vào S6.

## 8. Đối chiếu WFKG: bài báo hỗ trợ điều gì, không hỗ trợ điều gì

### Legal ontology papers: core semantics khác statistical term scores

[S10] Rinke Hoekstra, Joost Breuker, Marcello Di Bello, Alexander Boer (2007). *The LKIF Core Ontology of Basic Legal Concepts*. LOAIT, CEUR Vol. 321.
- https://ceur-ws.org/Vol-321/paper3.pdf
- Đã đọc PDF trang 1–3: generic legal knowledge interchange, OWL-DL/SWRL, concept definitions và inference. Trong phạm vi này bài không quy định bộ numeric confidence components cho từng assertion. Không dùng bài để nói mọi ontology luật không có confidence.

[S11] Alessandro Lenci, Simonetta Montemagni, Vito Pirrelli, Giulia Venturi (2007). *NLP-based ontology learning from legal texts. A case study.* LOAIT, CEUR Vol. 321.
- https://ceur-ws.org/Vol-321/paper7.pdf
- Đã đọc title, context và phương pháp scoring, PDF trang 8–10 / trang in 120–122: T2K khai thác văn bản pháp luật môi trường Italy. Candidate complex terms được xếp hạng theo log-likelihood ratio dựa trên joint/disjoint frequencies của lexical heads của chunks. Semantic-related terms dùng overlap giữa các bộ best verbs trong contextual distributions.
- Đây là statistical association/similarity scores, không phải calibrated probability rằng thuật ngữ hay legal relation là đúng. Bài cung cấp ví dụ pháp luật thực sự có scoring, nhưng scoring target khác bốn confidence WFKG.

### AMIE: empirical rule confidence từ số trường hợp trong KG

[S12] Luis Galárraga, Christina Teflioudi, Katja Hose, Fabian M. Suchanek (2013). *AMIE: Association Rule Mining under Incomplete Evidence in Ontological Knowledge Bases*. WWW.
- Author PDF: https://suchanek.name/work/publications/www2013.pdf
- Đã đọc mục Mining Model, PDF trang 4–5 và discussion confidence-versus-precision.

Với body B và head r(x,y), các counts tính trên distinct head pairs:
- `support = count(x,y satisfying B AND r(x,y))`.
- `standardConfidence = support / count(x,y satisfying B)`.
- `PCAConfidence = support / count(x,y satisfying B AND exists y': r(x,y'))`.

Standard confidence ngầm penalize unknown như false. PCA chỉ xét denominator theo giả định partial completeness: khi biết một r-value của subject thì coi đã biết hết r-values của nó (với orientation/functional assumptions của bài). Giả định này không tự đúng cho KG financial Việt Nam và temporal ownership.

Rule confidence dùng đánh giá regularity chung; không đồng nhất với confidence của một route instance cụ thể, càng không là xác suất giá cổ phiếu tăng. Không cần triển khai rule mining để tính confidence cho bốn route đã thiết kế cố định.

### ProbLog: query probability từ probabilistic facts và proofs

[S13] Luc De Raedt, Angelika Kimmig, Hannu Toivonen (2007). *ProbLog: A Probabilistic Prolog and its Application in Link Discovery*. IJCAI, 2462–2467.
- https://www.ijcai.org/Proceedings/07/Papers/396.pdf
- Đã đọc title/abstract/introduction; biological link discovery là application.

Xác suất query là tổng probability mass của các sampled subprograms/worlds làm query succeed. Paper giả định các selections của probabilistic clauses độc lập. Solver dùng Boolean formulas/BDDs để xử lý overlapping proofs, không cộng confidence từng proof một cách ngây thơ. Model inference không tự tạo nguồn dữ liệu để estimate probabilities đầu vào; input assumptions và validation vẫn cần tách riêng.

### Probabilistic Soft Logic: giải bài toán tối ưu nhiều soft rules

[S9] Stephen H. Bach, Matthias Broecheler, Bert Huang, Lise Getoor (2017). *Hinge-Loss Markov Random Fields and Probabilistic Soft Logic*. JMLR 18.
- https://arxiv.org/abs/1505.04406
- https://arxiv.org/pdf/1505.04406
- Đã đọc PDF sections 2.3–3.1, trang 8–11. Năm arXiv submission là 2015; full-text journal ghi Published 10/17, nên cite journal năm 2017.

Continuous variables nằm trong [0,1]; relaxed rules tạo distance-to-satisfaction penalties, có trọng số; MAP inference tối thiểu hóa tổng weighted hinge losses, kết hợp hard constraints riêng. Linear/squared hinge là lựa chọn model, weights có thể học. Weight diễn tả mức quan trọng tương đối của việc thỏa constraint, không phải trực tiếp xác suất fact đúng. PDF trang 9 nêu interpretations có thể là belief, confidence, ranking hoặc continuous quantity tùy ứng dụng; không gọi MAP value mặc định là calibrated correctness probability.

Đây là phương án kết hợp nhiều evidence/rules có nền tảng formal mạnh hơn checklist cộng đơn giản, nhưng triển khai/huấn luyện/kiểm chứng phức tạp hơn và không bắt buộc cho vertical slice WFKG.

### Ví dụ pháp luật: strength của luật không mặc định là numeric confidence

[S8, tiêu chuẩn chính thức, không phải paper] OASIS *LegalRuleML Core Specification Version 1.0*, bản OASIS Standard:
https://docs.oasis-open.org/legalruleml/legalruleml-core-spec/v1.0/os/legalruleml-core-spec-v1.0-os.html

Đã đọc trực tiếp glossary và sections 2.2–2.3, 4.2.1: strength là khả năng của luật chống rebuttal; strict/defeasible/defeater nói về semantics. Metadata giữ provenance, jurisdiction, authority và time. Không được chuyển StrictStrength thành probability=1 hay DefeasibleStrength thành 0.5. Đây là ví dụ cụ thể rằng hệ thống luật có thể xử lý độ chắc chắn bằng logic ưu tiên/ngoại lệ, không bằng bảng confidence bốn component. Tiêu chuẩn không phải bản đặc tả ontology pháp luật đầy đủ và không được viện dẫn như nghiên cứu đã đo numeric confidence.

| Component | Target đo được | Cách nghiên cứu có cơ sở | Giới hạn |
|---|---|---|---|
| sourceConfidence | Factual accuracy của nguồn, tách extraction noise | Knowledge-Based Trust; hoặc audited source facts trên gold độc lập | Không đủ dữ liệu thì giữ fixed control 0.5 như baseline, không giả vờ đã đo |
| extractionConfidence | Event assertion/type/required roles được trích đúng từ Evidence | Learned feature scorer kiểu REVERB; neural task scorers kiểu DyGIE++; calibration S4 | Model score không tự là probability; role-min là lựa chọn aggregation WFKG |
| linkingConfidence | Mention/reference ánh xạ đúng typed URI | Bi-/cross-encoder kiểu BLINK; deterministic curated registry mapping có provenance | Score phụ thuộc candidate coverage; registry 1 là convention không phải empirical certainty |
| relationConfidence | Evidence/facts hỗ trợ route đúng tại cutoff | Kiểm facts, mapping và rule semantics; learned rule confidence hoặc probabilistic reasoning trong note ontology | Fixed sound rule không chứng minh premises thật hay economic effect |

## 9. Checklist của người dùng: nên định vị thế nào?

`qualityScore = sum(w_j * pass_j) / sum(w_j)` là transparent rubric do dự án thiết kế. Trọng số bằng nhau là giả định của dự án, không phải tiêu chuẩn được các bài S1–S5 quy định. UNKNOWN lưu riêng, điều kiện hard gate tách khỏi soft score; không mặc định missing evidence là fact false.

Có hai hướng hợp lệ:
1. Rubric heuristic: version tiêu chí/PASS-FAIL, giữ evidence offsets và evaluator outputs; đánh giá agreement, correctness và ranking utility. Không gọi score là xác suất đúng.
2. Learned/calibrated scorer: biến checklist thành features, gán nhãn correct/incorrect độc lập, học logistic weights như tinh thần REVERB rồi kiểm tra calibration trên hold-out. Không sao chép features/weights tiếng Anh; cần features miền financial Việt Nam.

Việc `min` hoặc lấy trung bình bốn score không tạo joint calibrated probability. Min có thể là fuzzy/conservative bottleneck convention, không mặc định là xác suất mọi premise đều đúng. Scores extraction và relation của WFKG cùng dùng A nên có dependence; không nhân/cộng với giả định độc lập ngầm.

## 10. Đề xuất research-to-design (chưa sửa spec)

- Vertical slice: ưu tiên hard gates + rubric có provenance, gọi rõ heuristic nếu chưa có calibrated model.
- Nếu có logits/scorers: lưu raw score, model version và calibrator version; không chỉ lưu điểm cuối.
- Lưu row audit: target definition, input Evidence IDs/hash/offsets, component feature values, score origin (`CURATED`, `MODEL_RAW`, `CALIBRATED`, `HEURISTIC`, `FALLBACK`), timestamp/cutoff, original score và aggregation trace.
- Học/calibration trên component gold độc lập trong development; không dùng realised price/CAR để hiệu chỉnh extraction/linking.
- Kiểm riêng component accuracy/calibration và downstream ranking; một metric không thay thế metric khác.
- Giữ công thức baseline hiện hành đến khi có phê duyệt variant; đề xuất research không tự authorize thay 1.0.4.
