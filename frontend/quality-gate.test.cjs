const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const GATE_PATH = path.join(__dirname, "quality-gate.js");
const source = fs.readFileSync(GATE_PATH, "utf8");
const uploadSource = fs.readFileSync(path.join(__dirname, "upload.js"), "utf8");
const { buildFileNames } = require("./build.cjs");

const PASS_READING = { width: 1200, height: 900 };
const WARN_READING = { width: 320, height: 240 };

function createElement(tagName = "div") {
  const classes = new Set(["ux4g-alert", "ux4g-alert-content"]);
  const element = {
    tagName: tagName.toUpperCase(),
    attributes: {},
    classes,
    classList: {
      add: (name) => classes.add(name),
      remove: (name) => classes.delete(name),
      contains: (name) => classes.has(name),
    },
    listeners: {},
    hidden: false,
    value: "",
    alt: "",
    _textContent: "",
    get textContent() {
      return this._textContent;
    },
    set textContent(value) {
      this._textContent = String(value ?? "");
    },
    addEventListener(event, callback) {
      this.listeners[event] = callback;
    },
    setAttribute(name, value) {
      this.attributes[name] = value;
    },
    getAttribute(name) {
      return this.attributes[name] ?? null;
    },
    removeAttribute(name) {
      delete this.attributes[name];
    },
    click() {
      return this.listeners.click();
    },
  };
  return element;
}

function imageFile(overrides = {}) {
  return {
    name: "passport.jpg",
    type: "image/jpeg",
    size: 2048,
    ...overrides,
  };
}

// One sandbox per binding, with fetch and FormData as recorders rather than
// absences: the claim is that the gate sends nothing, so the test has to be
// able to see a send.
function loadQualityGate(options = {}) {
  const proceeded = [];
  const retakes = [];
  const sent = { fetches: 0, formData: 0 };
  const elements = {
    alert: createElement("div"),
    title: createElement("h3"),
    message: createElement("p"),
    retake: createElement("button"),
    anyway: createElement("button"),
  };
  const sandbox = {
    window: {},
    fetch() {
      sent.fetches += 1;
      throw new Error("the quality gate must not send anything");
    },
    FormData() {
      sent.formData += 1;
      throw new Error("the quality gate must not build a request");
    },
  };
  vm.runInNewContext(
    Object.prototype.hasOwnProperty.call(options, "source")
      ? options.source
      : source,
    sandbox,
  );
  const gate = sandbox.window.DRISHTI_QUALITY_GATE;
  const controller = gate.bindQualityGate({
    alert: elements.alert,
    title: elements.title,
    message: elements.message,
    retake: elements.retake,
    anyway: elements.anyway,
    onRetake: () => retakes.push(true),
    onProceed: () => proceeded.push(true),
  });
  return { gate, controller, elements, proceeded, retakes, sent };
}

function loadUploadAndGate(options = {}) {
  const proceeded = [];
  const objectUrls = [];
  let createdUrls = 0;
  const sent = { fetches: 0, formData: 0 };
  const elements = {
    input: createElement("input"),
    panel: createElement("div"),
    preview: createElement("img"),
    details: createElement("p"),
    error: createElement("p"),
    alert: createElement("div"),
    title: createElement("h3"),
    message: createElement("p"),
    retake: createElement("button"),
    anyway: createElement("button"),
  };
  const sandbox = {
    window: {},
    URL: {
      createObjectURL(file) {
        createdUrls += 1;
        const url = "blob:preview-" + createdUrls;
        objectUrls.push({ file, url });
        return url;
      },
      revokeObjectURL(url) {
        objectUrls.push({ revoked: url });
      },
    },
    fetch() {
      sent.fetches += 1;
      throw new Error("the quality gate must not send anything");
    },
    FormData() {
      sent.formData += 1;
      throw new Error("the quality gate must not build a request");
    },
  };
  // Both modules in one sandbox, and the retake wired to upload.clear() as
  // 22.2's page will wire it: the claim is that the file is gone afterwards,
  // so the test has to watch a real upload binding rather than a stub.
  vm.runInNewContext(uploadSource, sandbox);
  vm.runInNewContext(
    Object.prototype.hasOwnProperty.call(options, "source")
      ? options.source
      : source,
    sandbox,
  );
  const uploadController = sandbox.window.DRISHTI_UPLOAD.bindUpload({
    input: elements.input,
    panel: elements.panel,
    preview: elements.preview,
    details: elements.details,
    error: elements.error,
  });
  const gateController = sandbox.window.DRISHTI_QUALITY_GATE.bindQualityGate({
    alert: elements.alert,
    title: elements.title,
    message: elements.message,
    retake: elements.retake,
    anyway: elements.anyway,
    onRetake: () => uploadController.clear(),
    onProceed: () => proceeded.push(true),
  });
  return {
    uploadController,
    gateController,
    elements,
    objectUrls,
    proceeded,
    sent,
  };
}

