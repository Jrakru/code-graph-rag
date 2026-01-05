# ADR-001: Data Integrity Initiative

**Status:** Accepted  
**Date:** 2025-01-03  
**Decision Makers:** Project Team  
**Related Waves:** Wave 1, Wave 2, Wave 3, Wave 4

## Context

The codebase graph system parses multi-language repositories and builds knowledge graphs in Memgraph. As the system grew to support multiple languages and complex codebases, we identified critical gaps in data quality, traceability, and reliability:

1. **No Provenance Tracking**: No way to trace when files were parsed, detect stale data, or invalidate outdated graph nodes
2. **Silent Data Quality Issues**: Invalid relationships and orphaned nodes existed without detection or reporting
3. **Loose Type Safety**: Domain objects lacked validation, leading to runtime errors and inconsistent data
4. **Insufficient Test Coverage**: Core services lacked comprehensive unit and integration tests

These issues affected system reliability, debugging capability, and confidence in the graph data quality.

## Decision

We decided to implement a **four-wave data integrity initiative** to systematically address these gaps:

### Wave 1: Provenance Tracking
Implement file-level metadata tracking to enable:
- Detection of stale or outdated graph data
- Audit trails for debugging
- Future incremental update capabilities

### Wave 2: Validation Engine
Build a validation layer to:
- Detect orphaned nodes and invalid relationships
- Report data quality issues
- Prevent silent failures

### Wave 3: Contracts & Models
Establish type-safe contracts using:
- Protocol definitions for service interfaces
- Pydantic models for data validation
- Confidence scoring and file classification services

### Wave 4: Testing Infrastructure
Achieve comprehensive test coverage:
- Unit tests for all new services
- Integration tests for end-to-end workflows
- Regression prevention

## Rationale

### Why This Approach?

**Incremental Delivery**: Breaking the initiative into waves allowed us to:
- Deliver value incrementally
- Test each layer independently
- Adjust based on learnings from previous waves

**Foundation First**: We started with provenance and validation (Waves 1-2) before contracts (Wave 3) because:
- Services need metadata before they can validate it
- Type safety is most valuable once core functionality exists

**Test Last**: Wave 4 came last because:
- Tests require stable interfaces (from Waves 1-3)
- Testing validates the entire system integration

### Alternative Approaches Considered

1. **Big Bang Refactor**: Implement everything at once
   - **Rejected**: Too risky, no incremental value, harder to review
   
2. **Type Safety First**: Start with Pydantic models before services
   - **Rejected**: Without concrete use cases, models would be over-engineered or miss requirements

3. **Skip Provenance Tracking**: Only implement validation
   - **Rejected**: Validation without provenance can't detect staleness or support incremental updates

## Consequences

### Positive

- **Data Quality**: Validation engine catches issues that were previously silent
- **Debuggability**: Provenance tracking enables audit trails and stale data detection
- **Type Safety**: Pydantic models prevent invalid data at creation time
- **Confidence**: 78 passing unit tests provide regression protection
- **Maintainability**: Clean protocols enable future extension

### Negative

- **Complexity**: Added new services and abstractions
- **Migration Effort**: Existing code needed updates to use new services
- **Performance Overhead**: Validation and provenance tracking add compute cost (measured as acceptable)

### Risks

- **Incomplete Integration**: Not all parsers use provenance tracking yet (ongoing work)
- **Test Maintenance**: Tests need updates as system evolves

## Implementation Summary

### Wave 1: Provenance Tracking
- **Service**: `ProvenanceTracker`
- **Location**: `codebase_rag/services/provenance_tracker.py`
- **Integrated in**: Definition processor, structure processor

### Wave 2: Validation Engine
- **Service**: `ValidationEngine`
- **Location**: `codebase_rag/services/validation_engine.py`
- **Features**: Orphan detection, relationship validation

### Wave 3: Contracts & Models
- **Protocols**: 4 protocol definitions in `codebase_rag/protocols/`
- **Models**: Base, nodes, relationships in `codebase_rag/models/`
- **Services**: `FileClassifier`, `ConfidenceScorer` in `codebase_rag/services/`

### Wave 4: Testing Infrastructure
- **Unit Tests**: 78 tests across 5 test files
- **Integration Tests**: 5 tests (1 passing, 4 skipped for future work)
- **Test Files**:
  - `test_provenance_tracker.py`
  - `test_validation_engine.py`
  - `test_file_classifier.py`
  - `test_confidence_scorer.py`
  - `test_models.py`

## References

- Implementation details: See `docs/features/`
- Branch strategy: `BRANCH_STRATEGY.md`
- Test results: Run `make test` to see current status
