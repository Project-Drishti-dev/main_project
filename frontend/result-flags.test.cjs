const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const { buildFileNames } = require("./build.cjs");

const source = fs.readFileSync(path.join(__dirname, "result-flags.js"), "utf8");
const sheet = fs.readFileSync(
  path.join(__dirname, "node_modules", "ux4g-web-components", "styles", "ux4g.css"),
  "utf8",
);
const flagsServiceSource = fs.readFileSync(
  path.join(__dirname, "..", "backend", "app", "risk", "flags.py"),
  "utf8",
);
const flagIdsSource = fs.readFileSync(
  path.join(__dirname, "..", "backend", "app", "risk", "flag_ids.py"),
  "utf8",
);
const reportingSource = fs.readFileSync(
  path.join(__dirname, "..", "backend", "app", "reporting.py"),
  "utf8",
);

const TEXT_NODE = 3;

// The smallest element a row can be built on: the classes, the text and the
// children, and nothing else, so a property nobody implemented here would
// throw rather than pass quietly.
function createElement(tagName = "div") {
  const classes = new Set();
  return {
    tagName: tagName.toUpperCase(),
    nodeType: 1,
    classes: classes,
    children: [],
    textContent: "",
    classList: {
      add: function (name) {
        classes.add(name);
      },
      remove: function (name) {
        classes.delete(name);
      },
      contains: function (name) {
        return classes.has(name);
      },
    },
    appendChild: function (child) {
      this.children.push(child);
      return child;
    },
    removeChild: function (child) {
      const at = this.children.indexOf(child);
      if (at < 0) {
        throw new Error("the flag list removed a row it never drew");
      }
      this.children.splice(at, 1);
      return child;
    },
  };
}

function textOf(node) {
  if (node.nodeType === TEXT_NODE) {
    return node.textContent;
  }
  return node.textContent + node.children.map(textOf).join("");
}

// fetch and FormData are recorders rather than absences, so a send is visible
// to fail on rather than silently absent.
function loadList() {
  const sent = { fetches: 0, formData: 0 };
  const sandbox = {
    window: {},
    document: {
      createElement: createElement,
      createTextNode: function (text) {
        return { nodeType: TEXT_NODE, textContent: String(text) };
      },
    },
    fetch: function () {
      sent.fetches += 1;
      throw new Error("the flag list must not send anything");
    },
    FormData: function () {
      sent.formData += 1;
      throw new Error("the flag list must not build a request");
    },
  };
  vm.runInNewContext(source, sandbox);
  return { module: sandbox.window.DRISHTI_FLAG_LIST, sent: sent };
}

function bind(module) {
  const container = createElement();
  const controller = module.bindFlagList({ container: container });
  return { controller: controller, container: container };
}

// The module answers in its own sandbox, so its arrays carry another realm's
// prototype: they are read back into this one before anything is compared.
function host(value) {
  return Array.from(value);
}

// One stored finding as the service records it, carrying no value that came
// off a document: two digits, a field name and a fixed sentence.
function finding(overrides = {}) {
  return {
    id: "MRZ_DOCUMENT_NUMBER_CHECK_DIGIT_MISMATCH",
    tier: 0,
    label: "Document number check digits do not match",
    weight_band: "high",
    value: 0.9,
    confidence: 0.92,
    region: [
      [12, 40],
      [180, 40],
      [180, 64],
      [12, 64],
    ],
    expected: "2",
    found: "7",
    reason: "The check digits printed over the number do not match it.",
    source_module: "mrz",
    field: "document_number",
    ...overrides,
  };
}

// The groups as the page receives them: each heading and the list under it.
function groupsOf(container) {
  const groups = [];
  for (let at = 0; at < container.children.length; at += 2) {
    const heading = container.children[at];
    const list = container.children[at + 1];
    groups.push({
      heading: heading,
      list: list,
      label: textOf(heading.children[0]),
      rows: list.children,
    });
  }
  return groups;
}

function rowText(item) {
  const [start, end] = item.children[0].children;
  return textOf(start) + " " + textOf(end);
}

function refuses(call, code) {
  assert.throws(call, (error) => {
    assert.equal(error.name, "FlagListError");
    assert.equal(error.code, code);
    return true;
  });
}

