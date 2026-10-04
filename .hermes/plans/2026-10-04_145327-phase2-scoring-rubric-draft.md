# Phase 2 vertical-slice scoring — kế hoạch thiết kế dự thảo

> **For Hermes:** Triển khai theo từng task sau khi người dùng duyệt các quyết định mở; chưa thực thi code, chưa sửa contract chuẩn, không commit/push. Không dùng skill/tool chưa có trong môi trường.

**Goal:** Mỗi Candidate có thể trả lời: điểm được tính từ đâu, tiêu chí nào sinh từng điểm, nguồn/bằng chứng nào, vì sao chọn Evidence, dữ liệu đã available tại cutoff chưa, và replay có tính lại đúng điểm không.

**Architecture:** Article snapshot → extraction assignment → rule-based scoring observations → eligibility/identity/linking gates → chọn Evidence → route scoring → Candidate bất biến → Reaction riêng sau window. Numeric breakdown chi tiết lưu trong audit JSONL ngoài RDF; Candidate giữ các component hiện hành, không thêm lớp ontology.

**Tech Stack:** Đề xuất Python, Decimal cho score arithmetic, JSONL cho audit, YAML cho rule/config, RDFLib/pySHACL theo roadmap Phase 2. Chưa chọn/cài extractor hay dependency; stack/model/vendor cần duyệt. Đây là phương án thiết kế, không phải pipeline đã chạy.

## 1. Nguồn và trạng thái

Nguồn hiện hành, tương đối với root D:\project\master_thesis\01-10-2026:
- `ban_thay_gop_y/gop_y_phase1_truoc_code_phase2.txt`: mục 3, 4, 6, 7, 8 và kết luận.
- `chỉnh sửa mới nhất - 01-10/SCORING_SPEC.md` version 1.0.4, đặc biệt L35–38, L54–77, L99–124.
- `chỉnh sửa mới nhất - 01-10/EVENT_SCHEMA.md` L86–124.
- `chỉnh sửa mới nhất - 01-10/EVENT_DICTIONARY.yaml`: 14 eventType, required/optional roles, normalization và identity policy.
- `chỉnh sửa mới nhất - 01-10/ANNOTATION_GUIDELINE.md`, `EVALUATION_PROTOCOL.md`.
- `phase2/2026-10-04_102105-wfkg-phase2.md`: roadmap đang có, chưa được coi là triển khai hay duyệt.

Người dùng bổ sung acceptance cụ thể: giải thích và tái tính một điểm như 0.35. Không coi 0.35 là score mục tiêu để tune, chỉ là ví dụ phải truy vết được.

Inventory Phase 2 hiện kiểm tra chỉ có roadmap; chưa thấy code/manifest trong thư mục Phase 2. Không mở rộng kết luận này sang repository khác.

## 2. Khoảng trống thực sự của SCORING_SPEC 1.0.4

1. L54 đã định nghĩa min per-role nhưng chưa định nghĩa tiêu chí sinh per-role score, role correctness target, rule/model đầu vào.
2. Chưa có score eventType/assertion phân biệt loại sự kiện và phủ định/tin đồn/hoàn tất trong assignment formula một cách tường minh.
3. L73–75 có fallback 0.5 và provenance convention, nhưng chưa có audit data schema bắt buộc cho mỗi phép chấm và mỗi input dependency.
4. Completeness không đồng nghĩa semantic correctness: một assignment điền đủ field vẫn có thể ghép sai chủ thể/kỳ/metric.
5. `occurrence_id` luôn required trong dictionary nhưng thường là identity-registry decision, không phải span literal có sẵn trong bài. Cần phân biệt phần văn bản hỗ trợ original occurrence với ID kỹ thuật được resolver tạo.
6. Đã có rule max Evidence nhưng chưa có mẫu explanation ledger gồm cả eligible, excluded và lý do chọn/loại.
7. Hiện baseline chưa calibration dùng 0.5. Một rubric 1.0/0.8/0.5 là method mới, không thể chỉ gọi là diễn giải lại baseline.

