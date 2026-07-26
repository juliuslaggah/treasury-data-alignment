from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

import pandas as pd

from app.core.exceptions import DuplicateAccountError
from app.services.account_matcher import AccountMatcher, AlignmentResult
from app.services.data_cleaner import DataCleaner
from app.services.duplicate_detector import DuplicateDetector
from app.services.duplicate_resolver import (
    DuplicateGroup,
    DuplicateResolution,
    DuplicateResolutionResult,
    MasterDuplicateResolver,
)
from app.services.excel_exporter import ExcelExporter
from app.services.file_reader import ReportFileReader
from app.services.master_register import MasterRegisterLoader
from app.services.validator import DataValidator, ValidationResult


class AccountsContainer(Protocol):
    """Object containing a treasury accounts DataFrame."""

    accounts: pd.DataFrame


class SourceDuplicateResult(Protocol):
    """Duplicate-analysis interface required by the processor."""

    has_duplicates: bool


@dataclass(frozen=True, slots=True)
class ProcessingAnalysis:
    """Results produced during the analysis stage."""

    report: AccountsContainer
    master_register: AccountsContainer
    source_duplicates: SourceDuplicateResult
    master_duplicates: tuple[DuplicateGroup, ...]


@dataclass(frozen=True, slots=True)
class ProcessingResult:
    """Final result produced by the processing workflow."""

    report: AccountsContainer
    master_register: AccountsContainer
    duplicates: SourceDuplicateResult
    alignment: AlignmentResult
    validation: ValidationResult
    output_path: Path
    duplicate_resolution: DuplicateResolutionResult | None = None


class ReportProcessor:
    """Coordinate report analysis, resolution, alignment and export."""

    def __init__(
        self,
        *,
        reader: ReportFileReader | None = None,
        cleaner: DataCleaner | None = None,
        master_loader: MasterRegisterLoader | None = None,
        duplicate_detector: DuplicateDetector | None = None,
        duplicate_resolver: MasterDuplicateResolver | None = None,
        matcher: AccountMatcher | None = None,
        validator: DataValidator | None = None,
        exporter: ExcelExporter | None = None,
    ) -> None:
        self.reader = reader or ReportFileReader()
        self.cleaner = cleaner or DataCleaner()
        self.master_loader = master_loader or MasterRegisterLoader()
        self.duplicate_detector = (
            duplicate_detector or DuplicateDetector()
        )
        self.duplicate_resolver = (
            duplicate_resolver or MasterDuplicateResolver()
        )
        self.matcher = matcher or AccountMatcher()
        self.validator = validator or DataValidator()
        self.exporter = exporter or ExcelExporter()

    def analyse(
        self,
        source_path: Path,
        master_path: Path,
    ) -> ProcessingAnalysis:
        """Read and analyse both files without generating an output."""

        source = Path(source_path)
        master = Path(master_path)

        ingested_report = self.reader.read(source)

        cleaned_report = cast(
            AccountsContainer,
            self.cleaner.clean(ingested_report),
        )

        master_register = cast(
            AccountsContainer,
            self.master_loader.load(master),
        )

        source_duplicates = cast(
            SourceDuplicateResult,
            self.duplicate_detector.analyse(
                cleaned_report.accounts
            ),
        )

        master_duplicates = self.duplicate_resolver.analyse(
            master_register.accounts
        )

        return ProcessingAnalysis(
            report=cleaned_report,
            master_register=master_register,
            source_duplicates=source_duplicates,
            master_duplicates=master_duplicates,
        )

    def process(
        self,
        source_path: Path,
        master_path: Path,
        output_path: Path,
        *,
        resolutions: tuple[DuplicateResolution, ...] = (),
    ) -> ProcessingResult:
        """Run the complete treasury processing workflow."""

        source = Path(source_path)
        master = Path(master_path)
        output = Path(output_path)

        analysis = self.analyse(
            source_path=source,
            master_path=master,
        )

        self._ensure_source_accounts_are_unique(
            analysis.source_duplicates
        )

        duplicate_resolution = self.duplicate_resolver.resolve(
            analysis.master_register.accounts,
            resolutions,
        )

        alignment = self.matcher.align(
            analysis.report.accounts,
            duplicate_resolution.active_accounts,
        )

        validation = self.validator.validate(
            analysis.report.accounts,
            alignment,
        )

        self.exporter.export(
            master_path=master,
            output_path=output,
            alignment=alignment,
            validation=validation,
            excluded_accounts=(
                duplicate_resolution.excluded_accounts
            ),
            duplicate_resolutions=(
                duplicate_resolution.resolutions
            ),
        )

        return ProcessingResult(
            report=analysis.report,
            master_register=analysis.master_register,
            duplicates=analysis.source_duplicates,
            alignment=alignment,
            validation=validation,
            output_path=output,
            duplicate_resolution=duplicate_resolution,
        )

    @staticmethod
    def _ensure_source_accounts_are_unique(
        duplicates: SourceDuplicateResult,
    ) -> None:
        """Stop processing if the source report contains duplicates."""

        if duplicates.has_duplicates:
            raise DuplicateAccountError(
                "The source report contains duplicate accounts. "
                "Resolve the source duplicates before continuing."
            )


