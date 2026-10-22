const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const { buildFileNames } = require("./build.cjs");

const source = fs.readFileSync(
  path.join(__dirname, "progress-panel.js"),
  "utf8",
);
const stylesheet = fs.readFileSync(
  path.join(
    __dirname,
    "node_modules",
    "ux4g-web-components",
    "styles",
    "ux4g.css",
  ),
  "utf8",
);

// The smallest element the panel can build with: the attributes, classes,
// text and one custom property it writes, and nothing else, so a property
// nobody implemented here would throw rather than pass quietly.
function createElement(tagName) {
  const attributes = new Map();
  const classes = new Set();
  const properties = new Map();
  return {
    tagName: tagName.toUpperCase(),
    classes: classes,
    attributes: attributes,
    properties: properties,
    children: [],
    textContent: "",
    classList: {
      add: function (name) {
        classes.add(name);
      },
    },
    style: {
      setProperty: function (name, value) {
        properties.set(name, value);
      },
    },
    setAttribute: function (name, value) {
      attributes.set(name, String(value));
    },
    getAttribute: function (name) {
      return attributes.has(name) ? attributes.get(name) : null;
    },
    removeAttribute: function (name) {
      attributes.delete(name);
    },
    appendChild: function (child) {
      this.children.push(child);
      return child;
    },
  };
}

// One sandbox per panel, with fetch and FormData as recorders rather than
// absences: the claim is that this module sends nothing, so a send has to be
// visible to fail on.
function newSandbox(options = {}) {
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
    },
    fetch: function () {
      sent.fetches += 1;
      throw new Error("the progress panel must not send anything");
    },
    FormData: function () {
      sent.formData += 1;
      throw new Error("the progress panel must not build a request");
    },
  };
  if (options.noDocument === true) {
    delete sandbox.document;
  }
  return { sandbox: sandbox, created: created, sent: sent };
}

function loadPanel(options = {}) {
  const context = newSandbox(options);
  vm.runInNewContext(
    Object.prototype.hasOwnProperty.call(options, "source")
      ? options.source
      : source,
    context.sandbox,
  );
  const panel = context.sandbox.window.DRISHTI_PROGRESS_PANEL;
  const container = createElement("div");
  const controller = panel.bindProgressPanel({ container: container });
  return {
    panel: panel,
    controller: controller,
    container: container,
    created: context.created,
    sent: context.sent,
  };
}

// The two shapes the service writes (app/progress.py), built from its own
// words so a case cannot pass against a step the cascade never produces.
function tierStep(tier) {
  return { unit: "tier", state: "completed", tier: tier, module: null };
}

function moduleStep(moduleName, tier) {
  return {
    unit: "module",
    state: "reported",
    tier: tier,
    module: moduleName,
  };
}

test("the panel is the components the design system ships, and nothing else", () => {
  const { controller, container, created, panel } = loadPanel();
  const bar = controller.bar;

  assert.equal(container.children.length, 2);
  assert.equal(container.children[0], bar);
  assert.equal(container.children[1], controller.live);

  assert.equal(bar.getAttribute(panel.BAR_MARKER), "");
  assert.equal(bar.getAttribute("data-ux-shape"), "rounded");
  assert.equal(bar.getAttribute("data-ux-label-placement"), "outside");

  const track = bar.children[0];
  const fill = track.children[0];
  const label = bar.children[1];
  assert.deepEqual(Array.from(track.classes), [panel.TRACK_CLASS]);
  assert.deepEqual(Array.from(fill.classes), [panel.FILL_CLASS]);
  assert.equal(label.getAttribute(panel.LABEL_ATTRIBUTE), "");
  assert.equal(created.length, 5, "bar, track, fill, label and the live region");

  for (const selector of [
    "." + panel.TRACK_CLASS,
    "." + panel.FILL_CLASS,
    "[" + panel.BAR_MARKER + "]",
    "[data-ux-shape=rounded]",
    "[data-ux-label-placement=outside]",
    "[" + panel.LABEL_ATTRIBUTE + "]",
  ]) {
    assert.ok(
      stylesheet.includes(selector),
      "the installed stylesheet ships " + selector,
    );
  }

  const written = [panel.TRACK_CLASS, panel.FILL_CLASS];
  for (const name of written) {
    assert.doesNotMatch(name, /-(sm|md|lg|xl)$/, "the bar ships one size");
  }
});

