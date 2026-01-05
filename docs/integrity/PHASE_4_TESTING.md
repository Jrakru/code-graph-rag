# Phase 4: Testing & Integration

## Overview

**Duration:** Week 5  
**Status:** 🔄 Not Started  
**Goal:** Comprehensive test coverage and SOLID principle verification.

---

## Deliverables

| Deliverable | Description | Priority |
|-------------|-------------|----------|
| Unit tests | > 90% coverage on new code | P0 |
| Integration tests | End-to-end validation | P0 |
| Property-based tests | Edge case coverage | P1 |
| Performance benchmarks | Regression prevention | P1 |

---

## Test Structure

### Directory Layout

```
codebase_rag/tests/
├── unit/
│   ├── test_file_classifier.py
│   ├── test_provenance_tracker.py
│   ├── test_confidence_scorer.py
│   ├── test_validation_engine.py
│   └── test_pydantic_models.py
├── integration/
│   ├── test_provenance_pipeline.py
│   ├── test_validation_pipeline.py
│   └── test_full_indexing.py
├── property/
│   ├── test_file_classifier_properties.py
│   └── test_confidence_scorer_properties.py
└── benchmarks/
    ├── bench_indexing.py
    └── bench_validation.py
```

---

## Unit Tests

### FileClassifier Tests

**File:** `codebase_rag/tests/unit/test_file_classifier.py`

```python
"""Unit tests for FileClassifier."""
from pathlib import Path

import pytest

from codebase_rag.services.file_classifier import FileClassifier, SourceType


class TestDocumentationClassification:
    """Test documentation file classification."""

    @pytest.fixture
    def classifier(self) -> FileClassifier:
        return FileClassifier()

    @pytest.mark.parametrize(
        "path,expected",
        [
            ("README.md", SourceType.DOCUMENTATION),
            ("readme.rst", SourceType.DOCUMENTATION),
            ("CHANGELOG.md", SourceType.DOCUMENTATION),
            ("docs/guide.md", SourceType.DOCUMENTATION),
            ("documentation/api.txt", SourceType.DOCUMENTATION),
        ],
    )
    def test_classifies_documentation(
        self, classifier: FileClassifier, path: str, expected: SourceType
    ) -> None:
        """Documentation files should be classified correctly."""
        assert classifier.classify(Path(path)) == expected


class TestTestClassification:
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
            ("__tests__/util.test.ts", SourceType.TEST),
            ("spec/main.spec.js", SourceType.TEST),
        ],
    )
    def test_classifies_tests(
        self, classifier: FileClassifier, path: str, expected: SourceType
    ) -> None:
        """Test files should be classified correctly."""
        assert classifier.classify(Path(path)) == expected


class TestConfigClassification:
    """Test config file classification."""

    @pytest.fixture
    def classifier(self) -> FileClassifier:
        return FileClassifier()

    @pytest.mark.parametrize(
        "path,expected",
        [
            ("pyproject.toml", SourceType.CONFIG),
            ("package.json", SourceType.CONFIG),
            (".gitignore", SourceType.CONFIG),
            ("docker-compose.yaml", SourceType.CONFIG),
        ],
    )
    def test_classifies_config(
        self, classifier: FileClassifier, path: str, expected: SourceType
    ) -> None:
        """Config files should be classified correctly."""
        assert classifier.classify(Path(path)) == expected


class TestCodeClassification:
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
    def test_classifies_code(
        self, classifier: FileClassifier, path: str, expected: SourceType
    ) -> None:
        """Source files should be classified as CODE."""
        assert classifier.classify(Path(path)) == expected
```

### Pydantic Model Tests

**File:** `codebase_rag/tests/unit/test_pydantic_models.py`

