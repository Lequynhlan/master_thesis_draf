# Review bộ Markdown trước khi gửi thầy: ngôn ngữ và tính nhất quán

## Phạm vi và kết luận

Nguồn yêu cầu: `ban_thay_gop_y/gop_y_phase1_truoc_code_phase2.txt`; bộ hiện hành `chỉnh sửa mới nhất - 01-10/` gồm EVENT_SCHEMA.md, SCORING_SPEC.md, EVALUATION_PROTOCOL.md, ANNOTATION_GUIDELINE.md, PHASE1_ACCEPTANCE.md. Review này không tự chuyển ngôn ngữ hay thay numerical baseline, không xác nhận toàn bộ report/diagram/runtime readiness.

Khuyến nghị dùng **tiếng Anh thống nhất cho bộ đặc tả kỹ thuật**. EVENT_SCHEMA, EVALUATION_PROTOCOL và ANNOTATION_GUIDELINE đã dùng tiếng Anh; SCORING_SPEC và PHASE1_ACCEPTANCE là hai điểm lệch. Thư gửi thầy hoặc tóm tắt tiến độ có thể dùng tiếng Việt, là tài liệu riêng, không pha vào normative technical prose. Góp ý thầy không bắt buộc ngôn ngữ: đây là đề xuất biên tập, không phải requirement của thầy.

Bản Việt hóa SCORING_SPEC do assistant tự suy diễn đã được hoàn tác bằng exact-byte pre-translation backup; SHA256 khôi phục `fcd60f30d3ce86b2764a896e3f1200046477d61ea31d83198bc34946729f85a3`. Không coi translation tự ý là phương án đã được duyệt.

## Findings cụ thể

| Mức | Nguồn | Phát hiện | Đề xuất nhỏ nhất |
| --- | --- | --- | --- |
| Vừa | SCORING_SPEC.md:3–6,12,16–27,67–111,208–244 | Metadata tiếng Anh, tiêu đề/văn xuôi tiếng Việt pha thuật ngữ và nguyên đoạn Anh; mục Numeric contract nguyên đoạn tiếng Anh. | Dùng English technical prose toàn file; giữ identifiers/codes/formulas/namespace/paths; thuật ngữ được định nghĩa một lần. |
| Vừa | PHASE1_ACCEPTANCE.md:1–23,25–95 | Title và phần lớn hồ sơ bằng tiếng Việt, header/table xen tiếng Anh; một file chứa active V1 boundary và historical 1.0.4 acceptance evidence. | Active crosswalk viết English; chuyển lịch sử sang appendix/file historical có nhãn và snapshot rõ. Nếu giữ Vietnamese history, đặt ngoài bộ normative English và ghi tính chất supporting archive. |
| Cao về bàn giao, chưa phải lỗi số V1 | PHASE1_ACCEPTANCE.md:11,21–25,37–38,87–91 | Đã có warning legacy, nhưng acceptance conclusions/hằng số cũ vẫn gần active policy, dễ bị đọc lướt thành đồng bộ toàn bộ gói. | Tách Current specification readiness khỏi Historical execution evidence; không dùng câu 'ready' lịch sử làm kết luận V1. |
| Vừa | SCORING_SPEC.md:57,116–121,211–215 so với EVENT_SCHEMA.md:52 và ANNOTATION_GUIDELINE.md:46 | Evidence 'passed gates' bao gồm required linking nhưng execution order còn để resolve required links sau selection. Các file khác đã phân biệt assignment-required trước selection và optional route links sau selection. | Khóa lại thứ tự trong SCORING_SPEC: required role/identity/entity linking per assignment → chọn complete eligible Evidence một lần → optional/propagated route links/facts; không đổi S/A/L/R/T. |
| Vừa về khả năng đọc | ANNOTATION_GUIDELINE.md:46–47,56; EVENT_SCHEMA.md:140; EVALUATION_PROTOCOL.md:95–103 | Đoạn normative dài gồm nhiều quyết định, cần đọc lại nhiều lần mới thấy producer/selection/matching và ngoại lệ. | Tách bullet/numbered steps; mỗi rule nêu input, decision, failure/output; không thêm rubric hay semantic engine. |
| Vừa về gói gửi thầy | Góp ý thầy:160–169; PHASE1_ACCEPTANCE.md:11 | Thầy yêu cầu tối thiểu TTL/SHACL/schema/scoring/evaluation/Draw.io. Markdown sửa xong không đồng nghĩa Draw.io/PDF đã đồng bộ V1. | Ghi delivery manifest và trạng thái từng artifact; kiểm active numerical labels của Draw.io trước khi gọi cả gói ready-to-send. |

## Quy ước biên tập đề xuất

1. Giữ filenames và code identifiers: Event, Evidence, EventStockCandidate, EventStockReaction, sourceConfidence, extractionConfidence, linkingConfidence, relationConfidence, relationStrength, WFKG-SCORE-V1, route/reason/status codes.
2. Dùng thuật ngữ nhất quán: eligibility gate; complete assignment; selected Evidence; required-role decision; edge support origin; immutable cutoff snapshot; model checkpoint; task-trained extractor; deterministic replay.
3. Phân biệt document version 1.1.0, scoring method WFKG-SCORE-V1, structural ontology/shape version và historical package 1.0.4. Không nâng version header thành bằng chứng conformance.
4. Tiêu đề mô tả nội dung thay vì filename-only khi cần reader-facing title; metadata dùng cùng nhãn Document version / Active scoring method / Status / Authority. ANNOTATION có thể ghi scoring method chỉ áp dụng prediction audit.
5. Normative rules dùng must/must not; optional extension dùng may; proposal và future experiment ghi rõ chưa thực hiện. Có glossary ngắn hoặc bảng terms authoritative, tránh mỗi file tự định nghĩa biến thể khác.
6. Giữ nguyên các công thức và baseline: confidenceScore=(S+A+L+R)/4; candidateScore=confidenceScore*T; S=.5, accepted L=1, T=1 cả bốn routes; A trained required-decision min; R edge-origin min .5/1.
7. Source truth được phân miền: TTL/SHACL cho cấu trúc; SCORING_SPEC cho numerical producers/aggregation; EVENT_SCHEMA cho producer/temporal/lifecycle; evaluation/annotation cho gold và metrics. Không viết TTL là nguồn duy nhất của model score policies.
8. Tách specification, historical verification, current executed diagnostics và future runtime acceptance. Synthetic structural tests không chứng minh NLP quality hoặc complete calendar-aware real-data pipeline.

## Trạng thái

Đã review và đề xuất phương án English. Chưa tự dịch toàn bộ bộ submission sau user correction. Cần duyệt phương án biên tập trước khi chuyển SCORING_SPEC và active PHASE1_ACCEPTANCE sang English. Pipeline/model training/full graphical/report sync chưa được chạy trong review này.
