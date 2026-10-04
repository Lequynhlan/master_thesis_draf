# Review trước gửi — Standards / ontology machine-readiness của gói hiện hành

## 1. Kết luận ngắn

**PASS trong phạm vi schema/audit/regression đã chạy; chưa đủ để gọi gói là một validator end-to-end cho phương pháp WFKG-SCORE-V1.** Không tái hiện được lỗi HIGH/BLOCKER về OWL shared-domain hoặc công thức AR/CAR trong phạm vi kiểm tra này. Có **một điểm MEDIUM ở trust boundary của SHACL không inference**: kiểm tra Event có Evidence hỗ trợ có thể được thỏa bằng node chưa có type Evidence và thiếu các trường Evidence bắt buộc. Các phần identity/dictionary/calendar/method-specific constants/temporal selection chưa được generic SHACL enforce đã được đặc tả rõ là gates Phase 2; không nâng chúng thành lỗi Phase 1 chỉ vì runtime chưa tồn tại.

TTL/SHACL là nguồn chuẩn về mô hình; không đề nghị ép chúng theo diagram hoặc prose legacy. Baseline S=0.5 là experimental control đã công khai, không phải một lỗi thiếu calibration. Tài liệu scoring hiện hành có trained-task score producer và audit contract; review này không đánh giá lựa chọn PhoBERT so với LLM.

**Có thể dùng kết quả này để gửi thầy kiểm lại phần schema/spec với đúng giới hạn. Không dùng nó để tuyên bố toàn bộ gói đồng bộ V1 hay pipeline chạy thật.** PHASE1_ACCEPTANCE.md:3–23 đã tách rõ current V1 và historical 1.0.4. Review DOCX/PDF nội dung, trình bày và protocol annotation/evaluation chuyên sâu không nằm trong trục review này.

## 2. Phạm vi và không thay đổi nguồn

- Gói duy nhất: `D:\project\master_thesis\01-10-2026\chỉnh sửa mới nhất - 01-10`.
- Workspace: `D:\project\master_thesis\01-10-2026`; Git branch live `docs/phase1-contract-1.0.4`.
- Trước review đã có sửa chưa commit ở ANNOTATION_GUIDELINE, EVALUATION_PROTOCOL, EVENT_SCHEMA, PHASE1_ACCEPTANCE, SCORING_SPEC. Đây là current-folder review, không phải diff review; không revert và không ghi đè các sửa đó.
- Đã đọc live ontology, shapes, tools README, cả audit và hai test scripts trước khi chạy; đọc SCORING_SPEC, EVENT_SCHEMA, EVENT_DICTIONARY, PHASE1_ACCEPTANCE và feedback `ban_thay_gop_y/gop_y_phase1_truoc_code_phase2.txt`.
- Gói có 17 file trong snapshot được hash, gồm cả bản backup SCORING_SPEC dưới `review_phase1/backups/`. Backup không được coi là active spec. Gói không có runner crawler/NLP/calendar/identity/ranking/market ingestion production; Python hiện diện chỉ là audit và synthetic regressions.
- Không chạy generator; không sửa TTL/SHACL/diagram/reports/input scripts/matrices. Mọi mutation diễn ra trên Graph copy, serialize/reload trong thư mục tạm `review_phase1/presend-machine-*` ngoài gói rồi tự xóa.
- SHA256 cả 17 file trước/sau final run không đổi: `changed_inputs=[]`. Không ghi nhận nguồn thay đổi trong cửa sổ execution này; không khẳng định rằng các file không từng thay đổi trước snapshot.

## 3. Kết quả thực thi có thể kiểm chứng

Artifact mới, ngoài gói:

1. `review_phase1/presend_machine_probe.py` — runner chỉ đọc, chạy các entry points đã kiểm tra và diagnostic trên temporary serialized copies.
2. `review_phase1/presend_current_machine_execution.json` — interpreter/dependencies, exact argv/cwd/exit code, đầy đủ stdout/stderr, schema/dictionary inventory, hashes, 20 probe graphs + conformity/messages.
3. Báo cáo này.

Từ workspace, lệnh tái chạy:

```text
python -B review_phase1/presend_machine_probe.py
```