test("every row carries label, weight, confidence, expected, found and reason", () => {
  const { module } = loadList();
  const { controller, container } = bind(module);
  const record = finding();
  assert.equal(controller.render([record]), 1);

  const [group] = groupsOf(container);
  assert.equal(group.rows.length, 1);
  const [item] = group.rows;
  assert.ok(item.classes.has("ux4g-list-item"));
  assert.ok(item.classes.has(module.ROW_OWN_CLASS));
  assert.ok(item.children[0].classes.has("ux4g-list-item-row"));
  assert.ok(item.children[0].classes.has("ux4g-list-item-row-fixed"));

  const text = rowText(item);
  assert.ok(text.includes(record.label), "the label");
  assert.ok(text.includes("Weight band: high"), "the weight");
  assert.ok(text.includes("Confidence: 0.92"), "the confidence");
  assert.ok(text.includes("Expected: 2"), "the expected");
  assert.ok(text.includes("Found: 7"), "the found");
  assert.ok(text.includes(record.reason), "the plain-language reason");
});

test("findings are grouped by tier in the order the cascade runs them", () => {
  const { module } = loadList();
  const { controller, container } = bind(module);
  const tiers = ["crossdoc", 1, "quality", 0, 2];
  const flags = tiers.map((tier, at) =>
    finding({ id: "ID_" + at, tier: tier, label: "Finding " + at }),
  );
  assert.equal(controller.render(flags), 5);

  assert.deepEqual(host(controller.tiers()), host(module.TIER_ORDER));
  assert.deepEqual(
    groupsOf(container).map((group) => group.label),
    ["Capture quality", "Tier 0", "Tier 1", "Tier 2", "Cross-document"],
  );
  assert.deepEqual(
    groupsOf(container).map((group) => group.rows.length),
    [1, 1, 1, 1, 1],
  );
  // Cascade order, not arrival order: the capture gate runs before tier 0.
  assert.deepEqual(host(controller.ids()), [
    "ID_2",
    "ID_3",
    "ID_1",
    "ID_4",
    "ID_0",
  ]);
});

test("a tier nothing ran draws no group at all", () => {
  const { module } = loadList();
  const { controller, container } = bind(module);
  controller.render([finding({ tier: "quality" }), finding({ tier: 2 })]);
  assert.deepEqual(host(controller.tiers()), ["quality", 2]);
  assert.equal(groupsOf(container).length, 2);
  assert.equal(controller.rows(), 2);
});

test("a half of the comparison nothing wrote says the report's word", () => {
  const { module } = loadList();
  const { controller, container } = bind(module);
  controller.render([finding({ tier: "quality", expected: null, found: null })]);
  const text = rowText(groupsOf(container)[0].rows[0]);
  assert.ok(text.includes("Expected: not recorded"));
  assert.ok(text.includes("Found: not recorded"));
  assert.ok(!text.includes("Expected: 2"));
  assert.equal(controller.rows(), 1);
});

test("a finding with nowhere to point is listed, and says so", () => {
  const { module } = loadList();
  const { controller, container } = bind(module);
  const placed = finding({ id: "PLACED" });
  const unplaced = finding({ id: "UNPLACED", region: null });
  assert.equal(controller.render([placed, unplaced]), 2);
  assert.deepEqual(host(controller.ids()), ["PLACED", "UNPLACED"]);

  const [group] = groupsOf(container);
  const withRegion = rowText(group.rows[0]);
  const without = rowText(group.rows[1]);
  assert.ok(!withRegion.includes(module.NOT_LOCATABLE), "a located row notes nothing");
  assert.match(module.NOT_LOCATABLE, /not locatable on this document/i);
  assert.ok(
    without.includes(module.NOT_LOCATABLE),
    "the row says the finding is not on the document",
  );
  assert.ok(without.includes(unplaced.label), "the label is still there");
  assert.ok(without.includes(unplaced.reason), "the reason is still there");
  assert.ok(without.includes("Expected: 2"));
  assert.ok(without.includes("Found: 7"));
  assert.ok(without.includes("Weight band: high"));
  assert.ok(without.includes("Confidence: 0.92"));
});

test("a region nobody wrote and a box are the two other answers", () => {
  const { module } = loadList();
  const { controller, container } = bind(module);
  const row = () => rowText(groupsOf(container)[0].rows[0]);

  controller.render([finding({ region: undefined })]);
  assert.ok(row().includes(module.NOT_LOCATABLE), "no region at all");
  assert.equal(controller.empty(), false);
  assert.equal(controller.rows(), 1);

  controller.render([finding({ region: [] })]);
  assert.ok(row().includes(module.NOT_LOCATABLE), "an empty region is nowhere");

  // A box is a region too: the list asks whether one was recorded and leaves
  // the shape of it to overlay.js.
  controller.render([finding({ region: { x: 1, y: 2, width: 3, height: 4 } })]);
  assert.ok(!row().includes(module.NOT_LOCATABLE), "a box is a place");
});

