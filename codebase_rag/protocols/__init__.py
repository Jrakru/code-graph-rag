from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Protocol, runtime_checkable

type PathLike = str | Path
type ParseRecord = dict[str, object]


class SourceType(StrEnum):
    CODE = "code"
    DOCUMENTATION = "documentation"
    TEST = "test"
    CONFIG = "config"
    UNKNOWN = "unknown"


@runtime_checkable
class FileClassifierProtocol(Protocol):
    def classify(self, path: PathLike) -> SourceType: ...


@runtime_checkable
class ProvenanceTrackerProtocol(Protocol):
    def record_parse(self, path: PathLike) -> ParseRecord: ...

    def is_stale(self, path: PathLike, file_hash: str) -> bool: ...


@runtime_checkable
class ConfidenceScorerProtocol(Protocol):
    def score(self, method: str, ambiguity_count: int) -> float: ...


@runtime_checkable
class ValidationEngineProtocol(Protocol):
    def validate_relationship(self) -> object: ...

    def report_orphans(self) -> object: ...


__all__ = [
    "ConfidenceScorerProtocol",
    "FileClassifierProtocol",
    "ParseRecord",
    "PathLike",
    "ProvenanceTrackerProtocol",
    "SourceType",
    "ValidationEngineProtocol",
]
