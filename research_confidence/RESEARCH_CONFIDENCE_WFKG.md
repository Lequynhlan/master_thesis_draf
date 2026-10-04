# Confidence components trong ontology/KG và LLM rubric — tổng hợp cho WFKG

## 1. Câu hỏi và phạm vi

Câu hỏi: hệ ontology pháp luật và KG ở domain khác sinh/đo confidence như thế nào; có cơ sở khoa học nào cho LLM chấm danh sách tiêu chí để tạo extractionConfidence/linkingConfidence/relationConfidence/sourceConfidence?

Đây là focused literature review có chủ đích, không phải systematic review hoặc thống kê độ phổ biến của phương pháp trong toàn bộ ngành. Nguồn ưu tiên bài gốc ở ACL Anthology, PMLR, author PDF và tiêu chuẩn chính thức. Chỉ dùng nguồn full-method để trích công thức; abstract-only được ghi rõ. Không chạy model, không xác minh chất lượng WFKG thực nghiệm, không sửa contract v1.0.4.

Ngữ cảnh: luận văn xây dựng Weighted Financial KG từ tin tài chính tiếng Việt, entity registry, daily prices/volumes; so sánh Vector RAG với Ontology RAG. NLP/LLM là công cụ, không đặt mục tiêu train nhiều model hoặc tự xây semantic rule engine.

## 2. Kết luận chính

1. Không có một công thức chuẩn chung của ontology để tính source/extraction/linking/relation confidence. Ontology xác định ý nghĩa/constraints; score thường do model, data fusion, probabilistic inference hoặc evaluator của ứng dụng sinh ra.
2. Tính hợp lệ schema/logic, ưu tiên pháp lý, statistical association, ordinal quality score và probability of correctness là những đại lượng khác nhau.
3. LLM rubric có cơ sở literature như G-Eval; phù hợp để nghiên cứu một heuristic scorer. Bài đó không chứng minh rubric WFKG đã calibrated, cũng không chứng minh per-role min là probability.
4. Các hệ probabilistic KG như Knowledge Vault có bước score fusion và calibration riêng bằng validation labels; không đơn thuần cộng/trung bình các số do model tự khai.
5. LLM self-evaluation/quote explanation có thể hữu ích nhưng không phải gold. Phải đo quan hệ giữa score và correctness trên annotation độc lập của domain đích.
6. Công thức baseline WFKG hiện tại có thể giữ như một composite ranking heuristic, nhưng không nên trình bày như công thức xác suất chuẩn của cộng đồng.

## 3. Các khái niệm thường bị gọi chung là confidence

| Đại lượng | Ví dụ | Cách hiểu đúng |
|---|---|---|
| Validity/conformance | RDF/SHACL pass, entity đúng type | Đúng cấu trúc/constraint, không chứng minh trích đúng văn bản |
| Rule priority/strength | strict vs defeasible; luật ưu tiên | Cơ chế giải quyết suy luận/xung đột, không P(extractor đúng) |
| Association/ranking score | similarity, log-likelihood ratio, neural logits | Mức ưu tiên, cần kiểm chứng/calibration nếu muốn dùng như probability |
| LLM rubric rating | supported/partial/unsupported hoặc 1–5 | Đánh giá của model theo tiêu chí, không empirical truth |
| Calibrated probability | predicted correctness phù hợp observed correctness | Cần target/gold và kiểm tra calibration ngoài dữ liệu fit |
| Market impact | normalized abs(CAR) | Phản ứng thị trường hậu nghiệm, không confidence NLP |

## 4. Ontology pháp luật: học được gì?

### 4.1 LKIF Core — Hoekstra et al., LOAIT 2007 [L1]

Bài *The LKIF Core Ontology of Basic Legal Concepts* xây legal conceptual schema, OWL-DL/SWRL, propositions, belief/assertion/evaluative attitudes, và đánh giá ứng dụng bằng formalizing EU driving licence directive. Full PDF đã đọc các phần introduction, methodology, concepts và evaluation.

