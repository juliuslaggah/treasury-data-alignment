import {
  CheckCircle2,
  CloudUpload,
  Database,
  Download,
  FileCheck2,
  FileSpreadsheet,
  Files,
  LoaderCircle,
  Menu,
  RefreshCw,
  ShieldCheck,
  TriangleAlert,
  X,
  createIcons,
} from "lucide";

import {
  ApiError,
  analyseReports,
  checkHealth,
  downloadWorkbook,
  processReports,
} from "./services/api.js";
import "./styles/main.css";

const state = {
  sourceFile: null,
  masterFile: null,
  analysis: null,
  resolutions: new Map(),
  result: null,
  busy: false,
};

const app = document.querySelector("#app");

app.innerHTML = `
  <div class="app-shell">
    <aside class="sidebar" id="sidebar">
      <div class="brand">
        <div class="brand-mark">
          <i data-lucide="database"></i>
        </div>

        <div>
          <p class="brand-title">Treasury Align</p>
          <p class="brand-subtitle">Data Operations</p>
        </div>
      </div>

      <nav class="sidebar-nav" aria-label="Primary navigation">
        <a class="nav-item nav-item-active" href="#workspace">
          <i data-lucide="files"></i>
          <span>Processing workspace</span>
        </a>
      </nav>

      <div class="sidebar-footer">
        <div class="service-status">
          <span
            class="status-dot status-checking"
            id="status-dot"
          ></span>

          <div>
            <p class="status-label">Backend service</p>
            <p class="status-value" id="service-status">
              Checking connection
            </p>
          </div>
        </div>

        <p class="version-label">Version 0.1.0</p>
      </div>
    </aside>

    <main class="main-content">
      <header class="topbar">
        <button
          class="icon-button mobile-menu-button"
          id="menu-button"
          type="button"
          aria-label="Toggle navigation"
        >
          <i data-lucide="menu"></i>
        </button>

        <div>
          <p class="eyebrow">Treasury operations</p>
          <h1>Data cleaning and alignment</h1>
        </div>

        <div class="topbar-badge">
          <i data-lucide="shield-check"></i>
          <span>Controlled workflow</span>
        </div>
      </header>

      <div class="content-container">
        <section class="hero-panel" id="workspace">
          <div>
            <span class="section-label">Workspace</span>
            <h2>Process treasury reports</h2>
            <p>
              Select the current report and approved master workbook.
            </p>
          </div>
        </section>

        <section class="notice-card">
          <i data-lucide="shield-check"></i>

          <div>
            <h3>Validation is automatic</h3>
            <p>
              Duplicate accounts require a deliberate row selection
              before the workbook can be exported.
            </p>
          </div>
        </section>

        <section class="upload-grid" aria-label="File uploads">
          <article class="upload-card">
            <div class="card-heading">
              <div class="card-icon card-icon-blue">
                <i data-lucide="files"></i>
              </div>

              <div>
                <p class="card-step">File 1 of 2</p>
                <h3>Current treasury report</h3>
              </div>
            </div>

            <p class="card-description">
              EOD treasury account report
            </p>

            <label
              class="drop-zone"
              id="source-drop-zone"
              for="source-file"
            >
              <input
                id="source-file"
                type="file"
                accept=".csv,.xlsx,.xls"
                hidden
              />

              <span class="drop-zone-icon">
                <i data-lucide="cloud-upload"></i>
              </span>

              <strong>Select or drop report</strong>
              <span>CSV, XLSX or XLS</span>
            </label>

            <div class="selected-file hidden" id="source-selected">
              <i data-lucide="file-check-2"></i>

              <div>
                <strong id="source-name"></strong>
                <span id="source-size"></span>
              </div>

              <button
                class="remove-file"
                id="remove-source"
                type="button"
                aria-label="Remove source file"
              >
                <i data-lucide="x"></i>
              </button>
            </div>
          </article>

          <article class="upload-card">
            <div class="card-heading">
              <div class="card-icon card-icon-emerald">
                <i data-lucide="file-spreadsheet"></i>
              </div>

              <div>
                <p class="card-step">File 2 of 2</p>
                <h3>Master workbook</h3>
              </div>
            </div>

            <p class="card-description">
              Approved account-order and output template
            </p>

            <label
              class="drop-zone"
              id="master-drop-zone"
              for="master-file"
            >
              <input
                id="master-file"
                type="file"
                accept=".xlsx,.xlsm"
                hidden
              />

              <span class="drop-zone-icon">
                <i data-lucide="cloud-upload"></i>
              </span>

              <strong>Select or drop workbook</strong>
              <span>XLSX or XLSM</span>
            </label>

            <div class="selected-file hidden" id="master-selected">
              <i data-lucide="file-check-2"></i>

              <div>
                <strong id="master-name"></strong>
                <span id="master-size"></span>
              </div>

              <button
                class="remove-file"
                id="remove-master"
                type="button"
                aria-label="Remove master file"
              >
                <i data-lucide="x"></i>
              </button>
            </div>
          </article>
        </section>

        <section class="action-panel">
          <div>
            <h3 id="action-title">Select both files</h3>
            <p id="readiness-message">
              Analysis becomes available when both files are ready.
            </p>
          </div>

          <button
            class="primary-button"
            id="process-button"
            type="button"
            disabled
          >
            <i data-lucide="refresh-cw"></i>
            <span>Analyse files</span>
          </button>
        </section>

        <section
          class="duplicate-resolution-panel hidden"
          id="duplicate-resolution-panel"
          aria-labelledby="duplicate-resolution-title"
        >
          <div class="duplicate-resolution-heading">
            <div class="message-icon">
              <i data-lucide="triangle-alert"></i>
            </div>

            <div>
              <p class="card-step">Action required</p>
              <h2 id="duplicate-resolution-title">
                Resolve duplicate accounts
              </h2>
              <p>
                Select the row that should receive the source
                balance. Other occurrences will be set to 0.00
                in the generated workbook.
              </p>
            </div>
          </div>

          <div
            class="duplicate-list"
            id="duplicate-list"
          ></div>

          <div class="resolution-progress">
            <span id="resolution-progress-message">
              No decisions completed.
            </span>
          </div>
        </section>

        <section
          class="message-panel error-panel hidden"
          id="error-panel"
          role="alert"
        >
          <div class="message-icon">
            <i data-lucide="triangle-alert"></i>
          </div>

          <div>
            <h3>Processing stopped</h3>
            <p id="error-message"></p>
          </div>

          <button
            class="icon-button"
            id="dismiss-error"
            type="button"
            aria-label="Dismiss error"
          >
            <i data-lucide="x"></i>
          </button>
        </section>

        <section class="results-panel hidden" id="results-panel">
          <div class="results-heading">
            <div class="success-icon">
              <i data-lucide="check-circle-2"></i>
            </div>

            <div>
              <p class="card-step">Completed</p>
              <h2>Workbook ready</h2>
              <p>
                Processing and validation completed successfully.
              </p>
            </div>

            <button
              class="download-button"
              id="download-button"
              type="button"
            >
              <i data-lucide="download"></i>
              <span>Download Excel</span>
            </button>
          </div>

          <div class="metrics-grid">
            <article class="metric-card">
              <span>Matched</span>
              <strong id="matched-count">0</strong>
            </article>

            <article class="metric-card">
              <span>Unmatched source</span>
              <strong id="unmatched-source-count">0</strong>
            </article>

            <article class="metric-card">
              <span>Unmatched master</span>
              <strong id="unmatched-master-count">0</strong>
            </article>

            <article class="metric-card">
              <span>Warnings</span>
              <strong id="warning-count">0</strong>
            </article>
          </div>
        </section>
      </div>
    </main>
  </div>
`;

