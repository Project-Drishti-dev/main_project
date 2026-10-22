const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const SOURCE = fs.readFileSync(path.join(__dirname, "submit.js"), "utf8");
const API_SOURCE = fs.readFileSync(path.join(__dirname, "api.js"), "utf8");
const UPLOAD_SOURCE = fs.readFileSync(
  path.join(__dirname, "upload.js"),
  "utf8",
);

const BASE_URL = "https://api.example.test";
const SCREENING_ID = "0f8fad5b-d9cb-469f-a165-70867728950e";
const AUDIT_ID = "7c9e6679-7425-40de-944b-e07fc1f90ae7";

function createElement(tagName = "div") {
  const element = {
    tagName: tagName.toUpperCase(),
    disabled: false,
    listeners: {},
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
    click() {
      return this.listeners.click();
    },
  };
  return element;
}

function documentImage(name = "passport.jpg") {
  return new File([new Uint8Array([0xff, 0xd8, 0xff, 0xd9])], name, {
    type: "image/jpeg",
  });
}

// The five elements the upload path binds to. A preview, a panel and a
// file input are none of the submission path's business.
function createPreviewElement(tagName = "div") {
  const element = createElement(tagName);
  element.hidden = false;
  element.value = "";
  element.alt = "";
  element.attributes = {};
  element.setAttribute = (name, value) => {
    element.attributes[name] = value;
  };
  element.getAttribute = (name) =>
    Object.prototype.hasOwnProperty.call(element.attributes, name)
      ? element.attributes[name]
      : null;
  element.removeAttribute = (name) => {
    delete element.attributes[name];
  };
  return element;
}

// The answer the service gives a created screening, and the refusals 22.6 has
// to pass on rather than replace: an envelope the service wrote, an envelope
// it did not, and a body that cannot be read at all.
function createdAnswer(payload = { screening_id: SCREENING_ID, audit_id: AUDIT_ID }) {
  return async () => ({
    ok: true,
    status: 201,
    json: async () => payload,
    text: async () => JSON.stringify(payload),
  });
}

function refusedAnswer(status, body) {
  return async () => ({
    ok: false,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body),
  });
}

function deferredAnswer() {
  let release;
  const gate = new Promise((resolve) => {
    release = resolve;
  });
  return {
    answer: async () => {
      await gate;
      return createdAnswer()();
    },
    release,
  };
}

// One sandbox per binding, with api.js and submit.js loaded into it together:
// the claim is that the submission goes through the API module, so the test
// has to watch a real fetch rather than a stub of this module's own seam.
function loadSubmit(options = {}) {
  const requests = [];
  const bodies = { built: 0 };
  const answer = Object.prototype.hasOwnProperty.call(options, "answer")
    ? options.answer
    : createdAnswer();
  const sandbox = {
    window: {
      DRISHTI_CONFIG: {
        apiBaseUrl: Object.prototype.hasOwnProperty.call(options, "apiBaseUrl")
          ? options.apiBaseUrl
          : BASE_URL,
      },
    },
    FormData: function FormDataSpy(...args) {
      bodies.built += 1;
      return new FormData(...args);
    },
    File,
    AbortController,
    setTimeout,
    clearTimeout,
    fetch(url, init) {
      requests.push({ url, init });
      return answer(url, init);
    },
  };
  if (options.uploadSource) {
    sandbox.URL = {
      createObjectURL: () => "blob:preview",
      revokeObjectURL: () => {},
    };
  }
  vm.createContext(sandbox);
  if (options.api !== false) {
    vm.runInContext(API_SOURCE, sandbox, { filename: "api.js" });
  }
  if (options.uploadSource) {
    vm.runInContext(options.uploadSource, sandbox, { filename: "upload.js" });
  }
  vm.runInContext(
    Object.prototype.hasOwnProperty.call(options, "source")
      ? options.source
      : SOURCE,
    sandbox,
    { filename: "submit.js" },
  );
  return {
    submit: sandbox.window.DRISHTI_SUBMIT,
    upload: sandbox.window.DRISHTI_UPLOAD,
    requests,
    bodies,
    sandbox,
  };
}