Không xác định được trong bài này một công thức extraction/linking/source confidence tương ứng WFKG. Bài hữu ích để hiểu schema/semantics, không làm căn cứ khẳng định average S/A/L/R là legal-ontology standard. Kết luận giới hạn ở nguồn này, không nói mọi legal ontology đều không có numeric uncertainty.

### 4.2 LegalRuleML — Athan et al., 2015 và OASIS specification [L2, S1]

Chapter abstract đã đọc; full chapter subscription, chưa đọc. Standard full text §4.2.1 đã đọc: strict, defeasible, defeater, specificity/salience/superiority, Override.

Một legal rule có thể bị rule ưu tiên cao hơn đánh bại, chứ không nhất thiết được chấm 0.8 xác suất đúng. Phân biệt authority/lex superior/lex posterior với extraction support. Không áp dụng công thức probability từ abstract của chapter.

### 4.3 NLP-based ontology learning from legal texts — Lenci et al., LOAIT 2007 [L3]

T2K khai thác term/proto-concepts từ văn bản luật tiếng Ý. PDF p8 dùng log-likelihood ratio cho association của lexical-semantic heads trong chunks. P12–14 đánh giá bằng reference terminologies và manual checking; không kết luận recall vì references rộng hơn corpus.

Statistical association score không phải confidence từng role. Gold/reference assessment là một tầng khác với score phát sinh trong extraction.

### 4.4 OWL annotation [S2]

OWL2 Primer §8.1 nói annotation không thuộc logical meaning của ontology. Gắn annotation confidence lên axiom không tự tạo probabilistic reasoning. Đây là chuẩn bổ trợ, không phải bài báo research.

## 5. KG tự động: confidence đến từ model/fusion/calibration

### 5.1 Knowledge Vault — Dong et al., KDD 2014 [K1]

Full author PDF, §3.1–3.5 và §4 đã đọc.

- Text extraction: logistic regression theo predicate với distant supervision.
- DOM extraction: classifier output.
- Table/schema annotation: dùng entity-link confidence cho extracted triples.
- Fusion §3.2: feature vector gồm sqrt số nguồn và mean extraction scores từng extractor; classifier riêng theo predicate; boosted decision stumps dùng để học nonlinear relative reliability.
- Calibration §3.3: Platt scaling trên separate validation set; Figure1 reliability diagram kiểm tra predicted vs empirical correctness.
- De-dup evidence §3.5: đếm mỗi triple một lần mỗi domain, không mỗi URL.

Điều quan trọng: tác giả nói score của extractor/fused model không nhất thiết cùng scale hoặc có thể hiểu như probability trước calibration. Hệ này cũng không dùng equal-weight mean S/A/L/R của WFKG.

Target Knowledge Vault là correctness/truth của triple theo KB/LCWA assumptions. Target WFKG extraction nên là correctly supported assertion: trích đúng một rumor không đồng nghĩa rumor là true. Không đánh đồng hai targets.

### 5.2 Knowledge-Based Trust — Dong et al., 2015 [K2]

Full PDF p1, §2.2/2.3 và §5.1 đã đọc.

Tách lỗi source content khỏi extraction errors bằng multi-layer latent-variable model. Source accuracy khác extractor quality. Single-layer comparator dùng iterative EM-like posterior updates; multi-layer bổ sung latent source-content layer.

Đánh giá synthetic có truth cho source, extraction, triple; real data không có source-trust gold đầy đủ, chủ yếu đánh giá triple truth với square loss, calibration/deviation, AUC-PR và coverage. Vì vậy không thể chỉ thấy model confidence rồi khẳng định đã đo reliability source.

Ứng dụng WFKG: không hạ sourceConfidence vì LLM trích sai. Giữ source baseline hiện hành là hợp lý nếu chưa muốn triển khai source-trust research riêng.

## 6. LLM/model evaluator: cách chấm tiêu chí cụ thể

### 6.1 G-Eval — Liu et al., EMNLP 2023 [E1]

Full PDF §2, Eq(1), §3.1 và Table1 đã đọc.

Input gồm task definition, evaluation criteria, detailed evaluation steps, source/context và candidate output. Model thực hiện form-filling ratings theo aspect. Có thể dùng predefined scale 1–5.

