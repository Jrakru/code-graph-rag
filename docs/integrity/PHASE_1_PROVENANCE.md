# Phase 1: Data Provenance Implementation

## Overview

**Duration:** Week 1-2  
**Status:** 🔄 Not Started  
**Goal:** Add source type classification and provenance metadata to all indexed content.

---

## Problem Statement

Code-Graph-RAG currently treats all indexed files identically. A README.md file has the same authority as main.py, leading to:

1. **Stale documentation** returned as current truth
2. **No way to filter** queries by content type
3. **No audit trail** for when data was indexed

---

## Deliverables

| Deliverable | Description | Priority |
|-------------|-------------|----------|
| `FileClassifier` | Classify files by extension/path patterns | P0 |
| `ProvenanceTracker` | Track parse timestamps and file mtimes | P0 |
| Schema extensions | Add provenance fields to File nodes | P0 |
| Query filtering | Enable filtering by source_type | P1 |

---

## TDD Workflow

### Red-Green-Refactor Cycle

```
┌─────────────────────────────────────────────────────────────────┐
│                     TDD CYCLE                                    │
│                                                                  │
│  ┌─────────┐     ┌─────────┐     ┌─────────┐                   │
│  │  RED    │ --> │  GREEN  │ --> │ REFACTOR│ --> [repeat]      │
│  │         │     │         │     │         │                    │
│  │ Write   │     │ Write   │     │ Improve │                    │
│  │ failing │     │ minimal │     │ code    │                    │
│  │ test    │     │ code    │     │ quality │                    │
│  └─────────┘     └─────────┘     └─────────┘                    │
│                                                                  │
│  Tests MUST fail first. No implementation without a test.       │
└─────────────────────────────────────────────────────────────────┘
```

---

## Week 1: FileClassifier

### Day 1: Write FileClassifier Tests

**File:** `codebase_rag/tests/test_file_classifier.py`

```python
"""Tests for FileClassifier - TDD Red Phase."""
from pathlib import Path

import pytest

from codebase_rag.services.file_classifier import FileClassifier, SourceType


class TestFileClassifierDocumentation:
    """Test documentation file classification."""

    @pytest.fixture
    def classifier(self) -> FileClassifier:
        return FileClassifier()

    @pytest.mark.parametrize(
        "path,expected",
        [
            ("README.md", SourceType.DOCUMENTATION),
            ("docs/guide.md", SourceType.DOCUMENTATION),
            ("CHANGELOG.rst", SourceType.DOCUMENTATION),
            ("doc/api.txt", SourceType.DOCUMENTATION),
            ("documentation/index.adoc", SourceType.DOCUMENTATION),
        ],
    )
    def test_classifies_documentation_files(
        self, classifier: FileClassifier, path: str, expected: SourceType
    ) -> None:
        """Documentation files should be classified as DOCUMENTATION."""
        assert classifier.classify(Path(path)) == expected

    def test_readme_variants(self, classifier: FileClassifier) -> None:
        """All README variants should be documentation."""
        variants = ["README.md", "README.rst", "README.txt", "readme.md"]
        for variant in variants:
            assert classifier.classify(Path(variant)) == SourceType.DOCUMENTATION


class TestFileClassifierTests:
    """Test test file classification."""

    @pytest.fixture
    def classifier(self) -> FileClassifier:
        return FileClassifier()

    @pytest.mark.parametrize(
        "path,expected",
        [
            ("test_main.py", SourceType.TEST),
            ("tests/test_utils.py", SourceType.TEST),
            ("main_test.py", SourceType.TEST),
            ("src/__tests__/util.test.ts", SourceType.TEST),
            ("spec/main.spec.js", SourceType.TEST),
        ],
    )
    def test_classifies_test_files(
        self, classifier: FileClassifier, path: str, expected: SourceType
    ) -> None:
        """Test files should be classified as TEST."""
        assert classifier.classify(Path(path)) == expected


class TestFileClassifierConfig:
    """Test config file classification."""

    @pytest.fixture
    def classifier(self) -> FileClassifier:
        return FileClassifier()

    @pytest.mark.parametrize(
        "path,expected",
        [
            ("pyproject.toml", SourceType.CONFIG),
            ("package.json", SourceType.CONFIG),
            ("tsconfig.json", SourceType.CONFIG),
            (".gitignore", SourceType.CONFIG),
            ("docker-compose.yaml", SourceType.CONFIG),
            ("settings.ini", SourceType.CONFIG),
        ],
    )
    def test_classifies_config_files(
        self, classifier: FileClassifier, path: str, expected: SourceType
    ) -> None:
        """Config files should be classified as CONFIG."""
        assert classifier.classify(Path(path)) == expected


class TestFileClassifierCode:
    """Test source code classification."""

    @pytest.fixture
    def classifier(self) -> FileClassifier:
        return FileClassifier()

    @pytest.mark.parametrize(
        "path,expected",
        [
            ("main.py", SourceType.CODE),
            ("src/utils.ts", SourceType.CODE),
            ("lib/parser.rs", SourceType.CODE),
            ("app/models/user.java", SourceType.CODE),
        ],
    )
    def test_classifies_code_files(
        self, classifier: FileClassifier, path: str, expected: SourceType
    ) -> None:
        """Source code files should be classified as CODE."""
        assert classifier.classify(Path(path)) == expected


class TestFileClassifierHelpers:
    """Test helper methods."""

    @pytest.fixture
    def classifier(self) -> FileClassifier:
        return FileClassifier()

    def test_is_documentation_true(self, classifier: FileClassifier) -> None:
        """is_documentation should return True for doc files."""
        assert classifier.is_documentation(Path("README.md")) is True

    def test_is_documentation_false(self, classifier: FileClassifier) -> None:
        """is_documentation should return False for code files."""
        assert classifier.is_documentation(Path("main.py")) is False
```

