# Feature: Validation Engine

**Status:** Implemented (Wave 2)  
**Related ADR:** [ADR-003: Wave 2 - Validation Engine](../_internal/adr/ADR-003-wave-2-validation-engine.md)

## Overview

The validation engine audits the knowledge graph for data quality issues, detects orphaned nodes, validates relationships, and generates actionable reports. This ensures graph integrity and catches parser errors before they affect queries.

## What Problem Does This Solve?

Before validation engine:
- ❌ Orphaned nodes existed undetected (functions without parent modules)
- ❌ Invalid relationships pointed to non-existent nodes
- ❌ Parser errors were silent (no reports generated)
- ❌ No metrics on graph health
- ❌ Debugging was trial-and-error

After validation engine:
- ✅ Detect all orphaned nodes with file paths
- ✅ Find invalid relationships with source/target info
- ✅ Generate actionable reports with node IDs
- ✅ Track metrics by severity (errors vs warnings)
- ✅ Fail CI/CD builds on validation errors

## How It Works

### Validation Rules

#### Critical Errors (Block Production)

| Rule | Description | Impact |
|------|-------------|--------|
| **Orphaned Functions** | Function nodes without parent Module | Breaks module queries |
| **Orphaned Classes** | Class nodes without parent Module | Breaks class listing |
| **Invalid CALLS** | CALLS relationship with missing target | Breaks call graph analysis |
| **Invalid INHERITS** | INHERITS relationship with missing parent | Breaks inheritance queries |

#### Warnings (Quality Issues)

| Rule | Description | Impact |
|------|-------------|--------|
| **Missing Docstrings** | Public functions without documentation | Reduces code quality |
| **Incomplete Metadata** | Nodes missing provenance properties | Limits audit trail |

### Report Structure

```python
@dataclass
class ValidationReport:
    errors: list[Issue]           # Critical issues
    warnings: list[Issue]         # Quality issues
    metrics: ValidationMetrics    # Issue counts by type
    timestamp: datetime           # When validated

@dataclass
class Issue:
    severity: Literal["error", "warning"]
    rule: str                     # e.g., "orphaned_function"
    node_id: str                  # Memgraph node ID
    message: str                  # Human-readable description
    file_path: str | None         # Source file (if known)
```

## Usage Examples

### Basic Validation

```python
from codebase_rag.services.validation_engine import ValidationEngine

# Initialize with Memgraph connection
engine = ValidationEngine(connection=graph_connection)

# Run all validation rules
report = engine.validate_graph()

# Check results
if report.errors:
    print(f"❌ Found {len(report.errors)} critical errors")
    for error in report.errors:
        print(f"  - {error.message}")
        print(f"    Node: {error.node_id}")
        print(f"    File: {error.file_path}")
else:
    print("✅ No critical errors found")

if report.warnings:
    print(f"⚠️  Found {len(report.warnings)} warnings")
```

### Validate Specific Rules

```python
# Only check for orphaned nodes
orphans = engine.find_orphans()
print(f"Found {len(orphans)} orphaned nodes")

# Only validate relationships
invalid_rels = engine.validate_relationships()
print(f"Found {len(invalid_rels)} invalid relationships")
```

### Get Metrics

```python
# Get validation metrics
metrics = engine.get_metrics()

print(f"Total issues: {metrics.total_issues}")
print(f"Errors: {metrics.error_count}")
print(f"Warnings: {metrics.warning_count}")
print(f"Orphaned functions: {metrics.orphaned_functions}")
print(f"Invalid relationships: {metrics.invalid_relationships}")
```

### CLI Usage

```bash
# Validate during graph update
cgr start --repo-path /my/repo --update-graph --validate

# Validate existing graph
cgr validate --output report.json

# Fail on errors (for CI/CD)
cgr validate --fail-on-errors
```

## Example Report

```
╔══════════════════════════════════════════════════════════╗
║          VALIDATION REPORT - 2025-01-03 14:30:00        ║
╚══════════════════════════════════════════════════════════╝

ERRORS (3):
───────────
  ❌ [orphaned_function] Function "parse_args" has no parent Module
     Node ID: 12345
     File: src/cli.py:45

  ❌ [invalid_calls] CALLS relationship references non-existent target
     Source Node: 67890
     Target: <missing>

  ❌ [orphaned_class] Class "User" has no parent Module
     Node ID: 11111
     File: models/user.py:10

WARNINGS (5):
─────────────
  ⚠️  [missing_docstring] Public function "helper" lacks docstring
     Node ID: 22222
     File: utils/helpers.py:78

  ⚠️  [incomplete_metadata] Node missing provenance properties
     Node ID: 33333
     File: old_code/legacy.py:100

  ... (3 more warnings)

SUMMARY:
────────
  Total Issues: 8
  Errors: 3 ❌ (require immediate attention)
  Warnings: 5 ⚠️  (quality improvements)

╔══════════════════════════════════════════════════════════╗
║  ❌ VALIDATION FAILED - Fix errors before deployment     ║
╚══════════════════════════════════════════════════════════╝
```

## Integration Points

### 1. CLI Integration

Built into the CLI workflow:

```bash
# Validate automatically after parsing
cgr start --repo-path . --update-graph --validate
```

### 2. CI/CD Integration

Fail builds on validation errors:

