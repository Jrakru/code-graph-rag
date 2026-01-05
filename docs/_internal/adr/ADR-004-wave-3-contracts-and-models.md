# ADR-004: Wave 3 - Contracts & Models

**Status:** Accepted  
**Date:** 2025-01-03  
**Parent ADR:** [ADR-001: Data Integrity Initiative](ADR-001-data-integrity-initiative.md)

## Context

After implementing provenance tracking (Wave 1) and validation (Wave 2), we had working services but lacked:

1. **Type Safety**: Domain objects passed as dicts with no validation
2. **Clear Contracts**: Service interfaces weren't explicitly defined
3. **Runtime Validation**: No checks for invalid data at creation time
4. **Serialization**: No standard way to convert between graph data and Python objects

This led to:
- Runtime errors from invalid data
- Unclear service boundaries
- Difficulty extending services
- Manual validation scattered across codebase

## Decision

Implement a **contracts and models layer** using:

1. **Protocol Definitions**: Explicit interfaces for services
2. **Pydantic Models**: Validated domain objects
3. **Support Services**: FileClassifier, ConfidenceScorer
4. **Centralized Validation**: Move validation logic into models

### Architecture

```
┌─────────────────────────────────────────┐
│         Service Layer                   │
│  (ValidationEngine, ProvenanceTracker)  │
└─────────────────────────────────────────┘
                 │ uses
                 ▼
┌─────────────────────────────────────────┐
│       Protocol Layer                    │
│  (Defines service interfaces)           │
└─────────────────────────────────────────┘
                 │ implements
                 ▼
┌─────────────────────────────────────────┐
│         Model Layer                     │
│  (Pydantic validated domain objects)    │
└─────────────────────────────────────────┘
```

## Rationale

### Why Protocols?

**Alternatives considered:**

1. **Abstract Base Classes (ABC)**
   - **Rejected**: Forces inheritance, tighter coupling
   
2. **Duck Typing**
   - **Rejected**: No compile-time checks, unclear contracts
   
3. **Protocols** (chosen)
   - Structural subtyping (any class with matching methods satisfies protocol)
   - Clear contracts without forcing inheritance
   - Type checker support (mypy, pyright)

### Why Pydantic?

**Alternatives:**

1. **Plain Dataclasses**
   - **Rejected**: No runtime validation
   
2. **Manual Validation**
   - **Rejected**: Error-prone, scattered logic
   
3. **Pydantic BaseModel** (chosen)
   - Runtime validation
   - JSON serialization
   - Clear error messages
   - OpenAPI/JSON Schema generation

### Protocol Definitions

#### 1. ProvenanceProtocol

Defines interface for tracking file parsing metadata:

```python
class ProvenanceProtocol(Protocol):
    def track_file_parse(
        self,
        file_path: str,
        content: str,
        parser_version: str
    ) -> FileProvenance: ...
    
    def is_file_stale(
        self,
        file_path: str,
        current_content: str
    ) -> bool: ...
```

#### 2. ValidationProtocol

Defines interface for graph validation:

```python
class ValidationProtocol(Protocol):
    def validate_graph(self) -> ValidationReport: ...
    
    def find_orphans(self) -> list[Issue]: ...
    
    def validate_relationships(self) -> list[Issue]: ...
```

#### 3. FileClassifierProtocol

Defines interface for file classification:

```python
class FileClassifierProtocol(Protocol):
    def classify(self, file_path: str) -> FileCategory: ...
    
    def is_parseable(self, file_path: str) -> bool: ...
```

#### 4. ConfidenceScorerProtocol

Defines interface for confidence scoring:

```python
class ConfidenceScorerProtocol(Protocol):
    def score_relationship(
        self,
        source: Node,
        target: Node,
        rel_type: str
    ) -> float: ...
```

## Consequences

### Positive

- **Type Safety**: Pydantic catches invalid data at creation time
- **Clear Contracts**: Protocols make service interfaces explicit
- **Better IDE Support**: Autocomplete and type hints work correctly
- **Easier Testing**: Can mock protocols without concrete implementations
- **Self-Documenting**: Models serve as schema documentation

### Negative

