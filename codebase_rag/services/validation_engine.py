from __future__ import annotations

from collections.abc import Sequence

from ..protocols import ValidationEngineProtocol


class ValidationEngine(ValidationEngineProtocol):
    def __init__(self, orphaned_relationships: Sequence[object] | None = None) -> None:
        self._orphaned_relationships = list(orphaned_relationships or [])

    def validate_relationship(self) -> bool:
        return not self._orphaned_relationships

    def report_orphans(self) -> list[object]:
        return list(self._orphaned_relationships)
