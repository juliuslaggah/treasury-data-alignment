from decimal import Decimal

import pandas as pd
import pytest

from app.core.exceptions import DuplicateAccountError
from app.services.account_matcher import AccountMatcher


def test_matches_accounts_using_identifier_priority() -> None:
    source = pd.DataFrame(
        [
            {
                "T24 ACCOUNT": "001234",
                "LEGACY NO": "LEG-100",
                "BBAN NO": "BBAN-001",
                "ACCOUNT NAME": "Different source name",
                "DAILY BAL": Decimal("1500.00"),
            }
        ]
    )

    master = pd.DataFrame(
        [
            {
                "MASTER ROW": 10,
                "T24 ACCOUNT": "",
                "LEGACY NO": "",
                "BBAN NO": "BBAN-001",
                "ACCOUNT NAME": "Master account name",
                "NORMALIZED ACCOUNT NAME": "MASTER ACCOUNT NAME",
                "IS DUPLICATE": False,
            }
        ]
    )

    result = AccountMatcher().align(source, master)

    assert result.matched_count == 1
    assert result.unmatched_source_count == 0
    assert result.unmatched_master_count == 0
    assert result.aligned.iloc[0]["MATCH STATUS"] == "MATCHED"
    assert result.aligned.iloc[0]["MATCH METHOD"] == "BBAN NO"
    assert result.aligned.iloc[0]["DAILY BAL"] == Decimal("1500.00")


def test_falls_back_to_normalized_account_name() -> None:
    source = pd.DataFrame(
        [
            {
                "T24 ACCOUNT": "",
                "LEGACY NO": "",
                "BBAN NO": "",
                "ACCOUNT NAME": "  Sierra   Leone Standard Bureau Disbur  ",
                "DAILY BAL": Decimal("3000.00"),
            }
        ]
    )

    master = pd.DataFrame(
        [
            {
                "MASTER ROW": 67,
                "ACCOUNT NAME": "SIERRA LEONE STANDARD BUREAU DISBUR",
                "NORMALIZED ACCOUNT NAME": (
                    "SIERRA LEONE STANDARD BUREAU DISBUR"
                ),
                "IS DUPLICATE": False,
            }
        ]
    )

    result = AccountMatcher().align(source, master)

    assert result.matched_count == 1
    assert result.aligned.iloc[0]["MATCH METHOD"] == "ACCOUNT NAME"
    assert result.aligned.iloc[0]["SOURCE INDEX"] == 0


def test_preserves_master_order_and_reports_unmatched_accounts() -> None:
    source = pd.DataFrame(
        [
            {
                "T24 ACCOUNT": "",
                "LEGACY NO": "",
                "BBAN NO": "",
                "ACCOUNT NAME": "SECOND ACCOUNT",
                "DAILY BAL": Decimal("250.00"),
            }
        ]
    )

    master = pd.DataFrame(
        [
            {
                "MASTER ROW": 1,
                "ACCOUNT NAME": "FIRST ACCOUNT",
                "NORMALIZED ACCOUNT NAME": "FIRST ACCOUNT",
                "IS DUPLICATE": False,
            },
            {
                "MASTER ROW": 2,
                "ACCOUNT NAME": "SECOND ACCOUNT",
                "NORMALIZED ACCOUNT NAME": "SECOND ACCOUNT",
                "IS DUPLICATE": False,
            },
        ]
    )

    result = AccountMatcher().align(source, master)

    assert result.aligned["MASTER ROW"].tolist() == [1, 2]
    assert result.aligned["MATCH STATUS"].tolist() == ["UNMATCHED", "MATCHED"]
    assert result.unmatched_master_count == 1
    assert result.unmatched_master.iloc[0]["ACCOUNT NAME"] == "FIRST ACCOUNT"


def test_rejects_duplicate_master_accounts() -> None:
    source = pd.DataFrame(
        [
            {
                "ACCOUNT NAME": "DUPLICATE ACCOUNT",
                "DAILY BAL": Decimal("100.00"),
            }
        ]
    )

    master = pd.DataFrame(
        [
            {
                "MASTER ROW": 67,
                "ACCOUNT NAME": "DUPLICATE ACCOUNT",
                "NORMALIZED ACCOUNT NAME": "DUPLICATE ACCOUNT",
                "IS DUPLICATE": True,
            },
            {
                "MASTER ROW": 257,
                "ACCOUNT NAME": "DUPLICATE ACCOUNT",
                "NORMALIZED ACCOUNT NAME": "DUPLICATE ACCOUNT",
                "IS DUPLICATE": True,
            },
        ]
    )

    with pytest.raises(DuplicateAccountError):
        AccountMatcher().align(source, master)

