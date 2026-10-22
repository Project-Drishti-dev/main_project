const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const { buildFileNames } = require("./build.cjs");

const source = fs.readFileSync(path.join(__dirname, "result-decision.js"), "utf8");
const sheet = fs.readFileSync(
  path.join(__dirname, "node_modules", "ux4g-web-components", "styles", "ux4g.css"),
  "utf8",
);
const decisionSource = fs.readFileSync(
  path.join(__dirname, "..", "backend", "app", "audit", "decision.py"),
  "utf8",
);
const apiSource = fs.readFileSync(path.join(__dirname, "api.js"), "utf8");
const schemasSource = fs.readFileSync(
  path.join(__dirname, "..", "backend", "app", "schemas.py"),
  "utf8",
);

const BASE_URL = "https://api.example.test";
const SCREENING_ID = "0f8fad5b-d9cb-469f-a165-70867728950e";
const DECISION_ID = "1b4e28ba-2fa1-11d2-883f-0016d3cca427";
const SERVICE_MESSAGE = "That screening could not be found.";

// The answer the route writes for a recorded choice, in its own seven fields.
const DECISION_ANSWER = {
  screening_id: SCREENING_ID,
  action: "further_inspection",
  remark: "",
  override: false,
  decision_id: DECISION_ID,
  status: "current",
  supersedes: null,
};

const TEXT_NODE = 3;