Runner gọi từng script bằng `sys.executable -B` với đường dẫn tuyệt đối, cwd là workspace ngoài gói:

```text
python -B "chỉnh sửa mới nhất - 01-10/tools/audit_schema_diagram.py" --json
python -B "chỉnh sửa mới nhất - 01-10/tools/test_baseline_shacl.py"
python -B "chỉnh sửa mới nhất - 01-10/tools/test_schema_diagram_audit.py"
```

Môi trường thực tế: `C:\Python314\python.exe`, Python 3.14.3, RDFLib 7.6.0, pySHACL 0.40.1. Lệnh thử `py -3.13` thất bại vì interpreter đó không có rdflib; chuyển sang interpreter đã có dependencies, không cài package. Không dùng thông tin Python 3.13.2/pySHACL 0.40.0 của manifest cũ như môi trường live.

| Kiểm tra | Kết quả final thực tế | Diễn giải |
|---|---|---|
| Audit structural TTL/SHACL/Draw.io | Exit 0; **337 PASS, 0 FAIL, 57 NOT CHECKED** | Chỉ các assertion tool hỗ trợ; không phải equivalence proof |
| Existing SHACL synthetic regression | Exit 0; **31 tests / OK**, 26.688 s | Inference=none, có subtests; không phải 31 góp ý hay coverage % |
| Existing diagram audit regression | Exit 0; **8 tests / OK**, 1.653 s | XML mutation trong memory, không sửa diagram |
| SHACL SELECT | **44** parse được | Parse không tự chứng minh logic; behavioral suite và probe kiểm riêng |
| Ontology inventory | **22 classes**, mọi class có targetClass shape, không có property với nhiều explicit domains | Shape có target không chứng minh mọi business invariant được enforce |
| Dictionary | **14 entries / 14 unique eventTypes**, không unknown confusable reference ngoài explicit out-of-scope, không key role nằm ngoài required/optional | YAML/contract inventory, chưa execute normalizer |
| Focused diagnostic | **20 probes**, `probe_expectations_met=true` | Có positive controls và deliberate invalid examples; conformity=true của ví dụ sai là bằng chứng boundary, không phải business PASS |
| Read-only | 17 input hashes không đổi | Snapshot execution cụ thể |

Existing test script kiểm negative lifecycle/cutoff/inverse/confidence/cached-return/CAR/impact/direction và positive replay/zero/negative/saturation. Bộ này bắt được lỗi cũ REACTION_READY thiếu Reaction, kể cả plain/typed string: không giữ lại finding lịch sử đã đóng. Test fixture hiện tại chủ yếu DIRECT (tools/test_baseline_shacl.py:13–38); ba route gián tiếp được positive-test thêm ở probe ngoài gói, không gọi đó là expansion của delivered suite.

## 4. Finding cần lưu ý

### M1 — MEDIUM: Event “requires supporting Evidence” chỉ kiểm một triple, có thể bỏ qua EvidenceShape khi inference=none

**Nguồn:** `shapes_v1.0.ttl:134–139` kiểm existence của `?e supports $this` và `?a reports $this`; `:136–137` dùng availability của node support mà không kiểm type. `:638–688` ràng buộc Evidence nhưng chỉ `sh:targetClass wfkg:Evidence`. `ontology_v1.0.ttl:458–461` domain Evidence là entailment, không phải SHACL closed-world validation. Existing runner chủ động `inference='none'` ở `tools/test_baseline_shacl.py:77–86`; EVENT_SCHEMA.md:67 nói SHACL không repair inverse.

**Tái hiện:** từ fixture positive serialized, xóa `evidence rdf:type Evidence`, `extractedFrom`, `evidenceId`, `evidenceText`, giữ `supports event` và `availableAt`. Probe `untyped_support_node_without_evidence_fields` trả **conforms=true**, không message. Cùng graph, `untyped_support_node_owlrl` trả **conforms=false**, bắt thiếu evidenceId/evidenceText/extractedFrom. Positive controls cả none và OWL-RL đều true, nên đây không phải full fixture vốn đã invalid.

