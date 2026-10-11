(() => {
  "use strict";

  // The submission path owns one exchange and nothing else: it posts the file
  // an officer chose to the one endpoint that screens it, keeps the id that
  // came back, and carries that id into the result page's URL. It reads no
  // image and composes no sentence about the network -- api.js authors those.

  const ENDPOINT = "/api/screenings";
  const RESULT_PAGE = "result.html";
  const ID_PARAM = "id";
  // The service refuses a mode outside this set, so the page cannot send one
  // it has not heard of; a document type has no vocabulary but is never blank.
  const MODES = ["auto", "photo", "scan"];
  const DEFAULT_MODE = "auto";
  const DEFAULT_DOCUMENT_TYPE = "unspecified";
  const REQUIRED_ELEMENTS = ["button", "error"];

  const NO_FILE_MESSAGE =
    "There is no image to submit. Choose an image and submit again.";
  const NO_ID_MESSAGE =
    "The service accepted the image but answered with no screening id, so " +
    "there is no result to open.";
  const FAILED_MESSAGE =
    "The screening could not be submitted. Try again, and tell an " +
    "administrator if it keeps failing.";

  class SubmitError extends Error {
    constructor(code, message) {
      super(message);
      this.name = "SubmitError";
      this.code = code;
    }
  }

  function readElement(settings, name) {
    const element = settings ? settings[name] : null;
    if (!element) {
      throw new SubmitError(
        "missing_element",
        "The submission path needs an element named " + name + ".",
      );
    }
    return element;
  }

  function readCallback(settings, name) {
    const callback = settings ? settings[name] : null;
    if (typeof callback !== "function") {
      throw new SubmitError(
        "missing_callback",
        "The submission path needs a callback named " + name + ".",
      );
    }
    return callback;
  }

  // Refuse rather than coerce: a mode the service does not accept, and a
  // document type that is not a claim at all.
  function readMode(mode) {
    const value = mode === undefined ? DEFAULT_MODE : mode;
    if (typeof value !== "string" || MODES.indexOf(value) === -1) {
      throw new SubmitError(
        "unsupported_mode",
        "Choose a screening mode: " + MODES.join(", ") + ".",
      );
    }
    return value;
  }

  function readDocumentType(documentType) {
    const value =
      documentType === undefined ? DEFAULT_DOCUMENT_TYPE : documentType;
    if (typeof value !== "string" || value.trim() === "") {
      throw new SubmitError(
        "invalid_document_type",
        "Choose the type of document being screened.",
      );
    }
    return value;
  }

  function readFile(file) {
    if (file === null || file === undefined || typeof file !== "object") {
      throw new SubmitError("no_file", NO_FILE_MESSAGE);
    }
    return file;
  }

  // The id travels in the result page's query string, so the page reads one
  // parameter rather than a second store the two could disagree about.
  function readId(id) {
    if (typeof id !== "string" || id.trim() === "") {
      throw new SubmitError("no_screening_id", NO_ID_MESSAGE);
    }
    return id.trim();
  }

  function readScreeningId(payload) {
    const id =
      payload !== null && typeof payload === "object"
        ? payload.screening_id
        : null;
    return readId(id);
  }

  function resultUrlFor(screeningId) {
    return (
      RESULT_PAGE + "?" + ID_PARAM + "=" + encodeURIComponent(readId(screeningId))
    );
  }

  async function readJson(response) {
    try {
      return await response.json();
    } catch {
      // An unreadable body and a body carrying no id are the same answer to
      // the same question: the row the officer must open was not named.
      return null;
    }
  }

  // One multipart body, in the shape the endpoint reads: the image under
  // "image", the source it came from under "mode", the officer's claim under
  // "document_type".
  function readSubmission(described) {
    const fields =
      described !== null && typeof described === "object" ? described : {};
    const file = readFile(fields.file);
    const mode = readMode(fields.mode);
    const documentType = readDocumentType(fields.documentType);
    const body = new FormData();
    body.append("image", file);
    body.append("mode", mode);
    body.append("document_type", documentType);
    return { file, mode, documentType, body };
  }

  // bindSubmit wires one submit button to the one endpoint. describe() is
  // asked at click time for the file, the mode and the document type, so a
  // retake (22.7) and a changed radio are answered by this same path.
  function bindSubmit(options) {
    const settings = options || {};
    const button = readElement(settings, "button");
    const error = readElement(settings, "error");
    const navigate = readCallback(settings, "navigate");
    const describe = readCallback(settings, "describe");
    const onPending =
      typeof settings.onPending === "function" ? settings.onPending : () => {};
    const api = window.DRISHTI_API;
    if (!api || typeof api.request !== "function") {
      throw new SubmitError(
        "no_api",
        "This page cannot reach the quality service.",
      );
    }

    let screeningId = null;
    let pending = false;

    function refuse(refusal) {
      error.textContent = refusal.message;
      return null;
    }

    function isApiRefusal(failure) {
      return (
        typeof api.ApiError === "function" && failure instanceof api.ApiError
      );
    }

    // A refusal keeps the words it arrived with: this module's own, or
    // api.js's for anything the network raised.
    function readRefusal(failure) {
      if (failure instanceof SubmitError) return failure;
      if (isApiRefusal(failure)) return failure;
      return new SubmitError("submission_failed", FAILED_MESSAGE);
    }

    async function submit(described) {
      // A new submission drops the last id, so an officer who submits twice
      // cannot read the first run's result from the second.
      screeningId = null;
      if (pending) {
        return null;
      }

      let fields;
      try {
        fields = readSubmission(described);
      } catch (refusal) {
        return refuse(refusal);
      }

      pending = true;
      button.disabled = true;
      error.textContent = "";
      onPending(true);
      try {
        const response = await api.request(ENDPOINT, {
          method: "POST",
          body: fields.body,
        });
        const id = readScreeningId(await readJson(response));
        screeningId = id;
        navigate(resultUrlFor(id));
        return id;
      } catch (failure) {
        return refuse(readRefusal(failure));
      } finally {
        pending = false;
        button.disabled = false;
        onPending(false);
      }
    }

    button.addEventListener("click", () => submit(describe()));

    return {
      submit,
      screeningId: () => screeningId,
      resultUrl: () => (screeningId === null ? null : resultUrlFor(screeningId)),
      pending: () => pending,
    };
  }

  window.DRISHTI_SUBMIT = {
    DEFAULT_DOCUMENT_TYPE,
    DEFAULT_MODE,
    ENDPOINT,
    MODES,
    REQUIRED_ELEMENTS,
    RESULT_PAGE,
    SubmitError,
    bindSubmit,
    resultUrlFor,
  };
})();