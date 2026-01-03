"""Tests for provenance tracking."""

import hashlib
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from codebase_rag.services.provenance_tracker import ProvenanceTracker


@pytest.fixture
def tracker() -> ProvenanceTracker:
    """Create a ProvenanceTracker instance."""
    return ProvenanceTracker()


@pytest.fixture
def temp_file() -> Path:
    """Create a temporary file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("# test content\nprint('hello')")
        return Path(f.name)


class TestProvenanceTrackerRecordParse:
    """Test recording parse provenance."""

    def test_record_parse_returns_parsed_at(
        self, tracker: ProvenanceTracker, temp_file: Path
    ) -> None:
        """record_parse should include parsed_at timestamp."""
        metadata = tracker.record_parse(temp_file)
        assert "parsed_at" in metadata
        # Should be valid ISO 8601
        datetime.fromisoformat(metadata["parsed_at"])

    def test_record_parse_returns_file_mtime(
        self, tracker: ProvenanceTracker, temp_file: Path
    ) -> None:
        """record_parse should include file modification time."""
        metadata = tracker.record_parse(temp_file)
        assert "file_mtime" in metadata
        assert isinstance(metadata["file_mtime"], float)
        assert metadata["file_mtime"] > 0

    def test_record_parse_returns_file_hash(
        self, tracker: ProvenanceTracker, temp_file: Path
    ) -> None:
        """record_parse should include SHA256 hash of file content."""
        metadata = tracker.record_parse(temp_file)
        assert "file_hash" in metadata
        # Verify it's a valid SHA256 hash (64 hex chars)
        assert len(metadata["file_hash"]) == 64
        assert all(c in "0123456789abcdef" for c in metadata["file_hash"])

    def test_record_parse_hash_matches_content(
        self, tracker: ProvenanceTracker, temp_file: Path
    ) -> None:
        """Hash should match actual file content."""
        metadata = tracker.record_parse(temp_file)
        expected_hash = hashlib.sha256(temp_file.read_bytes()).hexdigest()
        assert metadata["file_hash"] == expected_hash

    def test_record_parse_nonexistent_file(self, tracker: ProvenanceTracker) -> None:
        """record_parse on nonexistent file should still return parsed_at."""
        metadata = tracker.record_parse(Path("/nonexistent/file.py"))
        assert "parsed_at" in metadata
        assert "file_mtime" not in metadata
        assert "file_hash" not in metadata


class TestProvenanceTrackerIsStale:
    """Test staleness detection."""

    def test_is_stale_returns_false_for_unchanged_file(
        self, tracker: ProvenanceTracker, temp_file: Path
    ) -> None:
        """is_stale should return False if file hasn't changed."""
        metadata = tracker.record_parse(temp_file)
        assert tracker.is_stale(temp_file, metadata["file_hash"]) is False

    def test_is_stale_returns_true_for_modified_file(
        self, tracker: ProvenanceTracker, temp_file: Path
    ) -> None:
        """is_stale should return True if file content changed."""
        metadata = tracker.record_parse(temp_file)
        # Modify the file
        temp_file.write_text("# modified content\nprint('goodbye')")
        assert tracker.is_stale(temp_file, metadata["file_hash"]) is True

    def test_is_stale_returns_true_for_deleted_file(
        self, tracker: ProvenanceTracker, temp_file: Path
    ) -> None:
        """is_stale should return True if file no longer exists."""
        metadata = tracker.record_parse(temp_file)
        temp_file.unlink()
        assert tracker.is_stale(temp_file, metadata["file_hash"]) is True

    def test_is_stale_returns_true_for_wrong_hash(
        self, tracker: ProvenanceTracker, temp_file: Path
    ) -> None:
        """is_stale should return True if stored hash doesn't match."""
        wrong_hash = "a" * 64
        assert tracker.is_stale(temp_file, wrong_hash) is True


class TestProvenanceTrackerEdgeCases:
    """Test edge cases."""

    def test_empty_file(self, tracker: ProvenanceTracker) -> None:
        """Should handle empty files correctly."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            # Write nothing - empty file
            pass

        empty_file = Path(f.name)
        metadata = tracker.record_parse(empty_file)

        assert "file_hash" in metadata
        # SHA256 of empty string
        expected_empty_hash = hashlib.sha256(b"").hexdigest()
        assert metadata["file_hash"] == expected_empty_hash

        # Cleanup
        empty_file.unlink()

    def test_binary_file(self, tracker: ProvenanceTracker) -> None:
        """Should handle binary files correctly."""
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".bin", delete=False) as f:
            binary_content = bytes(range(256))
            f.write(binary_content)
            binary_file = Path(f.name)

        metadata = tracker.record_parse(binary_file)
        expected_hash = hashlib.sha256(binary_content).hexdigest()
        assert metadata["file_hash"] == expected_hash

        # Cleanup
        binary_file.unlink()