Eq(1):

`score = Σ_i p(s_i) × s_i`

`s_i`: rating value định nghĩa trước; `p(s_i)`: normalized probability của output rating token, hoặc estimate từ sampling như setup GPT4 thời điểm bài viết. Đây là expected rating, không phải P(extraction correct).

§3.1: GPT4 trong setup của paper không có token probabilities nên dùng 20 samples với temperature1; đây là thiết lập paper năm2023, không phải yêu cầu triển khai WFKG hoặc tuyên bố capability API hiện tại. Không thay true token probabilities bằng số model tự viết trong JSON.

Table1: mean Spearman .514 với human SummEval ratings. Đây không phải extraction accuracy .514 và không chứng minh Vietnamese role extraction. Bài cũng cảnh báo preference toward LLM-generated text.

Ý nghĩa: hướng list criteria + LLM scorer có precedent; phải thiết kế criteria domain đích và validate riêng.

### 6.2 UniEval — Zhong et al., EMNLP 2022 [E2]

Full PDF §3.1–3.3 đã đọc. Chia mỗi evaluation dimension thành Boolean QA:

`score_i = P(Yes | output, reference, context, question_i) / (P(Yes | ...) + P(No | ...))`

Reference bỏ được ở dimension reference-independent. Model T5 có pseudo-data transformations và intermediate multi-task training; không phải chỉ prompt generic LLM rồi gọi đó là UniEval reproduction.

Giá trị cho WFKG: thay câu hỏi rộng “bạn chắc bao nhiêu?” bằng các câu hỏi rõ về type, role binding, assertion status và source support. Word-generation probability vẫn phải kiểm chứng trên target correctness trước khi gọi calibrated confidence.

### 6.3 FactCC — Kryściński et al., EMNLP 2020 [E3]

Đọc primary abstract, chưa đọc full methods. Bài mô tả classifier source-output consistency, source support span và inconsistent output span, với weak supervision bằng text transformations.

Chỉ dùng làm reference cho principle evidence-grounded consistency assessment; không trích công thức hoặc performance chưa đọc. Không cần thêm model FactCC vào pipeline chỉ vì literature có phương pháp này.

## 7. Calibration: đo score có đáng tin thế nào?

### Guo et al., ICML 2017 — On Calibration of Modern Neural Networks [C1]

Primary PMLR full PDF definitions và calibration discussion đã đọc. Calibration target:

`P(prediction correct | predicted confidence = p) = p`.

Accuracy cao không đảm bảo confidence đúng. Temperature scaling là post-processing trên classifier logits với held-out labels; Platt/logistic scaling và isotonic là các lựa chọn khác phù hợp loại score/data. Không cần train lại toàn LLM để thử một calibration mapping nhỏ, nhưng phải có target labels và đủ support.

Hai việc riêng:
1. Ranking utility: score cao có ưu tiên outputs đúng hơn không?
2. Probability calibration: nhóm có score quanh p có empirical correctness quanh p không?

Correlation/ROC/PR không chứng minh calibration; ECE/reliability diagram không thay thế extraction P/R/F1. ECE phụ thuộc binning/sample size; Brier đo probabilistic accuracy, không riêng calibration. Fit calibration trên development/calibration data, kiểm tra ngoài mẫu, freeze trước final test.

Với heuristic ordinal rubric chỉ tuyên bố quality/ranking score thì nên ưu tiên agreement/correctness by score band và risk–coverage; chưa báo Brier/ECE như evidence calibrated probability nếu chưa định nghĩa binary target hoặc có mapping probability hợp lệ.

## 7B. Bổ sung trực tiếp về ontology probabilistic, rule confidence và entity linking

Các nguồn dưới được nghiên cứu chuyên đề, sau đó đối chiếu trực tiếp lại primary PDF bằng HTTP fetch + PDF-header/title và các đoạn method liên quan. Không chỉ nhận summary của nhánh nghiên cứu.

### PR-OWL — da Costa, Laskey & Laskey, URSW2005 [O1]

