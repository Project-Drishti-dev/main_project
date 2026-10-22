(() => {
  "use strict";

  // Camera capture owns two decisions and no others: when a stream may be
  // opened, and how a frame becomes the File the upload path validates.
  // Nothing is recorded and nothing is sent from here -- 22.3's choose() is
  // the only door a file comes through, and 22.6's submit is the only sender.

  const MIME_TYPE = "image/jpeg";
  const CAPTURE_QUALITY = 0.92;
  const CAPTURE_NAME = "camera-capture.jpg";

  // The rear camera is an ideal, not a demand: a laptop with one camera
  // answers this rather than refusing, and a cause the table below does not
  // know keeps the generic sentence.
  const CONSTRAINTS = Object.freeze({
    audio: false,
    video: { facingMode: { ideal: "environment" } },
  });

  // The consent copy lives here so the module and the markup cannot drift:
  // binding writes it into the container the page marks up, exactly as 22.3
  // owns the refusal sentences (D167).
  const CONSENT =
    "The camera is used only to take this document's photo. Nothing is " +
    "recorded, and nothing is uploaded until you submit.";

  const NO_MEDIA_MESSAGE = "This browser cannot open a camera.";
  const OPEN_FAILED_MESSAGE = "The camera could not be opened.";
  const NOT_RUNNING_MESSAGE = "Turn the camera on before taking a photo.";
  const NO_FRAME_MESSAGE =
    "The camera has not produced an image yet. Take the photo again.";
  const CAPTURE_FAILED_MESSAGE = "The photo could not be captured. Take it again.";

  // A denied permission and a page served over plain HTTP are told apart by
  // what the browser hands back, and each sentence names what to change about
  // it rather than reporting only that something failed.
  const PERMISSION_DENIED_MESSAGE =
    "Camera access was not granted. Allow the camera for this site, then try again.";
  const INSECURE_CONTEXT_MESSAGE =
    "The camera needs a secure connection. Open this page over HTTPS, or from localhost.";
  const CAMERA_NOT_FOUND_MESSAGE = "No camera was found on this device.";
  const CAMERA_BUSY_MESSAGE =
    "The camera is in use by another application. Close it and try again.";
  const CONSTRAINTS_UNSUPPORTED_MESSAGE =
    "This camera cannot give the view this page asked for.";

  // getUserMedia refuses with a DOMException whose name is the only thing that
  // separates one failure from another, so the code is read off that name
  // rather than guessed at in the sentence. A name absent here keeps the
  // generic wording instead of borrowing another cause's.
  const CAUSE_CODES = Object.freeze({
    NotAllowedError: "permission_denied",
    PermissionDeniedError: "permission_denied",
    NotFoundError: "camera_not_found",
    DevicesNotFoundError: "camera_not_found",
    NotReadableError: "camera_busy",
    TrackStartError: "camera_busy",
    OverconstrainedError: "constraints_unsupported",
  });

  const MESSAGE_FOR_CODE = Object.freeze({
    permission_denied: PERMISSION_DENIED_MESSAGE,
    insecure_context: INSECURE_CONTEXT_MESSAGE,
    camera_not_found: CAMERA_NOT_FOUND_MESSAGE,
    camera_busy: CAMERA_BUSY_MESSAGE,
    constraints_unsupported: CONSTRAINTS_UNSUPPORTED_MESSAGE,
    start_failed: OPEN_FAILED_MESSAGE,
  });

  const REQUIRED_ELEMENTS = [
    "video",
    "canvas",
    "start",
    "capture",
    "stop",
    "consent",
  ];
  const REQUIRED_CALLBACKS = ["onCapture", "onRefuse"];

  class CameraError extends Error {
    constructor(code, message, cause) {
      super(message);
      this.name = "CameraError";
      this.code = code;
      // The browser's own refusal is kept beside the sentence rather than
      // paraphrased into it, so a caller can still read what the browser said.
      this.cause = cause === undefined ? null : cause;
    }
  }

  function readElement(options, name) {
    const element = options ? options[name] : null;
    if (!element) {
      throw new CameraError(
        "missing_element",
        "The camera needs an element named " + name + ".",
      );
    }
    return element;
  }

  function readCallback(options, name) {
    const callback = options ? options[name] : null;
    if (typeof callback !== "function") {
      throw new CameraError(
        "missing_callback",
        "The camera needs a callback named " + name + ".",
      );
    }
    return callback;
  }

  // null means the browser answered neither way: absent is not the same
  // answer as false, and only false places the blame on the connection.
  function secureContext() {
    return typeof isSecureContext === "undefined" ? null : isSecureContext;
  }

  // getUserMedia is exposed in secure contexts only, so a page served over
  // plain HTTP carries no navigator.mediaDevices at all -- the one case in
  // which a missing API has an accurate sentence of its own.
  function mediaDevices() {
    const devices =
      typeof navigator === "undefined" ? null : navigator.mediaDevices;
    if (!devices || typeof devices.getUserMedia !== "function") {
      if (secureContext() === false) {
        throw new CameraError("insecure_context", INSECURE_CONTEXT_MESSAGE);
      }
      throw new CameraError("no_media_api", NO_MEDIA_MESSAGE);
    }
    return devices;
  }

  // The refusal names its own cause, or falls back to the generic one.
  function codeForCause(cause) {
    const name = cause && typeof cause.name === "string" ? cause.name : null;
    const known =
      name !== null && Object.prototype.hasOwnProperty.call(CAUSE_CODES, name);
    return known ? CAUSE_CODES[name] : "start_failed";
  }

  function isPositive(value) {
    return typeof value === "number" && Number.isFinite(value) && value > 0;
  }

  // bindCamera wires one video surface to its three controls. Nothing is
  // opened here: the stream is the officer's click away, and a page that
  // loads this module has asked for no permission yet.
  function bindCamera(options) {
    const video = readElement(options, "video");
    const canvas = readElement(options, "canvas");
    const startControl = readElement(options, "start");
    const captureControl = readElement(options, "capture");
    const stopControl = readElement(options, "stop");
    const consent = readElement(options, "consent");
    const onCapture = readCallback(options, "onCapture");
    const onRefuse = readCallback(options, "onRefuse");

    let stream = null;

    consent.textContent = CONSENT;

    // Every refusal leaves here, so the module writes no sentence of its own
    // into a second element and the page has one message to show.
    function refuse(refusal) {
      onRefuse(refusal);
      return null;
    }

    // release is the one path back to a closed camera, so the tracks are
    // stopped and the surface detached in one place rather than two.
    function release() {
      if (stream === null) return null;
      for (const track of stream.getTracks()) {
        track.stop();
      }
      video.srcObject = null;
      stream = null;
      return null;
    }

    async function start() {
      // A second click while the camera is on is the same stream, not a
      // second permission prompt.
      if (stream !== null) return stream;

      let devices = null;
      try {
        devices = mediaDevices();
      } catch (refusal) {
        return refuse(refusal);
      }

      let opened = null;
      try {
        opened = await devices.getUserMedia(CONSTRAINTS);
      } catch (cause) {
        const code = codeForCause(cause);
        return refuse(new CameraError(code, MESSAGE_FOR_CODE[code], cause));
      }

      stream = opened;
      video.setAttribute("playsinline", "");
      video.srcObject = opened;
      // A play() the browser refuses is not a capture failure: the stream is
      // already open and the shutter works without autoplay. Swallowed here
      // so it cannot surface as an unhandled rejection.
      const playing = video.play();
      if (playing && typeof playing.catch === "function") {
        playing.catch(() => {});
      }
      return stream;
    }

    function capture() {
      if (stream === null) {
        return Promise.resolve(
          refuse(new CameraError("not_running", NOT_RUNNING_MESSAGE)),
        );
      }
      const width = video.videoWidth;
      const height = video.videoHeight;
      if (!isPositive(width) || !isPositive(height)) {
        return Promise.resolve(
          refuse(new CameraError("no_frame", NO_FRAME_MESSAGE)),
        );
      }

      canvas.width = width;
      canvas.height = height;
      const context =
        typeof canvas.getContext === "function" ? canvas.getContext("2d") : null;
      if (!context) {
        return Promise.resolve(
          refuse(new CameraError("no_frame", NO_FRAME_MESSAGE)),
        );
      }
      context.drawImage(video, 0, 0, width, height);

      return new Promise((resolve) => {
        canvas.toBlob(
          (blob) => {
            if (!blob) {
              resolve(
                refuse(new CameraError("capture_failed", CAPTURE_FAILED_MESSAGE)),
              );
              return;
            }
            const file = new File([blob], CAPTURE_NAME, { type: MIME_TYPE });
            onCapture(file);
            resolve(file);
          },
          MIME_TYPE,
          CAPTURE_QUALITY,
        );
      });
    }

    startControl.addEventListener("click", start);
    captureControl.addEventListener("click", capture);
    stopControl.addEventListener("click", release);

    return {
      start,
      stop: release,
      capture,
      active: () => stream !== null,
    };
  }

  window.DRISHTI_CAMERA = {
    ACCEPT: MIME_TYPE,
    CAPTURE_NAME,
    CONSENT,
    CONSTRAINTS,
    CameraError,
    REQUIRED_CALLBACKS,
    REQUIRED_ELEMENTS,
    bindCamera,
  };
})();