## 3. Quyết định gốc — Q1–Q3 đã được người dùng duyệt

Người dùng xác nhận chọn khuyến nghị cho Q1 đến Q3. Phạm vi duyệt: hướng heuristic rubric riêng với fallback comparator, LLM structured-output + deterministic scorer, và availability proxy/observed minh bạch. Không bao gồm phê duyệt numeric rubric, model/vendor/budget, grammar, occurrence resolver, sửa contract chuẩn hoặc triển khai code.

### Q1 — Ý nghĩa và phương pháp sinh điểm

Khuyến nghị: giữ method 1.0.4 với fallback nguyên vẹn làm comparator; thêm method dự thảo `vs-rubric-v0.1` để chấm theo rule và log đủ. Điểm của method mới là heuristic support score, không phải P(correct). Không dùng LLM self-reported confidence làm điểm chính. Các số 1.0/0.8 là hệ số thiết kế chưa được chứng minh thực nghiệm.

Phương án khác: chỉ hoàn thiện audit cho fallback 0.5; đơn giản nhất nhưng variation/ranking và ablation hạn chế. Hoặc calibration trên development gold; có cơ sở probability tốt hơn nhưng không phải lựa chọn tối thiểu cho slice.

### Q2 — Extractor trong slice

Khuyến nghị để duyệt: một LLM structured-output đề xuất span/event/roles; deterministic validator/scorer kiểm tra quoted text, rule IDs, required roles, normalization và attachment. Model/vendor/cost chưa quyết định. Có thể thay bằng rule-based extractor nếu mục tiêu trước mắt là các patterns rõ và chấp nhận coverage thấp. Cả hai phải xuất cùng assignment schema, không nhận gold/prices/future facts.

### Q3 — Availability mode

Khuyến nghị cho dữ liệu lịch sử: publication-time proxy được khai báo nếu không có acquisition logs thật; lưu snapshot text và nêu rủi ro bài đã sửa sau ngày đăng. Không gọi proxy là observed historical availability. Với bài thu thập mới dùng actual acquisition timestamp. Không trộn hai chế độ ngầm.

Q1–Q3 đã chốt theo khuyến nghị. Các chi tiết dưới vẫn là dự thảo có điều kiện: numeric rubric/formula, grammar từng eventType, occurrence resolver, bộ nguồn/registry và acceptance empirical coverage cần được duyệt riêng.

## 4. Domain model dùng để chấm

- Evidence: đoạn văn nguồn bất biến hỗ trợ assertion; không phải nhãn gold.
- ExtractionAssignment: một đề xuất eventType + toàn bộ roles và chứng cứ cho một assertion trong một Evidence; là pipeline record, không thêm RDF class.
- RoleExtractionDecision: xác định đoạn/value nào đóng vai trò gì trong assertion. Không quyết định canonical Company URI.
- EntityLinkDecision: ánh xạ mention đã chọn sang typed registry URI; chấm ở linkingConfidence.
- IdentityDecision: giải quyết original business occurrence/canonicalKey; không dùng article date/URL hay gold ID để bịa occurrence.
- ScoreObservation: rule ID, observed input/features, category, numeric value, producer/config version; audit record ngoài RDF.
- A: score original chosen complete Evidence assignment; copy vào Candidate.extractionConfidence trong method thường.
- Gold: annotation độc lập chỉ evaluator được đọc. Human review để sửa prediction nếu có phải là assisted method riêng, không lặng lẽ đưa gold vào automatic run.

Phân biệt ba thời gian: input factual availableAt, processing/decision generatedAt, inferenceCutoff. Offline replay có decision generatedAt muộn nhưng không được có thêm factual input sau cutoff. Extraction model chạy muộn không làm article available sớm hơn.

## 5. Gate trước score

