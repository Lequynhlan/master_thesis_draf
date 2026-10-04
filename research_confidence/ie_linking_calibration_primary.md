# Nguồn primary về confidence trong extraction, entity linking và calibration — đối chiếu WFKG

## 1. Kết luận dùng được ngay

- **Logit, dot-product, softmax probability và log-likelihood là những đại lượng khác nhau; không đại lượng nào tự động là xác suất đúng đã được calibration.** Guo et al. [P1] và Knowledge Vault [P5] nói trực tiếp về khác biệt này. BLINK [P2] cung cấp điểm retrieval/reranking và softmax training, không chứng minh điểm linking được calibration.
- **Có primary evidence sát IE/KG:** Knowledge Vault calibration extractor/fusion bằng Platt scaling trên validation set [P5, §3.3]; Nguyen–O’Connor đánh giá calibration của NLP cấu trúc rồi truyền uncertainty coreference sang event extraction bằng posterior sampling [P6, §§5–6]. Hai bài này phù hợp hơn việc chỉ viện dẫn một bài image classification.
- **Không thấy trong sáu bài được đọc cơ sở cho công thức WFKG `confidenceScore = (S + A + L + R)/4`, hoặc extraction `max_e min_role score(e,role)`, như một xác suất event đúng.** Chúng có thể là quy tắc engineering minh bạch, nhưng không nên trình bày là công thức calibration được literature chứng minh. Đây là kết luận giới hạn ở corpus sáu bài, không phải tuyên bố đã rà soát toàn bộ literature.
- **`min` không phải lower bound cho xác suất tất cả role đều đúng:** với các xác suất biên thực sự, nó là upper bound của intersection. `max` trên evidence cũng không phải posterior fusion. Trung bình các component là chỉ số tổng hợp có tính bù trừ, không phải xác suất tất cả component cùng đúng.
- **Baseline 0.5 khi chưa calibration, curated linking = 1 và số confidence do LLM tự khai là các convention của WFKG**, không được những bài này xác lập thành empirical probability. Nhãn trạng thái “chưa calibration” không mất đi khi đưa các số này vào trung bình.

Phạm vi: research-only; không sửa specification hoặc implementation. Ký hiệu S/A/L/R và quy tắc WFKG dưới đây lấy từ ngữ cảnh nhiệm vụ, chưa được kiểm tra với code/spec. Đối chiếu dùng S = source reliability, A = extraction, L = linking, R = relation; nếu tên chính thức của A khác thì cần đổi nhãn, không đổi các phân biệt thống kê. Không bàn thị trường hay dự báo tương lai.

## 2. Corpus primary đã fetch và đọc

Các PDF sau đều được fetch thành công HTTP 200, parse bằng PyMuPDF trong bộ nhớ và đọc phần phương pháp liên quan; không chỉ dựa vào abstract. URL được kiểm tra theo nội dung PDF, không coi HTTP 200 là đủ chứng minh tải đúng bài.

