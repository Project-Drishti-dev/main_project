const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const { buildFileNames } = require("./build.cjs");

const source = fs.readFileSync(path.join(__dirname, "audit.js"), "utf8");
const pageHtml = fs.readFileSync(path.join(__dirname, "audit.html"), "utf8");
const sheet = fs.readFileSync(
  path.join(__dirname, "node_modules", "ux4g-web-components", "styles", "ux4g.css"),
  "utf8",
);

const EVENT_ID = "0f9b1c2a-3d4e-4f60-8a71-2b3c4d5e6f70";
const OTHER_EVENT_ID = "1a2b3c4d-5e6f-4071-8293-a4b5c6d7e8f9";
const BATCH_ID = "2b3c4d5e-6f70-4182-9a3b-4c5d6e7f8091";

// The root as the log spells it (D57): 64 hex characters, and the page shows
// it whole, so a test that shortened it would red this file too.
const BATCH_ROOT =
  "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90";

// The event list as 24.8 freezes it. Written once here and read back out of
// the page, so a later task that rewrites either has to change this file
// rather than quietly change the look.
const TABLE_UX4G_CLASSES = [
  "ux4g-table",
  "ux4g-table-m",
  "ux4g-table-responsive",
];
const COLUMN_NAMES = [
  "Event",
  "Result",
  "Batch id",
  "Batch root",
  "Proof length",
  "What was checked",
];

// Every class the page names, so a typo reds this suite rather than shipping.
const PAGE_UX4G_CLASSES = [
  "ux4g-table",
  "ux4g-table-m",
  "ux4g-table-responsive",
  "ux4g-card",
  "ux4g-card-body",
  "ux4g-skeleton-block",
  "ux4g-alert",
  "ux4g-alert-error",
  "ux4g-alert-content",
  "ux4g-alert-title",
  "ux4g-alert-message",
  "ux4g-alert-actions",
  "ux4g-btn",
  "ux4g-btn-outline-primary",
  "ux4g-btn-md",
  "ux4g-empty-state",
  "ux4g-empty-state-content",
  "ux4g-d-flex",
  "ux4g-gap-y-l",
];

// The three sentences app/audit/verify.py writes, one per check the walk can
// complete, spelled here so a change to the service's own wording is a change
// this file has to make rather than a string the page quietly stops matching.
const ROOT_SENTENCE =
  "The root of the batch this record belongs to was read back from the " +
  "log, which is never amended.";
const RECORD_SENTENCE =
  "The stored record was hashed again from its own row and compared with " +
  "the digest stored beside it.";
const PROOF_SENTENCE =
  "The path from this record's own place in its batch was walked up to " +
  "that root, and the two were compared.";

function verifiedAnswer(overrides = {}) {
  return {
    audit_id: EVENT_ID,
    status: "verified",
    batch_id: null,
    batch_root: null,
    proof_length: null,
    checked: [ROOT_SENTENCE, RECORD_SENTENCE],
    ...overrides,
  };
}

// The smallest element the list can be built in: children, the classes and
// the attributes they write, the listeners they answer, and nothing else, so
// a property nobody implemented here would throw rather than pass quietly.
function createElement(tagName = "div") {
  const classes = new Set();
  const attributes = new Map();
  return {
    listeners: new Map(),
    tagName: String(tagName).toUpperCase(),
    nodeType: 1,
    classes: classes,
    attributes: attributes,
    children: [],
    own: "",
    parentElement: null,
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
      attributes.set(name, String(value));
    },
    getAttribute: function (name) {
      return attributes.has(name) ? attributes.get(name) : null;
    },
    appendChild: function (child) {
      this.children.push(child);
      child.parentElement = this;
      return child;
    },
    removeChild: function (child) {
      const at = this.children.indexOf(child);
      if (at < 0) {
        throw new Error("the list removed a row it never drew");
      }
      this.children.splice(at, 1);
      child.parentElement = null;
      return child;
    },
    closest: function (selector) {
      const wanted = selector.replace(/^\.|\]$/g, "");
      for (let node = this; node !== null; node = node.parentElement) {
        if (node.classes.has(wanted)) {
          return node;
        }
      }
      return null;
    },
    addEventListener: function (type, handler) {
      const handlers = this.listeners.get(type) ?? [];
      handlers.push(handler);
      this.listeners.set(type, handlers);
    },
    click: function () {
      for (const handler of this.listeners.get("click") ?? []) {
        handler({ type: "click", target: this });
      }
    },
  };
}