Fail/hold nếu text hash/offset không khớp, Evidence tương lai, eventType không có rule support, required role thiếu, role binding mơ hồ, normalized literal không hợp lệ, identity thiếu hoặc unresolved. Role absence không được nhận 0.5.

Extraction đủ nhưng link URI chưa resolve: giữ assignment phục vụ RQ1; suppress Candidate/path phụ thuộc link. Canonicalization chưa xong: HOLD_FOR_REVIEW, không mint key giả.

Nếu optional route entry thiếu: suppress riêng route; không đổi selected Evidence để cứu route. Optional key thiếu vẫn theo MATCH_EXISTING_ELSE_HOLD hiện hành, không tự bỏ key field.

Failure ledger là pipeline record; không mặc định tạo RDF Candidate REJECTED nếu chưa đủ field bắt buộc của Candidate. Candidate RDF reject lifecycle chỉ dùng khi record đã hợp lệ theo shape và flow quy định.

## 6. Rubric extraction đề xuất

### 6.1. Các thành phần của một assignment

1. `q_type`: support cho eventType và assertion state đúng dictionary, gồm handling phủ định/modality/attribution.
2. `q_role[r]`: score cho MỖI required role của eventType, không dùng danh sách role cố định cho mọi loại sự kiện.
3. Optional role scores lưu riêng; không tham gia A mặc định. Optional used route entry phải có support/link riêng. Identity-key gate vẫn áp dụng với optional key.

Dự thảo formula cho method mới:

`A_e = min(q_type, q_role[r] for every required role r)`

`extractionConfidence = A_selected`

Type là một decision riêng được đưa vào min; đây là bổ sung so với câu min per-role hiện tại và phải cập nhật spec sau duyệt. Không đưa source/linking/materiality/direction/CAR vào A.

### 6.2. Mỗi q_role được sinh từ gì?

Các check bắt buộc:
- G — Grounding: quote/spans khớp chính xác immutable article text và nằm trong Evidence assignment. Sai/không có => ineligible.
- N — Normalization/representation: literal được parser/vocabulary normalize và giữ qualifiers. Entity role ở đây giữ exact mention và role kind; canonical entity URI kiểm ở linker. Sai/unknown => HOLD, không lấy N=0.5.
- B — Binding: có rule chứng minh mention/value thuộc assertion và đúng vai trò, không chỉ xuất hiện cùng bài.

G và N là gate PASS, không phải xác suất. Sau pass, q_role = lookup score của binding rule. Có thể trình bày tương đương `min(1,1,B)` nhưng audit phải lưu G/N là gates, không giả ba estimator độc lập.

Các lớp binding:

| Code | Giá trị đề xuất | Điều kiện | Producer |
|---|---:|---|---|
| EXPLICIT_LOCAL | 1.0 | Role/value được gắn vào cùng claim bằng pattern lexical/syntactic đã khóa, không có actor/value cạnh tranh | deterministic rule engine |
| BOUNDED_CONTEXT | 0.8 | Một rule ngữ cảnh có tên nối hai câu kề nhau trong CÙNG Evidence; unique antecedent/period/scope, không cạnh tranh, không vượt clause khác | deterministic context rule engine |
| PRESENT_UNSCORED | 0.5 | Chỉ trong method fallback hiện hành: assignment present/evidenced chưa calibration theo contract; không phải một lời chứng nhận correctness bằng verifier | extractor output + fallback convention |
| MISSING/AMBIGUOUS/CONTRADICTED/UNMAPPED | không điểm eligible | Chưa hỗ trợ rõ/mơ hồ/sai claim/schema | hold/failure ledger |

Trong `vs-rubric-v0.1` mặc định KHÔNG dùng PRESENT_UNSCORED để cứu binding không match rule. Một decision unsupported by implemented rule => HOLD/coverage miss. Comparator fallback riêng có 0.5 theo 1.0.4. Không trộn scale/fallback bằng điều kiện ngầm.

Các rule 1.0/0.8 chưa đo correctness thực tế; 1.0 nghĩa rule category cao nhất, không nghĩa 100% đúng. Rule match sai vẫn là lỗi pipeline và phải bị gold evaluation phát hiện.

