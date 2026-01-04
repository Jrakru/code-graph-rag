from __future__ import annotations

import pytest

from codebase_rag.services.confidence_scorer import ConfidenceScorer


class TestConfidenceScorer:
    def test_default_base_score(self) -> None:
        scorer = ConfidenceScorer()
        assert scorer.score("direct_import", 0) == 1.0

    def test_custom_base_score(self) -> None:
        scorer = ConfidenceScorer(base_score=0.9)
        assert scorer.score("direct_import", 0) == 0.9

    def test_base_score_clamped_to_one(self) -> None:
        scorer = ConfidenceScorer(base_score=1.5)
        assert scorer.score("direct_import", 0) == 1.0

    def test_base_score_clamped_to_zero(self) -> None:
        scorer = ConfidenceScorer(base_score=-0.5)
        assert scorer.score("direct_import", 0) == 0.0

    def test_ambiguity_penalty_applied(self) -> None:
        scorer = ConfidenceScorer(base_score=1.0, ambiguity_penalty=0.1)
        assert scorer.score("direct_import", 3) == 0.7

    def test_ambiguity_penalty_does_not_go_negative(self) -> None:
        scorer = ConfidenceScorer(base_score=1.0, ambiguity_penalty=0.5)
        assert scorer.score("direct_import", 10) == 0.0

    def test_fallback_method_reduces_score(self) -> None:
        scorer = ConfidenceScorer()
        assert scorer.score("trie_fallback", 0) == 0.7

    def test_wildcard_method_reduces_score(self) -> None:
        scorer = ConfidenceScorer()
        assert scorer.score("wildcard_import", 0) == 0.7

    def test_direct_method_keeps_base_score(self) -> None:
        scorer = ConfidenceScorer()
        assert scorer.score("direct_import", 0) == 1.0

    def test_same_module_method_keeps_base_score(self) -> None:
        scorer = ConfidenceScorer()
        assert scorer.score("same_module", 0) == 1.0

    def test_unknown_method_uses_default_base(self) -> None:
        scorer = ConfidenceScorer()
        assert scorer.score("type_inference", 0) == 0.85

    def test_empty_method_string(self) -> None:
        scorer = ConfidenceScorer()
        assert scorer.score("", 0) == 1.0

    def test_method_case_insensitive(self) -> None:
        scorer = ConfidenceScorer()
        assert scorer.score("DIRECT_IMPORT", 0) == scorer.score("direct_import", 0)

    def test_method_whitespace_trimmed(self) -> None:
        scorer = ConfidenceScorer()
        assert scorer.score("  direct_import  ", 0) == scorer.score("direct_import", 0)

    def test_combined_fallback_and_ambiguity(self) -> None:
        scorer = ConfidenceScorer(ambiguity_penalty=0.1)
        assert abs(scorer.score("trie_fallback", 2) - 0.5) < 1e-9