function bindSubmitted(options = {}) {
  const context = loadSubmit(options);
  const elements = { button: createElement("button"), error: createElement("p") };
  const navigations = [];
  const pendingStates = [];
  const settings = {
    button: elements.button,
    error: elements.error,
    describe: () => ({ file: documentImage() }),
    navigate: (url) => navigations.push(url),
    onPending: (isPending) => pendingStates.push(isPending),
    ...options.settings,
  };
  const controller = context.submit.bindSubmit(settings);
  return { ...context, controller, elements, navigations, pendingStates };
}

function described(overrides = {}) {
  return { file: documentImage(), ...overrides };
}

// A refusal raised inside the sandbox is that sandbox's own Error, so the
// name and code are what the check reads rather than an instanceof.
function isRefusal(error, code, fragment) {
  return (
    error.name === "SubmitError" &&
    error.code === code &&
    fragment.test(error.message)
  );
}

test("the screening id the service answers with is stored and reaches the result page URL", async () => {
  const { controller, navigations, requests, elements } = bindSubmitted();

  const id = await controller.submit(described());

  assert.equal(id, SCREENING_ID);
  assert.equal(controller.screeningId(), SCREENING_ID);
  assert.equal(controller.resultUrl(), "result.html?id=" + SCREENING_ID);
  assert.deepEqual(navigations, ["result.html?id=" + SCREENING_ID]);
  assert.equal(requests.length, 1);
  assert.equal(elements.error.textContent, "");
});

test("the image is posted to POST /api/screenings as multipart, through api.js", async () => {
  const { controller, requests } = bindSubmitted();

  await controller.submit(
    described({ mode: "photo", documentType: "passport" }),
  );

  assert.equal(requests.length, 1);
  const [request] = requests;
  assert.equal(request.url, BASE_URL + "/api/screenings");
  assert.equal(request.init.method, "POST");
  assert.ok(request.init.body instanceof FormData);
  assert.equal(request.init.body.get("image").name, "passport.jpg");
  assert.equal(request.init.body.get("mode"), "photo");
  assert.equal(request.init.body.get("document_type"), "passport");
});

test("a source that names nothing is sent as auto and unspecified", async () => {
  const { controller, requests } = bindSubmitted();

  await controller.submit({ file: documentImage() });

  const [request] = requests;
  assert.equal(request.init.body.get("mode"), "auto");
  assert.equal(request.init.body.get("document_type"), "unspecified");
});

test("the click asks describe() at click time and submits what it answers", async () => {
  const asked = [];
  const { controller, navigations, elements } = bindSubmitted({
    settings: {
      describe: () => {
        asked.push(Date.now());
        return described({ documentType: "visa" });
      },
    },
  });

  await elements.button.click();

  assert.equal(asked.length, 1);
  assert.equal(controller.screeningId(), SCREENING_ID);
  assert.deepEqual(navigations, ["result.html?id=" + SCREENING_ID]);
});

test("what cannot be sent is refused before anything leaves the page", async () => {
  const cases = [
    { fields: { file: null }, code: "no_file" },
    { fields: { file: undefined }, code: "no_file" },
    { fields: { mode: "photograph" }, code: "unsupported_mode" },
    { fields: { mode: " auto" }, code: "unsupported_mode" },
    { fields: { mode: 7 }, code: "unsupported_mode" },
    { fields: { documentType: "   " }, code: "invalid_document_type" },
    { fields: { documentType: 12 }, code: "invalid_document_type" },
  ];

  for (const { fields, code } of cases) {
    const { controller, requests, bodies, navigations, elements } =
      bindSubmitted();

    const id = await controller.submit(described(fields));

    assert.equal(id, null);
    assert.equal(elements.error.textContent.length > 0, true);
    assert.equal(requests.length, 0, code + " must not reach the network");
    assert.equal(bodies.built, 0, code + " must not build a request");
    assert.deepEqual(navigations, []);
    assert.equal(controller.screeningId(), null);
    assert.equal(controller.resultUrl(), null);
  }
});