Full PDF p4 mô tả tạo situation-specific Bayesian network từ MFrags, finding evidence và query nodes. Posterior target là degree of belief có điều kiện trên evidence và model; cần probability distributions và dependencies thực sự. Annotation confidence không thay thế Bayesian model. Phù hợp nếu cần probabilistic ontology semantics, nhưng triển khai sẽ vượt slice tối thiểu hiện tại.

### PSL/HL-MRF — Bach et al., JMLR2017 [O2]

Full PDF verified title và p9: MAP state có thể được diễn giải là degree of belief, confidence, ranking hoặc continuous variable tùy application. Weighted soft rules tạo hinge-loss energy, joint density proportional exp(-energy), MAP tìm optimum dưới constraints. Atom MAP value không tự là posterior marginal của Boolean fact; rule weight cũng không phải rule probability. Không có căn cứ viết Knowledge Vault sử dụng PSL.

### AMIE — Galárraga et al., WWW2013 [R1]

Full PDF §4 p4–5 đã đối chiếu trực tiếp. Standard rule confidence:

`conf(B ⇒ H) = count(distinct predicted pairs có head fact trong KB) / count(distinct pairs thỏa body)`.

PCA confidence thay denominator bằng những predictions thuộc vùng được giả định locally complete: nếu KB biết một r-value của x, giả định biết tất cả r-values của x. Đây là giả định nhằm xử lý KB không có negative facts; unknown không đồng nghĩa false. Rule confidence là empirical rule reliability dưới coverage assumptions, không posterior correctness của mỗi candidate. WFKG Event–Stock many-valued có thể không thỏa PCA: biết một stock liên quan không đảm bảo đã biết tất cả stock liên quan. Không cần thêm rule mining chỉ để có relationConfidence.

### BLINK — Wu et al., EMNLP2020 [EL1]

Full PDF §3–4 p3–4 đã đối chiếu. Entity retrieval dùng `s(m,e)=embedding(m) dot embedding(e)`; cross-encoder score là linear output `embedding(m,e) W`, trained softmax loss rồi rerank candidate set. Dot-product/logit là compatibility score, không empirical probability. Paper giả định in-KB gold entity và để NIL/out-of-KB cho future work. Softmax cao trong một candidate set sai không sửa được việc retrieval bỏ sót gold. Evaluation cần retrieval coverage, rerank và unresolved cases riêng, không chỉ score lớn.

### Nguyen & O'Connor — EMNLP2015 [N1]

Full PDF p8–9 đã đối chiếu cùng specialized notes về definitions/marginals. Coreference posterior samples được đưa qua event extraction, sinh distribution của event counts và credible intervals, thay vì lấy min/mean role probabilities. Bài nhấn mạnh đây chỉ là một nguồn uncertainty: parsing, factivity, semantic roles vẫn có errors khác. Đây là evidence sát structured NLP/event extraction, nhưng không proof all pipeline confidence đã calibrated.

## 7C. LLM self-report: không mặc định vô dụng, cũng không mặc định calibrated

### Tian et al., EMNLP2023 — Just Ask for Calibration [LC1]

Đối chiếu camera-ready ACL PDF p2–3 và specialized notes §2/Appendix B. Verbalized numerical/linguistic confidence của RLHF LMs có thể tốt hơn sampling-based model-probability comparators ở TriviaQA/SciQ/TruthfulQA. `Ling.1S-opt` fit mapping linguistic label → empirical accuracy trên calibration data, rồi evaluate ngoài phần fit. Gold answers có từ benchmark nhưng semantic equivalence được kiểm tra bằng GPT4/GPT3.5, nên không gọi mọi correctness label là human-independent verification.

Implication: không nên nói "LLM tự báo confidence luôn sai". Cũng không lấy kết quả short-form QA làm bảo đảm financial extraction tiếng Việt. Numeric rubric labels và verbal uncertainty phrases là khác prompt targets; chỉ mượn principle empirical mapping.

### Xiong et al., ICLR2024 — Can LLMs Express Their Uncertainty? [LC2]

