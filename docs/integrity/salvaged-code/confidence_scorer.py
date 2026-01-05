"""Confidence scoring for call resolutions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ResolutionMethod(StrEnum):
    """Method used to resolve a call."""

    DIRECT_IMPORT = "direct_import"
    TYPE_INFERENCE = "type_inference"
    SAME_MODULE = "same_module"
    INHERITED_METHOD = "inherited_method"
    IIFE = "iife"
    WILDCARD_IMPORT = "wildcard_import"
    TRIE_FALLBACK = "trie_fallback"
    UNRESOLVED = "unresolved"


@dataclass
class ConfidenceConfig:
    """Configuration for confidence scoring weights."""

    direct_import_base: float = 1.0
    same_module_base: float = 0.95
    type_inference_base: float = 0.9
    inherited_method_base: float = 0.85
    iife_base: float = 0.8
    wildcard_import_base: float = 0.7
    trie_fallback_base: float = 0.5

    # Penalties
    ambiguity_penalty_per_match: float = 0.05
    max_ambiguity_penalty: float = 0.3


class ConfidenceScorer:
    """Scores confidence of call resolutions."""

    def __init__(self, config: ConfidenceConfig | None = None) -> None:
        self.config = config or ConfidenceConfig()

    def score(
        self,
        method: ResolutionMethod,
        ambiguity_count: int = 1,
        **context: Any,
    ) -> float:
        """Calculate confidence score for a resolution.

        Args:
            method: Resolution method used
            ambiguity_count: Number of possible matches (for trie fallback)
            **context: Additional context (reserved for future use)

        Returns:
            Confidence score between 0.0 and 1.0
        """
        base_scores = {
            ResolutionMethod.DIRECT_IMPORT: self.config.direct_import_base,
            ResolutionMethod.SAME_MODULE: self.config.same_module_base,
            ResolutionMethod.TYPE_INFERENCE: self.config.type_inference_base,
            ResolutionMethod.INHERITED_METHOD: self.config.inherited_method_base,
            ResolutionMethod.IIFE: self.config.iife_base,
            ResolutionMethod.WILDCARD_IMPORT: self.config.wildcard_import_base,
            ResolutionMethod.TRIE_FALLBACK: self.config.trie_fallback_base,
            ResolutionMethod.UNRESOLVED: 0.0,
        }

        base = base_scores.get(method, 0.5)

        # Apply ambiguity penalty for trie fallback
        if method == ResolutionMethod.TRIE_FALLBACK and ambiguity_count > 1:
            penalty = min(
                (ambiguity_count - 1) * self.config.ambiguity_penalty_per_match,
                self.config.max_ambiguity_penalty,
            )
            base -= penalty

        return max(0.0, min(1.0, base))
