# Implementation Plan: Data Integrity & Provenance

## Overview

This document outlines the implementation roadmap for adding data provenance, validation, and consistency checking to Code-Graph-RAG. The plan follows TDD methodology and SOLID principles throughout.

---

## Timeline Summary

| Phase | Duration | Focus | Status |
|-------|----------|-------|--------|
| **Phase 1** | Week 1-2 | Data Provenance | 🔄 Not Started |
| **Phase 2** | Week 3 | Consistency Validation | 🔄 Not Started |
| **Phase 3** | Week 4 | Contract-by-Design | 🔄 Not Started |
| **Phase 4** | Week 5 | Testing & Integration | 🔄 Not Started |

---

## Phase 1: Data Provenance (Week 1-2)

### Goal
Add source type classification and provenance metadata to all indexed content.

### Deliverables

| Deliverable | Description | Owner |
|-------------|-------------|-------|
| `FileClassifier` | Classify files by extension/path patterns | - |
| `ProvenanceTracker` | Track parse timestamps and file mtimes | - |
| Schema extensions | Add provenance fields to File, Module nodes | - |
| Query filtering | Enable filtering by source_type | - |

### Milestones

#### Week 1: FileClassifier

| Day | Task | Output |
|-----|------|--------|
| 1 | Write tests for FileClassifier | `test_file_classifier.py` |
| 2 | Implement FileClassifier | `file_classifier.py` |
| 3 | Add classification patterns | DOC, TEST, CONFIG patterns |
| 4 | Integrate with StructureProcessor | Modified `structure_processor.py` |
| 5 | Verify integration | Passing tests |

#### Week 2: ProvenanceTracker

| Day | Task | Output |
|-----|------|--------|
| 1 | Write tests for ProvenanceTracker | `test_provenance_tracker.py` |
| 2 | Implement ProvenanceTracker | `provenance_tracker.py` |
| 3 | Update schema definitions | Modified `types_defs.py` |
| 4 | Add query filtering | Cypher query support |
| 5 | End-to-end verification | Integration tests pass |

### Success Criteria
- [ ] All File nodes have `source_type` field
- [ ] Classification accuracy > 95% on test corpus
- [ ] `parsed_at` timestamps on all new nodes
- [ ] Query filtering by source type works

---

## Phase 2: Consistency Validation (Week 3)

### Goal
Implement relationship validation and integrity checking.

### Deliverables

| Deliverable | Description | Owner |
|-------------|-------------|-------|
| `ValidationEngine` | Verify relationship targets exist | - |
| `ConsistencyChecker` | Cross-validate imports/exports | - |
| `ConfidenceScorer` | Score call resolution confidence | - |
| Validation report | Generate integrity reports | - |

### Milestones

| Day | Task | Output |
|-----|------|--------|
| 1 | Write tests for ConfidenceScorer | `test_confidence_scorer.py` |
| 2 | Implement ConfidenceScorer | `confidence_scorer.py` |
| 3 | Integrate with CallResolver | Modified `call_resolver.py` |
| 4 | Write tests for ValidationEngine | `test_validation_engine.py` |
| 5 | Implement ValidationEngine | `validation_engine.py` |

### Success Criteria
- [ ] All CALLS relationships have `confidence` field
- [ ] Resolution method tracked for all calls
- [ ] Validation failures logged with context
- [ ] Orphan relationships reported

---

## Phase 3: Contract-by-Design (Week 4)

### Goal
Enforce invariants through Python's type system using Pydantic and Protocols.

### Deliverables

| Deliverable | Description | Owner |
|-------------|-------------|-------|
| Protocol definitions | ISP-compliant interfaces | - |
| Pydantic models | Validated node/relationship models | - |
| Result types | Explicit error handling | - |
| Immutable value objects | Thread-safe data structures | - |

### Milestones

| Day | Task | Output |
|-----|------|--------|
| 1 | Define Protocol hierarchy | `protocols/*.py` |
| 2 | Create Pydantic node models | `models/nodes.py` |
| 3 | Create Pydantic relationship models | `models/relationships.py` |
| 4 | Implement Result types | `models/results.py` |
| 5 | Migrate existing code | Updated processors |