```yaml
# .github/workflows/validate.yml
- name: Parse and Validate Codebase
  run: |
    cgr start --repo-path . --update-graph
    cgr validate --fail-on-errors --output report.json

- name: Upload Validation Report
  uses: actions/upload-artifact@v3
  if: failure()
  with:
    name: validation-report
    path: report.json
```

### 3. Pre-Commit Hook

Run validation before committing graph updates:

```bash
# .git/hooks/pre-commit
#!/bin/bash
cgr validate --fail-on-errors || {
  echo "❌ Validation failed - fix errors before committing"
  exit 1
}
```

## Performance Impact

Measured on different graph sizes:

| Graph Size | Validation Time | Memory Usage |
|------------|-----------------|--------------|
| 1,000 nodes | ~1 second | 10 MB |
| 10,000 nodes | ~10 seconds | 50 MB |
| 100,000 nodes | ~90 seconds | 200 MB |

**Optimization:** Validation runs asynchronously and doesn't block parsing.

## Benefits

### 1. Data Quality Visibility
Know exactly what's wrong with your graph:
- Which nodes are orphaned
- Which relationships are invalid
- Where to find problematic code

### 2. Actionable Reports
Reports include:
- Node IDs for direct Cypher queries
- File paths for code inspection
- Clear error messages for fixing

### 3. CI Integration
Prevent bad data from reaching production:
- Fail builds on critical errors
- Track warnings for quality trends
- Store reports as artifacts

### 4. Regression Prevention
Catch parser bugs early:
- Tests validate expected structure
- CI catches unexpected changes
- Historical reports track quality over time

### 5. Debug Support
Faster issue resolution:
- Pinpoint exact problematic nodes
- Trace errors to source files
- Identify patterns in failures

## Advanced Usage

### Custom Validation Rules

Add project-specific rules:

```python
class CustomValidator(ValidationEngine):
    def validate_naming_conventions(self) -> list[Issue]:
        """Ensure functions follow project naming conventions."""
        issues = []
        
        # Query for functions not following snake_case
        results = self.connection.execute("""
            MATCH (f:Function)
            WHERE NOT f.name =~ '^[a-z_][a-z0-9_]*$'
            RETURN id(f) as node_id, f.name as name, f.file_path as path
        """)
        
        for row in results:
            issues.append(Issue(
                severity="warning",
                rule="naming_convention",
                node_id=row["node_id"],
                message=f"Function '{row['name']}' doesn't follow snake_case",
                file_path=row["path"]
            ))
        
        return issues
```

### Programmatic Report Handling

```python
# Generate report
report = engine.validate_graph()

# Filter errors by type
orphan_errors = [
    e for e in report.errors 
    if "orphaned" in e.rule
]

# Export to JSON
import json
with open("validation_report.json", "w") as f:
    json.dump(report.to_dict(), f, indent=2)

# Send alerts for critical errors
if report.errors:
    send_slack_alert(
        channel="#code-quality",
        message=f"❌ {len(report.errors)} validation errors detected"
    )
```

## Limitations

### 1. Performance on Large Graphs
- Validation takes ~90 seconds on 100K nodes
- Consider incremental validation (future work)

### 2. False Positives Possible
- Some warnings may be incorrect for edge cases
- Custom rules needed for project-specific patterns

### 3. No Auto-Repair
- Engine only detects issues, doesn't fix them
- Auto-repair is future work

## Future Enhancements

### 1. Auto-Repair
Automatically fix orphan nodes by inferring relationships:

```python
# Detect orphaned function
orphan = find_orphan(function_id)

# Infer parent module from file path
module = infer_module_from_path(orphan.file_path)

# Create missing relationship
create_relationship(module, "DEFINES", orphan)
```

### 2. Custom Rules API
User-defined validation rules:

```python
@validation_rule(severity="warning")
def check_test_coverage(node):
    """Ensure public functions have tests."""
    if node.label == "Function" and is_public(node):
        if not has_test(node):
            return Issue(...)
```

### 3. Historical Tracking
Store reports over time for trend analysis:

```python
# Track validation metrics over time
store_report(report, timestamp=now)

# Query historical trends
trends = get_validation_trends(days=30)
plot_quality_graph(trends)
```

### 4. Incremental Validation
Only validate changed nodes:

```python
# Only check nodes modified since last validation
changed_nodes = get_changed_nodes(since=last_validation_time)
report = engine.validate_nodes(changed_nodes)
```

## Testing

Comprehensive test coverage in `codebase_rag/tests/test_validation_engine.py`:

- ✅ Orphan detection (functions, classes)
- ✅ Relationship validation (CALLS, INHERITS)
- ✅ Report generation and formatting
- ✅ Metrics calculation
- ✅ Edge cases (empty graph, circular refs)
- ✅ CLI integration

**Run tests:**
```bash
uv run pytest codebase_rag/tests/test_validation_engine.py -v
```

## References

- **Implementation:** `codebase_rag/services/validation_engine.py`
- **Tests:** `codebase_rag/tests/test_validation_engine.py`
- **ADR:** [ADR-003: Wave 2 - Validation Engine](../_internal/adr/ADR-003-wave-2-validation-engine.md)
- **Parent ADR:** [ADR-001: Data Integrity Initiative](../_internal/adr/ADR-001-data-integrity-initiative.md)
- **Related:** [Provenance Tracking](provenance-tracking.md)
