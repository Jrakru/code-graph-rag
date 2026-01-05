# Data Integrity & Provenance Documentation

This folder contains documentation for implementing data provenance, validation, and consistency checking in Code-Graph-RAG.

## Overview

Code-Graph-RAG indexes codebases into a knowledge graph for natural language querying. **Critical gap identified:** The system currently treats ALL indexed content as equally trustworthy—outdated README files are indexed with the same authority as actual source code.

This initiative adds:
1. **Data Provenance** - Track source reliability (code vs documentation)
2. **Consistency Validation** - Verify relationships point to real entities
3. **Contract-by-Design** - Enforce invariants through type system
4. **Comprehensive Testing** - TDD workflow with SOLID principles

## Documentation Structure

### Architecture
- [ARCHITECTURE_ANALYSIS.md](./ARCHITECTURE_ANALYSIS.md) - Current state analysis, gaps identified, and solution design
- [PLAN.md](./PLAN.md) - Implementation roadmap and milestones

### Implementation Phases

| Phase | Document | Timeline | Status |
|-------|----------|----------|--------|
| 1 | [PHASE_1_PROVENANCE.md](./PHASE_1_PROVENANCE.md) | Week 1-2 | 🔄 Not Started |
| 2 | [PHASE_2_VALIDATION.md](./PHASE_2_VALIDATION.md) | Week 3 | 🔄 Not Started |
| 3 | [PHASE_3_CONTRACTS.md](./PHASE_3_CONTRACTS.md) | Week 4 | 🔄 Not Started |
| 4 | [PHASE_4_TESTING.md](./PHASE_4_TESTING.md) | Week 5 | 🔄 Not Started |

### Phase Summary

#### Phase 1: Data Provenance Tracking
Add source type classification and confidence scoring:
- File classification (code, documentation, test, config)
- Node provenance fields (`source_type`, `parsed_at`, `confidence`)
- Relationship confidence tracking for call resolution
- Staleness detection for documentation

#### Phase 2: Consistency Validation
Implement relationship validation and integrity checks:
- Import resolution verification
- CALLS relationship target validation
- Schema validation for node properties
- Cross-file consistency checking

#### Phase 3: Contract-by-Design
Enforce invariants through Python's type system:
- Pydantic models with validators
- Protocol classes for interfaces (ISP)
- Result types for error handling
- Immutable value objects

#### Phase 4: Testing & SOLID Principles
Comprehensive TDD workflow:
- Unit tests for all new components
- Integration tests for validation pipeline
- Property-based testing for edge cases
- SOLID principle compliance verification

## Quick Reference

### Problem Statement

| Issue | Impact | Evidence |
|-------|--------|----------|
| No source distinction | Docs treated as code truth | `File` schema has no `source_type` |
| No confidence scores | Ambiguous resolutions unmarked | `CALLS` has no `confidence` field |
| No staleness tracking | Outdated docs returned | No `parsed_at` timestamp |
| Silent relationship failures | Missing call targets undetected | CALLS just don't get created |

### Proposed Solution

| Component | Purpose |
|-----------|---------|
| `FileClassifier` | Classify files by extension/name patterns |
| `ProvenanceTracker` | Track source reliability metadata |
| `ValidationEngine` | Verify relationship targets exist |
| `ConsistencyChecker` | Cross-validate imports/exports |

### Key Files (To Be Modified)

**Core Types:**
- `codebase_rag/types_defs.py` - Node schemas with provenance fields
- `codebase_rag/constants.py` - Source type enums

**Processors:**
- `codebase_rag/parsers/definition_processor.py` - Add provenance tracking
- `codebase_rag/parsers/call_processor.py` - Add confidence scoring
- `codebase_rag/parsers/call_resolver.py` - Track resolution method

**Services:**
- `codebase_rag/services/graph_service.py` - Validation hooks
- `codebase_rag/graph_updater.py` - Orchestration updates

### Design Principles

| Principle | Application |
|-----------|-------------|
| **SOLID - SRP** | Each class has one responsibility (FileClassifier, ValidationEngine, etc.) |
| **SOLID - OCP** | Validation rules are extensible without modifying core |
| **SOLID - LSP** | All validators implement common `Validator` protocol |
| **SOLID - ISP** | Separate protocols for classification, validation, tracking |
| **SOLID - DIP** | High-level modules depend on abstractions (Protocol classes) |
| **TDD** | Tests written BEFORE implementation (Red-Green-Refactor) |
| **Contract-by-Design** | Pydantic validators enforce invariants |

