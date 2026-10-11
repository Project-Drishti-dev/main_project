const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const { buildFileNames } = require("./build.cjs");

const source = fs.readFileSync(
  path.join(__dirname, "result-skeleton.js"),
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

function createElement(tagName = "div", classes = []) {
  const element = {
    tagName: tagName.toUpperCase(),
    attributes: new Map(),
    classes: new Set(classes),
    classList: new Set(classes),
    children: [],
    hidden: false,
    setAttribute(name, value) {
      this.attributes.set(name, String(value));
    },
    getAttribute(name) {
      return this.attributes.has(name) ? this.attributes.get(name) : null;
    },
    add(child) {
      this.children.push(child);
      return child;
    },
    // The module finds its shapes with one attribute-contains selector, so the
    // fake serves that selector and refuses any other rather than answering
    // whatever a caller happens to ask for.
    querySelectorAll(selector) {
      assert.equal(
        selector,
        '[class*="ux4g-skeleton-"]',
        "the shapes are found by the one documented class prefix",
      );
      const found = [];
      const walk = (node) => {
        for (const child of node.children) {
          for (const name of child.classes) {
            if (name.startsWith("ux4g-skeleton-")) {
              found.push(child);
              break;
            }
          }
          walk(child);
        }
      };
      walk(this);
      return found;
    },
  };
  return element;
}

// The skeleton a result page carries while its screening runs: the card's own
// title, subtitle and main surface, the sidebar card with a block inside it,
// the band circle and the decision button. Seven shapes, none of them the
// container itself, and markup that ships in the settled state -- the skeleton
// off and the result on -- which is what a result page looks like before it
// has anything to wait for.
function createMarkup() {
  const loading = createElement("div", ["result-loading"]);
  const surface = createElement("section", ["result-surface"]);
  const card = loading.add(createElement("div", ["ux4g-card"]));
  const sidebarCard = loading.add(
    createElement("aside", ["ux4g-skeleton-sidebar-card"]),
  );
  const shapes = {
    title: card.add(createElement("h2", ["ux4g-skeleton-title"])),
    subtitle: card.add(createElement("p", ["ux4g-skeleton-subtitle"])),
    main: card.add(createElement("div", ["ux4g-skeleton-main"])),
    sidebarCard: sidebarCard,
    block: sidebarCard.add(createElement("div", ["ux4g-skeleton-block"])),
    circle: loading.add(createElement("span", ["ux4g-skeleton-circle"])),
    button: loading.add(createElement("button", ["ux4g-skeleton-btn"])),
  };
  const markup = { loading, surface, shapes };
  drawMarkup(markup, false);
  return markup;
}

function drawMarkup(markup, drawing) {
  markup.loading.hidden = !drawing;
  markup.loading.setAttribute("aria-busy", drawing ? "true" : "false");
  for (const shape of Object.values(markup.shapes)) {
    shape.hidden = !drawing;
  }
  markup.surface.hidden = drawing;
}

function ariaOf(element, name) {
  return element.getAttribute(name);
}

function visibleShapes(markup) {
  return Object.values(markup.shapes).filter((shape) => !shape.hidden);
}

// One sandbox per binding, with fetch and FormData as recorders rather than
// absences: the claim is that this module sends nothing, so the test has to be
// able to see a send.
function loadSkeleton(options = {}) {
  const sent = { fetches: 0, formData: 0 };
  const markup = Object.prototype.hasOwnProperty.call(options, "markup")
    ? options.markup
    : createMarkup();
  const sandbox = {
    window: {},
    fetch() {
      sent.fetches += 1;
      throw new Error("the loading state must not send anything");
    },
    FormData() {
      sent.formData += 1;
      throw new Error("the loading state must not build a request");
    },
  };
  vm.runInNewContext(
    Object.prototype.hasOwnProperty.call(options, "source")
      ? options.source
      : source,
    sandbox,
  );
  const skeleton = sandbox.window.DRISHTI_RESULT_SKELETON;
  const settings = Object.prototype.hasOwnProperty.call(options, "settings")
    ? options.settings
    : { loading: markup.loading, surface: markup.surface };
  return {
    skeleton,
    controller: skeleton.bindResultSkeleton(settings),
    markup,
    sent,
  };
}

test("the skeleton appears while the screening runs and is removed when it lands", () => {
  const { controller, markup } = loadSkeleton();

  assert.equal(controller.pending(), false);
  assert.deepEqual(visibleShapes(markup), []);
  assert.equal(markup.surface.hidden, false);

  assert.equal(controller.show(), true);
  assert.equal(controller.pending(), true);
  assert.equal(markup.loading.hidden, false);
  assert.equal(visibleShapes(markup).length, 7);
  assert.equal(markup.surface.hidden, true);

  assert.equal(controller.hide(), true);
  assert.equal(controller.pending(), false);
  assert.equal(markup.loading.hidden, true);
  assert.deepEqual(visibleShapes(markup), []);
  assert.equal(markup.surface.hidden, false);
});

test("every shape is switched in its own right, so none is left behind", () => {
  const { controller, markup } = loadSkeleton();

  controller.show();
  assert.deepEqual(
    Object.values(markup.shapes).filter((shape) => shape.hidden),
    [],
  );

  controller.hide();
  assert.deepEqual(
    Object.values(markup.shapes).filter((shape) => !shape.hidden),
    [],
  );
});

test("the shapes are the seven the design system ships, at any depth", () => {
  const { controller, skeleton, markup } = loadSkeleton();

  assert.equal(controller.shapes(), 7);
  assert.deepEqual(controller.classes(), skeleton.SHAPE_CLASSES);
  assert.ok(
    !skeleton.SHAPE_CLASSES.includes("result-loading"),
    "the container is not one of its own shapes",
  );
  assert.ok(
    !Array.from(markup.loading.classes).some((name) =>
      name.startsWith(skeleton.SHAPE_PREFIX),
    ),
    "the container carries no shape class of its own",
  );
});

test("one skeleton at a time: showing twice is one skeleton", () => {
  const { controller, markup } = loadSkeleton();

  assert.equal(controller.show(), true);
  assert.equal(controller.show(), false);
  assert.equal(controller.pending(), true);
  assert.equal(visibleShapes(markup).length, 7);

  assert.equal(controller.hide(), true);
  assert.equal(controller.hide(), false);
  assert.equal(controller.pending(), false);
  assert.deepEqual(visibleShapes(markup), []);
});

test("markup that ships the skeleton drawn starts pending, with no first paint to fight", () => {
  const markup = createMarkup();
  drawMarkup(markup, true);
  const { controller } = loadSkeleton({ markup: markup });

  assert.equal(controller.pending(), true);
  assert.equal(controller.hide(), true);
  assert.equal(controller.pending(), false);
  assert.deepEqual(visibleShapes(markup), []);
  assert.equal(markup.surface.hidden, false);
});

test("a loading state with no shape is refused rather than bound", () => {
  const markup = createMarkup();
  const empty = createElement("div", ["result-loading"]);
  empty.hidden = true;

  assert.throws(
    () => loadSkeleton({ settings: { loading: empty, surface: markup.surface } }),
    (error) => error.code === "no_shapes",
  );
  assert.throws(
    () =>
      loadSkeleton({
        settings: {
          loading: createElement("div", ["ux4g-card"]),
          surface: markup.surface,
        },
      }),
    (error) => error.code === "no_shapes",
  );
});

test("a skeleton class the design system does not ship is refused by name", () => {
  const markup = createMarkup();
  markup.shapes.title.classes.add("ux4g-skeleton-heading");
  markup.shapes.title.classList.add("ux4g-skeleton-heading");

  assert.throws(
    () => loadSkeleton({ markup: markup }),
    (error) =>
      error.code === "unknown_shape" &&
      error.message.includes("ux4g-skeleton-heading"),
  );
  assert.doesNotMatch(
    source,
    /ux4g-skeleton-heading/,
    "the module does not itself carry the invented shape",
  );
});

test("a missing element is refused by name, in both directions", () => {
  const markup = createMarkup();

  assert.throws(
    () => loadSkeleton({ settings: { surface: markup.surface } }),
    (error) =>
      error.code === "missing_element" && error.message.includes("loading"),
  );
  assert.throws(
    () => loadSkeleton({ settings: { loading: markup.loading } }),
    (error) =>
      error.code === "missing_element" && error.message.includes("surface"),
  );
  assert.equal(loadSkeleton({ markup: markup }).controller.pending(), false);
});

test("a skeleton and a result both on the page is refused", () => {
  const markup = createMarkup();
  drawMarkup(markup, true);
  markup.surface.hidden = false;

  assert.throws(
    () => loadSkeleton({ markup: markup }),
    (error) => error.code === "both_visible",
  );
});

test("the shape list is read out of the installed stylesheet, size-free", () => {
  const { skeleton } = loadSkeleton();
  const shipped = [
    ...new Set(stylesheet.match(/\.ux4g-skeleton[a-z-]*/g)),
  ]
    .map((selector) => selector.slice(1))
    .sort();

  assert.deepEqual(shipped, [...skeleton.SHAPE_CLASSES].sort());
  assert.ok(
    !shipped.some((name) => /-(sm|md|lg|xl)$/.test(name)),
    "the skeleton ships one size, so no shape carries a size modifier",
  );
});

test("a shape switched only by its container is a mutation this file kills", () => {
  const dropped = source.replace("shape.hidden = !drawing_;", "");
  assert.notEqual(dropped, source, "the mutation must have changed the source");

  const real = loadSkeleton();
  const mutated = loadSkeleton({ source: dropped });

  real.controller.show();
  assert.equal(visibleShapes(real.markup).length, 7);

  mutated.controller.show();
  assert.equal(
    visibleShapes(mutated.markup).length,
    0,
    "the container is up but every shape is still hidden behind it",
  );

  real.controller.hide();
  mutated.controller.hide();
  assert.deepEqual(visibleShapes(real.markup), []);
});

test("a result left on the page behind the skeleton is a mutation this file kills", () => {
  const dropped = source.replace("surface.hidden = drawing_;", "");
  assert.notEqual(dropped, source, "the mutation must have changed the source");

  const real = loadSkeleton();
  const mutated = loadSkeleton({ source: dropped });
  real.controller.show();
  mutated.controller.show();

  assert.equal(real.markup.surface.hidden, true);
  assert.equal(
    mutated.markup.surface.hidden,
    false,
    "the skeleton is up and so is the result behind it",
  );
});

test("the loading state announces that it is busy, and hides the shapes", () => {
  const { controller, markup, skeleton } = loadSkeleton();
  const shapes = Object.values(markup.shapes);

  assert.equal(markup.loading.hidden, true, "the markup ships settled");
  assert.equal(ariaOf(markup.loading, skeleton.BUSY_ATTRIBUTE), skeleton.IDLE_VALUE);
  for (const shape of shapes) {
    assert.equal(
      ariaOf(shape, skeleton.DECORATIVE_ATTRIBUTE),
      skeleton.DECORATIVE_VALUE,
      "a shape standing in for content is not content",
    );
  }

  controller.show();
  assert.equal(
    ariaOf(markup.loading, skeleton.BUSY_ATTRIBUTE),
    skeleton.BUSY_VALUE,
    "the page is waiting on a screening",
  );

  controller.hide();
  assert.equal(
    ariaOf(markup.loading, skeleton.BUSY_ATTRIBUTE),
    skeleton.IDLE_VALUE,
    "the answer landed, so nothing is being fetched into",
  );
  for (const shape of shapes) {
    assert.equal(
      ariaOf(shape, skeleton.DECORATIVE_ATTRIBUTE),
      skeleton.DECORATIVE_VALUE,
      "a hidden shape is still not content",
    );
  }
});

test("a container that never says it is busy is a mutation this file kills", () => {
  const dropped = source.replace("        drawing_ ? BUSY_VALUE : IDLE_VALUE,", "        IDLE_VALUE,");
  assert.notEqual(dropped, source, "the mutation must have changed the source");

  const real = loadSkeleton();
  const mutated = loadSkeleton({ source: dropped });
  real.controller.show();
  mutated.controller.show();

  assert.equal(
    ariaOf(real.markup.loading, "aria-busy"),
    "true",
    "the real container announces the wait",
  );
  assert.equal(
    ariaOf(mutated.markup.loading, "aria-busy"),
    "false",
    "the mutated container is drawn and silent",
  );
});

test("a shape a screen reader reads out is a mutation this file kills", () => {
  const dropped = source.replace(
    "      shape.setAttribute(DECORATIVE_ATTRIBUTE, DECORATIVE_VALUE);",
    "",
  );
  assert.notEqual(dropped, source, "the mutation must have changed the source");

  const real = loadSkeleton();
  const mutated = loadSkeleton({ source: dropped });

  assert.equal(ariaOf(real.markup.shapes.title, "aria-hidden"), "true");
  assert.equal(
    ariaOf(mutated.markup.shapes.title, "aria-hidden"),
    null,
    "the mutated shape is announced as if it were content",
  );
});

test("the loading state sends nothing", () => {
  const { controller, sent } = loadSkeleton();
  controller.show();
  controller.hide();

  assert.deepEqual(sent, { fetches: 0, formData: 0 });
  assert.doesNotMatch(
    source,
    /DRISHTI_API|fetch\(|FormData\(|localStorage|sessionStorage/,
  );
});

test("no page loads the module yet, so the build copies nothing", () => {
  const { staticFiles, pageFileNames } = buildFileNames();
  const pages = pageFileNames.map((fileName) =>
    fs.readFileSync(path.join(__dirname, fileName), "utf8"),
  );
  const shell = fs.readFileSync(path.join(__dirname, "shell.html"), "utf8");

  assert.ok(!staticFiles.includes("result-skeleton.js"));
  for (const markup of [...pages, shell]) {
    assert.doesNotMatch(markup, /result-skeleton\.js/);
  }
});