test("the bar is a progressbar, and the region beside it is polite", () => {
  const { controller, panel } = loadPanel();
  const bar = controller.bar;

  assert.equal(bar.getAttribute("role"), "progressbar");
  assert.equal(bar.getAttribute("aria-valuemin"), "0");
  assert.equal(bar.getAttribute("aria-valuemax"), "100");
  assert.equal(bar.getAttribute("aria-label"), panel.BAR_NAME);
  assert.ok(bar.getAttribute("aria-label"), "the role carries a name");

  assert.equal(controller.live.getAttribute("role"), "status");
  assert.equal(controller.live.getAttribute("aria-live"), "polite");

  assert.equal(
    bar.getAttribute("aria-valuenow"),
    null,
    "the run's own step count is unknown, so the bar is indeterminate",
  );
});

test("the bar has a text alternative, and it is the sentence on screen", () => {
  const { controller } = loadPanel();
  const bar = controller.bar;
  const label = bar.children[1];

  assert.equal(controller.status(), bar.getAttribute("aria-valuetext"));
  assert.ok(controller.status(), "the bar names what it is showing");
  assert.equal(
    label.textContent,
    bar.getAttribute("aria-valuetext"),
    "the visible label and aria-valuetext are one string, not two claims",
  );

  controller.step(tierStep("crossdoc"), 0);
  assert.equal(label.textContent, bar.getAttribute("aria-valuetext"));
  assert.equal(controller.status(), "1 step reported.");

  controller.step(moduleStep("mrz_check", "tier0"), 1);
  assert.equal(controller.status(), "2 steps reported.");
  assert.equal(label.textContent, "2 steps reported.");
});

test("the bar starts empty rather than at the 50 the sheet ships", () => {
  const { controller, panel } = loadPanel();

  assert.ok(
    stylesheet.includes(panel.VALUE_VARIABLE + ":50"),
    "the sheet ships a half-full bar as its default",
  );
  assert.equal(controller.bar.properties.get(panel.VALUE_VARIABLE), "0");
});

test("a tier completion is announced, in the words the service wrote", () => {
  const { controller, panel } = loadPanel();

  const said = controller.step(tierStep("crossdoc"), 0);

  assert.equal(said, "Step 1: tier crossdoc completed.");
  assert.equal(controller.announced(), said);
  assert.equal(controller.steps(), 1);
  assert.ok(
    panel.statusText(1, null) !== said,
    "the announcement and the bar text answer different questions",
  );
});

test("a module step is announced as a module, never as a tier", () => {
  const { controller } = loadPanel();

  const said = controller.step(moduleStep("mrz_check", "tier0"), 0);

  assert.equal(said, "Step 1: module mrz_check reported under tier tier0.");
  assert.equal(controller.announced(), said);
  assert.ok(!said.includes("tier tier0 completed"));
});

test("the same tier twice is announced twice, because the index differs", () => {
  const { controller } = loadPanel();

  const first = controller.step(tierStep("quality"), 0);
  const second = controller.step(tierStep("quality"), 1);

  assert.notEqual(first, second);
  assert.equal(controller.announced(), second);
  assert.equal(controller.steps(), 2);
});

