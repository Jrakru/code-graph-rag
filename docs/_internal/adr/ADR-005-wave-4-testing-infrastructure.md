# ADR-005: Wave 4 - Testing Infrastructure

**Status:** Accepted  
**Date:** 2025-01-03  
**Parent ADR:** [ADR-001: Data Integrity Initiative](ADR-001-data-integrity-initiative.md)

## Context

After implementing provenance tracking (Wave 1), validation (Wave 2), and contracts/models (Wave 3), we had functional services but lacked comprehensive test coverage. This created risks:

1. **Regression Risk**: Changes could break existing functionality without detection
2. **Unclear Behavior**: Service behavior wasn't explicitly documented via tests
3. **Manual Testing**: Required manual verification after changes
4. **Integration Issues**: Cross-service interactions weren't tested

## Decision

Implement a **comprehensive testing infrastructure** covering:

1. **Unit Tests**: Test each service in isolation with mocked dependencies
2. **Integration Tests**: Test services working together end-to-end
3. **Test Coverage Goals**: 
   - Unit tests: 90%+ coverage for new services
   - Integration tests: Critical workflows covered
4. **Test Organization**: Mirror source structure in tests/

### Test Strategy

#### Unit Tests (Fast, Isolated)
- Mock external dependencies (Memgraph, file system)
- Focus on business logic
- Run in < 5 seconds total
- No Docker required

#### Integration Tests (Realistic, Slower)
- Use real Memgraph instance (Docker)
- Test actual database operations
- Run in < 30 seconds total
- Skip if Docker unavailable (CI flexibility)

## Rationale

### Why Both Unit and Integration Tests?

**Unit tests alone** would miss:
- Database query bugs
- Serialization issues
- Cross-service integration problems

**Integration tests alone** would be:
- Too slow for rapid feedback
- Hard to debug (many moving parts)
- Difficult to cover edge cases

**Combined approach** provides:
- Fast feedback (unit tests)
- Confidence in real behavior (integration tests)
- Clear failure localization

### Why Skip Integration Tests on Missing Docker?

**Reasoning**:
- CI environments may not have Docker
- Local development may not need full integration
- Unit tests provide most value anyway

**Implementation**:
```python
@pytest.mark.skipif(
    not is_docker_available(),
    reason="Docker not available"
)
def test_full_workflow():
    # Integration test requiring Memgraph
```

## Consequences

### Positive

- **Regression Prevention**: 78 tests catch breaking changes
- **Documentation**: Tests serve as usage examples
- **Refactoring Confidence**: Can safely change internals
- **Faster Development**: Tests catch bugs earlier than manual testing
- **CI Integration**: Automated testing on every PR

### Negative

- **Maintenance Burden**: Tests need updates when APIs change
- **Execution Time**: Full test suite takes 30 seconds
- **Complexity**: Need to maintain test fixtures and mocks
- **False Confidence**: Tests can pass but production can fail (test gaps)

### Test Coverage

Current coverage (Wave 4):
- **Unit tests**: 78 tests across 5 files
- **Integration tests**: 5 tests (1 passing, 4 skipped for future work)
- **Coverage**: 90%+ for new services

```bash
# Run all data integrity tests
uv run pytest codebase_rag/tests/test_provenance_tracker.py \
             codebase_rag/tests/test_validation_engine.py \
             codebase_rag/tests/test_file_classifier.py \
             codebase_rag/tests/test_confidence_scorer.py \
             codebase_rag/tests/test_models.py -v

# Result: 78 passed
```

## Implementation Details

### Test Organization

```
codebase_rag/tests/
├── conftest.py                     # Shared fixtures
├── test_provenance_tracker.py     # Unit tests (18 tests)
├── test_validation_engine.py      # Unit tests (25 tests)
├── test_file_classifier.py        # Unit tests (8 tests)
├── test_confidence_scorer.py      # Unit tests (7 tests)
├── test_models.py                 # Unit tests (20 tests)
└── integration/
    └── test_full_workflow.py      # Integration tests (5 tests)
```

