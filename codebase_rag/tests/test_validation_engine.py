"""Tests for validation engine."""

import pytest

from codebase_rag.services.validation_engine import (
    OrphanedRelationship,
    ValidationEngine,
    ValidationResult,
)


@pytest.fixture
def engine() -> ValidationEngine:
    """Create a ValidationEngine without graph backend."""
    return ValidationEngine(graph_service=None)


class TestValidationResult:
    """Test ValidationResult dataclass."""

    def test_valid_result(self) -> None:
        """Valid result should have is_valid=True."""
        result = ValidationResult(is_valid=True)
        assert result.is_valid is True
        assert result.error_message == ""

    def test_invalid_result_with_message(self) -> None:
        """Invalid result should include error message."""
        result = ValidationResult(is_valid=False, error_message="Target not found")
        assert result.is_valid is False
        assert result.error_message == "Target not found"


class TestOrphanedRelationship:
    """Test OrphanedRelationship dataclass."""

    def test_orphan_record(self) -> None:
        """OrphanedRelationship should store all fields."""
        orphan = OrphanedRelationship(
            source_id=1,
            target_id=999,
            rel_type="CALLS",
            source_label="Function",
            expected_target_label="Function",
        )
        assert orphan.source_id == 1
        assert orphan.target_id == 999
        assert orphan.rel_type == "CALLS"
        assert orphan.source_label == "Function"
        assert orphan.expected_target_label == "Function"


class TestValidationEngineWithoutGraph:
    """Test ValidationEngine without graph backend (fallback mode)."""

    def test_validate_relationship_valid_target(self, engine: ValidationEngine) -> None:
        """Relationships with target_id < 999 should be valid in fallback mode."""
        result = engine.validate_relationship(
            source_id=1, target_id=100, rel_type="CALLS"
        )
        assert result.is_valid is True

    def test_validate_relationship_invalid_target(
        self, engine: ValidationEngine
    ) -> None:
        """Relationships with target_id >= 999 should be invalid in fallback mode."""
        result = engine.validate_relationship(
            source_id=1, target_id=1000, rel_type="CALLS"
        )
        assert result.is_valid is False
        assert "Target not found" in result.error_message

    def test_validate_relationship_boundary(self, engine: ValidationEngine) -> None:
        """Test boundary condition at fallback threshold."""
        # ID 998 is valid (< 999)
        result_valid = engine.validate_relationship(
            source_id=1, target_id=998, rel_type="CALLS"
        )
        assert result_valid.is_valid is True

        # ID 999 is invalid (>= 999)
        result_invalid = engine.validate_relationship(
            source_id=1, target_id=999, rel_type="CALLS"
        )
        assert result_invalid.is_valid is False

    def test_report_orphans_empty_without_graph(self, engine: ValidationEngine) -> None:
        """report_orphans should return empty list without graph backend."""
        orphans = engine.report_orphans()
        assert orphans == []


class TestValidationEngineWithMockedGraph:
    """Test ValidationEngine with mocked graph service."""

    def test_validate_relationship_with_existing_node(self) -> None:
        """Should return valid when node exists in graph."""

        class MockGraphService:
            def fetch_all(self, query: str, params: dict | None = None) -> list:
                # Simulate node exists
                return [{"n": {"id": 100}}]

        engine = ValidationEngine(graph_service=MockGraphService())  # type: ignore[arg-type]
        result = engine.validate_relationship(
            source_id=1, target_id=100, rel_type="CALLS"
        )
        assert result.is_valid is True

    def test_validate_relationship_with_missing_node(self) -> None:
        """Should return invalid when node doesn't exist in graph."""

        class MockGraphService:
            def fetch_all(self, query: str, params: dict | None = None) -> list:
                # Simulate node doesn't exist
                return []

        engine = ValidationEngine(graph_service=MockGraphService())  # type: ignore[arg-type]
        result = engine.validate_relationship(
            source_id=1, target_id=9999, rel_type="CALLS"
        )
        assert result.is_valid is False
        assert "9999" in result.error_message

    def test_report_orphans_with_graph(self) -> None:
        """Should return orphans from graph query."""

        class MockGraphService:
            def fetch_all(self, query: str, params: dict | None = None) -> list:
                # Simulate orphaned relationships found
                return [
                    {
                        "source_id": 1,
                        "target_id": None,
                        "rel_type": "CALLS",
                        "source_label": "Function",
                        "expected_target_label": "",
                    },
                    {
                        "source_id": 2,
                        "target_id": None,
                        "rel_type": "IMPORTS",
                        "source_label": "Module",
                        "expected_target_label": "",
                    },
                ]

        engine = ValidationEngine(graph_service=MockGraphService())  # type: ignore[arg-type]
        orphans = engine.report_orphans()

        assert len(orphans) == 2
        assert orphans[0].source_id == 1
        assert orphans[0].rel_type == "CALLS"
        assert orphans[1].source_id == 2
        assert orphans[1].rel_type == "IMPORTS"


class TestValidationEngineEdgeCases:
    """Test edge cases."""

    def test_validate_with_zero_ids(self, engine: ValidationEngine) -> None:
        """Should handle zero IDs gracefully."""
        result = engine.validate_relationship(
            source_id=0, target_id=0, rel_type="CALLS"
        )
        # ID 0 is < 999 threshold, so valid in fallback mode
        assert result.is_valid is True

    def test_validate_with_negative_ids(self, engine: ValidationEngine) -> None:
        """Should handle negative IDs gracefully."""
        result = engine.validate_relationship(
            source_id=-1, target_id=-100, rel_type="CALLS"
        )
        # Negative IDs are < 999 threshold
        assert result.is_valid is True

    def test_validate_different_relationship_types(
        self, engine: ValidationEngine
    ) -> None:
        """Should work for any relationship type."""
        for rel_type in ["CALLS", "IMPORTS", "DEFINES", "INHERITS"]:
            result = engine.validate_relationship(
                source_id=1, target_id=2, rel_type=rel_type
            )
            assert result.is_valid is True
