# Đối chiếu specification V1 và hồ sơ kiểm tra Phase 1

## Current Phase 2 specification boundary — document version 1.1.0

Active method: WFKG-SCORE-V1. EVENT_SCHEMA, SCORING_SPEC, EVALUATION_PROTOCOL và ANNOTATION_GUIDELINE dùng cùng numerical/producer policy: S=.5; A từ trained required decisions không fallback; accepted exact typed unique links L=1; R=min edge supports automatic .5/curated eligible 1; T=1 cả bốn routes. Schema namespace/classes/properties và dictionary taxonomy không đổi.

Luồng active: crawl/snapshot availability → trained PhoBERT V1-SENTENCE-TRIGGER-BIO Evidence/roles → deterministic normalization/identity/exact registry linking → eligible four routes → immutable V1 Candidate/audit → calendar/adjustedClose → complete-window Reaction → RDF validation/diagnostics/replay. Direction dùng Dictionary rule per Candidate, thiếu căn cứ UNKNOWN. Gates và gold independence không bị giản lược.

EVALUATION_PROTOCOL tách INTEGRATION_DIAGNOSTIC, AUTOMATIC_VERTICAL_SLICE và FINAL_RQ; 100–300 batch, four executors regression và real per-route coverage ghi riêng. Final support floors/OWL semantic relation metrics/full ablations/CIs không chặn first integration. L ablation no-op và constant R được báo non-informative. Exposure-strength comparison thầy yêu cầu giữ thành separately versioned experiment sau automatic slice.

**Không coi gói đã đồng bộ hoàn toàn V1:** phần DOCX/PDF/Draw.io/demo và historical verification_contract_1.0.4.json dưới đây chưa được regenerate/audit về numerical V1 prose. TTL/SHACL giữ structural authority; method-aware V1 gates vẫn phải hiện thực/kiểm thử. Existing regression PASS chỉ xác nhận structural behaviors được tests bao phủ, không NLP performance, calibration, calendar correctness hoặc real-data acceptance. Approval của thầy và runtime acceptance chưa được thay thế bằng sửa Markdown.

| Active contract | Authority / required verification |
| --- | --- |
| Constants, accessors, edge origins, selection and decimal replay | SCORING_SPEC 1.1.0; method-aware producer/selection regression and audit, không chỉ SHACL pass |
| Evidence producer, temporal facts, direction, lifecycle/window readiness | EVENT_SCHEMA 1.1.0; original-text/trigger/window/calendar/late-fact tests |
| Split ownership, three profiles, diagnostic artifacts and final metrics | EVALUATION_PROTOCOL 1.1.0; manifests, independent gold, coverage and replay |
| Independent gold/whole-sentence anchors and audit separation | ANNOTATION_GUIDELINE 1.1.0; double-label/agreement, scores withheld from gold decisions |
| Structural schema/cardinality/inverse/arithmetic | unchanged ontology_v1.0.ttl/shapes_v1.0.ttl; existing SHACL/diagram regression, plus method gates outside generic shapes |

## Historical 1.0.4 acceptance evidence — not the active V1 numerical contract

All remaining sections below describe the prior 1.0.4 package and its historical tests/rendering. Legacy indirect strength/fallback statements and whole-package readiness conclusions apply only to that snapshot. Do not use them to override current V1 Markdown rules or claim reports/diagrams were updated in this synchronization.

Contract: **1.0.4**. Namespace giữ nguyên `https://example.org/wfkg/v1#`; ontology giữ 22 lớp, Draw.io giữ 7 tab. TTL/SHACL là nguồn chuẩn về schema/cardinality; các specification Markdown/YAML khóa thuật toán và protocol; Draw.io là minh họa. Không mở rộng lớp, không triển khai pipeline dữ liệu thật trong đợt hiệu đính này.

Nguồn yêu cầu: `ban_thay_gop_y/gop_y_phase1_truoc_code_phase2.txt` của workspace. Ma trận dưới đây ghi mức đáp ứng **đặc tả Phase 1**, không thay thế việc thầy duyệt lại hoặc acceptance end-to-end Phase 2.

## 1. Ma trận 9 góp ý

Số trang là trang vật lý của PDF hiện hành, được xác định sau khi Microsoft Word render, không suy ra từ paragraph index.