// The smallest element the form can be built on: the classes, the text, the
// attributes, the children, and nothing else, so a property nobody implemented
// here would throw rather than pass quietly.
function createElement(tagName = "div") {
  const classes = new Set();
  const attributes = new Map();
  return {
    tagName: tagName.toUpperCase(),
    nodeType: 1,
    classes: classes,
    attributes: attributes,
    children: [],
    textContent: "",
    disabled: false,
    listeners: {},
    addEventListener: function (event, callback) {
      this.listeners[event] = callback;
    },
    click: function () {
      return this.listeners.click();
    },
    classList: {
      add: function (name) {
        classes.add(name);
      },
      remove: function (...names) {
        for (const name of names) {
          classes.delete(name);
        }
      },
      contains: function (name) {
        return classes.has(name);
      },
    },
    setAttribute: function (name, value) {
      attributes.set(name, String(value));
    },
    getAttribute: function (name) {
      return attributes.has(name) ? attributes.get(name) : null;
    },
    appendChild: function (child) {
      this.children.push(child);
      return child;
    },
    removeChild: function (child) {
      const at = this.children.indexOf(child);
      if (at < 0) {
        throw new Error("the decision form removed a card it never drew");
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

function classesIn(node) {
  return [...node.classes, ...node.children.flatMap(classesIn)];
}

function host(value) {
  return Array.from(value);
}

// A whole word, not a substring: "allow" carries "low" inside it, and a check
// that read the band out of the word "allow" would pair the two vocabularies
// in the very test that says they are never paired.
function says(text, word) {
  return new RegExp("\\b" + word + "\\b").test(text);
}

// The answer a recorded choice comes back with, and the refusal a screening
// that cannot be found comes back with: both are envelopes the route writes,
// so the module is proved against what the service says rather than against a
// stub of this module's own seam.
function recordedAnswer(payload = DECISION_ANSWER) {
  return async () => ({
    ok: true,
    status: 200,
    json: async () => payload,
    text: async () => JSON.stringify(payload),
  });
}

function refusedAnswer(status, body) {
  return async () => ({
    ok: false,
    status: status,
    json: async () => body,
    text: async () => JSON.stringify(body),
  });
}

// An answer held until the case releases it, so the window between two
// presses is a window a case can look at.
function deferredAnswer(answer) {
  let release;
  const gate = new Promise((resolve) => {
    release = resolve;
  });
  return {
    answer: async () => {
      await gate;
      return answer();
    },
    release: release,
  };
}

// One answer per call, so a refusal and the record that follows it are one
// load rather than two.
function sequenceAnswer(answers) {
  let at = 0;
  return async (url, init) => {
    const answer = answers[Math.min(at, answers.length - 1)];
    at += 1;
    return answer(url, init);
  };
}

// Every continuation in the send is a microtask, so one turn of the event loop
// is enough for a click and its catch to have both run.
function flush() {
  return new Promise((resolve) => {
    setImmediate(resolve);
  });
}

// fetch and FormData are recorders rather than absences, so a send is visible
// to fail on rather than silently absent.  api.js is loaded into the same
// sandbox when a case wants a real exchange, because the claim under test is
// that the decision goes out through the API module.
function loadDecision(options = {}) {
  const sent = { fetches: 0, formData: 0 };
  const requests = [];
  const has = (name) => Object.prototype.hasOwnProperty.call(options, name);
  const answer = has("answer") ? options.answer : null;
  const sandbox = {
    window: { DRISHTI_CONFIG: { apiBaseUrl: BASE_URL } },
    document: {
      createElement: createElement,
      createTextNode: function (text) {
        return { nodeType: TEXT_NODE, textContent: String(text) };
      },
    },
    AbortController: AbortController,
    setTimeout: setTimeout,
    clearTimeout: clearTimeout,
    fetch: function (url, init) {
      sent.fetches += 1;
      requests.push({ url: url, init: init });
      if (answer === null) {
        throw new Error("the decision form must not send anything");
      }
      return answer(url, init);
    },
    FormData: function () {
      sent.formData += 1;
      throw new Error("the decision form must not build a request");
    },
  };
  vm.createContext(sandbox);
  if (options.api) {
    vm.runInContext(apiSource, sandbox, { filename: "api.js" });
  }
  vm.runInContext(has("source") ? options.source : source, sandbox, {
    filename: "result-decision.js",
  });
  return {
    module: sandbox.window.DRISHTI_RESULT_DECISION,
    sent: sent,
    requests: requests,
  };
}

function bind(module, options = {}) {
  const container = createElement();
  const controller = module.bindResultDecision({
    container: container,
    ...options,
  });
  return { controller: controller, container: container };
}

// The form as the page receives it: the card, its four parts, and the three
// radios inside the group.
function drawn(container) {
  const [card] = container.children;
  const [groupLabel, group, remark, overrideLabel, button, status] =
    card.children;
  return {
    card: card,
    groupLabel: groupLabel,
    group: group,
    radios: group.children,
    remark: remark,
    remarkLabel: remark.children[0],
    remarkInput: remark.children[1].children[0],
    remarkHelper: remark.children[2],
    overrideLabel: overrideLabel,
    overrideInput: overrideLabel.children[0],
    button: button,
    status: status,
  };
}

function refuses(call, code) {
  assert.throws(call, (error) => {
    assert.equal(error.name, "ResultDecisionError");
    assert.equal(error.code, code);
    return true;
  });
}

// The same refusal, reached through the promise a send hands back rather than
// through the call that made it.
async function refusesAsync(call, code) {
  await assert.rejects(call, (error) => {
    assert.equal(error.name, "ResultDecisionError");
    assert.equal(error.code, code);
    return true;
  });
}

// The three pairs that agree, written out rather than computed: agreeing is
// the claim under test, and computing it from the two orderings would assert
// the module against itself.
const AGREEING = ["low:allow", "review:further_inspection", "high:reject"];

function expectsAgreement(band, action) {
  return AGREEING.includes(band + ":" + action);
}

const BANDS = ["low", "review", "high"];
const ACTIONS = ["allow", "further_inspection", "reject"];

test("the override control is hidden until the officer contradicts the band", () => {
  const { module } = loadDecision();
  for (const band of BANDS) {
    const { controller, container } = bind(module);
    controller.render({ band: band });
    const form = drawn(container);

    assert.equal(form.overrideLabel.hidden, true, band + " renders the override");
    assert.equal(controller.overrideShown(), false, band);
    assert.equal(controller.override(), false, band);

    for (const action of ACTIONS) {
      controller.choose(action);
      const shown = !expectsAgreement(band, action);
      assert.equal(
        form.overrideLabel.hidden,
        !shown,
        band + " with " + action,
      );
      assert.equal(controller.overrideShown(), shown, band + " with " + action);
    }
  }
});

test("the control is on screen for exactly the six contradicting pairs", () => {
  const { module } = loadDecision();
  const seen = [];
  for (const band of BANDS) {
    for (const action of ACTIONS) {
      const { controller, container } = bind(module);
      controller.render({ band: band });
      controller.choose(action);
      seen.push(drawn(container).overrideLabel.hidden ? "no" : "yes");
      assert.equal(
        controller.overrideShown(),
        module.contradictsBand(band, action),
        band + " with " + action,
      );
    }
  }
  assert.deepEqual(host(seen).slice().sort(), [
    "no",
    "no",
    "no",
    "yes",
    "yes",
    "yes",
    "yes",
    "yes",
    "yes",
  ]);
});

test("the three choices are drawn in the abstract order, each one a radio", () => {
  const { module } = loadDecision();
  const { controller, container } = bind(module);
  controller.render({ band: "review" });
  const form = drawn(container);

  assert.deepEqual(
    form.radios.map((label) => label.children[0].value),
    ACTIONS,
  );
  for (const [at, label] of form.radios.entries()) {
    const input = label.children[0];
    assert.equal(input.tagName, "INPUT");
    assert.equal(input.type, "radio");
    assert.equal(input.name, module.ACTION_FIELD);
    assert.ok(label.classes.has("ux4g-radio"), ACTIONS[at]);
    assert.ok(label.classes.has("ux4g-radio-md"), ACTIONS[at]);
    assert.ok(input.classes.has("ux4g-radio-input"), ACTIONS[at]);
    assert.equal(textOf(label.children[2]), module.ACTION_LABELS[ACTIONS[at]]);
  }
  assert.equal(form.group.getAttribute("role"), "radiogroup");
  assert.equal(
    form.group.getAttribute("aria-labelledby"),
    form.groupLabel.id,
  );
  assert.equal(textOf(form.groupLabel), module.GROUP_LABEL);
});

test("the choices and the bands are the ones app/audit/decision.py freezes", () => {
  const { module } = loadDecision();
  const names = decisionSource.match(
    /^(?:ALLOW_ENTRY|FURTHER_INSPECTION|REJECT_ENTRY) = "([^"]+)"$/gm,
  );
  assert.ok(names, "app/audit/decision.py no longer names the officer three");
  const spelled = {};
  for (const line of names) {
    const [, name, value] = line.match(/^(\w+) = "([^"]+)"$/);
    spelled[name] = value;
  }
  const order = decisionSource.match(/OFFICER_ACTIONS = \(([^)]*)\)/);
  assert.ok(order, "app/audit/decision.py no longer orders the officer three");
  const bandOrder = decisionSource.match(/BAND_ORDER = \(([^)]*)\)/);
  assert.ok(bandOrder, "app/audit/decision.py no longer orders the bands");

  assert.deepEqual(host(module.OFFICER_ACTIONS), ACTIONS);
  assert.deepEqual(
    order[1].split(",").map((name) => spelled[name.trim()]),
    host(module.OFFICER_ACTIONS),
  );
  assert.deepEqual(
    bandOrder[1].match(/"([^"]+)"/g).map((quoted) => quoted.slice(1, -1)),
    host(module.BAND_ORDER),
  );
  assert.deepEqual(Object.keys(module.ACTION_LABELS).sort(), ACTIONS.slice().sort());
});

