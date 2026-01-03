# Architecture Analysis: Data Integrity & Provenance

## Executive Summary

This document analyzes the current Code-Graph-RAG architecture and identifies critical gaps in data provenance and validation. The system currently treats all indexed content as equally trustworthy, with no distinction between source code and documentation, and no confidence scoring for ambiguous call resolutions.

---

## Current Architecture

### 4-Pass Indexing Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           INDEXING PIPELINE                                      │
│                                                                                  │
│   Pass 1             Pass 2              Pass 3             Pass 4              │
│   STRUCTURE          DEFINITIONS         CALLS              EMBEDDINGS          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐      │
│  │ Structure   │ -> │ Definition  │ -> │ Call        │ -> │ Embedder    │      │
│  │ Processor   │    │ Processor   │    │ Processor   │    │             │      │
│  │             │    │             │    │ + Resolver  │    │             │      │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘      │
│                                                                                  │
│  Creates:           Creates:           Creates:           Creates:              │
│  - Project          - Module           - CALLS rels       - Vector              │
│  - Package          - Class            - Resolved         - embeddings          │
│  - Folder           - Function           targets                                │
│  - File             - Method                                                    │
│                     - DEFINES rels                                              │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Key Components

| Component | File | Responsibility |
|-----------|------|----------------|
| **GraphUpdater** | `graph_updater.py` | Orchestrates 4-pass indexing |
| **StructureProcessor** | `parsers/structure_processor.py` | Creates Package/Folder/File nodes |
| **DefinitionProcessor** | `parsers/definition_processor.py` | Extracts Classes/Functions/Methods |
| **CallProcessor** | `parsers/call_processor.py` | Extracts call expressions |
| **CallResolver** | `parsers/call_resolver.py` | Resolves call targets |
| **ImportProcessor** | `parsers/import_processor.py` | Tracks import mappings |
| **MemgraphIngestor** | `services/graph_service.py` | Writes to Memgraph |

---

## Identified Gaps

### Gap 1: No Source Type Classification

**Problem:** All files are indexed identically regardless of their purpose.

**Evidence from `types_defs.py` (line 402):**
```python
NodeSchema(NodeLabel.FILE, "{path: string, name: string, extension: string}"),
```

The `File` node schema only stores:
- `path` - File system path
- `name` - File name
- `extension` - File extension

**Missing:**
- `source_type` - Classification (code, documentation, test, config)
- `is_documentation` - Boolean flag for docs
- `parsed_at` - When the file was last indexed
- `file_mtime` - Original file modification time

**Impact:**
- README.md content has same authority as main.py
- Outdated documentation is returned as current truth
- No way to filter queries by source type

### Gap 2: No Confidence Scoring for Call Resolution

**Problem:** Ambiguous call resolutions have no quality indicator.

**Evidence from `call_resolver.py` (lines 207-223):**
```python
def _try_resolve_via_trie(
    self, call_name: str, module_qn: str
) -> tuple[str, str] | None:
    search_name = re.split(r"[.:]|::", call_name)[-1]
    possible_matches = self.function_registry.find_ending_with(search_name)
    if not possible_matches:
        logger.debug(ls.CALL_UNRESOLVED.format(call_name=call_name))
        return None

    possible_matches.sort(
        key=lambda qn: self._calculate_import_distance(qn, module_qn)
    )
    best_candidate_qn = possible_matches[0]
    logger.debug(
        ls.CALL_TRIE_FALLBACK.format(call_name=call_name, qn=best_candidate_qn)
    )
    return self.function_registry[best_candidate_qn], best_candidate_qn
```

**Analysis:**
- The trie fallback is a heuristic - it picks the "closest" match
- No indication that this resolution is less reliable than a direct import
- The CALLS relationship stores no metadata about resolution quality

**Missing on CALLS relationship:**
- `confidence` - Float 0.0-1.0 indicating resolution certainty
- `resolution_method` - How the call was resolved (direct_import, type_inference, trie_fallback)
- `ambiguity_count` - Number of possible matches before selecting best

### Gap 3: No Relationship Validation

**Problem:** CALLS relationships are created without verifying targets exist.

