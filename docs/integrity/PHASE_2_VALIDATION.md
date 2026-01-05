# Phase 2: Consistency Validation Implementation

## Overview

**Duration:** Week 3  
**Status:** 🔄 Not Started  
**Goal:** Implement relationship validation and confidence scoring for call resolutions.

---

## Problem Statement

The CallResolver uses multiple strategies to resolve function calls, but:

1. **No quality indicator** - Trie fallback resolutions appear identical to direct imports
2. **Silent failures** - Unresolved calls just don't create relationships
3. **No validation** - Relationships can point to non-existent targets

---

## Deliverables

| Deliverable | Description | Priority |
|-------------|-------------|----------|
| `ConfidenceScorer` | Score call resolution confidence | P0 |
| `ValidationEngine` | Verify relationship targets exist | P0 |
| `ConsistencyChecker` | Cross-validate imports/exports | P1 |
| Validation reports | Generate integrity reports | P1 |

---

## Resolution Methods & Confidence

### Current Resolution Priority (from `call_resolver.py`)

```python
def resolve_function_call(self, ...):
    # 1. IIFE resolution (high confidence)
    if result := self._try_resolve_iife(call_name, module_qn):
        return result

    # 2. Super call resolution (high confidence)
    if self._is_super_call(call_name):
        return self._resolve_super_call(call_name, class_context)

    # 3. Method chain resolution (medium confidence)
    if "." in call_name and self._is_method_chain(call_name):
        return self._resolve_chained_call(call_name, module_qn, local_var_types)

    # 4. Import-based resolution (high confidence)
    if result := self._try_resolve_via_imports(call_name, module_qn, local_var_types):
        return result

    # 5. Same module resolution (high confidence)
    if result := self._try_resolve_same_module(call_name, module_qn):
        return result

    # 6. Trie fallback (LOW confidence - heuristic)
    return self._try_resolve_via_trie(call_name, module_qn)
```

### Proposed Confidence Scores

| Method | Confidence | Rationale |
|--------|------------|-----------|
| `direct_import` | 1.0 | Explicit import statement |
| `same_module` | 0.95 | Function in same file |
| `type_inference` | 0.9 | Type annotation context |
| `inherited_method` | 0.85 | Class hierarchy traversal |
| `iife` | 0.8 | IIFE pattern match |
| `wildcard_import` | 0.7 | `import *` expansion |
| `trie_fallback` | 0.5 | Heuristic name match |
| `unresolved` | 0.0 | Failed to resolve |

---

## TDD Workflow

### Day 1: Write ConfidenceScorer Tests

**File:** `codebase_rag/tests/test_confidence_scorer.py`

```python
"""Tests for ConfidenceScorer - TDD Red Phase."""
import pytest

from codebase_rag.services.confidence_scorer import (
    ConfidenceConfig,
    ConfidenceScorer,
    ResolutionMethod,
)


class TestConfidenceScorerBasicScoring:
    """Test basic confidence scoring."""

    @pytest.fixture
    def scorer(self) -> ConfidenceScorer:
        return ConfidenceScorer()

    @pytest.mark.parametrize(
        "method,expected",
        [
            (ResolutionMethod.DIRECT_IMPORT, 1.0),
            (ResolutionMethod.SAME_MODULE, 0.95),
            (ResolutionMethod.TYPE_INFERENCE, 0.9),
            (ResolutionMethod.INHERITED_METHOD, 0.85),
            (ResolutionMethod.WILDCARD_IMPORT, 0.7),
            (ResolutionMethod.TRIE_FALLBACK, 0.5),
        ],
    )
    def test_base_confidence_scores(
        self, scorer: ConfidenceScorer, method: ResolutionMethod, expected: float
    ) -> None:
        """Each resolution method should have a defined base score."""
        score = scorer.score(method)
        assert score == expected


class TestConfidenceScorerAmbiguityPenalty:
    """Test ambiguity penalty for trie fallback."""

    @pytest.fixture
    def scorer(self) -> ConfidenceScorer:
        return ConfidenceScorer()

    def test_no_penalty_for_single_match(self, scorer: ConfidenceScorer) -> None:
        """Single match should not apply penalty."""
        score = scorer.score(ResolutionMethod.TRIE_FALLBACK, ambiguity_count=1)
        assert score == 0.5

    def test_penalty_for_multiple_matches(self, scorer: ConfidenceScorer) -> None:
        """Multiple matches should apply penalty."""
        score = scorer.score(ResolutionMethod.TRIE_FALLBACK, ambiguity_count=5)
        assert score < 0.5

    def test_max_penalty_cap(self, scorer: ConfidenceScorer) -> None:
        """Penalty should not exceed maximum."""
        score = scorer.score(ResolutionMethod.TRIE_FALLBACK, ambiguity_count=100)
        assert score >= 0.2  # base 0.5 - max penalty 0.3


class TestConfidenceScorerCustomConfig:
    """Test custom configuration."""

    def test_custom_base_scores(self) -> None:
        """Custom config should override base scores."""
        config = ConfidenceConfig(direct_import_base=0.95)
        scorer = ConfidenceScorer(config)
        
        score = scorer.score(ResolutionMethod.DIRECT_IMPORT)
        assert score == 0.95

    def test_custom_penalty(self) -> None:
        """Custom config should apply custom penalty."""
        config = ConfidenceConfig(
            trie_fallback_base=0.6,
            ambiguity_penalty_per_match=0.1,
        )
        scorer = ConfidenceScorer(config)
        
        score = scorer.score(ResolutionMethod.TRIE_FALLBACK, ambiguity_count=3)
        # 0.6 - (2 * 0.1) = 0.4
        assert score == 0.4
```

