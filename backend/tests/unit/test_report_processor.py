from pathlib import Path
from unittest.mock import Mock

import pandas as pd
import pytest

from app.services.duplicate_resolver import (
    DuplicateGroup,
    DuplicateOccurrence,
    DuplicateResolution,
    DuplicateResolutionResult,
    MasterDuplicateResolver,
)
from app.services.report_processor import ReportProcessor


@pytest.fixture
def source_path(tmp_path: Path) -> Path:
    path = tmp_path / "report.csv"
    path.write_text("ACCOUNT NAME,DAILY BAL\nACCOUNT ONE,100.00")
    return path


@pytest.fixture
def master_path(tmp_path: Path) -> Path:
    path = tmp_path / "master.xlsx"
    path.write_bytes(b"master-workbook")
    return path


@pytest.fixture
def output_path(tmp_path: Path) -> Path:
    return tmp_path / "aligned-report.xlsx"


@pytest.fixture
def duplicate_group() -> DuplicateGroup:
    return DuplicateGroup(
        account_key="SIERRA LEONE STANDARD BUREAU DISBUR",
        account_name="SIERRA LEONE STANDARD BUREAU DISBUR",
        occurrences=(
            DuplicateOccurrence(
                sheet_name="Sheet1",
                master_row=67,
                account_name="SIERRA LEONE STANDARD BUREAU DISBUR",
                source_index=65,
            ),
            DuplicateOccurrence(
                sheet_name="Sheet1",
                master_row=257,
                account_name="SIERRA LEONE STANDARD BUREAU DISBUR",
                source_index=255,
            ),
        ),
    )


def build_processor() -> tuple[
    ReportProcessor,
    Mock,
    Mock,
    Mock,
    Mock,
    Mock,
    Mock,
    Mock,
    Mock,
]:
    reader = Mock()
    cleaner = Mock()
    master_loader = Mock()
    duplicate_detector = Mock()
    duplicate_resolver = Mock(spec=MasterDuplicateResolver)
    matcher = Mock()
    validator = Mock()
    exporter = Mock()

    processor = ReportProcessor(
        reader=reader,
        cleaner=cleaner,
        master_loader=master_loader,
        duplicate_detector=duplicate_detector,
        duplicate_resolver=duplicate_resolver,
        matcher=matcher,
        validator=validator,
        exporter=exporter,
    )

    return (
        processor,
        reader,
        cleaner,
        master_loader,
        duplicate_detector,
        duplicate_resolver,
        matcher,
        validator,
        exporter,
    )


def configure_analysis_dependencies(
    *,
    reader: Mock,
    cleaner: Mock,
    master_loader: Mock,
    duplicate_detector: Mock,
    duplicate_resolver: Mock,
    duplicate_groups: tuple[DuplicateGroup, ...],
    source_has_duplicates: bool = False,
) -> tuple[Mock, Mock, Mock]:
    ingested_report = Mock(name="ingested_report")

    cleaned_report = Mock(name="cleaned_report")
    cleaned_report.accounts = pd.DataFrame(
        [
            {
                "ACCOUNT NAME": (
                    "SIERRA LEONE STANDARD BUREAU DISBUR"
                ),
                "ACCOUNT KEY": (
                    "SIERRA LEONE STANDARD BUREAU DISBUR"
                ),
                "DAILY BAL": "3000.00",
            }
        ]
    )

    master_register = Mock(name="master_register")
    master_register.accounts = pd.DataFrame(
        [
            {
                "ACCOUNT NAME": (
                    "SIERRA LEONE STANDARD BUREAU DISBUR"
                ),
                "ACCOUNT KEY": (
                    "SIERRA LEONE STANDARD BUREAU DISBUR"
                ),
                "SHEET NAME": "Sheet1",
                "MASTER ROW": 67,
                "SOURCE INDEX": 65,
                "IS DUPLICATE": True,
            },
            {
                "ACCOUNT NAME": (
                    "SIERRA LEONE STANDARD BUREAU DISBUR"
                ),
                "ACCOUNT KEY": (
                    "SIERRA LEONE STANDARD BUREAU DISBUR"
                ),
                "SHEET NAME": "Sheet1",
                "MASTER ROW": 257,
                "SOURCE INDEX": 255,
                "IS DUPLICATE": True,
            },
        ]
    )

    source_duplicates = Mock(name="source_duplicates")
    source_duplicates.has_duplicates = source_has_duplicates

    reader.read.return_value = ingested_report
    cleaner.clean.return_value = cleaned_report
    master_loader.load.return_value = master_register
    duplicate_detector.analyse.return_value = source_duplicates
    duplicate_resolver.analyse.return_value = duplicate_groups

    return cleaned_report, master_register, source_duplicates


def test_analyse_returns_master_duplicate_names_and_locations(
    source_path: Path,
    master_path: Path,
    duplicate_group: DuplicateGroup,
) -> None:
    (
        processor,
        reader,
        cleaner,
        master_loader,
        duplicate_detector,
        duplicate_resolver,
        matcher,
        validator,
        exporter,
    ) = build_processor()

    cleaned_report, master_register, source_duplicates = (
        configure_analysis_dependencies(
            reader=reader,
            cleaner=cleaner,
            master_loader=master_loader,
            duplicate_detector=duplicate_detector,
            duplicate_resolver=duplicate_resolver,
            duplicate_groups=(duplicate_group,),
        )
    )

    result = processor.analyse(source_path, master_path)

    assert result.report is cleaned_report
    assert result.master_register is master_register
    assert result.source_duplicates is source_duplicates
    assert result.master_duplicates == (duplicate_group,)

    assert result.master_duplicates[0].account_name == (
        "SIERRA LEONE STANDARD BUREAU DISBUR"
    )
    assert tuple(
        occurrence.master_row
        for occurrence in result.master_duplicates[0].occurrences
    ) == (67, 257)

    reader.read.assert_called_once_with(source_path)
    cleaner.clean.assert_called_once()
    master_loader.load.assert_called_once_with(master_path)
    duplicate_detector.analyse.assert_called_once_with(
        cleaned_report.accounts
    )
    duplicate_resolver.analyse.assert_called_once_with(
        master_register.accounts
    )

    matcher.align.assert_not_called()
    validator.validate.assert_not_called()
    exporter.export.assert_not_called()