### Success Criteria
- [ ] All new code uses Protocol-based interfaces
- [ ] Pydantic validation catches invalid data
- [ ] No type errors in new code (pyright clean)
- [ ] Immutable value objects used where appropriate

---

## Phase 4: Testing & Integration (Week 5)

### Goal
Comprehensive test coverage and SOLID principle verification.

### Deliverables

| Deliverable | Description | Owner |
|-------------|-------------|-------|
| Unit tests | > 90% coverage on new code | - |
| Integration tests | End-to-end validation | - |
| Property-based tests | Edge case coverage | - |
| Performance benchmarks | Regression prevention | - |

### Milestones

| Day | Task | Output |
|-----|------|--------|
| 1 | Complete unit test suite | All tests passing |
| 2 | Add integration tests | `tests/integration/` |
| 3 | Add property-based tests | Hypothesis tests |
| 4 | Performance benchmarking | Baseline metrics |
| 5 | Documentation & review | Final review pass |

### Success Criteria
- [ ] > 90% test coverage on new code
- [ ] All integration tests passing
- [ ] Performance regression < 5%
- [ ] Documentation complete

---

## Dependencies

### External Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| `pydantic` | ^2.0 | Model validation |
| `hypothesis` | ^6.0 | Property-based testing |
| `pytest-benchmark` | ^4.0 | Performance testing |

### Internal Dependencies

```
Phase 1 ──► Phase 2 ──► Phase 3 ──► Phase 4
   │           │           │
   │           └───────────┼─── Uses provenance metadata
   │                       │
   └───────────────────────┴─── Uses Protocol definitions
```

---

## Risk Mitigation

### Risk 1: Schema Migration Breaking Existing Graphs

**Mitigation:**
- Use additive schema changes only (add fields, don't remove)
- All new fields have defaults
- Provide migration script for backfilling

### Risk 2: Performance Impact from Validation

**Mitigation:**
- Make validation pass optional (configurable)
- Run validation asynchronously where possible
- Add caching for repeated validations

### Risk 3: Breaking Changes to Query Patterns

**Mitigation:**
- Maintain backward compatibility layer
- Document query changes
- Version query API

### Risk 4: Scope Creep

**Mitigation:**
- Strict milestone definitions
- Weekly checkpoint reviews
- Defer non-critical features to future phases

---

## Resource Estimates

### Engineering Time

| Phase | Effort (days) | Complexity |
|-------|---------------|------------|
| Phase 1 | 10 | Medium |
| Phase 2 | 5 | Medium-High |
| Phase 3 | 5 | High |
| Phase 4 | 5 | Medium |
| **Total** | **25** | - |

### Infrastructure

- No new infrastructure required
- Existing Memgraph instance sufficient
- CI/CD changes minimal (add new test suites)

---

## Acceptance Criteria (Overall)

### Functional
- [ ] File classification works for all supported languages
- [ ] Call resolution tracks confidence scores
- [ ] Validation catches missing relationship targets
- [ ] Queries can filter by source type and confidence

### Non-Functional
- [ ] Performance: < 5% regression on indexing time
- [ ] Test coverage: > 90% on new code
- [ ] Documentation: All new APIs documented
- [ ] Type safety: pyright clean on new code

### Quality Gates

| Gate | Criteria | Blocker? |
|------|----------|----------|
| Unit tests | All pass | Yes |
| Integration tests | All pass | Yes |
| Type checking | pyright clean | Yes |
| Coverage | > 90% new code | No |
| Performance | < 5% regression | No |

---

## Next Steps

1. **Review ARCHITECTURE_ANALYSIS.md** - Confirm gap analysis is complete
2. **Create PHASE_1_PROVENANCE.md** - Detail Week 1-2 implementation
3. **Set up development branch** - `feature/data-integrity`
4. **Begin TDD cycle** - Start with `test_file_classifier.py`

---

**Document Status:** Draft  
**Last Updated:** 2026-01-03  
**Author:** Architecture Team
