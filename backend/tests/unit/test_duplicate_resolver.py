import pandas as pd
import pytest

from app.core.exceptions import DuplicateAccountError
from app.services.duplicate_resolver import (
    DuplicateResolution,
    MasterDuplicateResolver,
)


def create_master_accounts() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "SHEET NAME": "Treasury Report",
                "MASTER ROW": 67,
                "ACCOUNT NAME": (
                    "SIERRA LEONE STANDARD BUREAU DISBUR"
                ),
                "NORMALIZED ACCOUNT NAME": (
                    "SIERRA LEONE STANDARD BUREAU DISBUR"
                ),
                "IS DUPLICATE": True,
            },
            {
                "SHEET NAME": "Treasury Report",
                "MASTER ROW": 100,
                "ACCOUNT NAME": "ANOTHER ACCOUNT",
                "NORMALIZED ACCOUNT NAME": "ANOTHER ACCOUNT",
                "IS DUPLICATE": False,
            },
            {
                "SHEET NAME": "Treasury Report",
                "MASTER ROW": 257,
                "ACCOUNT NAME": (
                    "SIERRA LEONE STANDARD BUREAU DISBUR"
                ),
                "NORMALIZED ACCOUNT NAME": (
                    "SIERRA LEONE STANDARD BUREAU DISBUR"
                ),
                "IS DUPLICATE": True,
            },
        ]
    )


def test_analyse_returns_duplicate_name_and_locations() -> None:
    master = create_master_accounts()

    groups = MasterDuplicateResolver().analyse(master)

    assert len(groups) == 1

    group = groups[0]

    assert group.account_key == (
        "SIERRA LEONE STANDARD BUREAU DISBUR"
    )
    assert group.account_name == (
        "SIERRA LEONE STANDARD BUREAU DISBUR"
    )
    assert len(group.occurrences) == 2
    assert [
        occurrence.master_row
        for occurrence in group.occurrences
    ] == [67, 257]
    assert all(
        occurrence.sheet_name == "Treasury Report"
        for occurrence in group.occurrences
    )


def test_resolve_keeps_selected_row_and_excludes_other() -> None:
    master = create_master_accounts()

    result = MasterDuplicateResolver().resolve(
        master,
        resolutions=(
            DuplicateResolution(
                account_key=(
                    "SIERRA LEONE STANDARD BUREAU DISBUR"
                ),
                keep_sheet_name="Treasury Report",
                keep_master_row=257,
            ),
        ),
    )

    assert result.active_accounts["MASTER ROW"].tolist() == [
        100,
        257,
    ]
    assert result.excluded_accounts["MASTER ROW"].tolist() == [
        67
    ]
    assert result.excluded_accounts.iloc[0][
        "RESOLUTION STATUS"
    ] == "EXCLUDED DUPLICATE"

    selected = result.active_accounts.loc[
        result.active_accounts["MASTER ROW"].eq(257)
    ].iloc[0]

    assert bool(selected["IS DUPLICATE"]) is False


def test_resolve_requires_choice_for_every_duplicate() -> None:
    master = create_master_accounts()

    with pytest.raises(
        DuplicateAccountError,
        match="requires a resolution",
    ):
        MasterDuplicateResolver().resolve(
            master,
            resolutions=(),
        )


def test_resolve_rejects_row_outside_duplicate_group() -> None:
    master = create_master_accounts()

    with pytest.raises(
        DuplicateAccountError,
        match="not a valid occurrence",
    ):
        MasterDuplicateResolver().resolve(
            master,
            resolutions=(
                DuplicateResolution(
                    account_key=(
                        "SIERRA LEONE STANDARD BUREAU DISBUR"
                    ),
                    keep_sheet_name="Treasury Report",
                    keep_master_row=999,
                ),
            ),
        )

    assert master["MASTER ROW"].tolist() == [67, 100, 257]
    assert master["IS DUPLICATE"].tolist() == [
        True,
        False,
        True,
    ]


