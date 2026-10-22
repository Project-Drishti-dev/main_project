(() => {
  "use strict";

  // Where the history view's rows come from: one page of
  // `GET /api/screenings`, drawn into the tbody the markup holds.
  // Reads window.DRISHTI_API for the request, window.DRISHTI_FORMAT for the
  // score and window.DRISHTI_DOWNLOAD to save the export. A payload it
  // cannot read is refused by name rather than drawn as half a row.

  const LIST_PATH = "/api/screenings";

  // Where the View action sends an officer: the result view, carrying the
  // screening it is about.
  const RESULT_PAGE = "result.html";

  // What the export writes: the six columns the table shows as data, in the
  // order the page's header cells name them. The seventh column is Actions,
  // and a button is not a value.
  const CSV_COLUMNS = [
    "Screening",
    "Document",
    "Checked",
    "Mode",
    "Score",
    "Result",
  ];
  const EXPORT_NAME = "drishti-screenings.csv";
  const EXPORT_TYPE = "text/csv;charset=utf-8";

  // One event a redraw announces, so the page can re-apply the filter it owns
  // over rows this module has just replaced.
  const REDRAWN_EVENT = "drishti:screenings-changed";

  // The three states the table is not in, and the state it is in when the
  // answer carries rows. One switch writes all of them, so the page cannot be
  // left showing a skeleton and an empty state at the same time.
  const STATE_ROWS = "rows";
  const STATE_LOADING = "loading";
  const STATE_EMPTY = "empty";
  const STATE_ERROR = "error";
  const STATES = [STATE_ROWS, STATE_LOADING, STATE_EMPTY, STATE_ERROR];

  // What the polite count line says while the answer is still in flight. The
  // sample count in the markup is a lie until the first read replaces it.
  const LOADING_MESSAGE = "Loading the screening history.";

  const STATUSES = ["pending", "completed", "failed"];

  // One variant per band app/risk/bands.py bands in, in the order of rising
  // risk. The same three names result-band.js and format.js label.
  const BAND_VARIANTS = {
    low: "ux4g-tag-filled-success",
    review: "ux4g-tag-filled-warning",
    high: "ux4g-tag-filled-error",
  };

  // The values the band filter answers to: the three bands the engine bands
  // in, plus the All chip. A row nothing scored is filed under neither, so
  // only All can show it.
  const ALL_FILTER = "all";
  const UNSCORED_FILTER = "not-scored";
  const BAND_FILTERS = Object.keys(BAND_VARIANTS);

  const UNSCORED_LABEL = "Not scored";
  const NOT_RECORDED = "Not recorded";

  const REQUIRED_ELEMENTS = ["body"];

  // The controls the confirmation can hold focus on. Read off the dialog as
  // a key is pressed rather than listed here, so a control added to the
  // markup is inside the trap without a second edit.
  const FOCUSABLE_SELECTOR =
    'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])';

  // The stored instant is UTC and the `datetime` attribute carries it whole;
  // the text beside it is the reader's own clock, so the two can disagree and
  // that is correct. Pinned to en-GB and h23 so the text is not left to a
  // machine's locale.
  const TIME_FORMAT = new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });

  const ELEMENTS_MESSAGE =
    "The history table needs an element to draw into: ";
  const NO_API_MESSAGE =
    "This page cannot reach the API client, so it cannot read the history.";
  const NO_FORMAT_MESSAGE =
    "This page cannot reach the formatter, so it cannot draw a score.";
  const PAYLOAD_MESSAGE =
    "The history answer must carry an items array and a total.";
  const ITEM_MESSAGE =
    "A history row must carry a screening_id, a status and a created_at.";
  const NO_CONFIRM_MESSAGE =
    "This page has no delete confirmation to show, so nothing was deleted.";
  const NO_DOWNLOAD_MESSAGE =
    "This page cannot save a file, so nothing was exported.";
  const BAND_MESSAGE =
    "A band is one of the three the engine bands in: " +
    Object.keys(BAND_VARIANTS).join(", ") +
    ".";

  class ScreeningsListError extends Error {
    constructor(code, message, cause) {
      super(message);
      this.name = "ScreeningsListError";
      this.code = code;
      if (cause !== undefined) {
        this.cause = cause;
      }
    }
  }

  // Both ids go into a URL, so both are encoded rather than pasted: a value
  // that were not an id must not be able to close the path or the query
  // string and carry parameters of its own.
  function viewHref(id) {
    return RESULT_PAGE + "?id=" + encodeURIComponent(id);
  }

  function deletePath(id) {
    return LIST_PATH + "/" + encodeURIComponent(id);
  }

  function readElement(settings, name) {
    const element = settings ? settings[name] : null;
    if (!element) {
      throw new ScreeningsListError(
        "missing_element",
        ELEMENTS_MESSAGE + name + ".",
      );
    }
    return element;
  }

  // hasOwnProperty rather than a lookup: a band named "toString" is a band
  // the engine never bands in, and an inherited property would answer for it.
  function bandVariant(band) {
    if (
      typeof band !== "string" ||
      Object.prototype.hasOwnProperty.call(BAND_VARIANTS, band) === false
    ) {
      throw new ScreeningsListError("bad_band", BAND_MESSAGE);
    }
    return BAND_VARIANTS[band];
  }

  function filterValue(band) {
    return band === null ? UNSCORED_FILTER : band;
  }

  function readInstant(value, format) {
    try {
      return new Date(format.parseInstant(value));
    } catch (error) {
      throw new ScreeningsListError("bad_timestamp", ITEM_MESSAGE, error);
    }
  }

  // Both halves of a row are read before anything is drawn, so a row this
  // page cannot read leaves the table as it stood rather than half replaced.
  function readRow(item, format) {
    if (
      item === null ||
      typeof item !== "object" ||
      typeof item.screening_id !== "string" ||
      item.screening_id.trim() === "" ||
      typeof item.status !== "string" ||
      STATUSES.includes(item.status) === false ||
      typeof item.document_type !== "string"
    ) {
      throw new ScreeningsListError("bad_item", ITEM_MESSAGE);
    }
    const instant = readInstant(item.created_at, format);
    const band = item.band === undefined ? null : item.band;
    let variant = null;
    let label = null;
    if (band !== null) {
      variant = bandVariant(band);
      label = format.bandLabel(band);
    }
    let score = null;
    if (item.score !== null && item.score !== undefined) {
      try {
        score = format.formatScore(item.score);
      } catch (error) {
        throw new ScreeningsListError("bad_score", ITEM_MESSAGE, error);
      }
    }
    return {
      id: item.screening_id,
      status: item.status,
      documentType: item.document_type,
      datetime: instant.toISOString(),
      when: TIME_FORMAT.format(instant),
      band: band,
      variant: variant,
      label: label,
      score: score,
      filter: filterValue(band),
    };
  }

  function readPayload(payload, format) {
    if (
      payload === null ||
      typeof payload !== "object" ||
      Array.isArray(payload.items) === false ||
      typeof payload.total !== "number" ||
      Number.isFinite(payload.total) === false ||
      payload.total < 0
    ) {
      throw new ScreeningsListError("bad_payload", PAYLOAD_MESSAGE);
    }
    return {
      rows: payload.items.map((item) => readRow(item, format)),
      total: payload.total,
    };
  }

  function textCell(text) {
    const cell = document.createElement("td");
    cell.textContent = text;
    return cell;
  }

  function idCell(row) {
    const cell = document.createElement("td");
    cell.classList.add("ux4g-table-cell-text");
    const primary = document.createElement("span");
    primary.classList.add("cell-primary");
    const strong = document.createElement("strong");
    strong.textContent = row.id;
    const small = document.createElement("small");
    small.textContent = row.status;
    primary.appendChild(strong);
    primary.appendChild(small);
    cell.appendChild(primary);
    return cell;
  }

  function checkedCell(row) {
    const cell = document.createElement("td");
    const time = document.createElement("time");
    time.setAttribute("datetime", row.datetime);
    time.textContent = row.when;
    cell.appendChild(time);
    return cell;
  }

  function resultCell(row) {
    const cell = document.createElement("td");
    const tag = document.createElement("span");
    tag.classList.add("ux4g-tag");
    tag.classList.add("ux4g-tag-s");
    if (row.variant === null) {
      tag.classList.add("ux4g-tag-filled-neutral");
      tag.textContent = UNSCORED_LABEL;
    } else {
      tag.classList.add(row.variant);
      tag.textContent = row.label;
    }
    cell.appendChild(tag);
    return cell;
  }

  // View navigates, so it is a link and needs nothing from this module to
  // work. Delete changes something a server holds, so it is a button and goes
  // through the confirmation before anything is sent.
  function viewLink(row) {
    const link = document.createElement("a");
    link.classList.add("ux4g-btn");
    link.classList.add("ux4g-btn-text-primary");
    link.classList.add("ux4g-btn-sm");
    link.setAttribute("data-row-action", "view");
    link.setAttribute("data-row-id", row.id);
    link.setAttribute("href", viewHref(row.id));
    link.setAttribute("aria-label", "View screening " + row.id);
    link.textContent = "View";
    return link;
  }

  function deleteButton(row) {
    const button = document.createElement("button");
    button.classList.add("ux4g-btn");
    button.classList.add("ux4g-btn-text-primary");
    button.classList.add("ux4g-btn-sm");
    button.setAttribute("type", "button");
    button.setAttribute("data-row-action", "delete");
    button.setAttribute("data-row-id", row.id);
    button.setAttribute("aria-label", "Delete screening " + row.id);
    button.textContent = "Delete";
    return button;
  }

  function actionsCell(row) {
    const cell = document.createElement("td");
    const actions = document.createElement("div");
    actions.classList.add("cell-actions");
    actions.appendChild(viewLink(row));
    actions.appendChild(deleteButton(row));
    cell.appendChild(actions);
    return cell;
  }

  function drawRow(row) {
    const tr = document.createElement("tr");
    tr.setAttribute("data-result", row.filter);
    tr.setAttribute(
      "data-search",
      (row.id + " " + row.documentType).toLowerCase(),
    );
    tr.appendChild(idCell(row));
    tr.appendChild(textCell(row.documentType));
    tr.appendChild(checkedCell(row));
    tr.appendChild(textCell(NOT_RECORDED));
    tr.appendChild(textCell(row.score === null ? NOT_RECORDED : row.score));
    tr.appendChild(resultCell(row));
    tr.appendChild(actionsCell(row));
    return tr;
  }

  // A CSV field is quoted and an inner quote is doubled, so a value carrying
  // a comma or a quote cannot open a column or end the row early.
  function csvField(value) {
    return '"' + String(value).replace(/"/g, '""') + '"';
  }

  // The Screening cell draws the id and the status as two lines. A CSV row is
  // one line, so they travel as one field, id then status, rather than as the
  // run-together string the cell's own text would give.
  function screeningField(cell) {
    const [id, status] = Array.from(cell.children[0]?.children ?? []);
    return [id?.textContent ?? "", status?.textContent ?? ""]
      .map((part) => part.trim())
      .filter((part) => part !== "")
      .join(" ");
  }

  // The values of a drawn row, in the order CSV_COLUMNS names them.
  function rowFields(row) {
    return Array.from(row.children)
      .slice(0, CSV_COLUMNS.length)
      .map((cell, index) =>
        index === 0 ? screeningField(cell) : cell.textContent.trim(),
      );
  }

  // bindScreeningsList wires one table to the history route, and draws
  // nothing until a caller calls load() or render().
  function bindScreeningsList(options) {
    const settings = options || {};
    const body = readElement(settings, "body");
    const count = settings.count ?? null;
    const loading = settings.loading ?? null;
    const failure = settings.failure ?? null;
    const failureMessage = settings.failureMessage ?? null;
    const retry = settings.retry ?? null;
    const empty = settings.empty ?? null;
    const scroll = settings.scroll ?? null;
    const total = settings.total ?? null;
    const notice = settings.notice ?? null;
    const confirm = settings.confirm ?? null;
    const confirmId = settings.confirmId ?? null;
    const confirmOk = settings.confirmOk ?? null;
    const confirmCancel = settings.confirmCancel ?? null;
    const exportButton = settings.export ?? null;
    const format = window.DRISHTI_FORMAT;
    if (
      !format ||
      typeof format.bandLabel !== "function" ||
      typeof format.formatScore !== "function" ||
      typeof format.parseInstant !== "function"
    ) {
      throw new ScreeningsListError("no_format", NO_FORMAT_MESSAGE);
    }

    let current = null;
    let lastError = null;
    let pendingDelete = null;
    let pendingTrigger = null;
    let shown = STATE_LOADING;
    function report(message) {
      if (notice) {
        notice.textContent = message;
      }
    }

    function clear() {
      while (body.firstChild) {
        body.removeChild(body.firstChild);
      }
      current = null;
      return true;
    }

    // One switch for the three states the table is not in. The table, the
    // skeleton, the alert and the empty panel are switched together, and the
    // container's aria-busy travels with the skeleton, so what a screen reader
    // is told and what an officer can see are written by the same call.
    function showState(state) {
      if (STATES.includes(state) === false) {
        throw new ScreeningsListError(
          "bad_state",
          "The history table can only be " + STATES.join(", ") + ".",
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
      if (scroll) {
        scroll.hidden = state !== STATE_ROWS;
      }
      if (empty) {
        empty.hidden = state !== STATE_EMPTY;
      }
      shown = state;
      return state;
    }

    function render(payload) {
      const page = readPayload(payload, format);
      clear();
      for (const row of page.rows) {
        body.appendChild(drawRow(row));
      }
      if (count) {
        count.textContent =
          "Showing " + page.rows.length + " of " + page.total + " screenings";
      }
      if (total) {
        total.textContent = String(page.total);
      }
      showState(page.rows.length === 0 ? STATE_EMPTY : STATE_ROWS);
      current = page;
      document.dispatchEvent(new Event(REDRAWN_EVENT));
      return page;
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

    // The page hides the rows its filter excludes, so a row it left visible
    // is a row the officer can see and a row the file carries. The filter is
    // not decided a second time here: a copy of it could disagree with the
    // table and write rows the officer cannot see.
    function visibleRows() {
      return Array.from(body.children).filter((row) => row.hidden !== true);
    }

    // The file itself: the column names, then one quoted line per visible
    // row, in the order the table holds them, so the sort the page applied
    // is the order the rows arrive in.
    function csvText() {
      const lines = [CSV_COLUMNS, ...visibleRows().map(rowFields)];
      const text = lines.map((line) => line.map(csvField).join(","));
      return text.join("\r\n") + "\r\n";
    }

    function exportCsv() {
      const download = window.DRISHTI_DOWNLOAD;
      if (typeof download !== "function") {
        lastError = new ScreeningsListError("no_download", NO_DOWNLOAD_MESSAGE);
        report(NO_DOWNLOAD_MESSAGE);
        return null;
      }
      const contents = csvText();
      download(EXPORT_NAME, contents, EXPORT_TYPE);
      return contents;
    }

    // The delete takes a second press, and that press names the row it is
    // about: a confirmation that does not say which row cannot be a
    // confirmation of anything.
    // Tab from the last control returns to the first and Shift+Tab from the
    // first returns to the last, so focus cannot walk out of the open dialog
    // and leave the officer tabbing through the table behind it.
    function trapTabKey(dialog, event) {
      const focusable = Array.from(
        dialog.querySelectorAll(FOCUSABLE_SELECTOR),
      ).filter(
        (element) =>
          !element.closest("[hidden]") &&
          element.getAttribute("aria-hidden") !== "true",
      );

      if (focusable.length === 0) {
        event.preventDefault();
        dialog.focus();
        return;
      }

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    // Closing the dialog, leaving focus where it was. The two ways out --
    // the confirming press and backing out -- differ only in what happens
    // to focus, so the switch itself is written once.
    function closeConfirm() {
      pendingDelete = null;
      if (confirm) {
        confirm.classList.remove("is-open");
      }
    }

    // Backing out hands focus back to the Delete that asked, so the next
    // Tab is where the officer left off rather than the top of the page.
    function cancelDelete() {
      closeConfirm();
      const trigger = pendingTrigger;
      pendingTrigger = null;
      if (trigger && trigger.isConnected) {
        trigger.focus();
      }
    }

    function requestDelete(id, trigger = null) {
      if (confirm === null || confirmOk === null) {
        lastError = new ScreeningsListError("no_confirm", NO_CONFIRM_MESSAGE);
        report(NO_CONFIRM_MESSAGE);
        return false;
      }
      pendingDelete = id;
      pendingTrigger = trigger ?? document.activeElement ?? null;
      if (confirmId) {
        confirmId.textContent = id;
      }
      confirm.classList.add("is-open");
      confirmOk.focus();
      return true;
    }

    // The list is re-read rather than patched out of the table. The repository
    // refuses a deleted row to every read, so the answer is the only thing
    // that can say what the history holds, and a count guessed here would be a
    // number about this page rather than about the station.
    async function confirmDelete() {
      const id = pendingDelete;
      if (id === null) {
        return null;
      }
      closeConfirm();
      pendingTrigger = null;
      const api = window.DRISHTI_API;
      if (!api || typeof api.request !== "function") {
        lastError = new ScreeningsListError("no_api", NO_API_MESSAGE);
        report(NO_API_MESSAGE);
        return null;
      }
      try {
        await api.request(deletePath(id), { method: "DELETE" });
      } catch (error) {
        lastError = error;
        report(error.message);
        return null;
      }
      report(id + " deleted.");
      return load();
    }

    body.addEventListener("click", (event) => {
      const trigger = event.target?.closest?.("[data-row-action]");
      if (trigger?.dataset.rowAction !== "delete") {
        return;
      }
      requestDelete(trigger.dataset.rowId, trigger);
    });

    if (confirmOk) {
      confirmOk.addEventListener("click", confirmDelete);
    }
    if (confirmCancel) {
      confirmCancel.addEventListener("click", cancelDelete);
    }

    // Both keys are answered on the dialog itself: the trap keeps focus
    // inside it, so a document listener would only be a wider target for
    // the same keys.
    if (confirm) {
      confirm.addEventListener("keydown", (event) => {
        if (event.key === "Tab") {
          trapTabKey(confirm, event);
        } else if (event.key === "Escape") {
          event.preventDefault();
          cancelDelete();
        }
      });
    }

    if (exportButton) {
      exportButton.addEventListener("click", exportCsv);
    }

    // The alert's own way out: one press reads the route again, which puts
    // the skeleton back for as long as that read takes.
    if (retry) {
      retry.addEventListener("click", load);
    }

    // A failure is stored and shown in the alert rather than thrown at the
    // caller: an unhandled rejection would leave the page on the skeleton
    // with nothing to say, which is the one answer that is worse than both.
    async function load() {
      const api = window.DRISHTI_API;
      if (!api || typeof api.request !== "function") {
        throw new ScreeningsListError("no_api", NO_API_MESSAGE);
      }
      showState(STATE_LOADING);
      if (count) {
        count.textContent = LOADING_MESSAGE;
      }
      try {
        const response = await api.request(LIST_PATH);
        return render(await response.json());
      } catch (error) {
        return fail(error);
      }
    }

    return {
      render,
      clear,
      load,
      requestDelete,
      cancelDelete,
      closeConfirm,
      confirmDelete,
      visibleRows,
      csvText,
      exportCsv,
      showState,
      state: () => shown,
      page: () => current,
      error: () => lastError,
    };
  }

  function start() {
    const body = document.getElementById("screenings-body");
    if (!body) {
      return null;
    }
    const list = bindScreeningsList({
      body: body,
      count: document.getElementById("result-count"),
      loading: document.getElementById("screenings-loading"),
      empty: document.getElementById("screenings-empty"),
      failure: document.getElementById("screenings-error"),
      failureMessage: document.getElementById("screenings-error-message"),
      retry: document.getElementById("screenings-retry"),
      scroll: body.closest(".table-scroll"),
      total: document.querySelector('[data-stat="total"]'),
      notice: document.getElementById("screenings-notice"),
      confirm: document.getElementById("delete-confirm"),
      confirmId: document.getElementById("delete-confirm-id"),
      confirmOk: document.getElementById("delete-confirm-button"),
      confirmCancel: document.getElementById("delete-cancel"),
      export: document.getElementById("export-screenings"),
    });
    list.load();
    return list;
  }

  window.DRISHTI_SCREENINGS_LIST = {
    LIST_PATH,
    RESULT_PAGE,
    CSV_COLUMNS,
    EXPORT_NAME,
    EXPORT_TYPE,
    REDRAWN_EVENT,
    LOADING_MESSAGE,
    STATES,
    STATE_EMPTY,
    STATE_ERROR,
    STATE_LOADING,
    STATE_ROWS,
    ALL_FILTER,
    BAND_FILTERS,
    BAND_VARIANTS,
    STATUSES,
    UNSCORED_FILTER,
    REQUIRED_ELEMENTS,
    ScreeningsListError,
    bandVariant,
    viewHref,
    deletePath,
    bindScreeningsList,
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