Full PDF verified venue/title và method overview; specialized notes đọc prompting/sampling/aggregation và implementation appendix. Nghiên cứu nhiều task cho thấy verbal confidence thường overconfident; consistency/sampling/prompts có thể cải thiện nhưng không có method tốt nhất cho mọi task. Professional Law là MMLU QA, không legal ontology extraction. Hai bài LC1/LC2 có kết quả theo task/protocol khác nhau, không tạo quy luật universal và không mâu thuẫn đơn giản.

### Vì sao phải sửa lời đề xuất trước nghiên cứu?

- DIRECT=1 và CONTEXT=.8 là heuristic đề xuất của người thiết kế, không hệ số được các bài trên establish.
- Direct/indirect support là evidence category; contextual binding rõ có thể đúng không kém direct binding.
- Min-role/max-evidence và mean S/A/L/R là engineering aggregations. Nếu diễn giải p_roles là probability thật thì min không phải conservative lower bound cho all-correct joint probability: intersection không lớn hơn từng marginal. Không đổi thuật ngữ heuristic thành probability chỉ vì phép toán có output [0,1].
- Numeric self-report, normalized rating, yes/no generation probability và empirically calibrated correctness phải được ghi nhận là bốn loại khác nhau.

## 8. Map literature sang component WFKG

| Component | Target riêng | Phương pháp có precedent | Mức tối thiểu phù hợp luận văn |
|---|---|---|---|
| sourceConfidence | chất lượng/accuracy nội dung nguồn, không extraction | KBT latent truth/source estimation, empirical source audit | Giữ .5 control hiện hành; không LLM đo uy tín chỉ từ tên báo |
| extractionConfidence | type/state và required roles đúng theo Evidence | extractor classifiers + calibration; source consistency evaluator; LLM rubric | Một LLM extractor và rubric assessor nhỏ; lưu rating + quote; score heuristic variant, gold đánh giá riêng |
| linkingConfidence | mention/context ánh xạ đúng canonical typed entity | entity retrieval/reranking model; calibrated decision/abstention | registry alias + context; curated mapping convention hiện hành; ambiguous unresolved không tự cho1 |
| relationConfidence | path thực sự có support facts, endpoint/time đúng | probabilistic inference hoặc learned/statistical rule score | provenance/cutoff gates + path support heuristic; không đổi ontology rule pass thành probability1 |
| relationStrength | cường độ/ưu tiên kinh tế giả định | domain-specific heuristic/measurement | bảng baseline hoặc exposureRatio variant hiện hành; không trộn với correctness |
| impactScore | observed market response | event-study AR/CAR, normalization | công thức Reaction hiện hành; chỉ sau window |

Knowledge Vault/UniEval/G-Eval không chứng minh bốn component độc lập. Khi extraction score A dùng lại trong relationConfidence, đây là shared signal. Mean/min/product của correlated scores không tự tạo calibrated joint probability.

## 9. Khuyến nghị sau nghiên cứu — không mở rộng scope

### 9.1 Giữ mục tiêu

Vector RAG vs Ontology/Weighted KG RAG là comparison chính. Extraction/scoring là supporting pipeline; không triển khai PR-OWL/fuzzy ontology/source truth-discovery hoặc train evaluator mới nếu không cần.

### 9.2 Có thể dùng LLM rubric, nhưng gọi đúng tên

Method riêng: `LLM-assessed extraction support score`, uncalibrated. Đây là adaptation từ multi-dimensional/model-as-evaluator literature, không adoption nguyên xi G-Eval/UniEval.

Rubric tập trung correctness/support, không fluency/coherence của văn phong:
- eventType đúng dictionary;
- assertion state giữ phủ định/tin đồn/dự kiến/hoàn tất;
- từng required role đúng actor/object và đúng assertion;
- literals giữ đủ period/year/scope/unit, không tự điền;
- support quote có thật trong text;
- thiếu/contradiction/ambiguity được báo, không dùng fallback để tạo missing facts.

