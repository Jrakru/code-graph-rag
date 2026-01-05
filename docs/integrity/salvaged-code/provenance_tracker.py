"""Provenance tracking for indexed files."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class ProvenanceTracker:
    """Tracks provenance metadata for parsed files."""

    def record_parse(self, path: Path) -> dict[str, Any]:
        """Record provenance metadata for a parsed file.

        Args:
            path: Path to the file being parsed

        Returns:
            Dictionary with provenance metadata:
            - parsed_at: ISO 8601 timestamp
            - file_mtime: Unix timestamp of file modification
            - file_hash: SHA256 hash of file contents
        """
        metadata: dict[str, Any] = {
            "parsed_at": datetime.now(UTC).isoformat(),
        }

        if path.exists():
            stat = path.stat()
            metadata["file_mtime"] = stat.st_mtime

            content = path.read_bytes()
            metadata["file_hash"] = hashlib.sha256(content).hexdigest()

        return metadata

    def is_stale(self, path: Path, stored_hash: str) -> bool:
        """Check if a file has changed since it was indexed.

        Args:
            path: Path to check
            stored_hash: Previously recorded hash

        Returns:
            True if file content has changed
        """
        if not path.exists():
            return True

        current_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        return current_hash != stored_hash
