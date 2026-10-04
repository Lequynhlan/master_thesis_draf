# Review SCORING_SPEC 1.0.4 khi extractor chuyển sang PhoBERT

Status: REVIEW + OPTIONS, chưa duyệt numerical design, chưa sửa nguồn chuẩn, chưa chạy model.

## Nguồn

- ban_thay_gop_y/gop_y_phase1_truoc_code_phase2.txt: toàn bộ; yêu cầu confidence components/provenance/freeze tại L38–56, Candidate vs Reaction tại L58–74, market provenance L76–90.
- chỉnh sửa mới nhất - 01-10/SCORING_SPEC.md: toàn bộ L1–124.
- ANNOTATION_GUIDELINE.md, EVALUATION_PROTOCOL.md: toàn bộ.
- EVENT_DICTIONARY.yaml: đối chiếu EARNINGS required roles.
- shapes_v1.0.ttl: chỉ các đoạn Candidate components, arithmetic/source control và temporal relation confidence; không audit toàn bộ ontology/shapes trong lượt này.
- .hermes/plans/2026-10-04_145327-phase2-scoring-rubric-draft.md và research/confidence_extraction_linking_calibration.md để nhận diện proposal cũ, không thay nguồn chuẩn.

Không thấy file riêng score.md qua kiểm kê tên file .md trong workspace; file hiện hành được hiểu là SCORING_SPEC.md. search_files trả rỗng đã kiểm tra lại bằng pathlib; không suy rỗng tool là không có source.

## Kết luận

Đã có aggregate formulas, fallback/conventions, Evidence selection, routes, anti-leakage và Reaction provenance. Không đúng nếu nói scoring hoàn toàn chưa đặc tả. Nhưng chưa có scoring adapter contract cho PhoBERT hoặc audit schema để hai implementation lấy logits/type/role/span scores giống nhau. Không dùng completeness/SHACL pass thay semantic correctness. Không coi pretrained PhoBERT tự kiểm rubric checklist.

## Map yêu cầu -> tình trạng

1. Components và frozen cutoff: SCORING_SPEC L25–38,L54–77 đáp ứng ở mức thiết kế. Numeric inputs có fallback nguồn gốc rõ.
2. Evidence selection và roles/linking cùng assignment: L54–69 đã có; giữ nguyên.
3. DIRECT relationConfidence=min(original assignment A,terminal M): L64,L75 đã có; không invent relation classifier hoặc tự cho1 khi route pass.
4. Market reaction tách ranking: L79–106 đã có; không sửa vì đổi extractor.
5. PhoBERT type score producer: chưa có event-instance/trigger pooling/logit-to-score definition.
6. Per-role score producer: L54 min per-role nhưng chưa định nghĩa span score từ BIO token probabilities, subword pooling, spans/window merging và required roles không phải neural output.
7. Occurrence identity: dictionary EARNINGS có occurrence_id required; đây không tự là neural span score. Cần identity evidence/gate và producer policy riêng; không dùng Company softmax cho ID, hoặc nhét .5 vào min mà không đánh giá score collapse.
8. Calibration vs raw score: L36,L54,L73–75 bắt uncalibrated evidenced assignment dùng .5. Dùng raw softmax/checklist heuristic vào Candidate là method mới phải duyệt/spec rõ, không chỉ đổi checkpoint.
9. Audit schema: spec đòi freeze nhưng chưa full field-level record with score origin, model/tokenizer/segmentation/decoder, logits/score vectors or sufficient replay inputs, role/identity/link provenance và exclusion ledger.
10. Semantic checklist producer: quote/offset/normalization/cutoff có thể machine-check; đúng actor/assertion/modality/period attachment không được PASS tự động chỉ do cùng câu hoặc value nằm trong text. Gold review offline khác runtime checker.

## Tách ba tầng