`DIRECT_SUPPORT` vs `CONTEXT_SUPPORT` là evidence category, chưa có proof rằng contextual extraction luôn kém đúng hơn. Có thể lưu làm audit feature; numeric .8 cho context chỉ là hypothesis phải đánh giá. Không chốt .8 chỉ vì nghe hợp lý.

### 9.3 Tránh aggregate gây che lỗi

Grounding/completeness/identity gates riêng, không để fluency hoặc những roles đúng bù role bắt buộc thiếu. Sau gate, min là weakest-link heuristic có thể thử; mean là quality average; learned aggregation cần labeled data. Literature này không cung cấp standard per-role min cho WFKG. Nếu giữ min/baseline average, gọi composite ranking signal và test utility/calibration target riêng.

### 9.4 Đánh giá tối thiểu

- LLM assessor đọc original article/Evidence + predicted assignment + dictionary, không gold/future prices.
- Same-model extractor/assessor có correlated bias, không gọi independent ground truth.
- Independent human gold cho type/state/roles; lấy đủ examples đúng/sai/mơ hồ, không chỉ direct-positive.
- Measure extraction P/R/F1/required-role-set accuracy và judge agreement, high-score errors, coverage/abstention.
- Repeated judge runs trên development subset để đo stability/cost; không coi temperature0 đảm bảo bit-identical.
- Freeze prompt/model/rubric/mapping trước final; raw response + config/hash để downstream replay.
- Chỉ thêm simple calibration nếu thật sự cần xác suất; nếu chưa đủ data, giữ honest heuristic.

### 9.5 Contract hiện tại

Đã đọc lại SCORING_SPEC1.0.4 trực tiếp: L14–20 cố định source reliability .5 và hoãn source-quality research; L54/L75 dùng .5 fallback cho present evidenced uncalibrated assignments; L73 curated mapping1 là convention; L75 đã ghi rõ shared/dependent signals và min/equal-average không calibrated joint probability. Vì vậy literature củng cố sự phân biệt mà contract hiện tại đã ghi, không chứng minh contract đang tuyên bố xác suất sai. Phần cần thiết kế/đánh giá thêm là cách sinh component scores phân hóa và utility của chúng. LLM rubric numeric variant sẽ thay đổi score provenance/assignment formula, nên method mới và sửa đặc tả có approval; nghiên cứu này chưa sửa file chuẩn. Không lấy literature làm sự phê duyệt automatic.

## 10. Bibliography và trạng thái đọc

[L1] Hoekstra, R.; Breuker, J.; Di Bello, M.; Boer, A. (2007). *The LKIF Core Ontology of Basic Legal Concepts*. LOAIT2007, pp43–63. Full PDF selected relevant sections: https://ceur-ws.org/Vol-321/paper3.pdf

[L2] Athan, T.; Governatori, G.; Palmirani, M.; Paschke, A.; Wyner, A. (2015). *LegalRuleML: Design Principles and Foundations*. DOI10.1007/978-3-319-21768-0_6. Publisher abstract/notes only: https://link.springer.com/chapter/10.1007/978-3-319-21768-0_6

[L3] Lenci, A.; Montemagni, S.; Pirrelli, V.; Venturi, G. (2007). *NLP-based ontology learning from legal texts. A case study.* LOAIT2007, pp113–129. Full PDF relevant method/evaluation sections: https://ceur-ws.org/Vol-321/paper7.pdf

[K1] Dong, X. L. et al. (2014). *Knowledge Vault: A Web-Scale Approach to Probabilistic Knowledge Fusion*. KDD2014, pp601–610. Google metadata + full author PDF: https://research.google/pubs/knowledge-vault-a-web-scale-approach-to-probabilistic-knowledge-fusion/ ; https://noon99jaki.github.io/publication/2014.kdd.pdf

[K2] Dong, X. L. et al. (2015). *Knowledge-Based Trust: Estimating the Trustworthiness of Web Sources*. Full author preprint selected method/evaluation sections: https://arxiv.org/abs/1502.03519 ; https://arxiv.org/pdf/1502.03519

[E1] Liu, Y.; Iter, D.; Xu, Y.; Wang, S.; Xu, R.; Zhu, C. (2023). *G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment*. EMNLP2023, pp2511–2522. Full PDF selected sections: https://aclanthology.org/2023.emnlp-main.153/