### Day 2: Implement ConfidenceScorer

**File:** `codebase_rag/services/confidence_scorer.py`

```python
"""Confidence scoring for call resolutions."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ResolutionMethod(StrEnum):
    """Method used to resolve a call."""

    DIRECT_IMPORT = "direct_import"
    TYPE_INFERENCE = "type_inference"
    SAME_MODULE = "same_module"
    INHERITED_METHOD = "inherited_method"
    IIFE = "iife"
    WILDCARD_IMPORT = "wildcard_import"
    TRIE_FALLBACK = "trie_fallback"
    UNRESOLVED = "unresolved"


@dataclass
class ConfidenceConfig:
    """Configuration for confidence scoring weights."""

    direct_import_base: float = 1.0
    same_module_base: float = 0.95
    type_inference_base: float = 0.9
    inherited_method_base: float = 0.85
    iife_base: float = 0.8
    wildcard_import_base: float = 0.7
    trie_fallback_base: float = 0.5

    # Penalties
    ambiguity_penalty_per_match: float = 0.05
    max_ambiguity_penalty: float = 0.3


class ConfidenceScorer:
    """Scores confidence of call resolutions."""

    def __init__(self, config: ConfidenceConfig | None = None) -> None:
        self.config = config or ConfidenceConfig()

    def score(
        self,
        method: ResolutionMethod,
        ambiguity_count: int = 1,
        **context: Any,
    ) -> float:
        """Calculate confidence score for a resolution.

        Args:
            method: Resolution method used
            ambiguity_count: Number of possible matches (for trie fallback)
            **context: Additional context (reserved for future use)

        Returns:
            Confidence score between 0.0 and 1.0
        """
        base_scores = {
            ResolutionMethod.DIRECT_IMPORT: self.config.direct_import_base,
            ResolutionMethod.SAME_MODULE: self.config.same_module_base,
            ResolutionMethod.TYPE_INFERENCE: self.config.type_inference_base,
            ResolutionMethod.INHERITED_METHOD: self.config.inherited_method_base,
            ResolutionMethod.IIFE: self.config.iife_base,
            ResolutionMethod.WILDCARD_IMPORT: self.config.wildcard_import_base,
            ResolutionMethod.TRIE_FALLBACK: self.config.trie_fallback_base,
            ResolutionMethod.UNRESOLVED: 0.0,
        }

        base = base_scores.get(method, 0.5)

        # Apply ambiguity penalty for trie fallback
        if method == ResolutionMethod.TRIE_FALLBACK and ambiguity_count > 1:
            penalty = min(
                (ambiguity_count - 1) * self.config.ambiguity_penalty_per_match,
                self.config.max_ambiguity_penalty,
            )
            base -= penalty

        return max(0.0, min(1.0, base))
```

### Day 3: Integrate with CallResolver

**Modify:** `codebase_rag/parsers/call_resolver.py`

Add resolution metadata to return values:

```python
from dataclasses import dataclass

@dataclass
class ResolutionResult:
    """Result of call resolution with metadata."""
    
    callee_type: str
    qualified_name: str
    method: ResolutionMethod
    confidence: float
    ambiguity_count: int = 1
```

### Day 4: Write ValidationEngine Tests

**File:** `codebase_rag/tests/test_validation_engine.py`