def test_process_uses_selected_master_row_and_exports_excluded_duplicate(
    source_path: Path,
    master_path: Path,
    output_path: Path,
    duplicate_group: DuplicateGroup,
) -> None:
    (
        processor,
        reader,
        cleaner,
        master_loader,
        duplicate_detector,
        duplicate_resolver,
        matcher,
        validator,
        exporter,
    ) = build_processor()

    cleaned_report, master_register, _ = (
        configure_analysis_dependencies(
            reader=reader,
            cleaner=cleaner,
            master_loader=master_loader,
            duplicate_detector=duplicate_detector,
            duplicate_resolver=duplicate_resolver,
            duplicate_groups=(duplicate_group,),
        )
    )

    resolution = DuplicateResolution(
        account_key=duplicate_group.account_key,
        keep_sheet_name="Sheet1",
        keep_master_row=67,
    )

    active_accounts = master_register.accounts.iloc[[0]].copy()
    excluded_accounts = master_register.accounts.iloc[[1]].copy()
    excluded_accounts["RESOLUTION STATUS"] = "EXCLUDED DUPLICATE"

    resolution_result = DuplicateResolutionResult(
        active_accounts=active_accounts,
        excluded_accounts=excluded_accounts,
        resolutions=(resolution,),
    )

    alignment = Mock(name="alignment")
    validation = Mock(name="validation")

    duplicate_resolver.resolve.return_value = resolution_result
    matcher.align.return_value = alignment
    validator.validate.return_value = validation
    exporter.export.return_value = output_path

    result = processor.process(
        source_path,
        master_path,
        output_path,
        resolutions=(resolution,),
    )

    duplicate_resolver.resolve.assert_called_once_with(
        master_register.accounts,
        (resolution,),
    )
    matcher.align.assert_called_once_with(
        cleaned_report.accounts,
        active_accounts,
    )
    validator.validate.assert_called_once_with(
        cleaned_report.accounts,
        alignment,
    )

    exporter.export.assert_called_once_with(
        master_path=master_path,
        output_path=output_path,
        alignment=alignment,
        validation=validation,
        excluded_accounts=excluded_accounts,
        duplicate_resolutions=(resolution,),
    )

    assert result.alignment is alignment
    assert result.validation is validation
    assert result.output_path == output_path
    assert result.duplicate_resolution is resolution_result


def test_process_does_not_modify_original_master_accounts(
    source_path: Path,
    master_path: Path,
    output_path: Path,
    duplicate_group: DuplicateGroup,
) -> None:
    (
        processor,
        reader,
        cleaner,
        master_loader,
        duplicate_detector,
        duplicate_resolver,
        matcher,
        validator,
        exporter,
    ) = build_processor()

    _, master_register, _ = configure_analysis_dependencies(
        reader=reader,
        cleaner=cleaner,
        master_loader=master_loader,
        duplicate_detector=duplicate_detector,
        duplicate_resolver=duplicate_resolver,
        duplicate_groups=(duplicate_group,),
    )

    original_master = master_register.accounts.copy(deep=True)

    resolution = DuplicateResolution(
        account_key=duplicate_group.account_key,
        keep_sheet_name="Sheet1",
        keep_master_row=67,
    )

    active_accounts = master_register.accounts.iloc[[0]].copy()
    excluded_accounts = master_register.accounts.iloc[[1]].copy()

    duplicate_resolver.resolve.return_value = (
        DuplicateResolutionResult(
            active_accounts=active_accounts,
            excluded_accounts=excluded_accounts,
            resolutions=(resolution,),
        )
    )
    matcher.align.return_value = Mock(name="alignment")
    validator.validate.return_value = Mock(name="validation")
    exporter.export.return_value = output_path

    processor.process(
        source_path,
        master_path,
        output_path,
        resolutions=(resolution,),
    )

    pd.testing.assert_frame_equal(
        master_register.accounts,
        original_master,
    )


def test_process_requires_resolution_for_master_duplicates(
    source_path: Path,
    master_path: Path,
    output_path: Path,
    duplicate_group: DuplicateGroup,
) -> None:
    (
        processor,
        reader,
        cleaner,
        master_loader,
        duplicate_detector,
        duplicate_resolver,
        matcher,
        validator,
        exporter,
    ) = build_processor()

    configure_analysis_dependencies(
        reader=reader,
        cleaner=cleaner,
        master_loader=master_loader,
        duplicate_detector=duplicate_detector,
        duplicate_resolver=duplicate_resolver,
        duplicate_groups=(duplicate_group,),
    )

    duplicate_resolver.resolve.side_effect = ValueError(
        "A deliberate resolution is required for every duplicate account."
    )

    with pytest.raises(
        ValueError,
        match="deliberate resolution is required",
    ):
        processor.process(
            source_path,
            master_path,
            output_path,
            resolutions=(),
        )

    matcher.align.assert_not_called()
    validator.validate.assert_not_called()
    exporter.export.assert_not_called()

    