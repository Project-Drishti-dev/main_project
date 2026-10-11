(() => {
  "use strict";

  // Where the case view's documents come from: one read of
  // `GET /api/screenings/{id}` per screening the page was opened with, drawn
  // as one card per document beside the others. Each card carries the kind of
  // document the upload claimed, the band it was scored at, and the
  // cross-document flags raised against it. Reads window.DRISHTI_API. A
  // payload it cannot read is refused by name rather than drawn as a half
  // card.

  const SCREENINGS_ROOT = "/api/screenings";

  // The query parameter naming a document. Read whole, so `?id=a&id=b` is two
  // documents: the page is asked about as many as the link names.
  const ID_PARAM = "id";

  // app/risk/flags.py spells a flag's tier as 0, 1, 2, "quality" or
  // "crossdoc". The cross-document tier is the one rule set that compares two
  // documents of a case, and the only tier this view draws.
  const CROSSDOC_TIER = "crossdoc";

  // One variant per band app/risk/bands.py bands in, and the words format.js
  // labels those bands with. Both tables are held here and pinned against
  // their owners by cases.test.cjs, so neither can fall behind.
  const BAND_VARIANTS = {
    low: "ux4g-tag-filled-success",
    review: "ux4g-tag-filled-warning",
    high: "ux4g-tag-filled-error",
  };

  const BAND_LABELS = {
    low: "Low Risk",
    review: "Review",
    high: "High Risk",
  };

  // A row nothing scored carries no band and no score. It gets the neutral tag
  // and says so, on screenings-list.js's rule: an unscored row is not a
  // clearance and not a verdict.
  const UNSCORED_VARIANT = "ux4g-tag-filled-neutral";
  const UNSCORED_LABEL = "Not scored";

  const TAG_CLASS = "ux4g-tag";
  const TAG_SIZE_CLASS = "ux4g-tag-s";
  const SR_ONLY_CLASS = "ux4g-sr-only";

  // What the cross-document cell is called, and what a document whose rules
  // raised no cross-document flag says instead of standing empty.
  const CROSSDOC_HEADING = "Cross-document flags";
  const NO_CROSSDOC_LABEL = "No cross-document flag was raised.";

  // A bare number beside a tag is not a score, so the word is in the markup
  // for a screen reader and out of the way on screen.
  const SCORE_LABEL = "Score: ";
  const ID_LABEL = "Screening id: ";

  // The states the document set is not in, and the state it is in when an
  // answer carries a card. One switch writes all of them, as 24.7's does on
  // the history page.
  const STATE_DOCUMENTS = "documents";
  const STATE_LOADING = "loading";
  const STATE_EMPTY = "empty";
  const STATE_ERROR = "error";
  const STATE_SINGLE = "single";
  const STATES = [
    STATE_DOCUMENTS,
    STATE_LOADING,
    STATE_EMPTY,
    STATE_ERROR,
    STATE_SINGLE,
  ];

  const LOADING_MESSAGE = "Loading the case.";
  const GRID_CLASSES = [
    "ux4g-grid",
    "ux4g-grid-cols-1",
    "ux4g-md-grid-cols-2",
    "ux4g-xl-grid-cols-3",
    "ux4g-gap-m",
  ];
  const CARD_CLASSES = ["ux4g-card", "ux4g-card-body"];
  const BAND_ROW_CLASSES = ["ux4g-d-flex", "ux4g-gap-s"];
  const CARD_STACK_CLASSES = ["ux4g-grid", "ux4g-gap-y-s"];

  const REQUIRED_ELEMENTS = ["grid"];

  const ELEMENTS_MESSAGE =
    "The case view needs an element to draw the documents into: ";
  const IDS_MESSAGE =
    "The case view needs a list of screening ids to read, even an empty one.";
  const NO_API_MESSAGE =
    "This page cannot reach the API client, so it cannot read the case.";
  const PAYLOAD_MESSAGE =
    "A screening answer must carry a screening_id, a document_type and a band.";
  const BAND_MESSAGE =
    "A band is one of the three the engine bands in: " +
    Object.keys(BAND_VARIANTS).join(", ") +
    ", or null where nothing scored the row.";
  const SCORE_MESSAGE =
    "A score must be a number between 0 and 100, or null where nothing " +
    "scored the row.";
  const FLAGS_MESSAGE =
    "A screening's flags must be a list, and a cross-document flag must " +
    "carry a label and a reason as non-empty sentences.";

  class CaseViewError extends Error {
    constructor(code, message, cause) {
      super(message);
      this.name = "CaseViewError";
      this.code = code;
      if (cause !== undefined) {
        this.cause = cause;
      }
    }
  }

  // The id goes into a URL, so it is encoded rather than pasted: a value that
  // were not an id must not be able to close the path.
  function screeningPath(id) {
    return SCREENINGS_ROOT + "/" + encodeURIComponent(id);
  }

  // The ids the page was opened with, in the order the link named them. A
  // blank parameter names no document and is dropped rather than read as one.
  function screeningIdsFromSearch(search) {
    const text = typeof search === "string" ? search : "";
    const parameters = new URLSearchParams(
      text.startsWith("?") ? text.slice(1) : text,
    );
    const ids = [];
    for (const value of parameters.getAll(ID_PARAM)) {
      const id = value.trim();
      if (id !== "") {
        ids.push(id);
      }
    }
    return ids;
  }

  function readElement(settings, name) {
    const element = settings ? settings[name] : null;
    if (!element) {
      throw new CaseViewError(
        "missing_element",
        ELEMENTS_MESSAGE + name + ".",
      );
    }
    return element;
  }

  // hasOwnProperty rather than a lookup: a band named "toString" is not one
  // the engine bands in, and an inherited property would answer for it. A
  // null band is not a bad band, and answers with the neutral variant.
  function bandVariant(band) {
    if (band === null) {
      return UNSCORED_VARIANT;
    }
    if (
      typeof band !== "string" ||
      Object.prototype.hasOwnProperty.call(BAND_VARIANTS, band) === false
    ) {
      throw new CaseViewError("bad_band", BAND_MESSAGE);
    }
    return BAND_VARIANTS[band];
  }

  function bandLabel(band) {
    if (band === null) {
      return UNSCORED_LABEL;
    }
    if (
      typeof band !== "string" ||
      Object.prototype.hasOwnProperty.call(BAND_LABELS, band) === false
    ) {
      throw new CaseViewError("bad_band", BAND_MESSAGE);
    }
    return BAND_LABELS[band];
  }

  // A score is the number the service sent, at the one decimal format.js
  // prints, or null where nothing scored the row.
  function readScore(value) {
    if (value === null) {
      return null;
    }
    if (
      typeof value !== "number" ||
      Number.isFinite(value) === false ||
      value < 0 ||
      value > 100
    ) {
      throw new CaseViewError("bad_score", SCORE_MESSAGE);
    }
    return value.toFixed(1);
  }

  // The cross-document flags and nothing else. Every other tier is scoped to
  // one document and belongs on the result page, so a card here carries only
  // the rules that compared this document with another one.
  function readCrossdocFlags(value) {
    if (Array.isArray(value) === false) {
      throw new CaseViewError("bad_flags", FLAGS_MESSAGE);
    }
    const crossdoc = [];
    for (const flag of value) {
      if (flag === null || typeof flag !== "object" || Array.isArray(flag)) {
        throw new CaseViewError("bad_flags", FLAGS_MESSAGE);
      }
      if (flag.tier !== CROSSDOC_TIER) {
        continue;
      }
      for (const name of ["label", "reason"]) {
        if (typeof flag[name] !== "string" || flag[name].trim() === "") {
          throw new CaseViewError("bad_flags", FLAGS_MESSAGE);
        }
      }
      crossdoc.push({ label: flag.label, reason: flag.reason });
    }
    return crossdoc;
  }

  // Every field is read before anything is drawn, so an answer this page
  // cannot read leaves the documents as they stood rather than half replaced.
  function readDocument(payload) {
    if (
      payload === null ||
      typeof payload !== "object" ||
      Array.isArray(payload)
    ) {
      throw new CaseViewError("bad_document", PAYLOAD_MESSAGE);
    }
    if (
      typeof payload.screening_id !== "string" ||
      payload.screening_id.trim() === ""
    ) {
      throw new CaseViewError("bad_document", PAYLOAD_MESSAGE);
    }
    if (
      typeof payload.document_type !== "string" ||
      payload.document_type.trim() === ""
    ) {
      throw new CaseViewError("bad_document", PAYLOAD_MESSAGE);
    }
    const band = payload.band === undefined ? null : payload.band;
    const variant = bandVariant(band);
    const label = bandLabel(band);
    return {
      id: payload.screening_id,
      documentType: payload.document_type,
      band: band,
      variant: variant,
      label: label,
      score: readScore(payload.score === undefined ? null : payload.score),
      crossdoc: readCrossdocFlags(
        payload.flags === undefined ? [] : payload.flags,
      ),
    };
  }

  function documentCountText(count) {
    return count === 1 ? "1 document" : count + " documents";
  }

  // The answer a set of documents has: none named, one named and therefore
  // nothing to place beside it, or two or more to compare against each other.
  function stateFor(count) {
    if (count === 0) {
      return STATE_EMPTY;
    }
    if (count === 1) {
      return STATE_SINGLE;
    }
    return STATE_DOCUMENTS;
  }

  function heading(level, text) {
    const element = document.createElement("h" + level);
    element.textContent = text;
    return element;
  }

  // The screening id beside the band: without it two cards of the same
  // document type are two rows an officer cannot tell apart.
  function idLine(entry) {
    const line = document.createElement("p");
    const label = document.createElement("span");
    label.classList.add(SR_ONLY_CLASS);
    label.textContent = ID_LABEL;
    line.appendChild(label);
    line.appendChild(document.createTextNode(entry.id));
    return line;
  }

  // The band as one tag, so three answers cannot be read as three shades of
  // the same thing, and the score beside it in the row result-band.js uses.
  function bandLine(entry) {
    const row = document.createElement("div");
    for (const name of BAND_ROW_CLASSES) {
      row.classList.add(name);
    }
    const tag = document.createElement("span");
    tag.classList.add(TAG_CLASS);
    tag.classList.add(TAG_SIZE_CLASS);
    tag.classList.add(entry.variant);
    tag.setAttribute("data-band", entry.band === null ? "" : entry.band);
    tag.textContent = entry.label;
    row.appendChild(tag);
    if (entry.score !== null) {
      const score = document.createElement("span");
      const label = document.createElement("span");
      label.classList.add(SR_ONLY_CLASS);
      label.textContent = SCORE_LABEL;
      score.appendChild(label);
      score.appendChild(document.createTextNode(entry.score));
      row.appendChild(score);
    }
    return row;
  }

  // A bare <ul>/<li>, as 24.9's explanation cell: the sheet's list classes
  // carry their own padding, border and divider, which would draw a box
  // inside the card's own box (G14).
  function crossdocCell(entry) {
    const cell = document.createElement("div");
    cell.appendChild(heading(4, CROSSDOC_HEADING));
    if (entry.crossdoc.length === 0) {
      const none = document.createElement("p");
      none.textContent = NO_CROSSDOC_LABEL;
      cell.appendChild(none);
      return cell;
    }
    const list = document.createElement("ul");
    for (const flag of entry.crossdoc) {
      const item = document.createElement("li");
      const title = document.createElement("p");
      title.textContent = flag.label;
      const reason = document.createElement("p");
      reason.textContent = flag.reason;
      item.appendChild(title);
      item.appendChild(reason);
      list.appendChild(item);
    }
    cell.appendChild(list);
    return cell;
  }

  // One card per document: the kind of document, the band it was scored at,
  // and the cross-document flags raised against it. The data-band attribute
  // carries the band itself, so the answer does not rest on the tag's colour.
  // The cross-document section is drawn only where there is a comparison to
  // report: two documents in the case, or a flag the service raised. With one
  // document and no flag the section would say the rules ran and found
  // nothing, which is a claim no cross-document rule could make.
  function drawDocument(entry, showCrossdoc) {
    const card = document.createElement("article");
    for (const name of CARD_CLASSES) {
      card.classList.add(name);
    }
    const stack = document.createElement("div");
    for (const name of CARD_STACK_CLASSES) {
      stack.classList.add(name);
    }
    stack.appendChild(heading(3, entry.documentType));
    stack.appendChild(idLine(entry));
    stack.appendChild(bandLine(entry));
    if (showCrossdoc) {
      stack.appendChild(crossdocCell(entry));
    }
    card.appendChild(stack);
    card.setAttribute("data-screening-id", entry.id);
    card.setAttribute("data-band", entry.band === null ? "" : entry.band);
    return card;
  }

  // bindCaseView wires one document set to the screenings route, and draws
  // nothing until a caller calls load() or render().
  function bindCaseView(options) {
    const settings = options || {};
    const grid = readElement(settings, "grid");
    const count = settings.count ?? null;
    const loading = settings.loading ?? null;
    const failure = settings.failure ?? null;
    const failureMessage = settings.failureMessage ?? null;
    const retry = settings.retry ?? null;
    const empty = settings.empty ?? null;
    const single = settings.single ?? null;
    const ids = settings.ids;
    if (Array.isArray(ids) === false) {
      throw new CaseViewError("missing_ids", IDS_MESSAGE);
    }

    let current = [];
    let lastError = null;
    let shown = STATE_LOADING;

    function clear() {
      while (grid.firstChild) {
        grid.removeChild(grid.firstChild);
      }
      current = [];
      return true;
    }

    // One switch for every state the document set is not in. The grid, the
    // skeleton, the alert, the empty panel and the one-document panel are
    // switched together, and the container's aria-busy travels with the
    // skeleton. A one-document case keeps the grid up: the document is real,
    // and only what it could be compared against is missing.
    function showState(state) {
      if (STATES.includes(state) === false) {
        throw new CaseViewError(
          "bad_state",
          "The case view can only be " + STATES.join(", ") + ".",
        );
      }
      if (loading) {
        loading.hidden = state !== STATE_LOADING;
        loading.setAttribute(
          "aria-busy",
          state === STATE_LOADING ? "true" : "false",
        );
      }
      if (failure) {
        failure.hidden = state !== STATE_ERROR;
      }
      if (grid) {
        grid.hidden = state !== STATE_DOCUMENTS && state !== STATE_SINGLE;
      }
      if (empty) {
        empty.hidden = state !== STATE_EMPTY;
      }
      if (single) {
        single.hidden = state !== STATE_SINGLE;
      }
      shown = state;
      return state;
    }

    // The answers are read whole before anything is drawn, so an answer this
    // page cannot read leaves the documents as they stood.
    function render(answers) {
      const read = (Array.isArray(answers) ? answers : []).map(readDocument);
      clear();
      for (const entry of read) {
        grid.appendChild(
          drawDocument(entry, read.length > 1 || entry.crossdoc.length > 0),
        );
      }
      if (count) {
        count.textContent =
          read.length === 0 ? "" : documentCountText(read.length);
      }
      showState(stateFor(read.length));
      current = read;
      return read;
    }

    // A failed read is shown in the alert the page ships, in the failure's own
    // words: the service wrote them, and this page does not improve on them.
    function fail(error) {
      lastError = error;
      if (failureMessage) {
        failureMessage.textContent = error.message;
      }
      if (count) {
        count.textContent = "";
      }
      showState(STATE_ERROR);
      return null;
    }

    if (retry) {
      retry.addEventListener("click", load);
    }

    // A failure is stored and shown in the alert rather than thrown at the
    // caller: an unhandled rejection would leave the page on the skeleton with
    // nothing to say. The ids are read one after another and every answer is
    // read whole before the first card is drawn.
    async function load() {
      const api = window.DRISHTI_API;
      if (!api || typeof api.request !== "function") {
        throw new CaseViewError("no_api", NO_API_MESSAGE);
      }
      if (ids.length === 0) {
        clear();
        if (count) {
          count.textContent = "";
        }
        showState(STATE_EMPTY);
        current = [];
        return [];
      }
      showState(STATE_LOADING);
      if (count) {
        count.textContent = LOADING_MESSAGE;
      }
      try {
        const answers = [];
        for (const id of ids) {
          const response = await api.request(screeningPath(id));
          answers.push(await response.json());
        }
        return render(answers);
      } catch (error) {
        return fail(error);
      }
    }

    return {
      render,
      clear,
      load,
      showState,
      state: () => shown,
      documents: () => current.slice(),
      error: () => lastError,
    };
  }

  function start() {
    const grid = document.getElementById("case-documents");
    if (!grid) {
      return null;
    }
    const view = bindCaseView({
      grid: grid,
      count: document.getElementById("case-count"),
      loading: document.getElementById("case-loading"),
      failure: document.getElementById("case-error"),
      failureMessage: document.getElementById("case-error-message"),
      retry: document.getElementById("case-retry"),
      empty: document.getElementById("case-empty"),
      single: document.getElementById("case-single"),
      ids: screeningIdsFromSearch(window.location.search),
    });
    view.load();
    return view;
  }

  window.DRISHTI_CASES = {
    SCREENINGS_ROOT,
    ID_PARAM,
    CROSSDOC_TIER,
    BAND_VARIANTS,
    BAND_LABELS,
    UNSCORED_VARIANT,
    UNSCORED_LABEL,
    TAG_CLASS,
    TAG_SIZE_CLASS,
    SR_ONLY_CLASS,
    CROSSDOC_HEADING,
    NO_CROSSDOC_LABEL,
    SCORE_LABEL,
    ID_LABEL,
    STATES,
    STATE_DOCUMENTS,
    STATE_EMPTY,
    STATE_ERROR,
    STATE_LOADING,
    STATE_SINGLE,
    LOADING_MESSAGE,
    GRID_CLASSES,
    CARD_CLASSES,
    BAND_ROW_CLASSES,
    CARD_STACK_CLASSES,
    REQUIRED_ELEMENTS,
    CaseViewError,
    screeningPath,
    screeningIdsFromSearch,
    bandVariant,
    bandLabel,
    readScore,
    readCrossdocFlags,
    readDocument,
    documentCountText,
    stateFor,
    drawDocument,
    bindCaseView,
    start,
  };

  if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", start);
    } else {
      start();
    }
  }
})();