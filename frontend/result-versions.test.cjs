const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const { buildFileNames } = require("./build.cjs");

const source = fs.readFileSync(path.join(__dirname, "result-versions.js"), "utf8");
const sheet = fs.readFileSync(
  path.join(__dirname, "node_modules", "ux4g-web-components", "styles", "ux4g.css"),
  "utf8",
);

const TEXT_NODE = 3;

// The smallest element the panel can be built on: the classes, the
// attributes, the text and the children, and nothing else, so a property
// nobody implemented here would throw rather than pass quietly.
function createElement(tagName = "div") {
  const classes = new Set();
  const attributes = {};
  return {
    tagName: tagName.toUpperCase(),
    nodeType: 1,
    classes: classes,
    attributes: attributes,
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
    setAttribute: function (name, value) {
      attributes[name] = String(value);
    },
    appendChild: function (child) {
      this.children.push(child);
      return child;
    },
    removeChild: function (child) {
      const at = this.children.indexOf(child);
      if (at < 0) {
        throw new Error("the panel removed a card it never drew");
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

// The module answers in another realm, so its arrays carry another realm's
// prototype: they are read back into this one before anything is compared.
function host(value) {
  return Array.from(value);
}

// fetch and FormData are recorders rather than absences, so a send is visible
// to fail on rather than silently absent: the panel reads one stored result
// and must reach no endpoint for any of it.
function loadPanel() {
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
      throw new Error("the version panel must not send anything");
    },
    FormData: function () {
      sent.formData += 1;
      throw new Error("the version panel must not build a request");
    },
  };
  vm.runInNewContext(source, sandbox);
  return {
    panel: sandbox.window.DRISHTI_RESULT_VERSIONS,
    created: created,
    sent: sent,
  };
}

function bind(module, options = {}) {
  const container = createElement();
  const controller = module.bindResultVersions({ container: container, ...options });
  return { controller: controller, container: container };
}

// The block as the page receives it: the card, the heading row with its tag,
// and the three rows of the table, each label beside the lines of its value.
function drawn(container) {
  const [card] = container.children;
  const [heading, table] = card.children;
  const [title, tag] = heading.children;
  const [caption, body] = table.children;
  const rows = body.children.map(function (row) {
    const [head, cell] = row.children;
    return {
      row: row,
      head: head,
      cell: cell,
      label: textOf(head),
      lines: cell.children.map(textOf),
      text: textOf(cell),
    };
  });
  return {
    card: card,
    heading: heading,
    table: table,
    title: title,
    tag: tag,
    caption: caption,
    body: body,
    rows: rows,
    text: textOf(card),
  };
}

function refuses(call, code) {
  assert.throws(call, (error) => {
    assert.equal(error.name, "ResultVersionsError");
    assert.equal(error.code, code);
    return true;
  });
}

// One stored result, spelled as app/schemas.py spells it.
const RESULT = {
  ruleset_version: "0.2.0",
  model_versions: { tier2_morph: "morph-0.9.0", tier1_faces: "arcface-1.2.0" },
  prompt_version: "0.1.0",
};

const MODEL_LINES = ["tier1_faces: arcface-1.2.0", "tier2_morph: morph-0.9.0"];

test("the three versions are shown and the block is labelled experimental", () => {
  const { panel } = loadPanel();
  const { controller, container } = bind(panel);
  controller.render(RESULT);
  const block = drawn(container);

  assert.deepEqual(block.rows.map((row) => row.label), [
    panel.RULESET_LABEL,
    panel.MODELS_LABEL,
    panel.PROMPT_LABEL,
  ]);
  assert.deepEqual(block.rows.map((row) => row.lines), [
    ["0.2.0"],
    MODEL_LINES,
    ["0.1.0"],
  ]);

  assert.equal(textOf(block.title), panel.HEADING);
  assert.equal(textOf(block.tag), panel.EXPERIMENTAL_LABEL);
  assert.equal(panel.EXPERIMENTAL_LABEL, "Experimental");
  assert.ok(block.tag.classes.has("ux4g-tag"));
  assert.ok(block.tag.classes.has("ux4g-tag-s"));
  // Warning-toned rather than error-toned: what the versions qualify is
  // advice, not a fault.
  assert.ok(block.tag.classes.has("ux4g-tag-filled-warning"));
  assert.ok(!block.tag.classes.has("ux4g-tag-filled-error"));
  assert.match(block.text, /Experimental/);

  assert.ok(controller.experimental());
  assert.equal(controller.ruleset(), "0.2.0");
  assert.equal(controller.prompt(), "0.1.0");
  assert.deepEqual(
    host(controller.models()).map((model) => model.module),
    ["tier1_faces", "tier2_morph"],
  );
});

test("the caption names the block and its experimental label for a screen reader", () => {
  const { panel } = loadPanel();
  const { controller, container } = bind(panel);
  controller.render(RESULT);
  const block = drawn(container);
  const caption = textOf(block.caption);

  assert.ok(block.caption.classes.has(panel.CAPTION_CLASS));
  assert.equal(caption, panel.CAPTION_TEXT);
  assert.match(caption, /ruleset/i);
  assert.match(caption, /model/i);
  assert.match(caption, /prompt/i);
  assert.match(caption, /experimental/i);
});

test("every version sits beside a row header that names it", () => {
  const { panel } = loadPanel();
  const { controller, container } = bind(panel);
  controller.render(RESULT);
  const block = drawn(container);

  assert.equal(block.rows.length, 3);
  for (const row of block.rows) {
    assert.equal(row.head.tagName, "TH");
    assert.equal(row.head.attributes.scope, "row");
    assert.equal(row.cell.tagName, "TD");
    assert.ok(row.cell.classes.has(panel.CELL_CLASS));
  }
});

test("every UX4G class the module writes is a class the sheet ships", () => {
  const { panel } = loadPanel();
  const { controller, container } = bind(panel);
  controller.render(RESULT);
  const block = drawn(container);

  const written = [
    ...block.card.classes,
    ...block.heading.classes,
    ...block.tag.classes,
    ...block.table.classes,
    ...block.caption.classes,
    ...block.rows.flatMap((row) => [...row.cell.classes]),
  ];
  assert.ok(written.length > 0);
  const names = host(written);
  for (const name of names) {
    assert.ok(
      name.startsWith("ux4g-"),
      name + " is not a UX4G class, so the sheet does not style it",
    );
    assert.ok(
      sheet.includes("." + name),
      name + " is not a class in ux4g-web-components@2.1.0",
    );
  }
  // The sheet ships a table and a tag for all of this, so no class of this
  // project's own is written and the G9 list is unchanged.
  assert.deepEqual(
    names.filter((name) => !name.startsWith("ux4g-")),
    [],
  );
});

test("a result carrying no version names none and invents none", () => {
  const { panel } = loadPanel();
  const { controller, container } = bind(panel);
  for (const result of [{}, null, undefined, [], "0.2.0"]) {
    controller.render(result);
    const block = drawn(container);
    assert.deepEqual(
      block.rows.map((row) => row.lines),
      [[panel.ABSENT_TEXT], [panel.ABSENT_TEXT], [panel.ABSENT_TEXT]],
      JSON.stringify(result),
    );
    // The block is still labelled: an absent version is not a reason to stop
    // saying the result is experimental.
    assert.equal(textOf(block.tag), panel.EXPERIMENTAL_LABEL);
    assert.equal(controller.ruleset(), null);
    assert.equal(controller.prompt(), null);
    assert.deepEqual(host(controller.models()), []);
  }
  assert.equal(panel.ABSENT_TEXT, "Not recorded");
});

test("an empty model set names no model rather than an empty version", () => {
  const { panel } = loadPanel();
  const { controller, container } = bind(panel);
  controller.render({
    ruleset_version: "0.2.0",
    model_versions: {},
    prompt_version: "0.1.0",
  });
  const block = drawn(container);

  assert.deepEqual(block.rows.map((row) => row.lines), [
    ["0.2.0"],
    [panel.ABSENT_TEXT],
    ["0.1.0"],
  ]);
  assert.deepEqual(host(controller.models()), []);
});

test("the same model set reads the same way whatever order it arrives in", () => {
  const { panel } = loadPanel();
  const { controller, container } = bind(panel);
  const orders = [
    { tier1_faces: "arcface-1.2.0", tier2_morph: "morph-0.9.0" },
    { tier2_morph: "morph-0.9.0", tier1_faces: "arcface-1.2.0" },
    {
      tier0_mrz: "icao-1.0.0",
      tier1_faces: "arcface-1.2.0",
      tier2_morph: "morph-0.9.0",
    },
  ];
  for (const model_versions of orders) {
    controller.render({ ruleset_version: "0.2.0", model_versions: model_versions });
    const shown = drawn(container).rows[1].lines;
    assert.deepEqual(shown, [...shown].sort(), "the model lines are not in order");
    for (const module of Object.keys(model_versions)) {
      assert.ok(shown.some((line) => line.startsWith(module + panel.MODEL_SEPARATOR)));
    }
  }
  controller.render(RESULT);
  assert.deepEqual(drawn(container).rows[1].lines, MODEL_LINES);
});

test("an inherited property is not a model, and an own key still is", () => {
  const { panel } = loadPanel();
  const { controller, container } = bind(panel);
  const inherited = Object.create({ tier1_faces: "arcface-1.2.0" });
  inherited.tier2_morph = "morph-0.9.0";

  controller.render({ model_versions: inherited });
  assert.deepEqual(drawn(container).rows[1].lines, ["tier2_morph: morph-0.9.0"]);

  // A key that shadows an inherited one is a module name this row carries,
  // and the panel displays it rather than looking it up.
  controller.render({ model_versions: { toString: "0.0.1" } });
  assert.deepEqual(drawn(container).rows[1].lines, ["toString: 0.0.1"]);
});

test("a version nobody could quote is refused by name", () => {
  const { panel } = loadPanel();
  const { controller } = bind(panel);
  for (const value of [42, 0, "", "   ", true, [], {}, ["0.2.0"]]) {
    refuses(
      () => controller.render({ ruleset_version: value }),
      "bad_ruleset_version",
    );
    refuses(
      () => controller.render({ prompt_version: value }),
      "bad_prompt_version",
    );
  }
});

test("a model set that is not module to version is refused by name", () => {
  const { panel } = loadPanel();
  const { controller } = bind(panel);
  for (const value of [
    [],
    ["arcface-1.2.0"],
    "arcface-1.2.0",
    3,
    true,
    { tier1_faces: 3 },
    { tier1_faces: null },
    { tier1_faces: undefined },
    { tier1_faces: "" },
    { tier1_faces: "  " },
    { tier1_faces: {} },
    { "  ": "arcface-1.2.0" },
    { "": "arcface-1.2.0" },
  ]) {
    refuses(
      () => controller.render({ model_versions: value }),
      "bad_model_versions",
      JSON.stringify(value),
    );
  }
});

test("a version read and refused leaves the panel exactly as it was", () => {
  const { panel } = loadPanel();
  const { controller, container } = bind(panel);
  controller.render(RESULT);
  const before = drawn(container);

  for (const bad of [
    { given: { ruleset_version: 5 }, code: "bad_ruleset_version" },
    { given: { prompt_version: "" }, code: "bad_prompt_version" },
    { given: { model_versions: { tier1_faces: 5 } }, code: "bad_model_versions" },
  ]) {
    refuses(() => controller.render(bad.given), bad.code);
    assert.equal(container.children.length, 1);
    assert.equal(container.children[0], before.card);
    assert.equal(textOf(container.children[0]), before.text);
  }
  assert.equal(controller.ruleset(), "0.2.0");
});

test("a binding is refused by cause when it has no container", () => {
  const { panel } = loadPanel();
  refuses(() => panel.bindResultVersions(), "missing_element");
  refuses(() => panel.bindResultVersions({}), "missing_element");
  assert.deepEqual(host(panel.REQUIRED_ELEMENTS), ["container"]);
});

test("clearing takes away only the block this module drew", () => {
  const { panel } = loadPanel();
  const { controller, container } = bind(panel);
  const own = createElement();
  container.appendChild(own);
  assert.equal(controller.clear(), false);
  assert.equal(controller.experimental(), false);

  controller.render(RESULT);
  assert.equal(controller.clear(), true);
  assert.equal(controller.experimental(), false);
  assert.equal(controller.ruleset(), null);
  assert.deepEqual(host(controller.models()), []);
  assert.equal(controller.prompt(), null);
  assert.equal(controller.clear(), false);
  assert.deepEqual(container.children, [own]);
});

test("the panel sends nothing and builds no request", () => {
  const { panel, sent } = loadPanel();
  const { controller } = bind(panel);
  controller.render(RESULT);
  controller.render({});
  assert.deepEqual(sent, { fetches: 0, formData: 0 });
});

test("no page loads the panel yet, so the build copies nothing", () => {
  const { staticFiles, pageFileNames } = buildFileNames();
  const pages = pageFileNames.map((fileName) =>
    fs.readFileSync(path.join(__dirname, fileName), "utf8"),
  );
  const shell = fs.readFileSync(path.join(__dirname, "shell.html"), "utf8");

  assert.ok(!staticFiles.includes("result-versions.js"));
  for (const markup of [...pages, shell]) {
    assert.doesNotMatch(markup, /result-versions\.js/);
  }
});