### 6.3. q_type

Từ action/metric trigger, actor/value binding và modality/negation/attribution rule IDs trong dictionary-specific pattern catalog.
- 1.0: explicit type rule xác nhận loại assertion và status trong claim.
- 0.8: chỉ khi một bounded-context type rule đã duyệt hỗ trợ, không phải guess.
- Không match/ambiguous/conflicting state: HOLD.

Tin đồn được extract đúng M_AND_A_RUMOR không bị giảm điểm chỉ vì rumor; chấm correctness của việc nhận diện assertion, không chấm truth of underlying business transaction. Phủ định đàm phán không được match completion/negotiation affirmative bằng keyword alone.

### 6.4. Tiêu chí theo nhóm required role

| Role kind | Input | Required checks |
|---|---|---|
| company/buyer/target/partner/leader/regulator/... | exact mention spans + claim pattern | đúng vị trí actor/object, không swap buyer/target; typed URI ở linking riêng |
| action roles | trigger spans + modality/negation context | đúng controlled token và event status; không bỏ phủ định/tin đồn |
| reporting_period | exact period/year/qualifier spans | đủ coordinate evidenced; đúng YEAR/QUARTER/HALF/MONTH/RANGE và scope/basis; không suy từ publishedAt |
| metric | exact metric phrase + clause | đúng metric token; không lấy revenue làm net profit, không dùng metric của doanh nghiệp khác |
| occurrence_id | original filing/decision reference spans hoặc registry provenance | extraction chấm support của original reference/context; identity resolver tạo/lookup stable business ID riêng, không pretend ID được trích nguyên từ bài |

Occurrence do adjudication hỗ trợ sau đó không được trở thành automatic prediction từ gold. Nếu chưa có evidenced original reference hoặc cutoff-supported identity resolution, giữ HOLD. Có thể làm assisted diagnostic riêng với disclosure, không dùng thay E2E automatic.

### 6.5. Rule catalog phải hoàn thiện trước coding scoring

Mỗi rule có: rule ID/version, eventType/role, pattern/grammar cụ thể, allowed context window, preconditions, competing value/negation blockers, source spans cần lưu, numeric category, positive/negative fixtures.

Không gọi BOUNDED_CONTEXT là đã implement khi mới có lời mô tả. Ví dụ rule dự thảo `EARNINGS.PERIOD.PREVIOUS_SENTENCE.v1`: hai câu trong cùng Evidence, câu trước chứa đúng một evidenced reporting period và original filing reference, câu sau bắt đầu bằng Company được chỉ định và công bố metric; không có period/scope cạnh tranh và không có câu chuyển issuer. Grammar thực tế/segmentation phải versioned và test, nếu không match thì HOLD. Không áp dụng rule hai câu này cho 14 eventType một cách mù quáng.

Rule coverage từng eventType được công khai; loại chưa hỗ trợ không được giả output để đạt số lượng. Phase 2 cuối cần thực hiện coverage đã duyệt trên dictionary baseline và bốn routes; mini-batch nhỏ chỉ debug, không đổi scope acceptance 100–300 bài.

## 7. Chọn Evidence và cutoff

Order không vòng tròn:
1. Snapshot dữ liệu cutoff-eligible.
2. Extract/score mỗi assignment độc lập với Stock target/route/market/gold.
3. Validate completeness, compatibility và canonical identity. Identity resolver phải có chính sách riêng không chọn bằng candidateScore; unresolved identity giữ HOLD.
4. Lọc cùng canonical Event/normalized identity assignment, đủ required roles, availableAt <= cutoff.
5. Chọn max A_e, tie Evidence URI ascending; select một lần/Event trước route scoring.
6. Link all required entity roles trong assignment đã chọn; route endpoints lấy từ facts/registry eligible riêng.
7. Không reselect Evidence điểm thấp hơn để cứu route hay linker. Ghi coverage miss.