function textOf(node) {
  return node.nodeType === 3 ? node.textContent : node.textContent;
}

// The module answers in another realm, so its arrays carry another realm's
// prototype. They are read back into this one before anything is compared.
function host(value) {
  return Array.from(value);
}

// The page as the module finds it: the four regions and the tbody the module
// owns, plus a recorder for every request the route was asked for.
function loadView({ ids = [EVENT_ID], answers, failWith } = {}) {
  const created = [];
  const requests = [];
  const body = createElement("tbody");
  const regions = {
    table: createElement("div"),
    count: createElement("p"),
    loading: createElement("div"),
    failure: createElement("div"),
    failureMessage: createElement("p"),
    retry: createElement("button"),
    empty: createElement("div"),
  };
  regions.table.classes.add("table-scroll");

  const sandbox = {
    URLSearchParams: URLSearchParams,
    console: console,
    window: {
      DRISHTI_API: {
        request: function (route) {
          requests.push(route);
          if (failWith) {
            return Promise.reject(failWith);
          }
          const answer =
            answers === undefined
              ? verifiedAnswer()
              : answers[requests.length - 1];
          return Promise.resolve({
            json: function () {
              return Promise.resolve(answer);
            },
          });
        },
      },
    },
    document: {
      readyState: "complete",
      getElementById: function () {
        return null;
      },
      createElement: function (tagName) {
        const element = createElement(tagName);
        created.push(element);
        return element;
      },
    },
  };
  vm.runInNewContext(source, sandbox);
  const module = sandbox.window.DRISHTI_AUDIT;
  const view = module.bindAuditView({
    body: body,
    table: regions.table,
    count: regions.count,
    loading: regions.loading,
    failure: regions.failure,
    failureMessage: regions.failureMessage,
    retry: regions.retry,
    empty: regions.empty,
    ids: ids,
  });
  return {
    module: module,
    view: view,
    body: body,
    regions: regions,
    requests: requests,
    created: created,
  };
}

// The rows the list holds, as a reader reads them: the id, the status tag's
// word and its classes, the three facts the walk reached, and the explanation
// cell -- both the text a reader sees and the individual sentences behind it.
function drawnRows(body) {
  return body.children.map(function (row) {
    const [
      idCell,
      statusCell,
      batchCell,
      rootCell,
      proofLengthCell,
      checksCell,
    ] = row.children;
    const tag = statusCell.children[0];
    const list = checksCell.children[0];
    return {
      id: idCell.textContent,
      idClasses: [...idCell.classes],
      auditId: row.getAttribute("data-audit-id"),
      verification: row.getAttribute("data-verification"),
      status: tag.textContent,
      statusKey: tag.getAttribute("data-verification"),
      statusClasses: [...tag.classes],
      batchId: batchCell.textContent,
      batchIdClasses: [...batchCell.classes],
      batchRoot: rootCell.textContent,
      batchRootClasses: [...rootCell.classes],
      proofLength: proofLengthCell.textContent,
      proofLengthClasses: [...proofLengthCell.classes],
      checks: checksCell.textContent,
      checkLines: list === undefined ? [] : list.children.map((line) => line.textContent),
    };
  });
}

/* ---------- the page ---------- */

