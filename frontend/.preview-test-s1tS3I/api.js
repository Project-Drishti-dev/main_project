(() => {
  "use strict";

  const DEFAULT_TIMEOUT_MS = 15000;
  const NO_STATUS = 0;
  const NETWORK_ERROR_CODE = "network_error";
  // A CORS refusal and a service that is down arrive as one TypeError, so the
  // composed sentence names both causes and both checks. The old text named
  // one cause and pointed an operator at a backend that was already running.
  const NETWORK_ERROR_MESSAGE =
    "The quality service could not be reached. The browser cannot tell a " +
    "service that is down from one whose answer this site is not allowed to " +
    "read (CORS): check that the service is running, then check that it " +
    "allows this site's origin.";

  class ApiError extends Error {
    constructor({ code, message, status }) {
      super(message);
      this.name = "ApiError";
      this.code = code;
      this.status = status;
    }
  }

  class ApiTimeoutError extends ApiError {
    constructor(timeoutMs) {
      super({
        code: "timeout",
        message: "The request timed out after " + timeoutMs + " ms.",
        status: NO_STATUS,
      });
      this.name = "ApiTimeoutError";
      this.timeoutMs = timeoutMs;
    }
  }

  function readApiBaseUrl() {
    const configured = window.DRISHTI_CONFIG?.apiBaseUrl;
    return typeof configured === "string"
      ? configured.trim().replace(/\/+$/, "")
      : "";
  }

  function codeForStatus(status) {
    if (status >= 500) {
      return "server_error";
    }
    if (status >= 400) {
      return "client_error";
    }
    return "unknown_error";
  }

  function readEnvelope(text) {
    let parsed;
    try {
      parsed = JSON.parse(text);
    } catch {
      return null;
    }
    const detail = parsed?.error;
    if (detail === null || typeof detail !== "object") {
      return null;
    }
    const { code, message } = detail;
    if (
      typeof code !== "string" ||
      code === "" ||
      typeof message !== "string" ||
      message === ""
    ) {
      return null;
    }
    return { code, message };
  }

  async function readApiError(response) {
    let body = "";
    try {
      body = await response.text();
    } catch {
      // An unreadable body and an empty body are the same refusal: the status
      // the response arrived with names it either way.
    }
    const envelope = readEnvelope(body);
    return new ApiError(
      envelope
        ? {
            code: envelope.code,
            message: envelope.message,
            status: response.status,
          }
        : {
            code: codeForStatus(response.status),
            message:
              "The server answered " + response.status + " with no error envelope.",
            status: response.status,
          },
    );
  }

  async function request(path, options = {}) {
    const {
      method = "GET",
      body,
      headers,
      timeoutMs = DEFAULT_TIMEOUT_MS,
    } = options;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(readApiBaseUrl() + path, {
        method,
        body,
        headers,
        signal: controller.signal,
      });
      if (response.ok) {
        return response;
      }
      throw await readApiError(response);
    } catch (error) {
      if (controller.signal.aborted) {
        throw new ApiTimeoutError(timeoutMs);
      }
      if (error instanceof ApiError) {
        throw error;
      }
      throw new ApiError({
        code: NETWORK_ERROR_CODE,
        message: NETWORK_ERROR_MESSAGE,
        status: NO_STATUS,
      });
    } finally {
      clearTimeout(timer);
    }
  }

  window.DRISHTI_API = {
    request,
    readApiBaseUrl,
    ApiError,
    ApiTimeoutError,
    DEFAULT_TIMEOUT_MS,
  };
})();
