import json
from pathlib import Path
from unittest.mock import Mock

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.account_matcher import AlignmentResult
from app.services.duplicate_resolver import (
    DuplicateGroup,
    DuplicateOccurrence,
    DuplicateResolution,
)
from app.services.report_processor import (
    ProcessingAnalysis,
    ProcessingResult,
    ReportProcessor,
)
from app.services.validator import ValidationResult

client = TestClient(app)


def test_analyse_endpoint_returns_duplicate_locations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    duplicate_group = DuplicateGroup(
        account_key="SIERRA LEONE STANDARD BUREAU DISBUR",
        account_name="SIERRA LEONE STANDARD BUREAU DISBUR",
        occurrences=(
            DuplicateOccurrence(
                sheet_name="Treasury Report",
                master_row=67,
                account_name=(
                    "SIERRA LEONE STANDARD BUREAU DISBUR"
                ),
                source_index=65,
            ),
            DuplicateOccurrence(
                sheet_name="Treasury Report",
                master_row=257,
                account_name=(
                    "SIERRA LEONE STANDARD BUREAU DISBUR"
                ),
                source_index=255,
            ),
        ),
    )

    source_duplicates = Mock()
    source_duplicates.has_duplicates = False

    def fake_analyse(
        self: ReportProcessor,
        source_path: Path,
        master_path: Path,
    ) -> ProcessingAnalysis:
        del self, source_path, master_path

        return ProcessingAnalysis(
            report=Mock(),
            master_register=Mock(),
            source_duplicates=source_duplicates,
            master_duplicates=(duplicate_group,),
        )

    monkeypatch.setattr(
        ReportProcessor,
        "analyse",
        fake_analyse,
    )

    response = client.post(
        "/api/v1/processing/analyse",
        files={
            "source_file": (
                "report.csv",
                (
                    b"ACCOUNT NAME,DAILY BAL\n"
                    b"ACCOUNT ONE,100.00"
                ),
                "text/csv",
            ),
            "master_file": (
                "master.xlsx",
                b"excel-template",
                (
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
            ),
        },
    )

    assert response.status_code == 200

    response_data = response.json()

    assert response_data["requires_resolution"] is True
    assert response_data["duplicate_count"] == 1
    assert response_data["source_has_duplicates"] is False

    duplicates = response_data["duplicates"]

    assert len(duplicates) == 1
    assert duplicates[0]["account_key"] == (
        "SIERRA LEONE STANDARD BUREAU DISBUR"
    )
    assert duplicates[0]["account_name"] == (
        "SIERRA LEONE STANDARD BUREAU DISBUR"
    )
    assert duplicates[0]["occurrences"] == [
        {
            "sheet_name": "Treasury Report",
            "master_row": 67,
            "account_name": (
                "SIERRA LEONE STANDARD BUREAU DISBUR"
            ),
            "source_index": 65,
        },
        {
            "sheet_name": "Treasury Report",
            "master_row": 257,
            "account_name": (
                "SIERRA LEONE STANDARD BUREAU DISBUR"
            ),
            "source_index": 255,
        },
    ]


def test_process_endpoint_returns_generated_workbook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    alignment = AlignmentResult(
        aligned=pd.DataFrame(
            [
                {
                    "MATCH STATUS": "MATCHED",
                    "ACCOUNT NAME": "ACCOUNT ONE",
                }
            ]
        ),
        unmatched_source=pd.DataFrame(),
        unmatched_master=pd.DataFrame(),
    )
    validation = ValidationResult(issues=())

    received_resolutions: list[
        tuple[DuplicateResolution, ...]
    ] = []

    def fake_process(
        self: ReportProcessor,
        source_path: Path,
        master_path: Path,
        output_path: Path,
        *,
        resolutions: tuple[
            DuplicateResolution, ...
        ] = (),
    ) -> ProcessingResult:
        del self, source_path, master_path

        received_resolutions.append(resolutions)
        output_path.write_bytes(
            b"generated-excel-workbook"
        )

        return ProcessingResult(
            report=Mock(),
            master_register=Mock(),
            duplicates=Mock(),
            alignment=alignment,
            validation=validation,
            output_path=output_path,
        )

    monkeypatch.setattr(
        ReportProcessor,
        "process",
        fake_process,
    )

    resolutions = [
        {
            "account_key": (
                "SIERRA LEONE STANDARD BUREAU DISBUR"
            ),
            "keep_sheet_name": "Treasury Report",
            "keep_master_row": 67,
        }
    ]

    response = client.post(
        "/api/v1/processing/process",
        files={
            "source_file": (
                "report.csv",
                (
                    b"ACCOUNT NAME,DAILY BAL\n"
                    b"ACCOUNT ONE,100.00"
                ),
                "text/csv",
            ),
            "master_file": (
                "master.xlsx",
                b"excel-template",
                (
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
            ),
        },
        data={
            "resolutions": json.dumps(resolutions),
        },
    )

    assert response.status_code == 200
    assert response.content == b"generated-excel-workbook"
    assert response.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument."
        "spreadsheetml.sheet"
    )
    assert "attachment;" in response.headers[
        "content-disposition"
    ]
    assert response.headers["x-matched-count"] == "1"
    assert response.headers[
        "x-unmatched-source-count"
    ] == "0"
    assert response.headers[
        "x-unmatched-master-count"
    ] == "0"
    assert response.headers[
        "x-validation-warning-count"
    ] == "0"

    assert received_resolutions == [
        (
            DuplicateResolution(
                account_key=(
                    "SIERRA LEONE STANDARD BUREAU DISBUR"
                ),
                keep_sheet_name="Treasury Report",
                keep_master_row=67,
            ),
        )
    ]


def test_process_endpoint_rejects_invalid_resolution_json() -> None:
    response = client.post(
        "/api/v1/processing/process",
        files={
            "source_file": (
                "report.csv",
                (
                    b"ACCOUNT NAME,DAILY BAL\n"
                    b"ACCOUNT ONE,100.00"
                ),
                "text/csv",
            ),
            "master_file": (
                "master.xlsx",
                b"excel-template",
                (
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
            ),
        },
        data={
            "resolutions": "not-valid-json",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "Duplicate resolutions must be valid JSON."
    )


def test_process_endpoint_rejects_invalid_source_extension() -> None:
    response = client.post(
        "/api/v1/processing/process",
        files={
            "source_file": (
                "report.txt",
                b"not a supported report",
                "text/plain",
            ),
            "master_file": (
                "master.xlsx",
                b"excel-template",
                (
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
            ),
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "The source report must be a CSV, XLSX, or XLS file."
    )


def test_process_endpoint_rejects_invalid_master_extension() -> None:
    response = client.post(
        "/api/v1/processing/process",
        files={
            "source_file": (
                "report.csv",
                (
                    b"ACCOUNT NAME,DAILY BAL\n"
                    b"ACCOUNT ONE,100.00"
                ),
                "text/csv",
            ),
            "master_file": (
                "master.csv",
                b"not an Excel template",
                "text/csv",
            ),
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "The master template must be an XLSX or XLSM workbook."
    )