Ledger bắt buộc lưu mọi Evidence considered, A_e/subscores, eligibility, exclusion reason và selected flag. Earliest cutoff nghĩa thường chỉ Evidence đầu tiên eligible; bài điểm cao hơn tới sau không được tham gia max.

Giữ Event.availableAt là earliest supporting factual Evidence availability, không chỉ earliest complete assignment. Không dời cutoff tới lúc role đầy đủ.

## 8. Các component khác và total score

### Source
`S=0.5` cố định; log source registry row/version và toàn bộ supporting source IDs; không cộng vì nhiều bài. Không dùng độ uy tín nguồn để thay q_type.

### Linking
Giữ bảng bốn route SCORING_SPEC L60–69. `L=min(required entity decision scores, route-entry/endpoint mappings, terminal M)`.
- Curated verified typed mapping: 1.0, đúng convention hiện tại; lưu reviewer/provenance/version/factual availability, không gọi calibrated.
- Automatic present/evidenced unique resolution chưa calibration: 0.5 theo fallback convention; không tạo random 0.7/0.9.
- Calibrated automatic nếu sau này có development fit: raw score/calibration artifacts, method riêng.
- Absent/ambiguous/mismatched/future: suppress path.

Không dùng score extraction của mention để thay linking URI decision. Registry curated hôm nay không tự chứng minh mapping available tại cutoff lịch sử; historical fact basis hoặc declared replay/proxy mode phải được kiểm tra.

### Relation
Giữ original A reuse và dependency theo spec hiện tại:
- DIRECT: `R=min(A,M)`.
- INDIRECT: min original A, selected relation-node confidence, endpoint identity mappings, M theo bảng bốn route.
- Present evidenced temporal relation chưa có score: 0.5 và fallback flag.
- Không nâng relation economic confidence lên 1 chỉ vì schema/registry/temporal gate PASS.
- Absent/stale/future: không path; không số 0.5 bù edge thiếu.

A tái dùng ở R gây dependence; composite không phải joint probability. Extraction-neutralization ablation chỉ đổi field extractionConfidence thành 1, giữ original A trong R/selection. Do đó ablation đo score channel đó, không loại sạch mọi ảnh hưởng của extraction.

### Strength và aggregation
DIRECT=1.0; ba indirect=0.5. Industry ratio variant giữ exposure eligibility và dùng exposureStrength=exposureRatio, không bịa ratio. `C=(S+A+L+R)/4`; `candidateScore=C*strength`. Aggregate max path cho Event–Stock trong cùng method/cutoff và URI tie rules hiện hành.

## 9. Ví dụ minh họa tính lại 0.35 — không phải dữ liệu thật

Giả định synthetic Evidence e01 sẵn có lúc 08:30 +07, cutoff=08:30. EARNINGS có đủ roles company/reporting_period/metric/occurrence_id. Bài có original filing reference và kỳ báo cáo trong câu trước; câu sau có Công ty C công bố lợi nhuận sau thuế. Hai câu nằm trong một Evidence, bounded-context rule như §6.5 match và không có kỳ/issuer cạnh tranh.

- q_type=1.0: explicit EARNINGS claim rule.
- q_company=1.0: explicit actor binding.
- q_reporting_period=0.8: named bounded-context rule, exact evidenced year/quarter, no publication-date imputation.
- q_metric=1.0: explicit NET_PROFIT phrase binding.
- q_occurrence_id=1.0: explicit original filing support; stable ID resolution qua identity gate riêng.
- A=min(1.0,1.0,0.8,1.0,1.0)=0.8.

Giả định C là subsidiary, relation child→parent và parent→Stock mapping có nguồn sẵn trước cutoff, temporal gate PASS; entity/endpoint/terminal curated identity mappings =1.0. SubsidiaryRelation confidence chưa calibration dùng 0.5.