test("the module pairs no band with a choice, on any line or in any table", () => {
  for (const line of source.split("\n")) {
    const code = line.replace(/\/\/.*$/, "");
    const saysBand = BANDS.some((band) => says(code, band));
    const saysAction = ACTIONS.some((action) => says(code, action));
    assert.ok(
      !(saysBand && saysAction),
      "a line names a band and a choice together: " + line.trim(),
    );
  }
  const { module } = loadDecision();
  for (const [name, value] of Object.entries(module)) {
    if (!Array.isArray(value) || typeof value[0] === "string") {
      continue;
    }
    for (const entry of Object.values(value)) {
      if (!entry || typeof entry !== "object") {
        continue;
      }
      const keys = Object.keys(entry);
      const names = Object.values(entry);
      const listsBand = [...keys, ...names].some((one) =>
        BANDS.includes(one),
      );
      const listsAction = [...keys, ...names].some((one) =>
        ACTIONS.includes(one),
      );
      assert.ok(
        !(listsBand && listsAction),
        name + " pairs a band with a choice",
      );
    }
  }
});

test("every UX4G class the module writes is a class the sheet ships", () => {
  const { module } = loadDecision();
  const { controller, container } = bind(module);
  controller.render({ band: "review" });
  const form = drawn(container);
  controller.choose("reject");
  const written = classesIn(form.card);
  const sheetOnes = written.filter((name) => name.startsWith("ux4g-"));
  assert.ok(sheetOnes.length > 0);
  for (const name of sheetOnes) {
    assert.ok(
      sheet.includes("." + name),
      name + " is not a class in ux4g-web-components@2.1.0",
    );
  }
  assert.deepEqual([...form.card.classes], host(module.CARD_CLASSES));
  assert.ok(
    !written.some((name) => name.startsWith("result-")),
    "the form adds no class of this project's own",
  );
});

