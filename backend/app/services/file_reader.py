import csv
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal, cast

import pandas as pd
from pandas.errors import EmptyDataError, ParserError

from app.core.config import get_settings
from app.core.exceptions import FileValidationError
from app.models.report import (
    REQUIRED_REPORT_COLUMNS,
    IngestedReport,
    ReportFileType,
)


class ReportFileReader:
    """Read and validate treasury reports without altering source values."""

    def __init__(self, max_file_size_mb: int | None = None) -> None:
        settings = get_settings()

        self._allowed_extensions = {
            extension.lower()
            for extension in settings.allowed_extensions
        }
        self._max_file_size_bytes = (
            max_file_size_mb or settings.max_upload_size_mb
        ) * 1024 * 1024

    def read(self, source_path: Path) -> IngestedReport:
        """Read a CSV or Excel report and return its validated table."""

        path = source_path.expanduser().resolve()
        file_type = self._validate_source(path)
        raw_table = self._read_raw_table(path, file_type)

        if raw_table.empty:
            raise FileValidationError(
                "The uploaded report is empty.",
                details={"filename": path.name},
            )

        header_index, column_positions = self._find_header_row(
            raw_table
        )
        report_date = self._extract_report_date(
            raw_table,
            header_index,
        )
        data = self._extract_data(
            raw_table,
            header_index,
            column_positions,
        )

        warnings: list[str] = []

        if report_date is None:
            warnings.append(
                "The report date could not be identified."
            )

        return IngestedReport(
            source_path=path,
            file_type=file_type,
            report_date=report_date,
            header_row_number=header_index + 1,
            data=data,
            warnings=tuple(warnings),
        )

    def _validate_source(self, path: Path) -> ReportFileType:
        """Validate the source path, extension, and file size."""

        if not path.exists():
            raise FileValidationError(
                "The selected file does not exist.",
                details={"path": str(path)},
            )

        if not path.is_file():
            raise FileValidationError(
                "The selected path is not a file.",
                details={"path": str(path)},
            )

        extension = path.suffix.lower()

        if extension not in self._allowed_extensions:
            raise FileValidationError(
                (
                    "Unsupported file type: "
                    f"{extension or 'no extension'}."
                ),
                details={
                    "filename": path.name,
                    "allowed_extensions": sorted(
                        self._allowed_extensions
                    ),
                },
            )

        file_size = path.stat().st_size

        if file_size == 0:
            raise FileValidationError(
                "The uploaded report is empty.",
                details={"filename": path.name},
            )

        if file_size > self._max_file_size_bytes:
            raise FileValidationError(
                "The uploaded report exceeds the permitted file size.",
                details={
                    "filename": path.name,
                    "file_size_bytes": file_size,
                    "maximum_size_bytes": (
                        self._max_file_size_bytes
                    ),
                },
            )

        return cast(
            ReportFileType,
            extension.removeprefix("."),
        )

    def _read_raw_table(
        self,
        path: Path,
        file_type: ReportFileType,
    ) -> pd.DataFrame:
        """Read all cells as text to preserve account identifiers."""

        try:
            if file_type == "csv":
                return self._read_csv(path)

            engine: Literal["openpyxl", "xlrd"] = (
                "openpyxl"
                if file_type == "xlsx"
                else "xlrd"
            )

            excel_data: pd.DataFrame = pd.read_excel(
                path,
                sheet_name=0,
                header=None,
                dtype=str,
                keep_default_na=False,
                engine=engine,
            )

            return excel_data

        except FileValidationError:
            raise
        except (
            EmptyDataError,
            ParserError,
            csv.Error,
            OSError,
            ValueError,
            ImportError,
        ) as exc:
            raise FileValidationError(
                "The report could not be read.",
                details={
                    "filename": path.name,
                    "reason": str(exc),
                },
            ) from exc

    @staticmethod
    def _read_csv(path: Path) -> pd.DataFrame:
        """
        Read a CSV containing variable-width metadata rows.

        Treasury reports can contain title rows with only one or two
        fields before the complete ten-column account table. The
        standard CSV reader accepts these variable row widths while
        preserving quoted commas and leading zeros.
        """

        encodings = (
            "utf-8-sig",
            "utf-8",
            "cp1252",
            "latin-1",
        )
        last_error: Exception | None = None

        for encoding in encodings:
            try:
                with path.open(
                    mode="r",
                    encoding=encoding,
                    newline="",
                ) as csv_file:
                    sample = csv_file.read(32768)
                    csv_file.seek(0)

                    delimiter = (
                        ReportFileReader._detect_csv_delimiter(
                            sample
                        )
                    )

                    rows = list(
                        csv.reader(
                            csv_file,
                            delimiter=delimiter,
                        )
                    )

                if not rows:
                    return pd.DataFrame()

                maximum_width = max(
                    len(row)
                    for row in rows
                )

                padded_rows = [
                    row
                    + [""] * (
                        maximum_width - len(row)
                    )
                    for row in rows
                ]

                return pd.DataFrame(
                    padded_rows,
                    dtype="string",
                )

            except (
                UnicodeDecodeError,
                csv.Error,
            ) as exc:
                last_error = exc

        raise FileValidationError(
            "The CSV character encoding or structure is not supported.",
            details={
                "filename": path.name,
                "reason": str(last_error),
            },
        )

    @staticmethod
    def _detect_csv_delimiter(sample: str) -> str:
        """Detect the delimiter using the complete CSV sample."""

        try:
            dialect = csv.Sniffer().sniff(
                sample,
                delimiters=",;\t|",
            )
            return dialect.delimiter
        except csv.Error:
            return ","

    @staticmethod
    def _normalise_cell(value: object) -> str:
        """Convert a cell to stripped text without changing content."""

        if bool(pd.isna(cast(Any, value))):
            return ""

        return str(value).replace("\ufeff", "").strip()

    @classmethod
    def _normalise_header(cls, value: object) -> str:
        """Create a stable header representation for comparison."""

        return " ".join(
            cls._normalise_cell(value).upper().split()
        )

    @classmethod
    def _find_header_row(
        cls,
        raw_table: pd.DataFrame,
    ) -> tuple[int, dict[str, int]]:
        """Locate the row containing every required treasury column."""

        for row_number in range(len(raw_table.index)):
            row_values = raw_table.iloc[
                row_number
            ].tolist()
            normalised_values = [
                cls._normalise_header(value)
                for value in row_values
            ]

            if all(
                required_column in normalised_values
                for required_column in REQUIRED_REPORT_COLUMNS
            ):
                positions = {
                    required_column: normalised_values.index(
                        required_column
                    )
                    for required_column in REQUIRED_REPORT_COLUMNS
                }

                return row_number, positions

        raise FileValidationError(
            "The required report header could not be identified.",
            details={
                "required_columns": list(
                    REQUIRED_REPORT_COLUMNS
                )
            },
        )

    @classmethod
    def _extract_data(
        cls,
        raw_table: pd.DataFrame,
        header_index: int,
        column_positions: dict[str, int],
    ) -> pd.DataFrame:
        """Extract required columns while preserving source values."""

        positions = [
            column_positions[column]
            for column in REQUIRED_REPORT_COLUMNS
        ]

        data = raw_table.iloc[
            header_index + 1 :,
            positions,
        ].copy()

        data.columns = list(REQUIRED_REPORT_COLUMNS)

        for column in REQUIRED_REPORT_COLUMNS:
            data[column] = data[column].map(
                cls._normalise_cell
            )

        non_empty_indices = [
            row_index
            for row_index, row in data.iterrows()
            if any(
                cls._normalise_cell(value)
                for value in row.tolist()
            )
        ]

        data = data.loc[non_empty_indices]

        return data.reset_index(drop=True)

    @classmethod
    def _extract_report_date(
        cls,
        raw_table: pd.DataFrame,
        header_index: int,
    ) -> date | None:
        """Extract the report date from rows above the header."""

        metadata = raw_table.iloc[:header_index]

        for _, row in metadata.iterrows():
            values = row.tolist()
            normalised_values = [
                cls._normalise_header(value)
                for value in values
            ]

            for position, value in enumerate(
                normalised_values
            ):
                if value != "AS AT":
                    continue

                for candidate in values[
                    position + 1 :
                ]:
                    candidate_text = (
                        cls._normalise_cell(candidate)
                    )
                    parsed_date = cls._parse_date(
                        candidate_text
                    )

                    if parsed_date is not None:
                        return parsed_date

        return None

    @staticmethod
    def _parse_date(value: str) -> date | None:
        """Parse supported treasury report date formats."""

        if not value:
            return None

        formats = (
            "%d %b %Y",
            "%d %B %Y",
            "%Y-%m-%d",
            "%Y-%m-%d %H:%M:%S",
            "%d/%m/%Y",
            "%d-%m-%Y",
        )

        for date_format in formats:
            try:
                return datetime.strptime(
                    value,
                    date_format,
                ).date()
            except ValueError:
                continue

        return None
    