from collections import Counter
from dataclasses import dataclass
from typing import Any, cast

import pandas as pd

from app.core.exceptions import DataCleaningError


@dataclass(frozen=True, slots=True)
class DuplicateReport:
    """Results of duplicate analysis across account identifiers."""

    issues: pd.DataFrame

    @property
    def has_duplicates(self) -> bool:
        """Return whether duplicate occurrences were detected."""

        return not self.issues.empty

    @property
    def occurrence_count(self) -> int:
        """Return the number of rows involved in duplicate groups."""

        return len(self.issues.index)

    @property
    def group_count(self) -> int:
        """Return the number of distinct duplicate groups."""

        if self.issues.empty:
            return 0

        groups = self.issues[
            ["MATCH FIELD", "MATCH VALUE"]
        ].drop_duplicates()

        return len(groups.index)


class DuplicateDetector:
    """Detect duplicate accounts using identifiers and account names."""

    _MATCH_FIELDS = (
        "BBAN NO",
        "T24 ACCOUNT",
        "LEGACY NO",
        "ACCOUNT NAME",
    )

    _ISSUE_COLUMNS = (
        "MATCH FIELD",
        "MATCH VALUE",
        "DATA ROW",
        "SOURCE INDEX",
        "ACCOUNT NAME",
    )

    def analyse(
        self,
        accounts: pd.DataFrame,
    ) -> DuplicateReport:
        """Analyse account data without modifying the source table."""

        self._validate_columns(accounts)

        issues: list[dict[str, object]] = []

        for field in self._MATCH_FIELDS:
            normalised_values = [
                self._normalise_value(field, value)
                for value in accounts[field].tolist()
            ]

            value_counts = Counter(
                value
                for value in normalised_values
                if value
            )
            duplicate_values = {
                value
                for value, count in value_counts.items()
                if count > 1
            }

            for position, (
                source_index,
                normalised_value,
            ) in enumerate(
                zip(
                    accounts.index,
                    normalised_values,
                    strict=True,
                ),
                start=1,
            ):
                if normalised_value not in duplicate_values:
                    continue

                account_name = self._clean_text(
                    accounts.loc[
                        source_index,
                        "ACCOUNT NAME",
                    ]
                )

                issues.append(
                    {
                        "MATCH FIELD": field,
                        "MATCH VALUE": normalised_value,
                        "DATA ROW": position,
                        "SOURCE INDEX": str(source_index),
                        "ACCOUNT NAME": account_name,
                    }
                )

        issue_table = pd.DataFrame(
            issues,
            columns=list(self._ISSUE_COLUMNS),
        )

        return DuplicateReport(issues=issue_table)

    def _validate_columns(
        self,
        accounts: pd.DataFrame,
    ) -> None:
        """Ensure all duplicate-analysis columns are available."""

        available_columns = {
            str(column)
            for column in accounts.columns
        }
        missing_columns = (
            set(self._MATCH_FIELDS) - available_columns
        )

        if missing_columns:
            missing = ", ".join(
                sorted(missing_columns)
            )
            raise DataCleaningError(
                "Duplicate analysis cannot be completed.",
                details={
                    "missing_columns": missing,
                },
            )

    @classmethod
    def _normalise_value(
        cls,
        field: str,
        value: object,
    ) -> str:
        """Normalize a field according to its matching semantics."""

        text = cls._clean_text(value)

        if field == "ACCOUNT NAME":
            return " ".join(text.upper().split())

        return text

    @staticmethod
    def _clean_text(value: object) -> str:
        """Convert a scalar value to stripped text."""

        if bool(pd.isna(cast(Any, value))):
            return ""

        return str(value).strip()

    