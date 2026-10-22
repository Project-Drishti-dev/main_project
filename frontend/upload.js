(() => {
  "use strict";

  // The upload path owns three decisions and no others: which types a document
  // image may be, how large it may be, and what the officer is shown before
  // anything is submitted. Submission is 22.6's, and this module reads no
  // network and holds no fetch.

  const KIBIBYTE = 1024;
  const MEBIBYTE = 1024 * KIBIBYTE;

  // The rules are the ones home.js and pages.js already ship, in one home:
  // 10 MiB, and exactly the three types. ACCEPT is those three types as the
  // one spelling the markup's accept attribute carries, so the attribute a
  // browser filters by and the set this module refuses cannot disagree.
  const MAX_BYTES = 10 * MEBIBYTE;
  const ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp"];
  const ACCEPT = ACCEPTED_TYPES.join(",");
  const TYPE_LIST = "JPEG, PNG, or WebP";

  const REQUIRED_ELEMENTS = ["input", "panel", "preview", "details", "error"];

  const UNREADABLE_MESSAGE =
    "This file could not be opened as an image. Choose a valid " + TYPE_LIST + ".";

  class UploadError extends Error {
    constructor(code, message) {
      super(message);
      this.name = "UploadError";
      this.code = code;
    }
  }

  // Refuse rather than coerce: a file whose type or size cannot be read is
  // not a document image, and guessing would put it past the only gate.
  function validate(file) {
    if (file === null || file === undefined || typeof file !== "object") {
      throw new UploadError("no_file", "Choose an image to screen.");
    }
    if (typeof file.type !== "string" || !ACCEPTED_TYPES.includes(file.type)) {
      throw new UploadError(
        "unsupported_type",
        "Choose a " + TYPE_LIST + " image.",
      );
    }
    if (
      typeof file.size !== "number" ||
      !Number.isFinite(file.size) ||
      file.size < 0
    ) {
      throw new UploadError(
        "unreadable_size",
        "This file's size could not be read. Choose the image again.",
      );
    }
    if (file.size > MAX_BYTES) {
      throw new UploadError(
        "too_large",
        "Choose an image that is 10 MB or smaller.",
      );
    }
    return file;
  }

  function formatSize(bytes) {
    if (bytes < KIBIBYTE) return `${bytes} B`;
    if (bytes < MEBIBYTE) return `${(bytes / KIBIBYTE).toFixed(1)} KB`;
    return `${(bytes / MEBIBYTE).toFixed(1)} MB`;
  }

  function describe(file) {
    const name = typeof file.name === "string" ? file.name : "";
    return `${name} · ${formatSize(file.size)}`;
  }

  function readElement(elements, name) {
    const element = elements ? elements[name] : null;
    if (!element) {
      throw new UploadError(
        "missing_element",
        "The upload path needs an element named " + name + ".",
      );
    }
    return element;
  }

  // bindUpload wires one file input to one preview panel. It sends nothing:
  // the accepted file is handed back to the caller, and a caller that has
  // not submitted it has not submitted anything.
  function bindUpload(options) {
    const settings = options || {};
    const input = readElement(settings, "input");
    const panel = readElement(settings, "panel");
    const preview = readElement(settings, "preview");
    const details = readElement(settings, "details");
    const error = readElement(settings, "error");
    const onSelect =
      typeof settings.onSelect === "function" ? settings.onSelect : () => {};

    let selectedFile = null;
    let previewUrl = null;

    function releasePreview() {
      if (previewUrl !== null) {
        URL.revokeObjectURL(previewUrl);
        previewUrl = null;
      }
      preview.removeAttribute("src");
      preview.alt = "";
    }

    // clear is the one path back to "nothing chosen", so a retake (22.7) and
    // a rejected file both land in the same state rather than two.
    function clear() {
      selectedFile = null;
      releasePreview();
      details.textContent = "";
      error.textContent = "";
      panel.hidden = true;
      // Cleared here, so choosing the same file twice fires a second change.
      input.value = "";
      onSelect(null);
      return null;
    }

    function refuse(refusal) {
      clear();
      error.textContent = refusal.message;
      return null;
    }

    // choose is what the input's change event calls and what 22.4's camera
    // capture will call, so both sources pass the same two gates.
    function choose(file) {
      if (file === null || file === undefined) {
        // A cancelled file picker is not a refusal and says nothing.
        return clear();
      }
      try {
        validate(file);
      } catch (refusal) {
        if (!(refusal instanceof UploadError)) throw refusal;
        return refuse(refusal);
      }

      clear();
      selectedFile = file;
      previewUrl = URL.createObjectURL(file);
      preview.setAttribute("src", previewUrl);
      preview.alt = `Preview of ${file.name}`;
      details.textContent = describe(file);
      panel.hidden = false;
      onSelect(file);
      return file;
    }

    input.addEventListener("change", () => {
      choose(input.files && input.files[0]);
    });

    preview.addEventListener("error", () => {
      if (previewUrl === null) return;
      if (preview.getAttribute("src") !== previewUrl) return;
      refuse(new UploadError("unreadable_image", UNREADABLE_MESSAGE));
    });

    return {
      choose,
      clear,
      selected: () => selectedFile,
    };
  }

  window.DRISHTI_UPLOAD = {
    ACCEPT,
    ACCEPTED_TYPES,
    MAX_BYTES,
    REQUIRED_ELEMENTS,
    UploadError,
    bindUpload,
    describe,
    formatSize,
    validate,
  };
})();
