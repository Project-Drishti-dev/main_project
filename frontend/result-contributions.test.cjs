const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const { buildFileNames } = require("./build.cjs");

const source = fs.readFileSync(
  path.join(__dirname, "result-contributions.js"),
  "utf8",
);
const sheet = fs.readFileSync(
  path.join(__dirname, "node_modules", "ux4g-web-components", "styles", "ux4g.css"),
  "utf8",
);
const scoringSource = fs.readFileSync(
  path.join(__dirname, "..", "backend", "app", "risk", "scoring.py"),
  "utf8",
);
const routeSource = fs.readFileSync(
  path.join(__dirname, "..", "backend", "app", "api", "routes_screenings.py"),
  "utf8",
);

const TEXT_NODE = 3;

// The smallest element a table cell can be built on: the classes, the text and
// the children, and nothing else, so a property nobody implemented here would
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
        throw new Error("the panel removed a table it never drew");
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

// The module answers in its own sandbox, and sends nothing: fetch and FormData
// are recorders rather than absences, so a send is visible to fail on rather
// than silently absent.
function loadPanel() {
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
      throw new Error("the panel must not send anything");
    },
    FormData: function () {
      sent.formData += 1;
      throw new Error("the panel must not build a request");
    },
  };
  vm.runInNewContext(source, sandbox);
  return { module: sandbox.window.DRISHTI_CONTRIBUTIONS, sent: sent };
}

function bind(module) {
  const container = createElement();
  const controller = module.bindContributions({ container: container });
  return { controller: controller, container: container };
}

// The module answers in another realm, so its arrays carry another realm's
// prototype: they are read back into this one before anything is compared.
function host(value) {
  return Array.from(value);
}

// One term as the API sends it: app/risk/scoring.py's Contribution as
// dataclasses.asdict writes it.
function term(overrides = {}) {
  return {
    id: "MRZ_DOCUMENT_NUMBER_CHECK_DIGIT_MISMATCH",
    weight: 12,
    value: 0.9,
    contribution: 10.8,
    ...overrides,
  };
}

// The table as the page receives it: the caption, the head, the body rows and
// the total row in the foot.
function drawn(container) {
  const [table] = container.children;
  const [caption, head, body, foot] = table.children;
  const headings = host(head.children[0].children).map(textOf);
  return {
    table: table,
    caption: caption,
    headings: headings,
    rows: body.children,
    cells: (row) => host(row.children).map(textOf),
    totalRow: foot.children[0],
  };
}

// The number in the fourth column of each row, read out of the markup rather
// than out of the module, and the one in the total row beside them.
function numbersOn(container) {
  const table = drawn(container);
  const read = table.rows.map((row) => Number(table.cells(row)[3]));
  const shown = Number(textOf(table.totalRow.children[3]));
  return { rows: read, total: shown };
}

function refuses(call, code, note) {
  assert.throws(call, (error) => {
    assert.equal(error.name, "ContributionsError", note);
    assert.equal(error.code, code, note);
    return true;
  });
}

test("each term renders its id, weight, value and product", () => {
  const { module } = loadPanel();
  const { controller, container } = bind(module);
  const record = term();
  assert.equal(controller.render([record]), 1);

  const table = drawn(container);
  assert.equal(table.table.tagName, "TABLE");
  assert.deepEqual(table.headings, host(module.HEADINGS));
  assert.equal(table.rows.length, 1);
  assert.deepEqual(table.cells(table.rows[0]), [
    record.id,
    "12.00",
    "0.90",
    "10.80",
  ]);
  assert.deepEqual(host(controller.ids()), [record.id]);
});

test("the contributions on screen add up to the total beside them", () => {
  const { module } = loadPanel();
  const { controller, container } = bind(module);
  const terms = [
    term({ id: "A", weight: 12, value: 0.9, contribution: 10.8 }),
    term({ id: "B", weight: 8, value: 0.25, contribution: 2 }),
    term({ id: "C", weight: 30, value: 1 / 3, contribution: 10 }),
  ];
  assert.equal(controller.render(terms), 3);

  const read = numbersOn(container);
  assert.equal(read.rows.length, 3);
  // The products are read out of the markup, so this is an assertion about
  // what an officer sees and not about what the module believes it wrote.
  let sum = 0;
  for (const value of read.rows) {
    sum += value;
  }
  // The same two-decimal rounding the panel shows, because a binary float sum
  // of three decimal values is not the decimal sum a reader would do.
  assert.equal(Number(sum.toFixed(module.DECIMALS)), read.total);
  assert.equal(controller.total(), "22.80");
  assert.equal(textOf(drawn(container).totalRow.children[0]), "Total");
});

test("an empty breakdown is the table with a total of zero, not an apology", () => {
  const { module } = loadPanel();
  const { controller, container } = bind(module);
  assert.equal(controller.render([]), 0);

  const table = drawn(container);
  assert.equal(table.rows.length, 0);
  assert.equal(controller.total(), "0.00");
  assert.equal(controller.empty(), true);
  assert.equal(textOf(table.caption), module.CAPTION_TEXT);
});

test("a total is the sum of the terms the panel was given, in the order they arrived", () => {
  const { module } = loadPanel();
  const { controller, container } = bind(module);
  const terms = [
    term({ id: "LATE", weight: 5, value: 0.5, contribution: 2.5 }),
    term({ id: "EARLY", weight: 5, value: 0.5, contribution: 2.5 }),
  ];
  controller.render(terms);
  assert.deepEqual(host(controller.ids()), ["LATE", "EARLY"]);

  const swapped = bind(module);
  swapped.controller.render([terms[1], terms[0]]);
  assert.deepEqual(host(swapped.controller.ids()), ["EARLY", "LATE"]);
  assert.equal(swapped.controller.total(), controller.total());
});

