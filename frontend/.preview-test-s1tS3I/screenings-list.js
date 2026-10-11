(() => {
  "use strict";

  // Where the history view's rows come from: one page of
  // `GET /api/screenings`, drawn into the tbody the markup holds.
  // Reads window.DRISHTI_API for the request and window.DRISHTI_FORMAT for
  // the score. A payload it cannot read is refused by name rather than
  // drawn as half a row.

  const LIST_PATH = "/api/screenings";

  const STATUSES = ["pending", "completed", "failed"];

  // One variant per band app/risk/bands.py bands in, in the order of rising
  // risk. The same three names result-band.js and format.js label.
  const BAND_VARIANTS = {
    low: "ux4g-tag-filled-success",
    review: "ux4g-tag-filled-warning",
    high: "ux4g-tag-filled-error",
  };

  // The band a "Passed" chip means, until 24.4 replaces the chips with the
  // real band values. `null` is neither: an unscored row is shown by the All
  // chip alone rather than filed under a verdict nothing gave it.
  const PASS_BAND = "low";
  const PASS_FILTER = "pass";
  const ATTENTION_FILTER = "attention";
  const ALL_FILTER = "all";

  const UNSCORED_LABEL = "Not scored";
  const NOT_RECORDED = "Not recorded";

  const REQUIRED_ELEMENTS = ["body"];

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
    if (band === null) {
      return ALL_FILTER;
    }
    return band === PASS_BAND ? PASS_FILTER : ATTENTION_FILTER;
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

  function actionButton(action, id, label) {
    const button = document.createElement("button");
    button.classList.add("ux4g-btn");
    button.classList.add("ux4g-btn-text-primary");
    button.classList.add("ux4g-btn-sm");
    button.setAttribute("type", "button");
    button.setAttribute("data-row-action", action);
    button.textContent = label;
    const hidden = document.createElement("span");
    hidden.classList.add("visually-hidden");
    hidden.textContent = id;
    button.appendChild(hidden);
    return button;
  }

  function actionsCell(row) {
    const cell = document.createElement("td");
    const actions = document.createElement("div");
    actions.classList.add("cell-actions");
    actions.appendChild(actionButton("view", row.id, "View"));
    actions.appendChild(actionButton("delete", row.id, "Delete"));
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

  // bindScreeningsList wires one table to the history route, and draws
  // nothing until a caller calls load() or render().
  function bindScreeningsList(options) {
    const settings = options || {};
    const body = readElement(settings, "body");
    const count = settings.count ?? null;
    const empty = settings.empty ?? null;
    const scroll = settings.scroll ?? null;
    const total = settings.total ?? null;
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

    function clear() {
      while (body.firstChild) {
        body.removeChild(body.firstChild);
      }
      current = null;
      return true;
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
      if (scroll) {
        scroll.hidden = page.rows.length === 0;
      }
      if (empty) {
        empty.hidden = page.rows.length !== 0;
      }
      current = page;
      return page;
    }

    // A failure is stored rather than thrown at the caller: the page has no
    // error state to show one in until 24.7 adds it, and an unhandled
    // rejection would be the worse of the two.
    async function load() {
      const api = window.DRISHTI_API;
      if (!api || typeof api.request !== "function") {
        throw new ScreeningsListError("no_api", NO_API_MESSAGE);
      }
      try {
        const response = await api.request(LIST_PATH);
        return render(await response.json());
      } catch (error) {
        lastError = error;
        return null;
      }
    }

    return {
      render,
      clear,
      load,
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
      empty: document.getElementById("screenings-empty"),
      scroll: body.closest(".table-scroll"),
      total: document.querySelector('[data-stat="total"]'),
    });
    list.load();
    return list;
  }

  window.DRISHTI_SCREENINGS_LIST = {
    LIST_PATH,
    BAND_VARIANTS,
    STATUSES,
    REQUIRED_ELEMENTS,
    ScreeningsListError,
    bandVariant,
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