test("the drawn bar and the announced bar are one number", () => {
  const { controller, panel } = loadPanel();

  controller.step(tierStep("tier0"), 0);
  controller.step(moduleStep("mrz_check", "tier0"), 1);
  controller.step(tierStep("crossdoc"), 2);

  assert.equal(controller.complete(3), 100);

  assert.equal(controller.bar.getAttribute("aria-valuenow"), "100");
  assert.equal(controller.bar.properties.get(panel.VALUE_VARIABLE), "100");
  assert.equal(controller.value(), 100);
  assert.equal(controller.status(), "3 of 3 steps reported.");
  assert.equal(
    controller.bar.children[1].textContent,
    "3 of 3 steps reported.",
  );
  assert.equal(controller.announced(), panel.FINISHED_TEXT);
});

test("the percentage is the steps over the total, not a fixed hundred", () => {
  const { controller, panel } = loadPanel();

  controller.step(tierStep("tier0"), 0);
  controller.step(moduleStep("mrz_check", "tier0"), 1);

  assert.equal(controller.complete(4), 50);
  assert.equal(controller.bar.getAttribute("aria-valuenow"), "50");
  assert.equal(controller.bar.properties.get(panel.VALUE_VARIABLE), "50");
  assert.equal(controller.status(), "2 of 4 steps reported.");

  assert.equal(panel.statusText(0, null), panel.WAITING_TEXT);
  assert.equal(panel.statusText(1, null), "1 step reported.");
  assert.equal(panel.statusText(2, null), "2 steps reported.");
  assert.equal(panel.statusText(0, 0), "0 of 0 steps reported.");
});

test("a step naming no tier is refused by name, and draws nothing", () => {
  const { controller } = loadPanel();

  controller.step(tierStep("tier0"), 0);
  const before = controller.announced();

  assert.throws(
    () => controller.step({ unit: "tier", state: "completed" }, 1),
    (error) => error.code === "bad_tier",
  );
  assert.throws(
    () => controller.step({ unit: "tier", state: "completed", tier: 0 }, 1),
    (error) => error.code === "bad_tier",
  );

  assert.equal(controller.announced(), before);
  assert.equal(controller.steps(), 1);
});

test("a module step naming no module is refused by name", () => {
  const { controller } = loadPanel();

  assert.throws(
    () => controller.step({ unit: "module", state: "reported", tier: "tier0" }, 0),
    (error) => error.code === "bad_module",
  );
  assert.equal(controller.steps(), 0);
  assert.equal(controller.announced(), "");
});

test("a unit the service does not write is refused by name", () => {
  const { controller } = loadPanel();

  assert.throws(
    () => controller.step({ unit: "stage", state: "completed", tier: "tier0" }, 0),
    (error) => error.code === "bad_unit" && error.message.includes("stage"),
  );
  assert.throws(
    () => controller.step(null, 0),
    (error) => error.code === "bad_unit",
  );
  assert.equal(controller.steps(), 0);
});

test("a finished count that is not a whole number is refused", () => {
  const { controller } = loadPanel();
  controller.step(tierStep("tier0"), 0);

  for (const units of ["1", -1, 1.5, null]) {
    assert.throws(
      () => controller.complete(units),
      (error) => error.code === "bad_units",
    );
  }
  assert.equal(controller.total(), null);
  assert.equal(controller.bar.getAttribute("aria-valuenow"), null);
});

test("nothing is drawn twice: a step after the run finished changes nothing", () => {
  const { controller } = loadPanel();

  controller.step(tierStep("tier0"), 0);
  assert.equal(controller.complete(1), 100);
  const said = controller.announced();

  assert.equal(controller.step(tierStep("crossdoc"), 1), null);
  assert.equal(controller.complete(1), null);
  assert.equal(controller.announced(), said);
  assert.equal(controller.steps(), 1);
});

test("a stop freezes the panel, and only the first one takes", () => {
  const { controller } = loadPanel();
  controller.step(tierStep("tier0"), 0);

  assert.equal(controller.stop(), true);
  assert.equal(controller.stop(), false);
  assert.equal(controller.step(tierStep("crossdoc"), 1), null);
  assert.equal(controller.complete(2), null);
  assert.equal(controller.steps(), 1);
  assert.equal(controller.stopped(), true);
});