createIcons({
  icons: {
    CheckCircle2,
    CloudUpload,
    Database,
    Download,
    FileCheck2,
    FileSpreadsheet,
    Files,
    LoaderCircle,
    Menu,
    RefreshCw,
    ShieldCheck,
    TriangleAlert,
    X,
  },
});

const elements = {
  sidebar: document.querySelector("#sidebar"),
  menuButton: document.querySelector("#menu-button"),
  serviceStatus: document.querySelector("#service-status"),
  statusDot: document.querySelector("#status-dot"),
  sourceInput: document.querySelector("#source-file"),
  masterInput: document.querySelector("#master-file"),
  sourceDropZone: document.querySelector("#source-drop-zone"),
  masterDropZone: document.querySelector("#master-drop-zone"),
  sourceSelected: document.querySelector("#source-selected"),
  masterSelected: document.querySelector("#master-selected"),
  sourceName: document.querySelector("#source-name"),
  masterName: document.querySelector("#master-name"),
  sourceSize: document.querySelector("#source-size"),
  masterSize: document.querySelector("#master-size"),
  removeSource: document.querySelector("#remove-source"),
  removeMaster: document.querySelector("#remove-master"),
  processButton: document.querySelector("#process-button"),
  actionTitle: document.querySelector("#action-title"),
  readinessMessage: document.querySelector(
    "#readiness-message",
  ),
  duplicateResolutionPanel: document.querySelector(
    "#duplicate-resolution-panel",
  ),
  duplicateList: document.querySelector("#duplicate-list"),
  resolutionProgressMessage: document.querySelector(
    "#resolution-progress-message",
  ),
  errorPanel: document.querySelector("#error-panel"),
  errorMessage: document.querySelector("#error-message"),
  dismissError: document.querySelector("#dismiss-error"),
  resultsPanel: document.querySelector("#results-panel"),
  downloadButton: document.querySelector("#download-button"),
  matchedCount: document.querySelector("#matched-count"),
  unmatchedSourceCount: document.querySelector(
    "#unmatched-source-count",
  ),
  unmatchedMasterCount: document.querySelector(
    "#unmatched-master-count",
  ),
  warningCount: document.querySelector("#warning-count"),
};

