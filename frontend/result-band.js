(() => {
  "use strict";

  // Where a screened document's band and its score sit on the result page:
  // one line, one tag, the number beside it.

  const TAG_CLASS = "ux4g-tag";
  const TAG_SIZE_CLASS = "ux4g-tag-s";
  const SR_ONLY_CLASS = "ux4g-sr-only";
  const ROW_CLASSES = ["ux4g-d-flex", "ux4g-gap-s"];

  // The sheet has no class for the row a badge and its score sit in, nor for
  // the score itself, so both carry one class of this project's own.
  const ROW_CLASS = "result-band";
  const SCORE_CLASS = "result-band-score";

  // One variant per band app/risk/bands.py bands in, in the order of rising
  // risk. The three names are the ones format.js labels, and a case holds the
  // two tables against each other so neither can fall behind.
  const BAND_VARIANTS = {
    low: "ux4g-tag-filled-success",
    review: "ux4g-tag-filled-warning",
    high: "ux4g-tag-filled-error",
  };

  // A bare number beside a badge is not a score, so the word is in the markup
  // for a screen reader and out of the way on screen.
  const SCORE_LABEL = "Score: ";

  const REQUIRED_ELEMENTS = ["container"];

  const CONTAINER_MESSAGE = "The band tag needs an element to draw into: ";
  const BAND_MESSAGE =
    "A band is one of the three the engine bands in: " +
    Object.keys(BAND_VARIANTS).join(", ") +
    ".";
  const SCORE_MESSAGE = "The score must be a number between 0 and 100.";
  const NO_FORMAT_MESSAGE = "This page cannot reach the formatter.";

  class ResultBandError extends Error {
    constructor(code, message, cause) {
      super(message);
      this.name = "ResultBandError";
      this.code = code;
      if (cause !== undefined) {
        this.cause = cause;
      }
    }
  }

  function readElement(settings, name) {
    const element = settings ? settings[name] : null;
    if (!element) {
      throw new ResultBandError(
        "missing_element",
        CONTAINER_MESSAGE + name + ".",
      );
    }
    return element;
  }

  // hasOwnProperty rather than a lookup: a band named "toString" is a band the
  // engine never bands in, and an inherited property would answer for it.
  function bandVariant(band) {
    if (
      typeof band !== "string" ||
      Object.prototype.hasOwnProperty.call(BAND_VARIANTS, band) === false
    ) {
      throw new ResultBandError("bad_band", BAND_MESSAGE);
    }
    return BAND_VARIANTS[band];
  }

  // bindResultBand wires one line of the result page, and draws nothing until a
  // page calls render().
  function bindResultBand(options) {
    const settings = options || {};
    const container = readElement(settings, "container");
    const format = window.DRISHTI_FORMAT;
    if (
      !format ||
      typeof format.bandLabel !== "function" ||
      typeof format.formatScore !== "function"
    ) {
      throw new ResultBandError("no_format", NO_FORMAT_MESSAGE);
    }

    let line = null;
    let current = null;

    // Both halves are read before anything is written, so a result this page
    // cannot read leaves the line already standing rather than half replaced
    // by a tag with no score beside it.
    function measure(result) {
      const band = result ? result.band : null;
      const variant = bandVariant(band);
      let label;
      try {
        label = format.bandLabel(band);
      } catch (error) {
        throw new ResultBandError("bad_band", BAND_MESSAGE, error);
      }
      let score;
      try {
        score = format.formatScore(result ? result.score : undefined);
      } catch (error) {
        throw new ResultBandError("bad_score", SCORE_MESSAGE, error);
      }
      return { band: band, variant: variant, label: label, score: score };
    }

    function render(result) {
      const read = measure(result);
      clear();
      const row = document.createElement("div");
      for (const name of [...ROW_CLASSES, ROW_CLASS]) {
        row.classList.add(name);
      }
      const tag = document.createElement("span");
      tag.classList.add(TAG_CLASS);
      tag.classList.add(TAG_SIZE_CLASS);
      tag.classList.add(read.variant);
      tag.textContent = read.label;
      const score = document.createElement("span");
      score.classList.add(SCORE_CLASS);
      const label = document.createElement("span");
      label.classList.add(SR_ONLY_CLASS);
      label.textContent = SCORE_LABEL;
      score.appendChild(label);
      score.appendChild(document.createTextNode(read.score));
      row.appendChild(tag);
      row.appendChild(score);
      container.appendChild(row);
      line = row;
      current = read;
      return true;
    }

    // Only what this module drew is taken away, so a page's own children in
    // the same container are none of this module's business.
    function clear() {
      const removed = line !== null;
      if (line !== null) {
        container.removeChild(line);
        line = null;
        current = null;
      }
      return removed;
    }

    return {
      render,
      clear,
      band: () => (current === null ? null : current.band),
      variant: () => (current === null ? null : current.variant),
      label: () => (current === null ? null : current.label),
      score: () => (current === null ? null : current.score),
    };
  }

  window.DRISHTI_RESULT_BAND = {
    TAG_CLASS,
    TAG_SIZE_CLASS,
    SR_ONLY_CLASS,
    ROW_CLASS,
    ROW_CLASSES,
    SCORE_CLASS,
    SCORE_LABEL,
    BAND_VARIANTS,
    REQUIRED_ELEMENTS,
    ResultBandError,
    bandVariant,
    bindResultBand,
  };
})();