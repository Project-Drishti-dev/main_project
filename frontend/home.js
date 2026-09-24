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
  const sidebarStatus = document.getElementById("sidebar-status");
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
  const resultsModal = document.getElementById("results-modal");
  const resultsIntro = document.getElementById("results-intro");
  const resultsCloseButton = document.getElementById("results-modal-close");
  const sourceMessage = document.getElementById("screening-source-message");
  const chooseAnotherButton = document.getElementById("choose-another-image");
  const startScreeningButton = document.getElementById("start-screening");

  let selectedFile = null;
  let previewUrl = null;
  let activeModal = null;

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

  document.querySelectorAll("[data-sidebar-placeholder]").forEach((option) => {
    option.addEventListener("click", () => {
      const label = option.getAttribute("data-sidebar-placeholder");
      sidebarStatus.textContent = `${label} is a placeholder in this prototype.`;
    });
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

  runButton.addEventListener("click", () => {
    if (!selectedFile) return;

    resultsIntro.textContent =
      `${selectedFile.name} · Demo preview only — the Python quality checker is not connected, so this image was not analyzed.`;
    screeningModal.classList.remove("is-open");
    resultsModal.classList.add("is-open");
    document.body.style.overflow = "hidden";
    activeModal = resultsModal;
    resultsCloseButton.focus();
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
      resetUpload();
      showSourceChooser();
      activeModal = null;
      startScreeningButton.focus();
    }
  });

  resultsModal.addEventListener("click", (event) => {
    if (
      event.target === resultsModal ||
      event.target.closest("[data-close-modal]")
    ) {
      resetUpload();
      resultsIntro.textContent =
        "Demo preview — the selected image has not been analyzed.";
      activeModal = null;
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
      resetUpload();
      if (activeModal === screeningModal) {
        showSourceChooser();
      } else {
        resultsIntro.textContent =
          "Demo preview — the selected image has not been analyzed.";
      }
      activeModal = null;
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
    fileInput.value = "";
    runButton.disabled = true;
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