**Evidence from `graph_service.py` - MERGE operations:**
```cypher
MERGE (caller)-[:CALLS]->(callee)
```

**What happens when target doesn't exist:**
- If `callee` node doesn't exist, Cypher MERGE simply creates no relationship
- No error is raised
- No tracking of unresolved calls

**Impact:**
- Silent data loss - we don't know what calls couldn't be resolved
- No audit trail for debugging relationship issues
- Can't distinguish "no calls" from "calls failed to resolve"

### Gap 4: No Staleness Detection

**Problem:** No timestamps on nodes to detect outdated information.

**Evidence from `types_defs.py`:**
All node schemas lack temporal metadata:
```python
NodeSchema(NodeLabel.MODULE, "{qualified_name: string, name: string, path: string}"),
NodeSchema(NodeLabel.CLASS, "{qualified_name: string, name: string, decorators: list[string]}"),
NodeSchema(NodeLabel.FUNCTION, "{qualified_name: string, name: string, decorators: list[string]}"),
```

**Missing:**
- `parsed_at` - ISO timestamp of indexing
- `source_mtime` - File modification time at parse
- `stale` - Boolean flag for detected staleness

---

## Resolution Method Analysis

The `CallResolver` uses a priority chain for resolution. Each method has different reliability:

| Resolution Method | Reliability | Evidence | Current Tracking |
|-------------------|-------------|----------|------------------|
| Direct Import | HIGH | Import statement explicitly maps name | Logged only |
| Type Inference | MEDIUM-HIGH | Type annotation provides context | Logged only |
| Same Module | HIGH | Function defined in same file | Logged only |
| Inherited Method | MEDIUM | Follows class hierarchy | Logged only |
| Trie Fallback | LOW | Heuristic based on name suffix | Logged only |
| Wildcard Import | MEDIUM | `import *` expansion | Logged only |

**Current state:** All resolutions are logged at DEBUG level but nothing persists to the graph.

---

## Proposed Solution Architecture

### New Components

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        PROPOSED ENHANCED PIPELINE                                │
│                                                                                  │
│   Pass 1             Pass 2              Pass 3             Pass 4              │
│   STRUCTURE          DEFINITIONS         CALLS              VALIDATION          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐      │
│  │ Structure   │ -> │ Definition  │ -> │ Call        │ -> │ Validation  │      │
│  │ Processor   │    │ Processor   │    │ Processor   │    │ Engine      │      │
│  │ +           │    │ +           │    │ +           │    │             │      │
│  │ FileClass-  │    │ Provenance  │    │ Confidence  │    │ Target      │      │
│  │ ifier       │    │ Tracker     │    │ Scorer      │    │ Verifier    │      │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘      │
│                                                                                  │
│  Adds:              Adds:              Adds:              Does:                 │
│  - source_type      - parsed_at        - confidence       - Verify targets     │
│  - is_docs          - source_mtime     - resolution_      - Report orphans     │
│  - file_mtime       - staleness          method           - Schema check       │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Schema Changes

#### File Node (Enhanced)

```python
# Current
NodeSchema(NodeLabel.FILE, "{path: string, name: string, extension: string}")

# Proposed
NodeSchema(
    NodeLabel.FILE,
    """{
        path: string,
        name: string,
        extension: string,
        source_type: string,      # "code" | "documentation" | "test" | "config"
        is_documentation: bool,   # Quick filter flag
        parsed_at: string,        # ISO 8601 timestamp
        file_mtime: float,        # Unix timestamp of file
        file_hash: string         # SHA256 of content for change detection
    }"""
)
```

#### CALLS Relationship (Enhanced)

```python
# Current - no schema defined, created implicitly

# Proposed
RelationshipSchema(
    (NodeLabel.FUNCTION, NodeLabel.METHOD),
    RelationshipType.CALLS,
    (NodeLabel.FUNCTION, NodeLabel.METHOD),
    properties="""{
        confidence: float,           # 0.0-1.0
        resolution_method: string,   # "direct_import" | "type_inference" | "trie_fallback" | etc.
        ambiguity_count: int,        # Number of possible matches
        call_site_line: int,         # Line number of the call
        created_at: string           # ISO 8601 timestamp
    }"""
)
```

