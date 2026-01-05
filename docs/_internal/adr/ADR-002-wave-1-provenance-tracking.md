# ADR-002: Wave 1 - Provenance Tracking

**Status:** Accepted  
**Date:** 2025-01-03  
**Parent ADR:** [ADR-001: Data Integrity Initiative](ADR-001-data-integrity-initiative.md)

## Context

When parsing multi-language codebases into a knowledge graph, we had no way to track:
- **When** a file was last parsed
- **What version** of the file was parsed (file hash)
- **Whether graph data is stale** (file modified since last parse)

This made it impossible to:
1. Detect outdated graph data
2. Implement incremental updates efficiently
3. Debug issues related to parser runs
4. Provide audit trails for compliance

## Decision

Implement a **ProvenanceTracker** service that records file-level metadata for every parsed file:

```python
@dataclass
class FileProvenance:
    file_path: str
    file_hash: str          # SHA-256 hash of file content
    mtime: float            # Last modified timestamp
    parsed_at: datetime     # When we parsed it
    parser_version: str     # Parser version used
```

### Integration Points

1. **Definition Processor**: Track provenance when creating Function/Class nodes
2. **Structure Processor**: Track provenance when creating Module/Package nodes
3. **Graph Nodes**: Add provenance properties to nodes in Memgraph

### Metadata Stored in Graph

Each parsed node includes:
- `file_hash`: SHA-256 hash for content-based staleness detection
- `parsed_at`: ISO timestamp for time-based tracking
- `parser_version`: Version string for compatibility checking

## Rationale

### Why File-Level Tracking?

**Alternatives considered:**
1. **Node-level tracking**: Too granular, high storage overhead
2. **Repository-level tracking**: Too coarse, can't detect partial staleness
3. **File-level tracking** (chosen): Right granularity for incremental updates

### Why SHA-256 Hashing?

- **Content-based detection**: Catches changes even if mtime is wrong (common in CI/CD)
- **Reliable**: Not affected by file copies, clock skew, or timezone issues
- **Standard**: Well-supported, cryptographically secure

### Why Store in Graph?

**Alternatives:**
1. **Separate database**: Requires additional infrastructure, synchronization issues
2. **File-based cache**: Can get out of sync with graph
3. **In-graph metadata** (chosen): Always consistent with graph state

## Consequences

### Positive

- **Staleness Detection**: Can identify outdated nodes by comparing file hash
- **Incremental Updates**: Future work can skip unchanged files
- **Audit Trail**: Full history of when files were parsed
- **Debug Support**: Can trace parsing issues to specific parser versions

### Negative

- **Storage Overhead**: ~200 bytes per node for metadata
- **Compute Overhead**: SHA-256 hashing adds ~5ms per file (measured on 1MB files)
- **Migration Required**: Existing nodes don't have provenance (need re-parse or backfill)

### Performance Impact

Measured on 1000-file codebase:
- **Hashing time**: 5 seconds total (~5ms per file)
- **Storage increase**: ~200KB for provenance metadata
- **Query overhead**: Negligible (indexed by file_hash)

**Verdict**: Overhead is acceptable for the value provided.

## Implementation Details

### Service API

```python
class ProvenanceTracker:
    def track_file_parse(
        self,
        file_path: str,
        content: str,
        parser_version: str
    ) -> FileProvenance:
        """Record that a file was parsed."""
        
    def is_file_stale(
        self,
        file_path: str,
        current_content: str
    ) -> bool:
        """Check if graph data is stale compared to current file."""
        
    def get_provenance(self, file_path: str) -> FileProvenance | None:
        """Retrieve provenance metadata for a file."""
```

### Integration Example

```python
# In definition processor
provenance = tracker.track_file_parse(
    file_path=file_path,
    content=source_code,
    parser_version="1.0.0"
)

# Add to graph node properties
function_node.properties.update({
    "file_hash": provenance.file_hash,
    "parsed_at": provenance.parsed_at.isoformat(),
    "parser_version": provenance.parser_version
})
```

### Graph Schema Addition

New properties on all nodes:
- `file_hash: string` (indexed)
- `parsed_at: string` (ISO 8601 timestamp)
- `parser_version: string`

## Testing

- **Unit tests**: `codebase_rag/tests/test_provenance_tracker.py`
- **Coverage**: 18 tests covering:
  - File hashing accuracy
  - Staleness detection
  - Metadata storage/retrieval
  - Edge cases (missing files, changed content)

## Future Work

1. **Incremental Updates**: Use provenance to skip unchanged files during re-parse
2. **Garbage Collection**: Remove stale nodes automatically
3. **Provenance Queries**: Cypher queries like "show files parsed > 30 days ago"
4. **Parser Compatibility**: Detect nodes from incompatible parser versions

## References

- Implementation: `codebase_rag/services/provenance_tracker.py`
- Tests: `codebase_rag/tests/test_provenance_tracker.py`
- Parent ADR: [ADR-001: Data Integrity Initiative](ADR-001-data-integrity-initiative.md)
