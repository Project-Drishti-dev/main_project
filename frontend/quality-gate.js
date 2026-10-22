(() => {
  "use strict";

  // The quality gate owns what an officer is told before anything is
  // analysed, and the two answers they are given. It measures the one thing
  // a browser can measure about an image before sending it, holds no fetch,
  // and starts no analysis: 22.6's submit is the only sender, and the
  // service runs its own nine checks on the image either way.

  // A browser cannot measure PPI without a physical size, so the frame's
  // short edge stands in for the card's long side. 500 px is the service's
  // own floor written in pixels -- m6_ppi refuses below 150 PPI on an
  // 85.6 mm card, which is 505 px -- rounded down. It is a floor, not the
  // gate, so a capture above it still faces the service's own check.
  const MIN_EDGE_PX = 500;
  const CHECK_NAME = "resolution";

  const PASS_TITLE = "Resolution check passed";
  const WARN_TITLE = "Resolution check failed";
  // The consequence belongs in the warning rather than in a footnote beside
  // the button: the officer is one click from analysing a capture that may
  // not read, and that click is the "Analyse anyway" this task asks for.
  const CONSEQUENCE =
    "If you analyse it anyway, the screening runs on this capture and the " +
    "result may be wrong, because text this small may not be read.";

  const UNREADABLE_READING_MESSAGE =
    "This image's size in pixels could not be read.";
  const NOT_WARNED_MESSAGE =
    "No quality warning is standing, so there is nothing to analyse anyway.";
  const ALREADY_ACCEPTED_MESSAGE =
    "This capture was already accepted for analysis.";

  // The variant class is this gate's own state on an alert the page marked up,
  // so the module swaps exactly the two variants it owns and leaves the rest.
  const PASS_VARIANT = "ux4g-alert-success";
  const WARN_VARIANT = "ux4g-alert-warning";
  const VARIANT_CLASS = { pass: PASS_VARIANT, warn: WARN_VARIANT };
  const OWNED_VARIANTS = [PASS_VARIANT, WARN_VARIANT];

  const REQUIRED_ELEMENTS = ["alert", "title", "message", "retake", "anyway"];
  const REQUIRED_CALLBACKS = ["onRetake", "onProceed"];

  // UX4G ships the alert as classes only (preflight G2), so the one fact that
  // arrives without being asked for -- a verdict the officer did not go and
  // read -- is announced by a live region on the alert itself. Polite rather
  // than assertive: a low-resolution capture is worth saying, but it is not
  // an emergency, and it is not interrupting a sentence being read elsewhere.
  const LIVE_ROLE = "status";
  const LIVE_POLITENESS = "polite";

  class QualityGateError extends Error {
    constructor(code, message) {
      super(message);
      this.name = "QualityGateError";
      this.code = code;
    }
  }

  function readElement(settings, name) {
    const element = settings ? settings[name] : null;
    if (!element) {
      throw new QualityGateError(
        "missing_element",
        "The quality gate needs an element named " + name + ".",
      );
    }
    return element;
  }

  function readCallback(settings, name) {
    const callback = settings ? settings[name] : null;
    if (typeof callback !== "function") {
      throw new QualityGateError(
        "missing_callback",
        "The quality gate needs a callback named " + name + ".",
      );
    }
    return callback;
  }

  function isPixelCount(value) {
    return typeof value === "number" && Number.isFinite(value) && value > 0;
  }

  // Refuse rather than coerce: a capture whose pixel size the browser did not
  // report is not a capture that passed, and a pass is never assumed here.
  function readReading(reading) {
    const fields =
      reading !== null && typeof reading === "object" ? reading : {};
    if (!isPixelCount(fields.width) || !isPixelCount(fields.height)) {
      throw new QualityGateError(
        "unreadable_reading",
        UNREADABLE_READING_MESSAGE,
      );
    }
    return { width: fields.width, height: fields.height };
  }

  // check is the verdict alone, with no page and no alert: what the officer
  // is told about one capture, as a reading answered.
  function check(reading) {
    const measured = readReading(reading);
    const size = measured.width + " × " + measured.height + " pixels";
    if (Math.min(measured.width, measured.height) >= MIN_EDGE_PX) {
      return {
        check: CHECK_NAME,
        code: "resolution_ok",
        status: "pass",
        title: PASS_TITLE,
        message:
          "This capture is " + size + ", at or above the " + MIN_EDGE_PX +
          "-pixel floor.",
      };
    }
    return {
      check: CHECK_NAME,
      code: "low_resolution",
      status: "warn",
      title: WARN_TITLE,
      message:
        "This capture is " + size + ", below the " + MIN_EDGE_PX +
        "-pixel floor a document image needs. " + CONSEQUENCE,
    };
  }

  // bindQualityGate wires one alert to the two answers a warning offers. The
  // retake lands in 22.3's clear() and the analyse-anyway path in 22.6's
  // submit, both supplied by the page: this module dials neither.
  function bindQualityGate(options) {
    const settings = options || {};
    const alert = readElement(settings, "alert");
    const title = readElement(settings, "title");
    const message = readElement(settings, "message");
    const retakeControl = readElement(settings, "retake");
    const anywayControl = readElement(settings, "anyway");
    const onRetake = readCallback(settings, "onRetake");
    const onProceed = readCallback(settings, "onProceed");

    // Written once at binding, so the region is already listening before the
    // first verdict lands: a live region added at the same moment as its
    // first text is one a screen reader may never announce.
    alert.setAttribute("role", LIVE_ROLE);
    alert.setAttribute("aria-live", LIVE_POLITENESS);

    let standing = null;
    let accepted = false;

    function setVariant(status) {
      for (const variant of OWNED_VARIANTS) {
        alert.classList.remove(variant);
      }
      if (status === null) return;
      alert.classList.add(VARIANT_CLASS[status]);
    }

    // hide is the one path back to no verdict at all, so a retake, a cleared
    // file and a reading nobody could measure leave the same state.
    function hide() {
      standing = null;
      accepted = false;
      setVariant(null);
      alert.hidden = true;
      title.textContent = "";
      message.textContent = "";
      retakeControl.hidden = true;
      anywayControl.hidden = true;
      return null;
    }

    // Both actions belong to a warning: a capture that passed has nothing to
    // override, and changing it is the upload panel's own control.
    function showActions(warned) {
      retakeControl.hidden = !warned;
      anywayControl.hidden = !warned;
    }

    // show answers a reading. Nothing chosen is not a refusal and says
    // nothing, the same answer a cancelled file picker gets in 22.3, and a
    // reading the browser could not measure leaves no verdict rather than a
    // pass the gate never made.
    function show(reading) {
      if (reading === null || reading === undefined) {
        return hide();
      }

      let verdict = null;
      try {
        verdict = check(reading);
      } catch (refusal) {
        if (!(refusal instanceof QualityGateError)) throw refusal;
        return hide();
      }

      standing = verdict;
      accepted = false;
      alert.hidden = false;
      setVariant(verdict.status);
      title.textContent = verdict.title;
      message.textContent = verdict.message;
      showActions(verdict.status === "warn");
      return verdict;
    }

    // retake is the one path back to nothing chosen, so a retake and a
    // rejected file leave the page in the same state rather than two.
    function retake() {
      hide();
      onRetake();
      return null;
    }

    // anyway is the only route past a standing warning, and it is the button's
    // own click: nothing else here releases a blocked analysis.
    function anyway() {
      if (standing === null || standing.status !== "warn") {
        throw new QualityGateError("not_warned", NOT_WARNED_MESSAGE);
      }
      if (accepted) {
        throw new QualityGateError(
          "already_accepted",
          ALREADY_ACCEPTED_MESSAGE,
        );
      }
      accepted = true;
      showActions(false);
      onProceed();
      return standing;
    }

    retakeControl.addEventListener("click", retake);
    anywayControl.addEventListener("click", anyway);

    return {
      show,
      retake,
      anyway,
      verdict: () => standing,
      blocking: () =>
        standing !== null && standing.status === "warn" && !accepted,
      accepted: () => accepted,
    };
  }

  window.DRISHTI_QUALITY_GATE = {
    CONSEQUENCE,
    LIVE_POLITENESS,
    LIVE_ROLE,
    MIN_EDGE_PX,
    REQUIRED_CALLBACKS,
    REQUIRED_ELEMENTS,
    QualityGateError,
    bindQualityGate,
    check,
  };
})();