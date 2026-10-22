const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const { buildFileNames } = require("./build.cjs");

const source = fs.readFileSync(path.join(__dirname, "result-band.js"), "utf8");
const formatSource = fs.readFileSync(path.join(__dirname, "format.js"), "utf8");
const sheet = fs.readFileSync(
  path.join(__dirname, "node_modules", "ux4g-web-components", "styles", "ux4g.css"),
  "utf8",
);

const TEXT_NODE = 3;

// The smallest element a band line can be built on: the classes, the text and
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
        throw new Error("the band line removed a row it never drew");
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

// The two modules in one sandbox, because the band line is drawn from both:
// fetch and FormData are recorders rather than absences, so a send is visible
// to fail on rather than silently absent.
function loadBand(withFormat = true) {
  const created = [];
  const sent = { fetches: 0, formData: 0 };
  const sandbox = {
    window: {},
    document: {
      createElement: function (tagName) {
        const element = createElement(tagName);
        created.push(element);
        return element;
      },
      createTextNode: function (text) {
        return { nodeType: TEXT_NODE, textContent: String(text) };
      },
    },
    fetch: function () {
      sent.fetches += 1;
      throw new Error("the band line must not send anything");
    },
    FormData: function () {
      sent.formData += 1;
      throw new Error("the band line must not build a request");
    },
  };
  if (withFormat) {
    vm.runInNewContext(formatSource, sandbox);
  }
  vm.runInNewContext(source, sandbox);
  return {
    band: sandbox.window.DRISHTI_RESULT_BAND,
    format: sandbox.window.DRISHTI_FORMAT,
    created: created,
    sent: sent,
  };
}

function bind(module, options = {}) {
  const container = createElement();
  const controller = module.bindResultBand({ container: container, ...options });
  return { controller: controller, container: container };
}

// The line as the page receives it: the row, its tag and its score.
function drawn(container) {
  const [row] = container.children;
  const [tag, score] = row.children;
  return {
    row: row,
    tag: tag,
    score: score,
    text: textOf(row),
  };
}

function refuses(call, code) {
  assert.throws(call, (error) => {
    assert.equal(error.name, "ResultBandError");
    assert.equal(error.code, code);
    return true;
  });
}

const CASES = [
  { band: "low", variant: "ux4g-tag-filled-success", label: "Low Risk" },
  { band: "review", variant: "ux4g-tag-filled-warning", label: "Review" },
  { band: "high", variant: "ux4g-tag-filled-error", label: "High Risk" },
];

test("each band renders its own tag variant beside its score", () => {
  const { band: module } = loadBand();
  for (const expected of CASES) {
    const { controller, container } = bind(module);
    controller.render({ band: expected.band, score: 42.5 });
    const line = drawn(container);

    assert.ok(line.tag.classes.has("ux4g-tag"), expected.band);
    assert.ok(line.tag.classes.has("ux4g-tag-s"), expected.band);
    assert.ok(line.tag.classes.has(expected.variant), expected.band);
    assert.equal(textOf(line.tag), expected.label);
    assert.equal(controller.variant(), expected.variant);
    assert.equal(textOf(line.score), "Score: 42.5");
    assert.equal(controller.score(), "42.5");
  }
});

test("one band never leaves another's variant behind it", () => {
  const { band: module } = loadBand();
  const { controller, container } = bind(module);
  for (const expected of CASES) {
    controller.render({ band: expected.band, score: 10 });
    const line = drawn(container);
    const variants = CASES.map((each) => each.variant);
    const written = [...line.tag.classes].filter((name) =>
      variants.includes(name),
    );
    assert.deepEqual(written, [expected.variant]);
  }
  assert.equal(container.children.length, 1);
});

test("every UX4G class the module writes is a class the sheet ships", () => {
  const { band: module } = loadBand();
  const { controller, container } = bind(module);
  controller.render({ band: "review", score: 0 });
  const line = drawn(container);
  const written = [
    ...line.row.classes,
    ...line.tag.classes,
    ...line.score.classes,
    ...line.score.children[0].classes,
  ];
  const sheetOnes = written.filter((name) => name.startsWith("ux4g-"));
  assert.ok(sheetOnes.length > 0);
  for (const name of sheetOnes) {
    assert.ok(
      sheet.includes("." + name),
      name + " is not a class in ux4g-web-components@2.1.0",
    );
  }
  // The other two are the project's own, because the sheet has no class for
  // the row or for the score: they are hooks for the rule G9 already owes.
  assert.deepEqual(
    written.filter((name) => name.startsWith("result-")),
    [module.ROW_CLASS, module.SCORE_CLASS],
  );
});