### Day 2: Implement FileClassifier

**File:** `codebase_rag/services/file_classifier.py`

```python
"""File classification by source type."""
from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import ClassVar


class SourceType(StrEnum):
    """Classification of source files."""

    CODE = "code"
    DOCUMENTATION = "documentation"
    TEST = "test"
    CONFIG = "config"


class FileClassifier:
    """Classifies files by source type based on extension and path patterns."""

    DOC_EXTENSIONS: ClassVar[frozenset[str]] = frozenset(
        {".md", ".rst", ".txt", ".adoc", ".asciidoc"}
    )

    DOC_PATTERNS: ClassVar[tuple[str, ...]] = (
        "README",
        "CHANGELOG",
        "LICENSE",
        "CONTRIBUTING",
        "docs/",
        "documentation/",
        "doc/",
    )

    TEST_PATTERNS: ClassVar[tuple[str, ...]] = (
        "test_",
        "_test.",
        ".test.",
        "tests/",
        "__tests__/",
        "spec/",
        ".spec.",
    )

    CONFIG_EXTENSIONS: ClassVar[frozenset[str]] = frozenset(
        {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf"}
    )

    CONFIG_NAMES: ClassVar[frozenset[str]] = frozenset(
        {
            "pyproject.toml",
            "setup.py",
            "setup.cfg",
            "package.json",
            "tsconfig.json",
            "cargo.toml",
            ".gitignore",
            ".env",
            "Makefile",
            "Dockerfile",
            "docker-compose.yaml",
            "docker-compose.yml",
        }
    )

    def classify(self, path: Path) -> SourceType:
        """Classify a file path into a source type.

        Args:
            path: Path to the file (can be relative or absolute)

        Returns:
            SourceType indicating the file's classification
        """
        name = path.name
        suffix = path.suffix.lower()
        path_str = str(path)

        # Check documentation first (highest priority for docs)
        if self._is_doc_file(name, suffix, path_str):
            return SourceType.DOCUMENTATION

        # Check test files
        if self._is_test_file(path_str):
            return SourceType.TEST

        # Check config files
        if self._is_config_file(name, suffix):
            return SourceType.CONFIG

        # Default to code
        return SourceType.CODE

    def is_documentation(self, path: Path) -> bool:
        """Quick check if file is documentation.

        Args:
            path: Path to check

        Returns:
            True if the file is documentation
        """
        return self.classify(path) == SourceType.DOCUMENTATION

    def _is_doc_file(self, name: str, suffix: str, path_str: str) -> bool:
        """Check if file is documentation."""
        if suffix in self.DOC_EXTENSIONS:
            return True
        return any(pattern in path_str or pattern in name.upper() 
                   for pattern in self.DOC_PATTERNS)

    def _is_test_file(self, path_str: str) -> bool:
        """Check if file is a test file."""
        return any(pattern in path_str for pattern in self.TEST_PATTERNS)

    def _is_config_file(self, name: str, suffix: str) -> bool:
        """Check if file is a config file."""
        if name in self.CONFIG_NAMES:
            return True
        return suffix in self.CONFIG_EXTENSIONS
```

