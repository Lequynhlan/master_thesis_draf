# Uncertainty/confidence trong ontology và KG: đọc nguồn primary cho WFKG

## 1. Kết luận trước

**Không có một công thức “ontology confidence” mặc định.** Trong sáu bài chính đã đọc abstract và phần phương pháp dưới đây, cần tách ít nhất năm đối tượng: (i) metadata về bằng chứng, (ii) xác suất một fact/hypothesis đúng, (iii) mức độ thuộc một khái niệm mờ, (iv) độ tin cậy thực nghiệm của một luật, và (v) trạng thái chứng minh/ưu tiên luật pháp lý. Cùng nằm trong [0,1] không khiến chúng có cùng ngữ nghĩa.

- **Knowledge Vault (KV)** gần bài toán confidence của WFKG nhất: học cách hợp nhất extraction signals và graph priors, rồi hiệu chỉnh thành xác suất fact correctness. Không phải tự gán một rubric là xác suất.
- **AMIE** là căn cứ rõ cho confidence của *luật*, không phải xác suất đúng của từng Event–Stock candidate. Phải kiểm tra giả định về độ đầy đủ dữ liệu.
- **PR-OWL** là biểu diễn và suy luận Bayesian trong ontology: cần random variables, dependencies và probability distributions thực sự, không chỉ một datatype property `confidence`.
- **PSL** là joint inference bằng weighted soft rules. Giá trị MAP của atom không mặc nhiên là calibrated marginal probability.
- **Fuzzy OWL 2** giải quyết vagueness/membership, không đồng nghĩa với epistemic confidence về sự đúng sai của fact.
- Nguồn pháp luật đã đọc, **Enabling Reasoning with LegalRuleML**, dùng modal defeasible logic và rule superiority; **không đưa mô hình numeric confidence cho correctness của legal facts**. Không biến compliance checking hoặc “strength of rule” thành xác suất.

Đối với WFKG: confidence của candidate Event–Stock phải được định nghĩa ở thời điểm biết tin. AR/CAR và market impact nằm ở hậu nghiệm, không dùng để xác nhận rằng bước extraction/linking ban đầu có confidence cao.

## 2. Phạm vi và mức chứng cứ

Đây là nghiên cứu tài liệu, không sửa ontology, contract hoặc code. Các PDF được tải bằng Python requests qua HTTPS và đọc text bằng PyMuPDF; các trang metadata dùng arXiv, CEUR và Crossref. “Đã đọc full-text” dưới đây nghĩa là truy cập PDF đầy đủ và đọc các phần abstract/method/evaluation được nêu; không tuyên bố đã kiểm toán tất cả proofs, chạy code hoặc tái lập thí nghiệm.

Sáu bài chính gồm một đối chiếu pháp luật và năm nguồn general/ontology/KG. Thêm một **position paper biomedical** ở mục 9 để đối chiếu loại bằng chứng; không tính nó là nghiên cứu numeric-confidence đã được đánh giá. DOI Crossref là xác minh bibliographic, không thay thế đọc bài. Bài CEUR không có DOI/arXiv được xác minh trong lượt nghiên cứu này: dùng URL proceedings và PDF, không tự chế DOI.

## 3. Bài pháp luật: Lam & Hashmi — *Enabling Reasoning with LegalRuleML*

**Tác giả/năm:** Ho-Pun Lam, Mustafa Hashmi; arXiv v1 năm 2017, v2 năm 2018. Bản PDF đã đọc là v2, ghi đang được xem xét tại TPLP; không dùng các ngày placeholder “1 January 2003” trong mẫu LaTeX làm ngày công bố. PDF cũng ghi có phiên bản sơ bộ RuleML 2016.

**Định danh verified:** https://arxiv.org/abs/1711.06128 ; https://arxiv.org/pdf/1711.06128 ; arXiv:1711.06128v2; DOI arXiv https://doi.org/10.48550/arXiv.1711.06128 . Đây là DOI arXiv, không phải DOI journal được xác minh.

