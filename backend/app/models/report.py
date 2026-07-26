from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

import pandas as pd

ReportFileType = Literal["csv", "xlsx", "xls"]

REQUIRED_REPORT_COLUMNS: tuple[str, ...] = (
    "T24 ACCOUNT",
    "LEGACY NO",
    "BBAN NO",
    "ACCOUNT NAME",
    "DR.CNT",
    "DEBIT BAL",
    "CR.CNT",
    "CREDIT BAL",
    "DAILY BAL",
    "LEDGER BALANCE",
)

IDENTIFIER_COLUMNS: tuple[str, ...] = (
    "T24 ACCOUNT",
    "LEGACY NO",
    "BBAN NO",
)

COUNT_COLUMNS: tuple[str, ...] = (
    "DR.CNT",
    "CR.CNT",
)

BALANCE_COLUMNS: tuple[str, ...] = (
    "DEBIT BAL",
    "CREDIT BAL",
    "DAILY BAL",
    "LEDGER BALANCE",
)

SUMMARY_ROW_LABELS: tuple[str, ...] = (
    "TREASURY TOTAL (INCL. WAYS AND MEANS):",
    "TREASURY TOTAL (EXCL. WAYS AND MEANS):",
    "WAYS AND MEANS:",
    "NET BALANCE ON TREASURY ACCOUNTS:",
)


@dataclass(frozen=True, slots=True)
class IngestedReport:
    """A validated report returned by the file-ingestion layer."""

    source_path: Path
    file_type: ReportFileType
    report_date: date | None
    header_row_number: int
    data: pd.DataFrame
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Ensure that every ingested report satisfies the data contract."""

        available_columns = {
            str(column)
            for column in self.data.columns
        }
        missing_columns = (
            set(REQUIRED_REPORT_COLUMNS) - available_columns
        )

        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            message = (
                "Ingested report is missing required columns: "
                f"{missing}"
            )
            raise ValueError(message)

        if self.header_row_number < 1:
            message = "The header row number must be one or greater."
            raise ValueError(message)

    @property
    def source_name(self) -> str:
        """Return the original source filename."""

        return self.source_path.name

    @property
    def row_count(self) -> int:
        """Return the number of ingested data rows."""

        return len(self.data.index)


@dataclass(frozen=True, slots=True)
class CleanedReport:
    """A cleaned report with account and summary rows separated."""

    source_report: IngestedReport
    accounts: pd.DataFrame
    summary_rows: pd.DataFrame
    warnings: tuple[str, ...] = ()

    @property
    def account_count(self) -> int:
        """Return the number of cleaned account records."""

        return len(self.accounts.index)

    @property
    def summary_row_count(self) -> int:
        """Return the number of separated report-summary rows."""

        return len(self.summary_rows.index)
    
