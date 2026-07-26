from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from app.core.exceptions import DataCleaningError
from app.models.report import IngestedReport
from app.services.data_cleaner import DataCleaner


def make_ingested_report(
    rows: list[dict[str, str]],
) -> IngestedReport:
    """Create an ingested report for cleaner tests."""

    return IngestedReport(
        source_path=Path("treasury_report.csv"),
        file_type="csv",
        report_date=date(2026, 7, 1),
        header_row_number=4,
        data=pd.DataFrame(rows),
    )


def account_row() -> dict[str, str]:
    """Return a representative raw account row."""

    return {
        "T24 ACCOUNT": "0111001255",
        "LEGACY NO": "001100501",
        "BBAN NO": "000001011100125595",
        "ACCOUNT NAME": "  TREASURY   MAIN  ",
        "DR.CNT": "1",
        "DEBIT BAL": "'-30,000,000.00'",
        "CR.CNT": "1",
        "CREDIT BAL": "540,426,742.46",
        "DAILY BAL": "510,426,742.46",
        "LEDGER BALANCE": "'-2,650,948,097.36'",
    }


def summary_row() -> dict[str, str]:
    """Return a representative report-summary row."""

    return {
        "T24 ACCOUNT": "TREASURY TOTAL (incl. Ways and Means):",
        "LEGACY NO": "",
        "BBAN NO": "",
        "ACCOUNT NAME": "",
        "DR.CNT": "407",
        "DEBIT BAL": "'-616,788,375.11'",
        "CR.CNT": "130",
        "CREDIT BAL": "616,788,375.11",
        "DAILY BAL": "0.00",
        "LEDGER BALANCE": "",
    }


def test_clean_converts_financial_values_and_preserves_identifiers() -> None:
    """Cleaning must convert values without damaging account identifiers."""

    source = make_ingested_report([account_row()])

    cleaned = DataCleaner().clean(source)
    account = cleaned.accounts.iloc[0]

    assert cleaned.account_count == 1
    assert cleaned.summary_row_count == 0
    assert account["T24 ACCOUNT"] == "0111001255"
    assert account["LEGACY NO"] == "001100501"
    assert account["BBAN NO"] == "000001011100125595"
    assert account["ACCOUNT NAME"] == "TREASURY MAIN"
    assert account["DR.CNT"] == 1
    assert account["CR.CNT"] == 1
    assert account["DEBIT BAL"] == Decimal("-30000000.00")
    assert account["CREDIT BAL"] == Decimal("540426742.46")
    assert account["DAILY BAL"] == Decimal("510426742.46")
    assert account["LEDGER BALANCE"] == Decimal("-2650948097.36")


def test_clean_separates_summary_rows_from_accounts() -> None:
    """Report totals must not remain in the account-level dataset."""

    source = make_ingested_report(
        [
            account_row(),
            summary_row(),
        ]
    )

    cleaned = DataCleaner().clean(source)

    assert cleaned.account_count == 1
    assert cleaned.summary_row_count == 1
    assert (
        cleaned.summary_rows.iloc[0]["T24 ACCOUNT"]
        == "TREASURY TOTAL (incl. Ways and Means):"
    )
    assert cleaned.summary_rows.iloc[0]["DR.CNT"] == 407
    assert cleaned.summary_rows.iloc[0]["DAILY BAL"] == Decimal("0.00")


def test_clean_does_not_modify_ingested_source() -> None:
    """Cleaning must not mutate the original ingested report."""

    source = make_ingested_report([account_row()])
    original = source.data.copy(deep=True)

    DataCleaner().clean(source)

    pd.testing.assert_frame_equal(source.data, original)


def test_clean_rejects_invalid_financial_value() -> None:
    """Invalid balances must be reported instead of silently replaced."""

    invalid_row = account_row()
    invalid_row["DAILY BAL"] = "not-a-number"
    source = make_ingested_report([invalid_row])

    with pytest.raises(
        DataCleaningError,
        match="Invalid financial value",
    ):
        DataCleaner().clean(source)

    