### Day 3-4: Integrate with StructureProcessor

**Modify:** `codebase_rag/parsers/structure_processor.py`

Add FileClassifier integration to inject `source_type` when creating File nodes.

### Day 5: Verify Integration

Run full test suite and verify:
- [ ] All File nodes have `source_type`
- [ ] Classification accuracy > 95%
- [ ] No regressions in existing tests

---

## Week 2: ProvenanceTracker

### Day 1: Write ProvenanceTracker Tests

**File:** `codebase_rag/tests/test_provenance_tracker.py`

```python
"""Tests for ProvenanceTracker - TDD Red Phase."""
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from codebase_rag.services.provenance_tracker import ProvenanceTracker


class TestProvenanceTrackerRecordParse:
    """Test parse recording functionality."""

    @pytest.fixture
    def tracker(self) -> ProvenanceTracker:
        return ProvenanceTracker()

    def test_record_parse_includes_parsed_at(self, tracker: ProvenanceTracker) -> None:
        """Recorded metadata should include parsed_at timestamp."""
        with patch("codebase_rag.services.provenance_tracker.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 1, 3, 12, 0, 0, tzinfo=timezone.utc)
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            
            metadata = tracker.record_parse(Path("test.py"))
            
            assert "parsed_at" in metadata
            assert metadata["parsed_at"] == "2026-01-03T12:00:00+00:00"

    def test_record_parse_includes_file_mtime(
        self, tracker: ProvenanceTracker, tmp_path: Path
    ) -> None:
        """Recorded metadata should include file modification time."""
        test_file = tmp_path / "test.py"
        test_file.write_text("# test")
        
        metadata = tracker.record_parse(test_file)
        
        assert "file_mtime" in metadata
        assert isinstance(metadata["file_mtime"], float)

    def test_record_parse_includes_file_hash(
        self, tracker: ProvenanceTracker, tmp_path: Path
    ) -> None:
        """Recorded metadata should include content hash."""
        test_file = tmp_path / "test.py"
        test_file.write_text("# test content")
        
        metadata = tracker.record_parse(test_file)
        
        assert "file_hash" in metadata
        assert len(metadata["file_hash"]) == 64  # SHA256 hex length


class TestProvenanceTrackerStaleness:
    """Test staleness detection."""

    @pytest.fixture
    def tracker(self) -> ProvenanceTracker:
        return ProvenanceTracker()

    def test_detect_staleness_unchanged_file(
        self, tracker: ProvenanceTracker, tmp_path: Path
    ) -> None:
        """Unchanged files should not be stale."""
        test_file = tmp_path / "test.py"
        test_file.write_text("# original")
        
        metadata = tracker.record_parse(test_file)
        
        is_stale = tracker.is_stale(test_file, metadata["file_hash"])
        assert is_stale is False

    def test_detect_staleness_changed_file(
        self, tracker: ProvenanceTracker, tmp_path: Path
    ) -> None:
        """Changed files should be detected as stale."""
        test_file = tmp_path / "test.py"
        test_file.write_text("# original")
        
        metadata = tracker.record_parse(test_file)
        original_hash = metadata["file_hash"]
        
        # Modify file
        test_file.write_text("# modified content")
        
        is_stale = tracker.is_stale(test_file, original_hash)
        assert is_stale is True
```