test("a panel with no container, or no page to build on, is refused by name", () => {
  const context = newSandbox();
  vm.runInNewContext(source, context.sandbox);
  const panel = context.sandbox.window.DRISHTI_PROGRESS_PANEL;

  assert.throws(
    () => panel.bindProgressPanel({}),
    (error) => error.code === "missing_element" && error.message.includes("container"),
  );

  const bare = newSandbox({ noDocument: true });
  vm.runInNewContext(source, bare.sandbox);
  assert.throws(
    () => bare.sandbox.window.DRISHTI_PROGRESS_PANEL.bindProgressPanel({
      container: createElement("div"),
    }),
    (error) => error.code === "no_document",
  );
});

test("the panel sends nothing and holds no address", () => {
  const { controller, sent } = loadPanel();

  controller.step(tierStep("tier0"), 0);
  controller.complete(1);

  assert.deepEqual(sent, { fetches: 0, formData: 0 });
  for (const forbidden of [
    "DRISHTI_API",
    "fetch(",
    "FormData",
    "EventSource",
    "localStorage",
    "sessionStorage",
  ]) {
    assert.ok(
      !source.includes(forbidden),
      "the panel does not mention " + forbidden,
    );
  }
});

test("a bar with no text alternative is a mutation this file kills", () => {
  const dropped = source.replace(
    'bar.setAttribute("aria-valuetext", sentence);',
    "",
  );
  assert.notEqual(dropped, source, "the mutation must have changed the source");

  const real = loadPanel();
  const mutated = loadPanel({ source: dropped });

  assert.ok(real.controller.status(), "the real bar carries a text alternative");
  assert.equal(
    mutated.controller.status(),
    null,
    "the mutated bar leaves a screen reader with nothing to read",
  );
});

test("a region that is not polite is a mutation this file kills", () => {
  const dropped = source.replace(
    'live.setAttribute("aria-live", LIVE_POLITENESS);',
    "",
  );
  assert.notEqual(dropped, source, "the mutation must have changed the source");

  const real = loadPanel();
  const mutated = loadPanel({ source: dropped });

  assert.equal(real.controller.live.getAttribute("aria-live"), "polite");
  assert.equal(
    mutated.controller.live.getAttribute("aria-live"),
    null,
    "the mutation leaves tier completions unannounced",
  );
});

test("a drawn bar that disagrees with the announced one is a mutation this file kills", () => {
  const dropped = source.replace(
    "bar.style.setProperty(VALUE_VARIABLE, String(percent));",
    "",
  );
  assert.notEqual(dropped, source, "the mutation must have changed the source");

  const real = loadPanel();
  const mutated = loadPanel({ source: dropped });

  real.controller.step(tierStep("tier0"), 0);
  mutated.controller.step(tierStep("tier0"), 0);
  real.controller.complete(1);
  mutated.controller.complete(1);

  assert.equal(real.controller.bar.properties.get("--ux4g-progress-value"), "100");
  assert.equal(
    mutated.controller.bar.properties.get("--ux4g-progress-value"),
    "0",
    "the bar announces a value its own fill no longer draws",
  );
  assert.equal(mutated.controller.bar.getAttribute("aria-valuenow"), "100");
});

test("no page loads the module yet, so the build copies nothing", () => {
  const { staticFiles, pageFileNames } = buildFileNames();
  const pages = pageFileNames.map((fileName) =>
    fs.readFileSync(path.join(__dirname, fileName), "utf8"),
  );
  const shell = fs.readFileSync(path.join(__dirname, "shell.html"), "utf8");

  assert.ok(!staticFiles.includes("progress-panel.js"));
  for (const markup of [...pages, shell]) {
    assert.doesNotMatch(markup, /progress-panel\.js/);
  }
});
