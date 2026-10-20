"""Candidate confidence and inference-time score calculations."""


def confidence_score(
    source_confidence: float,
    extraction_confidence: float,
    linking_confidence: float,
    relation_confidence: float,
) -> float:
    """Return the mean of the four frozen confidence components (Phase 1 SHACL rule)."""
    components = (source_confidence, extraction_confidence, linking_confidence, relation_confidence)
    if any(not 0.0 <= value <= 1.0 for value in components):
        raise ValueError("Confidence components must be between 0 and 1.")
    return sum(components) / len(components)


def candidate_score(confidence: float, relation_strength: float) -> float:
    """Compute the inference-time candidate score, excluding market reaction data."""
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("Confidence must be between 0 and 1.")
    if not 0.0 <= relation_strength <= 1.0:
        raise ValueError("Relation strength must be between 0 and 1.")
    return confidence * relation_strength
