# Phase 3: Contract-by-Design Implementation

## Overview

**Duration:** Week 4  
**Status:** 🔄 Not Started  
**Goal:** Enforce invariants through Python's type system using Pydantic and Protocols.

---

## Problem Statement

The codebase currently lacks:

1. **Formal interface definitions** - No Protocol classes for dependency injection
2. **Runtime validation** - Dict properties not validated
3. **Immutable value objects** - Data structures can be mutated unexpectedly
4. **Explicit error handling** - Exceptions used instead of Result types

---

## Deliverables

| Deliverable | Description | Priority |
|-------------|-------------|----------|
| Protocol definitions | ISP-compliant interfaces | P0 |
| Pydantic models | Validated node/relationship models | P0 |
| Result types | Explicit success/failure handling | P1 |
| Immutable value objects | Thread-safe data structures | P1 |

---

## SOLID Principles Application

### Single Responsibility Principle (SRP)

Each class has one reason to change:

```python
# ❌ BAD: Multiple responsibilities
class CallProcessor:
    def extract_calls(self, ...): ...
    def resolve_calls(self, ...): ...
    def validate_calls(self, ...): ...
    def score_confidence(self, ...): ...

# ✅ GOOD: Single responsibility each
class CallExtractor:
    def extract_calls(self, ...): ...

class CallResolver:
    def resolve_calls(self, ...): ...

class CallValidator:
    def validate_calls(self, ...): ...

class ConfidenceScorer:
    def score_confidence(self, ...): ...
```

### Interface Segregation Principle (ISP)

Small, focused protocols instead of large interfaces:

```python
# ❌ BAD: Fat interface
class ProcessorProtocol(Protocol):
    def classify_files(self, ...): ...
    def track_provenance(self, ...): ...
    def validate_relationships(self, ...): ...
    def score_confidence(self, ...): ...

# ✅ GOOD: Segregated interfaces
class FileClassifierProtocol(Protocol):
    def classify(self, path: Path) -> SourceType: ...

class ProvenanceTrackerProtocol(Protocol):
    def record_parse(self, path: Path) -> dict[str, Any]: ...

class ValidationEngineProtocol(Protocol):
    def validate_relationship(self, ...) -> ValidationResult: ...

class ConfidenceScorerProtocol(Protocol):
    def score(self, method: ResolutionMethod, ...) -> float: ...
```

### Dependency Inversion Principle (DIP)

High-level modules depend on abstractions:

```python
# ❌ BAD: Concrete dependency
class GraphUpdater:
    def __init__(self):
        self.classifier = FileClassifier()  # Concrete!

# ✅ GOOD: Depends on abstraction
class GraphUpdater:
    def __init__(self, classifier: FileClassifierProtocol):
        self.classifier = classifier  # Protocol!
```

---

## Protocol Definitions

### Core Protocols

**File:** `codebase_rag/protocols/provenance.py`

```python
"""Provenance-related protocols."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from codebase_rag.services.file_classifier import SourceType


class FileClassifierProtocol(Protocol):
    """Classifies files by source type."""

    def classify(self, path: Path) -> SourceType:
        """Return the source type for a file path."""
        ...

    def is_documentation(self, path: Path) -> bool:
        """Quick check if file is documentation."""
        ...


class ProvenanceTrackerProtocol(Protocol):
    """Tracks provenance metadata for parsed files."""

    def record_parse(self, path: Path) -> dict[str, Any]:
        """Return provenance metadata for a parsed file."""
        ...

    def is_stale(self, path: Path, stored_hash: str) -> bool:
        """Check if a file has changed since parsing."""
        ...
```

**File:** `codebase_rag/protocols/validation.py`

```python
"""Validation-related protocols."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from codebase_rag.services.confidence_scorer import ResolutionMethod
    from codebase_rag.services.validation_engine import (
        OrphanedRelationship,
        ValidationResult,
    )


class ConfidenceScorerProtocol(Protocol):
    """Scores confidence of call resolutions."""

    def score(
        self,
        method: ResolutionMethod,
        ambiguity_count: int = 1,
        **context: Any,
    ) -> float:
        """Return confidence score 0.0-1.0 for a resolution."""
        ...


class ValidationEngineProtocol(Protocol):
    """Validates relationship targets exist."""

    def validate_relationship(
        self,
        source_id: int,
        target_id: int,
        rel_type: str,
    ) -> ValidationResult:
        """Validate a relationship and return result."""
        ...

    def report_orphans(self) -> list[OrphanedRelationship]:
        """Return all relationships with missing targets."""
        ...
```

---

## Pydantic Models

### Node Models

**File:** `codebase_rag/models/nodes.py`

