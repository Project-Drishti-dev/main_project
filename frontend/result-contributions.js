(() => {
  "use strict";

  // How a score was reached: one row per finding, its weight, its value and
  // the product of the two, and the total those products add up to.

  // The sheet's own table, in the composition 2 of Design.md asks for: the
  // base class, the size, and the responsive wrapper for a narrow screen.
  const TABLE_CLASSES = [
    "ux4g-table",
    "ux4g-table-m",
    "ux4g-table-responsive",
  ];
  const CELL_CLASS = "ux4g-table-cell-text";
  const CAPTION_CLASS = "ux4g-sr-only";

  // The four columns, in the order the rows use them. "Weight" and "Value"
  // are the report's own two words (app/reporting.py), so a screen and a
  // printout of one screening call the same number the same thing.
  const HEADINGS = ["Finding", "Weight", "Value", "Contribution"];
  const TOTAL_LABEL = "Total";
  const CAPTION_TEXT =
    "Each finding's weight times its value, and their total";

  // A weight is points on the 0-100 score and a value is in [0, 1], so two
  // decimals carries both closely enough for an officer to add the column up
  // by hand. The total is the sum of the numbers as shown, not of the exact
  // products, so the rows visibly reach the number beside them.
  const DECIMALS = 2;

  const REQUIRED_ELEMENTS = ["container"];

  const CONTAINER_MESSAGE =
    "The contribution panel needs an element to draw into: ";
  const TERMS_MESSAGE =
    "The contributions to break down must be a list, so every row comes " +
    "from one.";
  const TERM_MESSAGE =
    "A contribution must carry a non-empty id, and a weight, a value and a " +
    "contribution that are each a finite number.";
  const NUMBER_MESSAGE =
    "A weight, a value and a contribution must each be a finite number.";

  class ContributionsError extends Error {
    constructor(code, message) {
      super(message);
      this.name = "ContributionsError";
      this.code = code;
    }
  }

  function readElement(settings, name) {
    const element = settings ? settings[name] : null;
    if (!element) {
      throw new ContributionsError(
        "missing_element",
        CONTAINER_MESSAGE + name + ".",
      );
    }
    return element;
  }

  function readNumber(term, name) {
    const value = term[name];
    if (typeof value !== "number" || !Number.isFinite(value)) {
      throw new ContributionsError("bad_number", NUMBER_MESSAGE);
    }
    return value;
  }

  // One term, read whole: the row is either a finding with its numbers beside
  // it or it is refused, never drawn with a cell missing.
  function readTerm(term) {
    if (typeof term !== "object" || term === null || Array.isArray(term)) {
      throw new ContributionsError("bad_term", TERM_MESSAGE);
    }
    if (typeof term.id !== "string" || term.id === "") {
      throw new ContributionsError("bad_term", TERM_MESSAGE);
    }
    return {
      id: term.id,
      weight: readNumber(term, "weight"),
      value: readNumber(term, "value"),
      contribution: readNumber(term, "contribution"),
    };
  }

  // The number as it is shown, which is the one place a rounding decision is
  // made.
  function shown(value) {
    return value.toFixed(DECIMALS);
  }

  function element(tagName, classNames, text) {
    const node = document.createElement(tagName);
    for (const name of classNames) {
      node.classList.add(name);
    }
    if (text !== undefined) {
      node.textContent = text;
    }
    return node;
  }

  function cell(tagName, text) {
    return element(tagName, [CELL_CLASS], text);
  }

  // Every term is read, and the total is worked out, before the first element
  // is written: a result this page cannot read leaves the table as it was
  // rather than half replaced by rows that stop mid-cascade (D6's rule).
  function measure(contributions) {
    if (!Array.isArray(contributions)) {
      throw new ContributionsError("bad_contributions", TERMS_MESSAGE);
    }
    const terms = contributions.map(readTerm);
    let total = 0;
    for (const term of terms) {
      total += Number(shown(term.contribution));
    }
    return { terms: terms, total: shown(total), rows: terms.length };
  }

  function drawHead() {
    const caption = element("caption", [CAPTION_CLASS], CAPTION_TEXT);
    const head = element("thead", []);
    const row = element("tr", []);
    for (const heading of HEADINGS) {
      row.appendChild(cell("th", heading));
    }
    head.appendChild(row);
    return [caption, head];
  }

  // The row a reader adds up to. Its label is a row header, so a screen
  // reader names the number it belongs to rather than reading four cells.
  function drawTotal(total) {
    const row = element("tr", []);
    row.appendChild(element("th", [], TOTAL_LABEL));
    row.appendChild(cell("td", ""));
    row.appendChild(cell("td", ""));
    row.appendChild(cell("td", total));
    return row;
  }

  // bindContributions wires the breakdown panel, and draws nothing until a
  // page calls render().
  function bindContributions(options) {
    const settings = options || {};
    const container = readElement(settings, "container");

    let drawn = [];
    let current = null;

    // A document on which nothing fired sends an empty list, and the backend
    // holds that an answer summing to 0.0 rather than a missing breakdown
    // (app/risk/scoring.py), so the table is drawn with its total and no
    // rows: the panel never prints a "no data" sentence the record did not
    // make.
    function render(contributions) {
      const read = measure(contributions);
      clear();
      const table = element("table", TABLE_CLASSES);
      for (const node of drawHead()) {
        table.appendChild(node);
      }
      const body = element("tbody", []);
      for (const term of read.terms) {
        const row = element("tr", []);
        row.appendChild(cell("td", term.id));
        row.appendChild(cell("td", shown(term.weight)));
        row.appendChild(cell("td", shown(term.value)));
        row.appendChild(cell("td", shown(term.contribution)));
        body.appendChild(row);
      }
      const last = element("tfoot", []);
      last.appendChild(drawTotal(read.total));
      table.appendChild(body);
      table.appendChild(last);
      container.appendChild(table);
      drawn.push(table);
      current = read;
      return read.rows;
    }

    // Only what this module drew is taken away, so a page's own children in
    // the same container are none of this module's business.
    function clear() {
      const removed = drawn.length > 0;
      for (const node of drawn) {
        container.removeChild(node);
      }
      drawn = [];
      current = null;
      return removed;
    }

    function ids() {
      if (current === null) {
        return [];
      }
      const found = [];
      for (const term of current.terms) {
        found.push(term.id);
      }
      return found;
    }

    return {
      render,
      clear,
      ids,
      rows: () => (current === null ? 0 : current.rows),
      total: () => (current === null ? null : current.total),
      empty: () => current !== null && current.rows === 0,
    };
  }

  window.DRISHTI_CONTRIBUTIONS = {
    TABLE_CLASSES,
    CELL_CLASS,
    CAPTION_CLASS,
    HEADINGS,
    TOTAL_LABEL,
    CAPTION_TEXT,
    DECIMALS,
    REQUIRED_ELEMENTS,
    ContributionsError,
    bindContributions,
  };
})();