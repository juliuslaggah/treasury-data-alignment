import pandas as pd

from app.services.duplicate_detector import DuplicateDetector


def account(
    *,
    t24: str,
    legacy: str,
    bban: str,
    name: str,
) -> dict[str, str]:
    """Return a minimal account record for duplicate tests."""

    return {
        "T24 ACCOUNT": t24,
        "LEGACY NO": legacy,
        "BBAN NO": bban,
        "ACCOUNT NAME": name,
    }


def test_detects_duplicate_bban_numbers() -> None:
    """The same non-blank BBAN must be reported as a duplicate."""

    accounts = pd.DataFrame(
        [
            account(
                t24="0111001255",
                legacy="1100501",
                bban="000001011100125595",
                name="TREASURY MAIN",
            ),
            account(
                t24="0111009999",
                legacy="1100999",
                bban="000001011100125595",
                name="ANOTHER ACCOUNT",
            ),
        ]
    )

    report = DuplicateDetector().analyse(accounts)

    assert report.has_duplicates is True
    assert report.group_count == 1
    assert report.occurrence_count == 2
    assert set(report.issues["MATCH FIELD"]) == {"BBAN NO"}
    assert set(report.issues["DATA ROW"]) == {1, 2}


def test_detects_normalised_account_name_duplicates() -> None:
    """Case and repeated spacing must not conceal duplicate names."""

    accounts = pd.DataFrame(
        [
            account(
                t24="0111003651",
                legacy="",
                bban="000001011100365185",
                name="SIERRA LEONE STANDARD BUREAU DISBUR",
            ),
            account(
                t24="0111009998",
                legacy="",
                bban="000001011100999800",
                name="  sierra   leone standard bureau disbur ",
            ),
        ]
    )

    report = DuplicateDetector().analyse(accounts)

    assert report.has_duplicates is True
    assert report.group_count == 1
    assert set(report.issues["MATCH FIELD"]) == {
        "ACCOUNT NAME"
    }
    assert set(report.issues["MATCH VALUE"]) == {
        "SIERRA LEONE STANDARD BUREAU DISBUR"
    }


def test_ignores_repeated_blank_identifiers() -> None:
    """Blank identifier fields must never create duplicate groups."""

    accounts = pd.DataFrame(
        [
            account(
                t24="0111001001",
                legacy="",
                bban="",
                name="FIRST ACCOUNT",
            ),
            account(
                t24="0111001002",
                legacy="",
                bban="",
                name="SECOND ACCOUNT",
            ),
        ]
    )

    report = DuplicateDetector().analyse(accounts)

    assert report.has_duplicates is False
    assert report.group_count == 0
    assert report.occurrence_count == 0
    assert report.issues.empty


def test_duplicate_analysis_does_not_modify_source_data() -> None:
    """Duplicate analysis must leave the source DataFrame unchanged."""

    accounts = pd.DataFrame(
        [
            account(
                t24="0111001255",
                legacy="1100501",
                bban="000001011100125595",
                name="TREASURY MAIN",
            )
        ]
    )
    original = accounts.copy(deep=True)

    DuplicateDetector().analyse(accounts)

    pd.testing.assert_frame_equal(accounts, original)

    