**Tác động:** khi writer hoặc import bỏ type, Event/Candidate/Reaction có thể qua validation mà không có một Evidence node hợp lệ ở regime đang được regression-test. Conformance không còn bảo đảm đầy đủ điều đang phát biểu bằng message “Event requires supporting Evidence”. Không có pipeline thật để khẳng định lỗi này đã xảy ra trong dữ liệu; severity MEDIUM tại boundary, không HIGH về correctness thị trường.

**Remedy tối thiểu đề xuất, chưa thực hiện:** thống nhất regime nhập graph; nếu giữ inference=none thì gate kiểm support/report nodes đã typed đúng trước validate, hoặc thêm inverse-path class/shape check phù hợp để Event không nhận node support thiếu type. Thêm negative test untyped support node và positive test graph typed hợp lệ. Không cần thêm lớp/property, không tự bật reasoner để che lỗi thiếu inverse, không tự thay đổi schema trong lượt review này.

## 5. Khoảng trống enforcement đã biết — không tự gọi là Phase 1 defect

### G1 — Method V1 constants/origins nằm ngoài generic arithmetic shapes

**Nguồn:** SCORING_SPEC.md:27, :44, :127–149, :164–206, :302–315; EVENT_SCHEMA.md:42–54, :65–69; shapes:189–205, :250–264, :284–290; NewsSourceShape:1009–1027.

SHACL kiểm S=0.5 trên Candidate và equations, nhưng không kiểm NewsSource.reliabilityScore=0.5, L=1, T=1 hay R thuộc đúng 0.5/1.0 với edge-origin provenance V1. Probe:

- `source_registry_not_point5`: NewsSource reliabilityScore=.9, Candidate S vẫn .5 → **true**.
- `compensated_strength_not_V1`: T=.2, candidateScore=.1, reactionWeight=signedWeight=.01, các công thức giữ nhất quán → **true**.
- `compensated_linking_not_V1`: L=.2, confidenceScore=candidateScore=.425, reactionWeight=signedWeight=.0425 → **true**.

Đây là bằng chứng “equations đúng” không đồng nghĩa “method V1 đúng”, không phải công thức bị sai. Current spec đã nói methodVersion không override shape và gates method-specific cần hiện thực. **Priority trước gọi implementation ready:** bổ sung method-aware validator/producer regression cùng versioned manifest. Không ép hằng số của mọi methods vào shared shape và không coi S=.5 uncalibrated là thiếu rubric gây lỗi Phase 1.

### G2 — Event dictionary/identity: machine-readable specification có, executor và uniqueness gate chưa có trong gói

**Nguồn:** shapes:111–133 chỉ datatype/cardinality Event ID/key/type; EVENT_DICTIONARY.yaml:4–13, :32–79, :197–339; EVENT_SCHEMA.md:126–132; SCORING_SPEC.md:50–63.

`unknown_event_type` (UNDECLARED_EVENT_TYPE), `malformed_canonical_key` (empty string), `duplicate_event_canonical_key` (hai Event URIs, eventIds khác nhau nhưng cùng key, mỗi Event có Article/Evidence) đều **true**. Dictionary parse/14 types và coverage confusables/key fields đã PASS, nhưng generic shape không tham chiếu membership hoặc kiểm registry identity. Optional-key missing có MATCH_EXISTING_ELSE_HOLD rõ ràng, không phải mặc định cho phép tạo key thiếu.

**Remedy tối thiểu khi code:** execute frozen dictionary/normalizer/registry gate trước curated graph, check uniqueness/positive same-occurrence identity với reason ledger. Dùng negative examples trên làm method-level regression. Không coi toàn bộ YAML phải chuyển thành RDF property mới.

### G3 — Route topology có enforce; historical eligibility/endpoint selection còn ở curated gate

**Nguồn:** shapes:170–179, :277–338; EVENT_SCHEMA.md:35–42, :91–124. Bốn path đều có constraint về topology; direct stock không có Company link bị bắt, unknown impactType bị bắt, relationPath khác impactType bị bắt. Ba indirect positive graph controls đều **true**.

