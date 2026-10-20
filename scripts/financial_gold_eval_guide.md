# Annotation guide — Financial-domain gold evaluation v1

## Purpose and limits

Review this purposive, stratified sample of 20 saved articles. The sheets contain model proposals for navigation, not gold labels. Check the source and annotate missed Events and Entities as well. All decision fields are blank initially. Never treat a blank or model prediction as a confirmed label.

The only decision values are `CORRECT`, `INCORRECT`, `UNCERTAIN`, and `NOT_IN_MAIN_ARTICLE`.

## Review units and offsets

- Review each row in `sentence_annotation_template.csv`. `originalText` is immutable saved source text. `sentenceStart` and `sentenceEnd` are zero-based, half-open character offsets within the given `sourceField`.
- Candidate trigger, evidence, and entity offsets are mapped to the same saved source fields. Check `sourceBodySha256` and `preparedTextSha256` before annotating; do not silently replace text with a newer webpage version.
- Record evidence as the shortest source span that supports the Event or its participant relation. Duplicate an add-slot row when a sentence contains more than one missed item.

## Decisions

- `CORRECT`: this candidate value is supported and correct for the column being reviewed.
- `INCORRECT`: the candidate value is wrong for that column.
- `UNCERTAIN`: evidence is insufficient to decide; it is excluded from gold scoring.
- `NOT_IN_MAIN_ARTICLE`: sidebar, related news, ad, navigation, footer, or other material outside the story. Keep the prediction; it can count as a false positive, but never as gold.

`sourceContextDecision` is only about source inclusion: `CORRECT` means the sentence belongs to the main article; `INCORRECT` means saved text is corrupted or mismapped; `NOT_IN_MAIN_ARTICLE` means the text is outside the article; `UNCERTAIN` means the boundary cannot be established. Judge trigger, type, argument role, and URI in their own decision columns.

## Workflow

1. Review the source sentence in context. Mark `sentenceReviewStatus=REVIEWED` only after checking the full sentence for missed Events and Entities; set its source decision separately.
2. ED: judge trigger and Event type separately. Leave prediction fields unchanged. Add/duplicate a `REVIEW_ADDED_SLOT` row and fill gold trigger/type/evidence when an Event is missed or needs a corrected span/type.
3. EMD: judge span and type separately. A correct span does not imply a correct type. Add a reviewer slot for missed Entities. Preserve exact source spelling and boundary.
4. EAE: judge whether this Entity participates in this specific Event (`argumentDecision`), then judge its role (`roleDecision`). `NONE` is a negative pair. Do not attach all same-sentence Entities to each Event. Add a row for a missed participant/role.
5. Entity linking: review `uriDecision` for every EMD proposal, including rows whose predicted URI is blank. URI correctness is independent of mention detection and Event participation. Fill `goldEntityURI` with the verified URI whenever the mention maps to the KG, even if the predicted URI is missing or wrong; leave it blank and explain when no KG URI applies or identity is unresolved. This lets the evaluator count both wrong URI assignments and missed links.
6. Enter reviewer ID/date. Never delete proposals; retain uncertain and non-main-article decisions.

## Concrete cases

### ACB: related-news contamination (do not pre-label)

Article: https://vietstock.vn/2026/10/tu-gan-200-ho-so-du-giai-acb-chinh-phuc-hang-muc-kep-tai-thuong-hieu-vang-tphcm-2026-757-1502321.htm

The story concerns ACB receiving awards. Two saved proposals predict `Transfer-money`, trigger `trả`, and assign ACB role `Giver`. The evidence begins near saved `bodyText` offset 7779, after an ACB customer-service call to action, and includes related-ticker/news headings and CSV/ECO headlines. The trigger appears in those unrelated headlines. The two ACB paths remain `BLOCKED_PENDING_SOURCE_CONTEXT_REVIEW`. If review verifies the text is outside the story, mark `NOT_IN_MAIN_ARTICLE`; if the saved structure cannot establish this, mark `UNCERTAIN`. Do not promote either path from model output or co-occurrence.

### Boundary and type examples

- CTS: v1 proposes `Công ty Cổ phần Chứng khoán VietinBank`; v2 overlaps only `Chứng khoán`. Check the complete organization span in source. Do not use v1's URI to excuse a v2 boundary error.
- BID: v1 proposes `Ngân hàng Thương mại Cổ phần Đầu tư và Phát triển Việt Nam`; v2 begins at `Thương mại Cổ phần Đầu tư và Phát triển Việt Nam`. Annotate the exact source boundary, then judge type separately.
- If an organization boundary is right but type is wrong, use `spanDecision=CORRECT` and `typeDecision=INCORRECT`; create a reviewer-added row containing the corrected gold type. Do not infer entity type from a ticker-like string or KG path.

## Evaluator

After review, run `python scripts/evaluate_financial_gold.py --input-dir <reviewed-copy>`. It refuses to emit metrics unless all 20 articles' sentence rows and model proposals have explicit review. It uses human-confirmed labels only; blank rows are never gold. `UNCERTAIN` is excluded. Rows marked source-context `INCORRECT` are excluded because their offsets/text are invalid. `NOT_IN_MAIN_ARTICLE` proposals remain predictions and can count as false positives, but never enter gold. EAE role micro PRF excludes `NONE`. Metrics are diagnostic for this purposive sample, not estimates for all 100 articles.
