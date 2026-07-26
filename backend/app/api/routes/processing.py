import json
from json import JSONDecodeError
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated, cast

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.core.exceptions import ApplicationError
from app.core.logging import get_logger
from app.services.duplicate_resolver import (
    DuplicateGroup,
    DuplicateResolution,
)
from app.services.report_processor import ReportProcessor

router = APIRouter(
    prefix="/processing",
    tags=["processing"],
)

logger = get_logger(__name__)

EXCEL_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument."
    "spreadsheetml.sheet"
)

SOURCE_EXTENSIONS = {".csv", ".xlsx", ".xls"}
MASTER_EXTENSIONS = {".xlsx", ".xlsm"}


@router.post(
    "/analyse",
    response_class=JSONResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyse a treasury report for duplicate accounts",
)
async def analyse_report(
    source_file: Annotated[UploadFile, File()],
    master_file: Annotated[UploadFile, File()],
) -> JSONResponse:
    """Analyse uploaded files and return duplicate row locations."""

    (
        source_name,
        master_name,
        source_extension,
        master_extension,
    ) = _validate_uploaded_files(
        source_file,
        master_file,
    )

    del source_name, master_name

    with TemporaryDirectory(
        prefix="treasury-analysis-"
    ) as temporary_directory:
        working_directory = Path(temporary_directory)

        source_path = (
            working_directory / f"source{source_extension}"
        )
        master_path = (
            working_directory / f"master{master_extension}"
        )

        await _save_uploaded_files(
            source_file=source_file,
            master_file=master_file,
            source_path=source_path,
            master_path=master_path,
        )

        processor = ReportProcessor()

        try:
            analysis = await run_in_threadpool(
                processor.analyse,
                source_path,
                master_path,
            )
        except ApplicationError as exc:
            logger.exception(
                "report_analysis_failed",
                error=str(exc),
                cause=repr(exc.__cause__),
            )

            raise HTTPException(
                status_code=(
                    status.HTTP_422_UNPROCESSABLE_CONTENT
                ),
                detail=str(exc),
            ) from exc

        duplicates = [
            _serialise_duplicate_group(group)
            for group in analysis.master_duplicates
        ]

        source_has_duplicates = (
            analysis.source_duplicates.has_duplicates
        )

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "requires_resolution": (
                    source_has_duplicates
                    or bool(analysis.master_duplicates)
                ),
                "source_has_duplicates": (
                    source_has_duplicates
                ),
                "duplicate_count": len(
                    analysis.master_duplicates
                ),
                "duplicates": duplicates,
            },
        )


@router.post(
    "/process",
    response_class=Response,
    status_code=status.HTTP_200_OK,
    summary="Process and align a treasury report",
)
async def process_report(
    source_file: Annotated[UploadFile, File()],
    master_file: Annotated[UploadFile, File()],
    resolutions: Annotated[str, Form()] = "[]",
) -> Response:
    """Resolve duplicates, align accounts and return an Excel report."""

    parsed_resolutions = _parse_resolutions(resolutions)

    (
        source_name,
        master_name,
        source_extension,
        master_extension,
    ) = _validate_uploaded_files(
        source_file,
        master_file,
    )

    del master_name

    with TemporaryDirectory(
        prefix="treasury-alignment-"
    ) as temporary_directory:
        working_directory = Path(temporary_directory)

        source_path = (
            working_directory / f"source{source_extension}"
        )
        master_path = (
            working_directory / f"master{master_extension}"
        )
        output_path = (
            working_directory / "aligned-report.xlsx"
        )

        await _save_uploaded_files(
            source_file=source_file,
            master_file=master_file,
            source_path=source_path,
            master_path=master_path,
        )

        processor = ReportProcessor()

        try:
            result = await run_in_threadpool(
                processor.process,
                source_path,
                master_path,
                output_path,
                resolutions=parsed_resolutions,
            )
        except (ApplicationError, ValueError) as exc:
            logger.exception(
                "report_processing_failed",
                error=str(exc),
                cause=repr(exc.__cause__),
            )

            raise HTTPException(
                status_code=(
                    status.HTTP_422_UNPROCESSABLE_CONTENT
                ),
                detail=str(exc),
            ) from exc

        output_content = result.output_path.read_bytes()
        output_filename = (
            f"aligned_{Path(source_name).stem}.xlsx"
        )

        headers = {
            "Content-Disposition": (
                f'attachment; filename="{output_filename}"'
            ),
            "X-Matched-Count": str(
                result.alignment.matched_count
            ),
            "X-Unmatched-Source-Count": str(
                result.alignment.unmatched_source_count
            ),
            "X-Unmatched-Master-Count": str(
                result.alignment.unmatched_master_count
            ),
            "X-Validation-Warning-Count": str(
                result.validation.warning_count
            ),
        }

        return Response(
            content=output_content,
            media_type=EXCEL_MEDIA_TYPE,
            headers=headers,
        )