Nhưng sau khi đổi relation/exposure.availableAt sang `2026-08-28T10:00:00+07:00`, muộn hơn Candidate cutoff `2026-08-26T14:16:00+07:00`, cả `future_input_SubsidiaryRelation`, `future_input_LeadershipPosition`, `future_input_IndustryExposure` vẫn **true**. Shape bảo đảm node có availability/validity cấu trúc, không execute latest-version-before-validity, stale/reporting scope hay input-before-cutoff selection.

Subsidiary route yêu cầu Event child, relation child/parent endpoints và parent owns relation/stock (shapes:314–325); không đảo parent→child. Domain/range Company riêng lẻ không thể kiểm parent role. Audit riêng đã kiểm tab00 owner identity và có negative tests. Không suy rằng mọi instance `Company hasSubsidiaryRelation` trong graph đều được kiểm owner↔parent chỉ vì canonical route có exists path đúng. Generic SubsidiaryRelationShape:1048–1080 chưa enforce global owner identity; EVENT_SCHEMA:115 giao gate suppress mismatched ownership.

**Remedy tối thiểu khi code:** registry-aware temporal/ownership executor trước route, lưu selected fact URI/business key/reason, negative tests late/future/ended/corrected versions và wrong owner. Không tự gọi thiếu runtime này là lỗi Phase 1 vì spec đã khóa thuật toán và boundary.

### G4 — Calendar/session offsets là gate riêng, không thể suy từ arithmetic PASS

**Nguồn:** feedback:26–36, :76–90; EVENT_SCHEMA.md:71–79, :94–103; SCORING_SPEC.md:246–265; shapes:435–558, :579–615.

Shape kiểm số ngày khác nhau, paired dates, unique observation/date, asset ownership, positive closes, nearest linked predecessor return, AR tại t0, CAR sum, impact/direction/weights. Existing negative tests thực sự fail khi cached returns/CAR/impact sai.

`intraday_same_day_effective_date` đổi Event lúc 14:16 sang t0 cùng 26/08 và dùng stock/index series phẳng (return/AR/CAR/weights đều zero) → **true**. Đồ thị có đúng count/date pairing nhưng t0 là observation sớm nhất, không phải phiên theo strict-opening rule và không có đúng t0 predecessor. Điều này chứng minh count + arithmetic không đủ xác nhận exact session placement. Không trình bày ví dụ zero như dữ liệu thị trường thật.

**Remedy tối thiểu khi code:** calendar-aware validator so đúng list `t_(a-1)..t_b`, session openings/timezone, closure/input availability, frozen calendar hash; positive/negative boundaries trước open/đúng open/intraday/holiday và multi-window placement. Spec đã yêu cầu điều này; không đòi SHACL tự biết ngày nghỉ khi graph chưa có calendar. Runtime calendar hiện **NOT CHECKED / ABSENT trong gói**, không phải một kết quả đã kiểm sai lịch thật.

## 6. Standards / ontology reasoning

- TTL parse đúng; property declaration không bị dùng như “ghi đè”. Đã kiểm live accumulated triples: không property nào có nhiều explicit `rdfs:domain`.
- Shared properties `adjustedClose`, `returnValue`, `observationId`, `relationConfidence`, `availableAt`, `fullName`, `periodType`, `periodStart`, `periodEnd`, `methodVersion`, `sourceReference`, `validFrom`, `validTo`, `tradingDate`, `taxonomyName`, `dataQualityFlag` đều domain-neutral ở live graph. Không tái hiện pollution Candidate/Observation/temporal class từ shared domains cũ. Đặc biệt relationConfidence ontology:387–389 là domain-neutral, adjustedClose:15–16 và :593–595 có chủ ý tương tự.
- Ranges datatype và class-specific SHACL là hai cơ chế khác nhau, không bắt chúng phải có cùng owner list. Property không domain không có nghĩa thiếu mô hình; đây là shared vocabulary đúng dụng ý. Audit ghi 57 NOT CHECKED là đúng giới hạn, không phải 57 lỗi.
- Bank subclass Company (ontology:515–517) hợp lệ. Specialized involvesCompany/involvesLeader subPropertyOf involves; relatedEvent domain/range Event và subproperties updates/clarifies/supersedes/contradicts kế thừa hợp lý. contradicts đối xứng (:88–91), không mặc định các quan hệ kia đối xứng/transitive.
- Positive fixture với OWL-RL vẫn conform; các indirect controls xác nhận các temporal classes không bị ép thành Candidate do shared relationConfidence. Đây là focused reasoning diagnostic, **không phải OWL DL consistency proof toàn ontology** hoặc gold correctness của inferred edges.
- Functional property là OWL identity semantics, không thay cho SHACL maxCount trong graph closed-world. Current Candidate/Reaction endpoints có SHACL min/maxCount rõ. Domain/range infer type, không phải validation cấm property trên owner khác; M1 minh họa sự khác nhau thực tế khi inference tắt.
- Không có reasoner deployed, named-graph/union-default configuration hay real CQ query files trong gói này để exercise. SPARQL được chạy là SHACL constraints qua pySHACL, không báo “đã chạy toàn CQ/RQ” từ 44 SELECT parse.

