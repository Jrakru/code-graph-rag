from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from loguru import logger

from .. import constants as cs
from .. import logs as ls


class ProvenanceTracker:
    def __init__(self, chunk_size: int = cs.BYTES_PER_MB) -> None:
        if chunk_size < 1:
            raise ValueError("chunk_size must be positive")
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

    def _hash_file(self, file_path: Path) -> str:
        hasher = sha256()
        with file_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(self.chunk_size), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    @staticmethod
    def _hash_bytes(source_bytes: bytes) -> str:
        return sha256(source_bytes).hexdigest()