function refuses(call, code, fragment) {
  assert.throws(call, (error) => {
    assert.equal(error.name, "QualityGateError");
    assert.equal(error.code, code);
    assert.ok(
      error.message.includes(fragment),
      "message was " + JSON.stringify(error.message),
    );
    return true;
  });
}

test("the floor is the service's own 150 PPI written in pixels, rounded down", () => {
  const { gate } = loadQualityGate();

  // m6_ppi refuses below 150 PPI on an 85.6 mm card: 150 * 85.6 / 25.4.
  const serviceFloor = Math.floor((150 * 85.6) / 25.4);
  assert.equal(gate.MIN_EDGE_PX, 500);
  assert.ok(
    gate.MIN_EDGE_PX <= serviceFloor && serviceFloor - gate.MIN_EDGE_PX < 10,
    "the client floor must be the service's floor, not a number of its own",
  );
});

test("the boundary is exact in both directions, on the shorter edge", () => {
  const { gate } = loadQualityGate();

  assert.equal(gate.check({ width: 500, height: 2000 }).status, "pass");
  assert.equal(gate.check({ width: 500, height: 499 }).status, "warn");
  assert.equal(gate.check({ width: 499, height: 500 }).status, "warn");
  assert.equal(gate.check({ width: 2000, height: 500 }).status, "pass");
});

test("a capture above the floor passes the resolution check", () => {
  const { gate } = loadQualityGate();

  const verdict = gate.check(PASS_READING);

  assert.equal(verdict.check, "resolution");
  assert.equal(verdict.code, "resolution_ok");
  assert.equal(verdict.status, "pass");
  assert.equal(verdict.title, "Resolution check passed");
  assert.equal(
    verdict.message,
    "This capture is 1200 × 900 pixels, at or above the 500-pixel floor.",
  );
  assert.ok(!verdict.message.includes(gate.CONSEQUENCE));
});

test("a capture below the floor is warned, and the warning states the consequence", () => {
  const { gate } = loadQualityGate();

  const verdict = gate.check(WARN_READING);

  assert.equal(verdict.code, "low_resolution");
  assert.equal(verdict.status, "warn");
  assert.equal(verdict.title, "Resolution check failed");
  assert.ok(
    verdict.message.includes("320 × 240 pixels"),
    "the officer is told the size that failed",
  );
  assert.ok(
    verdict.message.includes(gate.CONSEQUENCE),
    "the consequence is part of the warning, not a footnote",
  );
});

test("a consequence that says nothing is a mutation this file kills", () => {
  const dropped = source.replace(
    '"result may be wrong, because text this small may not be read."',
    '""',
  );
  assert.notEqual(dropped, source, "the mutation must have changed the source");

  const real = loadQualityGate();
  const mutated = loadQualityGate({ source: dropped });
  real.controller.show(WARN_READING);
  mutated.controller.show(WARN_READING);

  assert.ok(
    real.elements.message.textContent.includes(real.gate.CONSEQUENCE),
    "the real warning states its consequence",
  );
  assert.ok(
    !mutated.elements.message.textContent.includes(real.gate.CONSEQUENCE),
    "the mutated warning states no consequence at all",
  );
});

