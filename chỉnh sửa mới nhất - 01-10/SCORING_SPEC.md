# SCORING_SPEC.md

Document version: 1.1.0
Active scoring method: `WFKG-SCORE-V1`
Namespace: `https://example.org/wfkg/v1#`
Status: đặc tả scoring baseline đã chốt cho vertical slice; chưa xác nhận implementation hoặc calibration.

## 1. Phạm vi, ý nghĩa và ranh giới phiên bản

Tài liệu này đặc tả cách sinh từng điểm, chọn đầu vào, tổng hợp và lưu đủ dữ liệu để replay. Không chứa ví dụ số hoặc kết quả thực nghiệm.

`WFKG-SCORE-V1` là quy ước baseline của dự án, không phải chuẩn confidence phổ quát. Softmax/sigmoid scores, giá trị curated `1.0`, automatic relation support `0.5` (legacy fallback được tách ở mục 1.1), phép min và trung bình bốn thành phần không phải xác suất đúng đã calibration. Các thành phần có thể phụ thuộc nhau; không giả định độc lập.

### 1.1. Thay đổi so với SCORING_SPEC 1.0.4

| Nội dung | Legacy 1.0.4 | WFKG-SCORE-V1 hiện hành |
| --- | --- | --- |
| Extraction chưa calibration | Assignment đầy đủ nhận fallback 0.5 | Dùng task scores của extractor đã fine-tune, min các quyết định bắt buộc |
| Automatic entity linking | Cho phép calibrated score hoặc fallback 0.5 | Chỉ resolve xác định qua registry; ambiguous/fuzzy-only phải HOLD |
| Event–route-entry support | Dùng original extraction assignment score A | Evidence-backed automatic relation dùng 0.5; curated relation fact dùng 1.0 |
| DIRECT strength | 1.0 | 1.0 |
| Ba INDIRECT strengths | 0.5 | 1.0 |
| Industry exposure-strength comparison | Có trong legacy baseline | Không thuộc V1; phải dùng method khác |

Các Candidate legacy không được tính lại hoặc ghi đè bằng V1. Không trộn rankings của hai methods.

**Ranh giới đồng bộ:** EVENT_SCHEMA.md, EVALUATION_PROTOCOL.md và ANNOTATION_GUIDELINE.md document version 1.1.0 cùng dùng WFKG-SCORE-V1. Identity, bốn routes, temporal selection và calendar được giữ; numerical policies V1 thay legacy ở bảng trên. TTL/SHACL vẫn là structural source of truth; generic conformance không tự kiểm đầy đủ method-specific constants/origins/selection. `methodVersion` không tự vượt constraints của shape. Reports DOCX/PDF, diagrams, demos và pipeline code chưa được xác nhận đồng bộ V1; PHASE1_ACCEPTANCE.md tách historical 1.0.4 evidence khỏi current spec readiness. Không tuyên bố whole-bundle hay implementation acceptance chỉ vì Markdown đã đồng bộ.

Bản cũ được lưu tại `../review_phase1/backups/before_WFKG_SCORE_V1_20261004_191908/SCORING_SPEC.md`.

### 1.2. Công thức bắt buộc

```text
S = sourceConfidence
A = extractionConfidence
L = linkingConfidence
R = relationConfidence
T = relationStrength

confidenceScore = (S + A + L + R) / 4
candidateScore = confidenceScore * T
```

Tất cả thành phần thuộc `[0,1]`. V1 cố định `S=0.5`, `L=1.0` cho path vượt linking gate, `T=1.0`. A biến thiên theo model; R nhận `0.5` hoặc `1.0` theo nguồn xác lập các cạnh. Không áp dụng score threshold để loại Candidate trong V1. Eligibility được quyết định bằng gates, không bằng điểm tổng.

## 2. Eligibility gates và kết quả khi không đạt

Mọi Candidate phải vượt các gates sau; chưa đủ dữ liệu không được thay bằng điểm thấp hoặc fallback.

