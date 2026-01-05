# Feature: Provenance Tracking

**Status:** Implemented (Wave 1)  
**Related ADR:** [ADR-002: Wave 1 - Provenance Tracking](../_internal/adr/ADR-002-wave-1-provenance-tracking.md)

## Overview

Provenance tracking records metadata about when and how files were parsed into the knowledge graph. This enables staleness detection, audit trails, and future incremental update capabilities.

## What Problem Does This Solve?

Before provenance tracking:
- ❌ No way to know if graph data is outdated
- ❌ Can't detect when files changed since last parse
- ❌ No audit trail for debugging parsing issues
- ❌ Full re-parse required even for unchanged files

After provenance tracking:
- ✅ Detect stale graph data by comparing file hashes
- ✅ Know exactly when each file was last parsed
- ✅ Track which parser version created each node
- ✅ Foundation for incremental updates (skip unchanged files)

## How It Works

### File Metadata Captured

For every parsed file, we record:

| Field | Type | Purpose |
|-------|------|---------|
| `file_path` | string | Absolute path to source file |
| `file_hash` | string | SHA-256 hash of file content |
| `mtime` | float | Last modified timestamp (Unix epoch) |
| `parsed_at` | datetime | When we parsed this file |
| `parser_version` | string | Parser version that created the node |

### Metadata Storage

Provenance metadata is stored directly on graph nodes as properties:

```cypher
CREATE (f:Function {
  name: "parse_args",
  qualified_name: "cli.parse_args",
  file_path: "/src/cli.py",
  file_hash: "a3d5e...",           // SHA-256 hash
  parsed_at: "2025-01-03T14:30:00Z",
  parser_version: "1.0.0"
})
```

### Staleness Detection

Check if a file has changed since last parse:

```python
from codebase_rag.services.provenance_tracker import ProvenanceTracker

tracker = ProvenanceTracker()

# Check if file is stale
is_stale = tracker.is_file_stale(
    file_path="/src/main.py",
    current_content=open("/src/main.py").read()
)

if is_stale:
    print("File changed since last parse - needs update")
else:
    print("File unchanged - can skip parsing")
```

## Usage Examples

### Track File Parsing

```python
from codebase_rag.services.provenance_tracker import ProvenanceTracker

tracker = ProvenanceTracker()

# When parsing a file
provenance = tracker.track_file_parse(
    file_path="/project/src/utils.py",
    content=source_code,
    parser_version="1.2.0"
)

# Access metadata
print(f"File hash: {provenance.file_hash}")
print(f"Parsed at: {provenance.parsed_at}")
print(f"Parser version: {provenance.parser_version}")
```

### Check Staleness

```python
# Before re-parsing, check if file changed
with open("/project/src/utils.py") as f:
    current_content = f.read()

if tracker.is_file_stale("/project/src/utils.py", current_content):
    # File changed - re-parse it
    parse_file("/project/src/utils.py")
else:
    # File unchanged - skip parsing
    print("Skipping unchanged file")
```

### Query Provenance Metadata

```python
# Get provenance for a specific file
provenance = tracker.get_provenance("/project/src/utils.py")

if provenance:
    print(f"Last parsed: {provenance.parsed_at}")
    print(f"File modified: {datetime.fromtimestamp(provenance.mtime)}")
else:
    print("File not yet parsed")
```

## Integration Points

Provenance tracking is integrated into:

1. **Definition Processor** (`codebase_rag/parsers/definition_processor.py`)
   - Tracks provenance when creating Function/Class nodes
   - Adds metadata to node properties

2. **Structure Processor** (`codebase_rag/parsers/structure_processor.py`)
   - Tracks provenance when creating Module/Package nodes
   - Adds metadata to node properties

3. **Graph Nodes** (Memgraph)
   - All parsed nodes include provenance properties
   - Properties are indexed for fast staleness queries

## Performance Impact

Measured on a 1000-file codebase:

| Metric | Value | Impact |
|--------|-------|--------|
| Hash computation | ~5ms per file | Negligible |
| Total hashing time | ~5 seconds | Acceptable |
| Storage overhead | ~200 bytes per node | Minimal |
| Query overhead | Negligible | Indexed by hash |

**Verdict:** Performance overhead is acceptable for the value provided.

## Benefits

### 1. Staleness Detection
Identify outdated graph data by comparing current file hash with stored hash.

### 2. Audit Trail
Full history of when files were parsed and by which parser version.

### 3. Debug Support
Track down parsing issues to specific parser versions and timestamps.

### 4. Incremental Updates (Future)
Foundation for skipping unchanged files during re-parse operations.

### 5. Content-Based Detection
SHA-256 hashing detects changes reliably even when:
- File timestamps are wrong (common in CI/CD)
- Files are copied (preserves mtime)
- Clock skew or timezone issues exist

## Limitations

### 1. Migration Required
Existing nodes (parsed before Wave 1) don't have provenance metadata. Options:
- Full re-parse to add metadata
- Backfill script (future work)

### 2. No Historical Tracking
Only stores latest parse metadata. If you need full history:
- Use git for source file history
- Implement provenance versioning (future work)

### 3. Parser Version Compatibility
No automatic handling of incompatible parser versions. Manual intervention required if:
- Parser changes node structure
- Parser changes relationship types
- Breaking changes in parsing logic

## Future Enhancements

### 1. Incremental Updates
Use provenance to skip unchanged files during re-parse:

```python
# Pseudo-code for future feature
for file_path in all_files:
    if not tracker.is_file_stale(file_path, current_content):
        continue  # Skip unchanged file
    parse_file(file_path)  # Only parse changed files
```

### 2. Garbage Collection
Automatically remove stale nodes:

```cypher
// Find nodes from deleted files
MATCH (n {file_path: $path})
WHERE NOT file_exists($path)
DETACH DELETE n
```

### 3. Provenance Queries
Cypher queries for provenance analytics:

```cypher
// Files parsed more than 30 days ago
MATCH (n)
WHERE datetime(n.parsed_at) < datetime() - duration({days: 30})
RETURN n.file_path, n.parsed_at

// Count nodes by parser version
MATCH (n)
RETURN n.parser_version, count(n) AS node_count
ORDER BY node_count DESC
```

### 4. Parser Compatibility Checks
Detect and warn about nodes from incompatible parser versions:

```python
if provenance.parser_version != CURRENT_VERSION:
    if not is_compatible(provenance.parser_version):
        logger.warning(
            f"Node from incompatible parser {provenance.parser_version}"
        )
```

## Testing

Comprehensive test coverage in `codebase_rag/tests/test_provenance_tracker.py`:

- ✅ File hash computation accuracy
- ✅ Staleness detection (changed/unchanged files)
- ✅ Metadata storage and retrieval
- ✅ Edge cases (missing files, empty content)
- ✅ Parser version tracking
- ✅ Timestamp accuracy

**Run tests:**
```bash
uv run pytest codebase_rag/tests/test_provenance_tracker.py -v
```

## References

- **Implementation:** `codebase_rag/services/provenance_tracker.py`
- **Tests:** `codebase_rag/tests/test_provenance_tracker.py`
- **ADR:** [ADR-002: Wave 1 - Provenance Tracking](../_internal/adr/ADR-002-wave-1-provenance-tracking.md)
- **Parent ADR:** [ADR-001: Data Integrity Initiative](../_internal/adr/ADR-001-data-integrity-initiative.md)