test("the variant table is exactly the three bands the formatter labels", () => {
  const { band: module, format } = loadBand();
  assert.deepEqual(Object.keys(module.BAND_VARIANTS).sort(), [
    "high",
    "low",
    "review",
  ]);
  assert.deepEqual(
    Object.keys(module.BAND_VARIANTS).sort(),
    Object.keys(format.BAND_LABELS).sort(),
  );
  for (const band of Object.keys(format.BAND_LABELS)) {
    assert.equal(module.bandVariant(band), module.BAND_VARIANTS[band]);
  }
});

test("a band the engine never bands in is refused by name", () => {
  const { band: module } = loadBand();
  for (const band of [null, undefined, "", "LOW", "critical", 3, "toString"]) {
    refuses(() => module.bandVariant(band), "bad_band");
  }
});

test("a result carrying no band leaves the line standing", () => {
  const { band: module } = loadBand();
  const { controller, container } = bind(module);
  controller.render({ band: "high", score: 90 });
  refuses(() => controller.render({ score: 90 }), "bad_band");
  const line = drawn(container);
  assert.ok(line.tag.classes.has("ux4g-tag-filled-error"));
  assert.equal(textOf(line.score), "Score: 90");
  assert.equal(container.children.length, 1);
});

test("a score outside the scale is refused by name and by its own sentence", () => {
  const { band: module } = loadBand();
  const { controller, container } = bind(module);
  for (const score of [undefined, null, "42", Number.NaN, 100.1, -1]) {
    refuses(() => controller.render({ band: "low", score: score }), "bad_score");
  }
  assert.deepEqual(container.children, []);
  assert.equal(controller.score(), null);
  controller.render({ band: "low", score: 0 });
  assert.equal(controller.score(), "0");
  controller.render({ band: "low", score: 100 });
  assert.equal(controller.score(), "100");
});

test("a band read and a score read leave the line exactly as it was", () => {
  const { band: module } = loadBand();
  const { controller, container } = bind(module);
  controller.render({ band: "review", score: 35 });
  const before = drawn(container);
  refuses(() => controller.render({ band: "high", score: 500 }), "bad_score");
  assert.equal(container.children.length, 1);
  assert.equal(container.children[0], before.row);
  assert.ok(before.tag.classes.has("ux4g-tag-filled-warning"));
});

test("the score is labelled for a screen reader and quiet on screen", () => {
  const { band: module } = loadBand();
  const { controller, container } = bind(module);
  controller.render({ band: "high", score: 70 });
  const line = drawn(container);
  const [label, number] = line.score.children;
  assert.ok(line.score.classes.has("result-band-score"));
  assert.ok(label.classes.has("ux4g-sr-only"));
  assert.equal(textOf(label), "Score: ");
  assert.equal(number.nodeType, 3);
  assert.equal(textOf(number), "70");
});

test("a binding is refused by cause when it has no container or no formatter", () => {
  const { band: module } = loadBand();
  refuses(() => module.bindResultBand(), "missing_element");
  refuses(() => module.bindResultBand({}), "missing_element");
  const { band: without } = loadBand(false);
  refuses(
    () => without.bindResultBand({ container: createElement() }),
    "no_format",
  );
});

test("clearing takes away only the row this module drew", () => {
  const { band: module } = loadBand();
  const { controller, container } = bind(module);
  const own = createElement();
  container.appendChild(own);
  assert.equal(controller.clear(), false);
  controller.render({ band: "low", score: 12 });
  assert.equal(controller.clear(), true);
  assert.equal(controller.band(), null);
  assert.equal(controller.clear(), false);
  assert.deepEqual(container.children, [own]);
});

test("the band line sends nothing and builds no request", () => {
  const { band: module, sent } = loadBand();
  const { controller } = bind(module);
  controller.render({ band: "review", score: 35 });
  assert.deepEqual(sent, { fetches: 0, formData: 0 });
});

test("no page loads the band line yet, so the build copies nothing", () => {
  const { staticFiles, pageFileNames } = buildFileNames();
  const pages = pageFileNames.map((fileName) =>
    fs.readFileSync(path.join(__dirname, fileName), "utf8"),
  );
  const shell = fs.readFileSync(path.join(__dirname, "shell.html"), "utf8");

  assert.ok(
    !staticFiles.includes("result-band.js"),
    "result-band.js must not be copied yet",
  );
  for (const markup of [...pages, shell]) {
    assert.doesNotMatch(markup, /result-band\.js/);
  }
  // format.js stayed out of the build until 24.1 loaded it on the history
  // view; the band line itself still has no page, which is what this is about.
  assert.ok(staticFiles.includes("format.js"));
});
