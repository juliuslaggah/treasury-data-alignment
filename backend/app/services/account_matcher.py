from dataclasses import dataclass
from typing import Any, Final

import pandas as pd

from app.core.exceptions import DuplicateAccountError

MATCH_PRIORITY: Final[tuple[str, ...]] = (
    "BBAN NO",
    "T24 ACCOUNT",
    "LEGACY NO",
    "ACCOUNT NAME",
)

SOURCE_PREFIX: Final[str] = "SOURCE "


@dataclass(frozen=True, slots=True)
class AlignmentResult:
    """Result produced by matching source accounts to the master register."""

    aligned: pd.DataFrame
    unmatched_source: pd.DataFrame
    unmatched_master: pd.DataFrame

    @property
    def matched_count(self) -> int:
        """Return the number of successfully matched master accounts."""
        if "MATCH STATUS" not in self.aligned.columns:
            return 0

        statuses = self.aligned["MATCH STATUS"].astype("string")
        return int(statuses.eq("MATCHED").sum())

    @property
    def unmatched_source_count(self) -> int:
        """Return the number of source accounts that were not used."""
        return len(self.unmatched_source)

    @property
    def unmatched_master_count(self) -> int:
        """Return the number of master accounts without a source match."""
        return len(self.unmatched_master)


class AccountMatcher:
    """
    Align cleaned source accounts with the approved master register.

    Matching priority:

    1. BBAN number
    2. T24 account number
    3. Legacy account number
    4. Exact normalized account name

    Each source row can be assigned to only one master row.
    """

    def align(
        self,
        source_accounts: pd.DataFrame,
        master_accounts: pd.DataFrame,
    ) -> AlignmentResult:
        """Align source accounts to the master register."""

        source = source_accounts.copy(deep=True).reset_index(drop=True)
        master = master_accounts.copy(deep=True).reset_index(drop=True)

        self._validate_master_register(master)

        source["_SOURCE INDEX"] = source.index
        used_source_indexes: set[int] = set()
        aligned_records: list[dict[str, object]] = []

        for _, master_row in master.iterrows():
            source_index, match_method = self._find_match(
                master_row=master_row,
                source=source,
                used_source_indexes=used_source_indexes,
            )

            record = self._create_master_record(master_row)

            if source_index is None:
                record["MATCH STATUS"] = "UNMATCHED"
                record["MATCH METHOD"] = ""
                record["SOURCE INDEX"] = pd.NA
            else:
                source_row = source.iloc[source_index]
                used_source_indexes.add(source_index)

                record.update(self._create_source_record(source_row))
                record["MATCH STATUS"] = "MATCHED"
                record["MATCH METHOD"] = match_method
                record["SOURCE INDEX"] = source_index

            aligned_records.append(record)

        aligned = pd.DataFrame(aligned_records)

        unmatched_source = source.loc[
            ~source["_SOURCE INDEX"].isin(used_source_indexes)
        ].copy()

        unmatched_source = unmatched_source.drop(
            columns=["_SOURCE INDEX"],
            errors="ignore",
        ).reset_index(drop=True)

        if aligned.empty or "MATCH STATUS" not in aligned.columns:
            unmatched_master = master.copy()
        else:
            unmatched_master_indexes = aligned.index[
                aligned["MATCH STATUS"].astype("string").eq("UNMATCHED")
            ]
            unmatched_master = master.loc[unmatched_master_indexes].copy()

        unmatched_master = unmatched_master.reset_index(drop=True)

        return AlignmentResult(
            aligned=aligned,
            unmatched_source=unmatched_source,
            unmatched_master=unmatched_master,
        )

    def _find_match(
        self,
        master_row: pd.Series[Any],
        source: pd.DataFrame,
        used_source_indexes: set[int],
    ) -> tuple[int | None, str]:
        """Find the first unused source row using the matching hierarchy."""

        for match_field in MATCH_PRIORITY:
            master_value = self._master_match_value(
                master_row,
                match_field,
            )

            if not master_value:
                continue

            if match_field not in source.columns:
                continue

            for row_index in range(len(source)):
                if row_index in used_source_indexes:
                    continue

                source_value = source.iloc[row_index][match_field]

                normalized_source = self._normalize_match_value(
                    source_value,
                    match_field,
                )

                if normalized_source == master_value:
                    return row_index, match_field

        return None, ""

    def _master_match_value(
        self,
        master_row: pd.Series[Any],
        match_field: str,
    ) -> str:
        """Return the normalized master value for a matching field."""

        if match_field == "ACCOUNT NAME":
            normalized_name = master_row.get(
                "NORMALIZED ACCOUNT NAME",
                "",
            )

            if self._has_value(normalized_name):
                return self._normalize_name(normalized_name)

        return self._normalize_match_value(
            master_row.get(match_field, ""),
            match_field,
        )

    def _normalize_match_value(
        self,
        value: object,
        match_field: str,
    ) -> str:
        """Normalize an identifier or account name for exact matching."""

        if not self._has_value(value):
            return ""

        if match_field == "ACCOUNT NAME":
            return self._normalize_name(value)

        return str(value).strip().upper()

    @staticmethod
    def _normalize_name(value: object) -> str:
        """Normalize spacing and letter case in an account name."""
        return " ".join(str(value).strip().upper().split())

    @staticmethod
    def _has_value(value: object) -> bool:
        """Return whether a scalar value is present and non-blank."""
        if value is None or value is pd.NA:
            return False

        if isinstance(value, float) and pd.isna(value):
            return False

        return bool(str(value).strip())

    @staticmethod
    def _create_master_record(
        master_row: pd.Series[Any],
    ) -> dict[str, object]:
        """Create an output record from a master-register row."""
        return {
            str(column): value
            for column, value in master_row.items()
        }

    @staticmethod
    def _create_source_record(
        source_row: pd.Series[Any],
    ) -> dict[str, object]:
        """
        Create source output fields without overwriting master fields.

        Source identifiers and the source account name receive a SOURCE
        prefix. Financial values retain their original column names.
        """

        record: dict[str, object] = {}

        for column, value in source_row.items():
            column_name = str(column)

            if column_name == "_SOURCE INDEX":
                continue

            if column_name in MATCH_PRIORITY:
                record[f"{SOURCE_PREFIX}{column_name}"] = value
            else:
                record[column_name] = value

        return record

    def _validate_master_register(
        self,
        master: pd.DataFrame,
    ) -> None:
        """Prevent alignment when the master contains duplicate accounts."""

        if master.empty:
            return

        if "IS DUPLICATE" in master.columns:
            duplicate_flags = (
                master["IS DUPLICATE"]
                .fillna(False)
                .astype(bool)
            )

            if bool(duplicate_flags.any()):
                raise DuplicateAccountError(
                    "The master register contains duplicate accounts. "
                    "Resolve them before running account alignment."
                )

        if "NORMALIZED ACCOUNT NAME" not in master.columns:
            return

        normalized_names = master["NORMALIZED ACCOUNT NAME"].map(
            self._normalize_name
        )
        non_blank_names = normalized_names[normalized_names.ne("")]

        if bool(non_blank_names.duplicated(keep=False).any()):
            raise DuplicateAccountError(
                "The master register contains repeated normalized account "
                "names. Resolve them before running account alignment."
            )