elements.sourceInput.addEventListener("change", (event) => {
  setFile("source", event.target.files?.[0] ?? null);
});

elements.masterInput.addEventListener("change", (event) => {
  setFile("master", event.target.files?.[0] ?? null);
});

elements.removeSource.addEventListener("click", () => {
  elements.sourceInput.value = "";
  setFile("source", null);
});

elements.removeMaster.addEventListener("click", () => {
  elements.masterInput.value = "";
  setFile("master", null);
});

elements.processButton.addEventListener(
  "click",
  handlePrimaryAction,
);

elements.downloadButton.addEventListener("click", () => {
  if (state.result) {
    downloadWorkbook(
      state.result.workbook,
      state.result.filename,
    );
  }
});

elements.dismissError.addEventListener("click", hideError);

elements.menuButton.addEventListener("click", () => {
  elements.sidebar.classList.toggle("sidebar-open");
});

configureDropZone(elements.sourceDropZone, "source");
configureDropZone(elements.masterDropZone, "master");

updateReadiness();
checkBackendHealth();

function setFile(type, file) {
  const extensions = (
    type === "source"
      ? [".csv", ".xlsx", ".xls"]
      : [".xlsx", ".xlsm"]
  );

  if (file && !hasAllowedExtension(file, extensions)) {
    showError(
      type === "source"
        ? "Select a CSV, XLSX or XLS source report."
        : "Select an XLSX or XLSM master workbook.",
    );
    return;
  }

  state[`${type}File`] = file;
  resetWorkflow();

  const selected = elements[`${type}Selected`];
  const dropZone = elements[`${type}DropZone`];

  if (!file) {
    selected.classList.add("hidden");
    dropZone.classList.remove("hidden");
    updateReadiness();
    return;
  }

  elements[`${type}Name`].textContent = file.name;
  elements[`${type}Size`].textContent = (
    formatFileSize(file.size)
  );

  dropZone.classList.add("hidden");
  selected.classList.remove("hidden");

  updateReadiness();
}

function resetWorkflow() {
  state.analysis = null;
  state.resolutions.clear();
  state.result = null;

  hideError();
  elements.resultsPanel.classList.add("hidden");
  elements.duplicateResolutionPanel.classList.add(
    "hidden",
  );
  elements.duplicateList.innerHTML = "";
}

function configureDropZone(dropZone, type) {
  for (const eventName of ["dragenter", "dragover"]) {
    dropZone.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropZone.classList.add("drop-zone-active");
    });
  }

  for (const eventName of ["dragleave", "drop"]) {
    dropZone.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropZone.classList.remove("drop-zone-active");
    });
  }

  dropZone.addEventListener("drop", (event) => {
    setFile(
      type,
      event.dataTransfer?.files?.[0] ?? null,
    );
  });
}

async function handlePrimaryAction() {
  if (
    !state.sourceFile
    || !state.masterFile
    || state.busy
  ) {
    return;
  }

  if (!state.analysis) {
    await analyseSelectedFiles();
    return;
  }

  if (allDuplicateGroupsResolved()) {
    await processSelectedFiles();
  }
}