| Gate | Điều kiện | Reason code khi không đạt |
| --- | --- | --- |
| Model | ED/EAE đã task-trained, có checkpoint và adapter manifest; supported eventTypes được khai báo | UNSUPPORTED_EXTRACTOR |
| Dictionary | EventType hợp lệ và thuộc phạm vi model; đủ required roles theo dictionary version | UNSUPPORTED_EVENT_TYPE / MISSING_REQUIRED_ROLE |
| Evidence | Required roles có support; offsets 0-based, end-exclusive, truy về exact source text version/hash; không vượt bounds | INVALID_EVIDENCE |
| Normalization | Kiểu dữ liệu, vocab và ràng buộc nghiệp vụ hợp lệ; không tự bịa thông tin thiếu | INVALID_NORMALIZATION |
| Identity | Resolve canonical business occurrence theo dictionary/identity registry; không lấy URL/ngày bài làm occurrence ID | UNRESOLVED_OCCURRENCE |
| Linking | Mọi required entity và optional route-entry được resolve duy nhất, đúng kiểu, trong registry hợp lệ tại cutoff | HOLD_LINKING |
| Cutoff | Mọi input có availability hợp lệ và availableAt <= inferenceCutoff | INPUT_AFTER_CUTOFF / MISSING_AVAILABILITY |
| Route | Một trong bốn paths hợp lệ, đúng endpoints và Stock đích, đủ supporting facts | UNSUPPORTED_PATH / MISSING_ROUTE_FACT |
| Temporal facts | Chọn đúng version trước khi kiểm validity; exposure đúng scope/period/staleness | INELIGIBLE_TEMPORAL_FACT |
| Scores | Đủ scores bắt buộc, finite, trong [0,1] | INVALID_MODEL_SCORE / INVALID_SCORE_INPUT |

Lỗi ở Event/assignment giữ record staging/HOLD, không tạo Candidate. Lỗi chỉ thuộc một route thì suppress route đó; routes hợp lệ khác vẫn được xét. `INVALID_MODEL_SCORE` là lỗi producer/adapter phải điều tra, không được âm thầm bỏ qua như dự đoán chất lượng thấp. Gold Events bị bỏ sót vẫn thuộc common evaluation universe nếu protocol độc lập không loại chúng.

Gate structural/normalization pass không chứng minh semantic correctness. Actor attachment, event boundary, assertion state và role correctness phải được đánh giá bằng gold độc lập; không báo tự kiểm đúng chỉ vì spans tồn tại trong text.

## 3. Extraction score producer

### 3.1. Checkpoint và adapter

Pretrained PhoBERT nguyên bản không phải ED/EAE extractor. Automatic V1 yêu cầu checkpoint đã fine-tune, lưu model/task-head/tokenizer/segmentation/decoder versions. Fixture/gán tay ghi `ASSISTED`, không dùng làm kết quả automatic.

Reference adapter `V1-SENTENCE-TRIGGER-BIO` của slice đầu tiên dùng ED BIO trigger detection, phân loại EventType đơn nhãn cho từng trigger/event instance và EAE BIO có điều kiện theo instance. Trigger score là min selected BIO token scores, bắt buộc tham gia assignment min cùng EventType và required roles. Nếu có neural association decisions bắt buộc khác thì cũng đưa vào min. Không dùng classification cả bài để phân biệt nhiều occurrences. Instance/trigger và role assignment có IDs riêng. EVENT_SCHEMA.md khóa original-text sentence Evidence producer, trigger-to-instance mapping và window policy; ANNOTATION_GUIDELINE.md khóa gold anchors độc lập. Sentence splitter không nhận gold boundaries; cross-sentence fragments không được ghép trong reference adapter.

Adapter khác, gồm multi-label hoặc span classifier, phải có adapter ID/version và được khóa trước held-out test; không trộn output adapters/checkpoints trong cùng một ranking run. Manifest ánh xạ mọi required decision tới producer, cách decode và score accessor.

### 3.2. Chuyển logits thành scores

- Single-label classification: stable softmax trên toàn bộ label set; lấy score của nhãn decoder đã chọn.
- Independent multi-label classification: sigmoid của logit nhãn đã chọn; activation phải đúng training objective, không tùy ý chọn để tăng score.
- BIO token classification: stable softmax theo BIO label set tại từng token; lấy score của nhãn BIO decoder đã chọn.
- Span–role classifier: lấy softmax/sigmoid score của span–role được chọn theo training objective đã khóa trong adapter.
- Không dùng logits thô, margin, entropy hoặc điểm trung bình thay cho các accessors trên trong V1.

