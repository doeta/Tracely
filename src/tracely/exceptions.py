"""Domain-specific exceptions used by Tracely."""


class TracelyError(Exception):
    """Base exception for application-level errors."""


# Backward-compatible alias
BPIC17AnalyzerError = TracelyError


class DatasetLoadError(TracelyError):
    """Raised when an XES file cannot be loaded."""


class DatasetValidationError(TracelyError):
    """Raised when an event log does not satisfy required data constraints."""


class AnalysisPrerequisiteError(TracelyError):
    """Raised when an analysis needs an attribute that is not available."""