test("the remark is a textarea the officer writes into, and starts empty", () => {
  const { module } = loadDecision();
  const { controller, container } = bind(module);
  controller.render({ band: "low" });
  const form = drawn(container);

  assert.equal(form.remarkInput.tagName, "TEXTAREA");
  assert.ok(form.remark.classes.has("ux4g-textarea-container"));
  assert.ok(form.remark.classes.has("ux4g-textarea-default"));
  assert.ok(form.remark.classes.has("ux4g-textarea-md"));
  assert.ok(form.remarkInput.classes.has("ux4g-textarea-input"));
  assert.ok(form.remarkLabel.classes.has("ux4g-label-m-default"));
  assert.equal(form.remarkLabel.getAttribute("for"), form.remarkInput.id);
  assert.equal(textOf(form.remarkLabel), module.REMARK_LABEL);
  assert.equal(textOf(form.remarkHelper), module.REMARK_HELPER);
  assert.equal(controller.remark(), "");

  form.remarkInput.value = "Clean copy, passport expired last year.";
  assert.equal(controller.remark(), "Clean copy, passport expired last year.");
});

test("a hidden override answers false however its own input stands", () => {
  const { module } = loadDecision();
  const { controller, container } = bind(module);
  controller.render({ band: "low" });
  const form = drawn(container);

  controller.choose("allow");
  form.overrideInput.checked = true;
  assert.equal(controller.override(), false);

  controller.choose("reject");
  assert.equal(controller.override(), true);
  assert.equal(form.overrideLabel.hidden, false);

  controller.choose("allow");
  assert.equal(form.overrideLabel.hidden, true);
  assert.equal(form.overrideInput.checked, false);
  assert.equal(controller.override(), false);
});

test("one choice never leaves another's radio behind it", () => {
  const { module } = loadDecision();
  const { controller, container } = bind(module);
  controller.render({ band: "high" });
  const form = drawn(container);

  for (const action of ACTIONS) {
    controller.choose(action);
    const checked = form.radios.filter((label) => label.children[0].checked);
    assert.deepEqual(
      checked.map((label) => label.children[0].value),
      [action],
    );
    assert.equal(controller.action(), action);
  }
});

test("a row carrying no band is asked nothing and shows nothing", () => {
  const { module } = loadDecision();
  for (const result of [{}, { band: null }, { band: undefined }]) {
    const { controller, container } = bind(module);
    controller.render(result);
    assert.equal(controller.band(), null);
    assert.equal(drawn(container).overrideLabel.hidden, true);
    for (const action of ACTIONS) {
      controller.choose(action);
      assert.equal(drawn(container).overrideLabel.hidden, true);
      assert.equal(controller.overrideShown(), false);
    }
  }
});

test("a band the engine never bands in is refused by name, form standing", () => {
  const { module } = loadDecision();
  const { controller, container } = bind(module);
  controller.render({ band: "low" });
  const before = drawn(container);
  for (const band of ["LOW", "critical", 3, "toString", true]) {
    refuses(() => controller.render({ band: band }), "bad_band");
  }
  assert.equal(container.children.length, 1);
  assert.equal(container.children[0], before.card);
  assert.equal(controller.band(), "low");
});

