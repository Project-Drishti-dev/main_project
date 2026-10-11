(() => {
  "use strict";

  // The findings behind a screened document: one row per flag, grouped by the
  // stage that made it, and every field an officer needs to judge it.

  const LIST_CLASSES = ["ux4g-list", "ux4g-list-default", "ux4g-list-m"];
  const ITEM_CLASS = "ux4g-list-item";
  const ROW_CLASS = "ux4g-list-item-row";

  // ux4g-list-item-row is drawn as something to click, and no row on this page
  // is a control yet, so the sheet's own answer for a static row is used.
  const ROW_FIXED_CLASS = "ux4g-list-item-row-fixed";
  const START_CLASS = "ux4g-list-item-start";
  const END_CLASS = "ux4g-list-item-end";
  const STACK_CLASSES = ["ux4g-d-flex", "ux4g-flex-column", "ux4g-gap-y-2xs"];
  const MUTED_CLASS = "ux4g-text-neutral-secondary";
  const GROUP_CLASSES = [
    "ux4g-divider-horizontal",
    "ux4g-divider-horizontal-text",
  ];
  const GROUP_LABEL_CLASS = "ux4g-divider-label";
  const EMPTY_CLASS = "ux4g-empty-state";
  const EMPTY_CONTENT_CLASS = "ux4g-empty-state-content";

  // The sheet has no class for a row of its own, so one class of the project's
  // own: the hook for the pages.css rule G9 already owes.
  const ROW_OWN_CLASS = "result-flag-row";

  // The cascade's own order and the only five tiers a flag may carry: the
  // capture gate runs before tier 0.
  const TIER_ORDER = ["quality", 0, 1, 2, "crossdoc"];
  const TIER_LABELS = {
    quality: "Capture quality",
    0: "Tier 0",
    1: "Tier 1",
    2: "Tier 2",
    crossdoc: "Cross-document",
  };

  // The three bands a weight may sit in. The weightset's number for a band is
  // deliberately not held on a flag, so a row shows the band and never a
  // weight this page would have to invent.
  const WEIGHT_BANDS = ["low", "review", "high"];

  // The printable report's own wording, so a screen and a printout of one
  // screening call the same field the same thing.
  const WEIGHT_LABEL = "Weight band: ";
  const CONFIDENCE_LABEL = "Confidence: ";
  const EXPECTED_LABEL = "Expected: ";
  const FOUND_LABEL = "Found: ";
  const NOT_RECORDED = "not recorded";
  // The word for a finding that carries no region: it is still a finding, and
  // the note says why no highlight points at it.
  const NOT_LOCATABLE = "Not locatable on this document.";
  const NO_FINDINGS = "No findings were recorded for this screening.";

  const REQUIRED_ELEMENTS = ["container"];

  const CONTAINER_MESSAGE = "The flag list needs an element to draw into: ";
  const FLAGS_MESSAGE =
    "The findings to list must be a list, so every row comes from one.";
  const FLAG_MESSAGE =
    "A finding must carry a non-empty id, label and reason, and an expected " +
    "and a found that are each text or null.";
  const TIER_MESSAGE =
    "A tier is one of the five the cascade runs: quality, 0, 1, 2, crossdoc.";
  const WEIGHT_MESSAGE =
    "A weight band is one of the three a weight may sit in: " +
    WEIGHT_BANDS.join(", ") +
    ".";
  const CONFIDENCE_MESSAGE = "A confidence must be a number between 0 and 1.";
  const REGION_MESSAGE =
    "A region must be left out or null, or be the box or polygon overlay.js " +
    "draws: a finding that names anywhere else is a caller bug.";

  class FlagListError extends Error {
    constructor(code, message) {
      super(message);
      this.name = "FlagListError";
      this.code = code;
    }
  }

  function readElement(settings, name) {
    const element = settings ? settings[name] : null;
    if (!element) {
      throw new FlagListError(
        "missing_element",
        CONTAINER_MESSAGE + name + ".",
      );
    }
    return element;
  }

  function readText(flag, name) {
    const value = flag[name];
    if (typeof value !== "string" || value === "") {
      throw new FlagListError("bad_flag", FLAG_MESSAGE);
    }
    return value;
  }

  // null is the record for a half of the comparison nothing wrote, and the
  // word for it is the report's own rather than an empty cell.
  function readHalf(flag, name) {
    const value = flag[name];
    if (value === null) {
      return NOT_RECORDED;
    }
    if (typeof value !== "string" || value === "") {
      throw new FlagListError("bad_flag", FLAG_MESSAGE);
    }
    return value;
  }

  // indexOf rather than a lookup: a tier of "0" is a name the engine never
  // bands in, and strict equality is what refuses it (D177's rule).
  function readTier(flag) {
    const tier = flag.tier;
    if (TIER_ORDER.indexOf(tier) === -1) {
      throw new FlagListError("bad_tier", TIER_MESSAGE);
    }
    return tier;
  }

  function readWeightBand(flag) {
    const band = flag.weight_band;
    if (WEIGHT_BANDS.indexOf(band) === -1) {
      throw new FlagListError("bad_weight", WEIGHT_MESSAGE);
    }
    return band;
  }

  // Printed as the record carries it: a rounded confidence reads as a
  // different measurement than the one that was taken (D6).
  function readConfidence(flag) {
    const value = flag.confidence;
    if (
      typeof value !== "number" ||
      !Number.isFinite(value) ||
      value < 0 ||
      value > 1
    ) {
      throw new FlagListError("bad_confidence", CONFIDENCE_MESSAGE);
    }
    return String(value);
  }

  // One question and not the geometry: does this finding carry a region at
  // all. The shape of a region is judged by overlay.js (D185), so nothing
  // here reads a corner -- but a region that is neither null nor a shape is
  // refused rather than read as a finding with nowhere to point, which would
  // be a claim about the document the record never made.
  function readRegion(flag) {
    const region = flag.region;
    if (region === null || region === undefined) {
      return false;
    }
    if (Array.isArray(region)) {
      return region.length > 0;
    }
    if (typeof region === "object") {
      return Object.keys(region).length > 0;
    }
    throw new FlagListError("bad_region", REGION_MESSAGE);
  }

  // The whole record, read once: a row this page cannot read is refused
  // rather than drawn with a field missing from it.
  function readFinding(flag) {
    if (typeof flag !== "object" || flag === null || Array.isArray(flag)) {
      throw new FlagListError("bad_flag", FLAG_MESSAGE);
    }
    return {
      id: readText(flag, "id"),
      tier: readTier(flag),
      label: readText(flag, "label"),
      weight: readWeightBand(flag),
      confidence: readConfidence(flag),
      expected: readHalf(flag, "expected"),
      found: readHalf(flag, "found"),
      reason: readText(flag, "reason"),
      located: readRegion(flag),
    };
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

  function drawRow(record) {
    const item = element("li", [ITEM_CLASS, ROW_OWN_CLASS]);
    const row = element("div", [ROW_CLASS, ROW_FIXED_CLASS]);

    const start = element("span", [START_CLASS]);
    const stack = element("span", STACK_CLASSES);
    stack.appendChild(element("span", [], record.label));
    stack.appendChild(element("span", [], record.reason));
    stack.appendChild(
      element("span", [MUTED_CLASS], EXPECTED_LABEL + record.expected),
    );
    stack.appendChild(
      element("span", [MUTED_CLASS], FOUND_LABEL + record.found),
    );
    if (!record.located) {
      stack.appendChild(element("span", [MUTED_CLASS], NOT_LOCATABLE));
    }
    start.appendChild(stack);

    const end = element("span", [END_CLASS]);
    end.appendChild(
      element("span", [MUTED_CLASS], WEIGHT_LABEL + record.weight),
    );
    end.appendChild(
      element("span", [MUTED_CLASS], CONFIDENCE_LABEL + record.confidence),
    );

    row.appendChild(start);
    row.appendChild(end);
    item.appendChild(row);
    return item;
  }

  // bindFlagList wires the findings panel, and draws nothing until a page calls
  // render().
  function bindFlagList(options) {
    const settings = options || {};
    const container = readElement(settings, "container");

    let drawn = [];
    let current = null;

    // Every finding is read before the first element is written, so a result
    // this page cannot read leaves the list as it was rather than half
    // replaced by groups that stop mid-cascade (D6's rule turned round).
    function measure(flags) {
      if (!Array.isArray(flags)) {
        throw new FlagListError("bad_flags", FLAGS_MESSAGE);
      }
      const records = flags.map(readFinding);
      const groups = [];
      let total = 0;
      for (const tier of TIER_ORDER) {
        const rows = records.filter((record) => record.tier === tier);
        if (rows.length > 0) {
          groups.push({
            tier: tier,
            label: TIER_LABELS[tier],
            rows: rows,
          });
          total += rows.length;
        }
      }
      return { groups: groups, total: total, empty: records.length === 0 };
    }

    function drawGroup(group) {
      const heading = element("h3", GROUP_CLASSES);
      heading.appendChild(element("span", [GROUP_LABEL_CLASS], group.label));
      const list = element("ul", LIST_CLASSES);
      for (const record of group.rows) {
        list.appendChild(drawRow(record));
      }
      return [heading, list];
    }

    function render(flags) {
      const read = measure(flags);
      clear();
      if (read.empty) {
        const empty = element("div", [EMPTY_CLASS]);
        const words = element("div", [EMPTY_CONTENT_CLASS]);
        words.appendChild(element("p", [], NO_FINDINGS));
        empty.appendChild(words);
        container.appendChild(empty);
        drawn.push(empty);
      } else {
        for (const group of read.groups) {
          for (const node of drawGroup(group)) {
            container.appendChild(node);
            drawn.push(node);
          }
        }
      }
      current = read;
      return read.total;
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

    function tiers() {
      return current === null
        ? []
        : current.groups.map((group) => group.tier);
    }

    function ids() {
      if (current === null) {
        return [];
      }
      const found = [];
      for (const group of current.groups) {
        for (const record of group.rows) {
          found.push(record.id);
        }
      }
      return found;
    }

    return {
      render,
      clear,
      tiers,
      ids,
      rows: () => (current === null ? 0 : current.total),
      empty: () => current !== null && current.empty,
    };
  }

  window.DRISHTI_FLAG_LIST = {
    LIST_CLASSES,
    ITEM_CLASS,
    ROW_CLASS,
    ROW_FIXED_CLASS,
    START_CLASS,
    END_CLASS,
    STACK_CLASSES,
    MUTED_CLASS,
    GROUP_CLASSES,
    GROUP_LABEL_CLASS,
    EMPTY_CLASS,
    EMPTY_CONTENT_CLASS,
    ROW_OWN_CLASS,
    TIER_ORDER,
    TIER_LABELS,
    WEIGHT_BANDS,
    WEIGHT_LABEL,
    CONFIDENCE_LABEL,
    EXPECTED_LABEL,
    FOUND_LABEL,
    NOT_RECORDED,
    NOT_LOCATABLE,
    NO_FINDINGS,
    REQUIRED_ELEMENTS,
    FlagListError,
    bindFlagList,
  };
})();