**Đã đọc:** abstract; phần Defeasible Logic về superiority/tagged literals; §5.3 về compliance/violation; §5.4 implementation; §7 conclusions.

- **Confidence target:** Không có numeric confidence target. Đối tượng là provability của legal conclusions, nghĩa vụ/quyền/cấm và cách giải quyết luật xung đột.
- **Inputs:** LegalRuleML statements, facts, strict/defeasible rules, deontic operators, override/superiority relations.
- **Phương pháp:** Chuyển LegalRuleML sang một biến thể Modal Defeasible Logic và ngược lại. `r1 > r2` nghĩa là r1 override r2 khi cả hai áp dụng, không phải `P(r1 đúng) > P(r2 đúng)`. Các tagged literals `+Δq`, `−Δq`, `+∂q`, `−∂q` phân biệt definite/defeasible provability và rejection. Không ánh xạ bốn trạng thái này sang các số tự đặt.
- **Đánh giá:** Tích hợp parser/renderer trong SPINdle; so sánh thời gian và bộ nhớ với định dạng DFL. Dữ liệu gốc TCPC 2016 có 6 constitutive statements, 78 prescriptive statements, 10 override statements; tạo synthetic theories bằng nhân bản/đổi keys để kiểm tra scalability. Đây không phải đánh giá calibration, Brier hay precision của confidence score.
- **Liên quan WFKG:** Có thể mượn cách giữ lý do áp dụng luật, ngoại lệ và ưu tiên khi suy luận Event–Stock; **không dùng làm citation cho numeric relationConfidence**. Nếu tin tài chính nói về quy định pháp luật, đúng về trạng thái nghĩa vụ khác với đúng về liên kết cổ phiếu và khác với biến động thị trường.