test("a choice no officer makes is refused by name, and no radio moves", () => {
  const { module } = loadDecision();
  const { controller, container } = bind(module);
  controller.render({ band: "review" });
  const form = drawn(container);
  controller.choose("allow");

  for (const action of ["Allow", "further inspection", "", null, 1, "toString"]) {
    refuses(() => controller.choose(action), "bad_action");
  }
  assert.equal(controller.action(), "allow");
  assert.equal(form.radios[0].children[0].checked, true);
  // "review" with "allow" contradicts the band, so the override was already
  // on screen when the refusals happened and is still on screen after them.
  assert.equal(form.overrideLabel.hidden, false);
});

test("a choice before the form is drawn is refused rather than remembered", () => {
  const { module } = loadDecision();
  const { controller } = bind(module);
  refuses(() => controller.choose("allow"), "no_form");
  assert.equal(controller.action(), null);
  assert.equal(controller.band(), null);
  assert.equal(controller.remark(), null);
  refuses(() => module.bindResultDecision(), "missing_element");
  refuses(() => module.bindResultDecision({}), "missing_element");
});

test("clearing takes away only the card this module drew", () => {
  const { module } = loadDecision();
  const { controller, container } = bind(module);
  const own = createElement();
  container.appendChild(own);
  assert.equal(controller.clear(), false);
  controller.render({ band: "low" });
  controller.choose("reject");
  assert.equal(controller.clear(), true);
  assert.equal(controller.action(), null);
  assert.equal(controller.overrideShown(), false);
  assert.equal(controller.clear(), false);
  assert.deepEqual(container.children, [own]);
  refuses(() => controller.choose("allow"), "no_form");
});

test("the form sends nothing and builds no request", () => {
  const { module, sent } = loadDecision();
  const { controller } = bind(module);
  controller.render({ band: "review" });
  controller.choose("further_inspection");
  assert.deepEqual(sent, { fetches: 0, formData: 0 });
});

test("no page loads the decision form yet, so the build copies nothing", () => {
  const { staticFiles, pageFileNames } = buildFileNames();
  const pages = pageFileNames.map((fileName) =>
    fs.readFileSync(path.join(__dirname, fileName), "utf8"),
  );
  const shell = fs.readFileSync(path.join(__dirname, "shell.html"), "utf8");

  assert.ok(!staticFiles.includes("result-decision.js"));
  for (const markup of [...pages, shell]) {
    assert.doesNotMatch(markup, /result-decision\.js/);
  }
});test("the choice is posted to the screening it was made on, in the keys the request names", async () => {
  const { module, requests } = loadDecision({
    api: true,
    answer: recordedAnswer(),
  });
  const { controller, container } = bind(module);
  controller.render({ band: "review", screening_id: SCREENING_ID });
  const form = drawn(container);
  controller.choose("reject");
  form.overrideInput.checked = true;
  form.remarkInput.value = "The photo page is spliced.";

  const answer = await controller.submit();

  assert.equal(requests.length, 1, "the decision was not sent");
  const [request] = requests;
  assert.equal(
    request.url,
    BASE_URL + "/api/screenings/" + SCREENING_ID + "/decision",
  );
  assert.equal(request.init.method, "POST");
  assert.equal(request.init.headers["Content-Type"], "application/json");
  assert.deepEqual(JSON.parse(request.init.body), {
    action: "reject",
    remark: "The photo page is spliced.",
    override: true,
  });
  assert.equal(answer.decision_id, DECISION_ID);
  assert.equal(controller.locked(), true);
  assert.equal(controller.pending(), false);
});