test("the audit page is a fragment the build fills, and it marks the history section current", () => {
  for (const token of [
    "{{pageTitle}}",
    "{{pageDescription}}",
    "{{pageHeading}}",
    "{{activeNavKey}}",
    "{{content}}",
    "{{/content}}",
    "{{overlays}}",
    "{{/overlays}}",
    "{{pageScripts}}",
    "{{/pageScripts}}",
  ]) {
    assert.ok(pageHtml.includes(token), "the audit page carries " + token);
  }
  assert.ok(
    pageHtml.includes("{{activeNavKey}}screenings"),
    "the audit view is a detail view of one screening (D184)",
  );
  assert.match(pageHtml, /<script src="\.\/audit\.js"><\/script>/);
  assert.doesNotMatch(
    pageHtml,
    /aria-current="page"/,
    "the page marks no nav item the shell owns",
  );
});

test("the audit page ships the event list as a container, with no sample row", () => {
  assert.match(pageHtml, /<tbody id="audit-events-body"><\/tbody>/);
  assert.equal(
    (pageHtml.match(/<tr\b/g) ?? []).length,
    1,
    "the only row in the page is the header row",
  );
  assert.doesNotMatch(pageHtml, /data-audit-id=/);
});

test("the event list keeps the table composition and the six columns 24.10 settles", () => {
  const tag = pageHtml.slice(
    pageHtml.indexOf("<table"),
    pageHtml.indexOf(">", pageHtml.indexOf("<table")) + 1,
  );
  const classes = (/class="([^"]*)"/.exec(tag) ?? [])[1] ?? "";
  assert.deepEqual(
    classes.split(/\s+/).filter(Boolean),
    TABLE_UX4G_CLASSES,
    "the audit table keeps its four UX4G classes in order",
  );

  const head = pageHtml.slice(
    pageHtml.indexOf("<thead>"),
    pageHtml.indexOf("</thead>"),
  );
  const columns = [...head.matchAll(/<th\b[^>]*>([\s\S]*?)<\/th>/g)].map(
    ([, inner]) => inner.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim(),
  );
  assert.deepEqual(columns, COLUMN_NAMES);
});

test("the audit page names only classes the installed stylesheet ships", () => {
  for (const name of PAGE_UX4G_CLASSES) {
    assert.match(
      sheet,
      new RegExp("\\." + name + "(?![a-z0-9-])"),
      name + " is not in the installed stylesheet",
    );
  }
});

test("the module names only classes the installed stylesheet ships", () => {
  const module = loadView().module;
  for (const name of [
    module.CELL_CLASS,
    module.TAG_CLASS,
    module.TAG_SIZE_CLASS,
    ...Object.values(module.STATUS_VARIANTS),
  ]) {
    assert.match(
      sheet,
      new RegExp("\\." + name + "(?![a-z0-9-])"),
      name + " is not in the installed stylesheet",
    );
  }
});

/* ---------- the build lists ---------- */

test("the build renders the audit page and copies the module it loads", () => {
  const { pageFileNames, staticFiles } = buildFileNames();
  assert.ok(pageFileNames.includes("audit.html"));
  assert.ok(staticFiles.includes("audit.js"));
});

/* ---------- where the rows come from ---------- */

test("the route is the verification read, and an id is encoded into it", () => {
  const { module } = loadView();
  assert.equal(module.VERIFY_ROOT, "/api/audit");
  assert.equal(
    module.verifyPath("a b/c?d=1&e"),
    "/api/audit/a%20b%2Fc%3Fd%3D1%26e/verify",
  );
  assert.notEqual(
    module.verifyPath("a/b"),
    module.verifyPath("a%2Fb"),
    "an encoded id must not be able to close the path",
  );
});

