from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable

from .. import constants as cs


_GLOB_CHARS = set("*?[")


@dataclass(frozen=True)
class IgnoreSpec:
    parts: frozenset[str]
    globs: tuple[str, ...]

    def matches(self, path: Path, repo_root: Path) -> bool:
        try:
            rel_path = path.relative_to(repo_root)
        except ValueError:
            rel_path = path

        rel_parts = rel_path.parts
        if any(part in self.parts for part in rel_parts):
            return True

        if not self.globs:
            return False

        rel_str = rel_path.as_posix()
        for pattern in self.globs:
            if fnmatch(rel_str, pattern):
                return True
            for part in rel_parts:
                if fnmatch(part, pattern):
                    return True

        return False


def build_ignore_spec(repo_root: Path, base_parts: Iterable[str]) -> IgnoreSpec:
    ignore_parts = set(base_parts)
    ignore_globs: list[str] = []

    for pattern in _load_ignore_file(repo_root, cs.GRAPHRAG_IGNORE_FILENAME):
        if _is_simple_part(pattern):
            ignore_parts.add(pattern)
        else:
            ignore_globs.append(pattern)

    return IgnoreSpec(parts=frozenset(ignore_parts), globs=tuple(ignore_globs))


def _load_ignore_file(repo_root: Path, filename: str) -> list[str]:
    ignore_file = repo_root / filename
    if not ignore_file.exists():
        return []

    patterns: list[str] = []
    for raw_line in ignore_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("!"):
            continue
        line = line.removeprefix("./")
        if line.endswith("/") and len(line) > 1:
            line = line[:-1]
        if line:
            patterns.append(line)

    return patterns


def _is_simple_part(pattern: str) -> bool:
    if "/" in pattern:
        return False
    return not _GLOB_CHARS.intersection(pattern)