Stable softmax: `p_j = exp(z_j - max(z)) / sum_k exp(z_k - max(z))`. Sigmoid: `p = 1 / (1 + exp(-z))`, tính bằng implementation ổn định số học.

Đối với BIO, decoder chạy độc lập cho từng event instance. Chỉ decode token văn bản có offset mapping; bỏ special/padding tokens. BIO sequence vi phạm cấu trúc hoặc không align được về text gốc phải reject, không sửa nhãn âm thầm. Nếu decoder dùng constrained decoding/CRF thì accessor phải khai báo rõ là emission score hay marginal; reference adapter dùng softmax emission scores, không tự đổi sang sequence probability.

### 3.3. Role span score và decision completeness

```text
roleSpanScore = min(score của selected BIO label trên mọi token thuộc span)
```

Tính tất cả subword tokens thuộc span; không lấy token đầu hoặc chỉ token có score cao. Word segmentation, subword-to-original offsets và span boundaries phải được lưu trong adapter output. Role có nhiều fillers bắt buộc: tính mọi filler đã chọn trong assignment; role score là min của các filler scores. Không đưa mọi alternative predictions vào một assignment.

Required literal role được sinh từ neural extraction dùng score của quyết định/span tương ứng. Một role được chuẩn hóa deterministic từ span không nhận thêm điểm độc lập; giữ score của span đầu vào. Required role/occurrence ID resolve deterministic qua evidenced registry nhận `1.0` theo convention `DETERMINISTIC_SUPPORTED`, sau khi vượt gate; không coi đó là neural confidence. Resolve occurrence từ canonical Event có sẵn không thay thế evidence hỗ trợ assignment hiện tại.

Mỗi required dictionary role phải có entry trong decision manifest, dù là neural hay deterministic. Không có producer cho role bắt buộc thì assignment chưa hỗ trợ, không bỏ role đó khỏi phép min. Nếu identity/matching còn mơ hồ phải HOLD, không cấp 1.0 để hoàn tất manifest.

### 3.4. Assignment score

```text
assignmentScore = min(
    eventTypeScore,
    mọi requiredRoleScore,
    mọi required neural instance/trigger/association decisionScore nếu có
)
```

Optional roles không tham gia A. Optional entity được dùng làm route-entry vẫn bắt buộc có Evidence/link decision và relation support cho route đó. Thiếu bất cứ score neural bắt buộc nào là producer error; V1 không dùng extraction fallback 0.5. Mọi score finite, trong [0,1]; không clip sai số đầu vào để che lỗi.

## 4. Chọn Evidence và extractionConfidence

1. Khóa `inferenceCutoff = Event.availableAt`, là earliest supporting Evidence availability theo EVENT_SCHEMA.md. Không dời cutoff để chờ extraction đầy đủ.
2. Lập tập Evidence supporting cùng canonical Event, available không muộn hơn cutoff, có một complete assignment đã vượt gates và đồng thuận với normalized roles/identity snapshot.
3. Tính assignmentScore cho từng assignment; không ghép roles, windows hoặc partial Evidence để tạo complete assignment.
4. Một Evidence có nhiều complete assignments tương đương: chọn assignmentScore giảm dần, assignmentId tăng dần theo case-sensitive Unicode codepoint order.
5. Trong tập Evidence hợp lệ, chọn assignmentScore cao nhất; tie-break Evidence URI tăng dần theo cùng quy tắc.
6. Gán `A = extractionConfidence = selected assignmentScore`.
7. Freeze eligible/selected Evidence, assignments và quyết định chọn. Không chọn lại Evidence để cứu route hoặc nâng linking score.

Nếu không có complete Evidence tại cutoff: `NO_COMPLETE_EVIDENCE_AT_CUTOFF`, không Candidate. Conflicting assignments không được score tự xử lý thành một assertion; giữ riêng assertions/HOLD theo identity policy. Reports đến sau cutoff không thay snapshot.