```python
"""Unit tests for Pydantic models."""
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from codebase_rag.models.nodes import FileNode, FunctionNode
from codebase_rag.models.relationships import CallsRelationship
from codebase_rag.services.confidence_scorer import ResolutionMethod
from codebase_rag.services.file_classifier import SourceType


class TestFileNode:
    """Test FileNode validation."""

    def test_valid_file_node(self) -> None:
        """Valid data should create a FileNode."""
        node = FileNode(
            path="/src/main.py",
            name="main.py",
            extension=".py",
            source_type=SourceType.CODE,
            parsed_at=datetime.now(timezone.utc),
            file_mtime=1234567890.0,
            file_hash="a" * 64,
        )
        assert node.path == "/src/main.py"

    def test_empty_path_rejected(self) -> None:
        """Empty path should be rejected."""
        with pytest.raises(ValidationError) as exc:
            FileNode(
                path="",
                name="main.py",
                extension=".py",
                source_type=SourceType.CODE,
                parsed_at=datetime.now(timezone.utc),
                file_mtime=1234567890.0,
                file_hash="a" * 64,
            )
        assert "path cannot be empty" in str(exc.value)

    def test_invalid_hash_rejected(self) -> None:
        """Invalid hash should be rejected."""
        with pytest.raises(ValidationError) as exc:
            FileNode(
                path="/src/main.py",
                name="main.py",
                extension=".py",
                source_type=SourceType.CODE,
                parsed_at=datetime.now(timezone.utc),
                file_mtime=1234567890.0,
                file_hash="invalid_hash",
            )
        assert "file_hash" in str(exc.value)

    def test_immutable(self) -> None:
        """FileNode should be immutable."""
        node = FileNode(
            path="/src/main.py",
            name="main.py",
            extension=".py",
            source_type=SourceType.CODE,
            parsed_at=datetime.now(timezone.utc),
            file_mtime=1234567890.0,
            file_hash="a" * 64,
        )
        with pytest.raises(ValidationError):
            node.path = "/other.py"  # type: ignore


class TestCallsRelationship:
    """Test CallsRelationship validation."""

    def test_valid_relationship(self) -> None:
        """Valid data should create a CallsRelationship."""
        rel = CallsRelationship(
            confidence=0.95,
            resolution_method=ResolutionMethod.DIRECT_IMPORT,
        )
        assert rel.confidence == 0.95

    def test_confidence_range(self) -> None:
        """Confidence must be 0.0-1.0."""
        with pytest.raises(ValidationError):
            CallsRelationship(
                confidence=1.5,  # Invalid!
                resolution_method=ResolutionMethod.DIRECT_IMPORT,
            )

    def test_negative_confidence_rejected(self) -> None:
        """Negative confidence should be rejected."""
        with pytest.raises(ValidationError):
            CallsRelationship(
                confidence=-0.1,
                resolution_method=ResolutionMethod.DIRECT_IMPORT,
            )
```

---

## Integration Tests

### Full Indexing Pipeline

**File:** `codebase_rag/tests/integration/test_full_indexing.py`

