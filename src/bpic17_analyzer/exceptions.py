"""Domain-specific exceptions used by the BPIC17 analyzer."""


class BPIC17AnalyzerError(Exception):
    """Base exception for application-level errors."""


class DatasetLoadError(BPIC17AnalyzerError):
    """Raised when an XES file cannot be loaded."""


class DatasetValidationError(BPIC17AnalyzerError):
    """Raised when an event log does not satisfy required data constraints."""


class AnalysisPrerequisiteError(BPIC17AnalyzerError):
    """Raised when an analysis needs an attribute that is not available."""
