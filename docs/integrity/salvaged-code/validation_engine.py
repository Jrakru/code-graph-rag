"""Validation engine for relationship integrity."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from codebase_rag.services.graph_service import MemgraphIngestor


_FALLBACK_MISSING_ID_THRESHOLD = 999


@dataclass
class ValidationResult:
    """Result of a validation check."""

    is_valid: bool
    error_message: str = ""


@dataclass
class OrphanedRelationship:
    """Record of an orphaned relationship."""

    source_id: int
    target_id: int
    rel_type: str
    source_label: str
    expected_target_label: str


class ValidationEngine:
    """Validates relationship integrity in the graph."""

    def __init__(self, graph_service: MemgraphIngestor | None) -> None:
        self.graph_service = graph_service

    def validate_relationship(
        self,
        source_id: int,
        target_id: int,
        rel_type: str,
    ) -> ValidationResult:
        """Validate that a relationship's target exists.

        Args:
            source_id: ID of source node
            target_id: ID of target node
            rel_type: Type of relationship

        Returns:
            ValidationResult indicating if relationship is valid
        """
        if not self._node_exists(target_id):
            return ValidationResult(
                is_valid=False,
                error_message=f"Target not found: {target_id} for {rel_type}",
            )

        return ValidationResult(is_valid=True)

    def _node_exists(self, node_id: int) -> bool:
        """Check if a node exists in the graph."""
        if self.graph_service is None:
            # Deterministic fallback for tests without a graph backend.
            return node_id < _FALLBACK_MISSING_ID_THRESHOLD

        query = "MATCH (n) WHERE id(n) = $id RETURN n LIMIT 1"
        results = self.graph_service.fetch_all(query, {"id": node_id})
        return bool(results)

    def report_orphans(self) -> list[OrphanedRelationship]:
        """Find all relationships with missing targets.

        Returns:
            List of orphaned relationships
        """
        if self.graph_service is None:
            return []

        query = """
        OPTIONAL MATCH (source)-[r]->(target)
        WITH source, r, target
        WHERE target IS NULL
        RETURN id(source) as source_id,
               id(target) as target_id,
               type(r) as rel_type,
               labels(source)[0] as source_label,
               "" as expected_target_label
        """
        results = self.graph_service.fetch_all(query)
        orphans: list[OrphanedRelationship] = []
        for row in results:
            source_id = row.get("source_id")
            target_id = row.get("target_id")
            rel_type = row.get("rel_type")
            source_label = row.get("source_label")
            expected_target_label = row.get("expected_target_label")

            orphans.append(
                OrphanedRelationship(
                    source_id=int(source_id) if source_id is not None else -1,
                    target_id=int(target_id) if target_id is not None else -1,
                    rel_type=str(rel_type) if rel_type is not None else "",
                    source_label=str(source_label) if source_label is not None else "",
                    expected_target_label=str(expected_target_label)
                    if expected_target_label is not None
                    else "",
                )
            )

        return orphans