### New Protocols (ISP Compliance)

```python
# codebase_rag/protocols/provenance.py

from typing import Protocol
from enum import StrEnum

class SourceType(StrEnum):
    CODE = "code"
    DOCUMENTATION = "documentation"
    TEST = "test"
    CONFIG = "config"

class ResolutionMethod(StrEnum):
    DIRECT_IMPORT = "direct_import"
    TYPE_INFERENCE = "type_inference"
    SAME_MODULE = "same_module"
    INHERITED_METHOD = "inherited_method"
    TRIE_FALLBACK = "trie_fallback"
    WILDCARD_IMPORT = "wildcard_import"
    UNRESOLVED = "unresolved"

class FileClassifierProtocol(Protocol):
    """Classifies files by source type based on extension and path patterns."""
    
    def classify(self, path: Path) -> SourceType:
        """Return the source type for a file path."""
        ...
    
    def is_documentation(self, path: Path) -> bool:
        """Quick check if file is documentation."""
        ...

class ProvenanceTrackerProtocol(Protocol):
    """Tracks provenance metadata for nodes."""
    
    def record_parse(self, path: Path) -> dict[str, Any]:
        """Return provenance metadata for a parsed file."""
        ...
    
    def detect_staleness(self, node_id: int) -> bool:
        """Check if a node's source has changed since parsing."""
        ...

class ConfidenceScorerProtocol(Protocol):
    """Scores confidence of call resolutions."""
    
    def score(
        self,
        method: ResolutionMethod,
        ambiguity_count: int,
        **context: Any
    ) -> float:
        """Return confidence score 0.0-1.0 for a resolution."""
        ...

class ValidationEngineProtocol(Protocol):
    """Validates relationship targets exist."""
    
    def validate_relationship(
        self,
        source_id: int,
        target_id: int,
        rel_type: str
    ) -> ValidationResult:
        """Validate a relationship and return result."""
        ...
    
    def report_orphans(self) -> list[OrphanedRelationship]:
        """Return all relationships with missing targets."""
        ...
```

### Confidence Scoring Logic

```python
# codebase_rag/services/confidence_scorer.py

from dataclasses import dataclass

@dataclass
class ConfidenceConfig:
    """Configuration for confidence scoring weights."""
    direct_import_base: float = 1.0
    type_inference_base: float = 0.9
    same_module_base: float = 0.95
    inherited_method_base: float = 0.85
    wildcard_import_base: float = 0.7
    trie_fallback_base: float = 0.5
    
    # Penalties
    ambiguity_penalty_per_match: float = 0.05
    max_ambiguity_penalty: float = 0.3

class ConfidenceScorer:
    def __init__(self, config: ConfidenceConfig | None = None):
        self.config = config or ConfidenceConfig()
    
    def score(
        self,
        method: ResolutionMethod,
        ambiguity_count: int = 1,
        **context: Any
    ) -> float:
        base_scores = {
            ResolutionMethod.DIRECT_IMPORT: self.config.direct_import_base,
            ResolutionMethod.TYPE_INFERENCE: self.config.type_inference_base,
            ResolutionMethod.SAME_MODULE: self.config.same_module_base,
            ResolutionMethod.INHERITED_METHOD: self.config.inherited_method_base,
            ResolutionMethod.WILDCARD_IMPORT: self.config.wildcard_import_base,
            ResolutionMethod.TRIE_FALLBACK: self.config.trie_fallback_base,
        }
        
        base = base_scores.get(method, 0.5)
        
        # Apply ambiguity penalty for trie fallback
        if method == ResolutionMethod.TRIE_FALLBACK and ambiguity_count > 1:
            penalty = min(
                (ambiguity_count - 1) * self.config.ambiguity_penalty_per_match,
                self.config.max_ambiguity_penalty
            )
            base -= penalty
        
        return max(0.0, min(1.0, base))
```

### File Classification Logic

