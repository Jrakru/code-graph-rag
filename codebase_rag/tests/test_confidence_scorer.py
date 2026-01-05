import pytest

from codebase_rag.services.confidence_scorer import (
    ConfidenceConfig,
    ConfidenceScorer,
    ResolutionMethod,
)


def test_default_scores() -> None:
    scorer = ConfidenceScorer()
    assert scorer.score(ResolutionMethod.DIRECT_IMPORT) == pytest.approx(1.0)
    assert scorer.score(ResolutionMethod.SAME_MODULE) == pytest.approx(0.95)
    assert scorer.score(ResolutionMethod.TYPE_INFERENCE) == pytest.approx(0.9)
    assert scorer.score(ResolutionMethod.INHERITED_METHOD) == pytest.approx(0.85)
    assert scorer.score(ResolutionMethod.IIFE) == pytest.approx(0.8)
    assert scorer.score(ResolutionMethod.WILDCARD_IMPORT) == pytest.approx(0.7)
    assert scorer.score(ResolutionMethod.TRIE_FALLBACK) == pytest.approx(0.5)
    assert scorer.score(ResolutionMethod.UNRESOLVED) == pytest.approx(0.0)


def test_trie_fallback_penalty_applies() -> None:
    scorer = ConfidenceScorer()
    assert scorer.score(
        ResolutionMethod.TRIE_FALLBACK, ambiguity_count=3
    ) == pytest.approx(0.4)


def test_custom_config_overrides_defaults() -> None:
    config = ConfidenceConfig(
        direct_import_base=0.8,
        trie_fallback_base=0.2,
        ambiguity_penalty_per_match=0.1,
        max_ambiguity_penalty=0.2,
    )
    scorer = ConfidenceScorer(config)

    assert scorer.score(ResolutionMethod.DIRECT_IMPORT) == pytest.approx(0.8)
    assert scorer.score(
        ResolutionMethod.TRIE_FALLBACK, ambiguity_count=4
    ) == pytest.approx(0.0)
