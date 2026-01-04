from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .. import constants as cs
from .provenance_tracker import ProvenanceTracker


@dataclass(frozen=True)
class StalenessReport:
    """Summary of stale file detection for a repository scan.

    Attributes:
        stale_paths: Sorted list of stale file paths relative to the repo root.
        total_files: Total number of files scanned.
        stale_count: Number of files considered stale.
        stale_percentage: Percent of scanned files that are stale.
    """

    stale_paths: list[str]
    total_files: int
    stale_count: int
    stale_percentage: float


def normalize_extensions(extensions: Iterable[str] | None) -> set[str]:
    """Normalize extension filters to lowercase dot-prefixed values.

    Args:
        extensions: Iterable of extensions like ".py" or "py". Comma-separated
            values are supported in each entry.

    Returns:
        A set of normalized, lowercase extensions prefixed with a dot.
    """
    if not extensions:
        return set()
    normalized: set[str] = set()
    for raw_ext in extensions:
        for part in str(raw_ext).split(","):
            ext = part.strip()
            if not ext:
                continue
            if not ext.startswith("."):
                ext = f".{ext}"
            normalized.add(ext.lower())
    return normalized


def compile_path_pattern(pattern: str | None) -> re.Pattern[str] | None:
    """Compile a regex pattern for path filtering.

    Args:
        pattern: Regex pattern to compile. None returns no filter.

    Returns:
        Compiled regex pattern or None.

    Raises:
        ValueError: If the provided regex pattern is invalid.
    """
    if not pattern:
        return None
    try:
        return re.compile(pattern)
    except re.error as exc:
        raise ValueError(f"Invalid path pattern: {pattern}") from exc


def compute_file_hash(path: Path, chunk_size: int = 8192) -> str | None:
    """Compute a SHA-256 hash for the given file path.

    Args:
        path: Path to the file.
        chunk_size: Read chunk size in bytes.

    Returns:
        Hex digest string, or None when the file cannot be read.
    """
    try:
        hasher = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(chunk_size), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except OSError:
        return None


class StalenessChecker:
    """Scan a repository and report which files are stale in the graph."""

    def __init__(
        self,
        tracker: ProvenanceTracker,
        repo_root: Path,
        ignore_patterns: Iterable[str] | None = None,
        ignore_suffixes: Iterable[str] | None = None,
    ) -> None:
        self.tracker = tracker
        self.repo_root = repo_root.resolve()
        self.ignore_patterns = set(ignore_patterns or cs.IGNORE_PATTERNS)
        self.ignore_suffixes = set(ignore_suffixes or cs.IGNORE_SUFFIXES)

    def scan(
        self,
        extensions: Iterable[str] | None = None,
        path_pattern: str | None = None,
    ) -> StalenessReport:
        """Scan files in the repo and compare current hashes to stored graph hashes.

        Args:
            extensions: Optional list of file extensions to include.
            path_pattern: Optional regex pattern to match relative paths.

        Returns:
            A StalenessReport with counts and stale file paths.

        Raises:
            ValueError: If the provided path pattern is an invalid regex.
        """
        normalized_extensions = normalize_extensions(extensions)
        compiled_pattern = compile_path_pattern(path_pattern)

        file_hashes: dict[Path, str | None] = {}
        for path in self._iter_files(normalized_extensions, compiled_pattern):
            file_hashes[path] = compute_file_hash(path)

        results = self.tracker.is_stale_batch(file_hashes)
        stale_paths = sorted(path for path, is_stale in results.items() if is_stale)
        total_files = len(file_hashes)
        stale_count = len(stale_paths)
        percentage = (stale_count / total_files * 100) if total_files else 0.0

        return StalenessReport(
            stale_paths=stale_paths,
            total_files=total_files,
            stale_count=stale_count,
            stale_percentage=percentage,
        )

    def _iter_files(
        self,
        extensions: set[str],
        path_pattern: re.Pattern[str] | None,
    ) -> Iterable[Path]:
        for root, dirs, files in os.walk(self.repo_root):
            root_path = Path(root)
            rel_root = root_path.relative_to(self.repo_root)

            dirs[:] = [
                dirname for dirname in dirs if dirname not in self.ignore_patterns
            ]

            if any(part in self.ignore_patterns for part in rel_root.parts):
                continue

            for filename in files:
                if any(filename.endswith(suffix) for suffix in self.ignore_suffixes):
                    continue

                path = root_path / filename
                rel_path = path.relative_to(self.repo_root)
                rel_str = rel_path.as_posix()

                if extensions and path.suffix.lower() not in extensions:
                    continue
                if path_pattern and not path_pattern.search(rel_str):
                    continue

                yield path