- S=0.5.
- L=1.0.
- R=min(A=0.8, nodeConfidence=0.5, endpoint mappings=1.0, M=1.0)=0.5.
- strength=0.5.
- C=(0.5+0.8+1.0+0.5)/4=0.7.
- candidateScore=0.7*0.5=0.35.

Nếu e02 có A=1.0 nhưng available 09:00 thì loại trước selection; không đổi e01/A/0.35. Nếu cùng cutoff có e03 eligible A lớn hơn thì chọn theo max/tie rules, điểm thay đổi đúng rule, không giữ 0.35 tùy ý.

Đã kiểm tra arithmetic ví dụ này bằng Python Decimal trong lượt lập plan. Không thực thi extraction/binding/catalog/route trên article thật. Comparator fallback A=0.5 với cùng inputs S/L/R/strength cho 0.3125, không được nói fallback baseline tự sinh 0.35.

## 10. Audit contract để replay

Một record audit tối thiểu:
- candidate URI/event URI/stock URI/methodVersion/config hash/cutoff/generatedAt/replay mode.
- immutable article ID/text snapshot/hash; Evidence URI/start/end/text/availableAt và availability basis.
- assignment ID/eventType, q_type rule match, tất cả required roles/quotes/spans/raw+normalized values/qualifiers.
- per-decision observed features, rule ID/version, category/value, PASS/HOLD reasons, original raw model output hash nếu dùng model.
- identity registry decision/business occurrence key/provenance và selected assignment compatibility.
- considered Evidence ledger và selected Evidence URI/tie resolution.
- all linking decisions typed IDs/registry versions/availability/support refs/fallback flags.
- ordered route fact IDs/versions/business keys, latest-version selection, validity/staleness checks và input factual availability.
- S/A/L/R/strength/formula/calibration or heuristic flag, intermediate sums và final numeric value.
- optional-role/route-entry support audit tách khỏi A.
- model/prompt/parameters/response artifact/hash; rule catalog/parser/dictionary versions.

Điểm serialize bằng decimal strings, tính không round trung gian, hiển thị rounded riêng; tolerance theo contract khi RDF double roundtrip. Không rút ngắn score rồi dùng score display để rank. Config/checksum không thay thế nội dung input cần lưu.

Ba mức tái lập:
1. Arithmetic replay: đọc stored components → đúng total.
2. Rule replay: đọc frozen assignments/spans/features + rule catalog → đúng subcomponents/selection/total, không tin điểm lưu sẵn.
3. Extraction replay: rerun extractor từ text. Rule-based có thể deterministic; LLM seed/temperature=0 không bảo đảm output giống. Với LLM giữ original response và phân biệt replay response snapshot với fresh inference; ghi drift, không hứa bit-for-bit model rerun.

Verifier rule match chỉ kiểm support theo rule, không thay gold correctness. Later gold/human correction không ghi đè snapshot historical prediction.

## 11. Reaction scoring vẫn là stage riêng

Giữ adjustedClose Stock+benchmark, exact calendar sessions + predecessor, cached return tolerance 1e-9, AR/CAR, tau=0.10, epsilon=0 và reactionWeight như 1.0.4. Reaction audit link về immutable Candidate audit, không tính lại Candidate bằng newer Evidence. Window chưa đủ thì pending/invalid task theo contract, không partial CAR giả.

Daily day 0 strict opening. Nếu không có calendar coverage hoặc đúng benchmark prices thì block Reaction, không mất inference ranking/gold.

## 12. Tasks sau duyệt — file dự kiến, chưa tạo

