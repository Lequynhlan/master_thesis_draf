"""Generate event-stock candidates from explicitly supported relation paths."""

from __future__ import annotations

from copy import deepcopy

from .scoring import candidate_score

BASELINE_IMPACT_TYPES = ("DIRECT", "INDIRECT_INDUSTRY", "INDIRECT_SUBSIDIARY", "INDIRECT_LEADERSHIP")


def generate_candidates(
    events: list[dict[str, object]], stock_symbols: tuple[str, ...]
) -> list[dict[str, object]]:
    """Generate only candidates whose event record contains an evidenced path.

    Supported path rows are supplied in ``relationPaths`` with impactType,
    ticker, relationStrength, and evidence. The stock universe is a hard filter.
    """
    allowed = {symbol.upper() for symbol in stock_symbols}
    candidates = []
    for event in events:
        event_id = event.get("eventId")
        paths = event.get("relationPaths")
        if not isinstance(paths, list):
            continue
        for path in paths:
            if not isinstance(path, dict):
                continue
            impact = str(path.get("impactType", ""))
            ticker = str(path.get("ticker", "")).upper()
            if impact not in BASELINE_IMPACT_TYPES or ticker not in allowed:
                continue
            if not path.get("evidence"):
                continue
            try:
                confidence = float(path.get("confidenceScore", event.get("confidenceScore", 0)))
                strength = float(path["relationStrength"])
                score = candidate_score(confidence, strength)
            except (KeyError, TypeError, ValueError):
                continue
            candidates.append({
                "eventId": event_id,
                "candidateId": path.get("candidateId") or f"CANDIDATE:{event_id}:{ticker}:{impact}",
                "ticker": ticker,
                "impactType": impact,
                "confidenceScore": confidence,
                "relationStrength": strength,
                "candidateScore": score,
                "evidence": deepcopy(path["evidence"]),
                "status": "CANDIDATE_REVIEW_REQUIRED",
                "scoreUsesReaction": False,
            })
    return candidates
