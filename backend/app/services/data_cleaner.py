from decimal import Decimal, InvalidOperation
from typing import Any, cast

import pandas as pd

from app.core.exceptions import DataCleaningError
from app.models.report import (
    BALANCE_COLUMNS,
    COUNT_COLUMNS,
    IDENTIFIER_COLUMNS,
    SUMMARY_ROW_LABELS,
    CleanedReport,
    IngestedReport,
)


class DataCleaner:
    """Clean ingested treasury data without mutating the source report."""

    def clean(self, report: IngestedReport) -> CleanedReport:
        """Clean account data and separate report-summary rows."""

        working_data = report.data.copy(deep=True)

        account_indices: list[Any] = []
        summary_indices: list[Any] = []

        for row_index, row in working_data.iterrows():
            if self._is_summary_row(row):
                summary_indices.append(row_index)
            else:
                account_indices.append(row_index)

        account_rows = working_data.loc[account_indices].copy()
        summary_rows = working_data.loc[summary_indices].copy()

        cleaned_accounts = self._clean_frame(
            account_rows,
            report.header_row_number,
        )
        cleaned_summary_rows = self._clean_frame(
            summary_rows,
            report.header_row_number,
        )

        return CleanedReport(
            source_report=report,
            accounts=cleaned_accounts,
            summary_rows=cleaned_summary_rows,
            warnings=report.warnings,
        )

    @classmethod
    def _clean_frame(
        cls,
        frame: pd.DataFrame,
        header_row_number: int,
    ) -> pd.DataFrame:
        """Clean text, count and balance fields in a copied table."""

        cleaned = frame.copy(deep=True)

        for column in IDENTIFIER_COLUMNS:
            cleaned[column] = cleaned[column].map(
                cls._normalise_identifier
            )

        cleaned["ACCOUNT NAME"] = cleaned["ACCOUNT NAME"].map(
            cls._normalise_account_name
        )

        for column in COUNT_COLUMNS:
            cleaned[column] = [
                cls._parse_count(
                    value,
                    column=column,
                    row_number=header_row_number + position + 1,
                )
                for position, value in enumerate(
                    cleaned[column].tolist()
                )
            ]

        for column in BALANCE_COLUMNS:
            cleaned_balances = [
                cls._parse_balance(
                    value,
                    column=column,
                    row_number=header_row_number + position + 1,
                )
                for position, value in enumerate(
                    cleaned[column].tolist()
                )
            ]

            cleaned[column] = pd.Series(
                cleaned_balances,
                index=cleaned.index,
                dtype="object",
            )

        return cleaned.reset_index(drop=True)

    @classmethod
    def _is_summary_row(
        cls,
        row: pd.Series[Any],
    ) -> bool:
        """Return whether a row is a report-level summary record."""

        possible_labels = (
            row.get("T24 ACCOUNT", ""),
            row.get("ACCOUNT NAME", ""),
        )

        normalised_summary_labels = {
            cls._normalise_label(label)
            for label in SUMMARY_ROW_LABELS
        }

        return any(
            cls._normalise_label(value)
            in normalised_summary_labels
            for value in possible_labels
            if cls._normalise_identifier(value)
        )

    @staticmethod
    def _normalise_identifier(value: object) -> str:
        """Strip identifiers while preserving leading zeros."""

        if bool(pd.isna(cast(Any, value))):
            return ""

        return str(value).strip()

    @classmethod
    def _normalise_account_name(
        cls,
        value: object,
    ) -> str:
        """Collapse repeated whitespace in an account name."""

        text = cls._normalise_identifier(value)

        return " ".join(text.split())

    @classmethod
    def _normalise_label(cls, value: object) -> str:
        """Create a case-insensitive representation of a row label."""

        text = cls._normalise_account_name(value)

        return text.upper()

    @classmethod
    def _parse_count(
        cls,
        value: object,
        *,
        column: str,
        row_number: int,
    ) -> int:
        """Convert a transaction-count value to a non-negative integer."""

        text = cls._prepare_numeric_text(value)

        if not text:
            return 0

        try:
            number = Decimal(text)
        except InvalidOperation as exc:
            raise DataCleaningError(
                "Invalid transaction count.",
                details={
                    "column": column,
                    "row_number": row_number,
                    "value": str(value),
                },
            ) from exc

        if not number.is_finite():
            raise DataCleaningError(
                "Invalid transaction count.",
                details={
                    "column": column,
                    "row_number": row_number,
                    "value": str(value),
                },
            )

        if (
            number != number.to_integral_value()
            or number < 0
        ):
            raise DataCleaningError(
                "Invalid transaction count.",
                details={
                    "column": column,
                    "row_number": row_number,
                    "value": str(value),
                },
            )

        return int(number)

    @classmethod
    def _parse_balance(
        cls,
        value: object,
        *,
        column: str,
        row_number: int,
    ) -> Decimal:
        """Convert a financial value to an exact Decimal."""

        text = cls._prepare_numeric_text(value)

        if not text:
            return Decimal("0")

        try:
            number = Decimal(text)
        except InvalidOperation as exc:
            raise DataCleaningError(
                "Invalid financial value.",
                details={
                    "column": column,
                    "row_number": row_number,
                    "value": str(value),
                },
            ) from exc

        if not number.is_finite():
            raise DataCleaningError(
                "Invalid financial value.",
                details={
                    "column": column,
                    "row_number": row_number,
                    "value": str(value),
                },
            )

        return number

    @classmethod
    def _prepare_numeric_text(
        cls,
        value: object,
    ) -> str:
        """Remove source formatting without changing numeric meaning."""

        text = cls._normalise_identifier(value)

        if not text:
            return ""

        text = (
            text.strip("'")
            .replace(",", "")
            .replace(" ", "")
        )

        if text.startswith("(") and text.endswith(")"):
            text = f"-{text[1:-1]}"

        return text


    