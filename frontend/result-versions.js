(() => {
  "use strict";

  // Which versions produced this result: the ruleset that scored it, the
  // models that answered for it and the prompt template its summary came
  // from, under a tag that says the whole block is experimental.

  const CARD_CLASSES = ["ux4g-card", "ux4g-card-body"];
  const HEADING_ROW_CLASSES = ["ux4g-d-flex", "ux4g-gap-s"];
  const TAG_CLASSES = ["ux4g-tag", "ux4g-tag-s", "ux4g-tag-filled-warning"];

  // The sheet's own table, in the composition 2 of Design.md asks for: the
  // base class, the size, and the responsive wrapper for a narrow screen.
  const TABLE_CLASSES = [
    "ux4g-table",
    "ux4g-table-m",
    "ux4g-table-responsive",
  ];
  const CELL_CLASS = "ux4g-table-cell-text";
  const CAPTION_CLASS = "ux4g-sr-only";

  // The words the block says.  The three row labels are the spellings the
  // service already uses (app/schemas.py), and the tag is the one promise
  // app/version.py has made about the UI since before any endpoint existed
  // (D79).
  const HEADING = "Versions";
  const EXPERIMENTAL_LABEL = "Experimental";
  const RULESET_LABEL = "Ruleset version";
  const MODELS_LABEL = "Model versions";
  const PROMPT_LABEL = "Prompt version";
  const CAPTION_TEXT =
    "The ruleset, model and prompt versions this result was produced " +
    "under. Experimental.";
  const MODEL_SEPARATOR = ": ";

  // Nothing was recorded is an answer, not a fault and not a gap to fill: a
  // stored row carries what answered that screening and nothing else (D79),
  // so the block says so rather than quoting a version that did not produce
  // this result.
  const ABSENT_TEXT = "Not recorded";

  const REQUIRED_ELEMENTS = ["container"];

  const CONTAINER_MESSAGE =
    "The version panel needs an element to draw into: ";
  const RULESET_MESSAGE =
    "A ruleset version is a non-empty string, or nothing at all.";
  const MODELS_MESSAGE =
    "Model versions are an object of module name to version string, or " +
    "nothing at all.";
  const PROMPT_MESSAGE =
    "A prompt version is a non-empty string, or nothing at all.";

  class ResultVersionsError extends Error {
    constructor(code, message, cause) {
      super(message);
      this.name = "ResultVersionsError";
      this.code = code;
      if (cause !== undefined) {
        this.cause = cause;
      }
    }
  }

  function readElement(settings, name) {
    const element = settings ? settings[name] : null;
    if (!element) {
      throw new ResultVersionsError(
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

  // Absent is an answer; a value nobody could quote is a fault, refused by
  // name on 23.10 rule: a typo is a fault and an absent value is an answer.
  function readVersion(value, code, message) {
    if (value === null || value === undefined) {
      return null;
    }
    if (typeof value !== "string" || value.trim() === "") {
      throw new ResultVersionsError(code, message);
    }
    return value.trim();
  }

  // Inside a model set an absent version is not an answer: the key names a
  // module and then says nothing about what answered for it, which is a fault
  // rather than a value that was never recorded.
  function readModelVersion(value) {
    if (value === null || value === undefined) {
      throw new ResultVersionsError("bad_model_versions", MODELS_MESSAGE);
    }
    return readVersion(value, "bad_model_versions", MODELS_MESSAGE);
  }

  // The model set is read whole: every module name and every version it
  // carries is checked before the panel is drawn, so a half-read model set
  // never reaches the page.  Object.keys rather than a lookup, so an
  // inherited property is not a model this screening ran.
  function readModels(value) {
    if (value === null || value === undefined) {
      return [];
    }
    if (typeof value !== "object" || Array.isArray(value)) {
      throw new ResultVersionsError("bad_model_versions", MODELS_MESSAGE);
    }
    const models = [];
    for (const name of Object.keys(value)) {
      const version = readModelVersion(value[name]);
      if (name.trim() === "") {
        throw new ResultVersionsError("bad_model_versions", MODELS_MESSAGE);
      }
      models.push({ module: name, version: version });
    }
    // A stored object carries no order of its own, so the panel sorts what it
    // is given: the same model set never reshuffles between two renders.
    models.sort(function (left, right) {
      if (left.module < right.module) {
        return -1;
      }
      return left.module > right.module ? 1 : 0;
    });
    return models;
  }

  function modelLine(model) {
    return model.module + MODEL_SEPARATOR + model.version;
  }

  // The row a reader pairs with the value beside it: the label is a row
  // header, so a screen reader names the version rather than reading three
  // unlabelled cells.
  function drawRow(label, lines) {
    const row = document.createElement("tr");
    const head = document.createElement("th");
    head.setAttribute("scope", "row");
    head.textContent = label;
    const cell = element("td", [CELL_CLASS]);
    for (const line of lines) {
      const text = document.createElement("div");
      text.textContent = line;
      cell.appendChild(text);
    }
    row.appendChild(head);
    row.appendChild(cell);
    return row;
  }

  // bindResultVersions wires the version panel, and draws nothing until a page
  // calls render().
  function bindResultVersions(options) {
    const settings = options || {};
    const container = readElement(settings, "container");

    let card = null;
    let current = null;

    // All three versions are read before anything is written, so a result this
    // page cannot read leaves the panel as it was rather than half replaced.
    // None of them is defaulted from app/version.py: a stored row records what
    // answered that screening, and a constant quoted beside it would claim a
    // ruleset for a row nothing has scored.
    function measure(result) {
      const source =
        result && typeof result === "object" && !Array.isArray(result)
          ? result
          : {};
      return {
        ruleset: readVersion(
          source.ruleset_version,
          "bad_ruleset_version",
          RULESET_MESSAGE,
        ),
        models: readModels(source.model_versions),
        prompt: readVersion(
          source.prompt_version,
          "bad_prompt_version",
          PROMPT_MESSAGE,
        ),
      };
    }

    function render(result) {
      const read = measure(result);
      clear();
      const panel = element("div", CARD_CLASSES);
      const heading = element("div", HEADING_ROW_CLASSES);
      const title = document.createElement("strong");
      title.textContent = HEADING;
      heading.appendChild(title);
      // The tag is warning-toned rather than error-toned: what the versions
      // qualify is advice, not a fault.
      heading.appendChild(element("span", TAG_CLASSES, EXPERIMENTAL_LABEL));
      const table = element("table", TABLE_CLASSES);
      table.appendChild(element("caption", [CAPTION_CLASS], CAPTION_TEXT));
      const body = document.createElement("tbody");
      body.appendChild(
        drawRow(
          RULESET_LABEL,
          read.ruleset === null ? [ABSENT_TEXT] : [read.ruleset],
        ),
      );
      body.appendChild(
        drawRow(
          MODELS_LABEL,
          read.models.length === 0
            ? [ABSENT_TEXT]
            : read.models.map(modelLine),
        ),
      );
      body.appendChild(
        drawRow(
          PROMPT_LABEL,
          read.prompt === null ? [ABSENT_TEXT] : [read.prompt],
        ),
      );
      table.appendChild(body);
      panel.appendChild(heading);
      panel.appendChild(table);
      container.appendChild(panel);
      card = panel;
      current = read;
      return true;
    }

    // Only what this module drew is taken away, so a page own children in the
    // same container are none of this module business.
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
      ruleset: () => (current === null ? null : current.ruleset),
      models: () => (current === null ? [] : current.models.slice()),
      prompt: () => (current === null ? null : current.prompt),
      experimental: () => current !== null,
    };
  }

  window.DRISHTI_RESULT_VERSIONS = {
    ABSENT_TEXT,
    CAPTION_CLASS,
    CAPTION_TEXT,
    CARD_CLASSES,
    CELL_CLASS,
    EXPERIMENTAL_LABEL,
    HEADING,
    HEADING_ROW_CLASSES,
    MODELS_LABEL,
    MODEL_SEPARATOR,
    PROMPT_LABEL,
    REQUIRED_ELEMENTS,
    RULESET_LABEL,
    TABLE_CLASSES,
    TAG_CLASSES,
    ResultVersionsError,
    bindResultVersions,
  };
})();