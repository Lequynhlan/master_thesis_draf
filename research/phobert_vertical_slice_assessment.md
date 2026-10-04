# Đánh giá PhoBERT cho vertical slice WFKG 1.0.4

## Verdict

PhoBERT hợp lý như backbone tiếng Việt cho extractor được fine-tune; không phải checkpoint event extraction có sẵn. Pipeline fallback hiện hành phù hợp smoke/debug, không đủ chứng minh confidence có chất lượng thống kê hay RQ3 weighting hiệu quả. Chưa chạy inference/training PhoBERT trên corpus WFKG trong assessment này.

## Primary evidence

1. Nguyen & Nguyen (2020), PhoBERT: Pre-trained language models for Vietnamese: https://aclanthology.org/2020.findings-emnlp.92/ ; PDF https://aclanthology.org/2020.findings-emnlp.92.pdf . Đã đọc abstract và fine-tuning section. Bài đánh giá POS, dependency parsing, NER và NLI, không phải event detection/EAE tài chính WFKG. Bài thêm prediction heads và fine-tune theo task, không dùng pretrained model như zero-shot extractor.
2. Official README đã đọc: https://github.com/VinAIResearch/PhoBERT ; raw https://raw.githubusercontent.com/VinAIResearch/PhoBERT/master/README.md . PhoBERT-base 135M, max length 256; input phải word-segmented, tác giả khuyến nghị RDRSegmenter/VnCoreNLP. Đây là giới hạn thiết kế window, không phải runtime benchmark của máy này.
3. Official base config đã fetch: https://huggingface.co/vinai/phobert-base/resolve/main/config.json . Architecture RobertaForMaskedLM, không phải event-specific classifier/argument extractor. Instantiate task head không có checkpoint trained tương ứng không tạo predictor đã học event labels.
4. Current SCORING_SPEC.md:24–38,54–75 và EVALUATION_PROTOCOL.md:7–12,39–59 là source of truth cho fallback, evidence selection và đánh giá. Đã đọc trực tiếp.

## Điều kiện để triển khai có ý nghĩa

- Chốt input/output unit: Evidence anchor, trigger/eventType và arguments cho từng Event mention. Sentence-level single-label detection chỉ thích hợp subset kiểm soát có tối đa một Event/câu; không coi đây là full solution nhiều Events.
- Dùng PhoBERT encoder + supervised event detection head và event-conditioned argument head. Schema này là đề xuất thiết kế, không có sẵn trong pretrained PhoBERT. Hai Events trong cùng câu cần assignment theo từng Event; NER không tự gán buyer/target.
- Có nhãn development về eventType, Evidence anchors, roles, negatives/confusables. Không có gold/checkpoint task-trained thì chưa thể kết luận suitability runtime; không dùng random task head scores như extraction quality.
- 100–300 articles là smoke/debug slice theo protocol, không đảm bảo đủ train/evaluate 14 types. Báo support thực tế, chọn trọng tâm development và giữ misses/unsupported types minh bạch; không bí mật đổi dictionary. Held-out debug results vẫn exploratory; chronological final test sealed.
- PhoBERT không tự giải quyết canonical business-occurrence identity, dates/literal normalization, document references, Company/Stock distinctions hay registry resolution. Kết hợp deterministic normalization và curated registry phù hợp contract; manual prediction edits là assisted run riêng, không end-to-end automatic.
- Bảo toàn original text/hash và Unicode codepoint half-open offsets. Word segmentation/BPE/normalization cần alignment ngược về original text. Không lưu offsets trên text đã thay dấu gạch dưới rồi chấm exact spans trên original.
- Không silently truncate article. Window/cross-sentence context và full Evidence support phải được predeclare; không ghép incomplete Evidence để cứu required roles trong baseline.

## Raw scores cần lưu gì?

Lưu logits hoặc probability distribution của trained task heads, predicted eventType/trigger/roles, span IDs, window boundaries, decoder/threshold, checkpoint/model/tokenizer/segmenter versions, original text/hash/offsets, role normalization trace và fallback flags. Hidden embeddings, masked-LM likelihood hay LLM tự nêu confidence không phải confidence cho event assignment. Per-token softmax không tự là joint correctness probability của complete Event assignment.

## Contract fallback: correct but limited

- Present evidenced complete assignment chưa calibrated: extractionConfidence=0.5.
- Missing/unresolved/mismatched required roles: không Candidate; không bù bằng 0.5.
- Curated typed registry identity mapping: 1.0 là convention, không empirical probability. Tự động chọn sai curated entry không thừa hưởng 1.0 chỉ vì registry tốt.
- Automatic evidenced decision chưa calibrated: 0.5; missing/unresolved required link suppress path.
- relationConfidence vẫn theo minimum path-support table. DIRECT dùng A và Company–Stock M; A=.5 thì relationConfidence<=.5, kể cả mapping identity curated.
- Raw scores lưu audit nhưng không dùng lén thay extraction fallback hoặc chọn Evidence khác: baseline selects max assignment score A, ties bằng Evidence URI. Khi mọi A=.5, selection không ưu tiên raw neural score; thay selection cần method contract/version riêng được duyệt.

## Hypothetical calculation, không phải model result

Đã dùng Python để tính:
- Source=.5, extraction=.5, linking=1, relation=.5 => confidence=.625; DIRECT=.625, indirect strength=.5 => .3125.
- Source=.5, extraction=.5, linking=.5, relation=.5 => confidence=.5; DIRECT=.5, indirect=.25.

Vì vậy số .625 không nghĩa Candidate đúng 62.5%. Khi components cùng nhau trong một nhóm, điểm chỉ phân biệt relationStrength hoặc tie-break. Uniform fallback không kiểm tra khả năng model uncertainty xếp mẫu đúng lên trên mẫu sai. Ablation trên component hằng có thể không thay within-route rankings; nếu khác strengths/components giữa routes thì không khẳng định mọi overall ranking bất biến.

## Đánh giá nên báo riêng

1. Execution: trained checkpoint load/inference thành công, output artifacts và reproducibility. Chưa có evidence runtime trong note này.
2. Extraction quality: Evidence exact-span P/R/F1; typed Event P/R/F1; required-role P/R/F1, exact required-role-set accuracy; canonical coverage/missing reasons. Completeness gate không chứng minh đúng roles.
3. Linking: exact typed URI và unresolved/abstention theo protocol. Oracle-mention diagnostics tách end-to-end.
4. Scores: histogram/unique values/fallback fraction; raw score correctness separation/risk–coverage là diagnostic exploratory. Calibration phải dùng target và hold-out development phù hợp; ECE/reliability/NLL chỉ claim khi thật sự đo trên labels độc lập.
5. Downstream: common Event–Stock universe, cutoff eligible facts, complete assignment selection, frozen Candidate then reaction AR/CAR. RQ2/RQ3 final conclusion không lấy từ vertical slice hay CAR-based tuning của extractor.

## Recommendation

Giữ baseline .5 và formula 1.0.4 cho smoke/debug; ưu tiên train/fine-tune extractor với nhãn task đúng và artifact provenance. Nếu chưa có nhãn, bước đầu là annotation và chọn task architecture/checkpoint, không hứa chỉ load PhoBERT là chạy được EAE. Đánh giá extraction correctness dù confidence dùng fallback; sau đó mới fit calibrator hoặc duyệt heuristic/raw-score variant riêng. Không cần train model from scratch hay triển khai probabilistic rule engine để đạt mục tiêu vertical slice.