### Task 1 — Khóa design decisions và scoring rule contract
**Objective:** Q1–Q3 được duyệt và xác định method mới/fallback comparator.
**Files:** sửa sau duyệt `chỉnh sửa mới nhất - 01-10/SCORING_SPEC.md`, `EVENT_SCHEMA.md`, `ANNOTATION_GUIDELINE.md`, `EVALUATION_PROTOCOL.md`; proposed create `wfkg-pipeline/config/scoring_rubric_v0.1.yaml` và `wfkg-pipeline/docs/scoring-audit-contract.md`.
Steps: ghi decisions; định nghĩa min gồm q_type; policy unsupported rules; pending calibration; inventory affected DOCX/Draw.io summaries; backup ngoài delivery set trước sửa. Không sửa ontology class/property nếu audit ngoài RDF đủ; đánh giá shape impact trước tuyên bố method hợp lệ.
Validation: đối chiếu không còn câu 'mọi uncalibrated assignment=0.5' áp nhầm rubric method; giữ riêng fallback contract; rule catalog có positives/negatives và producer cho từng score.

### Task 2 — Assignment schema và role/type rule scoring
**Objective:** span-grounded role score thay vì model tự cho điểm.
**Files proposed:** `wfkg-pipeline/src/wfkg_pipeline/extraction_scoring.py`, `wfkg-pipeline/tests/test_extraction_scoring.py`.
TDD: test expected q_type/per-role/A trên fixture độc lập; chạy fail trước implementation; implement gates/rule lookup/min; chạy pass.
Cases: explicit claim, bounded context, missing year/role, actor swap, forecast vs actual, rumor correctly classified, negated completion, unmapped qualifier, unsupported occurrence ID, optional role không đổi A.

### Task 3 — Evidence selection và temporal/link route scoring
**Objective:** max eligible assignment đúng thời điểm và đúng route.
**Files proposed:** `wfkg-pipeline/src/wfkg_pipeline/snapshot.py`, `candidates.py`, `tests/test_score_selection.py`, `tests/test_candidate_scoring.py` (đồng bộ roadmap, không tự bịa API hiện có).
TDD: future Evidence score cao excluded; equal URI tie; incomplete not eligible; same chosen Evidence across routes; missing link/no mapping/no relation suppress; latest-version-before-validity; stale exposure; exact 0.35 arithmetic.

### Task 4 — Audit writer và independent replay checker
**Objective:** checker tính lại từ raw stored observations/rules chứ không từ total lưu sẵn.
**Files proposed:** `wfkg-pipeline/src/wfkg_pipeline/score_audit.py`, `recompute_scores.py`, `tests/test_score_replay.py`.
TDD: valid audit recomputes; mutate role span/rule/version/availableAt/mapping/score => detected; remove registry/article snapshot => fail. Arithmetic checker và rule checker tách rõ. Auditor không gọi gold/model/market endpoint.

### Task 5 — E2E mini-batch rồi slice thật
**Objective:** Article→Evidence/Event→Candidate→Reaction và explanation 0.35-type output từ dữ liệu thật.
**Files proposed:** roadmap extraction/link/identity/calendar/reaction/CLI modules, `wfkg-pipeline/tests/test_scoring_e2e.py`, run snapshots theo roadmap.
TDD trước: fixture cả bốn route + negative controls; kiểm extraction output thật khi chạy full slice, không feed gold graph thay extractor. Mini-batch debug trước; acceptance slice vẫn 100–300 bài thật, hold/misses giữ ledger.
Validation: fresh inference run, audit/replay run, SHACL inference=none, calendar/return checks, route counts, unsupported rule counts, factual/proxy availability và source licensing công khai. Thiếu empirical route cases ghi chưa đạt coverage, không bù synthetic rồi gọi real data.

### Task 6 — Diagnostic evaluation và explanation report
**Objective:** đo rubric có utility/correctness thực tế mà không tune vào final.
**Files proposed:** `wfkg-pipeline/docs/vertical-slice-scoring-report.md`, evaluator output và explanation snapshots.
Report: RQ1 role/type exact correctness theo gold độc lập, correctness frequency theo từng rubric category và support (không gọi calibration từ mẫu nhỏ), score distributions/fallback rates/coverage; RQ2/RQ3 diagnostics và ablations như protocol trên common eligible cohort. Bảng 0.35 breakdown cho Candidate thật phải có exact evidence/route factual refs. Không bịa target KG thắng.

