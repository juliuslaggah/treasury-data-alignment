from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

import pandas as pd
from pandas.errors import EmptyDataError

from app.core.exceptions import FileValidationError


@dataclass(frozen=True, slots=True)
class MasterRegister:
    """A loaded master account register with duplicate indicators."""

    source_path: Path
    sheet_name: str
    accounts: pd.DataFrame

    @property
    def source_name(self) -> str:
        """Return the source workbook filename."""

        return self.source_path.name

    @property
    def account_count(self) -> int:
        """Return the number of master-account entries."""

        return len(self.accounts.index)

    @property
    def duplicate_count(self) -> int:
        """Return the number of rows involved in duplication."""

        return int(self.accounts["IS DUPLICATE"].sum())

    @property
    def has_duplicates(self) -> bool:
        """Return whether duplicate master accounts exist."""

        return self.duplicate_count > 0

    @property
    def duplicates(self) -> pd.DataFrame:
        """Return every master row involved in duplication."""

        duplicate_mask = self.accounts["IS DUPLICATE"].astype(bool)

        return (
            self.accounts.loc[duplicate_mask]
            .copy()
            .reset_index(drop=True)
        )


class MasterRegisterLoader:
    """Load the standard DBP account list from an Excel workbook."""

    _SUPPORTED_EXTENSIONS = {".xlsx", ".xls"}
    _IGNORED_VALUES = {
        "",
        "DBP",
        "ACCOUNT NAME",
        "DAILY BAL",
    }

    def load(self, source_path: Path) -> MasterRegister:
        """Load and analyse the DBP master-account section."""

        path = source_path.expanduser().resolve()
        file_type = self._validate_source(path)
        workbook = self._read_workbook(path, file_type)

        master_location = self._find_dbp_section(workbook)

        if master_location is None:
            raise FileValidationError(
                "The DBP master section could not be identified.",
                details={"filename": path.name},
            )

        sheet_name, table, label_row, account_column = master_location
        accounts = self._extract_accounts(
            table,
            label_row,
            account_column,
        )

        if accounts.empty:
            raise FileValidationError(
                "The DBP master section does not contain any accounts.",
                details={
                    "filename": path.name,
                    "sheet_name": sheet_name,
                },
            )

        # Preserve the worksheet location for duplicate resolution.
        accounts["SHEET NAME"] = sheet_name

        accounts["IS DUPLICATE"] = accounts[
            "NORMALIZED ACCOUNT NAME"
        ].duplicated(keep=False)

        return MasterRegister(
            source_path=path,
            sheet_name=sheet_name,
            accounts=accounts,
        )

    @classmethod
    def _validate_source(
        cls,
        path: Path,
    ) -> Literal["xlsx", "xls"]:
        """Validate the master workbook path and extension."""

        if not path.exists():
            raise FileValidationError(
                "The master workbook does not exist.",
                details={"path": str(path)},
            )

        if not path.is_file():
            raise FileValidationError(
                "The selected master path is not a file.",
                details={"path": str(path)},
            )

        extension = path.suffix.lower()

        if extension not in cls._SUPPORTED_EXTENSIONS:
            raise FileValidationError(
                "The master register must be an Excel workbook.",
                details={
                    "filename": path.name,
                    "allowed_extensions": sorted(
                        cls._SUPPORTED_EXTENSIONS
                    ),
                },
            )

        if path.stat().st_size == 0:
            raise FileValidationError(
                "The master workbook is empty.",
                details={"filename": path.name},
            )

        return cast(
            Literal["xlsx", "xls"],
            extension.removeprefix("."),
        )

    @staticmethod
    def _read_workbook(
        path: Path,
        file_type: Literal["xlsx", "xls"],
    ) -> dict[str, pd.DataFrame]:
        """Read every workbook sheet without converting cells."""

        engine: Literal["openpyxl", "xlrd"] = (
            "openpyxl" if file_type == "xlsx" else "xlrd"
        )

        try:
            workbook: dict[str, pd.DataFrame] = pd.read_excel(
                path,
                sheet_name=None,
                header=None,
                dtype=str,
                keep_default_na=False,
                engine=engine,
            )
        except (
            EmptyDataError,
            OSError,
            ValueError,
            ImportError,
        ) as exc:
            raise FileValidationError(
                "The master workbook could not be read.",
                details={
                    "filename": path.name,
                    "reason": str(exc),
                },
            ) from exc

        return workbook

    @classmethod
    def _find_dbp_section(
        cls,
        workbook: dict[str, pd.DataFrame],
    ) -> tuple[str, pd.DataFrame, int, int] | None:
        """Locate the DBP label and its account-name column."""

        for sheet_name, table in workbook.items():
            for row_number in range(len(table.index)):
                for column_number in range(len(table.columns)):
                    value = table.iat[
                        row_number,
                        column_number,
                    ]

                    if cls._normalise_name(value) == "DBP":
                        return (
                            sheet_name,
                            table,
                            row_number,
                            column_number,
                        )

        return None

    @classmethod
    def _extract_accounts(
        cls,
        table: pd.DataFrame,
        label_row: int,
        account_column: int,
    ) -> pd.DataFrame:
        """Extract master accounts below the DBP section label."""

        extracted_rows: list[dict[str, object]] = []

        for row_number in range(
            label_row + 1,
            len(table.index),
        ):
            raw_name = table.iat[
                row_number,
                account_column,
            ]
            account_name = cls._clean_display_name(raw_name)
            normalised_name = cls._normalise_name(raw_name)

            if normalised_name in cls._IGNORED_VALUES:
                continue

            extracted_rows.append(
                {
                    "MASTER ROW": row_number + 1,
                    "ACCOUNT NAME": account_name,
                    "NORMALIZED ACCOUNT NAME": normalised_name,
                }
            )

        return pd.DataFrame(
            extracted_rows,
            columns=[
                "MASTER ROW",
                "ACCOUNT NAME",
                "NORMALIZED ACCOUNT NAME",
            ],
        )

    @staticmethod
    def _cell_to_text(value: object) -> str:
        """Convert a cell to safe text."""

        if bool(pd.isna(cast(Any, value))):
            return ""

        return str(value).replace("\ufeff", "").strip()

    @classmethod
    def _clean_display_name(
        cls,
        value: object,
    ) -> str:
        """Clean spacing while retaining the displayed account name."""

        return " ".join(cls._cell_to_text(value).split())

    @classmethod
    def _normalise_name(
        cls,
        value: object,
    ) -> str:
        """Create a case-insensitive account-name matching key."""

        return cls._clean_display_name(value).upper()

    