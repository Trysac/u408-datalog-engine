"""Typed errors for datalog-engine."""

from __future__ import annotations


class DatalogError(Exception):
    """Base exception for datalog-engine errors with a stable machine-readable code."""

    def __init__(self, message: str, code: str) -> None:
        # Ensure error messages never exceed 200 characters
        safe_message = message[:200] if len(message) > 200 else message
        super().__init__(safe_message)
        self.code = code


class ParseError(DatalogError):
    """Raised when Datalog syntax is invalid or arity limit is exceeded."""

    def __init__(self, message: str, code: str = "syntax_error") -> None:
        super().__init__(message, code=code)


class SafetyError(DatalogError):
    """Raised when a rule contains unsafe variables."""

    def __init__(self, message: str, code: str = "unsafe_variable") -> None:
        super().__init__(message, code=code)


class StratificationError(DatalogError):
    """Raised when negation or aggregate stratification fails."""

    def __init__(self, message: str, code: str = "stratification_cycle") -> None:
        super().__init__(message, code=code)


class ProgramLimitError(DatalogError):
    """Raised when resource bounds such as program size or iteration limit are exceeded."""

    def __init__(self, message: str, code: str = "program_size_exceeded") -> None:
        super().__init__(message, code=code)