## 7. Historical manifest và current canonical không được trộn

`tools/verification_contract_1.0.4.json` là hồ sơ stored run; đã so với live bytes chứ không lấy PASS cũ làm kết quả mới. Raw TTL/SHACL/Draw.io, dictionary, DOCX/PDF và audit/README hiện khớp stored artifact hashes. Hai test scripts raw hash không khớp nhưng hash của **current LF-normalized text** khớp stored hash: khác biệt biểu diễn CRLF/LF, không bằng chứng sửa logic test. Năm Markdown active (schema/scoring/evaluation/annotation/acceptance) khác cả raw và LF-normalized hash: không thể giải thích chỉ bằng line endings, đúng với current V1 modifications.

Không normalize file trên đĩa, không normalize binary DOCX/PDF; artifact JSON lưu raw hashes và chỉ kiểm LF cho text. Hash match schema/diagram không chứng minh nội dung prose tương thích V1. PHASE1_ACCEPTANCE:11, :21–23 đã label historical boundary; vì vậy đây không phải finding “manifest gian dối”, nhưng không được dùng whole-manifest cũ chứng minh current spec acceptance.

Một LF-equivalent text cũng **không** qua raw-byte delivery gate nếu gate đòi đúng checksum. Nếu cần gửi exact current snapshot, tạo manifest current tách riêng sau khi các reviewer hoàn tất; không ghi đè historical acceptance evidence trong lượt read-only này.

## 8. PASS / NOT CHECKED / cần làm ở đâu

| Lớp kiểm tra | Trạng thái | Không được suy rộng |
|---|---|---|
| Live TTL/SHACL syntax, class inventory, supported appendix comparison | PASS | Không ontology equivalence/visual readability |
| Baseline lifecycle/inverse/score and market arithmetic regressions | PASS | Không complete method V1 acceptance |
| OWL-RL positive diagnostic / absence shared multi-domain | PASS có giới hạn | Không factual truth/inference gold/OWL DL proof |
| Untyped Evidence trust-boundary negative | **MEDIUM reproducible gap**, regime none | Không chứng minh production đã tạo node sai |
| Dictionary machine-readable inventory | PASS | Normalizer/identity/role eligibility runtime NOT CHECKED |
| Four-route existence controls và invalid DIRECT/code | PASS focused probe | Temporal selection/owner global gate chưa execute trong package |
| Exact session calendar/day 0/window placement | NOT CHECKED/runtime absent | Không phủ nhận spec daily đã chốt đúng |
| Immutable snapshots/selected Evidence/origin provenance/replay | NOT CHECKED/runtime absent | Không sửa history chỉ vì tổng điểm hợp lý |
| NLP ED/EAE, scoring model/calibration, real market data | NOT CHECKED | Synthetic graphs không là empirical evidence |
| All 9 feedback closure across PDF/diagram/protocol | NOT CHECKED ở trục này | Không dùng audit 337 PASS đóng toàn bộ 9 comments |

**Khuyến nghị trước gửi trong phạm vi này:** giữ evidence mới ngoài gói theo yêu cầu; nêu M1 như đề xuất strengthening nhẹ hoặc contract input-typing phải khóa, giữ các G1–G4 là implementation acceptance gates rõ ràng. Không cần mở rộng ontology. Phân biệt “spec đủ chặt để thầy review trước code” với “máy đã enforce toàn bộ và pipeline đã nghiệm thu”.