test("the page is asked about every id its link names, in order", () => {
  const { module } = loadView();
  assert.deepEqual(host(module.auditIdsFromSearch("?id=" + EVENT_ID)), [EVENT_ID]);
  assert.deepEqual(
    host(
      module.auditIdsFromSearch("?id=" + EVENT_ID + "&id=" + OTHER_EVENT_ID),
    ),
    [EVENT_ID, OTHER_EVENT_ID],
  );
  assert.deepEqual(host(module.auditIdsFromSearch("id=" + EVENT_ID)), [EVENT_ID]);
  assert.deepEqual(
    host(module.auditIdsFromSearch("?id=&id=%20" + EVENT_ID + "%20")),
    [EVENT_ID],
  );
  assert.deepEqual(host(module.auditIdsFromSearch("")), []);
  assert.deepEqual(host(module.auditIdsFromSearch(undefined)), []);
});

test("load reads one route per named id and draws one row for each", async () => {
  const context = loadView({
    ids: [EVENT_ID, OTHER_EVENT_ID],
    answers: [
      verifiedAnswer(),
      verifiedAnswer({ audit_id: OTHER_EVENT_ID, status: "unknown", checked: [] }),
    ],
  });

  await context.view.load();

  assert.deepEqual(host(context.requests), [
    "/api/audit/" + EVENT_ID + "/verify",
    "/api/audit/" + OTHER_EVENT_ID + "/verify",
  ]);
  assert.deepEqual(
    drawnRows(context.body).map((row) => ({
      id: row.id,
      checks: row.checkLines.length,
    })),
    [
      { id: EVENT_ID, checks: 2 },
      { id: OTHER_EVENT_ID, checks: 0 },
    ],
  );
  assert.equal(context.regions.count.textContent, "2 recorded events");
  assert.equal(context.view.state(), "events");
});

test("one event is counted in the singular", () => {
  const { module } = loadView();
  assert.equal(module.eventCountText(1), "1 recorded event");
  assert.equal(module.eventCountText(0), "0 recorded events");
  assert.equal(module.eventCountText(4), "4 recorded events");
});

test("a row carries the id the answer held, not the id the link named", async () => {
  const context = loadView({
    answers: [verifiedAnswer({ audit_id: OTHER_EVENT_ID })],
  });

  await context.view.load();

  assert.equal(drawnRows(context.body)[0].id, OTHER_EVENT_ID);
});

/* ---------- what the page cannot read ---------- */

test("an answer it cannot read is refused by name", () => {
  const { module } = loadView();
  const refusals = [
    [null, "bad_event"],
    ["not an object", "bad_event"],
    [[], "bad_event"],
    [verifiedAnswer({ audit_id: "" }), "bad_event"],
    [verifiedAnswer({ audit_id: 7 }), "bad_event"],
    [verifiedAnswer({ status: "tampered" }), "bad_status"],
    [verifiedAnswer({ status: null }), "bad_status"],
    [verifiedAnswer({ checked: undefined }), "bad_checks"],
    [verifiedAnswer({ checked: "one" }), "bad_checks"],
    [verifiedAnswer({ checked: ["fine", ""] }), "bad_checks"],
    [verifiedAnswer({ checked: ["fine", 3] }), "bad_checks"],
    [verifiedAnswer({ batch_id: undefined }), "bad_batch"],
    [verifiedAnswer({ batch_id: "" }), "bad_batch"],
    [verifiedAnswer({ batch_id: 7 }), "bad_batch"],
    [verifiedAnswer({ batch_root: undefined }), "bad_batch"],
    [verifiedAnswer({ batch_root: " " }), "bad_batch"],
    [verifiedAnswer({ batch_root: [] }), "bad_batch"],
    [verifiedAnswer({ proof_length: undefined }), "bad_proof_length"],
    [verifiedAnswer({ proof_length: "3" }), "bad_proof_length"],
    [verifiedAnswer({ proof_length: 2.5 }), "bad_proof_length"],
    [verifiedAnswer({ proof_length: -1 }), "bad_proof_length"],
  ];

  for (const [payload, code] of refusals) {
    assert.throws(
      () => module.readEvent(payload),
      (error) => {
        assert.ok(error instanceof module.AuditViewError, "refused by name");
        assert.equal(error.code, code, JSON.stringify(payload));
        return true;
      },
    );
  }
  assert.deepEqual(
    module.readEvent(verifiedAnswer()).status,
    "verified",
  );
  for (const status of module.STATUSES) {
    assert.equal(module.readEvent(verifiedAnswer({ status: status })).status, status);
  }
});