| Mục góp ý | Nội dung đã khóa/hiệu đính | Nguồn trong gói và locator báo cáo | Phạm vi xác minh/việc Phase 2 |
|---|---|---|---|
| 1. PDF–Draw.io–TTL | Thống nhất WFKG/namespace, 4 route baseline; chỉ chiều con→mẹ, Industry→exposure Bank, không broadcast cùng ngành hoặc parent→subsidiary. Sửa owner `hasSubsidiaryRelation`, ticker string/Stock URI, RDF `hasAlias`, GovernmentOrganization và datatype `availableAt`. Comment cutoff TTL và ghi chú temporal tab 03 đã sửa theo nguồn chuẩn. | `ontology_v1.0.ttl`, `shapes_v1.0.ttl`, Draw.io tab 00/01/02/03/05; PDF mục 2.1, tr.4–6; phụ lục A, tr.43–45. | RDF/XML parse, audit appendix và parent-owner invariant; tab 03 được render lại sau sửa. Audit không chứng minh tất cả connector semantics. |
| 2. Daily effectiveTradingDate | Day 0 là phiên đầu có opening **strictly after** Event.availableAt; tin trước open dùng phiên đó, đúng open/intraday dùng phiên sau. Khóa `inferenceCutoff = Event.availableAt`; replay generatedAt muộn không được lấy future inputs. Không có complete assignment thì ghi miss, không lùi cutoff. | `EVENT_SCHEMA.md`: Effective trading date, Candidate temporal eligibility, Daily windows; PDF mục 2.4/2.7, tr.20–25. | SHACL kiểm equality và timestamp ordering. Calendar/exchange/session thật cần validator Phase 2; ví dụ 26/08 14:16→27/08 là giả định lịch, không phải lịch được bộ test xác thực. |
| 3. Confidence components | Lưu source/extraction/linking/relation và điểm tổng trên Candidate. Source baseline 0,5. Chọn complete Evidence assignment theo extraction, required-role min; max giữa assignments và URI tie-break. Linking phải dùng cùng assignment; khóa input table bốn route, DIRECT relation confidence, registry/automatic mapping/fallback và provenance. | `SCORING_SPEC.md`: Component sources and aggregation; `ANNOTATION_GUIDELINE.md`; PDF bảng Candidate tr.12–14, mục 2.7 tr.24–26. | Synthetic tests bắt missing/wrong score. Selection/calibration thực, input decision audit và immutable snapshot phải triển khai ở Phase 2. Không gọi heuristic confidence là xác suất calibrated hoặc giả định component độc lập. |
| 4. candidateScore/reactionWeight | candidateScore=confidenceScore×relationStrength cho inference ranking; reactionWeight thêm impactScore chỉ sau window. Chỉ max(candidateScore) trong cùng Event–Stock/method/cutoff; reactionWeight báo riêng từng path, không cộng CAR lặp. DIRECT strength=1, indirect=0,5; biến thể exposureRatio được định version riêng. | `SCORING_SPEC.md`, Draw.io tab 04/05; PDF RQ3 tr.2 và mục 2.7 tr.24–26, mục 2.8 tr.26–28. | SHACL kiểm công thức baseline và lifecycle; chưa chạy ranking/exposure variant trên dữ liệu thật. |
| 5. Market provenance | Stock/benchmark adjustedClose, nguồn, availability; Reaction truy observations đúng asset/date, đủ predecessor và mọi phiên trong window; AR ngày 0 và tổng CAR, tau/epsilon baseline rõ. | TTL/SHACL, `EVENT_SCHEMA.md`: Daily windows; PDF bảng observations tr.11–12, Reaction tr.15, mục 2.7 tr.24–26. | Behavioral tests về benchmark close, daily return, CAR, impact/direction. Exchange-calendar continuity và raw vendor adjustment/version là gate Phase 2, không được suy từ ngày synthetic. |
| 6. Event Dictionary | 14 eventType, description/required/optional roles/key/direction/positive-negative/confusables. Bổ sung role-specific normalization vocabulary và reporting-period grammar; unknown/ambiguous giữ HOLD, không invent token hoặc suy năm từ ngày báo. | `EVENT_DICTIONARY.yaml`, `ANNOTATION_GUIDELINE.md`; PDF mục 2.5 tr.22–23, phụ lục D tr.47. | YAML parse và cấu trúc 14 entries kiểm lại. Chưa có NLP/key-normalization executor; mapping/token là extraction contract, không phải class mới. |
| 7. Data rules | Article reports 0..* ở staging, curated yêu cầu Event đủ điều kiện. Ba relation temporal chọn latest available theo business key trước validity, không fallback bản cũ. IndustryExposure tách reporting scope, YEAR baseline, periodEnd≤cutoff, availableAt≤cutoff, newest-period/availability/URI selection và stale≤365 ngày. Exposure variant strength=ratio, không đổi baseline hằng số. | `EVENT_SCHEMA.md`: Temporal relation version selection / IndustryExposure selection; `SCORING_SPEC.md`; PDF tr.18, 21 và phụ lục C tr.46; Query 7 tr.37 ghi prerequisite scope-prefilter. | Cardinality và schema có kiểm; registry/calendar/selection gate thực chưa triển khai. Missing fact/link không được cứu bằng confidence fallback. |
| 8. Evaluation | Tách vertical slice 100–300 bài/development/validation/final; double-label 25%, agreement/adjudication. Freeze Event/Stock frame/universe độc lập score/CAR; out-of-universe prediction invalid, không post-filter top-K. Giữ gold Event bị extractor miss với empty ranking/FN. Overall relevance 0/1/2, route support độc lập trên common negatives; projection trước max/top-K, gain/IDCG/macro Event/empty cases/bootstrap được khóa. Bổ sung exact one-to-one RQ1 matching và method contracts: shared extractor; keyword toàn văn/alias chính xác/score 1/bucket DIRECT; RQ2 KG score 1, RQ3 mới so candidateScore. | `EVALUATION_PROTOCOL.md`, `ANNOTATION_GUIDELINE.md`; PDF mục 2.8 tr.26–28, kế hoạch tr.41, phụ lục D tr.47. | Đây là protocol đã đặc tả, chưa thu final dataset, gán nhãn kép, chạy metrics/bootstrap hay chứng minh RQ1–RQ3. Unmapped output có ledger riêng, không bị bỏ im lặng. Không loại Event vì model thiếu complete assignment để nâng recall. |
| 9. Property appendix | Đồng bộ object/datatype names/owners/ranges/cardinality được biểu diễn; có subsidiaryCompany/memberStock/exposureBank/exposureIndustry/forEvent. Audit script có trong gói; thêm mutation tests parent-owner vì domain/range Company không phân biệt mẹ/con. | Draw.io tab 06, `tools/audit_schema_diagram.py`, `tools/test_schema_diagram_audit.py`; PDF mục 3.3/3.4 tr.41–42 và phụ lục A tr.43–45. | 337 PASS/0 FAIL/**57 NOT CHECKED**; không biến audit thành generic diagram validator. Những shared/narrative/implicit constraints vẫn có giới hạn, xem tools/README.md. |

## 2. Kết quả thực thi và tái chạy

Từ thư mục gói, dùng interpreter đã có RDFLib/pySHACL:

```text
py -3.13 -B tools/test_baseline_shacl.py
py -3.13 -B tools/test_schema_diagram_audit.py
py -3.13 -B tools/audit_schema_diagram.py
```

- SHACL behavioral regression: **31/31 unittest qua**, inference=none. Có negative REACTION_READY thiếu Reaction với plain/typed string, cutoff sớm/muộn, invalid enum, inverse/score/market consistency; positive replay dùng cutoff gốc. Một số method chứa nhiều subtest: số 31 không phải số tất cả fixture hoặc tỷ lệ coverage.
- Diagram-audit regression: **8/8 unittest qua**, mutation XML trong bộ nhớ, không sửa gói.
- Structural audit: **337 PASS, 0 FAIL, 57 NOT CHECKED**; **44 SELECT parse** được, input SHA256 không đổi trong lần audit. SELECT parse không phải behavioral execution.
- RDF/Turtle, YAML và XML parse được; giữ **22 OWL classes**, **14 dictionary eventType**, **7 Draw.io tabs**.
- DOCX package health check: `ok=true`, không có issue. Kiểm tra này không phải OOXML XSD validation hoặc bảo đảm layout.
- Log và hash của lần kiểm tra được ghi tại `tools/verification_contract_1.0.4.json`; số liệu đến từ execution, không phải expected output hoặc kết quả RQ.

## 3. Word/PDF và kiểm tra trình bày

Báo cáo hiện hành:

- `Bao_cao_Phase_1_Ontology_WFKG_ban_chot_da_dong_bo_hieu_dinh.docx`
- `Bao_cao_Phase_1_Ontology_WFKG_ban_chot_da_dong_bo_hieu_dinh.pdf`

PDF được xuất lại bằng Microsoft Word từ DOCX sau sửa, **47 trang**; export không lưu thay đổi vào nguồn và SHA256 nguồn không đổi trong export. Text extraction không phát hiện ký tự NULL hoặc replacement glyph. Đã xem contact-sheet bố cục toàn bộ 47 trang và ảnh trang sửa/mẫu đầu–giữa–cuối; không thấy trang trắng, bảng tràn trang hoặc overlap lớn. Đây là layout review, không khẳng định đã proofreading từng ký tự trên mọi trang.

Giữ **9 ảnh demo lịch sử**, hash media không đổi; ảnh hiện nằm ở các trang 31–36, 38–40. Caption nêu synthetic/history, chưa tái chạy contract hiện hành; ảnh không phải validation hoặc RQ evidence.

Draw.io: lần trước đã render 7 tab bằng official Draw.io viewer và Chrome. Lần này chỉ tab 03 thay đổi; đã render lại tab đó, nới ô ghi chú và xem ảnh để kiểm tra chữ không tràn. Các tab khác không đổi. Tab 00/06 dày thông tin, cần zoom khi đọc; không coi việc render thành công là mọi nhãn đã được kiểm tra ngữ nghĩa tự động. Renderer và ảnh kiểm tra chỉ nằm ở scratch, không là dependency vận hành của gói.

## 4. Phát hiện ở lượt review lại và thay đổi

Lượt đối chiếu độc lập phát hiện các điểm không thể kết luận chỉ bằng test PASS. Đã sửa:

1. Comment `inferenceCutoff` của TTL dùng nhầm Evidence **complete sớm nhất**. Nguồn chuẩn là Evidence **hỗ trợ sớm nhất**, thiếu complete assignment thì ghi miss, không dời cutoff.
2. RQ3 tr.2 ghi max cả reactionWeight. Đã sửa chỉ max candidateScore; hậu nghiệm báo reactionWeight riêng từng path.
3. Tab 03 mô tả mọi relation bằng validity. Đã tách IndustryExposure theo reporting scope/kỳ/staleness.
4. Markdown chưa nêu latest-version-before-validity như báo cáo. Đã khóa business keys, identity correction registry, tie-break và không fallback bản cũ ở EVENT_SCHEMA; scoring/annotation dẫn chiếu cùng quy tắc.
5. Keyword/co-occurrence chưa khóa text unit, matching, score và route view. Đã khóa ba method trong EVALUATION_PROTOCOL, đồng bộ mục 2.8 báo cáo.
6. RQ1 chưa khóa prediction–gold matching. Đã chốt text/hash/offsets, exact one-to-one, duplicate FP, unmatched FN, roles, end-to-end/oracle linking và downstream alignment/coverage ledger.
7. Query 7 và phụ lục exposure thiếu reporting-scope prerequisite. Đã ghi scope-prefilter trên graph truy vấn và scope trong nhóm chọn bản báo cáo. Review cuối xác nhận Query 7 còn so trực tiếp key fields: đã giới hạn rõ đây chỉ là minh họa khi key fields không đổi, không phải correction-aware executor; inference thực bắt buộc dùng registry selection ở EVENT_SCHEMA trước. Đã khóa complete-assignment gate chung cho cả keyword và hai KG method, không để keyword tự cứu missing assignment.

Giữ contract schema 1.0.4, 22 lớp, dictionary 14 loại, namespace và tên artifact; đây là bản hiệu đính/chốt rõ quy tắc trước code. Hash manifest hiện hành xác định đúng snapshot bàn giao, không dùng hash của bản trước sửa để chứng minh bản này. Không nâng các quy tắc vừa đặc tả thành executor đã chạy.

## 5. Gate trước Phase 2 và giới hạn kết luận

Sau hai lượt review độc lập và lượt tự đối chiếu các sửa cuối, không còn phát hiện blocking chưa xử lý trong 9 yêu cầu ở mức **specification trước code Phase 2**. Các điểm phát hiện, cách sửa và giới hạn query/validator đã được ghi ở mục 4. Gói được chuẩn bị để **gửi thầy check lại một lần** theo kết luận góp ý. Đây không thay thế approval của thầy, không tuyên bố mọi constraint đều được kiểm tra tự động hoặc final evaluation đã hoàn tất.

Phase 2 còn phải hiện thực/kiểm thử: input snapshot bất biến; calendar/session và temporal eligibility; versioned registry/REF mapping; complete Evidence/link decisions và normalization; IndustryExposure selection/staleness; data provenance/adjustment; curated gate; metric/ranking executor với universe/route views; annotation agreement; real-data vertical slice. Chỉ sau những gate đó mới mở rộng dữ liệu và chạy held-out RQ1–RQ3.

Không thay đổi namespace/tên các artifact hiện hành, không thêm lớp, không cài package, không commit/push. Các bản backup/render/probe không nằm trong acceptance set của gói.