```python
"""Integration tests for full indexing pipeline."""
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from codebase_rag.graph_updater import GraphUpdater
from codebase_rag.services.file_classifier import SourceType


class TestFullIndexingWithProvenance:
    """Test full indexing with provenance tracking."""

    @pytest.fixture
    def temp_repo(self, tmp_path: Path) -> Path:
        """Create a temporary repository structure."""
        # Create source files
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.py").write_text("def main(): pass")
        (src / "utils.py").write_text("def helper(): pass")
        
        # Create documentation
        (tmp_path / "README.md").write_text("# Project")
        
        # Create tests
        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_main.py").write_text("def test_main(): pass")
        
        # Create config
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")
        
        return tmp_path

    def test_indexing_creates_provenance(
        self, temp_repo: Path, mock_graph_service: MagicMock
    ) -> None:
        """Indexing should create provenance metadata on all files."""
        updater = GraphUpdater(temp_repo, mock_graph_service)
        updater.update_graph()
        
        # Verify File nodes were created with source_type
        file_calls = [
            call for call in mock_graph_service.ensure_node_batch.call_args_list
            if call[0][0] == "File"
        ]
        
        for call in file_calls:
            props = call[0][2]
            assert "source_type" in props
            assert "parsed_at" in props
            assert "file_hash" in props

    def test_source_type_classification(
        self, temp_repo: Path, mock_graph_service: MagicMock
    ) -> None:
        """Files should be classified correctly by type."""
        updater = GraphUpdater(temp_repo, mock_graph_service)
        updater.update_graph()
        
        # Collect all File node creations
        file_nodes = {}
        for call in mock_graph_service.ensure_node_batch.call_args_list:
            if call[0][0] == "File":
                path = call[0][2]["path"]
                source_type = call[0][2]["source_type"]
                file_nodes[path] = source_type
        
        # Verify classifications
        assert file_nodes.get("src/main.py") == SourceType.CODE
        assert file_nodes.get("README.md") == SourceType.DOCUMENTATION
        assert file_nodes.get("tests/test_main.py") == SourceType.TEST
        assert file_nodes.get("pyproject.toml") == SourceType.CONFIG
```

### Validation Pipeline

**File:** `codebase_rag/tests/integration/test_validation_pipeline.py`

```python
"""Integration tests for validation pipeline."""
import pytest

from codebase_rag.services.confidence_scorer import ConfidenceScorer, ResolutionMethod
from codebase_rag.services.validation_engine import ValidationEngine


class TestValidationIntegration:
    """Test validation integration."""

    def test_confidence_scoring_in_pipeline(self) -> None:
        """Confidence should be calculated during call resolution."""
        scorer = ConfidenceScorer()
        
        # Simulate resolution results
        results = [
            (ResolutionMethod.DIRECT_IMPORT, 1),
            (ResolutionMethod.TRIE_FALLBACK, 5),
            (ResolutionMethod.TYPE_INFERENCE, 1),
        ]
        
        scores = [
            scorer.score(method, ambiguity)
            for method, ambiguity in results
        ]
        
        # Direct import should have highest confidence
        assert scores[0] == 1.0
        # Trie fallback with ambiguity should have lower confidence
        assert scores[1] < 0.5
        # Type inference should be high
        assert scores[2] == 0.9
```

---

## Property-Based Tests

### FileClassifier Properties

**File:** `codebase_rag/tests/property/test_file_classifier_properties.py`

```python
"""Property-based tests for FileClassifier."""
from pathlib import Path

from hypothesis import given, strategies as st

from codebase_rag.services.file_classifier import FileClassifier, SourceType


class TestFileClassifierProperties:
    """Property-based tests for FileClassifier."""

    @given(st.text(min_size=1, max_size=50).filter(lambda x: "/" not in x))
    def test_always_returns_valid_source_type(self, filename: str) -> None:
        """Classifier should always return a valid SourceType."""
        classifier = FileClassifier()
        result = classifier.classify(Path(filename))
        assert result in list(SourceType)

    @given(st.sampled_from([".md", ".rst", ".txt"]))
    def test_doc_extensions_always_classified_as_docs(self, ext: str) -> None:
        """Known doc extensions should always be DOCUMENTATION."""
        classifier = FileClassifier()
        result = classifier.classify(Path(f"file{ext}"))
        assert result == SourceType.DOCUMENTATION

    @given(st.sampled_from(["test_", "_test.", ".test."]))
    def test_test_patterns_always_classified_as_tests(self, pattern: str) -> None:
        """Known test patterns should always be TEST."""
        classifier = FileClassifier()
        if pattern.startswith("test_"):
            result = classifier.classify(Path(f"{pattern}main.py"))
        else:
            result = classifier.classify(Path(f"main{pattern}py"))
        assert result == SourceType.TEST


class TestConfidenceScorerProperties:
    """Property-based tests for ConfidenceScorer."""

    @given(st.integers(min_value=1, max_value=100))
    def test_confidence_always_in_range(self, ambiguity: int) -> None:
        """Confidence should always be between 0 and 1."""
        from codebase_rag.services.confidence_scorer import (
            ConfidenceScorer,
            ResolutionMethod,
        )
        
        scorer = ConfidenceScorer()
        score = scorer.score(ResolutionMethod.TRIE_FALLBACK, ambiguity)
        assert 0.0 <= score <= 1.0

    @given(st.integers(min_value=1, max_value=1000))
    def test_more_ambiguity_lower_confidence(self, ambiguity: int) -> None:
        """More ambiguity should mean lower or equal confidence."""
        from codebase_rag.services.confidence_scorer import (
            ConfidenceScorer,
            ResolutionMethod,
        )
        
        scorer = ConfidenceScorer()
        score_low = scorer.score(ResolutionMethod.TRIE_FALLBACK, 1)
        score_high = scorer.score(ResolutionMethod.TRIE_FALLBACK, ambiguity)
        assert score_high <= score_low
```