### Estimated Timeline

```
Week 1-2: Phase 1 - Data Provenance         🔄 Not Started
Week 3:   Phase 2 - Consistency Validation  🔄 Not Started
Week 4:   Phase 3 - Contract-by-Design      🔄 Not Started
Week 5:   Phase 4 - Testing & SOLID         🔄 Not Started
          ─────────────────────────────
Total:    5 weeks for full implementation
```

## Reports

See [reports/STATUS.md](./reports/STATUS.md) for detailed implementation status and task tracking.

## Related Documentation

- [Main README](../../README.md) - Project overview
- [CONTRIBUTING.md](../../CONTRIBUTING.md) - Contribution guidelines

## Architecture References

### Core Architecture Decisions

| Document | Description |
|----------|-------------|
| [types_defs.py](../../codebase_rag/types_defs.py) | Current node/relationship schemas |
| [graph_updater.py](../../codebase_rag/graph_updater.py) | Indexing orchestration |
| [call_resolver.py](../../codebase_rag/parsers/call_resolver.py) | Call resolution logic |

### Key Code Locations

| Component | Path | Purpose |
|-----------|------|---------|
| **Node Schemas** | `codebase_rag/types_defs.py` | NodeType, NODE_SCHEMAS, RELATIONSHIP_SCHEMAS |
| **Graph Updater** | `codebase_rag/graph_updater.py` | 4-pass indexing pipeline |
| **Definition Processor** | `codebase_rag/parsers/definition_processor.py` | AST parsing for definitions |
| **Call Processor** | `codebase_rag/parsers/call_processor.py` | Call extraction |
| **Call Resolver** | `codebase_rag/parsers/call_resolver.py` | Call target resolution |
| **Import Processor** | `codebase_rag/parsers/import_processor.py` | Import mapping |
| **Graph Service** | `codebase_rag/services/graph_service.py` | Memgraph operations |

### Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CURRENT INDEXING PIPELINE                             │
│                                                                              │
│   Pass 1: Structure    Pass 2: Definitions    Pass 3: Calls    Pass 4: Embed│
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐ ┌──────────┐│
│  │StructureProcessor│→│DefinitionProcess│→│  CallProcessor   │→│ Embedder ││
│  │                  │ │                  │ │  + CallResolver  │ │          ││
│  │ Packages/Folders │ │ Files/Modules    │ │  CALLS relations │ │ Vectors  ││
│  │                  │ │ Classes/Functions│ │                  │ │          ││
│  └──────────────────┘ └──────────────────┘ └──────────────────┘ └──────────┘│
│                                                                              │
│   ⚠️ NO PROVENANCE TRACKING AT ANY STAGE                                    │
│   ⚠️ NO VALIDATION OF RELATIONSHIP TARGETS                                  │
│   ⚠️ NO CONFIDENCE SCORING FOR RESOLUTIONS                                  │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                        PROPOSED ENHANCED PIPELINE                            │
│                                                                              │
│   Pass 1: Structure    Pass 2: Definitions    Pass 3: Calls    Pass 4: Valid│
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐ ┌──────────┐│
│  │StructureProcessor│→│DefinitionProcess│→│  CallProcessor   │→│Validation││
│  │ + FileClassifier │ │ + Provenance     │ │  + Confidence    │ │ Engine   ││
│  │                  │ │                  │ │                  │ │          ││
│  │ source_type      │ │ parsed_at        │ │ resolution_method│ │ verify   ││
│  │ is_documentation │ │ file_mtime       │ │ confidence       │ │ targets  ││
│  └──────────────────┘ └──────────────────┘ └──────────────────┘ └──────────┘│
│                                                                              │
│   ✅ PROVENANCE TRACKED FROM FILE CLASSIFICATION                            │
│   ✅ RELATIONSHIPS VALIDATED BEFORE COMMIT                                  │
│   ✅ CONFIDENCE SCORES FOR QUERY FILTERING                                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

**Document Maintainer:** Architecture Team  
**Last Updated:** 2026-01-03  
**Status:** 🔄 Planning