**Giới hạn legal:** Chỉ nguồn này đã được đọc sâu ở mảng pháp luật. Không kết luận toàn bộ legal ontology literature không có xác suất; chỉ kết luận bài đã đọc không cung cấp mô hình numeric confidence đó. KR4IPLaw (Ramakrishna & Paschke, 2014, https://arxiv.org/abs/1406.0079) chỉ được đọc abstract, không đưa vào sáu bài chính: abstract nói về Structured English → LegalRuleML/OWL2, không đưa bằng chứng numeric confidence.

## 4. PR-OWL: da Costa, K. B. Laskey & K. J. Laskey (2005)

**Title:** *PR-OWL: A Bayesian Ontology Language for the Semantic Web*.

**Tác giả:** Paulo Cesar G. da Costa, Kathryn B. Laskey, Kenneth J. Laskey.

**Nguồn verified:** URSW 2005, CEUR Workshop Proceedings Vol. 173. Proceedings https://ceur-ws.org/Vol-173/ ; full text https://ceur-ws.org/Vol-173/paper3.pdf . Không xác minh được DOI/arXiv cho phiên bản này. Không đánh đồng với chapter sau này có thể trùng title. Trang tác giả https://www.pr-owl.org/ xác nhận PR-OWL là Bayesian extension của OWL dựa trên MEBN; “PROWL/prowl” là cách phát âm/viết thông thường, tên citation là **PR-OWL**.

**Đã đọc:** abstract; §§3–5 MEBN, probabilistic ontologies, upper ontology; phần reified relationships; §6 conclusions, 11 trang.

- **Confidence target:** Degree of belief/posterior probability của target random variables cho những hypotheses về entity/property/relation/event, có điều kiện trên evidence; không phải “điểm chất lượng ontology”.
- **Inputs:** Generative MTheory gồm MFrags; context, input, resident random variables; các local probability distributions; finding MFrags cho evidence của tình huống; query nodes.
- **Phương pháp chính:** MFrags mô tả dependencies và probability distributions. MTheory phải thỏa consistency conditions để tồn tại unique joint distribution. Khởi tạo và nối các MFrag instances để tạo **situation-specific Bayesian network (SSBN)**, sau đó dùng Bayesian-network inference và đọc posterior của target nodes. Upper ontology cung cấp classes/properties, ví dụ `hasProbDist`; n-ary relations được reify để biểu diễn bằng OWL.
- **Công thức:** Bài trình bày pipeline suy luận, không đề xuất weighted average của các confidence components. Có thể tóm tắt ngữ nghĩa là `P(target | findings, MTheory)`; đây là ký hiệu diễn giải nội dung §3, **không phải phương trình được đánh số trong bài**. Không bổ sung CPT hoặc số xác suất giả.
- **Đánh giá:** Bài là nền tảng ngôn ngữ/biểu diễn với diagrams và lập luận về semantics, không báo một benchmark calibration/accuracy cho news KG. Plugin Protégé trong bài là operational concept/future work, không phải phần mềm đã được benchmark.
- **Liên quan WFKG:** Nếu muốn “confidence” mang ngữ nghĩa posterior thực sự, phải mô hình hóa reliability của nguồn/extractor/linker và dependence của evidence. Reified node của candidate là chỗ lưu mô hình và kết quả, không tự sinh posterior. Tin trích lại nhau cần được mô hình hóa hoặc deduplicate; không thể coi mọi article là independent observation chỉ vì có IRI riêng.

## 5. Bobillo & Straccia — *Fuzzy Ontology Representation using OWL 2*

**Tác giả/năm:** Fernando Bobillo, Umberto Straccia; preprint 2010, journal 2011.

**Verified:** https://arxiv.org/abs/1009.3391 ; https://arxiv.org/pdf/1009.3391 ; arXiv:1009.3391v3; DOI arXiv https://doi.org/10.48550/arXiv.1009.3391 . Crossref title/author/year khớp journal DOI https://doi.org/10.1016/j.ijar.2011.05.003 . Đã đọc PDF preprint, không tuyên bố đã đọc bản publisher cuối.

**Đã đọc:** abstract; §3.2 và Table 2 semantics; §4 encoding/`fuzzyLabel`; phần parsers/implementation và conclusions.

- **Confidence target:** Membership/truth degree của fuzzy concepts, roles và axioms, để biểu diễn vague knowledge. Không phải xác suất thông tin báo chí chính xác.
- **Inputs:** Fuzzy assertions, fuzzy datatypes/membership functions, modifiers, chọn fuzzy logic, weighted concepts/axioms.
- **Phương pháp/công thức:** Fuzzy interpretation gán `Cᴵ: Δᴵ → [0,1]`, `Rᴵ: Δᴵ × Δᴵ → [0,1]`; `Cᴵ(a)` biểu thị mức độ a thuộc concept C. Table 2: `(C ⊓ D)ᴵ(x) = Cᴵ(x) ⊗ Dᴵ(x)`; existential restriction dùng `sup_y {Rᴵ(x,y) ⊗ Cᴵ(y)}`. Kết quả phụ thuộc fuzzy operators/logic đã chọn, không thay ⊗ tùy tiện bằng một công thức xác suất. Encoding qua OWL 2 annotation property `fuzzyLabel`, giá trị XML `FuzzyOwl2`; parser chuyển sang fuzzyDL hoặc DeLorean.
- **Đánh giá:** Demonstration về biểu diễn, ví dụ và prototype parsers/reasoners; phần kết luận không cung cấp empirical probability-calibration benchmark. Standard non-fuzzy reasoner có thể bỏ annotations và trả kết quả như khi annotations không tồn tại — thêm annotation không làm reasoner OWL chuẩn tự suy luận mờ.
- **Liên quan WFKG:** Phù hợp nếu “high exposure”, “strong relation” là khái niệm graded/vague. Không gọi membership của “StrongExposure” là xác suất Event–Stock relation đúng. Giữ `relationStrength` và `relationConfidence` khác semantics dù đều có thể được chuẩn hóa về cùng khoảng.

## 6. Bach, Broecheler, Huang & Getoor (2017) — PSL/HL-MRF

**Title:** *Hinge-Loss Markov Random Fields and Probabilistic Soft Logic*.

**Tác giả:** Stephen H. Bach, Matthias Broecheler, Bert Huang, Lise Getoor. JMLR 18(109):1–67 (2017); arXiv v1 2015, v3 2017.

**Verified:** https://arxiv.org/abs/1505.04406 ; https://arxiv.org/pdf/1505.04406 ; arXiv:1505.04406v3; https://doi.org/10.48550/arXiv.1505.04406 . Metadata arXiv xác nhận journal reference; không tự thêm DOI journal.

**Đã đọc:** abstract/introduction; §3.1 về interpretation of MAP states; §3.2 Definitions 3–4/Eqs.23–26; §4.1 program grounding; §4.3 priors; §§6.4.1–6.4.2/Tables 1–3.

- **Confidence target:** Giá trị liên tục của ground atoms trong [0,1] và probability density trên assignments. Tùy domain, MAP state được hiểu như degree of belief/confidence/ranking hoặc continuous quantity. **Atom value tại MAP khác posterior marginal probability của một Boolean fact.**
- **Inputs:** Observed atoms x, unknown atoms y, weighted logical/arithmetic rules, constraints và labels cho weight learning.
- **Công thức verified:** `φ_j(y,x) = max{ℓ_j(y,x),0}^{p_j}`, `p_j ∈ {1,2}` (Eq.23); `f_w(y,x) = Σ_j w_j φ_j(y,x)`, `w_j ≥ 0` (Eq.25). Trong feasible domain: `P(y|x) = Z(w,x)^{-1} exp(−f_w(y,x))` (Eq.26); ngoài domain density bằng 0. MAP inference là constrained convex minimization của energy, giải bằng consensus optimization/message passing; có weight-learning algorithms. `w_j` là penalty/weight của potential, không mặc nhiên là probability của rule.
- **Đánh giá:** Node classification trên Cora/Citeseer bằng accuracy; trust-link prediction trên Epinions bằng ROC-AUC và PR-AUC cho positive/negative links, cùng inference runtime. So sánh linear/quadratic HL-MRF với discrete MRF và các cách học weights. Đây không phải bằng chứng rằng mọi atom MAP value đều được calibrate.
- **Liên quan WFKG:** Có thể encode soft rules để joint inference giữa event roles, entity links và candidate paths; tránh tự nhân độc lập các evidence đang phụ thuộc. Nếu công bố output dưới tên “probability”, vẫn phải định nghĩa interpretation và kiểm tra calibration trên ground truth WFKG.

**Lưu ý quan trọng:** PSL và Knowledge Vault là hai công trình khác nhau. Không viết “KV sử dụng PSL” dựa trên tên “probabilistic” hay việc KV cite literature về continuous relaxations. KV đã đọc mô tả supervised classifiers/PRA/neural prior/fusion, không mô tả một PSL inference engine.

## 7. Dong et al. (2014) — Knowledge Vault

**Title:** *Knowledge Vault: A Web-Scale Approach to Probabilistic Knowledge Fusion*.

**Tác giả:** Xin Luna Dong, Evgeniy Gabrilovich, Geremy Heitz, Wilko Horn, Ni Lao, Kevin Murphy, Thomas Strohmann, Shaohua Sun, Wei Zhang.

**Verified:** Google-hosted primary PDF https://research.google.com/pubs/archive/45634.pdf ; KDD 2014; DOI https://doi.org/10.1145/2623330.2623623 . Crossref xác nhận authors/year/DOI (record title rút gọn “Knowledge vault”). Full title từ PDF. Không có arXiv được xác minh.

**Đã đọc:** abstract; §2.2 LCWA; §§3.1–3.3 extraction/fusion/calibration; §4.1 PRA và §4.2 neural prior; §5 fusion; §6 human evaluation; §8 limitations.

- **Confidence target:** Probability một RDF triple `(s,p,o)` là đúng — fact correctness, không probability thị trường sẽ tăng/giảm.
- **Inputs:** Extractions từ TXT/DOM/TBL/ANO; extractor scores; số distinct sources (nguồn được deduplicate); prior từ Freebase graph; labels học supervised theo LCWA. Với TBL/ANO, extraction score có thể phản ánh entity-linking confidence; không phải mỗi extractor đã có bốn confidence components độc lập.
- **Phương pháp:** §3.2 lập feature vector cho mỗi triple, mỗi extractor có `sqrt(number of sources)` và mean extraction score; classifier theo predicate. Ban đầu thử logistic regression, nhưng boosted decision stumps tốt hơn. Graph priors dùng PRA (probabilities của walks qua typed relation paths, logistic classifier) và neural model. §5 hợp nhất priors với extraction bằng fusion framework.
- **Công thức verified:** §4.2 Eq.1 cho tensor factorization baseline: `P(G(s,p,o)=1) = σ(Σ_k u_sk w_pk v_ok)`, `σ(z)=1/(1+exp(−z))`. **Đây là baseline trong trình bày neural prior, không phải toàn bộ final KV fusion formula.** Final fusion không phải một weighted product của source/extraction/linking/relation confidence.
- **Calibration:** §3.3 nói rõ extractor/fusion scores chưa chắc cùng scale hay là probability; áp dụng **Platt scaling** bằng logistic regression trên separate validation set. Calibration plot so predicted probability với empirical fraction of true facts.
- **Đánh giá:** ROC/AUC, so extractors/priors/fusion, phân bố facts theo confidence bins, calibration curve. §6 human-rated subset kiểm tra giới hạn LCWA; Table 5 cho AUC prior+extractor 0.959 theo LCWA và 0.869 theo human labels trên subset đó. Không diễn giải chênh lệch thành kết quả WFKG.
- **Giới hạn quan trọng:** LCWA coi một subject–predicate pair đã có object values là locally complete; có thể tạo false negatives khi KB thiếu actors/children. §8 nêu xử lý từng fact như independent binary variable vì scalability, trong thực tế facts có correlation.
- **Liên quan WFKG:** Citation mạnh nhất cho “học fusion + calibrate”. Rubric LLM có thể là features/uncalibrated scores; cần labels đúng về extraction, linking và relation để train/validate/calibrate. Không coi số nguồn đăng lại là independent support; giữ features và provenance, kiểm tra theo thời gian. Không dùng CAR làm label fact correctness.

## 8. Galárraga, Teflioudi, Hose & Suchanek (2013) — AMIE

**Title:** *AMIE: Association Rule Mining under Incomplete Evidence in Ontological Knowledge Bases*.

**Verified:** Author-hosted PDF https://suchanek.name/work/publications/www2013.pdf ; WWW 2013; DOI https://doi.org/10.1145/2488388.2488425 . Crossref record trực tiếp xác nhận DOI/authors/year, title rút gọn “AMIE”. Trang dự án https://www.mpi-inf.mpg.de/departments/databases-and-information-systems/research/yago-naga/amie/ . Không trộn thí nghiệm AMIE+ 2015 từ trang này vào AMIE 2013.

**Đã đọc:** abstract; §4 mining model/support/confidence/PCA; §5 algorithm; §§6.1/6.3/6.4 evaluation.

- **Confidence target:** Độ tin cậy của Horn rule `B ⇒ r(x,y)` dựa trên counts trong incomplete KB, dùng để chọn/rank rules và dự đoán missing facts. Không confidence của ontology schema, không trực tiếp confidence của mọi predicted individual fact.
- **Inputs:** KB triples; instantiated rule bodies/heads; counts của distinct head-variable pairs; không yêu cầu explicit negative examples. Bài gốc loại `rdf:type` và literal-valued facts ở experimental KBs.
- **Công thức verified, §4:** Gọi z là các biến ngoài x,y:
  - `supp(B ⇒ r(x,y)) = #{(x,y): ∃z, B ∧ r(x,y)}`.
  - `conf = supp / #{(x,y): ∃z, B}`.
  - `pca_conf = supp / #{(x,y): ∃z,y′, B ∧ r(x,y′)}`.
  - `headCoverage = supp / #{(x′,y′): r(x′,y′)}`.
  Các counts chiếu trên distinct pairs, không đếm mọi body grounding nhiều lần. Công thức PCA trên theo orientation trong bài (FUN-property); không áp máy móc cho mọi chiều relation.
- **Ý nghĩa:** Standard confidence penalize unknown predictions như false. PCA chỉ lấy denominator trong vùng giả định complete: nếu biết một r-value của x thì giả định biết tất cả r-values của x. Đây là assumption, không theorem nói KB đã đầy đủ.
- **Phương pháp:** Mining operators mở rộng Horn rules, pruning bằng head coverage/confidence. Counts luôn trên original KB; không feedback predictions vào KB để tự nâng support.
- **Đánh giá:** Runtime/precision/coverage so WARMR và ALEPH; so standard/PCA confidence. Mine trên older YAGO2 rồi đánh giá predictions chưa có bằng newer YAGO2s; với trường hợp chưa xác minh được tự động, manual checking mẫu bằng Wikipedia. Chạy thêm DBpedia. §6.3/Table 9 đo average absolute error giữa confidence và empirical precision; kết quả không đảm bảo PCA là calibrated posterior probability cho từng fact.
- **Liên quan WFKG:** Có thể dùng cho learned relation-inference rules nếu đủ labeled graph evidence. Nhưng Event→Stock thường many-valued, graph tin tức thiếu coverage; biết một cổ phiếu liên quan **không có nghĩa đã biết tất cả cổ phiếu liên quan**. PCA assumption có nguy cơ sai. Muốn cho rule confidence vào candidate score cần giữ rule ID, support, head coverage, direction, evaluation set và method version; không tự gọi rule confidence là relation posterior.

## 9. Đối chiếu biomedical bổ sung: evidence codes khác numeric posterior

**Andrea Splendiani (2005), *Ontology based analysis of experimental data*.** Position paper URSW 2005, cùng CEUR Vol.173; https://ceur-ws.org/Vol-173/pos_paper3.pdf . Đã đọc abstract và toàn bộ nội dung ngắn §§2–6. Không xác minh DOI/arXiv; không thuộc sáu bài chính.

- **Target:** Uncertainty khi liên kết experimental observations với biological entities/classes/pathway concepts.
- **Inputs:** mRNA experimental data, pathway ontology, annotations/evidence support, measurement uncertainty.
- **Phương pháp được mô tả:** Evidence codes/citations/p-values được thảo luận như thông tin support; hợp nhất ontology với observations và dự kiến Bayesian network cập nhật plausibility. §5 nói infrastructure Cytoscape/ontology merging đã có, Bayesian update là phần **planned**.
- **Công thức/đánh giá:** Không có numeric fusion formula hoặc benchmark posterior calibration đã hoàn thành trong bài. Không dùng p-value như `1 − confidence`, không coi evidence code là xác suất.
- **Liên quan WFKG:** Mẫu hữu ích cho việc giữ loại evidence, nguồn và measurement/extraction uncertainty riêng. Không cung cấp công thức áp thẳng cho bốn confidence components.

Không mở rộng phát biểu “almost every ontology” của tác giả thành một thống kê hiện đại đã được kiểm chứng. Bài này chỉ là minh họa lịch sử/position paper, không strong empirical evidence.

## 10. RDF reification/provenance: biểu diễn khác tính điểm

Đã đọc nguồn chuẩn primary, không tính là research papers:

1. W3C **RDF 1.1 Semantics**, Appendix D.1 Reification: https://www.w3.org/TR/rdf11-mt/#Reif . Trang fetched https://www.w3.org/TR/rdf11-mt/ . Nguồn nêu rõ: “A reification of a triple does not entail the triple, and is not entailed by it.” Reification cho metadata về triple token, không chứng minh fact đúng.
2. W3C **PROV-O**: https://www.w3.org/TR/prov-o/ . Entity/Activity/Agent và `wasDerivedFrom`, `wasGeneratedBy`, `wasAttributedTo` mô tả nguồn gốc/quá trình/agent. Không có cơ chế mặc định biến provenance path thành calibrated correctness probability.

Do đó:

| Lớp | Cho biết | Không tự cung cấp |
|---|---|---|
| Reified assertion/candidate | Statement nào mang metadata/score/evidence | Công thức score hoặc probability semantics |
| Provenance | Ai/nguồn/quy trình tạo assertion | Source reliability được học hoặc calibration |
| OWL/classical rules | Logical consequences theo assumptions | Epistemic probability của fact ngoài đời |
| SHACL/constraint checks | Có thỏa constraints được khai báo không | Confidence correctness hoặc độ chắc chắn thị trường |
| PR-OWL | Bayesian model và posterior inference | Parameter estimates nếu chưa elicitation/learning |
| Fuzzy OWL | Graded concept/role membership | Calibrated probability fact correctness |
| PSL | Continuous structured inference với weighted rules | Mọi MAP score là posterior marginal |
| AMIE | Empirical rule confidence dưới assumptions | Xác suất đúng cho từng candidate không cần validation |
| KV | Learned/calibrated fact-correctness model | Universal four-component formula cho mọi domain |

## 11. Hàm ý cho thesis WFKG — khuyến nghị, không phải công thức từ paper

### 11.1 Định nghĩa bốn thành phần trước khi tổng hợp

- `sourceConfidence`: target cụ thể là reliability nào — bài đưa tin đúng, publisher accuracy hay support chất lượng? URL/provenance không đủ để suy ra giá trị.
- `extractionConfidence`: event/relation/attribute có được trích đúng theo evidence span không?
- `linkingConfidence`: mention có map đúng company/ticker/entity ID và đúng thời điểm không?
- `relationConfidence`: evidence/graph path có thực sự justify candidate Event–Stock role/relation không?

Đây là đề xuất phân rã theo pipeline WFKG, **không phải bốn trường chuẩn đã được KV hoặc PR-OWL thiết lập**. Một confidence target tổng thể hợp lý là correctness của assertion/candidate đã định nghĩa, không “probability stock reacts” khi chưa định nghĩa phản ứng.

### 11.2 LLM rubric dùng được ở giai đoạn đầu, nhưng phải đặt tên trung thực

1. Giữ evidence span, provenance, method/prompt/model version và raw rubric score.
2. Nếu chưa calibration, gọi là **heuristic/rubric score**, không viết “0.8 nghĩa là 80% facts đúng”.
3. Xây gold labels theo component và candidate correctness; giữ unknown/insufficient evidence khác false.
4. Dùng temporal holdout và group theo event/source family để giảm leakage/near-duplicates; không để tin syndicated vào train và test như independent examples.
5. So baseline aggregation với learned fusion; kiểm tra discrimination và calibration. Reliability diagram/Brier/ECE là đề xuất evaluation cho WFKG, **không phải tất cả sáu bài đều dùng những metrics này**.
6. Không nhân bốn scores để ra “joint probability” trừ khi có mô hình và giả định conditional dependence/independence phù hợp; cũng không coi weighted average là probability chỉ vì weights cộng bằng một.

### 11.3 Không trộn confidence, strength và impact

`relationStrength` mô tả exposure/liên hệ mạnh yếu; `confidence` mô tả độ đáng tin của assertion; `impact`/AR/CAR là quan sát thị trường hậu nghiệm. Một candidate extraction đúng có thể không tạo CAR đáng kể; CAR lớn không chứng minh entity linking đúng hoặc nhân quả từ event. Thiết kế evaluation tách correctness của candidate khỏi utility của ranking/market analysis.

**Câu có thể dùng cho thesis:** “WFKG lưu trữ confidence cùng evidence và provenance ở cấp assertion/candidate. Các điểm thành phần ban đầu là rubric-based scores, không được mặc định diễn giải là xác suất. Việc hợp nhất và hiệu chỉnh probability cần validation dữ liệu gán nhãn, theo tinh thần learned knowledge fusion của Knowledge Vault; rule confidence, fuzzy membership và defeasible priority được giữ riêng vì khác ngữ nghĩa.”

## 12. Fetch audit và limitations

### Nguồn thực sự fetched thành công

- `https://ceur-ws.org/Vol-173/` — proceedings identity/year/authors.
- `https://ceur-ws.org/Vol-173/paper3.pdf` — PR-OWL full text.
- `https://www.pr-owl.org/` — first-party background/name/MEBN link; guide/semantics subpages fetched nhưng là placeholders, không dùng làm phương pháp.
- `https://arxiv.org/abs/1009.3391` và `/pdf/1009.3391` — fuzzy ontology metadata/full text.
- `https://arxiv.org/abs/1505.04406` và `/pdf/1505.04406` — PSL metadata/full text.
- `https://research.google.com/pubs/archive/45634.pdf` — KV full text.
- `https://suchanek.name/work/publications/www2013.pdf` — AMIE full text.
- `https://www.mpi-inf.mpg.de/departments/databases-and-information-systems/research/yago-naga/amie/` — AMIE first-party project background; có nội dung AMIE+ cần phân biệt.
- `https://arxiv.org/abs/1711.06128` và `/pdf/1711.06128` — LegalRuleML metadata/full text.
- `https://arxiv.org/abs/1406.0079` — KR4IPLaw abstract only, không full-method evidence.
- `https://ceur-ws.org/Vol-173/pos_paper3.pdf` — supplementary biomedical position paper.
- `https://www.w3.org/TR/rdf11-mt/` và `https://www.w3.org/TR/prov-o/` — standards.
- `https://api.crossref.org/works?query.title=Knowledge%20Vault&rows=1` — KV DOI metadata.
- Crossref query title `Fuzzy Ontology Representation using OWL 2`, rows=1 — verified journal DOI/year/authors.
- `https://api.crossref.org/works/10.1145/2488388.2488425` — AMIE DOI metadata trực tiếp.

### Lỗi và phần chưa làm

- MPI-hosted AMIE PDF `https://resources.mpi-inf.mpg.de/yago-naga/amie/amie.pdf` trả 403; đọc được author-hosted alternative.
- MEBN foundational paper GMU link `https://ite.gmu.edu/~klaskey/papers/Laskey_MEBN_Logic.pdf` lỗi TLS; thử đọc tài liệu public bỏ certificate verification cho lookup này rồi nhận 404. **Không đọc được bài MEBN 2008, không gán công thức/proof của nó vào bảng.** PR-OWL 2005 CEUR là nguồn thực sự đọc cho MEBN-based inference.
- Crossref batched lookup ban đầu trả non-JSON ở ít nhất một request; retry có KV/fuzzy records. AMIE title search trả near matches; phải dùng direct DOI record xác minh lại, không nhận nhầm AMIE3/AMIE+.
- Một arXiv ID thử dò MEBN (`1206.6857`) thực tế là *Faster Gaussian Summation*; đã loại, không cite làm MEBN.
- Không có systematic legal-literature review toàn diện; không tìm ra legal numeric-confidence paper đủ bằng chứng trong phạm vi này. Không tuyên bố không tồn tại.
- Biomedical đối chiếu là position paper lịch sử, không đánh giá clinical/biomedical numeric model hiện đại.
- Không chạy original code hoặc tái lập metrics. Không có dataset WFKG để estimate weights/calibrate và không tạo scores mẫu.
- Các đề xuất WFKG/LLM rubric ở mục 11 là synthesis/design recommendations của notes, không attributed như kết quả thực nghiệm của paper.