async function analyseSelectedFiles() {
  setBusy(true, "Analysing...");
  hideError();
  elements.resultsPanel.classList.add("hidden");

  let continueAutomatically = false;

  try {
    state.analysis = await analyseReports(
      state.sourceFile,
      state.masterFile,
    );

    if (state.analysis.sourceHasDuplicates) {
      showError(
        "The source report contains duplicate accounts. "
        + "Resolve the source report before continuing.",
      );
      return;
    }

    if (state.analysis.duplicates.length > 0) {
      renderDuplicateResolutions();
    } else {
      continueAutomatically = true;
    }
  } catch (error) {
    state.analysis = null;
    showError(
      error instanceof ApiError
        ? error.message
        : "Unexpected analysis error.",
    );
  } finally {
    setBusy(false);
    updateReadiness();
  }

  if (continueAutomatically) {
    await processSelectedFiles();
  }
}

async function processSelectedFiles() {
  if (
    !state.sourceFile
    || !state.masterFile
    || state.busy
  ) {
    return;
  }

  if (
    state.analysis?.duplicates.length > 0
    && !allDuplicateGroupsResolved()
  ) {
    showError(
      "Select one row to keep for every duplicate account.",
    );
    return;
  }

  setBusy(true, "Processing...");
  hideError();
  elements.resultsPanel.classList.add("hidden");

  try {
    state.result = await processReports(
      state.sourceFile,
      state.masterFile,
      Array.from(state.resolutions.values()),
    );

    displayResult(state.result);
  } catch (error) {
    showError(
      error instanceof ApiError
        ? error.message
        : "Unexpected processing error.",
    );
  } finally {
    setBusy(false);
    updateReadiness();
  }
}

function renderDuplicateResolutions() {
  const duplicates = state.analysis?.duplicates ?? [];

  elements.duplicateList.innerHTML = duplicates
    .map((group, groupIndex) => (
      renderDuplicateGroup(group, groupIndex)
    ))
    .join("");

  elements.duplicateResolutionPanel.classList.remove(
    "hidden",
  );

  elements.duplicateList
    .querySelectorAll("[data-resolution-option]")
    .forEach((button) => {
      button.addEventListener("click", () => {
        selectDuplicateOccurrence(
          Number(button.dataset.groupIndex),
          Number(button.dataset.occurrenceIndex),
        );
      });
    });

  updateResolutionProgress();

  elements.duplicateResolutionPanel.scrollIntoView({
    behavior: "smooth",
    block: "start",
  });
}

function renderDuplicateGroup(group, groupIndex) {
  const selected = state.resolutions.get(
    group.accountKey,
  );

  const occurrenceMarkup = group.occurrences
    .map((occurrence, occurrenceIndex) => {
      const isSelected = Boolean(
        selected
        && selected.keepSheetName === occurrence.sheetName
        && selected.keepMasterRow === occurrence.masterRow
      );
      const isExcluded = Boolean(
        selected && !isSelected
      );

      const stateClass = isSelected
        ? "resolution-option-selected"
        : isExcluded
          ? "resolution-option-excluded"
          : "";

      const actionLabel = isSelected
        ? "Selected row"
        : isExcluded
          ? "Will be set to 0.00"
          : "Keep this row";

      return `
        <button
          class="resolution-option ${stateClass}"
          type="button"
          data-resolution-option
          data-group-index="${groupIndex}"
          data-occurrence-index="${occurrenceIndex}"
          aria-pressed="${isSelected}"
        >
          <span class="resolution-row-location">
            <strong>
              ${escapeHtml(occurrence.sheetName)}
            </strong>
            <span>Row ${occurrence.masterRow}</span>
          </span>

          <span class="resolution-account-name">
            ${escapeHtml(occurrence.accountName)}
          </span>

          <span class="resolution-option-action">
            ${actionLabel}
          </span>
        </button>
      `;
    })
    .join("");

  return `
    <article class="duplicate-group">
      <div class="duplicate-group-heading">
        <div>
          <p class="card-step">Duplicate account</p>
          <h3>${escapeHtml(group.accountName)}</h3>
        </div>

        <span class="duplicate-count-badge">
          ${group.occurrences.length} rows
        </span>
      </div>

      <div class="resolution-options">
        ${occurrenceMarkup}
      </div>
    </article>
  `;
}

