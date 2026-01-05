"""Provenance-related protocols."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from codebase_rag.services.file_classifier import SourceType


class FileClassifierProtocol(Protocol):
    """Classifies files by source type."""

    def classify(self, path: Path) -> SourceType:
        """Return the source type for a file path."""
        ...

    def is_documentation(self, path: Path) -> bool:
        """Quick check if file is documentation."""
        ...


class ProvenanceTrackerProtocol(Protocol):
    """Tracks provenance metadata for parsed files."""

    def record_parse(self, path: Path) -> dict[str, Any]:
        """Return provenance metadata for a parsed file."""
        ...

    def is_stale(self, path: Path, stored_hash: str) -> bool:
        """Check if a file has changed since parsing."""
        ...
