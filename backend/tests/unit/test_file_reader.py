from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from app.core.exceptions import FileValidationError
from app.models.report import REQUIRED_REPORT_COLUMNS
from app.services.file_reader import ReportFileReader


def sample_report_rows() -> list[list[str]]:
    """Return a minimal treasury report with identifiers containing leading zeros."""

    return [
        ["BANK OF SIERRA LEONE", "", "", "", "", "", "", "", "", ""],
        ["TREASURY ACCOUNT BALANCES", "", "", "", "", "", "", "", "", ""],
        ["AS AT", "01 JUL 2026", "", "", "", "", "", "", "", ""],
        list(REQUIRED_REPORT_COLUMNS),
        [
            "0111001255",
            "001100501",
            "000001011100125595",
            "TREASURY MAIN",
            "1",
            "'-30,000,000.00'",
            "1",
            "540,426,742.46",
            "510,426,742.46",
            "'-2,650,948,097.36'",
        ],
    ]


def test_read_csv_preserves_leading_zeros(tmp_path: Path) -> None:
    """CSV ingestion must preserve account identifiers exactly as supplied."""

    source = tmp_path / "treasury_report.csv"
    pd.DataFrame(sample_report_rows()).to_csv(source, header=False, index=False)

    report = ReportFileReader().read(source)

    assert report.file_type == "csv"
    assert report.report_date == date(2026, 7, 1)
    assert report.header_row_number == 4
    assert report.row_count == 1
    assert tuple(report.data.columns) == REQUIRED_REPORT_COLUMNS
    assert report.data.loc[0, "T24 ACCOUNT"] == "0111001255"
    assert report.data.loc[0, "LEGACY NO"] == "001100501"
    assert report.data.loc[0, "BBAN NO"] == "000001011100125595"


def test_read_xlsx_preserves_leading_zeros(tmp_path: Path) -> None:
    """Excel ingestion must preserve account identifiers as text."""

    source = tmp_path / "treasury_report.xlsx"
    pd.DataFrame(sample_report_rows()).to_excel(
        source,
        header=False,
        index=False,
        engine="openpyxl",
    )

    report = ReportFileReader().read(source)

    assert report.file_type == "xlsx"
    assert report.report_date == date(2026, 7, 1)
    assert report.row_count == 1
    assert report.data.loc[0, "T24 ACCOUNT"] == "0111001255"
    assert report.data.loc[0, "LEGACY NO"] == "001100501"
    assert report.data.loc[0, "BBAN NO"] == "000001011100125595"


def test_reject_unsupported_file_type(tmp_path: Path) -> None:
    """Files outside the approved formats must be rejected."""

    source = tmp_path / "treasury_report.txt"
    source.write_text("unsupported", encoding="utf-8")

    with pytest.raises(FileValidationError, match="Unsupported file type"):
        ReportFileReader().read(source)


def test_reject_report_without_required_header(tmp_path: Path) -> None:
    """A report without the complete treasury header must be rejected."""

    source = tmp_path / "invalid_report.csv"
    pd.DataFrame([["ACCOUNT", "BALANCE"], ["001", "100"]]).to_csv(
        source,
        header=False,
        index=False,
    )

    with pytest.raises(FileValidationError, match="required report header"):
        ReportFileReader().read(source)

    