const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const UPLOAD_PATH = path.join(__dirname, "upload.js");
const source = fs.readFileSync(UPLOAD_PATH, "utf8");
const { buildFileNames } = require("./build.cjs");

const KIBIBYTE = 1024;
const MEBIBYTE = 1024 * KIBIBYTE;

function createElement(tagName = "div") {
  const element = {
    tagName: tagName.toUpperCase(),
    attributes: {},
    listeners: {},
    hidden: false,
    value: "",
    alt: "",
    src: "",
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
      if (name === "src") this.src = value;
    },
    getAttribute(name) {
      return this.attributes[name] ?? null;
    },
    removeAttribute(name) {
      delete this.attributes[name];
      if (name === "src") this.src = "";
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

// A binding over five fake elements, plus the two globals the module reaches
// for. fetch and FormData are recorders rather than absences: the claim is
// that a previewed file is not sent, so the test must be able to see a send.
function loadUploadModule() {
  const elements = {
    input: createElement("input"),
    panel: createElement("div"),
    preview: createElement("img"),
    details: createElement("p"),
    error: createElement("p"),
  };
  const objectUrls = [];
  let createdUrls = 0;
  const sent = { fetches: 0, formData: 0 };
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
      throw new Error("the preview must not send anything");
    },
    FormData() {
      sent.formData += 1;
      throw new Error("the preview must not build a request");
    },
  };
  vm.runInNewContext(source, sandbox);
  return { upload: sandbox.window.DRISHTI_UPLOAD, elements, objectUrls, sent };
}

function bindUploaded({ onSelect } = {}) {
  const context = loadUploadModule();
  const controller = context.upload.bindUpload({
    input: context.elements.input,
    panel: context.elements.panel,
    preview: context.elements.preview,
    details: context.elements.details,
    error: context.elements.error,
    ...(onSelect ? { onSelect } : {}),
  });
  return { ...context, controller };
}

function pick(elements, ...files) {
  elements.input.files = files;
  // A browser leaves the chosen path on the control; clearing it is the
  // module's job, so the fake starts from the value a real one carries.
  elements.input.value = files.length > 0 ? "C:\\fakepath\\" + files[0].name : "";
  elements.input.listeners.change();
}

function refuses(call, code, fragment) {
  assert.throws(call, (error) => {
    assert.equal(error.name, "UploadError");
    assert.equal(error.code, code);
    assert.ok(
      error.message.includes(fragment),
      "message was " + JSON.stringify(error.message),
    );
    return true;
  });
}

test("the ceiling and the three types are the ones the site already ships", () => {
  const { upload } = loadUploadModule();

  assert.equal(upload.MAX_BYTES, 10 * MEBIBYTE);
  assert.deepEqual(Array.from(upload.ACCEPTED_TYPES), [
    "image/jpeg",
    "image/png",
    "image/webp",
  ]);
  assert.equal(upload.ACCEPT, "image/jpeg,image/png,image/webp");
});

test("the accept attribute and the refused set are the same three types", () => {
  const { upload } = loadUploadModule();

  const attributeTypes = upload.ACCEPT.split(",");
  assert.deepEqual(attributeTypes, Array.from(upload.ACCEPTED_TYPES));
  for (const type of attributeTypes) {
    assert.equal(upload.validate(imageFile({ type, size: 1 })).type, type);
  }
});

test("the binding names the five elements it needs", () => {
  const { upload } = loadUploadModule();

  assert.deepEqual(Array.from(upload.REQUIRED_ELEMENTS).sort(), [
    "details",
    "error",
    "input",
    "panel",
    "preview",
  ]);
});

const REJECTED_TYPES = [
  ["GIF", "image/gif"],
  ["BMP", "image/bmp"],
  ["TIFF", "image/tiff"],
  ["SVG", "image/svg+xml"],
  ["HEIC", "image/heic"],
  ["HEIF", "image/heif"],
  ["the near-miss image/jpg", "image/jpg"],
  ["PDF", "application/pdf"],
  ["plain text", "text/plain"],
  ["an empty type", ""],
  ["an upper-case type", "IMAGE/JPEG"],
  ["a type the browser did not give", undefined],
  ["a type that is not a string", 42],
];