test("a recorded decision cannot be sent again, and cannot be edited", async () => {
  const { module, requests } = loadDecision({
    api: true,
    answer: recordedAnswer(),
  });
  const { controller, container } = bind(module);
  controller.render({ band: "low", screening_id: SCREENING_ID });
  const form = drawn(container);
  controller.choose("reject");
  form.remarkInput.value = "Passport expired last year.";

  await controller.submit();

  assert.equal(controller.locked(), true);
  assert.equal(form.button.disabled, true);
  assert.equal(textOf(form.button), module.RECORDED_LABEL);
  for (const label of form.radios) {
    assert.equal(label.children[0].disabled, true, "a choice could still move");
  }
  assert.equal(form.remarkInput.disabled, true);
  assert.equal(form.overrideInput.disabled, true);

  await refusesAsync(controller.submit(), "already_recorded");
  refuses(() => controller.choose("allow"), "already_recorded");
  assert.equal(requests.length, 1, "the form was sent a second time");
  assert.equal(controller.action(), "reject");
  assert.equal(controller.remark(), "Passport expired last year.");
  assert.equal(form.radios[2].children[0].checked, true);
  assert.equal(form.radios[0].children[0].checked, false);
});

test("two presses send one decision: the second is refused while the first is in flight", async () => {
  const held = deferredAnswer(recordedAnswer());
  const { module, requests } = loadDecision({ api: true, answer: held.answer });
  const { controller, container } = bind(module);
  controller.render({ band: "review", screening_id: SCREENING_ID });
  controller.choose("further_inspection");

  const first = controller.submit();
  assert.equal(controller.pending(), true);
  assert.equal(drawn(container).button.disabled, true);
  await refusesAsync(controller.submit(), "pending");
  assert.equal(requests.length, 1, "the second press reached the service");

  held.release();
  await first;
  assert.equal(controller.locked(), true);
  assert.equal(controller.pending(), false);
});

test("a refused decision is still an officer's decision to make again", async () => {
  const { module, requests } = loadDecision({
    api: true,
    answer: refusedAnswer(422, {
      error: {
        code: "DECISION_OVERRIDE_REQUIRED",
        message: "Send override true to record it as your own.",
      },
    }),
  });
  const { controller, container } = bind(module);
  controller.render({ band: "low", screening_id: SCREENING_ID });
  controller.choose("reject");
  const form = drawn(container);

  await assert.rejects(controller.submit());

  assert.equal(controller.locked(), false);
  assert.equal(controller.pending(), false);
  assert.equal(form.button.disabled, false, "the button stayed dead");
  assert.equal(controller.action(), "reject", "the choice was taken away");
  assert.equal(requests.length, 1);
});

test("a form that cannot send says why, and reaches no service", async () => {
  const chosen = loadDecision({ api: true, answer: recordedAnswer() });
  const first = bind(chosen.module);
  first.controller.render({ band: "low", screening_id: SCREENING_ID });
  await refusesAsync(first.controller.submit(), "no_choice");

  const nameless = loadDecision({ api: true, answer: recordedAnswer() });
  const second = bind(nameless.module);
  second.controller.render({ band: "low" });
  second.controller.choose("allow");
  await refusesAsync(second.controller.submit(), "no_screening_id");

  const offline = loadDecision();
  const third = bind(offline.module);
  third.controller.render({ band: "low", screening_id: SCREENING_ID });
  third.controller.choose("allow");
  await refusesAsync(third.controller.submit(), "no_api");

  const empty = bind(chosen.module);
  await refusesAsync(empty.controller.submit(), "no_form");

  assert.deepEqual(chosen.sent, { fetches: 0, formData: 0 });
  assert.deepEqual(nameless.sent, { fetches: 0, formData: 0 });
  assert.deepEqual(offline.sent, { fetches: 0, formData: 0 });
});

test("an id no service could look up is refused by name, form standing", () => {
  const { module, sent } = loadDecision({ api: true, answer: recordedAnswer() });
  const { controller, container } = bind(module);
  controller.render({ band: "low", screening_id: SCREENING_ID });
  const before = drawn(container);

  for (const id of ["", "   ", 7, {}, ["x"]]) {
    refuses(
      () => controller.render({ band: "low", screening_id: id }),
      "bad_screening_id",
    );
  }
  assert.equal(container.children.length, 1);
  assert.equal(container.children[0], before.card);
  assert.equal(controller.band(), "low");
  assert.deepEqual(sent, { fetches: 0, formData: 0 });
});