| ID | Title, tác giả, năm/venue đã xác minh | Nguồn primary và phần đọc chính |
|---|---|---|
| P1 | **On Calibration of Modern Neural Networks** — Chuan Guo, Geoff Pleiss, Yu Sun, Kilian Q. Weinberger; **2017, ICML, PMLR 70** | [Trang proceedings](https://proceedings.mlr.press/v70/guo17a.html); [PDF đã fetch](https://proceedings.mlr.press/v70/guo17a/guo17a.pdf), 10 trang. Đọc definitions, ECE/NLL, §§4.1–4.2, đặc biệt Eq. (3), (6), (9). |
| P2 | **Scalable Zero-shot Entity Linking with Dense Entity Retrieval** — Ledell Wu, Fabio Petroni, Martin Josifoski, Sebastian Riedel, Luke Zettlemoyer; **2020, EMNLP**, pp. 6397–6407 | [ACL record](https://aclanthology.org/2020.emnlp-main.519/); [PDF đã fetch](https://aclanthology.org/2020.emnlp-main.519.pdf), 11 trang. Đọc task assumptions và §§4.1–4.3, Eq. (1)–(10). Đây là bài BLINK, không phải một bài có title chỉ là “Dense Entity Retrieval”. |
| P3 | **Calibration of Pre-trained Transformers** — Shrey Desai, Greg Durrett; **2020, EMNLP**, pp. 295–302 | [ACL record](https://aclanthology.org/2020.emnlp-main.21/); [PDF đã fetch](https://aclanthology.org/2020.emnlp-main.21.pdf), 8 trang. Đọc §3, §4.4, Tables 3–4. |
| P4 | **Selective Classification for Deep Neural Networks** — Yonatan Geifman, Ran El-Yaniv; **2017** | [arXiv record](https://arxiv.org/abs/1705.08500); [PDF đã fetch](https://arxiv.org/pdf/1705.08500), 12 trang, bản v2 ghi June 2017. Đọc §§2–3, Eq. (1)–(4), Algorithm 1 và Theorem 3.2. Dẫn theo bản arXiv đã đọc; không dùng record này để xác minh riêng proceedings venue. |
| P5 | **Knowledge Vault: A Web-Scale Approach to Probabilistic Knowledge Fusion** — Xin Luna Dong, Evgeniy Gabrilovich, Geremy Heitz, Wilko Horn, Ni Lao, Kevin Murphy, Thomas Strohmann, Shaohua Sun, Wei Zhang; **2014, KDD** | [Google Research record đã fetch](https://research.google/pubs/knowledge-vault-a-web-scale-approach-to-probabilistic-knowledge-fusion/); [PDF từ trang tác giả Kevin Murphy, đã fetch](https://www.cs.ubc.ca/~murphyk/Papers/kv-kdd14.pdf), 10 trang. Đọc §§2.2, 3.1–3.5, 4.3, 5, 6 và đoạn limitations §8. |
| P6 | **Posterior calibration and exploratory analysis for natural language processing models** — Khanh Nguyen, Brendan O’Connor; **2015, EMNLP**, pp. 1587–1598 | [ACL record](https://aclanthology.org/D15-1182/); [PDF đã fetch](https://aclanthology.org/D15-1182.pdf), 12 trang. Đọc §§2–6, Algorithms 1–2, Definition 2 và Eq. (2)–(5). Xác minh title/link thêm từ danh mục [EMNLP 2015](https://aclanthology.org/events/emnlp-2015/) đã fetch. |

**Độ sát bài toán:** P2 là entity linking; P5 là extraction + KG fusion có calibration; P6 có event extraction và uncertainty propagation. P1 là nền tảng calibration (vision và document classification); P3 là NLI/paraphrase/commonsense classification, không trực tiếp event-role extraction; P4 là selective classification trên vision, chỉ là nguyên lý tham khảo cho abstention, không phải một selective-IE experiment.

## 3. Các công thức thực sự được document

### 3.1 Guo et al.: confidence cần kiểm chứng, không chỉ softmax [P1]

Bài phân biệt class prediction và confidence. Điều kiện top-label calibration là:

\[
\Pr(\widehat Y=Y\mid\widehat P=p)=p.
\]

Ý nghĩa: trên quần thể các dự đoán có confidence p, tỷ lệ đúng tương ứng phải là p; không phải lời bảo đảm riêng cho một record.

Trong §4.2, logits là vector chưa chuẩn hóa \(z_i\), softmax là:

\[
 p_i^{(k)}=\frac{\exp z_i^{(k)}}{\sum_j\exp z_i^{(j)}},\qquad
 \widehat p_i=\max_k p_i^{(k)}.
\]

Temperature scaling, Eq. (9):

\[
 q_i^{(k)}=\operatorname{softmax}(z_i/T)^{(k)},\qquad
 \widehat q_i=\max_k q_i^{(k)},\quad T>0.
\]

T được tối ưu theo negative log-likelihood trên validation set, không huấn luyện lại network. Phép chia mọi logit trong cùng ví dụ cho cùng T > 0 giữ nguyên argmax/class accuracy. Đây là post-hoc calibration; lựa chọn T tùy ý hoặc dùng T cho distillation không đồng nghĩa đã calibration.

NLL, Eq. (6), và ECE, Eq. (3):

\[
 L=-\sum_i\log\widehat\pi(y_i\mid x_i),\qquad
 \mathrm{ECE}=\sum_m\frac{|B_m|}{n}\left|\operatorname{acc}(B_m)-\operatorname{conf}(B_m)\right|.
\]

Trong đó acc là trung bình indicator dự đoán đúng; conf là trung bình confidence **trên các record trong cùng bin**. Đây không phải trung bình các role trong một event. ECE phụ thuộc binning và không chứng minh calibration mọi subgroup/role/domain.

Platt scaling ở §4.1 học \(q_i=\sigma(a z_i+b)\) bằng NLL trên validation set. Isotonic regression là lựa chọn phi tham số được bài so sánh. Không được gọi một sigmoid với tham số tự đặt là “đã calibration”.

### 3.2 BLINK: điểm entity retrieval và linking [P2]

Bi-encoder encode mention/context và description entity độc lập thành \(y_m,y_e\), dùng dot-product, Eq. (3):

\[
 s(m,e_i)=y_m\cdot y_{e_i}.
\]

Đây là ranking score thực, không bị giới hạn [0,1]. Loss trên batch, Eq. (4):

\[
 L(m_i,e_i)=-s(m_i,e_i)+\log\sum_{j=1}^{B}\exp s(m_i,e_j).
\]

Bài dùng in-batch negatives và thêm hard negatives. Cross-encoder đọc mention/context và entity chung, dùng linear scoring, Eq. (6):

\[
 s_{\mathrm{cross}}(m,e)=y_{m,e}W.
\]

Cross-encoder tối ưu softmax loss tương tự và rerank tập nhỏ candidate do bi-encoder lấy về. Nếu chuyển logits reranking thành softmax, phân phối là **trên tập candidate đó**: confidence có thể cao dù gold entity đã bị retrieval bỏ sót. Bài giả định gold mentions và mỗi mention có gold entity trong KB; NIL/out-of-KB được để ngoài phạm vi (§3). Vì vậy không thể lấy linking accuracy/softmax của BLINK làm xác suất end-to-end extraction + linking đúng.

Eq. (7)–(10) dùng softmax với temperature cho **knowledge distillation**, teacher cross-encoder sang student bi-encoder. Không phải temperature được fit để calibration trên nhãn correctness theo P1. Không thấy thí nghiệm ECE/reliability plot/post-hoc calibration trong phương pháp BLINK đã đọc.

### 3.3 Desai–Durrett: calibration phải xét domain [P3]

Bài khảo sát BERT/RoBERTa trên NLI, paraphrase detection, commonsense reasoning, với cả in-domain và out-of-domain. §4.4 dùng temperature scaling trên development set in-domain rồi đánh giá cả hai loại test set.

Label smoothing của bài phân phối target thành:

\[
 y_{\mathrm{gold}}=1-\alpha,\qquad
 y_{\mathrm{other}}=\frac{\alpha}{|\mathcal Y|-1}.
\]

Không được đổi công thức của bài thành chia \(\alpha/|\mathcal Y|\) rồi vẫn ghi là công thức tác giả dùng. Kết quả phân biệt: temperature-scaled MLE hoạt động tốt in-domain; label smoothing thường hữu ích hơn khi shift mạnh. Đây là kết quả thực nghiệm trên các task của bài, không phải bảo đảm cho financial/event IE hoặc entity linking của WFKG.

### 3.4 Selective classification: ranking confidence đủ để xét reject, không đủ để gọi probability [P4]

Với classifier f và selection function g:

\[
 \phi(f,g)=\mathbb E[g(X)],\qquad
 R(f,g)=\frac{\mathbb E[\ell(f(X),Y)g(X)]}{\phi(f,g)}.
\]

Coverage \(\phi\) là tỷ lệ không reject; R là risk trên những dự đoán được chấp nhận, không phải risk toàn bộ đầu vào. Thresholding, Eq. (3):

\[
 g_\theta(x)=\mathbf1[\kappa_f(x)\ge\theta].
\]

Bài không đòi \(\kappa\) là calibrated probability. SGR sắp xếp confidence, binary-search threshold, dùng upper risk bound dựa trên binomial tail; Algorithm 1 điều chỉnh mức \(\delta\) theo số vòng tìm kiếm. Bảo đảm của tác giả đặt trong giả định labeled sample i.i.d. từ cùng distribution. Không được chuyển thành “WFKG dùng threshold này nên event nào được nhận cũng có confidence đúng bằng score”, hoặc áp dụng bảo đảm đó nguyên xi khi dữ liệu shift/chung nguồn/copied records.

### 3.5 Knowledge Vault: fusion học từ dữ liệu, không trung bình S/A/L/R [P5]

Pipeline gồm extractors, graph-based priors và knowledge fusion. TXT extractor dùng NLP gồm NER, parsing, coreference và entity linkage, rồi distant supervision + logistic regression riêng theo predicate. TBL/ANO có score phản ánh confidence của entity-linkage system; vì vậy score các module đã có thể chứa uncertainty chồng lấp.

§3.2 định nghĩa feature cho mỗi extractor j bằng **căn bậc hai số source** và **mean extraction score qua source**. Viết lại bằng ký hiệu thống nhất, không phải một numbered equation nguyên văn của bài:

\[
 f_j(t)=\big(\sqrt{n_j(t)},\ \overline{s}_j(t)\big),\qquad
 \overline{s}_j(t)=\frac{1}{n_j(t)}\sum_{u=1}^{n_j(t)}s_{j,u}(t)
\]

khi có extraction; bài mô tả mean score bằng 0 nếu extractor không tạo triple đó. Fusion classifier riêng theo predicate ban đầu là logistic regression; boosted decision stumps cho kết quả tốt hơn. **Mean là feature đi vào classifier học được, không phải final confidence.** Model học relative reliability của **extractor/system** và predicate; không phải bảng fixed source-authority score S cho từng website.

§3.3 nói rõ scores từ extractor/fused system “not necessarily on the same scale” và “cannot necessarily be interpreted as probabilities”; dùng Platt scaling — logistic regression fit scores trên validation set riêng. §4.3 fusion priors thêm indicator missingness, phân biệt thiếu prediction với score 0. §5 kết hợp priors và extraction bằng cách fusion học được tương tự §3.2.

§3.5 đếm triple tối đa một lần mỗi domain thay vì mỗi URL, để hạn chế over-counting; footnote §3.2 nói có source deduplication trước extraction. Điều này **giảm** trùng lặp, không chứng minh các domain độc lập. §8 thừa nhận coi từng fact là binary random variable độc lập vì scalability, trong khi các fact thực tế có thể correlated/mutually constrained.

Nhãn train/test dùng local closed world assumption (§2.2), không hoàn toàn là ground truth: thiếu triple không luôn đồng nghĩa false. §6 so sánh human labels và LCWA; AUC khi dùng human labels thấp hơn. Vì vậy claim “calibrated” của bài phải đọc cùng protocol/nhãn của nó, không suy ra mọi score đúng với factual truth trong mọi domain.

### 3.6 Nguyen–O’Connor: structural uncertainty và event extraction [P6]

§2 định nghĩa calibration trên binary prediction q và label y; dùng Brier loss và RMS calibration error:

\[
 L_2=\frac1N\sum_i(y_i-q_i)^2,\qquad
 \mathrm{CalibErr}=\sqrt{\mathbb E_q\,[q-\Pr(y=1\mid q)]^2}.
\]

Algorithm 1 dùng adaptive/equal-count binning và tính:

\[
 \widehat{\mathrm{CalibErr}}=
 \sqrt{\frac1N\sum_b|B_b|(\overline q_b-\overline y_b)^2}.
\]

Đây là RMS calibration error, **không phải ECE absolute-gap của P1**. Bài đánh giá single-token và consecutive-tag-pair marginals của HMM/CRF bằng forward–backward (§4.2), cho thấy cần kiểm tra đúng loại query/structure được dùng downstream.

Definition 2, §5: antecedent selection \(a_i\) có local log-linear distribution; sample các antecedent rồi lấy connected components để tạo coreference clustering e. Model cụ thể có factorization \(P(a\mid x)=\prod_iP(a_i\mid x)\), nhưng các query về cluster qua transitive closure không trở thành những biến role độc lập.

Eq. (2), §5.3 tính marginal probability hai mention coreferent bằng:

\[
 P(\ell_{ij}=1\mid x)=\sum_e\mathbf1[(i,j)\text{ thuộc cùng cluster trong }e]\,P(e\mid x).
\]

Ước lượng Monte Carlo lấy tỷ lệ samples có hai mention cùng cluster. §6 **chạy lại event extraction trên nhiều coreference samples**, tạo posterior distribution của event counts, thay vì lấy min/mean của role scores. Quy tắc count có document-level OR và aggregate sum (Eq. (3)–(5)); mean/credible interval cuối cùng là summary của distribution samples, không phải average confidence các role.

Giới hạn quan trọng: ví dụ này cô lập uncertainty coreference; dependency parsing, lexicon/rules và các nguồn lỗi khác không được tất cả marginalize. Calibration coreference tốt không chứng minh cả event extraction đã calibration. Không đổi credible interval của event count thành probability một event record đúng.

## 4. Score taxonomy cho WFKG

| Đại lượng | Diễn giải hợp lệ | Điều không được suy ra |
|---|---|---|
| Logit hoặc BLINK dot-product | Điểm compatibility/ranking trước normalization; cần biết model và candidate set [P1–P2] | Không thể trực tiếp trung bình với source score [0,1] rồi gọi probability |
| Softmax/sigmoid probability | Model-normalized distribution theo label/candidate space [P1–P2] | Nằm [0,1] không đủ xác lập empirical probability of correctness |
| Log-probability/log-likelihood | Log của model probability cho một label/output; NLL là objective/quality metric [P1, Eq. (6)] | Không phải confidence [0,1]; low NLL không tự động chứng minh mọi subgroup calibrated |
| Calibrated confidence | Probability đã có fitting/evaluation với correctness labels và population xác định [P1, P3, P5] | Không có bảo đảm transferable tự động sang domain/model/ontology mới |
| Numeric self-report của LLM | Một số được sinh ra dưới prompt; có thể xem là heuristic để nghiên cứu sau | Không phải logits/token probability hay calibrated factual probability; sáu bài không xác lập conversion này |
| Curated/rule-based score | Convention phản ánh trạng thái quy trình hoặc deterministic matching | Score 1 không đồng nghĩa không thể sai về alias, entity identity, context hoặc validity |

**Làm rõ log-likelihood cho generative extraction — định nghĩa xác suất tổng quát, không gán cho BLINK:** nếu extractor sinh chuỗi y, chain rule cho \(\log P(y\mid x)=\sum_t\log P(y_t\mid y_{<t},x)\). Tổng này đánh giá độ model cho chuỗi token/serialization, chịu tác động độ dài; không mặc nhiên là xác suất fact/role đúng. Trung bình log-probability theo token là length-normalized score, không phải phép calibration. Muốn dùng làm correctness confidence cần validation mapping riêng. P1 document NLL cho classification, **không document công thức “LLM sequence likelihood = event truth”**.

## 5. Per-role min, max-evidence và averages: mức literature support

### 5.1 Extraction của WFKG

Quy tắc được cung cấp trong nhiệm vụ có thể diễn đạt:

\[
 A(v)=\max_{e\in\mathcal E_{\mathrm{complete}}(v)}\min_{r\in\mathcal R_{\mathrm{required}}(v)}a_{e,r}.
\]

Đây là **diễn đạt quy tắc WFKG**, không là công thức được lấy từ P1–P6. “Complete evidence” cần được hiểu là một evidence cover đầy đủ required roles, không chọn từng role từ những evidence không tương thích rồi ghép một event giả hoàn chỉnh. Tập evidence rỗng cần convention xử lý rõ; biểu thức max trên tập rỗng không tự định nghĩa baseline.

- `min_role`: bottleneck heuristic để một role yếu kéo score xuống. Có thể giải thích ý định engineering, **không được nói đó là lower-confidence probability của conjunction**.
- `max_evidence`: chọn strongest complete witness, tránh để evidence yếu làm giảm best evidence. Nhưng mất thông tin agreement, contradictions, số nguồn và dependence. Chọn max trong nhiều candidates có thể gây selection bias; nếu muốn calibration, phải đánh giá sau đúng bước lựa chọn này, với phân bố số evidence tương ứng.
- P6 hỗ trợ đánh giá marginals/queries có cấu trúc và propagation bằng sampling; không hỗ trợ thay joint uncertainty bằng min-role. P5 hỗ trợ learned multi-evidence fusion, không max-only pooling.

### 5.2 Vì sao `min`/mean không là probability event cùng đúng

**Phân tích xác suất tổng quát, không phải numbered equation của sáu bài:** giả sử đã có các xác suất biên hợp lệ \(p_r=P(C_r\mid x)\) cho từng role trên cùng conditioning x, thì:

\[
 \max\!\left(0,\sum_{r=1}^k p_r-(k-1)\right)
 \le P\!\left(\bigcap_r C_r\mid x\right)
 \le \min_r p_r.
\]

Vì thế min là **upper bound**, không phải lower bound của all-correct probability. Chỉ khi có conditional independence phù hợp mới được dùng \(P(\cap_r C_r\mid x)=\prod_r p_r\). Marginal calibration theo bins cũng chưa bảo đảm từng p là đúng conditional probability cho chính x; không được áp dụng bounds như bằng chứng cho các heuristic chưa calibration.

Ví dụ minh họa toán học, **không phải measured WFKG data**: bốn role đều có marginal probability 0.8. Python đã tính min = mean = 0.8; nếu independent, joint all-correct = 0.4096; chỉ biết marginals thì bounds là [0.2, 0.8]. Ví dụ cho thấy không thể suy ra event probability từ min hoặc mean.

Tương tự, `1 - product(1-p_e)` là xác suất OR chỉ dưới independence của các biến tương ứng; không có cơ sở mặc định dùng nó cho nhiều báo copy cùng claim. Các báo/evidence cũng không nhất thiết là những event Bernoulli “fact independently true”. Một posterior fusion phải định nghĩa biến, dependence và observation model.

### 5.3 Trung bình S/A/L/R

\[
 \mathrm{confidenceScore}(v)=\frac{S(v)+A(v)+L(v)+R(v)}4
\]

là **equal-weight composite score theo convention WFKG**. Các bài không xác lập equal weights hay common empirical scale cho bốn component này. Ngay cả nếu từng component riêng calibrated cho target riêng, trung bình không tự động calibrated cho target event hoàn chỉnh.

Có các rủi ro riêng:

1. **Khác target:** source reliability nói về source/claim; A về extracting roles; L về identity; R về relation. Trung bình có thể bù một relation yếu bằng source mạnh nhưng không chữa relation sai.
2. **Double-counting:** A/R có thể cùng dùng một LLM/context; L lỗi làm A hoặc R lỗi; source score có thể đã chịu ảnh hưởng của verification evidence. P5 minh họa extractor score có thể đã phản ánh entity-linkage uncertainty.
3. **Khác semantics:** baseline 0.5 hay curated score 1 không là cùng loại measurement với calibrated p. Common numeric range không phải common statistical meaning.
4. **Aggregation khác calibration:** P5 dùng mean qua sources làm feature cho supervised fusion rồi calibrate; P1/P6 dùng bin means để đo calibration; cả hai không chứng minh mean S/A/L/R.

Nếu giữ nguyên specification, mô tả trung thực là “chỉ số tổng hợp phục vụ ranking/review, hiện chưa được xác nhận là xác suất event đúng”. Không viện dẫn Guo/BLINK như tác giả đã đề xuất công thức này.

## 6. Mapping vào extraction/linking/relation/source của WFKG

| Thành phần | Literature cung cấp gì | Giới hạn/diễn giải cho hiện trạng WFKG |
|---|---|---|
| **A — extraction** | P6: correctness target cần đúng mức token/pair/structure/query; uncertainty có thể truyền qua samples. P5: extraction scores cần calibration, fusion theo predicate | Min-role/max-complete-evidence là heuristic riêng. Cần nhãn exact role/span hoặc semantic role correctness và nhãn complete event nếu muốn kiểm chứng calibration ở hai mức. |
| **L — linking** | P2: bi-encoder retrieval, cross-encoder reranking, candidate-set softmax, gold-mention/in-KB assumptions | Phân biệt retrieval coverage, rerank correctness, end-to-end link và NIL. Curated link = 1 chỉ là convention workflow, không theorem của BLINK. |
| **R — relation** | P5: per-predicate binary classifier, supervised fusion và Platt scaling; P3: calibration có thể shift giữa domain | Classifier relation, logical constraint check và relation do LLM suy luận là các target khác nhau. Không gán confidence classifier cho chỉ số rule validity; không dùng label NLI làm bằng chứng relation WFKG đã calibrated. |
| **S — source reliability** | P5: domain/source deduplication, agreement evidence, learned extractor reliability, graph priors | Bài không cung cấp fixed source score cho website WFKG. Reliability của source và extraction correctness phải phân biệt. Một nguồn đáng tin vẫn có thể bị extractor hiểu sai; nhiều URL không có nghĩa nhiều nguồn độc lập. |
| **Composite confidenceScore** | P1/P3/P5: validation-based calibration; P4: risk–coverage cho reject; P6: posterior propagation | Không bài nào xác lập equal-average S/A/L/R. Có thể dùng composite để xếp hạng, nhưng probability claim đòi end-to-end evaluation sau toàn bộ aggregation. |

### Ghi nhận các convention được nêu trong nhiệm vụ

- **Uncalibrated baseline 0.5:** ghi rõ “fallback/convention, chưa có xác suất correctness đo được”. Không gọi 0.5 là Bayesian prior của WFKG khi chưa có prior model/data, hoặc gọi nó là “chance accuracy”: chance tùy label space và base rate. P5 không dùng mặc định 0.5 để thay mọi score thiếu.
- **Curated linking 1:** ghi “accepted by curated mapping/rule”; không diễn giải là empirical 100% correctness. Domain shift, nhầm alias hoặc mapping lỗi vẫn cần audit.
- **LLM self-report:** ghi nguồn score là verbalized/self-reported, không nói đó là posterior. Không đánh đồng con số trong JSON với token likelihood trả bởi inference API.
- **Provenance cho research/evaluation:** nên phân biệt score type, correctness target, model/prompt/version, candidate set, evidence scope, calibration dataset/method/version và missingness. Đây là khuyến nghị ghi nhận thí nghiệm, không phải sửa schema/spec trong nhiệm vụ này.

## 7. Nếu muốn đánh giá sau này: điều gì literature cho phép nói

Đây là hướng kiểm chứng, **chưa thực hiện experiment**:

1. Định nghĩa correctness riêng cho roles, entity IDs, relation và complete event; factual truth của nguồn không đồng nhất với extractor faithful-to-text.
2. Tách train/calibration/test; tránh cùng document, event, copied source hoặc alias family leak qua split. Đánh giá trên score sau max/mean aggregation thật sự sử dụng.
3. Với logits classifier phù hợp, thử temperature scaling [P1/P3]; với scalar score, thử Platt/isotonic theo bối cảnh [P1/P5]. Không hứa mọi phương pháp sẽ cải thiện.
4. Report reliability plots, ECE với binning rõ, NLL/Brier và correctness/coverage; với structured query có thể dùng adaptive-bin RMS của P6. Không so trực tiếp RMS CalibErr với ECE rồi coi là cùng metric.
5. Đánh giá theo role/relation/source/domain và end-to-end target. Với abstention, report empirical risk–coverage [P4]; không tuyên bố high-probability guarantee nếu chưa đáp ứng và thực thi protocol/assumptions của bài.

## 8. Giới hạn xác minh và sự cố truy cập

- Đọc sáu primary PDF, tập trung methods/formulas/assumptions; không tái chạy model hoặc reproduce benchmark. Không có WFKG labeled data được fetch hoặc experiment calibration WFKG nào được thực hiện.
- Các thông số/calibration outcomes của bài là dữ liệu tác giả, không là kết quả của WFKG. Ví dụ số học ở §5.2 là minh họa độc lập đã tính bằng Python.
- Link PDF Knowledge Vault từ Google Research trỏ đến CMU cũ. Khi thử bản HTTPS của URL đó, nội dung trả về không phải bài Knowledge Vault (PDF của trang tác giả), dù HTTP 200. Không dùng nội dung sai ấy làm paper evidence. Bản từ trang Kevin Murphy tại UBC tải đúng title/authors/KDD 2014 và đã đọc methods. Một URL archive Google đoán thử trả 404; đây không là nguồn trích dẫn.
- Bản UBC là author manuscript có dòng copyright placeholder; năm/venue được đối chiếu với Google Research metadata và dòng KDD 2014 của PDF. P4 dùng bản arXiv, không xác minh thêm proceedings venue.
- Không thực hiện systematic review toàn bộ calibration/IE literature; phát biểu “không hỗ trợ min/mean” giới hạn ở sáu nguồn trên. Không khẳng định văn học hoàn toàn không có heuristic tương tự.

**Cách viết an toàn trong luận văn:** “WFKG sử dụng một chỉ số tổng hợp theo convention để quản lý độ tin cậy của pipeline. Các score hiện chưa mặc nhiên là calibrated probabilities; lựa chọn min-role, max-complete-evidence và equal-weight averaging là quyết định thiết kế của hệ thống, trong khi các nghiên cứu primary về calibration và knowledge fusion yêu cầu kiểm chứng với nhãn đúng/sai và protocol đánh giá phù hợp.”