for (const [label, type] of REJECTED_TYPES) {
  test(`${label} is refused before it is previewed`, () => {
    const { upload, elements, objectUrls, sent } = bindUploaded();

    pick(elements, imageFile({ name: `document.${label}`, type, size: 10 }));

    assert.equal(elements.error.textContent, "Choose a JPEG, PNG, or WebP image.");
    assert.equal(elements.panel.hidden, true);
    assert.equal(elements.preview.getAttribute("src"), null);
    assert.equal(elements.input.value, "");
    assert.deepEqual(objectUrls, []);
    assert.deepEqual(sent, { fetches: 0, formData: 0 });
  });
}

test("the module holds none of the types it refuses", () => {
  const { upload } = loadUploadModule();

  for (const [, type] of REJECTED_TYPES) {
    assert.ok(
      !upload.ACCEPTED_TYPES.includes(type),
      "accepted types must not carry " + String(type),
    );
  }
});

for (const type of ["image/jpeg", "image/png", "image/webp"]) {
  test(`${type} is accepted and handed back as the chosen file`, () => {
    const { upload, controller } = bindUploaded();
    const file = imageFile({ type, size: 4096 });

    assert.equal(upload.validate(file), file);
    assert.equal(controller.choose(file), file);
    assert.equal(controller.selected(), file);
  });
}

test("the size boundary is exact in both directions", () => {
  const { upload } = bindUploaded();

  assert.equal(upload.MAX_BYTES, 10 * MEBIBYTE);
  assert.equal(upload.validate(imageFile({ size: 0 })).size, 0);
  assert.equal(upload.validate(imageFile({ size: upload.MAX_BYTES - 1 })).size, upload.MAX_BYTES - 1);
  assert.equal(upload.validate(imageFile({ size: upload.MAX_BYTES })).size, upload.MAX_BYTES);
  refuses(
    () => upload.validate(imageFile({ size: upload.MAX_BYTES + 1 })),
    "too_large",
    "10 MB or smaller",
  );
});

test("one byte over the ceiling is refused by the binding, not only by validate", () => {
  const { upload, elements, objectUrls } = bindUploaded();

  pick(elements, imageFile({ size: upload.MAX_BYTES + 1 }));

  assert.equal(elements.error.textContent, "Choose an image that is 10 MB or smaller.");
  assert.equal(elements.panel.hidden, true);
  assert.deepEqual(objectUrls, []);
});

for (const [label, size] of [
  ["absent", undefined],
  ["a string", "2048"],
  ["not a number", Number.NaN],
  ["infinite", Number.POSITIVE_INFINITY],
  ["negative", -1],
]) {
  test(`a size that is ${label} is refused rather than compared`, () => {
    const { upload } = bindUploaded();

    refuses(
      () => upload.validate(imageFile({ size })),
      "unreadable_size",
      "size could not be read",
    );
  });
}

test("nothing chosen is not a refusal and says nothing", () => {
  const { elements, objectUrls, controller } = bindUploaded();

  pick(elements);

  assert.equal(elements.error.textContent, "");
  assert.equal(elements.panel.hidden, true);
  assert.equal(controller.selected(), null);
  assert.deepEqual(objectUrls, []);
});

test("a file that is not a file at all is refused by name", () => {
  const { upload } = bindUploaded();

  for (const value of [null, undefined, "passport.jpg", 42]) {
    refuses(() => upload.validate(value), "no_file", "Choose an image to screen");
  }
});

test("an accepted file previews locally and is not sent", () => {
  const chosen = [];
  const { controller, elements, objectUrls, sent } = bindUploaded({
    onSelect: (file) => chosen.push(file),
  });
  const file = imageFile({ name: "passport.jpg", type: "image/jpeg", size: 2048 });

  pick(elements, file);

  assert.equal(elements.panel.hidden, false);
  assert.equal(elements.preview.getAttribute("src"), "blob:preview-1");
  assert.equal(elements.preview.alt, "Preview of passport.jpg");
  assert.equal(elements.details.textContent, "passport.jpg · 2.0 KB");
  assert.equal(controller.selected(), file);
  assert.deepEqual(chosen, [null, file]);
  assert.deepEqual(objectUrls, [{ file, url: "blob:preview-1" }]);
  assert.deepEqual(sent, { fetches: 0, formData: 0 });
});