```python
"""Tests for ValidationEngine - TDD Red Phase."""
import pytest

from codebase_rag.services.validation_engine import (
    OrphanedRelationship,
    ValidationEngine,
    ValidationResult,
)


class TestValidationEngineTargetValidation:
    """Test relationship target validation."""

    @pytest.fixture
    def engine(self) -> ValidationEngine:
        # Mock graph service
        return ValidationEngine(graph_service=None)

    def test_valid_relationship_passes(self, engine: ValidationEngine) -> None:
        """Relationships with existing targets should pass."""
        # Setup mock to return existing target
        result = engine.validate_relationship(
            source_id=1,
            target_id=2,
            rel_type="CALLS"
        )
        
        assert result.is_valid is True

    def test_orphaned_relationship_fails(self, engine: ValidationEngine) -> None:
        """Relationships with missing targets should fail."""
        # Setup mock to return no target
        result = engine.validate_relationship(
            source_id=1,
            target_id=999,  # Non-existent
            rel_type="CALLS"
        )
        
        assert result.is_valid is False
        assert "target not found" in result.error_message.lower()


class TestValidationEngineOrphanReporting:
    """Test orphan relationship reporting."""

    @pytest.fixture
    def engine(self) -> ValidationEngine:
        return ValidationEngine(graph_service=None)

    def test_report_orphans_returns_list(self, engine: ValidationEngine) -> None:
        """report_orphans should return list of OrphanedRelationship."""
        orphans = engine.report_orphans()
        
        assert isinstance(orphans, list)
        for orphan in orphans:
            assert isinstance(orphan, OrphanedRelationship)
```

### Day 5: Implement ValidationEngine

**File:** `codebase_rag/services/validation_engine.py`

```python
"""Validation engine for relationship integrity."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from codebase_rag.services.graph_service import MemgraphIngestor


@dataclass
class ValidationResult:
    """Result of a validation check."""

    is_valid: bool
    error_message: str = ""


@dataclass
class OrphanedRelationship:
    """Record of an orphaned relationship."""

    source_id: int
    target_id: int
    rel_type: str
    source_label: str
    expected_target_label: str


class ValidationEngine:
    """Validates relationship integrity in the graph."""

    def __init__(self, graph_service: MemgraphIngestor | None) -> None:
        self.graph_service = graph_service

    def validate_relationship(
        self,
        source_id: int,
        target_id: int,
        rel_type: str,
    ) -> ValidationResult:
        """Validate that a relationship's target exists.

        Args:
            source_id: ID of source node
            target_id: ID of target node
            rel_type: Type of relationship

        Returns:
            ValidationResult indicating if relationship is valid
        """
        if self.graph_service is None:
            return ValidationResult(is_valid=True)

        # Check if target exists
        target_exists = self._node_exists(target_id)
        
        if not target_exists:
            return ValidationResult(
                is_valid=False,
                error_message=f"Target not found: {target_id} for {rel_type}"
            )
        
        return ValidationResult(is_valid=True)

    def _node_exists(self, node_id: int) -> bool:
        """Check if a node exists in the graph."""
        if self.graph_service is None:
            return True
        
        query = "MATCH (n) WHERE id(n) = $id RETURN n LIMIT 1"
        # Execute query and check result
        return True  # Placeholder

    def report_orphans(self) -> list[OrphanedRelationship]:
        """Find all relationships with missing targets.

        Returns:
            List of orphaned relationships
        """
        if self.graph_service is None:
            return []

        # Query for orphaned relationships
        query = """
        MATCH (source)-[r]->(target)
        WHERE target IS NULL
        RETURN id(source) as source_id,
               id(target) as target_id,
               type(r) as rel_type,
               labels(source)[0] as source_label
        """
        # Execute and map results
        return []  # Placeholder
```

---

## Schema Changes

### CALLS Relationship Enhancement

```python
# Add to types_defs.py or create separate schema file

class CallsRelationshipProps(TypedDict):
    """Properties for CALLS relationships."""
    
    confidence: float          # 0.0-1.0
    resolution_method: str     # ResolutionMethod value
    ambiguity_count: int       # Number of possible matches
    call_site_line: int        # Line number of the call
    created_at: str            # ISO 8601 timestamp
```

---

## Verification Gates

### Must Pass Before Phase 3

| Gate | Criteria | Status |
|------|----------|--------|
| Unit Tests | All ConfidenceScorer tests pass | ⬜ |
| Unit Tests | All ValidationEngine tests pass | ⬜ |
| Integration | CallResolver returns ResolutionResult | ⬜ |
| Integration | CALLS relationships have confidence | ⬜ |
| Coverage | > 90% on new code | ⬜ |
| Types | pyright clean on new code | ⬜ |

---

## Files to Create/Modify

### New Files

| File | Purpose |
|------|---------|
| `codebase_rag/services/confidence_scorer.py` | Confidence scoring |
| `codebase_rag/services/validation_engine.py` | Relationship validation |
| `codebase_rag/tests/test_confidence_scorer.py` | ConfidenceScorer tests |
| `codebase_rag/tests/test_validation_engine.py` | ValidationEngine tests |

### Modified Files

| File | Changes |
|------|---------|
| `codebase_rag/parsers/call_resolver.py` | Return ResolutionResult |
| `codebase_rag/parsers/call_processor.py` | Track resolution metadata |
| `codebase_rag/services/graph_service.py` | Store relationship properties |

---

**Phase Status:** 🔄 Not Started  
**Last Updated:** 2026-01-03
