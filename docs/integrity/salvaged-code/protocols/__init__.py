"""Protocol interfaces for dependency injection."""

from .provenance import FileClassifierProtocol, ProvenanceTrackerProtocol
from .validation import ConfidenceScorerProtocol, ValidationEngineProtocol

__all__ = [
    "ConfidenceScorerProtocol",
    "FileClassifierProtocol",
    "ProvenanceTrackerProtocol",
    "ValidationEngineProtocol",
]
