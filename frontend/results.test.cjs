const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const { staticFiles, pageFileNames } = require("./build.cjs").buildFileNames();

const viewSource = fs.readFileSync(path.join(__dirname, "results.js"), "utf8");
const pageHtml = fs.readFileSync(path.join(__dirname, "results.html"), "utf8");
const generatedSource = fs.readFileSync(
  path.join(__dirname, "results-metrics.js"),
  "utf8",
);
const sheet = fs.readFileSync(
  path.join(
    __dirname,
    "node_modules",
    "ux4g-web-components",
    "styles",
    "ux4g.css",
  ),
  "utf8",
);

// The committed file, read the way the page reads it: the generated script is
// the only thing that stands between the four harnesses and a screen.
function loadGenerated() {
  const windowStub = {};
  vm.runInNewContext(generatedSource, { window: windowStub });
  return windowStub.DRISHTI_RESULTS_METRICS;
}

// The smallest element a row can be built in: children, classes, hidden and
// nothing else, so a property the view did not implement throws rather than
// passing quietly.
function createElement(tagName = "div") {
  const classes = new Set();
  return {
    tagName: String(tagName).toUpperCase(),
    nodeType: 1,
    classes: classes,
    children: [],
    own: "",
    hidden: false,
    get textContent() {
      return this.own + this.children.map(textOf).join("");
    },
    set textContent(value) {
      this.own = String(value);
      this.children = [];
    },
    get firstChild() {
      return this.children.length === 0 ? null : this.children[0];
    },
    classList: {
      // The real DOM's add takes every name it is handed, and the view hands
      // it a tag's base, variant and size in one call.
      add: function (...names) {
        for (const name of names) {
          classes.add(name);
        }
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
    setAttribute: function () {},
    getAttribute: function () {
      return null;
    },
    addEventListener: function () {},
  };
}

function textOf(node) {
  return node.textContent;
}

function firstLine(text) {
  return text.split("\n")[0];
}

// The page as the view finds it: the table body it fills and the empty state
// it puts away.
function loadView({ generated = loadGenerated() } = {}) {
  const body = createElement("tbody");
  const empty = createElement("div");
  const sandbox = {
    console: console,
    window: { DRISHTI_RESULTS_METRICS: generated },
    document: {
      readyState: "complete",
      getElementById: function () {
        return null;
      },
      createElement: createElement,
      addEventListener: function () {},
    },
  };
  vm.runInNewContext(viewSource, sandbox);
  return { module: sandbox.window.DRISHTI_RESULTS, body: body, empty: empty };
}

const RESULT_COLUMN = 1;
const DATASET_COLUMN = 3;

/* The claim 27.12 makes, as a function the tests below can both pass and
   fail: every row that shows a number must name the dataset that number was
   read over, and the only row allowed to name none is a design target, which
   says so in as many words. Returns what it found missing rather than
   asserting, so a held-to check can be shown going red. */
function numbersMissingTheirDataset(rows, module) {
  const names = loadGenerated().datasets.map((dataset) => dataset.name);
  const missed = [];
  rows.forEach((row, index) => {
    const cells = row.children.map(textOf);
    const result = cells[RESULT_COLUMN].trim();
    if (!module.showsANumber(result)) {
      return;
    }
    const dataset = cells[DATASET_COLUMN].trim();
    if (dataset === module.WHAT_A_TARGET_NAMES) {
      return;
    }
    if (!names.includes(dataset)) {
      missed.push({
        row: index + 1,
        metric: firstLine(cells[0]),
        result: result,
        dataset: dataset,
      });
    }
  });
  return missed;
}

function drawRealRows() {
  const view = loadView();
  const drawn = view.module
    .bindResultsView({ body: view.body, empty: view.empty })
    .draw(loadGenerated());
  return { view: view, drawn: drawn, rows: view.body.children };
}

test("every number the page shows is drawn beside its dataset", () => {
  const { view, drawn, rows } = drawRealRows();

  assert.ok(drawn > 0, "the page must show at least one metric");
  assert.equal(rows.length, drawn, "one row is drawn per metric");

  const missed = numbersMissingTheirDataset(rows, view.module);
  assert.deepEqual(
    missed,
    [],
    "every number drawn must name the dataset it was read over",
  );
});

test("the committed file holds no number that names no dataset", () => {
  const generated = loadGenerated();

  for (const metric of generated.metrics) {
    if (!showsANumber(metric.value)) {
      continue;
    }
    if (metric.source === "designed") {
      assert.equal(
        metric.dataset,
        "",
        metric.id + " is a design target and must not name a dataset",
      );
      continue;
    }
    assert.ok(
      metric.dataset,
      metric.id + " shows " + metric.value + " and names no dataset",
    );
    assert.ok(
      generated.datasets.some((dataset) => dataset.id === metric.dataset),
      metric.id + " names dataset " + metric.dataset + ", which is not declared",
    );
  }
});

function showsANumber(value) {
  return String(value) !== "--" && String(value).trim() !== "";
}

test("a metric showing a number with no dataset is refused", () => {
  const view = loadView();
  const datasets = new Map([["drawn-corpus", { id: "drawn-corpus", name: "D" }]]);

  assert.throws(
    () =>
      view.module.checkMetric(
        { id: "bare", value: "1/2", source: "measured", dataset: "" },
        datasets,
      ),
    (error) => {
      assert.equal(error.name, "ResultsError");
      assert.match(error.message, /names no dataset/);
      return true;
    },
  );
});

test("a design target naming a dataset is refused", () => {
  const view = loadView();
  const datasets = new Map([["drawn-corpus", { id: "drawn-corpus", name: "D" }]]);

  assert.throws(
    () =>
      view.module.checkMetric(
        { id: "target", value: "<0.3 s", source: "designed", dataset: "drawn-corpus" },
        datasets,
      ),
    /must not name a dataset/,
  );
});

test("a dataset nothing declares is refused", () => {
  const view = loadView();

  assert.throws(
    () =>
      view.module.checkMetric(
        { id: "stray", value: "1/2", source: "measured", dataset: "imaginary" },
        new Map(),
      ),
    /which is not one this file declares/,
  );
});

test("a design target is labelled as one rather than given a dataset", () => {
  const view = loadView();
  const target = { source: "designed", dataset: "" };

  assert.equal(
    view.module.datasetText(target, new Map()),
    view.module.WHAT_A_TARGET_NAMES,
  );
  assert.notEqual(view.module.WHAT_A_TARGET_NAMES, "");
});

test("a row with nothing counted shows the mark, not a zero", () => {
  const { view, rows } = drawRealRows();
  const unmeasured = rows.filter((row) => row.children[1].textContent.trim() === "--");

  assert.ok(unmeasured.length > 0, "the file has metrics that were not read");
  for (const row of unmeasured) {
    assert.equal(
      view.module.showsANumber(row.children[1].textContent.trim()),
      false,
      "a row with nothing counted must not read as a number",
    );
  }
});

test("each source is tagged with its own variant", () => {
  const view = loadView();
  const { rows } = drawRealRows();
  const expected = {
    measured: "ux4g-tag-filled-success",
    stub: "ux4g-tag-filled-warning",
    designed: "ux4g-tag-filled-neutral",
    "not measured": "ux4g-tag-filled-info",
  };

  for (const row of rows) {
    const tag = row.children[2].firstChild;
    assert.ok(tag.classList.contains("ux4g-tag"), "a row's source is tagged");
    assert.ok(
      Object.values(expected).includes([...tag.classes][1]),
      "the tag carries a variant the stylesheet ships",
    );
  }
  assert.deepEqual(
    Object.keys(view.module.SOURCES).sort(),
    Object.keys(expected).sort(),
    "the four sources the harnesses write are the four the view labels",
  );
});

test("nothing is drawn and the empty state shows when no metric was read", () => {
  const view = loadView({ generated: { datasets: [], metrics: [] } });
  const drawn = view.module
    .bindResultsView({ body: view.body, empty: view.empty })
    .draw({ datasets: [], metrics: [] });

  assert.equal(drawn, 0);
  assert.equal(view.body.children.length, 0, "no row is drawn");
  assert.equal(view.empty.hidden, false, "the empty state is shown");
});

test("the committed file is the generated script, and it holds metrics", () => {
  const generated = loadGenerated();

  assert.match(generatedSource, /do not edit/, "the file says it is generated");
  assert.ok(generated.metrics.length > 0, "the file holds metrics");
  assert.ok(generated.datasets.length > 0, "the file holds datasets");
});

test("the check is held to the way it could pass wrongly", () => {
  const { view, rows } = drawRealRows();

  assert.deepEqual(
    numbersMissingTheirDataset(rows, view.module),
    [],
    "the check passes on the real rows first",
  );

  const measured = rows.find((row) =>
    view.module.showsANumber(row.children[1].textContent.trim()),
  );
  assert.ok(measured, "the file shows at least one number");
  measured.children[DATASET_COLUMN].own = "";

  assert.deepEqual(
    numbersMissingTheirDataset([measured], view.module),
    [
      {
        row: 1,
        metric: firstLine(measured.children[0].textContent),
        result: measured.children[RESULT_COLUMN].textContent.trim(),
        dataset: "",
      },
    ],
    "a number with its dataset reference removed must be reported",
  );
});

test("the page ships a container and no sample row", () => {
  assert.match(pageHtml, /<tbody id="results-body"><\/tbody>/);
  assert.doesNotMatch(pageHtml, /<tbody id="results-body">\s*<tr/);
  assert.match(pageHtml, /class="ux4g-table ux4g-table-m ux4g-table-responsive"/);
  for (const heading of ["Metric", "Result", "Source", "Dataset", "Read by"]) {
    assert.ok(
      pageHtml.includes('<th scope="col">' + heading + "</th>"),
      "the table heads " + heading,
    );
  }
});

test("the page loads the metrics before the view that reads them", () => {
  const metrics = pageHtml.indexOf('src="./results-metrics.js"');
  const view = pageHtml.indexOf('src="./results.js"');

  assert.ok(metrics > 0, "the page loads the generated metrics");
  assert.ok(view > metrics, "the metrics load first");
});

test("the build copies both scripts and renders the page", () => {
  assert.ok(pageFileNames.includes("results.html"), "the page is rendered");
  assert.ok(staticFiles.includes("results.js"), "the view is copied");
  assert.ok(
    staticFiles.includes("results-metrics.js"),
    "the generated metrics are copied",
  );
});

test("every class the view writes is in the installed stylesheet", () => {
  const written = new Set(
    [...viewSource.matchAll(/"(ux4g-[a-z0-9-]+)"/g)].map((match) => match[1]),
  );

  assert.ok(written.size > 0, "the view writes UX4G classes");
  for (const name of written) {
    assert.ok(sheet.includes("." + name), name + " is not in ux4g.css");
  }
});