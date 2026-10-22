(() => {
  "use strict";

  // Where the audit view's rows come from: one read of
  // `GET /api/audit/{id}/verify` per audit id the page was opened with,
  // drawn into the tbody the markup holds. Each row is six columns: the event
  // id, the status the walk answered, the batch it reached, the root it read
  // back, the length of the path it walked, and one line per check that
  // completed. Reads window.DRISHTI_API for the request. A payload it cannot
  // read is refused by name rather than drawn as a half row.

  const VERIFY_ROOT = "/api/audit";
  const VERIFY_SUFFIX = "/verify";

  // The query parameter naming a record. Read whole, so `?id=a&id=b` is two
  // rows: the page is asked about as many events as the link names.
  const ID_PARAM = "id";

  // The three words app/ledger/verification.py answers with, and no others.
  const STATUSES = ["verified", "altered", "unknown"];

  // The states the event list is not in, and the state it is in when the
  // answer carries a row. One switch writes all of them, as 24.7's does on
  // the history page.
  const STATE_EVENTS = "events";
  const STATE_LOADING = "loading";
  const STATE_EMPTY = "empty";
  const STATE_ERROR = "error";
  const STATES = [STATE_EVENTS, STATE_LOADING, STATE_EMPTY, STATE_ERROR];

  const LOADING_MESSAGE = "Loading the audit trail.";
  const CELL_CLASS = "ux4g-table-cell-text";

  // The status as a tag: base class, then the variant, then the size, in the
  // order 23.4 and 24.1 write them. `altered` is the only one of the three
  // that is a refusal, so it is the only one taking the error tag; `unknown`
  // is not a clearance, and an answer nothing has checked gets the neutral
  // tag rather than a band of its own.
  const TAG_CLASS = "ux4g-tag";
  const TAG_SIZE_CLASS = "ux4g-tag-s";
  const STATUS_VARIANTS = {
    verified: "ux4g-tag-filled-success",
    altered: "ux4g-tag-filled-error",
    unknown: "ux4g-tag-filled-neutral",
  };

  // The same three words in the officer's own capitals, so the result does
  // not rest on the tag's colour: the word is what a screen reader reads and
  // what a reader in print is left with.
  const STATUS_LABELS = {
    verified: "Verified",
    altered: "Altered",
    unknown: "Unknown",
  };

  // A walk that stopped before it compared anything has no sentence to show,
  // so the cell says so rather than standing empty. 23.10's rule again.
  const NO_CHECKS_LABEL = "No check completed.";

  // The three facts 9.17 sends beside its three answers, and the one label
  // standing for any of them the walk never reached: it sends null rather
  // than a blank, so the cell says so rather than standing empty. The header
  // names which fact is missing and the explanation cell carries the reason,
  // so one label serves all three.
  const ABSENT_LABEL = "Not recorded.";

  const REQUIRED_ELEMENTS = ["body"];

  const ELEMENTS_MESSAGE =
    "The audit event list needs an element to draw into: ";
  const IDS_MESSAGE =
    "The audit view needs a list of event ids to read, even an empty one.";
  const NO_API_MESSAGE =
    "This page cannot reach the API client, so it cannot read the audit trail.";
  const PAYLOAD_MESSAGE =
    "An audit answer must carry an audit_id, a status and the checks that ran.";
  const STATUS_MESSAGE =
    "A verification status is one of " + STATUSES.join(", ") + ".";
  const CHECKS_MESSAGE =
    "The checks that ran must each be a non-empty sentence.";
  const BATCH_MESSAGE =
    "A batch id and a batch root must each be a non-empty string, or null " +
    "where the walk reached none.";
  const PROOF_LENGTH_MESSAGE =
    "A proof length must be a whole number of steps that is not negative, or " +
    "null where the walk built no proof.";

  class AuditViewError extends Error {
    constructor(code, message, cause) {
      super(message);
      this.name = "AuditViewError";
      this.code = code;
      if (cause !== undefined) {
        this.cause = cause;
      }
    }
  }

  // The id goes into a URL, so it is encoded rather than pasted: a value that
  // were not an id must not be able to close the path.
  function verifyPath(id) {
    return VERIFY_ROOT + "/" + encodeURIComponent(id) + VERIFY_SUFFIX;
  }

  // The ids the page was opened with, in the order the link named them. A
  // blank parameter names no record and is dropped rather than read as one.
  function auditIdsFromSearch(search) {
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
      throw new AuditViewError(
        "missing_element",
        ELEMENTS_MESSAGE + name + ".",
      );
    }
    return element;
  }

  function readChecks(value) {
    if (Array.isArray(value) === false) {
      throw new AuditViewError("bad_checks", CHECKS_MESSAGE);
    }
    for (const sentence of value) {
      if (typeof sentence !== "string" || sentence.trim() === "") {
        throw new AuditViewError("bad_checks", CHECKS_MESSAGE);
      }
    }
    return value.slice();
  }

  // One fact of the walk, read as 9.17 sends it: the value itself, or null
  // where the walk reached none. The batch id and the batch root are read
  // apart rather than as a pair, because a row can carry a batch whose entry
  // the log no longer answers for: one and not the other, which the walk
  // reaches and still answers unknown.
  function readFact(value, code, message) {
    if (value === null) {
      return null;
    }
    if (typeof value !== "string" || value.trim() === "") {
      throw new AuditViewError(code, message);
    }
    return value;
  }

  // A proof length counts the siblings the walked path carried, so a whole
  // number from zero up: a batch of one leaf has a path of none, and 0 is
  // that path walked rather than a fact missing.
  function readProofLength(value) {
    if (value === null) {
      return null;
    }
    if (Number.isInteger(value) === false || value < 0) {
      throw new AuditViewError("bad_proof_length", PROOF_LENGTH_MESSAGE);
    }
    return value;
  }

  // Every field is read before anything is drawn, so an answer this page
  // cannot read leaves the list as it stood rather than half replaced.
  function readEvent(payload) {
    if (payload === null || typeof payload !== "object" || Array.isArray(payload)) {
      throw new AuditViewError("bad_event", PAYLOAD_MESSAGE);
    }
    if (typeof payload.audit_id !== "string" || payload.audit_id.trim() === "") {
      throw new AuditViewError("bad_event", PAYLOAD_MESSAGE);
    }
    if (
      typeof payload.status !== "string" ||
      STATUSES.includes(payload.status) === false
    ) {
      throw new AuditViewError("bad_status", STATUS_MESSAGE);
    }
    return {
      id: payload.audit_id,
      status: payload.status,
      checks: readChecks(payload.checked),
      batchId: readFact(payload.batch_id, "bad_batch", BATCH_MESSAGE),
      batchRoot: readFact(payload.batch_root, "bad_batch", BATCH_MESSAGE),
      proofLength: readProofLength(payload.proof_length),
    };
  }

  // hasOwnProperty rather than a lookup: a status named "toString" is not one
  // 9.17 answers with, and an inherited property would answer for it.
  function statusVariant(status) {
    if (
      typeof status !== "string" ||
      Object.prototype.hasOwnProperty.call(STATUS_VARIANTS, status) === false
    ) {
      throw new AuditViewError("bad_status", STATUS_MESSAGE);
    }
    return STATUS_VARIANTS[status];
  }

  function statusLabel(status) {
    if (
      typeof status !== "string" ||
      Object.prototype.hasOwnProperty.call(STATUS_LABELS, status) === false
    ) {
      throw new AuditViewError("bad_status", STATUS_MESSAGE);
    }
    return STATUS_LABELS[status];
  }

  function eventCountText(count) {
    return count === 1 ? "1 recorded event" : count + " recorded events";
  }

  function idCell(event) {
    const cell = document.createElement("td");
    cell.classList.add(CELL_CLASS);
    cell.textContent = event.id;
    return cell;
  }

  // The status as one tag, so three answers cannot be read as three shades of
  // the same thing, and so the word beside the colour carries the meaning.
  function statusCell(event) {
    const cell = document.createElement("td");
    const tag = document.createElement("span");
    tag.classList.add(TAG_CLASS);
    tag.classList.add(TAG_SIZE_CLASS);
    tag.classList.add(statusVariant(event.status));
    tag.setAttribute("data-verification", event.status);
    tag.textContent = statusLabel(event.status);
    cell.appendChild(tag);
    return cell;
  }

  // The plain sentences app/audit/verify.py wrote, one per line, so a reader
  // sees which check stopped the walk and not only how many ran. A walk that
  // completed none says so rather than leaving the cell empty.
  function checksCell(event) {
    const cell = document.createElement("td");
    if (event.checks.length === 0) {
      cell.textContent = NO_CHECKS_LABEL;
      return cell;
    }
    const list = document.createElement("ul");
    for (const sentence of event.checks) {
      const item = document.createElement("li");
      item.textContent = sentence;
      list.appendChild(item);
    }
    cell.appendChild(list);
    return cell;
  }

  // A fact the walk reached, or the one label standing for one it did not, so
  // a cell is never blank and never guesses at what it was not told.
  function factText(value) {
    return value === null ? ABSENT_LABEL : String(value);
  }

  // The batch id, drawn as the event id is: two ids of one width, and 24.8's
  // cell class is what already holds that column on one line.
  function batchCell(event) {
    const cell = document.createElement("td");
    cell.classList.add(CELL_CLASS);
    cell.textContent = factText(event.batchId);
    return cell;
  }

  // The root as the log spells it, whole. No cell class on purpose:
  // ux4g-table-cell-text truncates with an ellipsis, and a root that cannot be
  // read out in full is a commitment nobody can compare against the anchor.
  function rootCell(event) {
    const cell = document.createElement("td");
    cell.textContent = factText(event.batchRoot);
    return cell;
  }

  // The count of steps the walked path carried, as the number the service
  // sent rather than as prose this page invented.
  function proofLengthCell(event) {
    const cell = document.createElement("td");
    cell.textContent = factText(event.proofLength);
    return cell;
  }

  function drawEvent(event) {
    const row = document.createElement("tr");
    row.setAttribute("data-audit-id", event.id);
    row.setAttribute("data-verification", event.status);
    row.appendChild(idCell(event));
    row.appendChild(statusCell(event));
    row.appendChild(batchCell(event));
    row.appendChild(rootCell(event));
    row.appendChild(proofLengthCell(event));
    row.appendChild(checksCell(event));
    return row;
  }

  // bindAuditView wires one event list to the verification route, and draws
  // nothing until a caller calls load() or render().
  function bindAuditView(options) {
    const settings = options || {};
    const body = readElement(settings, "body");
    const table = settings.table ?? null;
    const count = settings.count ?? null;
    const loading = settings.loading ?? null;
    const failure = settings.failure ?? null;
    const failureMessage = settings.failureMessage ?? null;
    const retry = settings.retry ?? null;
    const empty = settings.empty ?? null;
    const ids = settings.ids;
    if (Array.isArray(ids) === false) {
      throw new AuditViewError("missing_ids", IDS_MESSAGE);
    }

    let current = [];
    let lastError = null;
    let shown = STATE_LOADING;

    function clear() {
      while (body.firstChild) {
        body.removeChild(body.firstChild);
      }
      current = [];
      return true;
    }

    // One switch for the three states the list is not in. The list, the
    // skeleton, the alert and the empty panel are switched together, and the
    // container's aria-busy travels with the skeleton.
    function showState(state) {
      if (STATES.includes(state) === false) {
        throw new AuditViewError(
          "bad_state",
          "The audit event list can only be " + STATES.join(", ") + ".",
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
      if (table) {
        table.hidden = state !== STATE_EVENTS;
      }
      if (empty) {
        empty.hidden = state !== STATE_EMPTY;
      }
      shown = state;
      return state;
    }

    // The answers are read whole before anything is drawn, so an answer this
    // page cannot read leaves the list as it stood rather than half replaced.
    function render(answers) {
      const read = (Array.isArray(answers) ? answers : []).map(readEvent);
      clear();
      for (const event of read) {
        body.appendChild(drawEvent(event));
      }
      if (count) {
        count.textContent = read.length === 0 ? "" : eventCountText(read.length);
      }
      showState(read.length === 0 ? STATE_EMPTY : STATE_EVENTS);
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
    // read whole before the first row is drawn.
    async function load() {
      const api = window.DRISHTI_API;
      if (!api || typeof api.request !== "function") {
        throw new AuditViewError("no_api", NO_API_MESSAGE);
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
          const response = await api.request(verifyPath(id));
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
      events: () => current.slice(),
      error: () => lastError,
    };
  }

  function start() {
    const body = document.getElementById("audit-events-body");
    if (!body) {
      return null;
    }
    const view = bindAuditView({
      body: body,
      table: body.closest(".table-scroll"),
      count: document.getElementById("audit-count"),
      loading: document.getElementById("audit-loading"),
      failure: document.getElementById("audit-error"),
      failureMessage: document.getElementById("audit-error-message"),
      retry: document.getElementById("audit-retry"),
      empty: document.getElementById("audit-empty"),
      ids: auditIdsFromSearch(window.location.search),
    });
    view.load();
    return view;
  }

  window.DRISHTI_AUDIT = {
    VERIFY_ROOT,
    VERIFY_SUFFIX,
    ID_PARAM,
    STATUSES,
    STATUS_LABELS,
    STATUS_VARIANTS,
    STATES,
    STATE_EMPTY,
    STATE_ERROR,
    STATE_EVENTS,
    STATE_LOADING,
    LOADING_MESSAGE,
    CELL_CLASS,
    TAG_CLASS,
    TAG_SIZE_CLASS,
    NO_CHECKS_LABEL,
    ABSENT_LABEL,
    REQUIRED_ELEMENTS,
    AuditViewError,
    verifyPath,
    auditIdsFromSearch,
    statusVariant,
    statusLabel,
    eventCountText,
    readFact,
    readProofLength,
    readEvent,
    bindAuditView,
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