### Example Unit Test

```python
def test_track_file_parse(provenance_tracker):
    """Test that file parsing is tracked correctly."""
    # Arrange
    file_path = "src/main.py"
    content = "def hello(): pass"
    parser_version = "1.0.0"
    
    # Act
    provenance = provenance_tracker.track_file_parse(
        file_path=file_path,
        content=content,
        parser_version=parser_version
    )
    
    # Assert
    assert provenance.file_path == file_path
    assert provenance.parser_version == parser_version
    assert provenance.file_hash is not None
    assert provenance.parsed_at <= datetime.now()
```

### Example Integration Test

```python
@pytest.mark.skipif(
    not is_docker_available(),
    reason="Docker not available"
)
def test_full_parsing_workflow(memgraph_connection):
    """Test full workflow: parse → track provenance → validate."""
    # Arrange
    repo_path = "/tmp/test_repo"
    create_test_repo(repo_path)
    
    # Act
    parse_repository(repo_path)
    report = validate_graph()
    
    # Assert
    assert report.errors == []
    assert len(report.warnings) < 5
    cleanup_test_repo(repo_path)
```

### Fixtures (conftest.py)

```python
@pytest.fixture
def provenance_tracker():
    """Provide a ProvenanceTracker instance."""
    return ProvenanceTracker()

@pytest.fixture
def validation_engine():
    """Provide a ValidationEngine with mocked graph connection."""
    mock_conn = MagicMock()
    return ValidationEngine(connection=mock_conn)

@pytest.fixture(scope="session")
def memgraph_connection():
    """Provide real Memgraph connection for integration tests."""
    if not is_docker_available():
        pytest.skip("Docker not available")
    
    conn = connect_to_memgraph()
    yield conn
    conn.close()
```

## Testing Principles

### 1. Arrange-Act-Assert Pattern

Every test follows AAA structure:

```python
def test_example():
    # Arrange - set up test data
    data = prepare_test_data()
    
    # Act - execute the behavior
    result = function_under_test(data)
    
    # Assert - verify outcome
    assert result == expected_value
```

### 2. Test One Thing Per Test

Bad:
```python
def test_everything():
    test_creation()
    test_validation()
    test_serialization()
```

Good:
```python
def test_creation(): ...
def test_validation(): ...
def test_serialization(): ...
```

### 3. Descriptive Test Names

Format: `test_<what>_<condition>_<expected>`

```python
def test_track_file_parse_with_valid_data_creates_provenance(): ...
def test_validate_graph_with_orphans_returns_errors(): ...
def test_classify_file_with_py_extension_returns_source_code(): ...
```

## CI Integration

### GitHub Actions Workflow

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      memgraph:
        image: memgraph/memgraph:latest
        ports:
          - 7687:7687
    
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: uv sync --extra test
      
      - name: Run unit tests
        run: make test
      
      - name: Run integration tests
        run: make test-integration
```

## Future Work

1. **Property-Based Testing**: Use Hypothesis for fuzzing
2. **Performance Tests**: Benchmark test suite for regressions
3. **Mutation Testing**: Verify test quality with mutation testing tools
4. **Coverage Tracking**: Integrate codecov for coverage reports
5. **Snapshot Testing**: Visual regression tests for reports
6. **Load Testing**: Simulate large codebases (100K+ nodes)

## References

- Unit tests:
  - `codebase_rag/tests/test_provenance_tracker.py`
  - `codebase_rag/tests/test_validation_engine.py`
  - `codebase_rag/tests/test_file_classifier.py`
  - `codebase_rag/tests/test_confidence_scorer.py`
  - `codebase_rag/tests/test_models.py`
- Integration tests: `codebase_rag/tests/integration/`
- Fixtures: `codebase_rag/tests/conftest.py`
- CI: `.github/workflows/tests.yml`
- Parent ADR: [ADR-001: Data Integrity Initiative](ADR-001-data-integrity-initiative.md)