## 13. Lệnh verification dự kiến và hiện có

Đây là plan, chưa chạy pipeline. Lệnh exact pytest sẽ khóa khi pyproject/test files được tạo sau duyệt; không khẳng định `.venv`/pytest đang có.

Sau implementation env được chuẩn bị tại `wfkg-pipeline`, dự kiến:
- `.venv/Scripts/python.exe -m pytest tests/test_extraction_scoring.py tests/test_score_selection.py tests/test_candidate_scoring.py tests/test_score_replay.py tests/test_scoring_e2e.py`
- CLI inference/recompute/explain design cần chốt trước code; chưa đưa lệnh không tồn tại như đã runnable.

Regression hiện có, chạy từ repo root với interpreter có dependencies:
- `python -B "chỉnh sửa mới nhất - 01-10/tools/test_baseline_shacl.py"`
- `python -B "chỉnh sửa mới nhất - 01-10/tools/test_schema_diagram_audit.py"`
- `python -B "chỉnh sửa mới nhất - 01-10/tools/audit_schema_diagram.py"`

Không chạy generator rewrite delivery files trong lượt lập kế hoạch. Khi spec sửa sau duyệt cần reread test/audit implementation và verify shapes support method; parse PASS không chứng minh full semantic consistency.

## 14. Acceptance theo 5 câu hỏi người đọc

| Câu hỏi | Artifact bắt buộc | Test |
|---|---|---|
| 0.35 từ điểm nào? | S/A/L/R/strength + q_type/q_roles + formula | independent Decimal arithmetic |
| Điểm đầu vào từ đâu? | exact quote/span/rule match/model response/registry/fact provenance | trace refs/content hashes, role rule replay |
| Vì sao chọn Evidence? | all considered evidence ledger + eligibility/max/tie | better-late Evidence excluded, equal-score tie stable |
| Dữ liệu có ở cutoff chưa? | factual availability basis của mọi dependency; generatedAt tách riêng | mutate availability + historical fact validation |
| Có tính lại đúng không? | full frozen inputs/config/rule catalog | replay selection/subscores/total, missing input fails |

Không đặt thang 100 điểm acceptance pipeline. Đây là các gate cần đạt, không cho lỗi anti-leakage bù bằng điểm nhóm khác.

## 15. Rủi ro, trade-offs và nhánh câu hỏi tiếp theo

- Rubric 1.0/0.8 có giá trị kỹ thuật giải thích nhưng chưa có bằng chứng xác suất/thứ hạng tối ưu. Không gọi 0.8 là 80% correctness.
- Min bảo thủ, role nhiều có thể giảm score; cần report by eventType/role count. Không đổi sang mean sau nhìn final.
- A reused in R và strong DIRECT priority có thể làm ranking ít variation; phải đo histogram, ties và ablations, không bảo đảm utility.
- Rules coverage thấp/occurrence identity thiếu có thể làm nhiều empty ranks; giữ coverage misses đúng protocol.
- Modern model có thể biết thông tin sau cutoff từ pretraining dù prompt không chứa future facts. Evidence-only output/rule validation giảm rủi ro nhưng không chứng minh sạch tuyệt đối; report model/version/training-cutoff nếu biết, không claim observed real-time prediction.
- Archived text/proxy timestamp không đảm bảo bài không sửa sau ngày đăng; cần snapshot basis/threats to validity.
- Gold, prediction curation, registry review phải tách role; review sau run không biến future human knowledge thành cutoff input.
- Sau khi Q1–Q3 chốt, vòng kế tiếp mới hỏi chi tiết thresholds/context grammar/extractor prompt/nguồn/chế độ occurrence resolver. Không tự coi downstream assumptions là đồng thuận.

**Status:** DRAFT — Q1–Q3 đã duyệt; đang làm rõ rubric, Evidence boundary và occurrence identity ở vòng kế tiếp. Chưa sửa SCORING_SPEC và chưa có pipeline execution evidence.