test("an answer the page cannot read leaves the list as it stood", async () => {
  const context = loadView({
    answers: [verifiedAnswer(), verifiedAnswer({ status: "tampered" })],
    ids: [EVENT_ID, OTHER_EVENT_ID],
  });

  await context.view.load();

  assert.equal(drawnRows(context.body).length, 0, "no row was half drawn");
  assert.equal(context.view.state(), "error");
  assert.equal(context.view.error().code, "bad_status");
});

/* ---------- the states ---------- */

test("the four states are exclusive, and a state the page does not have is refused", async () => {
  const context = loadView();
  const regions = context.regions;

  for (const state of context.module.STATES) {
    context.view.showState(state);
    const shown = [
      regions.loading.hidden === false,
      regions.failure.hidden === false,
      regions.table.hidden === false,
      regions.empty.hidden === false,
    ].filter(Boolean);
    assert.equal(shown.length, 1, state + " shows one region, not " + shown.length);
  }

  assert.throws(
    () => context.view.showState("bad_state"),
    (error) => {
      assert.equal(error.code, "bad_state");
      assert.match(error.message, /events, loading, empty, error/);
      return true;
    },
  );
});

test("the skeleton's aria-busy is written by the same call that switches it", () => {
  const context = loadView();
  const loading = context.regions.loading;

  context.view.showState(context.module.STATE_LOADING);
  assert.equal(loading.getAttribute("aria-busy"), "true");
  assert.equal(loading.hidden, false);

  context.view.showState(context.module.STATE_EVENTS);
  assert.equal(loading.getAttribute("aria-busy"), "false");
  assert.equal(loading.hidden, true);
});

test("every shape of the skeleton is hidden from a screen reader", () => {
  const loading = pageHtml.slice(
    pageHtml.indexOf('id="audit-loading"'),
    pageHtml.indexOf('id="audit-error"'),
  );
  const shapes = [...loading.matchAll(/class="ux4g-skeleton-block"/g)];
  assert.equal(shapes.length, 3);
  assert.equal(
    (loading.match(/aria-hidden="true"/g) ?? []).length,
    3,
    "every shape carries aria-hidden (G2)",
  );
});

test("a page opened with no id reads nothing and says so", async () => {
  const context = loadView({ ids: [] });

  await context.view.load();

  assert.deepEqual(host(context.requests), []);
  assert.equal(context.view.state(), "empty");
  assert.equal(drawnRows(context.body).length, 0);
  assert.equal(context.regions.count.textContent, "");
});

test("a failed read is shown in the failure's own words, and is kept", async () => {
  const refusal = new Error("The server answered 422 with no error envelope.");
  const context = loadView({ failWith: refusal });

  await context.view.load();

  assert.equal(context.view.state(), "error");
  assert.equal(
    context.regions.failureMessage.textContent,
    refusal.message,
    "the alert says what the service said",
  );
  assert.equal(context.view.error(), refusal);
  assert.equal(context.regions.count.textContent, "");
});

test("the retry button reads the route again", async () => {
  const context = loadView();

  await context.view.load();
  assert.equal(context.requests.length, 1);

  context.regions.retry.click();
  await new Promise((resolve) => setImmediate(resolve));

  assert.equal(context.requests.length, 2);
});

test("a view with no tbody is refused by name", () => {
  const { module } = loadView();
  assert.throws(
    () => module.bindAuditView({}),
    (error) => {
      assert.equal(error.code, "missing_element");
      assert.match(error.message, /needs an element to draw into: body/);
      return true;
    },
  );
});

