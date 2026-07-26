const API_BASE_URL = "/api/v1";

export class ApiError extends Error {
  constructor(message, status = 0, details = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
  }
}

export async function checkHealth() {
  const response = await fetch(`${API_BASE_URL}/health`, {
    method: "GET",
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw await createApiError(response);
  }

  return response.json();
}

export async function analyseReports(
  sourceFile,
  masterFile,
) {
  const formData = createFilesFormData(
    sourceFile,
    masterFile,
  );

  const response = await fetch(
    `${API_BASE_URL}/processing/analyse`,
    {
      method: "POST",
      body: formData,
      headers: {
        Accept: "application/json",
      },
    },
  );

  if (!response.ok) {
    throw await createApiError(response);
  }

  const analysis = await response.json();

  return {
    requiresResolution: Boolean(
      analysis.requires_resolution,
    ),
    sourceHasDuplicates: Boolean(
      analysis.source_has_duplicates,
    ),
    duplicateCount: Number(
      analysis.duplicate_count ?? 0,
    ),
    duplicates: Array.isArray(analysis.duplicates)
      ? analysis.duplicates.map(normaliseDuplicateGroup)
      : [],
  };
}

export async function processReports(
  sourceFile,
  masterFile,
  resolutions = [],
) {
  const formData = createFilesFormData(
    sourceFile,
    masterFile,
  );

  formData.append(
    "resolutions",
    JSON.stringify(
      resolutions.map(serialiseResolution),
    ),
  );

  const response = await fetch(
    `${API_BASE_URL}/processing/process`,
    {
      method: "POST",
      body: formData,
    },
  );

  if (!response.ok) {
    throw await createApiError(response);
  }

  const workbook = await response.blob();

  return {
    workbook,
    filename: extractFilename(
      response.headers.get("content-disposition"),
    ),
    summary: {
      matchedCount: readNumberHeader(
        response,
        "x-matched-count",
      ),
      unmatchedSourceCount: readNumberHeader(
        response,
        "x-unmatched-source-count",
      ),
      unmatchedMasterCount: readNumberHeader(
        response,
        "x-unmatched-master-count",
      ),
      warningCount: readNumberHeader(
        response,
        "x-validation-warning-count",
      ),
    },
  };
}

export function downloadWorkbook(
  workbook,
  filename,
) {
  const objectUrl = URL.createObjectURL(workbook);
  const link = document.createElement("a");

  link.href = objectUrl;
  link.download = filename || "aligned-report.xlsx";
  link.style.display = "none";

  document.body.appendChild(link);
  link.click();
  link.remove();

  URL.revokeObjectURL(objectUrl);
}

function createFilesFormData(
  sourceFile,
  masterFile,
) {
  const formData = new FormData();

  formData.append("source_file", sourceFile);
  formData.append("master_file", masterFile);

  return formData;
}

function normaliseDuplicateGroup(group) {
  return {
    accountKey: String(group?.account_key ?? ""),
    accountName: String(group?.account_name ?? ""),
    occurrences: Array.isArray(group?.occurrences)
      ? group.occurrences.map(normaliseOccurrence)
      : [],
  };
}

function normaliseOccurrence(occurrence) {
  return {
    sheetName: String(
      occurrence?.sheet_name ?? "",
    ),
    masterRow: Number(
      occurrence?.master_row ?? 0,
    ),
    accountName: String(
      occurrence?.account_name ?? "",
    ),
    sourceIndex: Number(
      occurrence?.source_index ?? 0,
    ),
  };
}

function serialiseResolution(resolution) {
  return {
    account_key: resolution.accountKey,
    keep_sheet_name: resolution.keepSheetName,
    keep_master_row: resolution.keepMasterRow,
  };
}

async function createApiError(response) {
  let details = null;
  let message = (
    `The server returned status ${response.status}.`
  );

  try {
    details = await response.json();

    if (typeof details?.detail === "string") {
      message = details.detail;
    } else if (Array.isArray(details?.detail)) {
      message = details.detail
        .map((item) => item.msg)
        .filter(Boolean)
        .join(" ");
    }
  } catch {
    // Preserve the status-based fallback message.
  }

  return new ApiError(
    message,
    response.status,
    details,
  );
}

function readNumberHeader(response, headerName) {
  const value = Number.parseInt(
    response.headers.get(headerName) ?? "0",
    10,
  );

  return Number.isNaN(value) ? 0 : value;
}

function extractFilename(contentDisposition) {
  if (!contentDisposition) {
    return "aligned-report.xlsx";
  }

  const encodedMatch = contentDisposition.match(
    /filename\*=UTF-8''([^;]+)/i,
  );

  if (encodedMatch) {
    return decodeURIComponent(encodedMatch[1]);
  }

  const filenameMatch = contentDisposition.match(
    /filename="?([^";]+)"?/i,
  );

  return filenameMatch?.[1] ?? "aligned-report.xlsx";
}

