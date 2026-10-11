(() => {
  "use strict";

  // The cascade progress panel: one progress bar for the whole screening,
  // and one live region beside it saying what the bar cannot. UX4G ships the
  // bar as classes and data attributes with no ARIA at all (preflight G2), so
  // every role, every aria- value and every sentence below is written by hand
  // onto markup this module builds. It reads no service and sends nothing:
  // the steps arrive as 22.9's feed calls them, and that feed is the only
  // caller.

  const REQUIRED_ELEMENTS = ["container"];

  // Read out of the installed stylesheet (styles/ux4g.css) by a case, so a
  // name UX4G stops shipping cannot go on being written here.
  const BAR_MARKER = "data-ux-progress-bar";
  const TRACK_CLASS = "ux4g-progress-bar-track";
  const FILL_CLASS = "ux4g-progress-bar-fill";
  const LABEL_ATTRIBUTE = "data-ux-progress-label";
  const SHAPE_ATTRIBUTE = "data-ux-shape";
  const SHAPE_VALUE = "rounded";
  const PLACEMENT_ATTRIBUTE = "data-ux-label-placement";
  const PLACEMENT_VALUE = "outside";
  const VALUE_VARIABLE = "--ux4g-progress-value";

  const BAR_ROLE = "progressbar";
  const BAR_NAME = "Cascade progress";
  const MINIMUM = "0";
  const MAXIMUM = "100";
  const LIVE_ROLE = "status";
  const LIVE_POLITENESS = "polite";
  const EMPTY_VALUE = "0";
  const INDETERMINATE = null;

  // The two units the service writes and no others (app/progress.py): a tier
  // is completed because the trail recorded it and a module is reported
  // because a stored finding named it, so neither word stands in for the
  // other here either.
  const UNIT_TIER = "tier";
  const UNIT_MODULE = "module";
  const UNITS = [UNIT_TIER, UNIT_MODULE];

  const WAITING_TEXT = "Screening running. No steps reported yet.";
  const FINISHED_TEXT =
    "Screening finished. Every recorded step has been reported.";

  const NO_DOCUMENT_MESSAGE = "This page cannot build the progress panel.";
  const NO_TIER_MESSAGE = "A progress step naming no tier cannot be drawn.";
  const NO_MODULE_MESSAGE = "A progress step naming no module cannot be drawn.";
  const NO_UNIT_MESSAGE =
    "The service reported a progress step this panel cannot draw: ";
  const BAD_UNITS_MESSAGE =
    "A finished screening reports a whole number of steps, and none below " +
    "zero.";

  class ProgressPanelError extends Error {
    constructor(code, message) {
      super(message);
      this.name = "ProgressPanelError";
      this.code = code;
    }
  }

  function readElement(settings, name) {
    const element = settings ? settings[name] : null;
    if (!element) {
      throw new ProgressPanelError(
        "missing_element",
        "The progress panel needs an element named " + name + ".",
      );
    }
    return element;
  }

  function readName(step, key) {
    const name = step ? step[key] : undefined;
    if (typeof name !== "string" || name === "") {
      throw new ProgressPanelError(
        key === UNIT_TIER ? "bad_tier" : "bad_module",
        key === UNIT_TIER ? NO_TIER_MESSAGE : NO_MODULE_MESSAGE,
      );
    }
    return name;
  }

  function readUnits(units) {
    if (!Number.isInteger(units) || units < 0) {
      throw new ProgressPanelError("bad_units", BAD_UNITS_MESSAGE);
    }
    return units;
  }

  // statusText is the bar's text alternative: the same sentence goes to
  // aria-valuetext and to the visible label, so what a screen reader is told
  // and what an officer reads are one string rather than two claims.
  function statusText(steps, total) {
    if (total === INDETERMINATE) {
      if (steps === 0) {
        return WAITING_TEXT;
      }
      return steps === 1
        ? "1 step reported."
        : steps + " steps reported.";
    }
    return steps + " of " + total + " steps reported.";
  }

  // The service's own words, in the service's own order. A step that ran
  // twice is announced twice, because the index makes the two sentences
  // different -- a live region only speaks when its text changes.
  function announcementFor(step, index) {
    const position = "Step " + (index + 1) + ": ";
    if (step.unit === UNIT_TIER) {
      return (
        position + UNIT_TIER + " " + readName(step, UNIT_TIER) + " " +
        step.state + "."
      );
    }
    return (
      position + UNIT_MODULE + " " + readName(step, UNIT_MODULE) + " " +
      step.state + " under " + UNIT_TIER + " " + readName(step, UNIT_TIER) +
      "."
    );
  }

  // percentFor is the one number the drawn bar and the announced bar are both
  // written from, so the fill and aria-valuenow cannot disagree.
  function percentFor(steps, total) {
    if (total === INDETERMINATE || total === 0) {
      return 0;
    }
    return Math.round((steps / total) * 100);
  }

  // bindProgressPanel builds one panel into a container the page owns, and
  // starts nothing: the page calls step() as 22.9's feed reports and
  // complete() when the sequence ends.
  function bindProgressPanel(options) {
    const settings = options || {};
    const container = readElement(settings, "container");
    if (
      typeof document !== "object" ||
      document === null ||
      typeof document.createElement !== "function"
    ) {
      throw new ProgressPanelError("no_document", NO_DOCUMENT_MESSAGE);
    }

    // The bar's own markup, spelled the way the sheet spells it. The label
    // sits outside the track because the bar starts empty: a label inside a
    // 0%-wide fill is a label nobody can read.
    const bar = document.createElement("div");
    bar.setAttribute(BAR_MARKER, "");
    bar.setAttribute(SHAPE_ATTRIBUTE, SHAPE_VALUE);
    bar.setAttribute(PLACEMENT_ATTRIBUTE, PLACEMENT_VALUE);
    const track = document.createElement("div");
    track.classList.add(TRACK_CLASS);
    const fill = document.createElement("div");
    fill.classList.add(FILL_CLASS);
    track.appendChild(fill);
    bar.appendChild(track);
    const label = document.createElement("span");
    label.setAttribute(LABEL_ATTRIBUTE, "");
    bar.appendChild(label);
    const live = document.createElement("div");
    live.setAttribute("role", LIVE_ROLE);
    live.setAttribute("aria-live", LIVE_POLITENESS);
    container.appendChild(bar);
    container.appendChild(live);

    let steps = 0;
    let total = INDETERMINATE;
    let finished = false;
    let stopped = false;

    // The run's own step count arrives with the done frame (D151), so until it
    // lands the bar is indeterminate: no aria-valuenow, and an empty fill
    // rather than the 50 the sheet ships as its default.
    function setValue(percent) {
      if (percent === INDETERMINATE) {
        bar.style.setProperty(VALUE_VARIABLE, EMPTY_VALUE);
        bar.removeAttribute("aria-valuenow");
        return;
      }
      bar.style.setProperty(VALUE_VARIABLE, String(percent));
      bar.setAttribute("aria-valuenow", String(percent));
    }

    function setStatus(reported, out) {
      const sentence = statusText(reported, out);
      bar.setAttribute("aria-valuetext", sentence);
      label.textContent = sentence;
      return sentence;
    }

    bar.setAttribute("role", BAR_ROLE);
    bar.setAttribute("aria-label", BAR_NAME);
    bar.setAttribute("aria-valuemin", MINIMUM);
    bar.setAttribute("aria-valuemax", MAXIMUM);
    setValue(INDETERMINATE);
    setStatus(steps, total);

    // step draws one reported step. A step the panel cannot name is refused
    // before anything is written, so a refused step leaves no announcement
    // and no moved bar behind it.
    function step(entry, index) {
      if (finished || stopped) {
        return null;
      }
      const report =
        entry !== null && typeof entry === "object" ? entry : {};
      if (!UNITS.includes(report.unit)) {
        throw new ProgressPanelError(
          "bad_unit",
          NO_UNIT_MESSAGE + String(report.unit),
        );
      }
      const position = Number.isInteger(index) && index >= 0 ? index : steps;
      const announcement = announcementFor(report, position);
      steps += 1;
      live.textContent = announcement;
      setStatus(steps, total);
      return announcement;
    }

    // complete is the done frame: the denominator the bar was waiting for.
    function complete(units) {
      if (finished || stopped) {
        return null;
      }
      const counted = readUnits(units);
      finished = true;
      total = counted;
      const percent = percentFor(steps, counted);
      setValue(percent);
      setStatus(steps, counted);
      live.textContent = FINISHED_TEXT;
      return percent;
    }

    // stop is the one path back to a panel that claims nothing further, so a
    // refused sequence cannot keep filling a bar nobody is reading.
    function stop() {
      if (finished || stopped) {
        return false;
      }
      stopped = true;
      return true;
    }

    return {
      bar,
      live,
      step,
      complete,
      stop,
      steps: () => steps,
      total: () => total,
      value: () =>
        total === INDETERMINATE ? INDETERMINATE : percentFor(steps, total),
      status: () => bar.getAttribute("aria-valuetext"),
      announced: () => live.textContent,
      stopped: () => stopped,
    };
  }

  window.DRISHTI_PROGRESS_PANEL = {
    BAR_MARKER,
    BAR_NAME,
    BAR_ROLE,
    FILL_CLASS,
    FINISHED_TEXT,
    LABEL_ATTRIBUTE,
    LIVE_POLITENESS,
    LIVE_ROLE,
    PLACEMENT_VALUE,
    REQUIRED_ELEMENTS,
    TRACK_CLASS,
    UNIT_MODULE,
    UNIT_TIER,
    UNITS,
    VALUE_VARIABLE,
    WAITING_TEXT,
    ProgressPanelError,
    announcementFor,
    bindProgressPanel,
    statusText,
  };
})();