- Eligibility gates: unsupported/invalid offsets, missing roles/identity, unresolved type/URI/facts, future input -> HOLD/no relevant path. Không gán .5 để cứu thiếu.
- Score production: fallback convention, model-based heuristic, calibrated decision, hoặc explicitly implemented rubric evaluator. Producer khác nhau cần source_type/version, không tự đổi lẫn nhau.
- Independent evaluation: gold correctness/score bands/errors trên development/heldout; không nhập gold vào runtime hoặc dùng CAR fit extraction.

## Checklist mục tiêu, không mặc định là runtime verifier

Event type: dictionary valid; assertion state đúng (rumor/negation/completion); instance boundary; confusable cases.
Company/participant: span thật; đúng actor/object role; đúng event instance; typed URI giải riêng ở linking.
Period: year và period evidenced; normalize grammar; qualifiers conserved; attachment đúng company/metric.
Metric: phrase evidenced; exact metric vocabulary; instance/company attachment; không tráo revenue/profit.
Occurrence: original assertion/document or evidenced registry identity; same business occurrence vs new assertion; support cutoff; no article URL/date fabrication.

Mỗi criterion cần ID, explicit condition, input/producer, PASS/FAIL/UNKNOWN, evidence reference và fixture/test. Semantic criteria không implement được phải ghi NOT_AUTOMATICALLY_CHECKED, không cố làm semantic rule engine bao phủ14 types chỉ để chấm checklist.

## Các lựa chọn cần duyệt

A. Giữ fallback-only 1.0.4 + raw PhoBERT scores trong audit: nhỏ nhất và reproducible, nhưng .5 không phân hóa chất lượng extraction; không claim đã đáp ứng mục tiêu confidence ranking có variation.
B. PhoBERT task scores thành model-based heuristic variant, gates + checklist để annotation/evaluation/audit: đề xuất phù hợp với hướng không thêm evaluator/model/rule engine. Phải khóa score adapter sau khi ED/EAE output format chốt; không gọi raw scores calibrated P(correct). Type contribution, span aggregation và occurrence policy chưa duyệt. Giữ baseline comparator không ghi đè.
C. Numeric checklist rubric: chỉ khả thi nếu rõ ai đánh PASS/FAIL/UNKNOWN. Human -> assisted; semantic rules -> cost/coverage hạn chế; model judge -> additional evaluator không tự có từ PhoBERT. Rule categories/direct-context scores không có cơ sở mặc định1/.8. Nếu chọn cần design riêng và đánh giá.

Proposal cũ 145327 có LLM extractor + deterministic semantic binding rubric; extractor đã bị user steering thay bằng PhoBERT. Không giữ ngầm proposal LLM hoặc áp mechanical checklist lên PhoBERT. Rubric numeric từng tiêu chí chưa được coi đã duyệt; report này không sửa proposal cũ.

## Ví dụ arithmetic synthetic kiểm bằng Decimal

Inputs assumed evidenced/eligible, selected A=.5 uncalibrated, S=.5, all required entity decisions và terminal M là verified curated mapping1. DIRECT R=min(A,M)=.5 -> C=.625 -> DIRECT candidateScore=.625.
Nếu indirect facts/endpoints đủ và node confidence=.5, R=.5, strength=.5 -> candidateScore=.3125.
Đây là số minh họa, không model output hoặc Candidate thật. Raw PhoBERT score không tự đổi A trong method1.0.4. Không ép example ra .35.

## Cấu trúc nên bổ sung sau duyệt

SCORING_SPEC: score semantics/origin; gates separate; PhoBERT scoring adapter; each component lookup/input list; Evidence decision ledger; fallback/calibration/method policy; exact audit schema; numeric worked case and negative tests; freeze/rounding/replay; score diagnostic evaluation.

Audit ngoài RDF giữ source schema gọn; không cần thêm class. Nếu approved variant, rà soát đồng bộ schema/annotation/evaluation và shape compatibility trước tuyên bố hợp lệ. SHACL arithmetic pass không xác nhận raw model score origin hoặc semantic correctness.

Frontier hiện tại: chọn producer cho numeric extraction score khi dùng PhoBERT. Khuyến nghị B cùng A comparator; chưa quyết định formula type/span/identity hoặc sửa contract trước câu trả lời người dùng.
