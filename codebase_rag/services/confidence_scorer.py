from __future__ import annotations

from ..protocols import ConfidenceScorerProtocol


class ConfidenceScorer(ConfidenceScorerProtocol):
    def __init__(self, base_score: float = 1.0, ambiguity_penalty: float = 0.1):
        self._base_score = max(0.0, min(1.0, base_score))
        self._ambiguity_penalty = max(0.0, ambiguity_penalty)

    def score(self, method: str, ambiguity_count: int) -> float:
        normalized = method.strip().lower()
        base = self._base_score

        if normalized:
            if any(token in normalized for token in ("fallback", "wildcard", "trie")):
                base = min(base, 0.7)
            elif any(token in normalized for token in ("direct", "exact", "same")):
                base = min(base, 1.0)
            else:
                base = min(base, 0.85)

        penalty = max(0.0, ambiguity_count * self._ambiguity_penalty)
        return max(0.0, min(1.0, base - penalty))