test("a floor one pixel too low is a mutation this file kills", () => {
  const offByOne = source.replace(
    "Math.min(measured.width, measured.height) >= MIN_EDGE_PX",
    "Math.min(measured.width, measured.height) > MIN_EDGE_PX",
  );
  assert.notEqual(offByOne, source, "the mutation must have changed the source");

  const real = loadQualityGate();
  const mutated = loadQualityGate({ source: offByOne });
  const boundary = { width: 500, height: 900 };
  real.controller.show(boundary);
  mutated.controller.show(boundary);

  assert.equal(real.gate.check(boundary).status, "pass");
  assert.equal(real.elements.alert.classes.has("ux4g-alert-success"), true);
  assert.equal(mutated.gate.check(boundary).status, "warn");
  assert.equal(mutated.elements.alert.classes.has("ux4g-alert-warning"), true);
});

test("the short edge is what is measured, not the long one", () => {
  const { gate } = loadQualityGate();

  assert.equal(gate.check({ width: 4000, height: 320 }).status, "warn");
  assert.equal(gate.check({ width: 320, height: 4000 }).status, "warn");
});

for (const [label, reading] of [
  ["a string", "1200x900"],
  ["a number", 42],
  ["no width", { height: 900 }],
  ["no height", { width: 1200 }],
  ["a width that is a string", { width: "1200", height: 900 }],
  ["a zero edge", { width: 0, height: 900 }],
  ["a negative edge", { width: 1200, height: -1 }],
  ["not a number", { width: Number.NaN, height: 900 }],
  ["infinite", { width: Number.POSITIVE_INFINITY, height: 900 }],
]) {
  test(`a reading that is ${label} is refused rather than measured`, () => {
    const { gate } = loadQualityGate();

    refuses(
      () => gate.check(reading),
      "unreadable_reading",
      "size in pixels could not be read",
    );
  });
}

test("an unreadable reading is refused by check and shown by nobody", () => {
  const { controller, elements } = loadQualityGate();

  controller.show(PASS_READING);
  const shown = controller.show({ width: "wide", height: 900 });

  assert.equal(shown, null);
  assert.equal(elements.alert.hidden, true);
  assert.equal(elements.alert.classes.has("ux4g-alert-success"), false);
  assert.equal(elements.message.textContent, "");
  assert.equal(controller.verdict(), null);
  assert.equal(controller.blocking(), false);
});

test("the binding names the five elements and the two callbacks it needs", () => {
  const { gate } = loadQualityGate();

  assert.deepEqual(Array.from(gate.REQUIRED_ELEMENTS).sort(), [
    "alert",
    "anyway",
    "message",
    "retake",
    "title",
  ]);
  assert.deepEqual(Array.from(gate.REQUIRED_CALLBACKS), [
    "onRetake",
    "onProceed",
  ]);
});

test("the binding refuses a missing element or callback by name", () => {
  const { gate, elements } = loadQualityGate();
  const wired = {
    alert: elements.alert,
    title: elements.title,
    message: elements.message,
    retake: elements.retake,
    anyway: elements.anyway,
    onRetake: () => {},
    onProceed: () => {},
  };

  for (const name of gate.REQUIRED_ELEMENTS) {
    const without = { ...wired };
    delete without[name];
    refuses(() => gate.bindQualityGate(without), "missing_element", name);
  }
  for (const name of gate.REQUIRED_CALLBACKS) {
    refuses(
      () => gate.bindQualityGate({ ...wired, [name]: null }),
      "missing_callback",
      name,
    );
  }
  refuses(() => gate.bindQualityGate(), "missing_element", "alert");
});

test("a passing capture is shown as the success alert with nothing to override", () => {
  const { controller, elements, proceeded } = loadQualityGate();

  const verdict = controller.show(PASS_READING);

  assert.equal(verdict.status, "pass");
  assert.equal(elements.alert.hidden, false);
  assert.equal(elements.alert.classes.has("ux4g-alert-success"), true);
  assert.equal(elements.alert.classes.has("ux4g-alert-warning"), false);
  assert.equal(elements.title.textContent, "Resolution check passed");
  assert.equal(
    elements.message.textContent,
    "This capture is 1200 × 900 pixels, at or above the 500-pixel floor.",
  );
  assert.equal(elements.retake.hidden, true);
  assert.equal(elements.anyway.hidden, true);
  assert.equal(controller.blocking(), false);
  assert.deepEqual(proceeded, []);
});

