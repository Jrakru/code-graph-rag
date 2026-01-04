from __future__ import annotations

import hashlib
import inspect
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


def _hash_algorithm(tracker: object) -> str:
    algo = getattr(tracker, "hash_algorithm", None)
    if isinstance(algo, str) and algo:
        return algo
    return "sha256"


def _call_is_stale(tracker: object, file_path: Path, record: object) -> bool:
    signature = inspect.signature(tracker.is_stale)
    params = list(signature.parameters.values())
    if len(params) == 2:
        return tracker.is_stale(file_path)
    if len(params) == 3:
        return tracker.is_stale(file_path, record)
    return tracker.is_stale(record)


class TestProvenanceRecordParse:
    def test_record_parse_captures_timestamp_mtime_and_hash(
        self, tmp_path: Path
    ) -> None:
        file_path = tmp_path / "sample.py"
        file_path.write_text("print('hello')\n", encoding="utf-8")

        tracker = ProvenanceTracker(tmp_path)
        before = datetime.now(UTC)
        record = tracker.record_parse(file_path)
        after = datetime.now(UTC)

        parsed_at = _parse_parsed_at(_get_record_value(record, "parsed_at"))
        assert before <= parsed_at <= after

        file_mtime = _get_record_value(record, "file_mtime")
        assert isinstance(file_mtime, (int, float))
        assert file_mtime == pytest.approx(file_path.stat().st_mtime)

        file_hash = _get_record_value(record, "file_hash")
        expected_hash = hashlib.new(
            _hash_algorithm(tracker), file_path.read_bytes()
        ).hexdigest()
        assert file_hash == expected_hash


class TestProvenanceIsStale:
    def test_is_stale_false_for_unchanged_file(self, tmp_path: Path) -> None:
        file_path = tmp_path / "sample.py"
        file_path.write_text("print('hello')\n", encoding="utf-8")

        tracker = ProvenanceTracker(tmp_path)
        record = tracker.record_parse(file_path)

        assert _call_is_stale(tracker, file_path, record) is False

    def test_is_stale_true_for_modified_file(self, tmp_path: Path) -> None:
        file_path = tmp_path / "sample.py"
        file_path.write_text("print('hello')\n", encoding="utf-8")

        tracker = ProvenanceTracker(tmp_path)
        record = tracker.record_parse(file_path)

        file_path.write_text("print('changed')\n", encoding="utf-8")
        file_path.touch()

        assert _call_is_stale(tracker, file_path, record) is True

    def test_is_stale_true_for_missing_file(self, tmp_path: Path) -> None:
        file_path = tmp_path / "sample.py"
        file_path.write_text("print('hello')\n", encoding="utf-8")

        tracker = ProvenanceTracker(tmp_path)
        record = tracker.record_parse(file_path)

        file_path.unlink()

        assert _call_is_stale(tracker, file_path, record) is True


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
        assert "parsed_at" in file_props
        assert "file_mtime" in file_props
        assert "file_hash" in file_props

        parsed_at = _parse_parsed_at(file_props["parsed_at"])
        assert isinstance(parsed_at, datetime)
        assert file_props["file_mtime"] == pytest.approx(target_file.stat().st_mtime)
        assert (
            file_props["file_hash"]
            == hashlib.new(
                _hash_algorithm(ProvenanceTracker(project_path)),
                target_file.read_bytes(),
            ).hexdigest()
        )
