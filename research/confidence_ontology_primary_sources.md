# Confidence trong ontology/KG: luật, suy luận xác suất và ví dụ pháp lý

## 1. Phạm vi và kết luận quan trọng

Ghi chú này phục vụ thiết kế WFKG với bốn thành phần **nguồn – trích xuất – liên kết thực thể – quan hệ**. Phạm vi ưu tiên là ontology, luật và pháp lý; không thay thế khảo sát riêng về hiệu chỉnh xác suất của mô hình extraction/entity linking.

**Kết luận:** Có các phương pháp thực sự tính confidence bằng đếm dữ liệu (AMIE), suy luận trên possible worlds (ProbLog/DISPONTE), hoặc tối ưu mô hình cấu trúc học từ dữ liệu (PSL). Tuy nhiên, chúng **không cung cấp sẵn một bộ bốn subscore phổ quát**, và không biến kết quả kiểm tra ontology hay checklist chuyên gia thành xác suất đúng của một triple.

Đã tải và đọc trực tiếp **6 bài nghiên cứu gốc**, gồm 2 bài pháp lý. PDF và văn bản trích xuất lưu tại `research/confidence_sources/`. Số trang dẫn bên dưới là trang PDF, không phải lúc nào cũng trùng số trang proceedings. Các công thức được viết lại bằng ký hiệu thống nhất; không phải trích dẫn nguyên văn.

## 2. Phải phân biệt các loại điểm

| Loại | Đối tượng được đo | Phép tính/kiểm tra | Không được diễn giải thành |
|---|---|---|---|
| Ontology consistency / entailment | Tập axioms và hệ quả logic | Kiểm tra satisfiability, consistency, entailment bằng DL reasoner | Xác suất văn bản được trích đúng hay sự kiện đúng ngoài đời |
| Extraction/linking probability | Nhãn hoặc entity ứng viên của một mẫu | Mô hình thống kê; cần đánh giá/hiệu chỉnh trên dữ liệu gán nhãn | Độ tin cậy do ontology tự sinh ra |
| Rule support/confidence | Luật Horn trên KG | Đếm các cặp thỏa body/head; giả định đóng/mở/đầy đủ một phần | Xác suất đã calibrated cho từng triple |
| Probabilistic logical query | Truy vấn từ axioms/facts có xác suất | Tổng xác suất worlds chứng minh query; giải thích logic + BDD | Phương pháp tự đánh giá nguồn hoặc tự tạo các xác suất đầu vào |
| PSL soft truth / MAP | Biến [0,1] trong mô hình cấu trúc | Tối thiểu hóa tổng hinge losses có trọng số | Marginal probability của một Boolean fact nếu chưa chứng minh/hiệu chỉnh |
| Checklist chuyên gia | Mức đáp ứng tiêu chí chất lượng | Rubric, đếm tiêu chí, trọng số do người thiết kế đặt | Xác suất thống kê có cơ sở thực nghiệm chỉ vì đã chuẩn hóa về [0,1] |

**Lưu ý kỹ thuật:** OWL domain/range thường là axioms để suy ra kiểu, không đơn thuần là ràng buộc kiểm tra dữ liệu như SHACL. Vắng một type assertion chưa đồng nghĩa vi phạm; open-world và khả năng suy ra type phải được tính đến. Vì vậy không nên viết `C_relation = 1` chỉ vì triple không làm ontology mâu thuẫn.

## 3. AMIE: các subscore tính trực tiếp từ KG

**[S1]** Luis Galárraga, Christina Teflioudi, Katja Hose, Fabian M. Suchanek. **AMIE: Association Rule Mining under Incomplete Evidence in Ontological Knowledge Bases**. WWW, **2013**.

- PDF tác giả, đã đọc: <https://suchanek.name/work/publications/www2013.pdf>
- Vị trí bằng chứng: §3–4, PDF trang 3–5; đặc biệt định nghĩa support, head coverage, standard confidence và PCA confidence.
- Tác giả phân biệt ABox và TBox, tập trung chủ yếu vào ABox; “ontological knowledge bases” ở tên bài không có nghĩa confidence là điểm chất lượng schema.

Cho luật `R: B(x,y,z) => r(x,y)`, với `z` đại diện các biến body ngoài head, `#` đếm **cặp head phân biệt**, không đếm mọi đường chứng minh:

\[
\operatorname{supp}(R)=\#\{(x,y):\exists z\; B(x,y,z)\land r(x,y)\}.
\]

\[
\operatorname{hc}(R)=\frac{\operatorname{supp}(R)}{\#\{(x,y):r(x,y)\}}.
\]

\[
\operatorname{conf}_{std}(R)=\frac{\operatorname{supp}(R)}{\#\{(x,y):\exists z\;B(x,y,z)\}}.
\]

Standard confidence phạt các dự đoán không xuất hiện trong KG, kể cả chúng chỉ **chưa được biết**, không thực sự sai. Đây là vấn đề của closed-world khi KG không đầy đủ.

AMIE đề xuất **partial completeness assumption (PCA)**: nếu đã biết một giá trị của quan hệ `r` cho chủ thể `x`, xem các giá trị `r` của `x` là đầy đủ. Khi áp dụng theo hướng head phù hợp:

\[
\operatorname{conf}_{PCA}(R)=
\frac{\operatorname{supp}(R)}{\#\{(x,y):\exists z,y'\; B(x,y,z)\land r(x,y')\}}.
\]

Mẫu số chỉ giữ các dự đoán đối với chủ thể đã có ít nhất một head fact. Bài còn tính functionality:

\[
\operatorname{fun}(r)=\frac{\#\{x:\exists y\;r(x,y)\}}{\#\{(x,y):r(x,y)\}},
\]

và inverse functionality để chọn hướng quan hệ. Không nên bỏ qua hướng này rồi áp PCA tùy ý lên mọi quan hệ pháp lý.

**Ý nghĩa cho WFKG:** Nếu `C_relation` là độ tin cậy của **luật sinh quan hệ**, AMIE cung cấp phép tính có nguồn rõ ràng. Cần lưu riêng `support`, `headCoverage`, `stdConfidence`, `pcaConfidence`, phiên bản KG và chiều áp PCA. Không lấy support hay head coverage làm xác suất đúng của triple.

**Giới hạn pháp lý:** Biết một điều luật dẫn chiếu một văn bản không có nghĩa đã thu thập đủ toàn bộ dẫn chiếu. PCA có thể sai mạnh đối với quan hệ nhiều–nhiều như dẫn chiếu, ngoại lệ, sửa đổi. Luật thống kê học trên văn bản cũng không tự trở thành quy phạm pháp luật; các điều kiện hiệu lực, thời điểm, thẩm quyền và ngoại lệ cần mô hình riêng. Mẫu số bằng 0 thì confidence không xác định; không tùy tiện gán 1.

## 4. ProbLog: tính xác suất query từ facts/clauses có xác suất

**[S2]** Luc De Raedt, Angelika Kimmig, Hannu Toivonen. **ProbLog: A Probabilistic Prolog and its Application in Link Discovery**. IJCAI, **2007**.

- PDF proceedings, đã đọc: <https://www.ijcai.org/Proceedings/07/Papers/396.pdf>
- Bằng chứng: §2–4, PDF trang 2–4, equations (1)–(4); §6 trang 5 mô tả mạng sinh học thực nghiệm.

Với chương trình `T={p_i:c_i}` và một chương trình con `L` được chọn ngẫu nhiên:

\[
P(L\mid T)=\prod_{c_i\in L}p_i\prod_{c_i\notin L}(1-p_i),
\qquad
P(q\mid T)=\sum_{L:L\models q}P(L\mid T).
\]

Trong bài, các quyết định đưa clause vào chương trình được giả định độc lập. Query thành công nếu có một proof trong chương trình con. Hệ thống tìm proofs bằng SLD-resolution, biểu diễn sự tồn tại proof bằng công thức Boolean và dùng **binary decision diagrams (BDD)** để tính xác suất. Bài còn đưa phương pháp xấp xỉ với cận trên/cận dưới khi chưa tìm hết proofs.

**Điểm có thể tính:** xác suất kết nối/quan hệ suy ra từ nhiều facts, với provenance đến facts/clauses gốc. Đây là một cơ chế propagation/aggregation uncertainty, không phải checklist.

**Các xác suất đầu vào từ đâu?** §2 nói xác suất cạnh sinh học có thể đến từ phương pháp dự đoán sự tồn tại cạnh sử dụng co-occurrence hoặc sequence similarity; §6 dùng mạng được xây từ cơ sở dữ liệu sinh học và trọng số theo một nghiên cứu khác. Vì vậy bài **không trực tiếp cung cấp một quy trình calibrated source/extraction/linking cho WFKG**. Đừng dẫn ProbLog như bằng chứng rằng bất cứ số do LLM hoặc người nhập đều là xác suất chuẩn.

**Cảnh báo gộp proofs:** Các proof chia sẻ fact nên không độc lập. Không cộng các xác suất proof hoặc dùng noisy-OR giữa mọi proof nếu chưa kiểm tra dependence. BDD xử lý sự chồng lấn này dưới các giả định của mô hình.

## 5. DISPONTE/BUNDLE: uncertainty ở chính axiom ontology

**[S3]** Fabrizio Riguzzi, Elena Bellodi, Evelina Lamma, Riccardo Zese. **Reasoning with Probabilistic Ontologies**. IJCAI, **2015**, pp. 4310–4316.

- PDF proceedings, đã đọc: <https://www.ijcai.org/papers15/Papers/IJCAI15-613.pdf>
- Bằng chứng: §3 PDF trang 2–3, equations (1)–(4); §4 trang 3–5 về explanations/BDD và complexity; §6 về ontology sinh học.
- Tài liệu first-party phụ trợ về annotation OWL: <https://ml.unife.it/disponte/> (đã mở; không tính thay cho một bài academic).

DISPONTE gắn `p::E` cho DL axiom `E`, với `p∈[0,1]`. Mỗi probabilistic axiom có biến Boolean độc lập `X_i`. Một world gồm các axioms được chọn và các axioms chắc chắn. Khi `σ_i∈{0,1}`:

\[
P(w_\sigma)=\prod_i p_i^{\sigma_i}(1-p_i)^{1-\sigma_i},
\qquad P(Q)=\sum_{w:w\models Q}P(w).
\]

**Phân biệt đặc biệt quan trọng, nêu rõ ngay trong §3:** `p::C⊑D` là mức tin rằng **cả axiom subclass** đúng; không phải “mỗi instance của C có xác suất p thuộc D”. Đây là epistemic uncertainty về axiom, không phải tần suất phần trăm cá thể.

BUNDLE dùng DL reasoner (ví dụ Pellet) để tìm explanations cho query; chuyển chúng thành Boolean formula/BDD rồi tính xác suất. §4 nhấn mạnh không được cộng xác suất explanations trực tiếp vì explanations có thể chồng lấn. Nếu giới hạn số explanations, kết quả là **lower bound**, không phải xác suất đầy đủ.

**Ví dụ kiểm chứng có ngay trong bài:** ontology people+pets có xác suất Cat(fluffy)=0.4, Cat(tom)=0.3, Cat⊑Pet=0.6; query kevin:NatureLover có kết quả 0.348 theo phép tính trong PDF trang 3. Các số này là ví dụ lý thuyết của tác giả, **không phải số đo pháp lý hay kết quả của WFKG**.

**WFKG có thể học gì?** Phân tách uncertainty của schema axioms với uncertainty của assertions. Khi một kết luận phụ thuộc nhiều axioms và facts, tính query probability qua explanations thay cho một tích bốn điểm không có mô hình phụ thuộc. Nếu nhiều triples được tạo từ cùng một câu hoặc cùng một nguồn, cần biểu diễn/shared random choices phù hợp; giả định mỗi axiom độc lập có thể đánh giá sai uncertainty.

**Không thể học gì chỉ từ bài này?** Công thức tự ấn định `p` cho một văn bản luật, thực thể hay relation extracted. Bài trọng tâm là suy luận, không phải đo độ tin cậy nguồn tin. Thực nghiệm sinh học đánh giá tính khả thi/scalability không chứng minh calibration cho corpus pháp lý.

### Pronto: liên quan nhưng chưa kiểm chứng trực tiếp bản bài gốc

Crossref xác minh metadata **Pavel Klinov, “Pronto: A Non-monotonic Probabilistic Description Logic Reasoner”, 2008**, DOI <https://doi.org/10.1007/978-3-540-68234-9_66>. Bản bài Pronto chưa được tải/đọc trực tiếp trong khảo sát này, vì vậy **không tính vào 6 bài trực tiếp và không viện công thức chi tiết như đã xác minh từ Pronto**.

[S3] §5 giải thích P-SHIQ(D)/PRONTO dùng probabilistic lexicographic entailment, default reasoning và probabilistic interpretations, khác với distribution semantics của DISPONTE. Sự phân biệt này được xác minh từ **bài của nhóm DISPONTE**, không được đánh đồng với xác minh trực tiếp bài Pronto. Đây là đầu mối nên đọc tiếp nếu WFKG cần ràng buộc xác suất/default reasoning; không phải bằng chứng cho checklist confidence nguồn.

## 6. PSL/HL-MRF: học trọng số và suy luận nhất quán mềm

**[S4]** Stephen H. Bach, Matthias Broecheler, Bert Huang, Lise Getoor. **Hinge-Loss Markov Random Fields and Probabilistic Soft Logic**. Journal of Machine Learning Research 18, **2017**, pp. 1–67.

- PDF đã đọc: <https://arxiv.org/pdf/1505.04406>
- Bản arXiv xuất phát năm 2015 nhưng PDF trực tiếp ghi JMLR 2017; không gọi hai mốc này là hai bài độc lập.
- Bằng chứng: §3 PDF trang 10–13; definitions/eqs (25)–(27), §4 về PSL logical rules; §6 trang 36–40 về weight learning.

Mô hình có biến `y_i∈[0,1]`, bằng chứng quan sát `x`, các hinge potentials:

\[
\phi_j(y,x)=[\max\{\ell_j(y,x),0\}]^{p_j},\quad p_j\in\{1,2\},
\qquad f_w(y,x)=\sum_j w_j\phi_j(y,x),\quad w_j\ge0.
\]

Trên miền khả thi do hard constraints quy định:

\[
P(y\mid x)=Z(w,x)^{-1}\exp[-f_w(y,x)],
\qquad y^*=\arg\min_{y\;\mathrm{feasible}} f_w(y,x).
\]

Bên ngoài miền khả thi, mật độ bằng 0. Đây là **mật độ trên các biến liên tục**, không phải mặc nhiên Bernoulli marginal.

Ví dụ dạng luật mềm `A ∧ B => C` có linear violation `max(A+B-C-1,0)` theo relaxation logic PSL. Đây là minh họa ký hiệu tổng quát, không phải luật pháp lý trích từ bài.

**Trọng số được tính như thế nào?** §6 trình bày structured perceptron/approximate maximum likelihood, maximum pseudolikelihood và large-margin estimation từ dữ liệu huấn luyện. Với template potentials `Φ_q` và trọng số `W_q`, gradient log likelihood:

\[
\frac{\partial\log P(y\mid x)}{\partial W_q}
=\mathbb E_W[\Phi_q(y,x)]-\Phi_q(y,x).
\]

Tác giả thay kỳ vọng khó tính bằng potentials tại MAP state trong phương pháp structured perceptron. Pseudolikelihood tối ưu tích các conditional distributions của từng biến theo Markov blanket; đây là quy trình học thực sự, không phải tự gán phần trăm cho từng luật.

**Ý nghĩa cho WFKG:** Dùng extractor/linker scores làm observed predicates, luật domain và evidence khác để suy luận tập thể các quan hệ. Có thể học rule weights từ gold labels, rồi ghi tên score là `pslSoftTruth` hoặc `structuredInferenceScore`.

**Giới hạn:** Chính §3 nói MAP states có thể được diễn giải thành rounding probabilities, pseudo-marginals, degrees of belief hoặc rankings tùy ứng dụng. Vì vậy `y_i*=0.8` **chưa chứng minh** trong 100 quan hệ tương tự có 80 quan hệ đúng. Rule weight `w_j` cũng không phải xác suất luật. Muốn gọi `C_relation` là calibrated correctness probability phải kiểm định trên tập pháp lý gán nhãn; không chỉ dựa vào [0,1].

## 7. Ví dụ pháp lý 1: LKIF Core là mô hình hóa, không phải bộ confidence subscores

**[S5]** Rinke Hoekstra, Joost Breuker, Marcello Di Bello, Alexander Boer. **The LKIF Core Ontology of Basic Legal Concepts**. LOAIT, **2007**, pp. 43–63.

- PDF đã đọc: <https://ceur-ws.org/Vol-321/paper3.pdf>
- Trang proceedings xác minh workshop 2007: <https://ceur-ws.org/Vol-321/>. Volume đưa lên CEUR tháng 1/2008; cần phân biệt năm workshop với năm đăng web.
- Bằng chứng: abstract; §3–4 phương pháp và modules; §5, PDF trang 15–17 về formalization EU Directive 2006/126; conclusion trang 18.

LKIF Core phục vụ trao đổi tri thức pháp lý, mô tả các khái niệm, norms, attitudes và expressions. Tác giả đánh giá khả năng sử dụng bằng formalization một directive về giấy phép lái xe và thảo luận giới hạn OWL/nhu cầu module định lượng.

**Không tìm thấy trong bài đã đọc:** phép tính confidence cho từng triple hoặc công thức phân rã nguồn/trích xuất/liên kết/quan hệ. “Belief”, “evaluative attitude” trong ontology là **khái niệm được mô hình hóa**, không phải một mô hình tính calibrated score cho hệ thống extraction.

**Áp dụng đúng:** LKIF gợi ý loại entity, quan hệ, định nghĩa và biểu diễn deontic cho WFKG. Một ontology sử dụng được để formalize một directive là bằng chứng về khả năng biểu đạt/use case, không phải xác suất chính xác của một assertion mới.

## 8. Ví dụ pháp lý 2: T2K có association/ranking scores và đánh giá thủ công

**[S6]** Alessandro Lenci, Simonetta Montemagni, Vito Pirrelli, Giulia Venturi. **NLP-based ontology learning from legal texts. A case study.** LOAIT, **2007**, pp. 113–129.

- PDF đã đọc: <https://ceur-ws.org/Vol-321/paper7.pdf>
- Bằng chứng: §3.1 PDF trang 7–9 về acquisition/ranking; §3.2 trang 9–10 về conceptual organization; §4 trang 10–15 về corpus và evaluation.

Hệ T2K xử lý văn bản pháp luật môi trường tiếng Ý bằng NLP, thống kê và organization thuật ngữ:

1. Single terms được lựa chọn bằng frequency sau loại stopwords.
2. Complex terms được tạo bằng chunk/syntactic patterns, rồi **xếp hạng bằng log-likelihood ratio** cho sự đồng xuất hiện của lexical heads trong các chunks.
3. Các verb–subject/object associations vượt một threshold tạo tập “best verbs” cho mỗi term. Semantic relatedness giữa các terms tính từ overlap của các tập này, dựa trên metric ở một bài được tác giả viện dẫn. **Bài hiện tại không in công thức overlap đầy đủ; không được tự thay bằng Jaccard rồi bảo đó là công thức T2K.**

Corpus trong bài gồm **824** văn bản legislative/institutional/administrative; evaluation một TermBank **4.685** terms dùng legal dictionary và environmental glossary, cho phép full và partial matches. PDF trang 13 báo **51%** có match ở giai đoạn đầu; mở rộng reference resources và đánh giá thủ công một phần glossary làm thay đổi các kết quả đối chiếu. PDF trang 14 nhấn mạnh **không kết luận recall** từ các reference resources vì phạm vi của chúng rộng hơn corpus.

**Các điểm ở đây thực sự đo gì?** Frequency và log-likelihood ratio đo mức nổi bật/liên kết thống kê; similarity đo mức relatedness theo distributional contexts. Reference matching/manual evaluation đo chất lượng đầu ra ở mức tập thuật ngữ và protocol đánh giá, **không phải posterior probability của từng extracted relation**.

**Đừng biến score này thành xác suất bằng một phép chia tùy tiện:** Bài xác nhận sử dụng LLR nhưng không trình bày công thức chi tiết tại đây; cần đọc thêm nguồn Dunning (1993) được viện dẫn trước khi tái hiện chính xác estimator. Không gán `C_extraction = LLR/max(LLR)` và gọi calibrated confidence dựa vào bài này. Cũng không lấy tỷ lệ dictionary match làm xác suất đúng của mọi term không match: reference resources có thể thiếu terms hợp lệ.

**Áp dụng cho WFKG:** Bằng chứng pháp lý trực tiếp cho pipeline semi-automatic: thống kê xếp hạng ứng viên, domain/reference validation, chuyên gia rà soát. Có thể giữ `termAssociationScore`, `dictionaryMatchType`, `humanReviewed` riêng; không gộp các trường ấy thành “confidence probability” nếu thiếu một nghiên cứu/đánh giá bổ sung.

## 9. Khuyến nghị cho bốn thành phần WFKG — đây là diễn giải thiết kế, không phải công thức nguyên bản của một bài

| Thành phần WFKG | Nghiên cứu trên thực sự hỗ trợ | Điều chưa có căn cứ từ khảo sát này |
|---|---|---|
| `C_source` | Provenance giúp biết facts/axioms nào tham gia explanations; có thể quản lý các giả định nguồn trong mô hình riêng | Bảng điểm độ tin cậy website/cơ quan rồi coi là probability; không bài nào ở đây định nghĩa universal source-score |
| `C_extraction` | T2K cho association ranking + protocol evaluation; ProbLog cho phép nhận probability đầu vào | Xem frequency/LLR/checklist/parser pass là calibrated extraction probability |
| `C_linking` | Ontology hỗ trợ loại/khái niệm, reference resources hỗ trợ kiểm tra; PSL có thể kết hợp bằng chứng cấu trúc | Ontology tương thích tự sinh xác suất linking; cần khảo sát linker riêng |
| `C_relation` | AMIE nếu quan hệ từ luật: confidence theo đếm; ProbLog/DISPONTE nếu suy ra xác suất từ probabilistic evidence; PSL nếu collective inference | Trộn AMIE PCA confidence, PSL MAP và binary schema validity như ba xác suất cùng nghĩa |

**Nên tách hai trục:** (a) correctness/uncertainty score có nguồn, unit và estimator rõ; (b) validation status/provenance để giải thích và rà soát. Nếu validation checks có mẫu số, có thể báo tỷ lệ vượt kiểm tra như một **quality metric do WFKG định nghĩa**, không nhận là calibrated probability và không nhận là phương pháp đã được LKIF/T2K chứng minh.

**Không mặc định** `C_total=C_source*C_extraction*C_linking*C_relation`: tích đó cần diễn giải sự kiện/điều kiện hoặc giả định độc lập thích hợp. Bốn stage thường liên quan nhau; source ảnh hưởng extraction, linker dùng context của extraction, relation dùng endpoints đã link. DISPONTE/ProbLog minh họa rằng phép nhân chỉ có căn cứ sau khi chọn các random choices độc lập, rồi còn phải xử lý proof overlap. Nếu chưa có cơ sở học/kiểm định một điểm tổng, lưu vector các scores và validation flags là cách trung thực hơn.

Muốn triển khai một phương pháp có thể bảo vệ trong luận văn:

1. Chọn rõ `C_relation` áp cho **text-extracted relation**, **mined rule** hay **inferred fact**; không dùng một công thức cho cả ba mà không giải thích.
2. Với mined rules, dùng AMIE, lưu các số đếm/mẫu số và giả định PCA; kiểm tra phù hợp quan hệ pháp lý.
3. Với probabilistic inference, dùng probabilities có nguồn đo riêng và shared provenance; chọn ProbLog/DISPONTE nếu muốn semantics query probability.
4. Với collective constraints, chọn PSL nhưng ghi soft truth/MAP và quy trình học trọng số; cần validation trước khi gọi xác suất đúng.
5. Với ontology/legal validation, báo loại lỗi và status, không thay posterior bằng “đúng schema”. Với pháp luật cần giữ thời điểm hiệu lực, phiên bản và ngoại lệ; những thông tin này không được đảm bảo chỉ bởi confidence cao.

## 10. Giới hạn và kiểm chứng nguồn

- Đây là khảo sát có mục tiêu, không phải systematic review toàn bộ legal KG.
- Đã trực tiếp đọc 6 PDFs nêu trên; Pronto chỉ có metadata và phần đối chiếu từ [S3], được ghi rõ phạm vi.
- AMIE URL MPI ban đầu trả HTTP 403; thay bằng bản tác giả `suchanek.name`, tải được PDF đúng tiêu đề. Một URL IJCAI đoán ban đầu trả **bài khác**; đã kiểm tra index IJCAI và thay bằng `396.pdf` đúng ProbLog. Không dùng nội dung bài sai.
- URL DISPONTE cũ ở ML@UNIFE trả 404; tìm bibliography first-party BUNDLE và dùng bản IJCAI 2015 tải thành công.
- Không thực hiện training/calibration trên dữ liệu WFKG; ghi chú không báo performance hay probabilities được tạo ra cho thesis.
- Không chỉnh sửa thư mục submission.