test("a failing capture is shown as the warning alert with both answers", () => {
  const { gate, controller, elements } = loadQualityGate();

  controller.show(WARN_READING);

  assert.equal(elements.alert.hidden, false);
  assert.equal(elements.alert.classes.has("ux4g-alert-warning"), true);
  assert.equal(elements.alert.classes.has("ux4g-alert-success"), false);
  assert.equal(elements.title.textContent, "Resolution check failed");
  assert.ok(elements.message.textContent.includes(gate.CONSEQUENCE));
  assert.equal(elements.retake.hidden, false);
  assert.equal(elements.anyway.hidden, false);
  assert.equal(controller.blocking(), true);
});

test("the verdict is announced, and the region listens before it speaks", () => {
  const { controller, elements, gate } = loadQualityGate();

  assert.equal(elements.alert.getAttribute("role"), gate.LIVE_ROLE);
  assert.equal(elements.alert.getAttribute("aria-live"), gate.LIVE_POLITENESS);
  // Read before any verdict exists: a live region written at the same moment
  // as its first text is one a screen reader may never announce.
  assert.equal(elements.title.textContent, "", "nothing has been said yet");

  const warned = controller.show(WARN_READING);
  assert.equal(elements.alert.hidden, false);
  assert.equal(elements.title.textContent, warned.title);
  assert.equal(elements.message.textContent, warned.message);

  const cleared = controller.show(PASS_READING);
  assert.equal(elements.alert.hidden, false);
  assert.equal(
    elements.title.textContent,
    cleared.title,
    "a later verdict replaces the sentence, so the region speaks again",
  );
  assert.equal(
    elements.alert.getAttribute("aria-live"),
    "polite",
    "the region is still the one the binding set up",
  );
});

test("a verdict nobody can hear is a mutation this file kills", () => {
  const dropped = source.replace(
    '    alert.setAttribute("aria-live", LIVE_POLITENESS);',
    "",
  );
  assert.notEqual(dropped, source, "the mutation must have changed the source");

  const real = loadQualityGate();
  const mutated = loadQualityGate({ source: dropped });

  assert.equal(real.elements.alert.getAttribute("aria-live"), "polite");
  assert.equal(
    mutated.elements.alert.getAttribute("aria-live"),
    null,
    "the mutated alert appears without announcing its verdict",
  );
});

test("the two variants are swapped, not stacked", () => {
  const { controller, elements } = loadQualityGate();

  controller.show(PASS_READING);
  controller.show(WARN_READING);
  controller.show(PASS_READING);

  const owned = [...elements.alert.classes].filter((name) =>
    ["ux4g-alert-success", "ux4g-alert-warning"].includes(name),
  );
  assert.deepEqual(owned, ["ux4g-alert-success"]);
  assert.equal(elements.alert.classes.has("ux4g-alert"), true);
});

test("nothing chosen is not a refusal and says nothing", () => {
  const { controller, elements } = loadQualityGate();

  controller.show(WARN_READING);

  for (const reading of [null, undefined]) {
    assert.equal(controller.show(reading), null);
    assert.equal(elements.alert.hidden, true);
    assert.equal(elements.message.textContent, "");
    assert.equal(controller.verdict(), null);
    assert.equal(controller.blocking(), false);
  }
});