test("a region that names nowhere is refused, not called a finding with no place", () => {
  const { module } = loadList();
  const { controller, container } = bind(module);
  controller.render([finding({ label: "First finding" })]);
  const before = groupsOf(container);

  for (const region of ["top left", 7, true]) {
    refuses(() => controller.render([finding({ region: region })]), "bad_region");
  }

  assert.equal(container.children.length, before.length * 2);
  assert.ok(rowText(before[0].rows[0]).includes("First finding"));
});

test("a screening with no findings says so instead of drawing an empty list", () => {
  const { module } = loadList();
  const { controller, container } = bind(module);
  assert.equal(controller.render([]), 0);
  assert.ok(controller.empty());
  assert.deepEqual(host(controller.tiers()), []);
  const [empty] = container.children;
  assert.ok(empty.classes.has("ux4g-empty-state"));
  const [words] = empty.children;
  assert.ok(words.classes.has("ux4g-empty-state-content"));
  assert.ok(textOf(empty).includes(module.NO_FINDINGS));
});

test("every UX4G class the module writes is a class the sheet ships", () => {
  const { module } = loadList();
  const { controller, container } = bind(module);
  const written = [];
  const walk = (node) => {
    for (const name of node.classes) {
      written.push(name);
    }
    for (const child of node.children) {
      walk(child);
    }
  };
  controller.render([finding({ tier: "quality" }), finding({ tier: 0 })]);
  walk(container);
  controller.render([]);
  walk(container);

  const sheetOnes = written.filter((name) => name.startsWith("ux4g-"));
  assert.ok(sheetOnes.length > 0);
  for (const name of sheetOnes) {
    assert.ok(
      sheet.includes("." + name),
      name + " is not a class in ux4g-web-components@2.1.0",
    );
  }
  // The only class of the project's own, because the sheet has none for a
  // row of its own: the hook for the rule G9 already owes.
  assert.deepEqual(
    written.filter((name) => name.startsWith("result-")),
    [module.ROW_OWN_CLASS, module.ROW_OWN_CLASS],
  );
});

test("the tier table is exactly the five the cascade runs", () => {
  const { module } = loadList();
  assert.deepEqual(host(module.TIER_ORDER), ["quality", 0, 1, 2, "crossdoc"]);
  // app/risk/flag_ids.py documents the order in a sentence, so the two cannot
  // fall apart without this case going red.
  assert.match(
    flagIdsSource,
    /the quality gate[\s\S]*?first, then tier 0, tier 1, tier 2, then the cross-document rules/,
  );
  assert.deepEqual(Object.keys(module.TIER_LABELS).sort(), [
    "0",
    "1",
    "2",
    "crossdoc",
    "quality",
  ]);
});

test("the weight bands are the three app/risk/flags.py freezes", () => {
  const { module } = loadList();
  const frozen = flagsServiceSource.match(
    /WEIGHT_BANDS = frozenset\(\{([^}]*)\}\)/,
  );
  assert.ok(frozen, "app/risk/flags.py no longer freezes WEIGHT_BANDS");
  assert.deepEqual(host(module.WEIGHT_BANDS), ["low", "review", "high"]);
  assert.deepEqual(
    frozen[1].match(/"([^"]+)"/g).map((quoted) => quoted.slice(1, -1)).sort(),
    host(module.WEIGHT_BANDS).slice().sort(),
  );
});

test("the row calls each field what the printable report calls it", () => {
  const { module } = loadList();
  for (const heading of ["Weight band", "Confidence"]) {
    assert.ok(
      reportingSource.includes('("' + heading + '",'),
      heading + " is not a heading of the printable report",
    );
  }
  assert.equal(module.WEIGHT_LABEL, "Weight band: ");
  assert.equal(module.CONFIDENCE_LABEL, "Confidence: ");
  assert.equal(module.NOT_RECORDED, "not recorded");
  assert.match(reportingSource, /NOT_RECORDED = "not recorded"/);
  assert.ok(
    reportingSource.includes(module.NO_FINDINGS),
    "the empty state is not the report's own sentence",
  );
});

