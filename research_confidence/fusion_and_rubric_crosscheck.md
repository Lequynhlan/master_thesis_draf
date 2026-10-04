# Kiểm chứng sâu: Knowledge Vault, Knowledge-Based Trust và G-Eval

Research-only; không chỉnh contract. Các method dưới đọc trực tiếp từ PDF nguồn tác giả/venue, có page/section. Phân biệt công thức bài báo với đề xuất WFKG.

## A. Dong et al. (KDD 2014), Knowledge Vault: A Web-Scale Approach to Probabilistic Knowledge Fusion

Primary publisher/organization page:
https://research.google/pubs/knowledge-vault-a-web-scale-approach-to-probabilistic-knowledge-fusion/

Full author PDF đã đọc:
https://noon99jaki.github.io/publication/2014.kdd.pdf

HTTP 200, Content-Type application/pdf, bytes bắt đầu %PDF, PDF 10 trang. Google page dẫn old CMU link http://www.cs.cmu.edu/~nlao/publication/2014.kdd.pdf nhưng link cũ redirects sang homepage HTML. Không dùng HTML đó làm full paper; đã tìm href publication/2014.kdd.pdf tại homepage mới và verify title trên p1.

§3.1.1 PDF p3: NER, dependency/co-reference, entity linking trước relation extraction. Distant-supervision examples và local closed-world labels; logistic regression riêng từng predicate.

§3.1.2 p4: DOM extractor score là output classifier. §3.1.3/3.1.4 p4: table/schema.org extractor dùng named entity linkage confidence. Vì vậy không phải mọi component là độc lập; một score có thể tái sử dụng linking signal.

§3.2 p4: fusion feature vector gồm, cho mỗi extractor, sqrt(number of sources) và mean extraction score across sources (0 nếu không output). Initial logistic fusion được thay bởi boosted decision stumps có performance tốt hơn. Mỗi predicate có classifier riêng để học relative reliabilities.

§3.3 p4: raw confidence không cùng scale và chưa chắc là probability. Platt scaling fit logistic model trên separate validation set. Reliability diagram Figure1 so predicted vs empirical correctness. Đây là bằng chứng trực tiếp rằng chỉ ép [0,1] không đủ calibration.

§3.5 p5: đếm mỗi triple một lần mỗi domain thay vì URL để giảm overcount; không cộng tất cả bài như independent facts.

§4 p5–6: graph priors PRA/path features và neural model; §4.3 dùng fusion/calibration riêng. Không phải equal-weight mean S/A/L/R.

Target là triple truth/correctness theo Freebase + LCWA, có assumptions về KB missingness. WFKG target extraction phải là đúng assertion được bài hỗ trợ, kể cả rumor/negated statements; không trực tiếp dùng triple factual truth để chấm rumor extraction sai.

## B. Dong et al. (2015), Knowledge-Based Trust: Estimating the Trustworthiness of Web Sources

Primary full PDF: https://arxiv.org/pdf/1502.03519
Primary metadata: https://arxiv.org/abs/1502.03519

HTTP 200, verified %PDF, 12 pages; đọc p1, §2.2/2.3 p3 và §5.1 p8.

P1 định nghĩa source trustworthiness là probability nguồn cung cấp đúng value cho fact nếu nguồn đề cập value đó, không phải source popularity/PageRank.

§2.3 phân biệt:
1. đúng extraction, fact đúng;
2. đúng extraction, fact nguồn sai;
3. sai extraction dù fact thực tế đúng;
4. sai extraction và fact sai.

Multi-layer probabilistic model có latent true value V_d, latent source content C_wdv, source accuracy A_w và extractor quality parameters. Không nên phạt website vì lỗi extractor.

§2.2 overview SINGLE-LAYER comparator, KHÔNG công thức toàn multi-layer method:
A_s^(t+1) = sum_d sum_v I(X_sdv=1) P(V_d=v | X_d,A^t) / sum_d sum_v I(X_sdv=1).
Nghĩa là average posterior correctness của các values source/extractor pair đưa ra. Paper trình bày iterative EM-like updates. Multi-layer sửa việc trộn source và extractor pair.