test("the retake action clears the file through the upload path", () => {
  const {
    uploadController,
    gateController,
    elements,
    objectUrls,
    proceeded,
    sent,
  } = loadUploadAndGate();
  const file = imageFile();
  elements.input.files = [file];
  elements.input.listeners.change();
  gateController.show({ width: 320, height: 240 });

  assert.equal(uploadController.selected(), file);
  assert.equal(elements.preview.getAttribute("src"), "blob:preview-1");
  assert.equal(elements.panel.hidden, false);
  assert.equal(gateController.blocking(), true);

  elements.retake.click();

  assert.equal(uploadController.selected(), null);
  assert.equal(elements.preview.getAttribute("src"), null);
  assert.equal(elements.preview.alt, "");
  assert.equal(elements.panel.hidden, true);
  assert.equal(elements.details.textContent, "");
  assert.equal(elements.error.textContent, "");
  assert.equal(elements.input.value, "");
  assert.deepEqual(objectUrls[1], { revoked: "blob:preview-1" });
  assert.equal(elements.alert.hidden, true);
  assert.equal(elements.message.textContent, "");
  assert.equal(elements.retake.hidden, true);
  assert.equal(elements.anyway.hidden, true);
  assert.equal(gateController.verdict(), null);
  assert.equal(gateController.blocking(), false);
  assert.deepEqual(proceeded, []);
  assert.deepEqual(sent, { fetches: 0, formData: 0 });
});

test("a retake that never clears the file is a mutation this file kills", () => {
  const withoutRetake = source.replace("      onRetake();\n", "");
  assert.notEqual(
    withoutRetake,
    source,
    "the mutation must have changed the source",
  );

  const real = loadUploadAndGate();
  const mutated = loadUploadAndGate({ source: withoutRetake });
  for (const context of [real, mutated]) {
    context.elements.input.files = [imageFile()];
    context.elements.input.listeners.change();
    context.gateController.show(WARN_READING);
    context.elements.retake.click();
  }

  assert.equal(real.uploadController.selected(), null);
  assert.notEqual(
    mutated.uploadController.selected(),
    null,
    "the mutated retake leaves the file chosen",
  );
});

test("analyse anyway needs the click, and one click is one analysis", () => {
  const { controller, elements, proceeded } = loadQualityGate();

  controller.show(WARN_READING);

  assert.deepEqual(proceeded, []);
  assert.equal(controller.blocking(), true);
  assert.equal(controller.accepted(), false);

  elements.anyway.click();

  assert.deepEqual(proceeded, [true]);
  assert.equal(controller.accepted(), true);
  assert.equal(controller.blocking(), false);
  assert.equal(elements.retake.hidden, true);
  assert.equal(elements.anyway.hidden, true);
  assert.equal(controller.verdict().code, "low_resolution");
});

test("a second click on analyse anyway is refused rather than a second screening", () => {
  const { controller, elements, proceeded } = loadQualityGate();

  controller.show(WARN_READING);
  elements.anyway.click();

  refuses(() => elements.anyway.click(), "already_accepted", "already accepted");
  refuses(() => controller.anyway(), "already_accepted", "already accepted");
  assert.deepEqual(proceeded, [true]);
});

test("there is nothing to analyse anyway when no warning stands", () => {
  const { controller, elements, proceeded } = loadQualityGate();

  refuses(() => controller.anyway(), "not_warned", "nothing to analyse anyway");

  controller.show(PASS_READING);
  refuses(
    () => elements.anyway.click(),
    "not_warned",
    "nothing to analyse anyway",
  );
  controller.retake();
  refuses(() => controller.anyway(), "not_warned", "nothing to analyse anyway");

  assert.deepEqual(proceeded, []);
  assert.equal(elements.anyway.hidden, true);
});

test("the gate sends nothing and reads no clock or storage", () => {
  const { controller, elements, sent } = loadQualityGate();

  controller.show(WARN_READING);
  elements.anyway.click();
  controller.retake();
  controller.show(PASS_READING);

  assert.deepEqual(sent, { fetches: 0, formData: 0 });
  assert.doesNotMatch(
    source,
    /DRISHTI_API|fetch\(|FormData\(|Date\.now|new Date|localStorage|sessionStorage/,
  );
});

test("no page loads the module yet, so the build copies nothing", () => {
  const { staticFiles, pageFileNames } = buildFileNames();
  const pages = pageFileNames.map((fileName) =>
    fs.readFileSync(path.join(__dirname, fileName), "utf8"),
  );
  const shell = fs.readFileSync(path.join(__dirname, "shell.html"), "utf8");

  assert.ok(!staticFiles.includes("quality-gate.js"));
  for (const markup of [...pages, shell]) {
    assert.doesNotMatch(markup, /quality-gate\.js/);
  }
});