test("a refusal the service wrote is shown in the service's own words", async () => {
  const message = "Choose an image to screen.";
  const { controller, navigations, elements } = bindSubmitted({
    answer: refusedAnswer(400, { error: { code: "IMAGE_REQUIRED", message } }),
  });

  const id = await controller.submit(described());

  assert.equal(id, null);
  assert.equal(elements.error.textContent, message);
  assert.deepEqual(navigations, []);
  assert.equal(controller.screeningId(), null);
});

test("a failure with no envelope, and one with no answer at all, each keep their own sentence", async () => {
  const server = bindSubmitted({
    answer: refusedAnswer(503, "gateway is down"),
  });
  await server.controller.submit(described());
  assert.equal(
    server.elements.error.textContent,
    "The server answered 503 with no error envelope.",
  );

  const offline = bindSubmitted({
    answer: async () => {
      throw new TypeError("Failed to fetch");
    },
  });
  await offline.controller.submit(described());
  assert.match(offline.elements.error.textContent, /quality service could not be reached/);
  assert.match(offline.elements.error.textContent, /CORS/);
  assert.deepEqual(offline.navigations, []);
});

test("an accepted image with no id in the answer is refused, and nothing opens", async () => {
  for (const payload of [{}, { audit_id: AUDIT_ID }, { screening_id: "" }, null]) {
    const { controller, navigations, elements } = bindSubmitted({
      answer: createdAnswer(payload),
    });

    const id = await controller.submit(described());

    assert.equal(id, null);
    assert.equal(controller.screeningId(), null);
    assert.deepEqual(navigations, []);
    assert.match(elements.error.textContent, /no screening id/);
  }
});

test("a body that cannot be read is the same refusal as a body with no id", async () => {
  const { controller, navigations, elements } = bindSubmitted({
    answer: async () => ({
      ok: true,
      status: 200,
      json: async () => {
        throw new SyntaxError("Unexpected end of JSON input");
      },
    }),
  });

  assert.equal(await controller.submit(described()), null);
  assert.deepEqual(navigations, []);
  assert.match(elements.error.textContent, /no screening id/);
});

test("the button is held while a submission is in flight, and a second one sends nothing", async () => {
  const { answer, release } = deferredAnswer();
  const { controller, requests, elements, pendingStates } = bindSubmitted({
    answer,
  });

  const first = controller.submit(described());

  assert.equal(elements.button.disabled, true);
  assert.equal(controller.pending(), true);
  assert.deepEqual(pendingStates, [true]);

  assert.equal(await controller.submit(described()), null);
  assert.equal(requests.length, 1);

  release();
  assert.equal(await first, SCREENING_ID);
  assert.equal(elements.button.disabled, false);
  assert.equal(controller.pending(), false);
  assert.deepEqual(pendingStates, [true, false]);
});

// One sandbox holds api.js, upload.js and submit.js together, and the
// recorder is a real fetch: the claim is about what crosses the network,
// so it has to be watched where the network is dialled.
test("nothing leaves the page until the submit button is clicked", async () => {
  const context = loadSubmit({ uploadSource: UPLOAD_SOURCE });
  const ui = {
    input: createPreviewElement("input"),
    panel: createPreviewElement("div"),
    preview: createPreviewElement("img"),
    details: createPreviewElement("p"),
    error: createPreviewElement("p"),
    button: createElement("button"),
    submitError: createElement("p"),
  };
  const upload = context.upload.bindUpload({
    input: ui.input,
    panel: ui.panel,
    preview: ui.preview,
    details: ui.details,
    error: ui.error,
  });
  const navigations = [];
  context.submit.bindSubmit({
    button: ui.button,
    error: ui.submitError,
    describe: () => ({ file: upload.selected() }),
    navigate: (url) => navigations.push(url),
  });

  ui.input.files = [documentImage()];
  ui.input.listeners.change();

  assert.equal(upload.selected().name, "passport.jpg");
  assert.equal(ui.panel.hidden, false);
  assert.deepEqual(
    context.requests,
    [],
    "choosing a file must not leave the page",
  );
  assert.equal(context.bodies.built, 0, "a preview must build no request");

  await ui.button.click();

  assert.equal(context.requests.length, 1);
  assert.equal(context.requests[0].url, BASE_URL + "/api/screenings");
  assert.equal(
    context.requests[0].init.body.get("image").name,
    "passport.jpg",
  );
  assert.deepEqual(navigations, ["result.html?id=" + SCREENING_ID]);
});