function selectDuplicateOccurrence(
  groupIndex,
  occurrenceIndex,
) {
  const group = state.analysis?.duplicates[groupIndex];
  const occurrence = group?.occurrences[occurrenceIndex];

  if (!group || !occurrence) {
    return;
  }

  state.resolutions.set(
    group.accountKey,
    {
      accountKey: group.accountKey,
      keepSheetName: occurrence.sheetName,
      keepMasterRow: occurrence.masterRow,
    },
  );

  renderDuplicateResolutions();
  updateReadiness();
}

function allDuplicateGroupsResolved() {
  const duplicates = state.analysis?.duplicates ?? [];

  return (
    duplicates.length === 0
    || duplicates.every((group) => (
      state.resolutions.has(group.accountKey)
    ))
  );
}

function updateResolutionProgress() {
  const duplicateCount = (
    state.analysis?.duplicates.length ?? 0
  );
  const completedCount = state.resolutions.size;

  elements.resolutionProgressMessage.textContent = (
    `${completedCount} of ${duplicateCount} `
    + "duplicate decisions completed."
  );
}

function setBusy(busy, label = "") {
  state.busy = busy;

  elements.processButton.disabled = busy;
  elements.processButton.classList.toggle(
    "button-loading",
    busy,
  );

  if (busy) {
    elements.processButton.innerHTML = `
      <i data-lucide="loader-circle"></i>
      <span>${escapeHtml(label)}</span>
    `;

    createIcons({
      icons: {
        LoaderCircle,
      },
    });
  }
}

function displayResult(result) {
  elements.matchedCount.textContent = (
    result.summary.matchedCount
  );
  elements.unmatchedSourceCount.textContent = (
    result.summary.unmatchedSourceCount
  );
  elements.unmatchedMasterCount.textContent = (
    result.summary.unmatchedMasterCount
  );
  elements.warningCount.textContent = (
    result.summary.warningCount
  );

  elements.resultsPanel.classList.remove("hidden");
  elements.resultsPanel.scrollIntoView({
    behavior: "smooth",
    block: "start",
  });
}

function updateReadiness() {
  const filesReady = Boolean(
    state.sourceFile && state.masterFile,
  );

  if (!filesReady) {
    updateActionPanel(
      "Select both files",
      "Analysis becomes available when both files are ready.",
      "Analyse files",
      true,
    );
    return;
  }

  if (state.busy) {
    return;
  }

  if (!state.analysis) {
    updateActionPanel(
      "Ready to analyse",
      "Both files are ready for duplicate analysis.",
      "Analyse files",
      false,
    );
    return;
  }

  const duplicateCount = state.analysis.duplicates.length;

  if (
    duplicateCount > 0
    && !allDuplicateGroupsResolved()
  ) {
    updateActionPanel(
      "Resolve duplicate accounts",
      (
        `${state.resolutions.size} of ${duplicateCount} `
        + "decisions completed."
      ),
      "Continue processing",
      true,
    );
    return;
  }

  if (duplicateCount > 0) {
    updateActionPanel(
      "Duplicate decisions complete",
      "The selected rows are ready for processing.",
      "Continue processing",
      false,
    );
    return;
  }

  updateActionPanel(
    "Ready to process",
    "No duplicate master accounts require review.",
    "Process files",
    false,
  );
}

function updateActionPanel(
  title,
  message,
  buttonLabel,
  disabled,
) {
  elements.actionTitle.textContent = title;
  elements.readinessMessage.textContent = message;
  elements.processButton.disabled = disabled;

  elements.processButton.innerHTML = `
    <i data-lucide="refresh-cw"></i>
    <span>${escapeHtml(buttonLabel)}</span>
  `;

  createIcons({
    icons: {
      RefreshCw,
    },
  });
}

function showError(message) {
  elements.errorMessage.textContent = message;
  elements.errorPanel.classList.remove("hidden");
  elements.errorPanel.scrollIntoView({
    behavior: "smooth",
    block: "center",
  });
}

function hideError() {
  elements.errorPanel.classList.add("hidden");
  elements.errorMessage.textContent = "";
}

async function checkBackendHealth() {
  try {
    await checkHealth();

    elements.serviceStatus.textContent = "Connected";
    elements.statusDot.className = (
      "status-dot status-connected"
    );
  } catch {
    elements.serviceStatus.textContent = "Unavailable";
    elements.statusDot.className = (
      "status-dot status-disconnected"
    );
  }
}

function hasAllowedExtension(file, extensions) {
  const name = file.name.toLowerCase();

  return extensions.some((extension) => (
    name.endsWith(extension)
  ));
}

function formatFileSize(bytes) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }

  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }

  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

