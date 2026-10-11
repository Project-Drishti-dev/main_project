(() => {
  "use strict";

  // One feed reads one screening's recorded progress and hands a page the same
  // sequence whichever transport carried it: the stream, when the browser has
  // one and it connects, and the whole document when it does not. The address
  // belongs to api.js, so this module holds two paths and no host.

  const STREAM_SUFFIX = "/progress/stream";
  const POLL_SUFFIX = "/progress";

  const IDLE = "idle";
  const STREAM = "stream";
  const POLL = "poll";

  // The service writes these two names and no others (app/progress.py).
  const PROGRESS_EVENT = "progress";
  const DONE_EVENT = "done";

  const POLL_INTERVAL_MS = 1000;
  const MAX_POLL_ATTEMPTS = 3;

  const NO_API_MESSAGE = "This page cannot reach the quality service.";
  const NO_ID_MESSAGE = "There is no screening to read progress for.";
  const BAD_STEP_MESSAGE =
    "The service reported a step that names no unit, so it cannot be drawn.";
  const BAD_DOCUMENT_MESSAGE =
    "The service answered with no readable progress document.";
  const BAD_FRAME_MESSAGE =
    "The service sent a progress frame this page cannot read.";
  const GAVE_UP_MESSAGE =
    "The progress of this screening could not be read. Reload the page to " +
    "try again.";

  class ProgressFeedError extends Error {
    constructor(code, message) {
      super(message);
      this.name = "ProgressFeedError";
      this.code = code;
    }
  }

  function readId(screeningId) {
    if (typeof screeningId !== "string" || screeningId.trim() === "") {
      throw new ProgressFeedError("no_screening_id", NO_ID_MESSAGE);
    }
    return screeningId.trim();
  }

  function screeningPath(screeningId, suffix) {
    return "/api/screenings/" + encodeURIComponent(readId(screeningId)) + suffix;
  }

  function streamPath(screeningId) {
    return screeningPath(screeningId, STREAM_SUFFIX);
  }

  function pollPath(screeningId) {
    return screeningPath(screeningId, POLL_SUFFIX);
  }

  function readUnits(units) {
    if (!Number.isInteger(units) || units < 0) {
      throw new ProgressFeedError("bad_document", BAD_DOCUMENT_MESSAGE);
    }
    return units;
  }

  // A panel cannot draw a step naming no unit and no state, so such a step is
  // refused rather than passed on as a blank row. The remaining keys travel
  // through untouched: the service owns what a step carries besides these two.
  function readStep(entry) {
    if (entry === null || typeof entry !== "object" || Array.isArray(entry)) {
      throw new ProgressFeedError("bad_step", BAD_STEP_MESSAGE);
    }
    for (const key of ["unit", "state"]) {
      if (typeof entry[key] !== "string" || entry[key] === "") {
        throw new ProgressFeedError("bad_step", BAD_STEP_MESSAGE);
      }
    }
    return entry;
  }

  function readEvents(document) {
    if (document === null || typeof document !== "object") {
      throw new ProgressFeedError("bad_document", BAD_DOCUMENT_MESSAGE);
    }
    if (!Array.isArray(document.events)) {
      throw new ProgressFeedError("bad_document", BAD_DOCUMENT_MESSAGE);
    }
    return document.events.map(readStep);
  }

  // A frame's data line is text, so it is parsed here rather than trusted: a
  // body that is not JSON is refused by name instead of reaching a panel.
  function readFrame(event) {
    const data = event ? event.data : undefined;
    if (typeof data !== "string") {
      throw new ProgressFeedError("bad_frame", BAD_FRAME_MESSAGE);
    }
    let parsed;
    try {
      parsed = JSON.parse(data);
    } catch {
      throw new ProgressFeedError("bad_frame", BAD_FRAME_MESSAGE);
    }
    if (parsed === null || typeof parsed !== "object") {
      throw new ProgressFeedError("bad_frame", BAD_FRAME_MESSAGE);
    }
    return parsed;
  }

  async function readJson(response) {
    try {
      return await response.json();
    } catch {
      // An unreadable body and a body that is not a document are one answer:
      // the service did not send the sequence.
      throw new ProgressFeedError("bad_document", BAD_DOCUMENT_MESSAGE);
    }
  }

  function readAttempts(attempts) {
    if (attempts === undefined) {
      return MAX_POLL_ATTEMPTS;
    }
    if (!Number.isInteger(attempts) || attempts < 1) {
      throw new ProgressFeedError(
        "bad_attempts",
        "A progress feed takes a whole number of polling attempts, at least one.",
      );
    }
    return attempts;
  }

  function readCallback(settings, name) {
    const callback = settings ? settings[name] : null;
    if (typeof callback !== "function") {
      throw new ProgressFeedError(
        "missing_callback",
        "The progress feed needs a callback named " + name + ".",
      );
    }
    return callback;
  }

  // bindProgressFeed wires one screening's progress to three callbacks and
  // starts nothing: start() opens the stream, and only a caller starts it.
  function bindProgressFeed(options) {
    const settings = options || {};
    const screeningId = readId(settings.screeningId);
    const onStep = readCallback(settings, "onStep");
    const onComplete = readCallback(settings, "onComplete");
    const onFailed = readCallback(settings, "onFailed");
    const maxAttempts = readAttempts(settings.maxPollAttempts);
    const api = window.DRISHTI_API;
    if (!api || typeof api.request !== "function") {
      throw new ProgressFeedError("no_api", NO_API_MESSAGE);
    }

    let transport = IDLE;
    let source = null;
    let timer = null;
    let attempts = 0;
    let stopped = false;
    let complete = false;
    const steps = [];

    function closeSource() {
      if (source !== null) {
        source.close();
        source = null;
      }
    }

    function clearTimer() {
      if (timer !== null) {
        clearTimeout(timer);
        timer = null;
      }
    }

    function armTimer() {
      clearTimer();
      timer = setTimeout(poll, POLL_INTERVAL_MS);
    }

    // A stream frame is the next step in the sequence, so it is always told.
    function publishOne(step) {
      const index = steps.length;
      steps.push(step);
      onStep(step, index);
    }

    // A document is the whole sequence from its first step, so a poll after a
    // stream that died midway starts where the stream stopped: what was told
    // is skipped, and the rest is told once. `steps` is the only count of what
    // the page has seen, so the two transports cannot drift from each other.
    function publishFrom(list) {
      for (let index = steps.length; index < list.length; index += 1) {
        steps.push(list[index]);
        onStep(list[index], index);
      }
    }

    function finish(units) {
      if (complete || stopped) {
        return;
      }
      complete = true;
      closeSource();
      clearTimer();
      onComplete(units);
    }

    function fail(refusal) {
      if (complete || stopped) {
        return;
      }
      complete = true;
      closeSource();
      clearTimer();
      onFailed(refusal);
    }

    // A frame arrives through the browser, not through this module's own
    // awaits, so a refusal is caught here and named rather than thrown back
    // into the event listener that delivered it.
    function onProgressFrame(event) {
      if (complete || stopped) {
        return;
      }
      try {
        publishOne(readStep(readFrame(event)));
      } catch (refusal) {
        fail(refusal);
      }
    }

    function onDoneFrame(event) {
      if (complete || stopped) {
        return;
      }
      try {
        finish(readUnits(readFrame(event).units));
      } catch (refusal) {
        fail(refusal);
      }
    }

    // The service ends its own stream on `done`, so an error always means the
    // sequence did not arrive whole -- whatever was delivered stands, and the
    // document fills in the rest.
    function onStreamError() {
      if (complete || stopped) {
        return;
      }
      closeSource();
      startPolling();
    }

    async function poll() {
      if (complete || stopped) {
        return;
      }
      timer = null;
      attempts += 1;
      let document;
      try {
        const response = await api.request(pollPath(screeningId));
        document = await readJson(response);
      } catch {
        if (attempts >= maxAttempts) {
          fail(new ProgressFeedError("no_progress", GAVE_UP_MESSAGE));
          return;
        }
        armTimer();
        return;
      }
      try {
        publishFrom(readEvents(document));
        const units = readUnits(document.units);
        if (document.events.length >= units) {
          finish(units);
          return;
        }
      } catch (refusal) {
        fail(refusal);
        return;
      }
      armTimer();
    }

    function startPolling() {
      transport = POLL;
      attempts = 0;
      poll();
    }

    function openStream() {
      if (typeof window.EventSource !== "function") {
        startPolling();
        return;
      }
      const opened = new window.EventSource(
        api.readApiBaseUrl() + streamPath(screeningId),
      );
      source = opened;
      transport = STREAM;
      opened.addEventListener(PROGRESS_EVENT, onProgressFrame);
      opened.addEventListener(DONE_EVENT, onDoneFrame);
      opened.addEventListener("error", onStreamError);
    }

    // One connection per feed: a second start reads nothing and changes
    // nothing, so a page cannot open the same sequence twice.
    function start() {
      if (transport !== IDLE) {
        return transport;
      }
      openStream();
      return transport;
    }

    function stop() {
      stopped = true;
      closeSource();
      clearTimer();
    }

    return {
      start,
      stop,
      transport: () => transport,
      steps: () => steps.slice(),
      units: () => steps.length,
      complete: () => complete,
      attempts: () => attempts,
    };
  }

  window.DRISHTI_PROGRESS_FEED = {
    DONE_EVENT,
    IDLE,
    MAX_POLL_ATTEMPTS,
    POLL,
    POLL_INTERVAL_MS,
    POLL_SUFFIX,
    PROGRESS_EVENT,
    STREAM,
    STREAM_SUFFIX,
    ProgressFeedError,
    bindProgressFeed,
    pollPath,
    streamPath,
  };
})();