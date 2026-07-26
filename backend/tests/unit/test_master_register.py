from pathlib import Path

import pandas as pd
import pytest

from app.core.exceptions import FileValidationError
from app.services.master_register import MasterRegisterLoader


def create_master_workbook(
    path: Path,
    account_names: list[str],
) -> None:
    """Create a workbook matching the April standard-list structure."""

    rows: list[list[str]] = [
        ["", "", "", ""],
        ["DOWNLOAD", "", "", "DBP"],
        ["", "", "", ""],
        ["ACCOUNT NAME", "DAILY BAL", "", ""],
    ]

    rows.extend(
        ["", "", "", account_name]
        for account_name in account_names
    )

    pd.DataFrame(rows).to_excel(
        path,
        sheet_name="Sheet1",
        header=False,
        index=False,
        engine="openpyxl",
    )


def test_load_master_register_preserves_order_and_positions(
    tmp_path: Path,
) -> None:
    """The loader must preserve order, rows and worksheet names."""

    source = tmp_path / "April 1, 2026.xlsx"
    create_master_workbook(
        source,
        [
            "TREASURY MAIN",
            "INCOME TAX TREAS AC",
            "CUSTOMS AND EXCISE TREAS AC",
        ],
    )

    register = MasterRegisterLoader().load(source)

    assert register.account_count == 3
    assert register.sheet_name == "Sheet1"
    assert register.accounts["MASTER ROW"].tolist() == [5, 6, 7]
    assert register.accounts["SHEET NAME"].tolist() == [
        "Sheet1",
        "Sheet1",
        "Sheet1",
    ]
    assert register.accounts["ACCOUNT NAME"].tolist() == [
        "TREASURY MAIN",
        "INCOME TAX TREAS AC",
        "CUSTOMS AND EXCISE TREAS AC",
    ]
    assert register.has_duplicates is False
    assert register.duplicate_count == 0


def test_load_master_register_detects_normalised_duplicates(
    tmp_path: Path,
) -> None:
    """Case and repeated spaces must not hide duplicate accounts."""

    source = tmp_path / "April 1, 2026.xlsx"
    create_master_workbook(
        source,
        [
            "SIERRA LEONE STANDARD BUREAU DISBUR",
            "TREASURY MAIN",
            "  sierra   leone standard bureau disbur  ",
        ],
    )

    register = MasterRegisterLoader().load(source)

    assert register.has_duplicates is True
    assert register.duplicate_count == 2
    assert register.duplicates["MASTER ROW"].tolist() == [5, 7]
    assert register.duplicates["SHEET NAME"].tolist() == [
        "Sheet1",
        "Sheet1",
    ]
    assert set(
        register.duplicates["NORMALIZED ACCOUNT NAME"]
    ) == {
        "SIERRA LEONE STANDARD BUREAU DISBUR"
    }


def test_load_master_register_rejects_missing_dbp_section(
    tmp_path: Path,
) -> None:
    """A workbook without the standard DBP section must be rejected."""

    source = tmp_path / "invalid_master.xlsx"

    pd.DataFrame(
        [["NOT A MASTER REGISTER"]]
    ).to_excel(
        source,
        header=False,
        index=False,
        engine="openpyxl",
    )

    with pytest.raises(
        FileValidationError,
        match="DBP master section",
    ):
        MasterRegisterLoader().load(source)


def test_load_master_register_rejects_empty_account_list(
    tmp_path: Path,
) -> None:
    """The DBP section must contain at least one account."""

    source = tmp_path / "empty_master.xlsx"
    create_master_workbook(source, [])

    with pytest.raises(
        FileValidationError,
        match="does not contain any accounts",
    ):
        MasterRegisterLoader().load(source)

    