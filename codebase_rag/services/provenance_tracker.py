from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

from .. import constants as cs
from .. import logs as ls
from ..cypher_queries import CYPHER_FETCH_FILE_HASHES

if TYPE_CHECKING:
    from . import QueryProtocol


class ProvenanceTracker:
    def __init__(
        self,
        ingestor: QueryProtocol | None = None,
        repo_root: Path | str | None = None,
        chunk_size: int = cs.BYTES_PER_MB,
    ) -> None:
        if chunk_size < 1:
            raise ValueError("chunk_size must be positive")
        self.ingestor = ingestor
        self.repo_root = Path(repo_root).resolve() if repo_root is not None else None
        self.chunk_size = chunk_size

    def record_parse(
        self, file_path: Path | str, source_bytes: bytes | None = None
    ) -> dict[str, str | float]:
        path = Path(file_path)
        try:
            file_mtime = path.stat().st_mtime
        except FileNotFoundError:
            logger.warning(ls.SOURCE_FILE_NOT_FOUND.format(path=path))
            return {}
        except OSError as exc:
            logger.error(ls.SOURCE_FILE_NOT_FOUND.format(path=path))
            logger.error(str(exc))
            return {}

        try:
            if source_bytes is not None:
                file_hash = self._hash_bytes(source_bytes)
            else:
                file_hash = self._hash_file(path)
        except OSError as exc:
            logger.error(ls.SOURCE_FILE_NOT_FOUND.format(path=path))
            logger.error(str(exc))
            return {}

        return {
            cs.KEY_PARSED_AT: datetime.now(UTC).isoformat(),
            cs.KEY_FILE_MTIME: file_mtime,
            cs.KEY_FILE_HASH: file_hash,
        }

    def is_stale(self, path: Path | str, file_hash: str | None) -> bool:
        """Return True when the given file hash is missing or differs from graph state."""
        normalized_path = self._normalize_path(path)

        if not self._hash_is_valid(file_hash):
            return True

        if not self._path_exists(path):
            return True

        stored_hash = self.get_stored_hash(normalized_path)
        if not self._hash_is_valid(stored_hash):
            return True

        return stored_hash != file_hash

    def is_stale_batch(
        self,
        files: Mapping[Path | str, str | None]
        | Iterable[tuple[Path | str, str | None]],
    ) -> dict[str, bool]:
        """Batch staleness check keyed by normalized relative paths."""
        items: list[tuple[Path | str, str | None]] = []
        if isinstance(files, Mapping):
            for path, file_hash in files.items():
                if not isinstance(path, (str, Path)):
                    continue
                if file_hash is not None and not isinstance(file_hash, str):
                    file_hash = None
                items.append((path, file_hash))
        else:
            for entry in files:
                if not isinstance(entry, tuple) or len(entry) != 2:
                    continue
                path, file_hash = entry
                if not isinstance(path, (str, Path)):
                    continue
                if file_hash is not None and not isinstance(file_hash, str):
                    file_hash = None
                items.append((path, file_hash))

        if not items:
            return {}

        normalized_items: list[tuple[str, Path | str, str | None]] = [
            (self._normalize_path(path), path, file_hash) for path, file_hash in items
        ]

        stored_hashes = self.get_stored_hashes(
            [normalized for normalized, _, _ in normalized_items]
        )

        results: dict[str, bool] = {}
        for normalized_path, original_path, file_hash in normalized_items:
            stored_hash = stored_hashes.get(normalized_path)
            results[normalized_path] = self._is_stale_with_stored(
                original_path, file_hash, stored_hash
            )
        return results

    def get_stored_hash(self, path: Path | str) -> str | None:
        """Fetch the stored file hash for a single path."""
        hashes = self.get_stored_hashes([path])
        normalized_path = self._normalize_path(path)
        return hashes.get(normalized_path)

    def get_stored_hashes(self, paths: Sequence[Path | str]) -> dict[str, str | None]:
        """Fetch stored file hashes for multiple paths from Memgraph."""
        normalized_paths = [self._normalize_path(path) for path in paths]
        if not normalized_paths:
            return {}

        ingestor = self._require_ingestor()
        results = ingestor.fetch_all(
            CYPHER_FETCH_FILE_HASHES, {cs.KEY_PATHS: normalized_paths}
        )

        stored: dict[str, str | None] = {}
        for row in results:
            path_value = row.get(cs.KEY_PATH)
            if isinstance(path_value, str):
                stored[path_value] = self._coerce_hash(row.get(cs.KEY_FILE_HASH))

        return {path: stored.get(path) for path in normalized_paths}

    def _is_stale_with_stored(
        self, path: Path | str, file_hash: str | None, stored_hash: str | None
    ) -> bool:
        if not self._hash_is_valid(file_hash):
            return True
        if not self._path_exists(path):
            return True
        if not self._hash_is_valid(stored_hash):
            return True
        return stored_hash != file_hash

    def _normalize_path(self, path: Path | str) -> str:
        repo_root = self._require_repo_root()
        path_obj = Path(path)
        if path_obj.is_absolute():
            try:
                return str(path_obj.relative_to(repo_root))
            except ValueError:
                return str(path_obj)
        return str(path_obj)

    def _path_exists(self, path: Path | str) -> bool:
        repo_root = self._require_repo_root()
        path_obj = Path(path)
        if path_obj.is_absolute():
            return path_obj.exists()
        return (repo_root / path_obj).exists()

    def _hash_is_valid(self, value: str | None) -> bool:
        return isinstance(value, str) and value != ""

    def _coerce_hash(self, value: Any) -> str | None:
        if isinstance(value, str):
            return value
        return None

    def _hash_file(self, file_path: Path) -> str:
        hasher = sha256()
        with file_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(self.chunk_size), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    @staticmethod
    def _hash_bytes(source_bytes: bytes) -> str:
        return sha256(source_bytes).hexdigest()

    def _require_ingestor(self) -> QueryProtocol:
        if self.ingestor is None:
            raise ValueError("ingestor is required for staleness checks")
        return self.ingestor

    def _require_repo_root(self) -> Path:
        if self.repo_root is None:
            raise ValueError("repo_root is required for staleness checks")
        return self.repo_root
