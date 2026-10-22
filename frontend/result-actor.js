(() => {
  "use strict";

  // Which station this screen is acting for: the configured station label the
  // audit trail stamps its events with, and never a person, a sign-in or a
  // session.  Nothing here is read off a stored result -- the station is a
  // property of where the screen is running, so the page hands it in and
  // this draws it.

  const CARD_CLASSES = ["ux4g-card", "ux4g-card-body"];
  const HEADING_ROW_CLASSES = ["ux4g-d-flex", "ux4g-gap-s"];

  // The sheet's own table, in the composition Design.md asks for: the base
  // class, the size, and the responsive wrapper for a narrow screen.
  const TABLE_CLASSES = [
    "ux4g-table",
    "ux4g-table-m",
    "ux4g-table-responsive",
  ];
  const CELL_CLASS = "ux4g-table-cell-text";
  const CAPTION_CLASS = "ux4g-sr-only";

  // The heading is the field name the trail stores, and the row header is
  // what the value actually is.  The caption says so out loud, because the
  // difference between a station and the officer behind it is the whole
  // point of the block.
  const HEADING = "Actor";
  const STATION_LABEL = "Station";
  const CAPTION_TEXT =
    "The station every event on this screen is recorded under. A station " +
    "label, not a person.";

  const REQUIRED_ELEMENTS = ["container"];

  const CONTAINER_MESSAGE =
    "The actor display needs an element to draw into: ";
  const STATION_MESSAGE =
    "A station label is a non-empty string, or nothing at all.";

  class ResultActorError extends Error {
    constructor(code, message, cause) {
      super(message);
      this.name = "ResultActorError";
      this.code = code;
      if (cause !== undefined) {
        this.cause = cause;
      }
    }
  }

  function readElement(settings, name) {
    const element = settings ? settings[name] : null;
    if (!element) {
      throw new ResultActorError(
        "missing_element",
        CONTAINER_MESSAGE + name + ".",
      );
    }
    return element;
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

  // A station nobody configured is a fault here, not an absence: the build
  // writes the placeholder when no label is set, so a label that does not
  // arrive is a page that passed nothing.  Naming a station in that case
  // would put a post on the record that nobody is standing at.
  function readStation(value) {
    if (typeof value !== "string" || value.trim() === "") {
      throw new ResultActorError("bad_station_label", STATION_MESSAGE);
    }
    return value.trim();
  }

  // bindResultActor wires the display, and draws nothing until a page calls
  // render() with the label it was configured with.
  function bindResultActor(options) {
    const settings = options || {};
    const container = readElement(settings, "container");

    let card = null;
    let current = null;

    function render(stationLabel) {
      const station = readStation(stationLabel);
      clear();
      const panel = element("div", CARD_CLASSES);
      const heading = element("div", HEADING_ROW_CLASSES);
      const title = document.createElement("strong");
      title.textContent = HEADING;
      heading.appendChild(title);
      const table = element("table", TABLE_CLASSES);
      table.appendChild(element("caption", [CAPTION_CLASS], CAPTION_TEXT));
      const body = document.createElement("tbody");
      // The label is a row header, so a screen reader names the station
      // rather than reading one unlabelled cell.
      const row = document.createElement("tr");
      const head = document.createElement("th");
      head.setAttribute("scope", "row");
      head.textContent = STATION_LABEL;
      row.appendChild(head);
      row.appendChild(element("td", [CELL_CLASS], station));
      body.appendChild(row);
      table.appendChild(body);
      panel.appendChild(heading);
      panel.appendChild(table);
      container.appendChild(panel);
      card = panel;
      current = station;
      return true;
    }

    // Only what this module drew is taken away, so a page own children in
    // the same container are none of this module business.
    function clear() {
      const removed = card !== null;
      if (card !== null) {
        container.removeChild(card);
        card = null;
        current = null;
      }
      return removed;
    }

    return {
      render,
      clear,
      actor: () => current,
      rendered: () => current !== null,
    };
  }

  window.DRISHTI_RESULT_ACTOR = {
    CAPTION_CLASS,
    CAPTION_TEXT,
    CARD_CLASSES,
    CELL_CLASS,
    HEADING,
    HEADING_ROW_CLASSES,
    REQUIRED_ELEMENTS,
    STATION_LABEL,
    TABLE_CLASSES,
    ResultActorError,
    bindResultActor,
  };
})();