test("a view with no list of ids is refused, even an empty one is allowed", () => {
  const { module } = loadView();
  const body = createElement("tbody");
  assert.throws(
    () => module.bindAuditView({ body: body }),
    (error) => {
      assert.equal(error.code, "missing_ids");
      return true;
    },
  );
  assert.doesNotThrow(() => module.bindAuditView({ body: body, ids: [] }));
});

// The client is read when load is called, so a page that cannot reach it is a
// wiring fault the caller sees rather than an empty list it cannot explain.
function loadViewWithoutApi() {
  const body = createElement("tbody");
  const sandbox = {
    URLSearchParams: URLSearchParams,
    window: {},
    document: {
      readyState: "complete",
      getElementById: () => null,
      createElement: (tagName) => createElement(tagName),
    },
  };
  vm.runInNewContext(source, sandbox);
  return {
    view: sandbox.window.DRISHTI_AUDIT.bindAuditView({ body: body, ids: [EVENT_ID] }),
    body: body,
  };
}

test("a page that cannot reach the API client refuses by name rather than drawing", async () => {
  const context = loadViewWithoutApi();

  await assert.rejects(
    () => context.view.load(),
    (error) => {
      assert.equal(error.code, "no_api");
      assert.match(error.message, /cannot reach the API client/);
      return true;
    },
  );
  assert.equal(drawnRows(context.body).length, 0);
});

/* ---------- the refusals hold to what is wrong ---------- */

test("a state name that is not one of the four is refused rather than drawn", () => {
  const context = loadView();
  for (const state of ["", "rows", "ERROR", "loading "]) {
    assert.throws(() => context.view.showState(state), {
      code: "bad_state",
    });
  }
});

test("the check counter counts the sentences the walk completed, and nothing else", () => {
  const { module } = loadView();
  assert.equal(module.readEvent(verifiedAnswer({ checked: [] })).checks.length, 0);
  assert.equal(
    module.readEvent(verifiedAnswer({ checked: ["one", "two", "three"] })).checks.length,
    3,
  );
  // A copy, so a caller mutating what it was handed cannot rewrite the list.
  const event = module.readEvent(verifiedAnswer());
  event.checks.push("a check the walk did not run");
  assert.equal(module.readEvent(verifiedAnswer()).checks.length, 2);
});
/* ---------- 24.9: the result, and what was checked ---------- */

// The test 24.9 asks for. An `altered` event is the one answer an officer must
// not be able to miss and must not be left guessing about, so it wears its own
// tag and carries the sentence naming the check that disagreed.
test("an altered result is drawn distinct from the other two answers, and is explained", async () => {
  const ids = ["verified-event", "altered-event", "unknown-event"];
  const context = loadView({
    ids: ids,
    answers: ids.map((id, index) =>
      verifiedAnswer({
        audit_id: id,
        status: index === 2 ? "unknown" : index === 1 ? "altered" : "verified",
        checked: index === 2 ? [] : [RECORD_SENTENCE],
      }),
    ),
  });

  await context.view.load();

  const [verified, altered, unknown] = drawnRows(context.body);

  // Distinct: three answers, three tags, and none of them another's.
  assert.deepEqual(
    [verified, altered, unknown].map((row) => row.statusKey),
    ["verified", "altered", "unknown"],
    "each row says which of the three answers it is",
  );
  assert.equal(
    new Set(
      [verified, altered, unknown].map((row) => row.statusClasses.join(" ")),
    ).size,
    3,
    "the three answers are not drawn in the same tag",
  );
  assert.ok(
    altered.statusClasses.includes("ux4g-tag-filled-error"),
    "altered is the refusal of the three, so it takes the error tag",
  );
  assert.ok(
    !verified.statusClasses.includes("ux4g-tag-filled-error") &&
      !unknown.statusClasses.includes("ux4g-tag-filled-error"),
    "no other answer borrows the tag altered is drawn in",
  );

  // Explained: the word carries the meaning, and the sentence naming the
  // check that disagreed is shown rather than counted.
  assert.equal(altered.status, "Altered");
  assert.equal(verified.status, "Verified");
  assert.equal(unknown.status, "Unknown");
  assert.deepEqual(
    altered.checkLines,
    [RECORD_SENTENCE],
    "the sentence naming the check that disagreed is shown",
  );
  assert.doesNotMatch(
    altered.checks,
    /^\d+$/,
    "an explanation is not a count of checks",
  );
});

