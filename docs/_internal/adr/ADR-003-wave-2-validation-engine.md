# ADR-003: Wave 2 - Validation Engine

**Status:** Accepted  
**Date:** 2025-01-03  
**Parent ADR:** [ADR-001: Data Integrity Initiative](ADR-001-data-integrity-initiative.md)

## Context

After implementing provenance tracking (Wave 1), we had metadata about parsed files but no way to validate the quality of the resulting graph data. Common issues included:

1. **Orphaned Nodes**: Functions/classes with no parent module or file
2. **Invalid Relationships**: References to non-existent nodes
3. **Silent Failures**: Parser errors that didn't prevent graph updates
4. **Data Quality Unknown**: No metrics or reports on graph health

These issues made debugging difficult and reduced confidence in the graph's accuracy.

## Decision

Implement a **ValidationEngine** service that:

1. **Validates Relationships**: Ensures source and target nodes exist
2. **Detects Orphans**: Finds nodes without required parent relationships
3. **Generates Reports**: Produces actionable reports with node IDs and file paths
4. **Provides Metrics**: Counts issues by severity (error, warning)

### Validation Rules

#### Critical (Errors)
- **Orphaned Functions**: Function nodes without a parent Module
- **Orphaned Classes**: Class nodes without a parent Module
- **Invalid CALLS**: CALLS relationships with missing source or target
- **Invalid INHERITS**: INHERITS relationships with missing parent class

#### Warnings
- **Missing Docstrings**: Public functions without documentation
- **Incomplete Metadata**: Nodes missing expected provenance properties

## Rationale

### Why Post-Parse Validation?

**Alternatives considered:**

1. **Inline Validation During Parsing**
   - **Rejected**: Mixes concerns, makes parsers complex, can't validate cross-file relationships
   
2. **Pre-Commit Validation**
   - **Rejected**: Too late, data already in graph
   
3. **Post-Parse Validation** (chosen)
   - Can validate complete graph including cross-file relationships
   - Separates concerns (parsers focus on extraction, validator on correctness)
   - Can run on existing graphs for auditing

### Why Two Severity Levels?

- **Errors**: Data integrity issues that break graph queries
- **Warnings**: Quality issues that don't prevent functionality

This separation allows users to:
- Fail CI/CD on errors but not warnings
- Prioritize fixing critical issues first
- Track quality metrics over time

## Consequences

### Positive

- **Data Quality Visibility**: Know exactly what's wrong with the graph
- **Actionable Reports**: Reports include node IDs and file paths for fixing
- **CI Integration**: Can fail builds on validation errors
- **Regression Prevention**: Catch parser bugs before they reach production

### Negative

- **Performance Cost**: Full graph validation takes ~10 seconds on 10K nodes
- **False Positives**: Some warnings may be incorrect for edge cases
- **Maintenance**: Validation rules need updates when graph schema changes

### Performance Impact

Measured on 10,000 node graph:
- **Validation time**: 8-12 seconds (depends on rule complexity)
- **Memory usage**: ~50MB for validation state
- **Storage**: Reports are ~100KB for typical findings

**Optimization**: Validation runs async, doesn't block parsing.

## Implementation Details

### Service API

```python
class ValidationEngine:
    def validate_graph(self) -> ValidationReport:
        """Run all validation rules and generate report."""
        
    def validate_relationships(self) -> list[Issue]:
        """Check all relationships for dangling references."""
        
    def find_orphans(self) -> list[Issue]:
        """Find nodes without required parent relationships."""
        
    def get_metrics(self) -> ValidationMetrics:
        """Get counts of issues by severity."""
```

### Report Structure

```python
@dataclass
class ValidationReport:
    errors: list[Issue]           # Critical issues
    warnings: list[Issue]         # Quality issues
    metrics: ValidationMetrics    # Counts by type
    timestamp: datetime           # When validated
    
@dataclass
class Issue:
    severity: Literal["error", "warning"]
    rule: str                     # e.g., "orphaned_function"
    node_id: str                  # Memgraph node ID
    message: str                  # Human-readable description
    file_path: str | None         # Source file (if known)
```

### Example Report

```
Validation Report (2025-01-03 14:30:00)
=======================================

ERRORS (3):
  - [orphaned_function] Function "parse_args" (node:12345) has no parent Module
    File: src/cli.py:45
  - [invalid_calls] CALLS relationship references non-existent target
    Source: node:67890
  - [orphaned_class] Class "User" (node:11111) has no parent Module
    File: models/user.py:10

WARNINGS (5):
  - [missing_docstring] Public function "helper" (node:22222) lacks docstring
    File: utils/helpers.py:78
  - ...

SUMMARY:
  Total Issues: 8
  Errors: 3
  Warnings: 5
```

## Integration

### In CLI

```bash
# Validate after parsing
cgr start --repo-path /my/repo --update-graph --validate

# Validate existing graph
cgr validate --output report.json
```

### In CI/CD

```yaml
- name: Validate Graph
  run: |
    cgr start --repo-path . --update-graph
    cgr validate --fail-on-errors
```

## Testing

- **Unit tests**: `codebase_rag/tests/test_validation_engine.py`
- **Coverage**: 25 tests covering:
  - Orphan detection (functions, classes)
  - Relationship validation (CALLS, INHERITS)
  - Report generation
  - Metrics calculation
  - Edge cases (empty graph, circular references)

## Future Work

1. **Auto-Repair**: Fix orphans by inferring parent relationships
2. **Custom Rules**: User-defined validation rules
3. **Historical Tracking**: Store validation reports over time for trend analysis
4. **Performance**: Incremental validation (only check changed nodes)
5. **Integration**: Webhook notifications on validation failures

## References

- Implementation: `codebase_rag/services/validation_engine.py`
- Tests: `codebase_rag/tests/test_validation_engine.py`
- Parent ADR: [ADR-001: Data Integrity Initiative](ADR-001-data-integrity-initiative.md)
- Related: [ADR-002: Wave 1 - Provenance Tracking](ADR-002-wave-1-provenance-tracking.md)