Inference qua nhiều windows giữ assignment riêng cho từng window; không ghép các role fragments giữa windows trong reference adapter. Stable assignmentId phải dựa trên frozen output identity/offsets, không dùng số ngẫu nhiên hoặc execution order. Optional fields khác nhau vẫn phải freeze chính xác assignment đã chọn.

## 5. Source confidence

```text
NewsSource.reliabilityScore = 0.5
S = sourceConfidence = 0.5
```

Áp dụng đồng nhất cho nguồn tham gia V1. Selected Evidence phải có Article/Source provenance. Không tăng điểm theo số bài, số nguồn, reprints hoặc max source score. Đánh giá/ranking nguồn là extension khác, không thuộc V1.

## 6. Entity linking confidence

### 6.1. Quy tắc resolve

Chỉ chấp nhận exact match mã định danh chuẩn, exact normalized canonical name hoặc exact normalized alias đã đăng ký. Phải đúng entity type, đúng scope/thời gian và resolve duy nhất tại cutoff. Normalization theo versioned registry/dictionary; không fuzzy matching hoặc đoán từ ticker để tự đồng nhất Company với Stock.

Nếu nhiều matched keys cùng resolve tới cùng typed entity, đây vẫn là một quyết định duy nhất. Nếu resolve tới nhiều entity IDs hoặc các keys mâu thuẫn, HOLD; không chọn match có vẻ tốt nhất bằng thứ tự tên.

```text
linkDecisionScore = 1.0 cho mỗi quyết định resolve đạt quy tắc
L = linkingConfidence = min(tất cả required linkDecisionScores của route)
```

`1.0` là convention registry-resolved, không phải accuracy thực tế 100%. Registry phải được đánh giá riêng. Fuzzy-only, ambiguous, absent hoặc future mapping => HOLD/suppress; không dùng 0.5/0.7/0.8 để cứu link.

### 6.2. Link inputs theo route

`E` là links của tất cả dictionary-required entity roles từ selected assignment, kể cả entities ngoài path; thêm optional route-entry nếu route sử dụng. Literals/dates/document IDs không phải entity links. `M` là terminal Company–Stock mapping đúng Company và Candidate Stock.

| Route | Required linking inputs |
| --- | --- |
| DIRECT | E; selected Company entry; terminal M |
| INDIRECT_SUBSIDIARY | E; selected child Company; child/parent endpoint identity mappings của selected SubsidiaryRelation; parent terminal M |
| INDIRECT_LEADERSHIP | E; selected CorporateLeader; leader/company endpoint identity mappings của selected LeadershipPosition; position-company terminal M |
| INDIRECT_INDUSTRY | E; selected Industry; industry/Bank endpoint identity mappings của selected IndustryExposure; Bank terminal M |

Propagated parent/Bank/position-company không cần mention trong article; identity phải đến từ eligible typed facts/registry. Không lấy links từ Evidence khác. Một decision xuất hiện nhiều lần chỉ ghi một decision ID, không tạo thêm bằng chứng độc lập.

## 7. Relation confidence

### 7.1. Điểm support cho mỗi cạnh/fact

| Support origin | Điều kiện | edgeSupportScore |
| --- | --- | --- |
| CURATED_STRUCTURED | Fact đã được kiểm duyệt trong registry/dataset cấu trúc, có provenance, version và eligibility/validity | 1.0 |
| AUTOMATIC_EVIDENCED | Fact suy ra tự động, có Evidence, vượt validation, chưa calibrated/curated | 0.5 |
| Missing/unsupported/ineligible | Không đủ fact, provenance, endpoint hoặc temporal eligibility | Không chấm; suppress path |

Có cấu trúc dữ liệu không đồng nghĩa đã curated. Import output tự động vào registry không tự nâng 0.5 lên 1.0. Curated fact phải có curation record/version và availability không sau cutoff; review diễn ra sau cutoff không nâng điểm lịch sử. V1 không dùng numerical relationConfidence legacy khác hai mức này; retain raw legacy value trong audit, nhưng tính active score theo support origin V1.