test("a finding this page cannot read is refused by name, and the list stands", () => {
  const { module } = loadList();
  const { controller, container } = bind(module);
  controller.render([finding({ label: "First finding" })]);
  const before = groupsOf(container);
  const record = finding();

  refuses(() => controller.render(undefined), "bad_flags");
  refuses(() => controller.render("flags"), "bad_flags");
  refuses(() => controller.render([null]), "bad_flag");
  refuses(() => controller.render([[record]]), "bad_flag");
  for (const field of ["id", "label", "reason"]) {
    refuses(() => controller.render([finding({ [field]: "" })]), "bad_flag");
    refuses(() => controller.render([finding({ [field]: 7 })]), "bad_flag");
  }
  for (const half of ["expected", "found"]) {
    refuses(() => controller.render([finding({ [half]: undefined })]), "bad_flag");
    refuses(() => controller.render([finding({ [half]: 7 })]), "bad_flag");
  }

  // One heading and one list per group, so the refusal changed no element.
  assert.equal(container.children.length, before.length * 2);
  assert.equal(container.children[0], before[0].heading);
  assert.equal(controller.rows(), 1);
  assert.ok(rowText(before[0].rows[0]).includes("First finding"));
});

test("a tier, a weight or a confidence the engine never records is refused", () => {
  const { module } = loadList();
  const { controller, container } = bind(module);
  controller.render([finding()]);
  assert.equal(container.children.length, 2);

  for (const tier of [null, "0", "3", "TIER_0", "tier0", true]) {
    refuses(() => controller.render([finding({ tier: tier })]), "bad_tier");
  }
  for (const band of ["LOW", "medium", "", null, 3]) {
    refuses(
      () => controller.render([finding({ weight_band: band })]),
      "bad_weight",
    );
  }
  for (const confidence of [
    undefined,
    null,
    "0.92",
    Number.NaN,
    1.0001,
    -0.0001,
    Number.POSITIVE_INFINITY,
  ]) {
    refuses(
      () => controller.render([finding({ confidence: confidence })]),
      "bad_confidence",
    );
  }
  assert.equal(container.children.length, 2);
  assert.equal(controller.rows(), 1);
});

test("a confidence is printed as it was measured, never rounded", () => {
  const { module } = loadList();
  const { controller, container } = bind(module);
  const readings = [0, 1, 0.9, 0.925, 0.1 + 0.2];
  controller.render(
    readings.map((confidence, at) =>
      finding({ id: "C" + at, confidence: confidence }),
    ),
  );
  const rows = groupsOf(container)[0].rows;
  assert.equal(rows.length, readings.length);
  readings.forEach((confidence, at) => {
    assert.ok(
      rowText(rows[at]).includes("Confidence: " + String(confidence)),
      "confidence " + at,
    );
  });
});

test("a binding is refused by cause when it has no container", () => {
  const { module } = loadList();
  refuses(() => module.bindFlagList(), "missing_element");
  refuses(() => module.bindFlagList({}), "missing_element");
  const { controller, container } = bind(module);
  assert.deepEqual(host(controller.tiers()), []);
  assert.deepEqual(host(controller.ids()), []);
  assert.equal(controller.rows(), 0);
  assert.equal(controller.empty(), false);
  assert.deepEqual(container.children, []);
});

test("clearing takes away only what this module drew", () => {
  const { module } = loadList();
  const { controller, container } = bind(module);
  const own = createElement();
  container.appendChild(own);
  assert.equal(controller.clear(), false);
  controller.render([finding({ tier: "quality" }), finding({ tier: 0 })]);
  assert.equal(controller.clear(), true);
  assert.equal(controller.rows(), 0);
  assert.equal(controller.clear(), false);
  assert.deepEqual(container.children, [own]);
  assert.equal(controller.render([finding()]), 1);
  assert.equal(container.children.length, 3);
});

test("the flag list sends nothing and builds no request", () => {
  const { module, sent } = loadList();
  const { controller } = bind(module);
  controller.render([finding()]);
  controller.render([]);
  assert.deepEqual(sent, { fetches: 0, formData: 0 });
});

test("no page loads the flag list yet, so the build copies nothing", () => {
  const { staticFiles, pageFileNames } = buildFileNames();
  const pages = pageFileNames.map((fileName) =>
    fs.readFileSync(path.join(__dirname, fileName), "utf8"),
  );
  const shell = fs.readFileSync(path.join(__dirname, "shell.html"), "utf8");

  assert.ok(!staticFiles.includes("result-flags.js"));
  for (const markup of [...pages, shell]) {
    assert.doesNotMatch(markup, /result-flags\.js/);
  }
});