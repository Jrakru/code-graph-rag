from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from ..protocols import ParseRecord, PathLike, ProvenanceTrackerProtocol

_HASH_BUFFER_SIZE = 8192


class ProvenanceTracker(ProvenanceTrackerProtocol):
    def __init__(self) -> None:
        self._records: dict[str, ParseRecord] = {}

    def record_parse(self, path: PathLike) -> ParseRecord:
        path_obj = Path(path)
        file_hash = self._hash_file(path_obj)
        record: ParseRecord = {
            "path": str(path_obj),
            "parsed_at": datetime.now(UTC).isoformat(),
            "hash": file_hash,
        }
        self._records[str(path_obj)] = record
        return record

    def is_stale(self, path: PathLike, file_hash: str) -> bool:
        record = self._records.get(str(Path(path)))
        if not record:
            return True
        stored_hash = record.get("hash")
        return stored_hash != file_hash

    def _hash_file(self, path: Path) -> str:
        try:
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(_HASH_BUFFER_SIZE), b""):
                    digest.update(chunk)
            return digest.hexdigest()
        except FileNotFoundError:
            return ""