test("the input is cleared so the same file can be chosen twice", () => {
  const { controller, elements } = bindUploaded();

  pick(elements, imageFile());
  assert.equal(elements.input.value, "");

  pick(elements, imageFile({ name: "visa.png", type: "image/png" }));
  assert.equal(controller.selected().name, "visa.png");
});

test("choosing a second file releases the first preview URL", () => {
  const { controller, elements, objectUrls } = bindUploaded();
  const first = imageFile({ name: "first.jpg" });
  const second = imageFile({ name: "second.png", type: "image/png" });

  pick(elements, first);
  pick(elements, second);

  assert.deepEqual(objectUrls, [
    { file: first, url: "blob:preview-1" },
    { revoked: "blob:preview-1" },
    { file: second, url: "blob:preview-2" },
  ]);
  assert.equal(elements.preview.getAttribute("src"), "blob:preview-2");
  assert.equal(controller.selected(), second);
});

test("clear is the one path back to nothing chosen", () => {
  const chosen = [];
  const { controller, elements, objectUrls } = bindUploaded({
    onSelect: (file) => chosen.push(file),
  });
  pick(elements, imageFile());

  controller.clear();

  assert.equal(controller.selected(), null);
  assert.equal(elements.panel.hidden, true);
  assert.equal(elements.preview.getAttribute("src"), null);
  assert.equal(elements.preview.alt, "");
  assert.equal(elements.details.textContent, "");
  assert.equal(elements.error.textContent, "");
  assert.equal(elements.input.value, "");
  assert.deepEqual(objectUrls[1], { revoked: "blob:preview-1" });
  assert.deepEqual(chosen, [null, imageFile(), null]);
});

test("a preview that will not decode is refused and the file is released", () => {
  const chosen = [];
  const { controller, elements, objectUrls } = bindUploaded({
    onSelect: (file) => chosen.push(file),
  });
  pick(elements, imageFile());

  elements.preview.listeners.error();

  assert.equal(
    elements.error.textContent,
    "This file could not be opened as an image. Choose a valid JPEG, PNG, or WebP.",
  );
  assert.equal(elements.panel.hidden, true);
  assert.equal(elements.preview.getAttribute("src"), null);
  assert.equal(controller.selected(), null);
  assert.deepEqual(objectUrls[1], { revoked: "blob:preview-1" });
  assert.deepEqual(chosen, [null, imageFile(), null]);
});

test("a decode failure belonging to a preview already replaced is ignored", () => {
  const { controller, elements } = bindUploaded();
  pick(elements, imageFile());

  elements.preview.setAttribute("src", "blob:someone-elses");
  elements.preview.listeners.error();

  assert.equal(elements.error.textContent, "");
  assert.equal(controller.selected().name, "passport.jpg");
});

test("the binding refuses a missing element by name", () => {
  const { upload, elements } = loadUploadModule();

  for (const name of upload.REQUIRED_ELEMENTS) {
    const without = { ...elements };
    delete without[name];
    refuses(() => upload.bindUpload(without), "missing_element", name);
  }
  refuses(() => upload.bindUpload(), "missing_element", "input");
});

test("the size ladder reads the way the site already spells it", () => {
  const { upload } = bindUploaded();

  assert.equal(upload.formatSize(0), "0 B");
  assert.equal(upload.formatSize(900), "900 B");
  assert.equal(upload.formatSize(2048), "2.0 KB");
  assert.equal(upload.formatSize(upload.MAX_BYTES), "10.0 MB");
  assert.equal(upload.describe(imageFile({ size: 900 })), "passport.jpg · 900 B");
  assert.equal(upload.describe({ size: 900 }), " · 900 B");
});

test("the module reads no clock and holds no storage", () => {
  assert.doesNotMatch(source, /Date\.now|new Date|localStorage|sessionStorage/);
});

test("no page loads the module yet, so the build copies nothing", () => {
  const { staticFiles, pageFileNames } = buildFileNames();
  const pages = pageFileNames.map((fileName) =>
    fs.readFileSync(path.join(__dirname, fileName), "utf8"),
  );
  const shell = fs.readFileSync(path.join(__dirname, "shell.html"), "utf8");

  assert.ok(!staticFiles.includes("upload.js"));
  for (const markup of [...pages, shell]) {
    assert.doesNotMatch(markup, /upload\.js/);
  }
});
