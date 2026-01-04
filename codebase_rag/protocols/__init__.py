from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Protocol


class ProvenanceTrackerProtocol(Protocol):
    def is_stale(self, path: Path | str, file_hash: str | None) -> bool: ...

    def is_stale_batch(
        self,
        files: Mapping[Path | str, str | None]
        | Iterable[tuple[Path | str, str | None]],
    ) -> dict[str, bool]: ...
