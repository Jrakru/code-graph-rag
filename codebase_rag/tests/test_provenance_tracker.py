from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from codebase_rag import constants as cs
from codebase_rag.tests.conftest import get_nodes, run_updater

try:
    from codebase_rag.services.provenance_tracker import ProvenanceTracker
except ModuleNotFoundError:
    ProvenanceTracker = None


if ProvenanceTracker is None:
    pytest.skip(
        "ProvenanceTracker not implemented yet; skipping provenance tests",
        allow_module_level=True,
    )


def _get_record_value(record: object, key: str) -> object:
    if isinstance(record, dict):
        return record[key]
    if hasattr(record, "model_dump"):
        return record.model_dump()[key]
    return getattr(record, key)


def _parse_parsed_at(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        assert isinstance(value, str)
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


class TestProvenanceRecordParse:
    def test_record_parse_captures_timestamp_mtime_and_hash(
        self, tmp_path: Path
    ) -> None:
        file_path = tmp_path / "sample.py"
        file_path.write_text("print('hello')\n", encoding="utf-8")

        tracker = ProvenanceTracker()
        before = datetime.now(UTC)
        record = tracker.record_parse(file_path)
        after = datetime.now(UTC)

        parsed_at = _parse_parsed_at(_get_record_value(record, cs.KEY_PARSED_AT))
        assert before <= parsed_at <= after

        file_mtime = _get_record_value(record, cs.KEY_FILE_MTIME)
        assert isinstance(file_mtime, (int, float))
        assert file_mtime == pytest.approx(file_path.stat().st_mtime)

        file_hash = _get_record_value(record, cs.KEY_FILE_HASH)
        expected_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
        assert file_hash == expected_hash

    def test_record_parse_with_source_bytes(self, tmp_path: Path) -> None:
        file_path = tmp_path / "sample.py"
        content = b"print('hello')\n"
        file_path.write_bytes(content)

        tracker = ProvenanceTracker()
        record = tracker.record_parse(file_path, source_bytes=content)

        assert cs.KEY_PARSED_AT in record
        assert cs.KEY_FILE_MTIME in record
        assert cs.KEY_FILE_HASH in record
        assert record[cs.KEY_FILE_HASH] == hashlib.sha256(content).hexdigest()

    def test_record_parse_returns_empty_for_missing_file(self, tmp_path: Path) -> None:
        file_path = tmp_path / "nonexistent.py"

        tracker = ProvenanceTracker()
        record = tracker.record_parse(file_path)

        assert record == {}

    def test_custom_chunk_size(self, tmp_path: Path) -> None:
        file_path = tmp_path / "sample.py"
        file_path.write_text("x" * 100, encoding="utf-8")

        tracker = ProvenanceTracker(chunk_size=10)
        record = tracker.record_parse(file_path)

        assert cs.KEY_FILE_HASH in record
        assert record[cs.KEY_FILE_HASH] == hashlib.sha256(b"x" * 100).hexdigest()

    def test_invalid_chunk_size_raises(self) -> None:
        with pytest.raises(ValueError, match="chunk_size must be positive"):
            ProvenanceTracker(chunk_size=0)

        with pytest.raises(ValueError, match="chunk_size must be positive"):
            ProvenanceTracker(chunk_size=-1)


class TestProvenanceIntegration:
    def test_indexing_attaches_provenance_fields(
        self, temp_repo: Path, mock_ingestor
    ) -> None:
        project_path = temp_repo / "sample_project"
        project_path.mkdir()
        (project_path / "__init__.py").touch()
        target_file = project_path / "main.py"
        target_file.write_text("def main():\n    return 1\n", encoding="utf-8")

        run_updater(project_path, mock_ingestor)

        file_nodes = get_nodes(mock_ingestor, cs.NodeLabel.FILE)
        assert file_nodes

        relative_path = str(target_file.relative_to(project_path))
        matching = [
            call
            for call in file_nodes
            if call.args[1].get(cs.KEY_PATH) == relative_path
        ]
        assert matching

        file_props = matching[0].args[1]
        assert cs.KEY_PARSED_AT in file_props
        assert cs.KEY_FILE_MTIME in file_props
        assert cs.KEY_FILE_HASH in file_props

        parsed_at = _parse_parsed_at(file_props[cs.KEY_PARSED_AT])
        assert isinstance(parsed_at, datetime)
        assert file_props[cs.KEY_FILE_MTIME] == pytest.approx(
            target_file.stat().st_mtime
        )
        assert (
            file_props[cs.KEY_FILE_HASH]
            == hashlib.sha256(target_file.read_bytes()).hexdigest()
        )