Event–Company/Event–Leader/Event–Industry support của automatic extractor dùng 0.5 khi được selected Evidence hỗ trợ. Không sao chép A hoặc Company linker score sang relation score. Curated fixture không làm automatic extraction run thành curated support. Optional route-entry phải có explicit supporting assertion và đúng attachment; mention xuất hiện trong text thôi chưa đủ.

### 7.2. Tổng hợp path

```text
R = relationConfidence = min(mọi required edgeSupportScore trên path)
```

| Route | Required relation-support inputs |
| --- | --- |
| DIRECT | Event–Company support; Company–Stock mapping support |
| INDIRECT_SUBSIDIARY | Event–child support; selected SubsidiaryRelation business fact support; parent terminal mapping support |
| INDIRECT_LEADERSHIP | Event–Leader support; selected LeadershipPosition business fact support; position-company terminal mapping support |
| INDIRECT_INDUSTRY | Event–Industry support; selected IndustryExposure business fact support; Bank terminal mapping support |

Endpoint identity decisions kiểm ở linking gate; các asserted endpoint bindings/ownership phải có provenance và là một phần của corresponding relation fact validation. Curated identity mapping không tự chứng minh economic relation đã curated. Không minimize unrelated registry facts hoặc lấy max relation score từ facts không được selected.

## 8. Relation strength

```text
T = relationStrength = 1.0 cho mọi eligible route
```

| impactType | V1 relationStrength |
| --- | --- |
| DIRECT | 1.0 |
| INDIRECT_INDUSTRY | 1.0 |
| INDIRECT_SUBSIDIARY | 1.0 |
| INDIRECT_LEADERSHIP | 1.0 |

V1 chưa đo economic exposure/path magnitude và không phân biệt strength DIRECT/INDIRECT. Constant 1.0 là experimental control, không phải tuyên bố các relations có tác động thực tế như nhau. Exposure facts vẫn cần đủ fields và đúng selection contract để route hợp lệ; không fabricate exposure khi strength cố định. Exposure-strength hoặc decay variants cần method/config/protocol riêng, không âm thầm dùng trong V1.

## 9. Execution order và immutable audit

```text
cutoff eligibility
→ validate/scoring complete extraction assignments
→ select Evidence assignment một lần
→ resolve required entity links
→ select temporal facts và eligible routes
→ assign edge support origin/scores
→ S, A, L, R, T
→ confidenceScore
→ candidateScore
→ immutable Candidate snapshot
→ completed market window
→ Reaction
```

### 9.1. Required audit record

Lưu ngoài RDF trong immutable JSON/JSONL sidecar; không mặc nhiên thêm ontology properties/classes. RDF Candidate giữ các components hiện có, cutoff và methodVersion. Candidate ID phải resolve tới exact audit record/hash trong run manifest.

- Identity: candidateId, eventId, canonicalKey, stockId, impactType, relationPath, selected assignmentId.
- Versions: documentVersion, methodVersion, adapterVersion, model/checkpoint hash, task heads, tokenizer, segmentation, decoder, label vocabulary, dictionary, normalizer, registry, temporal facts, ontology/shape, config hash.
- Time: Event.availableAt, inferenceCutoff, generatedAt, availability mode observed/proxy; timezone-aware instants; snapshot/run IDs.
- Evidence: source Article/Source IDs, source text/hash, eligible Evidence IDs, selected URI, offsets, role values, normalized values, eligible/selected assignment IDs, selection sort keys, exclusion reason codes.
- Model decisions: decisionId, role/type/instance, chosen label, full finite logits or lossless full score vector, token IDs, offset mapping, selected tokens/labels, activation, decisionScore and aggregation. Storing replay scores does not imply re-running GPU inference yields bit-identical output.
- Deterministic decisions: role producer, supporting span/registry ID, normalization/identity rules, result, convention flag.
- Linking: required decision set E and M, match mode, normalized key, matching candidate entity IDs, chosen typed ID, availability/version, decision score.
- Relations: selected fact/business-key/version, endpoints, availability/validity decision, curation/provenance record, support origin, raw legacy score if any, active edgeSupportScore.
- Scores: original S/A/L/R/T, confidenceScore, candidateScore, constants, numeric conversion/rounding policy, ablation settings.
- Freeze: content hash of exact inputs and audit record; any correction creates separate snapshot/version, never overwrites.

