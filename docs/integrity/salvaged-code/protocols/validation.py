"""Validation-related protocols."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from codebase_rag.services.confidence_scorer import ResolutionMethod
    from codebase_rag.services.validation_engine import (
        OrphanedRelationship,
        ValidationResult,
    )


class ConfidenceScorerProtocol(Protocol):
    """Scores confidence of call resolutions."""

    def score(
        self,
        method: ResolutionMethod,
        ambiguity_count: int = 1,
        **context: Any,
    ) -> float:
        """Return confidence score 0.0-1.0 for a resolution."""
        ...


class ValidationEngineProtocol(Protocol):
    """Validates relationship targets exist."""

    def validate_relationship(
        self,
        source_id: int,
        target_id: int,
        rel_type: str,
    ) -> ValidationResult:
        """Validate a relationship and return result."""
        ...

    def report_orphans(self) -> list[OrphanedRelationship]:
        """Return all relationships with missing targets."""
        ...
