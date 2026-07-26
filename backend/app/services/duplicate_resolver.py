from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd

from app.core.exceptions import DuplicateAccountError


@dataclass(frozen=True, slots=True)
class DuplicateOccurrence:
    """One physical occurrence of a duplicate master account."""

    sheet_name: str
    master_row: int
    account_name: str
    source_index: int


@dataclass(frozen=True, slots=True)
class DuplicateGroup:
    """A group of master rows representing the same account."""

    account_key: str
    account_name: str
    occurrences: tuple[DuplicateOccurrence, ...]


@dataclass(frozen=True, slots=True)
class DuplicateResolution:
    """The master occurrence deliberately selected by the user."""

    account_key: str
    keep_sheet_name: str
    keep_master_row: int


@dataclass(frozen=True, slots=True)
class DuplicateResolutionResult:
    """Master accounts after duplicate resolution."""

    active_accounts: pd.DataFrame
    excluded_accounts: pd.DataFrame
    resolutions: tuple[DuplicateResolution, ...]


class MasterDuplicateResolver:
    """Analyse and resolve duplicate master-register accounts."""

    def analyse(
        self,
        master_accounts: pd.DataFrame,
    ) -> tuple[DuplicateGroup, ...]:
        """Return every duplicate account and its workbook locations."""

        master = master_accounts.copy(
            deep=True
        ).reset_index(drop=True)

        if master.empty:
            return ()

        if "ACCOUNT NAME" not in master.columns:
            raise DuplicateAccountError(
                "The master register does not contain account names."
            )

        normalized_names = self._normalized_names(master)

        duplicate_mask = (
            normalized_names.ne("")
            & normalized_names.duplicated(keep=False)
        )

        duplicate_keys = (
            normalized_names.loc[duplicate_mask]
            .drop_duplicates()
            .tolist()
        )

        groups: list[DuplicateGroup] = []

        for account_key_value in duplicate_keys:
            account_key = str(account_key_value)
            occurrences: list[DuplicateOccurrence] = []

            for source_index in range(len(master)):
                if (
                    str(normalized_names.iloc[source_index])
                    != account_key
                ):
                    continue

                row = master.iloc[source_index]

                occurrences.append(
                    DuplicateOccurrence(
                        sheet_name=self._sheet_name(row),
                        master_row=self._master_row(row),
                        account_name=self._account_name(row),
                        source_index=source_index,
                    )
                )

            if len(occurrences) < 2:
                continue

            groups.append(
                DuplicateGroup(
                    account_key=account_key,
                    account_name=occurrences[0].account_name,
                    occurrences=tuple(occurrences),
                )
            )

        return tuple(groups)

    def resolve(
        self,
        master_accounts: pd.DataFrame,
        resolutions: tuple[DuplicateResolution, ...],
    ) -> DuplicateResolutionResult:
        """
        Apply deliberate duplicate choices without changing the source.

        The selected occurrence remains available for matching. Other
        occurrences are returned separately for zeroing and auditing.
        """

        master = master_accounts.copy(
            deep=True
        ).reset_index(drop=True)

        groups = self.analyse(master)

        if not groups:
            if resolutions:
                raise DuplicateAccountError(
                    "Duplicate resolutions were supplied, but the "
                    "master register contains no duplicate accounts."
                )

            return DuplicateResolutionResult(
                active_accounts=master,
                excluded_accounts=master.iloc[0:0].copy(),
                resolutions=(),
            )

        resolution_map = self._resolution_map(resolutions)

        duplicate_keys = {
            group.account_key
            for group in groups
        }

        unknown_keys = set(resolution_map).difference(
            duplicate_keys
        )

        if unknown_keys:
            unknown = ", ".join(
                sorted(unknown_keys)
            )

            raise DuplicateAccountError(
                "A duplicate resolution references an unknown "
                f"account: {unknown}."
            )

        excluded_indices: list[int] = []
        selected_indices: list[int] = []

        for group in groups:
            resolution = resolution_map.get(
                group.account_key
            )

            if resolution is None:
                raise DuplicateAccountError(
                    f"Duplicate account '{group.account_name}' "
                    "requires a resolution."
                )

            selected_occurrence = next(
                (
                    occurrence
                    for occurrence in group.occurrences
                    if (
                        occurrence.sheet_name
                        == resolution.keep_sheet_name
                        and occurrence.master_row
                        == resolution.keep_master_row
                    )
                ),
                None,
            )

            if selected_occurrence is None:
                raise DuplicateAccountError(
                    f"Row {resolution.keep_master_row} on sheet "
                    f"'{resolution.keep_sheet_name}' is not a valid "
                    f"occurrence of '{group.account_name}'."
                )

            selected_indices.append(
                selected_occurrence.source_index
            )

            excluded_indices.extend(
                occurrence.source_index
                for occurrence in group.occurrences
                if occurrence.source_index
                != selected_occurrence.source_index
            )

        active = master.drop(
            index=excluded_indices
        ).copy()

        if "IS DUPLICATE" in active.columns:
            active.loc[
                active.index.isin(selected_indices),
                "IS DUPLICATE",
            ] = False

        excluded = master.loc[
            excluded_indices
        ].copy()

        excluded["RESOLUTION STATUS"] = (
            "EXCLUDED DUPLICATE"
        )

        return DuplicateResolutionResult(
            active_accounts=active.reset_index(drop=True),
            excluded_accounts=excluded.reset_index(drop=True),
            resolutions=resolutions,
        )

    @classmethod
    def _normalized_names(
        cls,
        master: pd.DataFrame,
    ) -> pd.Series[Any]:
        """Return normalized master account names."""

        if "NORMALIZED ACCOUNT NAME" in master.columns:
            values = master[
                "NORMALIZED ACCOUNT NAME"
            ]
        else:
            values = master["ACCOUNT NAME"]

        return values.astype("string").fillna("").map(
            cls._normalize_name
        )

    @staticmethod
    def _resolution_map(
        resolutions: tuple[DuplicateResolution, ...],
    ) -> dict[str, DuplicateResolution]:
        """Create a validated account-resolution lookup."""

        resolution_map: dict[
            str,
            DuplicateResolution,
        ] = {}

        for resolution in resolutions:
            account_key = (
                MasterDuplicateResolver._normalize_name(
                    resolution.account_key
                )
            )

            if account_key in resolution_map:
                raise DuplicateAccountError(
                    f"Duplicate account '{account_key}' has more "
                    "than one submitted resolution."
                )

            resolution_map[account_key] = resolution

        return resolution_map

    @staticmethod
    def _normalize_name(value: object) -> str:
        """Normalize an account name for stable comparison."""

        return " ".join(
            str(value).strip().upper().split()
        )

    @staticmethod
    def _sheet_name(
        row: pd.Series[Any],
    ) -> str:
        """Extract the worksheet name from a master row."""

        value = row.get("SHEET NAME", "")

        if value is None or value is pd.NA:
            return ""

        return str(value).strip()

    @staticmethod
    def _master_row(
        row: pd.Series[Any],
    ) -> int:
        """Extract and validate the Excel row number."""

        value = row.get("MASTER ROW")

        if value is None or value is pd.NA:
            raise DuplicateAccountError(
                "A duplicate master account does not have an "
                "Excel row number."
            )

        try:
            decimal_row = Decimal(str(value))
        except InvalidOperation as exc:
            raise DuplicateAccountError(
                f"Invalid master row number: {value}."
            ) from exc

        if decimal_row != decimal_row.to_integral_value():
            raise DuplicateAccountError(
                f"Invalid master row number: {value}."
            )

        master_row = int(decimal_row)

        if master_row < 1:
            raise DuplicateAccountError(
                f"Invalid master row number: {master_row}."
            )

        return master_row

    @staticmethod
    def _account_name(
        row: pd.Series[Any],
    ) -> str:
        """Extract the account name displayed to the user."""

        value = row.get("ACCOUNT NAME", "")

        if value is None or value is pd.NA:
            return ""

        return str(value).strip()