### 9.2. Numeric contract

Compute activation/model accessors in float64; reject nonfinite logits/scores. Convert each final neural decision score through its round-trip decimal string to Decimal. Aggregate minima, sums, divisions and products using Decimal precision 50, ROUND_HALF_EVEN. Serialize decimals as numeric lexical strings without display rounding. Ranking uses stored full-precision candidateScore, not rounded UI values. Replay from frozen decision scores must reproduce serialized score values exactly; independent RDF/SHACL arithmetic comparisons use absolute tolerance 1e-9.

No clipping out-of-range inputs. Display rounding is output-only and cannot be used for Evidence/path selection. Hold the scored inputs fixed when rerunning aggregation; model retraining is not a replay.

## 10. Reaction-time score (giữ công thức hiện hành)

Chỉ tính sau khi toàn bộ configured event window đóng và mọi observations cần thiết đã available, bao gồm session ngay trước session đầu tiên trong window.

```text
R(i,t) = adjustedClose(i,t) / adjustedClose(i,t-1) - 1
AR(i,t) = R(i,t) - R(m,t)
CAR(i,[a,b]) = sum(AR(i,t), t thuộc mọi trading sessions [a,b])
impactScore = min(1, abs(CAR) / tau)
reactionWeight = impactScore * frozenCandidate.confidenceScore * frozenCandidate.relationStrength
signedWeight = reactionWeight * sign(CAR)
```

Khóa `tau=0.10`, `epsilon=0`; marketReactionDirection theo exact sign CAR. Reaction dùng Candidate components V1 đã freeze; không recompute A/R/T từ dữ liệu mới. R(i,t) trong mục này là asset return, không phải ký hiệu R của relationConfidence ở mục 1.

`adjustedClose` > 0 là source of truth cho Stock và benchmark; `returnValue` là cache phải tính lại và khớp absolute tolerance 1e-9. Window `[a,b]` links một observation mỗi asset/session cho `t_(a-1), t_a, ..., t_b`. Asset ownership phải đúng Candidate Stock/Reaction benchmark; date sets phải giống nhau, không duplicate, đủ consecutive exchange sessions.

Supported windows `[0,0]`, `[0,+1]`, `[0,+3]`, `[-1,+1]` đều chứa 0. `abnormalReturn=AR(i,0)`; `cumulativeAbnormalReturn` là tổng AR cho toàn window inclusive. Không dùng partial-window CAR làm kết quả cuối. `[-1,+1]` là retrospective robustness, không cung cấp Candidate ranking inputs.

Run manifest lưu provider/dataset snapshot, adjusted-price/corporate-action convention, benchmark, exchange và calendar version/hash. Calendar-aware validator kiểm exact sessions; SHACL arithmetic pass không chứng minh coverage đúng calendar. Reaction observations có availableAt <= Reaction.availableAt, không bắt buộc <= Candidate cutoff.

## 11. Anti-leakage và temporal selection

- `inferenceCutoff = Event.availableAt` chính xác; chỉ inputs availableAt <= cutoff. generatedAt replay muộn hơn không cho phép dùng future inputs.
- Earliest availability thiếu complete assignment => no baseline Candidate, giữ coverage miss; không đẩy cutoff tới bài sau hoặc bỏ missed gold positives khỏi universe.
- LeadershipPosition/SubsidiaryRelation/IndexMembership chọn latest cutoff-available version theo business key rồi mới kiểm inclusive validity tại local cutoff date; không fallback older open-ended version.
- IndustryExposure chọn theo fixed scope và YEAR/newest period rule, inclusive 365-day staleness, availability/URI tie-break của EVENT_SCHEMA.md; không broadcast tới toàn ngành.
- Timestamps timezone-aware; compare UTC, derive local dates Asia/Ho_Chi_Minh. Missing acquisition time chỉ được dùng declared proxy mode, không giả observed historical availability.
- Day 0 là first exchange session có Event.availableAt < session.open strict; equality tại open chuyển sang next session. Không dùng weekday arithmetic thay exchange calendar.
- Late Evidence không sửa Event/cutoff/day 0 hoặc historical Candidate. New substantive assertion có Event riêng; corrections/reconstructions phải version riêng.
- `reactionWeight`, CAR, future returns, future curation hoặc gold labels không dùng để chọn Evidence, tính Candidate hoặc tune trên held-out test.

