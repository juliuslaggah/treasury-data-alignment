from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Final, Literal

import pandas as pd

from app.services.account_matcher import AlignmentResult

ValidationSeverity = Literal["ERROR", "WARNING"]

BALANCE_COLUMNS: Final[tuple[str, ...]] = (
    "DEBIT BAL",
    "CREDIT BAL",
    "DAILY BAL",
    "LEDGER BALANCE",
)


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """A single issue discovered during validation."""

    code: str
    message: str
    severity: ValidationSeverity
    row_count: int = 0


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Complete result of validating an account alignment."""

    issues: tuple[ValidationIssue, ...]

    @property
    def is_valid(self) -> bool:
        """Return whether validation completed without errors."""

        return not any(
            issue.severity == "ERROR"
            for issue in self.issues
        )

    @property
    def error_count(self) -> int:
        """Return the number of error-level validation issues."""

        return sum(
            issue.severity == "ERROR"
            for issue in self.issues
        )

    @property
    def warning_count(self) -> int:
        """Return the number of warning-level validation issues."""

        return sum(
            issue.severity == "WARNING"
            for issue in self.issues
        )

    def has_issue(self, code: str) -> bool:
        """Return whether a validation issue has the supplied code."""

        return any(
            issue.code == code
            for issue in self.issues
        )


class DataValidator:
    """Validate an alignment before an Excel report is exported."""

    def validate(
        self,
        source_accounts: pd.DataFrame,
        alignment: AlignmentResult,
    ) -> ValidationResult:
        """Run all validation rules against an alignment result."""

        issues: list[ValidationIssue] = []

        self._validate_unmatched_source(
            alignment,
            issues,
        )
        self._validate_unmatched_master(
            alignment,
            issues,
        )
        self._validate_source_reuse(
            alignment,
            issues,
        )

        if alignment.unmatched_source.empty:
            self._validate_balance_reconciliation(
                source_accounts,
                alignment,
                issues,
            )

        return ValidationResult(issues=tuple(issues))

    @staticmethod
    def _validate_unmatched_source(
        alignment: AlignmentResult,
        issues: list[ValidationIssue],
    ) -> None:
        """Report source accounts that were not aligned."""

        unmatched_count = alignment.unmatched_source_count

        if unmatched_count == 0:
            return

        account_names: list[str] = []

        if "ACCOUNT NAME" in alignment.unmatched_source.columns:
            for value in alignment.unmatched_source[
                "ACCOUNT NAME"
            ].tolist():
                if value is None or value is pd.NA:
                    continue

                if isinstance(value, float) and pd.isna(value):
                    continue

                account_name = str(value).strip()

                if (
                    account_name
                    and account_name not in account_names
                ):
                    account_names.append(account_name)

        message = (
            f"{unmatched_count} source account(s) could not be "
            "matched to the master register."
        )

        if account_names:
            names = ", ".join(account_names)
            message = (
                f"{unmatched_count} source account(s) could not be "
                f"matched to the master register: {names}."
            )

        issues.append(
            ValidationIssue(
                code="UNMATCHED_SOURCE_ACCOUNT",
                message=message,
                severity="ERROR",
                row_count=unmatched_count,
            )
        )

    @staticmethod
    def _validate_unmatched_master(
        alignment: AlignmentResult,
        issues: list[ValidationIssue],
    ) -> None:
        """Report master accounts without a corresponding source row."""

        unmatched_count = alignment.unmatched_master_count

        if unmatched_count == 0:
            return

        issues.append(
            ValidationIssue(
                code="UNMATCHED_MASTER_ACCOUNT",
                message=(
                    f"{unmatched_count} master account(s) have no "
                    "corresponding source account."
                ),
                severity="WARNING",
                row_count=unmatched_count,
            )
        )

    @staticmethod
    def _validate_source_reuse(
        alignment: AlignmentResult,
        issues: list[ValidationIssue],
    ) -> None:
        """Ensure a source row was not assigned more than once."""

        if alignment.aligned.empty:
            return

        if "SOURCE INDEX" not in alignment.aligned.columns:
            return

        source_indexes = alignment.aligned["SOURCE INDEX"].dropna()

        duplicate_indexes = source_indexes[
            source_indexes.duplicated(keep=False)
        ]

        if duplicate_indexes.empty:
            return

        duplicate_count = int(duplicate_indexes.nunique())

        issues.append(
            ValidationIssue(
                code="SOURCE_ACCOUNT_REUSED",
                message=(
                    f"{duplicate_count} source account(s) were assigned "
                    "to more than one master account."
                ),
                severity="ERROR",
                row_count=duplicate_count,
            )
        )

    def _validate_balance_reconciliation(
        self,
        source_accounts: pd.DataFrame,
        alignment: AlignmentResult,
        issues: list[ValidationIssue],
    ) -> None:
        """Ensure source and aligned financial totals remain equal."""

        mismatched_columns: list[str] = []

        for column in BALANCE_COLUMNS:
            if column not in source_accounts.columns:
                continue

            if column not in alignment.aligned.columns:
                source_total = self._sum_decimal_column(
                    source_accounts,
                    column,
                )

                if source_total != Decimal("0"):
                    mismatched_columns.append(column)

                continue

            source_total = self._sum_decimal_column(
                source_accounts,
                column,
            )
            aligned_total = self._sum_decimal_column(
                alignment.aligned,
                column,
            )

            if source_total != aligned_total:
                mismatched_columns.append(column)

        if not mismatched_columns:
            return

        columns = ", ".join(mismatched_columns)

        issues.append(
            ValidationIssue(
                code="BALANCE_RECONCILIATION_FAILED",
                message=(
                    "Source and aligned balance totals do not agree for: "
                    f"{columns}."
                ),
                severity="ERROR",
                row_count=len(mismatched_columns),
            )
        )

    def _sum_decimal_column(
        self,
        frame: pd.DataFrame,
        column: str,
    ) -> Decimal:
        """Calculate an exact Decimal total for a DataFrame column."""

        total = Decimal("0")

        for value in frame[column].tolist():
            total += self._to_decimal(value)

        return total

    @staticmethod
    def _to_decimal(value: object) -> Decimal:
        """Convert a scalar financial value to Decimal safely."""

        if value is None or value is pd.NA:
            return Decimal("0")

        if isinstance(value, float) and pd.isna(value):
            return Decimal("0")

        if isinstance(value, Decimal):
            return value

        cleaned_value = str(value).strip().replace(",", "")

        if not cleaned_value:
            return Decimal("0")

        try:
            return Decimal(cleaned_value)
        except InvalidOperation:
            return Decimal("0")


    