§5.1 p8: trên synthetic có truth cho extraction/triple/source, dùng square loss cho ba targets riêng. Trên real không có gold source trust đầy đủ, chủ yếu evaluate triple truth; WDev bin predicted probabilities và so với gold bucket accuracy, AUC-PR và coverage. Không biến global source accuracy thành per-role extraction score.

Nguồn này hỗ trợ tách sourceConfidence/extractionConfidence, KHÔNG chứng minh cần triển khai web-scale iterative truth discovery trong luận văn.

## C. Liu, Iter, Xu, Wang, Xu, Zhu (EMNLP 2023), G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment

Primary metadata: https://aclanthology.org/2023.emnlp-main.153/
Primary full PDF: https://aclanthology.org/2023.emnlp-main.153.pdf

HTTP 200, full PDF loaded; đọc PDF p1–5, tương ứng proceedings pp2511–2515.

§2: prompt định nghĩa task + criteria; detailed evaluation steps; form-filling rating cho mỗi aspect. Ví dụ coherence 1–5; summarization criteria gồm coherence/consistency/fluency/relevance. KHÔNG sao chép fluency/coherence làm extraction correctness trong WFKG.

Eq(1) PDF p3:
score = sum_i p(s_i) * s_i,
trong đó s_i là predefined rating value, p(s_i) là normalized score-output token probability (hoặc estimate từ samples). Đây là expected rating, không phải P(extraction correct).

§3.1 p3–4: GPT-3.5 dùng token probabilities, temperature0; GPT-4 thời điểm paper không xuất token probabilities nên sample n20, temperature1, top_p1 để estimate. Không nói mọi deployment hiện tại có logprob, không dùng lời LLM tự khai p(s_i) như logprob.

Table1 p4: G-EVAL-4 average Spearman rho .514 trên SummEval, individual consistency rho .507. Đây là task-specific correlation với human ratings, không 51.4% extraction accuracy. Bài cảnh báo preference/bias toward LLM-generated text.

WFKG có thể adapt rubric/form-filling approach, nhưng eventType/role binding/normalization support criteria và numeric mapping phải thiết kế, đóng băng, đánh giá riêng trên tiếng Việt. Đọc paper này không có nghĩa 1.0 direct / .8 context / min components được tác giả chứng minh.

## D. Zhong et al. (EMNLP 2022), Towards a Unified Multi-Dimensional Evaluator for Text Generation — UniEval

Primary metadata: https://aclanthology.org/2022.emnlp-main.131/
Primary full PDF: https://aclanthology.org/2022.emnlp-main.131.pdf

HTTP200, verified %PDF; đọc PDF p1–4, proceedings pp2023–2026. §3.1 p3 Eq(1) quy mỗi dimension thành Boolean QA; score_i = P(Yes | x,y,c,q_i) / [P(Yes | x,y,c,q_i) + P(No | x,y,c,q_i)]. P là model output-word probability, không lời model tự khai. Reference y có thể bỏ với source-consistency task. §3.2 dùng T5 training trên pseudo positive/negative data từ transformations (entity replacement, numerical editing, antonym substitution,...); §3.3 intermediate multi-task training. Không phải chỉ prompt một generic model là tái hiện UniEval.

Score là normalized yes/no model preference cho evaluation dimension. Cần validate/calibrate trên target task trước khi gọi empirical correctness probability. Có thể tham khảo cách chia câu hỏi semantic từng tiêu chí cho WFKG, không yêu cầu train UniEval mới hoặc chuyển ontology.

FactCC primary abstract được đọc (chưa đọc full method): https://aclanthology.org/2020.emnlp-main.750/ — Kryściński et al., Evaluating the Factual Consistency of Abstractive Text Summarization (EMNLP2020). Abstract mô tả joint consistency classification + source support span + inconsistent output span, weakly supervised transformed data; chỉ dùng làm nguồn phụ cho principle source-grounded assessment, không trích công thức/metrics chưa đọc.
