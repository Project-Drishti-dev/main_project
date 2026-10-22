const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const {
  PLACEHOLDER_STATION_LABEL,
  STATION_LABEL_ENV_VAR,
  buildFileNames,
} = require("./build.cjs");

const source = fs.readFileSync(path.join(__dirname, "result-actor.js"), "utf8");
const sheet = fs.readFileSync(
  path.join(__dirname, "node_modules", "ux4g-web-components", "styles", "ux4g.css"),
  "utf8",
);
const apiConfig = fs.readFileSync(
  path.join(__dirname, "api-config.js"),
  "utf8",
);

const TEXT_NODE = 3;

// The smallest element the display can be built on: the classes, the
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
      if (at === -1) {
        throw new Error("the display removed a card it never drew");
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
// to fail on rather than silently absent: the display reads one configured
// label and must reach no endpoint for it.
function loadModule() {
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
      throw new Error("the actor display must not send anything");
    },
    FormData: function () {
      sent.formData += 1;
      throw new Error("the actor display must not build a request");
    },
  };
  vm.runInNewContext(source, sandbox);
  return {
    actor: sandbox.window.DRISHTI_RESULT_ACTOR,
    created: created,
    sent: sent,
  };
}

function bind(module, options = {}) {
  const container = createElement();
  const controller = module.bindResultActor({ container: container, ...options });
  return { controller: controller, container: container };
}

// The block as the page receives it: the card, the heading row, and the one
// row of the table with its label beside the value.
function drawn(container) {
  const [card] = container.children;
  const [heading, table] = card.children;
  const [title] = heading.children;
  const [caption, body] = table.children;
  const [row] = body.children;
  const [head, cell] = row.children;
  return {
    card: card,
    heading: heading,
    table: table,
    title: title,
    caption: caption,
    body: body,
    row: row,
    head: head,
    cell: cell,
    label: textOf(head),
    value: textOf(cell),
    text: textOf(card),
  };
}

function refuses(call, code) {
  assert.throws(call, (error) => {
    assert.equal(error.name, "ResultActorError");
    assert.equal(error.code, code);
    return true;
  });
}

const STATION = "BLR-GATE-3";

test("the configured station label is shown as the actor on the page", () => {
  const { actor } = loadModule();
  const { controller, container } = bind(actor);
  controller.render(STATION);
  const block = drawn(container);

  assert.equal(textOf(block.title), actor.HEADING);
  assert.equal(block.label, actor.STATION_LABEL);
  assert.equal(block.value, STATION);
  assert.equal(controller.actor(), STATION);
  assert.ok(controller.rendered());
  assert.ok(block.text.includes(STATION));
});

test("the caption says the value is a station and not a person", () => {
  const { actor } = loadModule();
  const { controller, container } = bind(actor);
  controller.render(STATION);
  const block = drawn(container);
  const caption = textOf(block.caption);

  assert.ok(block.caption.classes.has(actor.CAPTION_CLASS));
  assert.equal(caption, actor.CAPTION_TEXT);
  assert.match(caption, /station/i);
  assert.match(caption, /not a person/i);
});

test("the station sits beside a row header that names it", () => {
  const { actor } = loadModule();
  const { controller, container } = bind(actor);
  controller.render(STATION);
  const block = drawn(container);

  assert.equal(block.body.children.length, 1);
  assert.equal(block.head.tagName, "TH");
  assert.equal(block.head.attributes.scope, "row");
  assert.equal(block.cell.tagName, "TD");
  assert.ok(block.cell.classes.has(actor.CELL_CLASS));
});