def _validate_uploaded_files(
    source_file: UploadFile,
    master_file: UploadFile,
) -> tuple[str, str, str, str]:
    """Validate upload filenames and supported extensions."""

    source_name = _require_filename(
        source_file,
        "source report",
    )
    master_name = _require_filename(
        master_file,
        "master template",
    )

    source_extension = Path(source_name).suffix.lower()
    master_extension = Path(master_name).suffix.lower()

    if source_extension not in SOURCE_EXTENSIONS:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_CONTENT
            ),
            detail=(
                "The source report must be a CSV, XLSX, or XLS file."
            ),
        )

    if master_extension not in MASTER_EXTENSIONS:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_CONTENT
            ),
            detail=(
                "The master template must be an XLSX or XLSM workbook."
            ),
        )

    return (
        source_name,
        master_name,
        source_extension,
        master_extension,
    )


async def _save_uploaded_files(
    *,
    source_file: UploadFile,
    master_file: UploadFile,
    source_path: Path,
    master_path: Path,
) -> None:
    """Save uploaded files inside the temporary working directory."""

    source_content = await source_file.read()
    master_content = await master_file.read()

    source_path.write_bytes(source_content)
    master_path.write_bytes(master_content)


def _parse_resolutions(
    resolutions: str,
) -> tuple[DuplicateResolution, ...]:
    """Parse and validate duplicate resolutions submitted as JSON."""

    try:
        decoded: object = json.loads(resolutions)
    except (JSONDecodeError, TypeError) as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_CONTENT
            ),
            detail=(
                "Duplicate resolutions must be valid JSON."
            ),
        ) from exc

    if not isinstance(decoded, list):
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_CONTENT
            ),
            detail=(
                "Duplicate resolutions must be a JSON array."
            ),
        )

    parsed: list[DuplicateResolution] = []

    for item in decoded:
        if not isinstance(item, dict):
            raise HTTPException(
                status_code=(
                    status.HTTP_422_UNPROCESSABLE_CONTENT
                ),
                detail=(
                    "Each duplicate resolution must be "
                    "a JSON object."
                ),
            )

        resolution_data = cast(
            dict[str, object],
            item,
        )

        account_key = _required_resolution_text(
            resolution_data,
            "account_key",
        )
        keep_sheet_name = _required_resolution_text(
            resolution_data,
            "keep_sheet_name",
        )
        keep_master_row = resolution_data.get(
            "keep_master_row"
        )

        if (
            isinstance(keep_master_row, bool)
            or not isinstance(keep_master_row, int)
            or keep_master_row < 1
        ):
            raise HTTPException(
                status_code=(
                    status.HTTP_422_UNPROCESSABLE_CONTENT
                ),
                detail=(
                    "Each duplicate resolution must contain "
                    "a positive integer keep_master_row."
                ),
            )

        parsed.append(
            DuplicateResolution(
                account_key=account_key,
                keep_sheet_name=keep_sheet_name,
                keep_master_row=keep_master_row,
            )
        )

    return tuple(parsed)


def _required_resolution_text(
    resolution: dict[str, object],
    field_name: str,
) -> str:
    """Return a required non-empty resolution text value."""

    value = resolution.get(field_name)

    if not isinstance(value, str) or not value.strip():
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_CONTENT
            ),
            detail=(
                "Each duplicate resolution must contain "
                f"a non-empty {field_name}."
            ),
        )

    return value.strip()


def _serialise_duplicate_group(
    group: DuplicateGroup,
) -> dict[str, object]:
    """Convert a duplicate group into a JSON-safe response."""

    return {
        "account_key": group.account_key,
        "account_name": group.account_name,
        "occurrences": [
            {
                "sheet_name": occurrence.sheet_name,
                "master_row": occurrence.master_row,
                "account_name": occurrence.account_name,
                "source_index": occurrence.source_index,
            }
            for occurrence in group.occurrences
        ],
    }


def _require_filename(
    uploaded_file: UploadFile,
    description: str,
) -> str:
    """Return a safe filename or raise a validation error."""

    filename = uploaded_file.filename

    if filename is None or not filename.strip():
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_CONTENT
            ),
            detail=(
                f"The {description} must have a filename."
            ),
        )

    return Path(filename).name

    