- **Learning Curve**: Team needs to understand Pydantic and protocols
- **Performance**: Pydantic validation adds ~1ms per object (measured)
- **Boilerplate**: More code than plain dicts
- **Migration Effort**: Existing code needs updates to use models

### Performance Impact

Measured on 1000 model instances:
- **Creation time**: 1.2 seconds (1.2ms per instance)
- **Validation time**: Included in creation
- **Serialization**: 0.8 seconds to JSON (0.8ms per instance)

**Verdict**: Overhead is negligible for improved safety.

## Implementation Details

### Model Structure

```
codebase_rag/
├── models/
│   ├── __init__.py         # Public API
│   ├── base.py             # Base models (Node, Edge)
│   ├── nodes.py            # Node models (Function, Class, Module)
│   └── relationships.py    # Relationship models (CALLS, INHERITS)
├── protocols/
│   └── __init__.py         # Protocol definitions
└── services/
    ├── provenance_tracker.py      # Implements ProvenanceProtocol
    ├── validation_engine.py       # Implements ValidationProtocol
    ├── file_classifier.py         # Implements FileClassifierProtocol
    └── confidence_scorer.py       # Implements ConfidenceScorerProtocol
```

### Example Models

```python
class Node(BaseModel):
    """Base model for all graph nodes."""
    node_id: str
    label: str
    properties: dict[str, Any]
    
    model_config = ConfigDict(frozen=True)  # Immutable

class Function(Node):
    """Model for function nodes."""
    qualified_name: str
    name: str
    decorators: list[str] = []
    file_path: str
    
    @field_validator("qualified_name")
    def validate_qualified_name(cls, v: str) -> str:
        if not v or "." not in v:
            raise ValueError("qualified_name must be in format 'module.function'")
        return v
```

### Support Services

#### FileClassifier

Classifies files into categories:

```python
class FileCategory(StrEnum):
    SOURCE_CODE = "source_code"
    TEST = "test"
    CONFIG = "config"
    DOCUMENTATION = "documentation"
    BINARY = "binary"
    UNKNOWN = "unknown"

class FileClassifier:
    def classify(self, file_path: str) -> FileCategory:
        """Classify file based on path and extension."""
```

#### ConfidenceScorer

Assigns confidence scores to relationships:

```python
class ConfidenceScorer:
    def score_relationship(
        self,
        source: Node,
        target: Node,
        rel_type: str
    ) -> float:
        """Return confidence score 0.0-1.0."""
        # Uses heuristics:
        # - Same module: higher confidence
        # - Type annotations: higher confidence
        # - Dynamic calls: lower confidence
```

## Testing

- **Unit tests**: `codebase_rag/tests/test_models.py`
- **Coverage**: 20 tests covering:
  - Model validation (valid/invalid data)
  - Serialization (to/from JSON)
  - Immutability
  - Field validators
  - Edge cases (empty fields, None values)

- **Service tests**:
  - `test_file_classifier.py`: 8 tests
  - `test_confidence_scorer.py`: 7 tests

## Migration Guide

### Before (Plain Dicts)

```python
node = {
    "node_id": "123",
    "label": "Function",
    "name": "parse_args",
    "qualified_name": "cli.parse_args"
}
```

### After (Pydantic Models)

```python
node = Function(
    node_id="123",
    label="Function",
    name="parse_args",
    qualified_name="cli.parse_args",
    file_path="src/cli.py"
)

# Validation happens automatically
# Invalid data raises ValidationError
```

## Future Work

1. **Derived Fields**: Auto-compute fields from other fields
2. **Custom Validators**: Domain-specific validation rules
3. **Schema Evolution**: Handle model version upgrades
4. **GraphQL Schema**: Generate GraphQL API from Pydantic models
5. **ORM Layer**: Map models directly to Memgraph nodes

## References

- Models: `codebase_rag/models/`
- Protocols: `codebase_rag/protocols/`
- Services: `codebase_rag/services/`
- Tests: 
  - `codebase_rag/tests/test_models.py`
  - `codebase_rag/tests/test_file_classifier.py`
  - `codebase_rag/tests/test_confidence_scorer.py`
- Parent ADR: [ADR-001: Data Integrity Initiative](ADR-001-data-integrity-initiative.md)
