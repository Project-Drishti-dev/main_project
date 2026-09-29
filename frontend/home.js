(() => {
  const MAX_IMAGE_BYTES = 10 * 1024 * 1024;
  const SUPPORTED_IMAGE_TYPES = new Set([
    "image/jpeg",
    "image/png",
    "image/webp",
  ]);

  const workspaceShell = document.getElementById("workspace-shell");
  const sidebar = document.getElementById("app-sidebar");
  const sidebarToggle = document.getElementById("sidebar-toggle");
  const sourceChooser = document.getElementById("source-chooser");
  const uploadStep = document.getElementById("upload-step");
  const uploadButton = document.getElementById("choose-upload");
  const cameraButton = document.getElementById("choose-camera");
  const backButton = document.getElementById("back-to-source");
  const fileInput = document.getElementById("screening-file");
  const fileError = document.getElementById("file-error");
  const previewPanel = document.getElementById("preview-panel");
  const imagePreview = document.getElementById("image-preview");
  const fileDetails = document.getElementById("file-details");
  const imageDimensions = document.getElementById("image-dimensions");
  const runButton = document.getElementById("run-screening");
  const screeningModal = document.getElementById("screening-modal");
  const screeningCloseButton = document.getElementById("screening-modal-close");
  const resultsModal = document.getElementById("results-modal");
  const resultsIntro = document.getElementById("results-intro");
  const overallResult = document.getElementById("overall-result");
  const analysisStatus = document.getElementById("analysis-status");
  const resultsCloseButton = document.getElementById("results-modal-close");
  const sourceMessage = document.getElementById("screening-source-message");
  const chooseAnotherButton = document.getElementById("choose-another-image");
  const startScreeningButton = document.getElementById("start-screening");
  const metricCards = Array.from(document.querySelectorAll(".metric-card"));
  const apiBaseUrl =
    typeof window.DRISHTI_CONFIG?.apiBaseUrl === "string"
      ? window.DRISHTI_CONFIG.apiBaseUrl.trim().replace(/\/+$/, "")
      : "";

  const EXPECTED_MODULES = new Set([
    "sharpness",
    "noise",
    "exposure",
    "uniformity",
    "glare",
    "ppi",
    "skew",
    "coverage",
    "completeness",
  ]);
  const MODULE_KEYS_BY_LABEL = new Map([
    ["Sharpness", "sharpness"],
    ["Noise", "noise"],
    ["Exposure", "exposure"],
    ["Lighting uniformity", "uniformity"],
    ["Glare", "glare"],
    ["Resolution (PPI)", "ppi"],
    ["Skew / perspective", "skew"],
    ["Card coverage", "coverage"],
    ["Completeness (cut/crop)", "completeness"],
  ]);
  const RUN_BUTTON_LABEL = "Review quality checks";

  let selectedFile = null;
  let previewUrl = null;
  let activeModal = null;
  let isAnalyzing = false;

  startScreeningButton.addEventListener("click", () => {
    showSourceChooser();
    activeModal = screeningModal;
    setTimeout(() => uploadButton.focus(), 0);
  });

  sidebarToggle.addEventListener("click", () => {
    const expanded = sidebar.classList.toggle("is-expanded");
    workspaceShell.classList.toggle("is-sidebar-expanded", expanded);
    sidebarToggle.setAttribute("aria-expanded", String(expanded));
    sidebarToggle.setAttribute(
      "aria-label",
      expanded ? "Collapse sidebar" : "Expand sidebar",
    );
    sidebarToggle.setAttribute(
      "title",
      expanded ? "Collapse sidebar" : "Expand sidebar",
    );
  });

  uploadButton.addEventListener("click", () => {
    sourceChooser.hidden = true;
    uploadStep.hidden = false;
    sourceMessage.textContent = "";
    fileInput.focus();
  });

  cameraButton.addEventListener("click", () => {
    sourceMessage.textContent =
      "Camera capture is coming soon. For now, upload an existing image.";
  });

  backButton.addEventListener("click", () => {
    resetUpload();
    showSourceChooser();
    uploadButton.focus();
  });

  fileInput.addEventListener("change", () => {
    const file = fileInput.files && fileInput.files[0];
    resetUpload();

    if (!file) return;
    if (!SUPPORTED_IMAGE_TYPES.has(file.type)) {
      fileError.textContent = "Choose a JPEG, PNG, or WebP image.";
      return;
    }
    if (file.size > MAX_IMAGE_BYTES) {
      fileError.textContent = "Choose an image that is 10 MB or smaller.";
      return;
    }

    selectedFile = file;
    previewUrl = URL.createObjectURL(file);
    imagePreview.src = previewUrl;
    imagePreview.alt = `Preview of ${file.name}`;
    fileDetails.textContent = `${file.name} · ${formatFileSize(file.size)}`;
    imageDimensions.textContent = "Checking image…";
    previewPanel.hidden = false;
    fileInput.value = "";
  });

  imagePreview.addEventListener("load", () => {
    if (!selectedFile || imagePreview.src !== previewUrl) return;
    if (imagePreview.naturalWidth && imagePreview.naturalHeight) {
      imageDimensions.textContent =
        `${imagePreview.naturalWidth} × ${imagePreview.naturalHeight} px`;
      runButton.disabled = false;
    }
  });

  imagePreview.addEventListener("error", () => {
    resetUpload();
    fileError.textContent =
      "This file could not be opened as an image. Choose a valid JPEG, PNG, or WebP.";
  });

  runButton.addEventListener("click", async () => {
    if (!selectedFile || isAnalyzing) return;
    if (!apiBaseUrl) {
      fileError.textContent =
        "The quality API is not configured for this site yet.";
      return;
    }

    const fileToAnalyze = selectedFile;
    const formData = new FormData();
    formData.append("image", fileToAnalyze);
    formData.append("mode", "auto");

    isAnalyzing = true;
    fileError.textContent = "";
    analysisStatus.textContent = "Analyzing image…";
    runButton.disabled = true;
    runButton.textContent = "Analyzing…";
    fileInput.disabled = true;
    backButton.disabled = true;
    screeningCloseButton.disabled = true;
    analysisStatus.focus();
    clearMetricResults();

    try {
      const response = await fetch(`${apiBaseUrl}/api/analyze`, {
        method: "POST",
        body: formData,
      });
      let payload = null;
      try {
        payload = await response.json();
      } catch {
        payload = null;
      }

      if (!response.ok) {
        const apiMessage = payload?.error?.message;
        fileError.textContent =
          typeof apiMessage === "string" && apiMessage.trim()
            ? apiMessage
            : `The quality API returned an error (${response.status}).`;
        return;
      }

      if (!isAnalysisResponse(payload)) {
        fileError.textContent =
          "The quality API returned an unexpected response. Please try again.";
        return;
      }

      renderAnalysis(payload, fileToAnalyze.name);
      screeningModal.classList.remove("is-open");
      resultsModal.classList.add("is-open");
      document.body.style.overflow = "hidden";
      activeModal = resultsModal;
      resultsCloseButton.focus();
    } catch {
      fileError.textContent =
        "Could not connect to the quality API. Make sure the local backend is running, then try again.";
    } finally {
      isAnalyzing = false;
      analysisStatus.textContent = "";
      runButton.textContent = RUN_BUTTON_LABEL;
      runButton.disabled = !selectedFile;
      fileInput.disabled = false;
      backButton.disabled = false;
      screeningCloseButton.disabled = false;
      if (!resultsModal.classList.contains("is-open") && selectedFile) {
        runButton.focus();
      }
    }
  });

  chooseAnotherButton.addEventListener("click", () => {
    resetUpload();
    resultsModal.classList.remove("is-open");
    screeningModal.classList.add("is-open");
    activeModal = screeningModal;
    showSourceChooser();
    document.body.style.overflow = "hidden";
    uploadButton.focus();
  });

  screeningModal.addEventListener("click", (event) => {
    if (
      event.target === screeningModal ||
      event.target.closest("[data-close-modal]")
    ) {
      if (isAnalyzing) return;
      resetUpload();
      showSourceChooser();
      activeModal = null;
      document.body.style.overflow = "";
      startScreeningButton.focus();
    }
  });

  resultsModal.addEventListener("click", (event) => {
    if (
      event.target === resultsModal ||
      event.target.closest("[data-close-modal]")
    ) {
      resetUpload();
      clearMetricResults();
      resultsIntro.textContent =
        "Upload and run the quality checks to see the analysis here.";
      activeModal = null;
      document.body.style.overflow = "";
      startScreeningButton.focus();
    }
  });

  screeningModal.addEventListener("keydown", (event) => {
    if (event.key === "Tab") trapTabKey(screeningModal, event);
  });

  resultsModal.addEventListener("keydown", (event) => {
    if (event.key === "Tab") trapTabKey(resultsModal, event);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && activeModal) {
      if (isAnalyzing) return;
      resetUpload();
      if (activeModal === screeningModal) {
        showSourceChooser();
      } else {
        clearMetricResults();
        resultsIntro.textContent =
          "Upload and run the quality checks to see the analysis here.";
      }
      activeModal = null;
      document.body.style.overflow = "";
      startScreeningButton.focus();
    }
  });

  function resetUpload() {
    selectedFile = null;
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
      previewUrl = null;
    }
    imagePreview.removeAttribute("src");
    imagePreview.alt = "Selected document preview";
    fileDetails.textContent = "";
    imageDimensions.textContent = "";
    previewPanel.hidden = true;
    fileError.textContent = "";
    analysisStatus.textContent = "";
    fileInput.value = "";
    runButton.textContent = RUN_BUTTON_LABEL;
    runButton.disabled = true;
  }

  function isAnalysisResponse(payload) {
    if (
      !isRecord(payload) ||
      !["photo", "scan"].includes(payload.mode) ||
      !isRecord(payload.image) ||
      !Number.isInteger(payload.image.width) ||
      payload.image.width <= 0 ||
      !Number.isInteger(payload.image.height) ||
      payload.image.height <= 0 ||
      typeof payload.overall_pass !== "boolean" ||
      !Array.isArray(payload.modules) ||
      payload.modules.length !== EXPECTED_MODULES.size
    ) {
      return false;
    }

    if (
      payload.trim_box !== null &&
      (!Array.isArray(payload.trim_box) ||
        payload.trim_box.length !== 4 ||
        !payload.trim_box.every(Number.isInteger))
    ) {
      return false;
    }

    const receivedModules = new Set();
    for (const result of payload.modules) {
      if (!isRecord(result)) return false;
      const moduleKey = getModuleKey(result);
      if (
        !moduleKey ||
        receivedModules.has(moduleKey) ||
        typeof result.label !== "string" ||
        (result.score !== null &&
          (typeof result.score !== "number" || !Number.isFinite(result.score))) ||
        typeof result.unit !== "string" ||
        (result.passed !== null && typeof result.passed !== "boolean") ||
        typeof result.rule !== "string" ||
        !Array.isArray(result.reasons) ||
        !result.reasons.every((reason) => typeof reason === "string") ||
        !isRecord(result.details) ||
        !["photo", "scan"].includes(result.mode)
      ) {
        return false;
      }
      receivedModules.add(moduleKey);
    }

    return receivedModules.size === EXPECTED_MODULES.size;
  }

  function isRecord(value) {
    return value !== null && typeof value === "object" && !Array.isArray(value);
  }

  function getModuleKey(result) {
    if (EXPECTED_MODULES.has(result.module)) return result.module;
    return MODULE_KEYS_BY_LABEL.get(result.label) ?? null;
  }

  function formatDetailLabel(key) {
    const label = key
      .replace(/[_-]+/g, " ")
      .replace(/\s+/g, " ")
      .trim();
    return label ? label[0].toUpperCase() + label.slice(1) : "Detail";
  }

  function formatDetailValue(value) {
    if (value === null || value === undefined) return "Not available";
    if (typeof value === "boolean") return value ? "Yes" : "No";
    if (Array.isArray(value)) {
      return value.length
        ? value.map(formatDetailValue).join(", ")
        : "None reported";
    }
    if (isRecord(value)) {
      const entries = Object.entries(value);
      return entries.length
        ? entries
            .map(
              ([key, nestedValue]) =>
                `${formatDetailLabel(key)}: ${formatDetailValue(nestedValue)}`,
            )
            .join("; ")
        : "None reported";
    }
    return String(value);
  }

  function renderMetricDetails(detailsElement, detailValues) {
    const rows = Object.entries(detailValues).map(([key, value]) => {
      const row = document.createElement("div");
      const label = document.createElement("dt");
      const description = document.createElement("dd");

      label.textContent = formatDetailLabel(key);
      description.textContent = formatDetailValue(value);
      row.appendChild(label);
      row.appendChild(description);
      return row;
    });

    detailsElement.replaceChildren(...rows);
  }

  function renderAnalysis(result, fileName) {
    resultsIntro.textContent =
      `${fileName} · ${result.image.width} × ${result.image.height} px · ${result.mode} mode` +
      (result.trim_box
        ? ` · trimmed to ${result.trim_box.join(", ")}`
        : "");
    overallResult.textContent = result.overall_pass
      ? "Overall result: Pass"
      : "Overall result: Needs attention";
    overallResult.classList.remove("is-pass", "is-fail");
    overallResult.classList.add(result.overall_pass ? "is-pass" : "is-fail");

    for (const moduleResult of result.modules) {
      const card = metricCards.find(
        (metricCard) =>
          metricCard.dataset.module === getModuleKey(moduleResult),
      );
      if (!card) continue;

      const score = card.querySelector("[data-metric-score]");
      const unit = card.querySelector("[data-metric-unit]");
      const status = card.querySelector("[data-metric-status]");
      const rule = card.querySelector("[data-metric-rule]");
      const reasons = card.querySelector("[data-metric-reasons]");
      const details = card.querySelector("[data-metric-details]");
      const statusText =
        moduleResult.passed === null
          ? "N/A"
          : moduleResult.passed
            ? "Pass"
            : "Fail";

      score.textContent =
        moduleResult.score === null ? "—" : String(moduleResult.score);
      unit.textContent = moduleResult.unit;
      status.textContent = statusText;
      rule.textContent = moduleResult.rule || "No rule supplied.";
      reasons.textContent = moduleResult.reasons.length
        ? moduleResult.reasons.join(", ")
        : "None reported.";
      renderMetricDetails(details, moduleResult.details);

      status.classList.remove("is-pass", "is-fail", "is-na");
      status.classList.add(
        moduleResult.passed === null
          ? "is-na"
          : moduleResult.passed
            ? "is-pass"
            : "is-fail",
      );
    }
  }

  function clearMetricResults() {
    overallResult.textContent = "No analysis completed yet.";
    overallResult.classList.remove("is-pass", "is-fail");

    for (const card of metricCards) {
      card.querySelector("[data-metric-score]").textContent = "—";
      card.querySelector("[data-metric-unit]").textContent = "";
      card.querySelector("[data-metric-status]").textContent = "Not run";
      card.querySelector("[data-metric-rule]").textContent = "";
      card.querySelector("[data-metric-reasons]").textContent = "";
      card.querySelector("[data-metric-details]").textContent = "";
      card
        .querySelector("[data-metric-status]")
        .classList.remove("is-pass", "is-fail", "is-na");
    }
  }

  function showSourceChooser() {
    sourceChooser.hidden = false;
    uploadStep.hidden = true;
    sourceMessage.textContent = "";
  }

  function trapTabKey(modal, event) {
    const focusable = Array.from(
      modal.querySelectorAll(
        'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])',
      ),
    ).filter(
      (element) =>
        !element.closest("[hidden]") &&
        element.getAttribute("aria-hidden") !== "true",
    );

    if (focusable.length === 0) {
      event.preventDefault();
      modal.focus();
      return;
    }

    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  function formatFileSize(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }
})();