test("a second submission drops the first id before it is asked for", async () => {
  const { controller } = bindSubmitted();

  await controller.submit(described());
  assert.equal(controller.screeningId(), SCREENING_ID);

  await controller.submit(described({ file: null }));

  assert.equal(controller.screeningId(), null);
  assert.equal(controller.resultUrl(), null);
});

test("the binding refuses each piece it needs by name, and needs nothing more", () => {
  const { submit } = loadSubmit();
  const elementNames = ["button", "error"];
  assert.deepEqual([...submit.REQUIRED_ELEMENTS].sort(), elementNames);

  for (const name of elementNames) {
    const { submit: module } = loadSubmit();
    const settings = {
      button: createElement("button"),
      error: createElement("p"),
      describe: () => ({ file: documentImage() }),
      navigate: () => {},
      [name]: undefined,
    };
    assert.throws(
      () => module.bindSubmit(settings),
      (error) => isRefusal(error, "missing_element", new RegExp(name)),
    );
  }

  for (const name of ["describe", "navigate"]) {
    const { submit: module } = loadSubmit();
    const settings = {
      button: createElement("button"),
      error: createElement("p"),
      describe: () => ({ file: documentImage() }),
      navigate: () => {},
      [name]: undefined,
    };
    assert.throws(
      () => module.bindSubmit(settings),
      (error) => isRefusal(error, "missing_callback", new RegExp(name)),
    );
  }

  // Nothing outside the table is needed: the two listed elements and the two
  // callbacks are a whole binding.
  const { submit: module } = loadSubmit();
  const controller = module.bindSubmit({
    button: createElement("button"),
    error: createElement("p"),
    describe: () => ({ file: documentImage() }),
    navigate: () => {},
  });
  assert.equal(controller.screeningId(), null);
});

test("a page that never loaded api.js is refused rather than dialled", () => {
  const { submit } = loadSubmit({ api: false });
  assert.throws(
    () =>
      submit.bindSubmit({
        button: createElement("button"),
        error: createElement("p"),
        describe: () => ({ file: documentImage() }),
        navigate: () => {},
      }),
    (error) => isRefusal(error, "no_api", /quality service/),
  );
});

test("the result URL is built from the id alone, and refuses one it was not given", () => {
  const { submit } = loadSubmit();

  assert.equal(submit.resultUrlFor(SCREENING_ID), "result.html?id=" + SCREENING_ID);
  assert.equal(
    submit.resultUrlFor("id with spaces"),
    "result.html?id=" + encodeURIComponent("id with spaces"),
  );
  for (const id of ["", "   ", null, undefined, 42, {}]) {
    assert.throws(
      () => submit.resultUrlFor(id),
      (error) => isRefusal(error, "no_screening_id", /no screening id/),
    );
  }
});

test("a path that navigates without the id fails the URL assertion", async () => {
  const mutated = SOURCE.replace(
    "navigate(resultUrlFor(id));",
    "navigate(RESULT_PAGE);",
  );
  assert.notEqual(mutated, SOURCE, "the mutation must have landed");

  const { controller, navigations } = bindSubmitted({ source: mutated });

  const id = await controller.submit(described());

  assert.equal(id, SCREENING_ID);
  assert.equal(controller.screeningId(), SCREENING_ID);
  assert.notEqual(navigations[0], "result.html?id=" + SCREENING_ID);
});

test("the module reaches the network only through api.js", () => {
  assert.doesNotMatch(SOURCE, /\bfetch\s*\(/);
  assert.match(SOURCE, /window\.DRISHTI_API/);
});