from decimal import Decimal

import pandas as pd

from app.services.account_matcher import AlignmentResult
from app.services.validator import DataValidator


def test_valid_alignment_passes_validation() -> None:
    source = pd.DataFrame(
        [
            {
                "ACCOUNT NAME": "ACCOUNT ONE",
                "DAILY BAL": Decimal("100.00"),
                "LEDGER BALANCE": Decimal("100.00"),
            },
            {
                "ACCOUNT NAME": "ACCOUNT TWO",
                "DAILY BAL": Decimal("250.00"),
                "LEDGER BALANCE": Decimal("250.00"),
            },
        ]
    )

    aligned = pd.DataFrame(
        [
            {
                "MASTER ROW": 1,
                "ACCOUNT NAME": "ACCOUNT ONE",
                "SOURCE INDEX": 0,
                "MATCH STATUS": "MATCHED",
                "MATCH METHOD": "ACCOUNT NAME",
                "DAILY BAL": Decimal("100.00"),
                "LEDGER BALANCE": Decimal("100.00"),
            },
            {
                "MASTER ROW": 2,
                "ACCOUNT NAME": "ACCOUNT TWO",
                "SOURCE INDEX": 1,
                "MATCH STATUS": "MATCHED",
                "MATCH METHOD": "ACCOUNT NAME",
                "DAILY BAL": Decimal("250.00"),
                "LEDGER BALANCE": Decimal("250.00"),
            },
        ]
    )

    alignment = AlignmentResult(
        aligned=aligned,
        unmatched_source=source.iloc[0:0].copy(),
        unmatched_master=pd.DataFrame(),
    )

    result = DataValidator().validate(source, alignment)

    assert result.is_valid is True
    assert result.error_count == 0
    assert result.warning_count == 0


def test_unmatched_source_account_is_an_error() -> None:
    source = pd.DataFrame(
        [
            {
                "ACCOUNT NAME": "UNKNOWN ACCOUNT",
                "DAILY BAL": Decimal("500.00"),
                "LEDGER BALANCE": Decimal("500.00"),
            }
        ]
    )

    alignment = AlignmentResult(
        aligned=pd.DataFrame(),
        unmatched_source=source.copy(),
        unmatched_master=pd.DataFrame(),
    )

    result = DataValidator().validate(source, alignment)

    assert result.is_valid is False
    assert result.has_issue("UNMATCHED_SOURCE_ACCOUNT")
    assert result.error_count == 1
    assert len(result.issues) == 1
    assert result.issues[0].message == (
        "1 source account(s) could not be matched to the master "
        "register: UNKNOWN ACCOUNT."
    )


def test_unmatched_master_account_is_a_warning() -> None:
    source = pd.DataFrame(
        columns=["ACCOUNT NAME", "DAILY BAL", "LEDGER BALANCE"]
    )

    unmatched_master = pd.DataFrame(
        [
            {
                "MASTER ROW": 10,
                "ACCOUNT NAME": "MASTER ACCOUNT WITHOUT ACTIVITY",
            }
        ]
    )

    alignment = AlignmentResult(
        aligned=pd.DataFrame(),
        unmatched_source=pd.DataFrame(),
        unmatched_master=unmatched_master,
    )

    result = DataValidator().validate(source, alignment)

    assert result.is_valid is True
    assert result.has_issue("UNMATCHED_MASTER_ACCOUNT")
    assert result.warning_count == 1


def test_balance_mismatch_is_an_error() -> None:
    source = pd.DataFrame(
        [
            {
                "ACCOUNT NAME": "ACCOUNT ONE",
                "DAILY BAL": Decimal("1000.00"),
                "LEDGER BALANCE": Decimal("1000.00"),
            }
        ]
    )

    aligned = pd.DataFrame(
        [
            {
                "MASTER ROW": 1,
                "ACCOUNT NAME": "ACCOUNT ONE",
                "SOURCE INDEX": 0,
                "MATCH STATUS": "MATCHED",
                "MATCH METHOD": "ACCOUNT NAME",
                "DAILY BAL": Decimal("900.00"),
                "LEDGER BALANCE": Decimal("900.00"),
            }
        ]
    )

    alignment = AlignmentResult(
        aligned=aligned,
        unmatched_source=source.iloc[0:0].copy(),
        unmatched_master=pd.DataFrame(),
    )

    result = DataValidator().validate(source, alignment)

    assert result.is_valid is False
    assert result.has_issue("BALANCE_RECONCILIATION_FAILED")
    assert result.error_count == 1