test("the button and the line under it are the ones the preflight names", async () => {
  const { module } = loadDecision({ api: true, answer: recordedAnswer() });
  const { controller, container } = bind(module);
  controller.render({ band: "review", screening_id: SCREENING_ID });
  const form = drawn(container);

  assert.equal(form.button.tagName, "BUTTON");
  assert.equal(form.button.type, "button");
  assert.deepEqual(host([...form.button.classes]), host(module.SUBMIT_CLASSES));
  assert.equal(textOf(form.button), module.SUBMIT_LABEL);
  assert.equal(form.status.hidden, true, "an empty line is on screen");
  assert.equal(textOf(form.status), "");
  assert.equal(form.status.getAttribute("role"), module.LIVE_ROLE);
  assert.equal(form.status.getAttribute("aria-live"), module.LIVE_POLITENESS);

  controller.choose("further_inspection");
  await controller.submit();

  assert.equal(form.status.hidden, false);
  assert.equal(textOf(form.status), module.RECORDED_MESSAGE);
  assert.ok(form.status.classes.has(module.ALERT_SUCCESS_CLASS));
  assert.ok(!form.status.classes.has(module.ALERT_ERROR_CLASS));
});

test("a refusal is said on the line under the form, and the same button records it after", async () => {
  const { module, requests } = loadDecision({
    api: true,
    answer: sequenceAnswer([
      refusedAnswer(404, {
        error: { code: "SCREENING_NOT_FOUND", message: SERVICE_MESSAGE },
      }),
      recordedAnswer(),
    ]),
  });
  const { controller, container } = bind(module);
  controller.render({ band: "review", screening_id: SCREENING_ID });
  const form = drawn(container);
  controller.choose("further_inspection");

  form.button.click();
  await flush();
  assert.equal(requests.length, 1);
  assert.equal(form.status.hidden, false);
  assert.equal(textOf(form.status), SERVICE_MESSAGE);
  assert.ok(form.status.classes.has(module.ALERT_ERROR_CLASS));
  assert.equal(controller.locked(), false);

  controller.choose("further_inspection");
  form.button.click();
  await flush();
  assert.equal(requests.length, 2);
  assert.equal(controller.locked(), true);
  assert.equal(textOf(form.status), module.RECORDED_MESSAGE);
  assert.ok(form.status.classes.has(module.ALERT_SUCCESS_CLASS));
  assert.ok(!form.status.classes.has(module.ALERT_ERROR_CLASS));
});

test("a press with nothing chosen says so and sends nothing", async () => {
  const { module, requests } = loadDecision({ api: true, answer: recordedAnswer() });
  const { controller, container } = bind(module);
  controller.render({ band: "review", screening_id: SCREENING_ID });
  const form = drawn(container);

  form.button.click();
  await flush();

  assert.deepEqual(requests, []);
  assert.equal(form.status.hidden, false);
  assert.equal(textOf(form.status), module.NO_CHOICE_MESSAGE);
  assert.ok(form.status.classes.has(module.ALERT_ERROR_CLASS));
  assert.equal(controller.locked(), false);
});

test("the three keys the body carries are the ones DecisionRequest names", () => {
  const { module } = loadDecision();
  const block = schemasSource.match(
    /class DecisionRequest\(BaseModel\):\n([\s\S]*?)(?=\nclass )/,
  );
  assert.ok(block, "app.schemas no longer declares DecisionRequest");
  const named = [
    ...block[1].replace(/"""[\s\S]*?"""/g, "").matchAll(/^ {4}(\w+): /gm),
  ].map((found) => found[1]);
  assert.deepEqual(named, host(module.REQUEST_FIELDS));
});

test("the lock is what stops the second send", async () => {
  const weakened = source.split("if (locked) {").join("if (false) {");
  assert.notEqual(weakened, source, "the module no longer guards on the lock");
  const { module, requests } = loadDecision({
    api: true,
    answer: recordedAnswer(),
    source: weakened,
  });
  const { controller } = bind(module);
  controller.render({ band: "low", screening_id: SCREENING_ID });
  controller.choose("reject");

  await controller.submit();
  await controller.submit();

  assert.equal(requests.length, 2, "without the lock the form sends twice");
});