```python
# codebase_rag/services/file_classifier.py

from pathlib import Path
from typing import ClassVar

class FileClassifier:
    """Classifies files by source type."""
    
    DOC_EXTENSIONS: ClassVar[frozenset[str]] = frozenset({
        ".md", ".rst", ".txt", ".adoc", ".asciidoc"
    })
    
    DOC_PATTERNS: ClassVar[tuple[str, ...]] = (
        "README", "CHANGELOG", "LICENSE", "CONTRIBUTING",
        "docs/", "documentation/", "doc/"
    )
    
    TEST_PATTERNS: ClassVar[tuple[str, ...]] = (
        "test_", "_test.", ".test.", "tests/", "__tests__/",
        "spec/", ".spec."
    )
    
    CONFIG_EXTENSIONS: ClassVar[frozenset[str]] = frozenset({
        ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf"
    })
    
    CONFIG_NAMES: ClassVar[frozenset[str]] = frozenset({
        "pyproject.toml", "setup.py", "setup.cfg",
        "package.json", "tsconfig.json", "cargo.toml",
        ".gitignore", ".env", "Makefile", "Dockerfile"
    })
    
    def classify(self, path: Path) -> SourceType:
        """Classify a file path into a source type."""
        name = path.name
        suffix = path.suffix.lower()
        path_str = str(path)
        
        # Check documentation first (highest priority for docs)
        if suffix in self.DOC_EXTENSIONS:
            return SourceType.DOCUMENTATION
        if any(pattern in path_str for pattern in self.DOC_PATTERNS):
            return SourceType.DOCUMENTATION
        
        # Check test files
        if any(pattern in path_str for pattern in self.TEST_PATTERNS):
            return SourceType.TEST
        
        # Check config files
        if name in self.CONFIG_NAMES:
            return SourceType.CONFIG
        if suffix in self.CONFIG_EXTENSIONS:
            return SourceType.CONFIG
        
        # Default to code
        return SourceType.CODE
    
    def is_documentation(self, path: Path) -> bool:
        """Quick check if file is documentation."""
        return self.classify(path) == SourceType.DOCUMENTATION
```

---

## Risk Assessment

### Implementation Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Schema migration breaks existing graphs | HIGH | Add fields with defaults, don't remove |
| Performance impact from validation | MEDIUM | Make validation optional, run async |
| Confidence thresholds need tuning | LOW | Make configurable, start conservative |
| Breaking changes to query patterns | MEDIUM | Maintain backward compatibility |

### Backward Compatibility Strategy

1. **Additive schema changes only** - New fields have defaults
2. **Optional validation pass** - Can be disabled for performance
3. **Graceful degradation** - Missing provenance treated as legacy data
4. **Migration tooling** - Script to backfill provenance on existing graphs

---

## Success Criteria

### Phase 1: Data Provenance
- [ ] All File nodes have `source_type` field
- [ ] Classification accuracy > 95% on test corpus
- [ ] `parsed_at` timestamps on all new nodes
- [ ] Query filtering by source type works

### Phase 2: Confidence Scoring
- [ ] All CALLS relationships have `confidence` field
- [ ] Resolution method tracked for all calls
- [ ] Ambiguity count recorded for trie fallback
- [ ] Query filtering by confidence works

### Phase 3: Validation Engine
- [ ] All relationships verified before commit
- [ ] Orphaned relationships reported
- [ ] Validation failures logged with context
- [ ] Recovery mechanism for invalid states

### Phase 4: Integration
- [ ] TDD coverage > 90% for new code
- [ ] All new code follows SOLID principles
- [ ] Performance regression < 5%
- [ ] Documentation complete

---

## References

### Code Locations

| File | Lines | Component |
|------|-------|-----------|
| `types_defs.py` | 396-431 | NODE_SCHEMAS definition |
| `types_defs.py` | 434-515 | RELATIONSHIP_SCHEMAS definition |
| `call_resolver.py` | 207-223 | Trie fallback resolution |
| `call_resolver.py` | 654-674 | Import distance calculation |
| `graph_service.py` | - | MERGE operations |

### External References

- [Pydantic Validators](https://docs.pydantic.dev/latest/concepts/validators/)
- [Python Protocols (PEP 544)](https://peps.python.org/pep-0544/)
- [Memgraph Cypher](https://memgraph.com/docs/cypher-manual)

---

**Document Status:** Draft  
**Last Updated:** 2026-01-03  
**Author:** Architecture Team