## 12. Multi-path aggregation và ranking

Chấm từng eligible path riêng. Group theo exact method/config, cutoff và `(Event, Stock)`:

```text
stockRankingScore = max(candidateScore của eligible paths)
```

Tie representative path theo Candidate URI ascending; Stock ranking theo score descending rồi Stock URI ascending. URI order case-sensitive Unicode codepoint, không locale collation. Không sum/average nhiều paths hoặc articles. CAR không cộng qua duplicate paths; paths không phải independent events.

Candidate URI/assignment IDs phải deterministic từ frozen semantic identity và method/config; không dùng timestamp execution/random ID làm tie-break. Không có score threshold trong V1; eligibility rejects vẫn được ghi vào ledger.

## 13. Evaluation và ablations của V1

- Giữ common Event/Stock universe, cutoff, eligible paths và independently adjudicated gold; không đánh giá chỉ trên accepted outputs.
- Unweighted comparator: score 1 trên cùng eligible population; không thay gates.
- V1 weighted ranking: candidateScore theo tài liệu này.
- Ba component-neutralization variants: thay riêng A, L hoặc R bằng 1; giữ Evidence/assignment/path selection, original edge scores, S=0.5 và T=1.0. Tính lại tổng, dùng separate methodVersion/Candidate URI.
- Linking đã constant 1 trong V1 nên neutralization L không thay ranking; phải báo là non-informative ablation, không claim chứng minh linker không quan trọng.
- R có thể constant 0.5 trong automatic population; nếu không có variation phải báo rõ. Source/strength đều fixed, không claim đã đo source reliability hay economic path strength.
- Exposure-strength comparison của 1.0.4 không thuộc active V1. Cần giữ dưới method legacy riêng hoặc định nghĩa variant mới và đồng bộ protocol trước chạy.
- Báo ED/EAE correctness, argument/identity/link/path errors, coverage/rejects và association score–correctness trên gold. Không dùng SHACL pass thay semantic quality hoặc gọi min/mean là calibrated probability.
- Lock mọi formulas, adapters, label/vocab versions và selection/config trước final test. Calibration/scoring changes tạo method mới, chọn trên development/validation.

## 14. Acceptance checklist cho implementation

1. Cùng frozen inputs/versions => cùng selection, components, ranking và serialized scores.
2. Missing required role/identity, invalid offsets, ambiguous links hoặc unavailable facts => no relevant Candidate/path, có reason code.
3. Invalid neural scores => producer error; không fallback extraction hoặc clip.
4. Complete assignment selection theo max score và URI/assignment tie-break; không mix roles/Evidence/windows hoặc reselect để cứu route.
5. Linking accepted => đúng exact typed entity/registry provenance và L=1.0.
6. Edge origins => đúng 1.0/0.5; thiếu fact suppress; không reuse linker/A làm relation confidence.
7. S=0.5, T=1.0 cho cả bốn routes; tổng và candidateScore đúng công thức.
8. Reprints/multiple paths không cộng điểm; grouping và tie-break deterministic.
9. Audit đủ để replay không cần current mutable registry; late inputs không sửa snapshots.
10. Reaction có complete sessions, correct benchmark, adjustedClose provenance, tau/epsilon và frozen Candidate values; không partial-window result.
11. Automatic/ASSISTED và V1/legacy outputs được tách; báo coverage và constant/non-informative ablations đúng thực tế.
12. Trước bundle acceptance: đối chiếu EVENT_SCHEMA, TTL/SHACL, annotation/evaluation, demos và diagrams/reports; chạy tests trên đúng method/shape/config. Việc hoàn tất tài liệu này không có nghĩa các artifact đó hoặc implementation đã được cập nhật.
