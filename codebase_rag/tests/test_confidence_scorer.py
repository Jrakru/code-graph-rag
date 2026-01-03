"""Tests for confidence scoring of call resolutions."""

import pytest

from codebase_rag.services.confidence_scorer import (
    ConfidenceConfig,
    ConfidenceScorer,
    ResolutionMethod,
)


@pytest.fixture
def scorer() -> ConfidenceScorer:
    """Create a ConfidenceScorer with default config."""
    return ConfidenceScorer()


@pytest.fixture
def custom_scorer() -> ConfidenceScorer:
    """Create a ConfidenceScorer with custom config."""
    config = ConfidenceConfig(
        direct_import_base=0.99,
        trie_fallback_base=0.4,
        ambiguity_penalty_per_match=0.1,
    )
    return ConfidenceScorer(config)


class TestResolutionMethodEnum:
    """Test ResolutionMethod enum values."""

    def test_all_methods_exist(self) -> None:
        """All expected resolution methods should be defined."""
        assert ResolutionMethod.DIRECT_IMPORT == "direct_import"
        assert ResolutionMethod.TYPE_INFERENCE == "type_inference"
        assert ResolutionMethod.SAME_MODULE == "same_module"
        assert ResolutionMethod.INHERITED_METHOD == "inherited_method"
        assert ResolutionMethod.IIFE == "iife"
        assert ResolutionMethod.WILDCARD_IMPORT == "wildcard_import"
        assert ResolutionMethod.TRIE_FALLBACK == "trie_fallback"
        assert ResolutionMethod.UNRESOLVED == "unresolved"


class TestConfidenceConfig:
    """Test ConfidenceConfig defaults."""

    def test_default_config_values(self) -> None:
        """Default config should have expected values."""
        config = ConfidenceConfig()
        assert config.direct_import_base == 1.0
        assert config.same_module_base == 0.95
        assert config.type_inference_base == 0.9
        assert config.inherited_method_base == 0.85
        assert config.iife_base == 0.8
        assert config.wildcard_import_base == 0.7
        assert config.trie_fallback_base == 0.5
        assert config.ambiguity_penalty_per_match == 0.05
        assert config.max_ambiguity_penalty == 0.3


class TestConfidenceScorerBasicScoring:
    """Test basic confidence scoring."""

    @pytest.mark.parametrize(
        ("method", "expected_score"),
        [
            (ResolutionMethod.DIRECT_IMPORT, 1.0),
            (ResolutionMethod.SAME_MODULE, 0.95),
            (ResolutionMethod.TYPE_INFERENCE, 0.9),
            (ResolutionMethod.INHERITED_METHOD, 0.85),
            (ResolutionMethod.IIFE, 0.8),
            (ResolutionMethod.WILDCARD_IMPORT, 0.7),
            (ResolutionMethod.TRIE_FALLBACK, 0.5),
            (ResolutionMethod.UNRESOLVED, 0.0),
        ],
    )
    def test_base_scores_for_methods(
        self, scorer: ConfidenceScorer, method: ResolutionMethod, expected_score: float
    ) -> None:
        """Each method should return its configured base score."""
        assert scorer.score(method) == expected_score

    def test_score_always_between_0_and_1(self, scorer: ConfidenceScorer) -> None:
        """Score should always be clamped between 0.0 and 1.0."""
        for method in ResolutionMethod:
            score = scorer.score(method, ambiguity_count=100)
            assert 0.0 <= score <= 1.0


class TestConfidenceScorerAmbiguityPenalty:
    """Test ambiguity penalty for trie fallback."""

    def test_no_penalty_for_single_match(self, scorer: ConfidenceScorer) -> None:
        """No penalty when there's only one match."""
        score = scorer.score(ResolutionMethod.TRIE_FALLBACK, ambiguity_count=1)
        assert score == 0.5

    def test_penalty_applied_for_multiple_matches(
        self, scorer: ConfidenceScorer
    ) -> None:
        """Penalty should reduce score for multiple matches."""
        score_1 = scorer.score(ResolutionMethod.TRIE_FALLBACK, ambiguity_count=1)
        score_2 = scorer.score(ResolutionMethod.TRIE_FALLBACK, ambiguity_count=2)
        score_3 = scorer.score(ResolutionMethod.TRIE_FALLBACK, ambiguity_count=3)

        assert score_2 < score_1
        assert score_3 < score_2

    def test_penalty_capped_at_max(self, scorer: ConfidenceScorer) -> None:
        """Penalty should not exceed max_ambiguity_penalty."""
        # With default config: base=0.5, max_penalty=0.3, so min score = 0.2
        score_many = scorer.score(ResolutionMethod.TRIE_FALLBACK, ambiguity_count=100)
        assert score_many == pytest.approx(0.2)

    def test_penalty_only_applies_to_trie_fallback(
        self, scorer: ConfidenceScorer
    ) -> None:
        """Ambiguity penalty should only apply to TRIE_FALLBACK."""
        # Direct import should not be penalized
        score = scorer.score(ResolutionMethod.DIRECT_IMPORT, ambiguity_count=10)
        assert score == 1.0


class TestConfidenceScorerCustomConfig:
    """Test with custom configuration."""

    def test_custom_base_scores(self, custom_scorer: ConfidenceScorer) -> None:
        """Custom config should override base scores."""
        score = custom_scorer.score(ResolutionMethod.DIRECT_IMPORT)
        assert score == 0.99

    def test_custom_trie_fallback_base(self, custom_scorer: ConfidenceScorer) -> None:
        """Custom trie fallback base should be used."""
        score = custom_scorer.score(ResolutionMethod.TRIE_FALLBACK, ambiguity_count=1)
        assert score == 0.4

    def test_custom_ambiguity_penalty(self, custom_scorer: ConfidenceScorer) -> None:
        """Custom ambiguity penalty should be applied."""
        # Custom config has penalty of 0.1 per match
        score = custom_scorer.score(ResolutionMethod.TRIE_FALLBACK, ambiguity_count=3)
        # base=0.4, penalty=(3-1)*0.1=0.2, result=0.2
        assert score == pytest.approx(0.2)


class TestConfidenceScorerEdgeCases:
    """Test edge cases."""

    def test_score_with_zero_ambiguity(self, scorer: ConfidenceScorer) -> None:
        """Zero ambiguity should be treated same as 1."""
        score = scorer.score(ResolutionMethod.TRIE_FALLBACK, ambiguity_count=0)
        # No penalty since ambiguity_count <= 1
        assert score == 0.5

    def test_score_with_negative_ambiguity(self, scorer: ConfidenceScorer) -> None:
        """Negative ambiguity should be handled gracefully."""
        score = scorer.score(ResolutionMethod.TRIE_FALLBACK, ambiguity_count=-5)
        # No penalty applied
        assert score == 0.5

    def test_score_ignores_extra_context(self, scorer: ConfidenceScorer) -> None:
        """Extra context kwargs should be ignored (reserved for future)."""
        score = scorer.score(
            ResolutionMethod.DIRECT_IMPORT,
            ambiguity_count=1,
            caller_file="foo.py",
            some_future_param=42,
        )
        assert score == 1.0