test("the explanation is the walk's own sentences, in the order it ran them", async () => {
  const context = loadView({
    answers: [
      verifiedAnswer({
        checked: [ROOT_SENTENCE, RECORD_SENTENCE, PROOF_SENTENCE],
      }),
    ],
  });

  await context.view.load();

  assert.deepEqual(drawnRows(context.body)[0].checkLines, [
    ROOT_SENTENCE,
    RECORD_SENTENCE,
    PROOF_SENTENCE,
  ]);
});

test("a walk that completed no check says so rather than drawing an empty cell", async () => {
  const context = loadView({
    answers: [verifiedAnswer({ status: "unknown", checked: [] })],
  });

  await context.view.load();

  const row = drawnRows(context.body)[0];
  assert.equal(row.checks, "No check completed.");
  assert.deepEqual(row.checkLines, []);
});

test("every status the walk answers with has a tag and a word of its own", () => {
  const { module } = loadView();
  const variants = new Set();
  const labels = new Set();
  for (const status of module.STATUSES) {
    variants.add(module.statusVariant(status));
    labels.add(module.statusLabel(status));
  }
  assert.equal(
    variants.size,
    module.STATUSES.length,
    "no two answers are drawn in one tag",
  );
  assert.equal(
    labels.size,
    module.STATUSES.length,
    "no two answers are read as one word",
  );
});

test("a status the walk never answers with is refused by name", () => {
  const { module } = loadView();
  for (const status of ["", "tampered", "toString", "VERIFIED", null, 3]) {
    assert.throws(() => module.statusVariant(status), { code: "bad_status" });
    assert.throws(() => module.statusLabel(status), { code: "bad_status" });
  }
  assert.equal(module.statusVariant("altered"), "ux4g-tag-filled-error");
  assert.equal(module.statusLabel("altered"), "Altered");
});

/* ---------- 24.10: the batch, the root, and the path that was walked ---------- */

test("the batch, the root and the proof length are drawn as the walk reported them", async () => {
  const context = loadView({
    answers: [
      verifiedAnswer({
        batch_id: BATCH_ID,
        batch_root: BATCH_ROOT,
        proof_length: 3,
        checked: [ROOT_SENTENCE, RECORD_SENTENCE, PROOF_SENTENCE],
      }),
    ],
  });

  await context.view.load();

  const row = drawnRows(context.body)[0];
  assert.equal(row.batchId, BATCH_ID, "the batch the walk reached is shown");
  assert.equal(
    row.batchRoot,
    BATCH_ROOT,
    "the root is shown as the log spells it (D57)",
  );
  assert.equal(
    row.batchRoot.length,
    64,
    "the root is shown whole: a shortened one cannot be compared to the anchor",
  );
  assert.equal(row.proofLength, "3", "the walked path's length is shown");
  assert.deepEqual(
    row.checkLines,
    [ROOT_SENTENCE, RECORD_SENTENCE, PROOF_SENTENCE],
    "24.9's explanation is untouched by the three columns beside it",
  );
});

test("a proof length of zero is a path walked, not a fact missing", async () => {
  const context = loadView({
    answers: [verifiedAnswer({ proof_length: 0 })],
  });

  await context.view.load();

  assert.equal(
    drawnRows(context.body)[0].proofLength,
    "0",
    "a batch of one leaf has a path of none, and 0 says so",
  );
});

