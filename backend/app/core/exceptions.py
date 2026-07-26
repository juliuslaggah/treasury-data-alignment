from collections.abc import Mapping
from typing import Any


class ApplicationError(Exception):
    """Base exception for controlled application errors."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str,
        status_code: int = 500,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = dict(details or {})


class FileValidationError(ApplicationError):
    """Raised when an uploaded file fails validation."""

    def __init__(
        self,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code="FILE_VALIDATION_ERROR",
            status_code=400,
            details=details,
        )


class DataCleaningError(ApplicationError):
    """Raised when source data cannot be cleaned safely."""

    def __init__(
        self,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code="DATA_CLEANING_ERROR",
            status_code=422,
            details=details,
        )


class DuplicateAccountError(ApplicationError):
    """Raised when duplicate accounts prevent reliable alignment."""

    def __init__(
        self,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code="DUPLICATE_ACCOUNT_ERROR",
            status_code=409,
            details=details,
        )


class AccountAlignmentError(ApplicationError):
    """Raised when account alignment cannot be completed safely."""

    def __init__(
        self,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code="ACCOUNT_ALIGNMENT_ERROR",
            status_code=422,
            details=details,
        )


class ExportError(ApplicationError):
    """Raised when an output workbook cannot be generated."""

    def __init__(
        self,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code="EXPORT_ERROR",
            status_code=500,
            details=details,
        )