test("every UX4G class the module writes is a class the sheet ships", () => {
  const { actor } = loadModule();
  const { controller, container } = bind(actor);
  controller.render(STATION);
  const block = drawn(container);

  const written = [
    ...block.card.classes,
    ...block.heading.classes,
    ...block.table.classes,
    ...block.caption.classes,
    ...block.cell.classes,
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
  // The sheet styles all of this, so no class of this project's own is
  // written and the G9 list is unchanged.
  assert.deepEqual(
    names.filter((name) => !name.startsWith("ux4g-")),
    [],
  );
});

test("the display collects nothing: it writes no control and no attribute one would hang a credential on", () => {
  const { actor, created } = loadModule();
  const { controller } = bind(actor);
  controller.render(STATION);

  const collecting = created.filter(function (node) {
    return ["INPUT", "TEXTAREA", "SELECT", "FORM", "BUTTON"].includes(node.tagName);
  });
  assert.deepEqual(collecting, []);

  const written = created.flatMap(function (node) {
    return Object.keys(node.attributes);
  });
  for (const name of written) {
    assert.ok(
      !["type", "name", "id", "autocomplete", "formaction", "value"].includes(name),
      "the display wrote a " + name + ", which is where a credential would hang",
    );
  }
});

test("the same station draws the same block however often it is asked", () => {
  const { actor } = loadModule();
  const { controller, container } = bind(actor);
  controller.render(STATION);
  const first = drawn(container);
  controller.render("  " + STATION + "  ");
  const second = drawn(container);

  assert.equal(container.children.length, 1);
  assert.equal(second.value, STATION);
  assert.equal(second.label, first.label);
  assert.equal(second.value, STATION);
  assert.equal(controller.actor(), STATION);
});

test("a second station replaces the first rather than joining it", () => {
  const { actor } = loadModule();
  const { controller, container } = bind(actor);
  controller.render(STATION);
  controller.render("MUM-ARRIVALS-2");
  const block = drawn(container);

  assert.equal(container.children.length, 1);
  assert.equal(block.value, "MUM-ARRIVALS-2");
  assert.equal(controller.actor(), "MUM-ARRIVALS-2");
});

test("a station nobody configured is refused by name", () => {
  const { actor } = loadModule();
  for (const value of [null, undefined, "", "   ", 42, {}, ["BLR-GATE-3"]]) {
    refuses(() => bind(actor).controller.render(value), "bad_station_label");
  }
});

test("a label read and refused leaves the display exactly as it was", () => {
  const { actor } = loadModule();
  const { controller, container } = bind(actor);
  controller.render(STATION);
  refuses(() => controller.render(""), "bad_station_label");

  assert.equal(container.children.length, 1);
  assert.equal(drawn(container).value, STATION);
  assert.equal(controller.actor(), STATION);
});

test("a binding is refused by cause when it has no container", () => {
  const { actor } = loadModule();
  refuses(() => actor.bindResultActor(), "missing_element");
  refuses(() => actor.bindResultActor({}), "missing_element");
  assert.deepEqual(host(actor.REQUIRED_ELEMENTS), ["container"]);
});

test("clearing takes away only the block this module drew", () => {
  const { actor } = loadModule();
  const { controller, container } = bind(actor);
  const own = createElement();
  container.appendChild(own);
  assert.equal(controller.clear(), false);
  assert.equal(controller.rendered(), false);

  controller.render(STATION);
  assert.equal(controller.clear(), true);
  assert.equal(controller.rendered(), false);
  assert.equal(controller.actor(), null);
  assert.equal(controller.clear(), false);
  assert.deepEqual(container.children, [own]);
});

test("the display sends nothing and builds no request", () => {
  const { actor, sent } = loadModule();
  const { controller } = bind(actor);
  controller.render(STATION);
  controller.render("MUM-ARRIVALS-2");
  assert.deepEqual(sent, { fetches: 0, formData: 0 });
});

test("the station is configured at build time and defaults to the placeholder the trail already stamps", () => {
  assert.equal(STATION_LABEL_ENV_VAR, "DRISHTI_STATION_LABEL");
  assert.equal(PLACEHOLDER_STATION_LABEL, "station-unset");
  // The page and the audit trail must not disagree about what an unset
  // station looks like, so the one string is held against the other.
  const emit = fs.readFileSync(
    path.join(__dirname, "..", "backend", "app", "audit", "emit.py"),
    "utf8",
  );
  assert.match(
    emit,
    new RegExp('PLACEHOLDER_ACTOR\\s*=\\s*"' + PLACEHOLDER_STATION_LABEL + '"'),
  );
  // The source copy a served-from-source checkout reads carries the same
  // default the build writes, so the two cannot drift apart.
  assert.match(
    apiConfig,
    /stationLabel:\s*"station-unset"/,
  );
});

test("no page loads the display yet, so the build copies nothing", () => {
  const { staticFiles, pageFileNames } = buildFileNames();
  const pages = pageFileNames.map((fileName) =>
    fs.readFileSync(path.join(__dirname, fileName), "utf8"),
  );
  const shell = fs.readFileSync(path.join(__dirname, "shell.html"), "utf8");

  assert.ok(!staticFiles.includes("result-actor.js"));
  for (const markup of [...pages, shell]) {
    assert.doesNotMatch(markup, /result-actor\.js/);
  }
});

/* The credential claim is read off the whole shipped frontend rather than off
   a list of files a case happens to know, so a new page is covered the day it
   is written.  node_modules/ and dist/ are what the build fetched and wrote,
   and a *.test.cjs file is never shipped: all three are out, because the claim
   is about what a browser is handed. */
function shippedSourceFiles() {
  const names = [];
  for (const entry of fs.readdirSync(__dirname, { withFileTypes: true })) {
    if (!entry.isFile()) continue;
    if (entry.name.endsWith(".test.cjs")) continue;
    if (![".html", ".js", ".css"].includes(path.extname(entry.name))) continue;
    names.push(entry.name);
  }
  return names.sort();
}

const shipped = shippedSourceFiles();

// The words a credential or a session is spelled with.  Matched against an
// attribute, a property or a value a control carries, never against prose:
// about.html and profile.html both say in words that this build has no
// password, and a sentence is not an input.
const CREDENTIAL_WORDS =
  "(?:pass(?:word|wd|phrase)|credential|secret|api[-_]?key|access[-_]?key|" +
  "token|session|jwt|bearer|username|user[-_]?id|officer[-_]?id|" +
  "log[-_]?in|sign[-_]?in)";
const CREDENTIAL = new RegExp(CREDENTIAL_WORDS, "i");

// The attributes that decide what a control collects, for a value written as
// markup or as a property.  \b so a class or a grid cannot be read as an id.
const VALUE_ATTRIBUTE = "(?:type|name|id|autocomplete|formaction|action|value)";
const BY_ASSIGNMENT =
  new RegExp("\\b" + VALUE_ATTRIBUTE + "\\s*=\\s*[\"']?([^\"'\\s>;,)]+)", "gi");
const BY_SET_ATTRIBUTE =
  /setAttribute\(\s*["']([a-z-]+)["']\s*,\s*["']([^"']*)["']\s*\)/gi;

// What a control carries that a credential could be written into.  Null when
// it carries nothing of the kind, so a caller can say which fragment was the
// offending one rather than only that something was.
function credentialIn(text) {
  for (let found = BY_ASSIGNMENT.exec(text); found; found = BY_ASSIGNMENT.exec(text)) {
    if (CREDENTIAL.test(found[1])) return found[0];
  }
  BY_SET_ATTRIBUTE.lastIndex = 0;
  for (let found = BY_SET_ATTRIBUTE.exec(text); found; found = BY_SET_ATTRIBUTE.exec(text)) {
    if (new RegExp("\\b" + VALUE_ATTRIBUTE + "\\b", "i").test(found[1]) && CREDENTIAL.test(found[2])) {
      return found[0];
    }
  }
  // A credential word anywhere else in the control is a hit too, so an
  // attribute this list has never heard of cannot walk past the claim.
  BY_ASSIGNMENT.lastIndex = 0;
  if (CREDENTIAL.test(text)) return text.trim().replace(/\s+/g, " ");
  return null;
}

// Every value-collecting control in a file, written as markup or built in
// script, so a control cannot escape the claim by being assembled rather than
// typed.  A script-built control is read as the call plus what the script
// goes on to set on it.
const MARKUP_CONTROL = /<(input|textarea|select|form)\b([^>]*)>/gi;
const BUILT_CONTROL = /createElement\(\s*["'](input|textarea|select|form)["'][\s\S]{0,200}/gi;

function credentialControls(fileSource) {
  const hits = [];
  for (const scan of [MARKUP_CONTROL, BUILT_CONTROL]) {
    scan.lastIndex = 0;
    for (let found = scan.exec(fileSource); found; found = scan.exec(fileSource)) {
      const hit = credentialIn(found[0]);
      if (hit !== null) hits.push(hit);
    }
  }
  return hits;
}

// What holds a session: the store a session lives in, the cookie jar, and the
// ways a request carries a credential of its own.
const SESSION_CARRIERS = [
  ["session storage", /\bsessionStorage\b/],
  ["a cookie", /\bdocument\.cookie\b|\bcookieStore\b/],
  ["an authorization header", /\bAuthorization\b/],
  ["a bearer token", /\bBearer\s/],
  ["credentials on a request", /\bcredentials\s*:\s*["'](?:include|same-origin)["']/],
  ["a stored session key", /\b(?:get|set|remove)Item\(\s*["'][^"']*(?:token|session|auth|jwt|credential)/i],
];

function sessionCarriers(fileSource) {
  return SESSION_CARRIERS.filter(function (carrier) {
    return carrier[1].test(fileSource);
  }).map(function (carrier) {
    return carrier[0];
  });
}

test("no page or script in the frontend takes a credential or holds a session", () => {
  // Shown failing first, so neither scan can pass by refusing everything.
  const controlFixtures = [
    '<input class="ux4g-input-input" type="password" name="officer-pin" />',
    '<input id="session-token" autocomplete="current-password" />',
    '<textarea name="api_key" />',
    'const field = document.createElement("input"); field.name = "bearerToken";',
    'const field = document.createElement("input"); field.setAttribute("name", "officer-token");',
  ];
  for (const fixture of controlFixtures) {
    assert.ok(
      credentialControls(fixture).length > 0,
      "this scan would not notice: " + fixture,
    );
  }
  const carrierFixtures = [
    "window.sessionStorage.setItem(key, value);",
    "document.cookie = name + '=' + value;",
    'headers: { Authorization: "Bearer " + token },',
    'fetch(url, { credentials: "include" });',
    'localStorage.setItem("session-token", value);',
  ];
  for (const fixture of carrierFixtures) {
    assert.ok(
      sessionCarriers(fixture).length > 0,
      "this scan would not notice: " + fixture,
    );
  }

  // Shown passing, so the scans are not refused by a rule too wide to be
  // true: the controls this frontend really does collect are not credentials.
  assert.deepEqual(
    credentialControls(
      '<input class="ux4g-input-input" id="avatar-file" type="file" accept="image/png" />',
    ),
    [],
  );
  assert.deepEqual(
    credentialControls('<input name="remark" type="text" autocomplete="off" />'),
    [],
  );
  assert.deepEqual(sessionCarriers("window.localStorage.setItem(key, value);"), []);

  assert.ok(shipped.length > 10, "the scan should have files to read");
  const found = [];
  for (const fileName of shipped) {
    const fileSource = fs.readFileSync(path.join(__dirname, fileName), "utf8");
    for (const hit of credentialControls(fileSource)) {
      found.push(fileName + " collects a credential: " + hit);
    }
    for (const carrier of sessionCarriers(fileSource)) {
      found.push(fileName + " holds a session through " + carrier);
    }
  }
  assert.deepEqual(found, []);
});