### Day 2: Implement ProvenanceTracker

**File:** `codebase_rag/services/provenance_tracker.py`

```python
"""Provenance tracking for indexed files."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ProvenanceTracker:
    """Tracks provenance metadata for parsed files."""

    def record_parse(self, path: Path) -> dict[str, Any]:
        """Record provenance metadata for a parsed file.

        Args:
            path: Path to the file being parsed

        Returns:
            Dictionary with provenance metadata:
            - parsed_at: ISO 8601 timestamp
            - file_mtime: Unix timestamp of file modification
            - file_hash: SHA256 hash of file contents
        """
        metadata: dict[str, Any] = {
            "parsed_at": datetime.now(timezone.utc).isoformat(),
        }

        if path.exists():
            stat = path.stat()
            metadata["file_mtime"] = stat.st_mtime

            content = path.read_bytes()
            metadata["file_hash"] = hashlib.sha256(content).hexdigest()

        return metadata

    def is_stale(self, path: Path, stored_hash: str) -> bool:
        """Check if a file has changed since it was indexed.

        Args:
            path: Path to check
            stored_hash: Previously recorded hash

        Returns:
            True if file content has changed
        """
        if not path.exists():
            return True

        current_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        return current_hash != stored_hash
```

### Day 3: Update Schema Definitions

**Modify:** `codebase_rag/types_defs.py`

```python
# Update FILE schema
NodeSchema(
    NodeLabel.FILE,
    """{
        path: string,
        name: string,
        extension: string,
        source_type: string,
        parsed_at: string,
        file_mtime: float,
        file_hash: string
    }"""
)
```

### Day 4: Add Query Filtering

**Add Cypher query support:**

```cypher
-- Filter by source type
MATCH (f:File {source_type: "code"})
RETURN f.path, f.name

-- Exclude documentation
MATCH (m:Module)-[:DEFINES]->(fn:Function)
MATCH (m)-[:CONTAINED_BY]->(f:File)
WHERE f.source_type <> "documentation"
RETURN fn.qualified_name
```

### Day 5: End-to-End Verification

- [ ] Run full indexing on test repository
- [ ] Verify all File nodes have provenance fields
- [ ] Test query filtering works
- [ ] Verify staleness detection

---

## Verification Gates

### Must Pass Before Phase 2

| Gate | Criteria | Status |
|------|----------|--------|
| Unit Tests | All FileClassifier tests pass | ⬜ |
| Unit Tests | All ProvenanceTracker tests pass | ⬜ |
| Integration | StructureProcessor creates provenance | ⬜ |
| Coverage | > 90% on new code | ⬜ |
| Types | pyright clean on new code | ⬜ |

### Acceptance Tests

```python
def test_end_to_end_provenance():
    """Full indexing should create provenance metadata."""
    # Given a repository with mixed file types
    # When indexed
    # Then all File nodes have source_type
    # And all File nodes have parsed_at
    # And all File nodes have file_hash
```

---

## Files to Create/Modify

### New Files

| File | Purpose |
|------|---------|
| `codebase_rag/services/file_classifier.py` | File classification |
| `codebase_rag/services/provenance_tracker.py` | Provenance tracking |
| `codebase_rag/tests/test_file_classifier.py` | FileClassifier tests |
| `codebase_rag/tests/test_provenance_tracker.py` | ProvenanceTracker tests |

### Modified Files

| File | Changes |
|------|---------|
| `codebase_rag/types_defs.py` | Add provenance fields to FILE schema |
| `codebase_rag/parsers/structure_processor.py` | Integrate FileClassifier |
| `codebase_rag/parsers/definition_processor.py` | Add provenance to nodes |

---

## Rollback Plan

If Phase 1 causes issues:

1. **Schema fields are additive** - old graphs still work
2. **FileClassifier is optional** - can disable classification
3. **ProvenanceTracker is optional** - can skip provenance

No destructive changes. All additions have safe defaults.

---

**Phase Status:** 🔄 Not Started  
**Last Updated:** 2026-01-03
