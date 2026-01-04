from __future__ import annotations

from pathlib import Path

from .. import constants as cs
from ..protocols import FileClassifierProtocol, PathLike, SourceType

_DOC_EXTENSIONS = frozenset({".md", ".rst", ".txt"})
_CONFIG_EXTENSIONS = frozenset(
    {".yml", ".yaml", ".json", ".toml", ".ini", ".cfg", ".conf", ".env"}
)
_DOC_NAME_HINTS = ("readme", "changelog", "license", "copying", "notice")
_DOC_DIR_HINTS = {"doc", "docs", "documentation"}
_TEST_DIR_HINTS = {"test", "tests", "__tests__", "spec", "specs"}

_CODE_EXTENSIONS = frozenset(
    {
        *cs.PY_EXTENSIONS,
        *cs.JS_EXTENSIONS,
        *cs.TS_EXTENSIONS,
        *cs.RS_EXTENSIONS,
        *cs.GO_EXTENSIONS,
        *cs.SCALA_EXTENSIONS,
        *cs.JAVA_EXTENSIONS,
        *cs.CPP_EXTENSIONS,
        *cs.CS_EXTENSIONS,
        *cs.PHP_EXTENSIONS,
        *cs.LUA_EXTENSIONS,
    }
)


class FileClassifier(FileClassifierProtocol):
    def classify(self, path: PathLike) -> SourceType:
        path_obj = Path(path)
        name = path_obj.name.lower()
        parts = {part.lower() for part in path_obj.parts}
        suffix = path_obj.suffix.lower()

        if parts & _TEST_DIR_HINTS:
            return SourceType.TEST

        if name.startswith("test_"):
            return SourceType.TEST

        if name.endswith("_test" + suffix) or ".test." in name:
            return SourceType.TEST

        if name.endswith("_spec" + suffix) or ".spec." in name:
            return SourceType.TEST

        if suffix in _DOC_EXTENSIONS or parts & _DOC_DIR_HINTS:
            return SourceType.DOCUMENTATION

        if any(name.startswith(hint) for hint in _DOC_NAME_HINTS):
            return SourceType.DOCUMENTATION

        if suffix in _CONFIG_EXTENSIONS or name == ".env" or name.endswith(".env"):
            return SourceType.CONFIG

        if suffix in _CODE_EXTENSIONS:
            return SourceType.CODE

        return SourceType.UNKNOWN
