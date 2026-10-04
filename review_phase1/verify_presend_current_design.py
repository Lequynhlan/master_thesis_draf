"""Read-only, synthetic algebra/protocol diagnostic; NOT a pipeline or model benchmark.

Uses live SCORING_SPEC.md V1 policy guards and outputs stdout JSON only.
Submission files are never written. Rankings and gold below are illustrative.
"""
from decimal import Decimal, localcontext
from pathlib import Path
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "chỉnh sửa mới nhất - 01-10"
D = Decimal


def main():
    spec_path = BUNDLE / "SCORING_SPEC.md"
    spec = spec_path.read_text(encoding="utf-8")
    required = [
        "Document version: 1.1.0",
        "S = sourceConfidence = 0.5",
        "T = relationStrength = 1.0 cho mọi eligible route",
        "Event–Company/Event–Leader/Event–Industry support của automatic extractor dùng 0.5",
        "R = relationConfidence = min(mọi required edgeSupportScore trên path)",
        "A = extractionConfidence = selected assignmentScore",
    ]
    for policy in required:
        assert policy in spec, f"Policy changed: {policy}"

    stocks = [f"urn:synthetic:stock:{n:02d}" for n in range(1, 9)]
    relevance = {stock: (2 if i in (2, 6) else 1 if i == 5 else 0)
                 for i, stock in enumerate(stocks)}
    routes = ["DIRECT", "INDIRECT_INDUSTRY", "INDIRECT_SUBSIDIARY", "INDIRECT_LEADERSHIP"]
    records = []
    with localcontext() as ctx:
        ctx.prec = 50
        for event_a in map(D, ["0.2", "0.8", "0.99"]):
            rankings = {}
            scores_by_method = {}
            for method in ["unweighted", "V1", "neutralize_A", "neutralize_L", "neutralize_R"]:
                stock_scores = {}
                path_records = []
                for i, stock in enumerate(stocks):
                    # Every automatic path has an Event-entry support of .5;
                    # downstream provenance can be curated 1 or automatic .5.
                    required_supports = [D("0.5"), D("1") if i % 2 else D("0.5")]
                    path_r = min(required_supports)
                    a = D("1") if method == "neutralize_A" else event_a
                    r = D("1") if method == "neutralize_R" else path_r
                    l = D("1")  # accepted unique typed registry resolution
                    s = D("0.5")
                    t = D("1")
                    score = D("1") if method == "unweighted" else (s + a + l + r) / 4 * t
                    stock_scores[stock] = score
                    path_records.append({"stock": stock, "route": routes[i % len(routes)],
                                         "required_edge_supports": list(map(str, required_supports)),
                                         "original_R": str(path_r), "score": str(score)})
                ranking = sorted(stocks, key=lambda x: (-stock_scores[x], x))
                rankings[method] = ranking
                scores_by_method[method] = {
                    "unique_score_count": len(set(stock_scores.values())),
                    "path_records": path_records,
                    "ndcg_at_5": ndcg(ranking, relevance, 5),
                }
            assert all(x == rankings["unweighted"] for x in rankings.values())
            assert all(x["unique_score_count"] == 1 for x in scores_by_method.values())
            assert len({x["ndcg_at_5"] for x in scores_by_method.values()}) == 1
            records.append({"selected_Event_assignment_A": str(event_a),
                            "all_rankings_identical": True,
                            "rankings": rankings, "methods": scores_by_method})

    outputs = {
        "scope": "synthetic algebraic reproduction of current V1 policies, not empirical WFKG results",
        "spec_path": str(spec_path),
        "spec_sha256": hashlib.sha256(spec_path.read_bytes()).hexdigest(),
        "policy_guards_pass": True,
        "automatic_event_entry_R_min_forces_half": True,
        "assumptions": [
            "The compared methods use the exact same eligible Event-Stock paths.",
            "One selected Evidence assignment A is shared across that Event's paths.",
            "All Event-entry relations are produced by automatic extraction, not ASSISTED/curated fixtures.",
            "Each accepted path has L=1, S=.5 and T=1.",
            "Common Stock URI tie-break; no score threshold (as in V1).",
        ],
        "event_scenarios": records,
        "conclusion": "For these policies, per-Event stock order cannot change with V1 weighting or A/L/R neutralization. This is an algebraic consequence for the stated automatic population, not a measured model result.",
    }
    print(json.dumps(outputs, ensure_ascii=False, indent=2))


def ndcg(ranking, relevance, k):
    def dcg(values):
        return sum((2 ** value - 1) / math.log2(rank + 1)
                   for rank, value in enumerate(values, start=1))
    actual = dcg([relevance[s] for s in ranking[:k]])
    ideal = dcg(sorted(relevance.values(), reverse=True)[:k])
    return actual / ideal if ideal else None


if __name__ == "__main__":
    main()