---

## Performance Benchmarks

### Indexing Benchmark

**File:** `codebase_rag/tests/benchmarks/bench_indexing.py`

```python
"""Performance benchmarks for indexing."""
from pathlib import Path

import pytest


@pytest.fixture
def large_repo(tmp_path: Path) -> Path:
    """Create a large test repository."""
    for i in range(100):
        module_dir = tmp_path / f"module_{i}"
        module_dir.mkdir()
        for j in range(10):
            (module_dir / f"file_{j}.py").write_text(
                f"def func_{j}(): pass\n" * 10
            )
    return tmp_path


def test_indexing_performance(large_repo: Path, benchmark) -> None:
    """Benchmark indexing performance."""
    from codebase_rag.graph_updater import GraphUpdater
    from unittest.mock import MagicMock
    
    mock_service = MagicMock()
    
    def run_indexing():
        updater = GraphUpdater(large_repo, mock_service)
        updater.update_graph()
    
    result = benchmark(run_indexing)
    
    # Assert performance constraints
    assert result.stats.mean < 30.0  # Should complete in under 30 seconds


def test_classification_performance(benchmark) -> None:
    """Benchmark file classification performance."""
    from codebase_rag.services.file_classifier import FileClassifier
    
    classifier = FileClassifier()
    paths = [Path(f"module_{i}/file_{j}.py") for i in range(100) for j in range(100)]
    
    def run_classification():
        for path in paths:
            classifier.classify(path)
    
    result = benchmark(run_classification)
    
    # 10,000 classifications should be fast
    assert result.stats.mean < 1.0  # Under 1 second
```

---

## Verification Gates

### Final Quality Gates

| Gate | Criteria | Status |
|------|----------|--------|
| Unit Tests | All pass | ⬜ |
| Integration Tests | All pass | ⬜ |
| Property Tests | All pass | ⬜ |
| Coverage | > 90% on new code | ⬜ |
| Type Check | pyright clean | ⬜ |
| Performance | < 5% regression | ⬜ |

### Coverage Requirements

```
# Run coverage report
pytest --cov=codebase_rag/services --cov=codebase_rag/models --cov=codebase_rag/protocols --cov-report=term-missing

# Required coverage
services/file_classifier.py    > 95%
services/provenance_tracker.py > 95%
services/confidence_scorer.py  > 95%
services/validation_engine.py  > 95%
models/nodes.py                > 90%
models/relationships.py        > 90%
protocols/                     > 90%
```

---

## Documentation Checklist

- [ ] All new classes have docstrings
- [ ] All public methods have docstrings
- [ ] Type hints on all functions
- [ ] README updated with new features
- [ ] Migration guide for existing users
- [ ] API documentation generated

---

**Phase Status:** 🔄 Not Started  
**Last Updated:** 2026-01-03