[E2] Zhong, M. et al. (2022). *Towards a Unified Multi-Dimensional Evaluator for Text Generation*. EMNLP2022, pp2023–2038. Full PDF §3: https://aclanthology.org/2022.emnlp-main.131/

[E3] Kryściński, W. et al. (2020). *Evaluating the Factual Consistency of Abstractive Text Summarization*. EMNLP2020. Abstract only: https://aclanthology.org/2020.emnlp-main.750/

[C1] Guo, C.; Pleiss, G.; Sun, Y.; Weinberger, K. Q. (2017). *On Calibration of Modern Neural Networks*. ICML2017, PMLR70, pp1321–1330. Full PDF selected sections: https://proceedings.mlr.press/v70/guo17a.html

[S1] OASIS (2021). *LegalRuleML Core Specification Version1.0*, §4.2.1. Standard, not research paper: https://docs.oasis-open.org/legalruleml/legalruleml-core-spec/v1.0/os/legalruleml-core-spec-v1.0-os.html

[S2] W3C (2012). *OWL2 Web Ontology Language Primer*, Second Edition, §8.1. Standard, not research paper: https://www.w3.org/TR/owl2-primer/#Annotating_Axioms_and_Entities

[O1] da Costa, P. C. G.; Laskey, K. B.; Laskey, K. J. (2005). *PR-OWL: A Bayesian Ontology Language for the Semantic Web*. URSW2005. Full method PDF: https://ceur-ws.org/Vol-173/paper3.pdf

[O2] Bach, S. H.; Broecheler, M.; Huang, B.; Getoor, L. (2017). *Hinge-Loss Markov Random Fields and Probabilistic Soft Logic*. JMLR18(109):1–67. Full PDF selected relevant paragraphs verified: https://arxiv.org/abs/1505.04406 ; https://arxiv.org/pdf/1505.04406

[R1] Galárraga, L.; Teflioudi, C.; Hose, K.; Suchanek, F. M. (2013). *AMIE: Association Rule Mining under Incomplete Evidence in Ontological Knowledge Bases*. WWW2013. DOI10.1145/2488388.2488425. Full §4 source: https://suchanek.name/work/publications/www2013.pdf

[EL1] Wu, L.; Petroni, F.; Josifoski, M.; Riedel, S.; Zettlemoyer, L. (2020). *Scalable Zero-shot Entity Linking with Dense Entity Retrieval*. EMNLP2020, pp6397–6407. Full §3–4: https://aclanthology.org/2020.emnlp-main.519/

[N1] Nguyen, K.; O'Connor, B. (2015). *Posterior calibration and exploratory analysis for natural language processing models*. EMNLP2015, pp1587–1598. Full event-extraction sections: https://aclanthology.org/D15-1182/

[LC1] Tian, K. et al. (2023). *Just Ask for Calibration: Strategies for Eliciting Calibrated Confidence Scores from Language Models Fine-Tuned with Human Feedback*. EMNLP2023, pp5433–5442. Camera-ready selected sections: https://aclanthology.org/2023.emnlp-main.330/

[LC2] Xiong, M. et al. (2024). *Can LLMs Express Their Uncertainty? An Empirical Evaluation of Confidence Elicitation in LLMs*. ICLR2024 (preprint2023). Full primary PDF relevant paragraphs: https://arxiv.org/abs/2306.13063

Chi tiết kiểm chứng nguồn được lưu trong `legal_ontology_crosscheck.md` và `fusion_and_rubric_crosscheck.md`. Báo cáo specialized đã đọc lại và đối chiếu nguồn được lưu cạnh báo cáo này: `ontology_uncertainty_primary.md`, `ie_linking_calibration_primary.md`, `llm_rubric_primary.md`. Các nghiên cứu supplementary trong specialized notes không đều được đọc lại toàn bộ từ đầu ở synthesis; phạm vi đọc được chỉ rõ trong từng phần. Không chạy/tái lập experiment bài gốc hoặc calibration WFKG.