test("a fact the walk never reached says so rather than standing blank", async () => {
  const context = loadView({
    answers: [verifiedAnswer({ status: "unknown", checked: [] })],
  });

  await context.view.load();

  const row = drawnRows(context.body)[0];
  for (const [name, cell] of [
    ["batch id", row.batchId],
    ["batch root", row.batchRoot],
    ["proof length", row.proofLength],
  ]) {
    assert.equal(cell, context.module.ABSENT_LABEL, name + " says it is missing");
    assert.notEqual(cell, "", name + " is never a blank cell");
  }
});

test("a batch reached with no root read is drawn as one fact and not the other", async () => {
  // Reachable: the row carries a batch, and the log entry behind it does not
  // answer, so the walk reaches the batch and never reads a root.
  const context = loadView({
    answers: [
      verifiedAnswer({
        status: "unknown",
        batch_id: BATCH_ID,
        batch_root: null,
        proof_length: null,
        checked: [],
      }),
    ],
  });

  await context.view.load();

  const row = drawnRows(context.body)[0];
  assert.equal(row.batchId, BATCH_ID, "the batch the walk did reach is shown");
  assert.equal(row.batchRoot, context.module.ABSENT_LABEL);
  assert.equal(row.proofLength, context.module.ABSENT_LABEL);
});

test("the read event carries the three facts as they were sent", () => {
  const { module } = loadView();
  const event = module.readEvent(
    verifiedAnswer({
      batch_id: BATCH_ID,
      batch_root: BATCH_ROOT,
      proof_length: 12,
    }),
  );
  assert.equal(event.batchId, BATCH_ID);
  assert.equal(event.batchRoot, BATCH_ROOT);
  assert.equal(event.proofLength, 12, "a length is a count, not prose");
  const unreached = module.readEvent(verifiedAnswer());
  assert.equal(unreached.batchId, null);
  assert.equal(unreached.batchRoot, null);
  assert.equal(unreached.proofLength, null);
});

test("a proof length that is not a whole count of steps is refused by name", () => {
  const { module } = loadView();
  for (const value of ["3", 2.5, -1, NaN, Infinity, true, undefined]) {
    assert.throws(
      () => module.readEvent(verifiedAnswer({ proof_length: value })),
      { code: "bad_proof_length" },
      String(value) + " is not a count of steps",
    );
  }
  assert.equal(module.readProofLength(0), 0);
  assert.equal(module.readProofLength(null), null);
  assert.equal(module.readProofLength(17), 17);
});

test("a batch fact that is not an id or a root is refused by name", () => {
  const { module } = loadView();
  assert.equal(module.readFact(BATCH_ID, "bad_batch", "not a fact"), BATCH_ID);
  assert.equal(module.readFact(null, "bad_batch", "not a fact"), null);
  for (const value of ["", "   ", 7, [], {}, true]) {
    assert.throws(() => module.readFact(value, "bad_batch", "not a fact"), {
      code: "bad_batch",
    });
  }
});

test("only the columns that truncate carry the truncating class", async () => {
  const context = loadView({
    answers: [
      verifiedAnswer({
        batch_id: BATCH_ID,
        batch_root: BATCH_ROOT,
        proof_length: 3,
      }),
    ],
  });

  await context.view.load();

  // ux4g-table-cell-text ends a cell in an ellipsis. It belongs on the two
  // ids, and nowhere the root: an ellipsised root is a commitment a reader
  // cannot check, and the count is short enough not to need it.
  const row = drawnRows(context.body)[0];
  assert.deepEqual(row.batchIdClasses, [context.module.CELL_CLASS]);
  assert.deepEqual(row.batchRootClasses, []);
  assert.deepEqual(row.proofLengthClasses, []);
});