```python
"""Pydantic models for graph nodes."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from codebase_rag.services.file_classifier import SourceType


class FileNode(BaseModel):
    """Validated model for File nodes."""

    model_config = {"frozen": True}  # Immutable

    path: str = Field(..., description="File system path")
    name: str = Field(..., description="File name")
    extension: str = Field(..., description="File extension")
    source_type: SourceType = Field(..., description="Classification")
    parsed_at: datetime = Field(..., description="When file was parsed")
    file_mtime: float = Field(..., description="File modification time")
    file_hash: str = Field(..., min_length=64, max_length=64, description="SHA256 hash")

    @field_validator("path")
    @classmethod
    def path_not_empty(cls, v: str) -> str:
        """Path must not be empty."""
        if not v.strip():
            raise ValueError("path cannot be empty")
        return v

    @field_validator("file_hash")
    @classmethod
    def valid_sha256(cls, v: str) -> str:
        """Hash must be valid hex."""
        if not all(c in "0123456789abcdef" for c in v.lower()):
            raise ValueError("file_hash must be valid hex")
        return v.lower()


class ModuleNode(BaseModel):
    """Validated model for Module nodes."""

    model_config = {"frozen": True}

    qualified_name: str = Field(..., description="Fully qualified module name")
    name: str = Field(..., description="Simple module name")
    path: str = Field(..., description="Module file path")
    parsed_at: datetime | None = Field(None, description="When module was parsed")

    @field_validator("qualified_name")
    @classmethod
    def qn_not_empty(cls, v: str) -> str:
        """Qualified name must not be empty."""
        if not v.strip():
            raise ValueError("qualified_name cannot be empty")
        return v


class FunctionNode(BaseModel):
    """Validated model for Function nodes."""

    model_config = {"frozen": True}

    qualified_name: str = Field(..., description="Fully qualified function name")
    name: str = Field(..., description="Simple function name")
    decorators: list[str] = Field(default_factory=list, description="Decorators")
    start_line: int | None = Field(None, ge=1, description="Start line number")
    end_line: int | None = Field(None, ge=1, description="End line number")
    docstring: str | None = Field(None, description="Function docstring")

    @field_validator("end_line")
    @classmethod
    def end_after_start(cls, v: int | None, info) -> int | None:
        """End line must be >= start line."""
        if v is not None and info.data.get("start_line") is not None:
            if v < info.data["start_line"]:
                raise ValueError("end_line must be >= start_line")
        return v
```

### Relationship Models

**File:** `codebase_rag/models/relationships.py`

```python
"""Pydantic models for graph relationships."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from codebase_rag.services.confidence_scorer import ResolutionMethod


class CallsRelationship(BaseModel):
    """Validated model for CALLS relationships."""

    model_config = {"frozen": True}

    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Resolution confidence"
    )
    resolution_method: ResolutionMethod = Field(
        ..., description="How call was resolved"
    )
    ambiguity_count: int = Field(
        default=1, ge=1, description="Number of possible matches"
    )
    call_site_line: int | None = Field(
        None, ge=1, description="Line number of the call"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="When relationship was created"
    )


class DefinesRelationship(BaseModel):
    """Validated model for DEFINES relationships."""

    model_config = {"frozen": True}

    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="When relationship was created"
    )
```

---

## Result Types

**File:** `codebase_rag/models/results.py`

```python
"""Result types for explicit error handling."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")
E = TypeVar("E")


@dataclass(frozen=True)
class Success(Generic[T]):
    """Successful result containing a value."""

    value: T

    @property
    def is_success(self) -> bool:
        return True

    @property
    def is_failure(self) -> bool:
        return False


@dataclass(frozen=True)
class Failure(Generic[E]):
    """Failed result containing an error."""

    error: E

    @property
    def is_success(self) -> bool:
        return False

    @property
    def is_failure(self) -> bool:
        return True


Result = Success[T] | Failure[E]


# Helper functions
def ok(value: T) -> Success[T]:
    """Create a success result."""
    return Success(value)


def err(error: E) -> Failure[E]:
    """Create a failure result."""
    return Failure(error)


# Example usage:
# def resolve_call(...) -> Result[ResolutionResult, str]:
#     if resolved:
#         return ok(ResolutionResult(...))
#     return err("Could not resolve call")
```

---

## Migration Strategy

### Gradual Adoption

1. **New code uses Protocols** - All new classes implement Protocols
2. **New models use Pydantic** - All new data structures are validated
3. **Existing code unchanged** - No breaking changes to existing code
4. **Adapter pattern** - Wrap existing classes in Protocol-compliant adapters

### Example Adapter

```python
class FileClassifierAdapter:
    """Adapter to make existing code Protocol-compliant."""

    def __init__(self, legacy_classifier: Any) -> None:
        self._classifier = legacy_classifier

    def classify(self, path: Path) -> SourceType:
        """Delegate to legacy classifier."""
        return self._classifier.classify(path)

    def is_documentation(self, path: Path) -> bool:
        """Delegate to legacy classifier."""
        return self._classifier.is_documentation(path)
```

---

## Verification Gates

### Must Pass Before Phase 4

| Gate | Criteria | Status |
|------|----------|--------|
| Protocols | All protocols defined | ⬜ |
| Models | All Pydantic models defined | ⬜ |
| Results | Result types implemented | ⬜ |
| Types | pyright clean on all new code | ⬜ |
| Tests | > 90% coverage on new code | ⬜ |

---

## Files to Create

| File | Purpose |
|------|---------|
| `codebase_rag/protocols/__init__.py` | Protocol package |
| `codebase_rag/protocols/provenance.py` | Provenance protocols |
| `codebase_rag/protocols/validation.py` | Validation protocols |
| `codebase_rag/models/__init__.py` | Models package |
| `codebase_rag/models/nodes.py` | Node models |
| `codebase_rag/models/relationships.py` | Relationship models |
| `codebase_rag/models/results.py` | Result types |

---

**Phase Status:** 🔄 Not Started  
**Last Updated:** 2026-01-03
