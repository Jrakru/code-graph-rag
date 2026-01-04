from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from codebase_rag import constants as cs
from codebase_rag.cypher_queries import CYPHER_FETCH_FILE_HASHES
from codebase_rag.services.provenance_tracker import ProvenanceTracker


def _write_file(root: Path, name: str) -> Path:
    path = root / name
    path.write_text("content", encoding="utf-8")
    return path


def test_is_stale_returns_false_when_hash_matches(tmp_path: Path) -> None:
    _write_file(tmp_path, "file.txt")
    ingestor = MagicMock()
    ingestor.fetch_all.return_value = [
        {cs.KEY_PATH: "file.txt", cs.KEY_FILE_HASH: "abc", cs.KEY_PARSED_AT: "t"}
    ]

    tracker = ProvenanceTracker(ingestor, tmp_path)

    assert tracker.is_stale("file.txt", "abc") is False
    ingestor.fetch_all.assert_called_once_with(
        CYPHER_FETCH_FILE_HASHES, {cs.KEY_PATHS: ["file.txt"]}
    )


def test_is_stale_returns_true_when_hash_differs(tmp_path: Path) -> None:
    _write_file(tmp_path, "file.txt")
    ingestor = MagicMock()
    ingestor.fetch_all.return_value = [
        {cs.KEY_PATH: "file.txt", cs.KEY_FILE_HASH: "abc", cs.KEY_PARSED_AT: "t"}
    ]

    tracker = ProvenanceTracker(ingestor, tmp_path)

    assert tracker.is_stale("file.txt", "def") is True


def test_is_stale_returns_true_when_missing_in_graph(tmp_path: Path) -> None:
    _write_file(tmp_path, "file.txt")
    ingestor = MagicMock()
    ingestor.fetch_all.return_value = []

    tracker = ProvenanceTracker(ingestor, tmp_path)

    assert tracker.is_stale("file.txt", "abc") is True


def test_is_stale_returns_true_for_missing_file(tmp_path: Path) -> None:
    ingestor = MagicMock()
    tracker = ProvenanceTracker(ingestor, tmp_path)

    assert tracker.is_stale("missing.txt", "abc") is True
    ingestor.fetch_all.assert_not_called()


def test_is_stale_returns_true_for_corrupted_hash(tmp_path: Path) -> None:
    _write_file(tmp_path, "file.txt")
    ingestor = MagicMock()
    ingestor.fetch_all.return_value = [
        {cs.KEY_PATH: "file.txt", cs.KEY_FILE_HASH: None, cs.KEY_PARSED_AT: "t"}
    ]

    tracker = ProvenanceTracker(ingestor, tmp_path)

    assert tracker.is_stale("file.txt", "abc") is True


def test_is_stale_returns_true_for_missing_current_hash(tmp_path: Path) -> None:
    _write_file(tmp_path, "file.txt")
    ingestor = MagicMock()
    tracker = ProvenanceTracker(ingestor, tmp_path)

    assert tracker.is_stale("file.txt", "") is True
    ingestor.fetch_all.assert_not_called()


def test_is_stale_batch_returns_expected_map(tmp_path: Path) -> None:
    file_a = _write_file(tmp_path, "a.txt")
    _write_file(tmp_path, "b.txt")

    ingestor = MagicMock()
    ingestor.fetch_all.return_value = [
        {cs.KEY_PATH: "a.txt", cs.KEY_FILE_HASH: "hash-a", cs.KEY_PARSED_AT: "t"}
    ]

    tracker = ProvenanceTracker(ingestor, tmp_path)

    results = tracker.is_stale_batch(
        [
            (file_a, "hash-a"),
            ("b.txt", "hash-b"),
        ]
    )

    assert results == {"a.txt": False, "b.txt": True}
    ingestor.fetch_all.assert_called_once_with(
        CYPHER_FETCH_FILE_HASHES, {cs.KEY_PATHS: ["a.txt", "b.txt"]}
    )


def test_get_stored_hashes_normalizes_paths(tmp_path: Path) -> None:
    file_a = _write_file(tmp_path, "a.txt")

    ingestor = MagicMock()
    ingestor.fetch_all.return_value = [
        {cs.KEY_PATH: "a.txt", cs.KEY_FILE_HASH: "hash-a", cs.KEY_PARSED_AT: "t"}
    ]

    tracker = ProvenanceTracker(ingestor, tmp_path)

    result = tracker.get_stored_hashes([file_a])

    assert result == {"a.txt": "hash-a"}
    ingestor.fetch_all.assert_called_once_with(
        CYPHER_FETCH_FILE_HASHES, {cs.KEY_PATHS: ["a.txt"]}
    )