test("a second render replaces the first table rather than adding to it", () => {
  const { module } = loadPanel();
  const { controller, container } = bind(module);
  controller.render([term()]);
  controller.render([term({ id: "B" })]);
  assert.equal(container.children.length, 1);
  assert.equal(drawn(container).rows.length, 1);
  assert.deepEqual(host(controller.ids()), ["B"]);
});

test("a term this page cannot read leaves the table standing", () => {
  const { module } = loadPanel();
  const { controller, container } = bind(module);
  controller.render([term({ id: "KEPT", contribution: 4 })]);
  const before = drawn(container);

  const refusals = [
    { given: "MRZ_DOCUMENT_NUMBER_CHECK_DIGIT_MISMATCH", code: "bad_contributions" },
    { given: [{ ...term(), id: "" }], code: "bad_term" },
    { given: [{ ...term(), id: 7 }], code: "bad_term" },
    { given: [null], code: "bad_term" },
    { given: [term(), "SECOND"], code: "bad_term" },
    { given: [{ ...term(), weight: "12" }], code: "bad_number" },
    { given: [{ ...term(), value: Number.NaN }], code: "bad_number" },
    { given: [{ ...term(), contribution: undefined }], code: "bad_number" },
    { given: [{ ...term(), contribution: null }], code: "bad_number" },
  ];
  for (const refusal of refusals) {
    refuses(
      () => controller.render(refusal.given),
      refusal.code,
      JSON.stringify(refusal.given),
    );
  }

  assert.equal(container.children.length, 1);
  assert.equal(drawn(container).rows.length, 1);
  assert.equal(textOf(before.rows[0].children[0]), "KEPT");
  assert.equal(controller.total(), "4.00");
});

test("a contribution list is refused by cause before anything is drawn", () => {
  const { module } = loadPanel();
  const { controller, container } = bind(module);
  for (const bad of [undefined, null, "[]", 0, {}, new Map()]) {
    refuses(() => controller.render(bad), "bad_contributions");
  }
  assert.deepEqual(container.children, []);
  assert.equal(controller.rows(), 0);
  assert.equal(controller.total(), null);
  assert.deepEqual(host(controller.ids()), []);
});

test("a binding is refused by cause when it has no container", () => {
  const { module } = loadPanel();
  refuses(() => module.bindContributions(), "missing_element");
  refuses(() => module.bindContributions({}), "missing_element");
  refuses(
    () => module.bindContributions({ pane: createElement() }),
    "missing_element",
  );
  assert.deepEqual(host(module.REQUIRED_ELEMENTS), ["container"]);
});

test("clearing takes away only the table this module drew", () => {
  const { module } = loadPanel();
  const { controller, container } = bind(module);
  const own = createElement();
  container.appendChild(own);
  assert.equal(controller.clear(), false);
  controller.render([term()]);
  assert.equal(controller.clear(), true);
  assert.equal(controller.total(), null);
  assert.equal(controller.clear(), false);
  assert.deepEqual(container.children, [own]);
});

test("every UX4G class the panel writes is a class the sheet ships", () => {
  const { module } = loadPanel();
  const { controller, container } = bind(module);
  controller.render([term()]);
  const table = drawn(container);
  const written = new Set();
  const walk = (node) => {
    for (const name of node.classes) {
      written.add(name);
    }
    for (const child of node.children) {
      walk(child);
    }
  };
  walk(table.table);

  const sheetOnes = [...written].filter((name) => name.startsWith("ux4g-"));
  assert.ok(sheetOnes.length > 0);
  for (const name of sheetOnes) {
    assert.ok(
      sheet.includes("." + name),
      name + " is not a class in ux4g-web-components@2.1.0",
    );
  }
  // The table is the sheet's own, so this panel adds no hook to the G9 list of
  // classes waiting for a pages.css rule.
  assert.deepEqual(
    [...written].filter((name) => name.startsWith("result-")),
    [],
  );
});

test("the total row is a row header, so a screen reader names its number", () => {
  const { module } = loadPanel();
  const { controller, container } = bind(module);
  controller.render([term()]);
  const total = drawn(container).totalRow;
  assert.equal(total.tagName, "TR");
  assert.equal(total.children[0].tagName, "TH");
  assert.equal(textOf(total.children[0]), module.TOTAL_LABEL);
  assert.equal(total.children.length, module.HEADINGS.length);
});

test("the panel sends nothing and builds no request", () => {
  const { module, sent } = loadPanel();
  const { controller } = bind(module);
  controller.render([term()]);
  assert.deepEqual(sent, { fetches: 0, formData: 0 });
});

test("the panel reads the four fields the result route already sends", () => {
  assert.match(routeSource, /"contributions": \[/);
  assert.match(scoringSource, /weight: float/);
  assert.match(scoringSource, /value: float/);
  assert.match(scoringSource, /contribution: float/);
  assert.match(scoringSource, /id: str/);
});

test("no page loads the panel yet, so the build copies nothing", () => {
  const { staticFiles, pageFileNames } = buildFileNames();
  const pages = pageFileNames.map((fileName) =>
    fs.readFileSync(path.join(__dirname, fileName), "utf8"),
  );
  const shell = fs.readFileSync(path.join(__dirname, "shell.html"), "utf8");

  assert.ok(!staticFiles.includes("result-contributions.js"));
  for (const markup of [...pages, shell]) {
    assert.doesNotMatch(markup, /result-contributions\.js/);
  }
});