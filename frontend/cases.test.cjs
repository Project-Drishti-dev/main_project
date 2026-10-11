const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const { buildFileNames } = require("./build.cjs");

const source = fs.readFileSync(path.join(__dirname, "cases.js"), "utf8");
const pageHtml = fs.readFileSync(path.join(__dirname, "cases.html"), "utf8");
const sheet = fs.readFileSync(
  path.join(__dirname, "node_modules", "ux4g-web-components", "styles", "ux4g.css"),
  "utf8",
);

// The tier spelling cases.js filters on, read out of the service rather than
// recalled: "grep before you copy" is a rule in tasks.md, and a tier renamed
// in app/risk/flags.py must red this file rather than quietly empty the card.
const flagsSource = fs.readFileSync(
  path.join(__dirname, "..", "backend", "app", "risk", "flags.py"),
  "utf8",
);
const flagIdsSource = fs.readFileSync(
  path.join(__dirname, "..", "backend", "app", "risk", "flag_ids.py"),
  "utf8",
);

// The two tables cases.js holds a copy of, read from their owners so a change
// to either is a change this file has to make.
const resultBandSource = fs.readFileSync(
  path.join(__dirname, "result-band.js"),
  "utf8",
);
const formatSource = fs.readFileSync(path.join(__dirname, "format.js"), "utf8");

const PASSPORT_ID = "3c4d5e6f-7081-4293-a4b5-c6d7e8f9012";
const VISA_ID = "4d5e6f70-8192-43a4-b5c6-d7e8f9012345";
const UNKNOWN_ID = "5e6f7081-9234-44b5-c6d7-e8f901234567";
const SECOND_PASSPORT_ID = "6f708192-3344-45b6-c7d8-e9f0a1b2c3d4";

const NAME_MISMATCH_LABEL = "Names do not match across the documents";
const NAME_MISMATCH_REASON =
  "The surname on the visa does not match the surname on the passport.";
const PASSPORT_REFERENCE_LABEL = "The passport is not one we have seen";
const PASSPORT_REFERENCE_REASON =
  "This visa names a passport number no screening in this case recorded.";

// A flag of a tier scoped to one document. It belongs on the result page and
// must never reach a case card.
const TIER0_LABEL = "Check digit does not match";

function crossdocFlag(overrides = {}) {
  return {
    id: "CROSSDOC_NAME_MISMATCH",
    tier: "crossdoc",
    label: NAME_MISMATCH_LABEL,
    reason: NAME_MISMATCH_REASON,
    ...overrides,
  };
}

function passportAnswer(overrides = {}) {
  return {
    screening_id: PASSPORT_ID,
    status: "completed",
    document_type: "passport",
    created_at: "2026-10-05T09:15:00+00:00",
    score: 12.5,
    band: "low",
    flags: [],
    ...overrides,
  };
}

function visaAnswer(overrides = {}) {
  return {
    screening_id: VISA_ID,
    status: "completed",
    document_type: "visa",
    created_at: "2026-10-05T09:16:00+00:00",
    score: 74,
    band: "high",
    flags: [crossdocFlag()],
    ...overrides,
  };
}

// Every class the page names, so a typo reds this suite rather than shipping.
const PAGE_UX4G_CLASSES = [
  "ux4g-card",
  "ux4g-card-body",
  "ux4g-grid",
  "ux4g-grid-cols-1",
  "ux4g-md-grid-cols-2",
  "ux4g-xl-grid-cols-3",
  "ux4g-gap-m",
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
];

// The smallest element a card can be built in: children, the classes and the
// attributes they write, the listeners they answer, and nothing else, so a
// property nobody implemented here would throw rather than pass quietly.
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
        throw new Error("the grid removed a card it never drew");
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

function createTextNode(value) {
  return { nodeType: 3, textContent: String(value), children: [] };
}

function textOf(node) {
  return node.textContent;
}

// The module answers in another realm, so its arrays carry another realm's
// prototype. They are read back into this one before anything is compared.
function host(value) {
  return Array.from(value);
}

// The page as the module finds it: the grid the module owns, the four regions
// around it, and a recorder for every request the route was asked for.
function loadView({ ids = [PASSPORT_ID, VISA_ID], answers, failWith } = {}) {
  const created = [];
  const requests = [];
  const grid = createElement("div");
  grid.classes.add("ux4g-grid");
  const regions = {
    count: createElement("p"),
    loading: createElement("div"),
    failure: createElement("div"),
    failureMessage: createElement("p"),
    retry: createElement("button"),
    empty: createElement("div"),
    single: createElement("div"),
  };

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
              ? [passportAnswer(), visaAnswer()][requests.length - 1]
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
      createTextNode: createTextNode,
    },
  };
  vm.runInNewContext(source, sandbox);
  const module = sandbox.window.DRISHTI_CASES;
  const view = module.bindCaseView({
    grid: grid,
    count: regions.count,
    loading: regions.loading,
    failure: regions.failure,
    failureMessage: regions.failureMessage,
    retry: regions.retry,
    empty: regions.empty,
    single: regions.single,
    ids: ids,
  });
  return {
    module: module,
    view: view,
    grid: grid,
    regions: regions,
    requests: requests,
    created: created,
  };
}

// The cards the grid holds, as a reader reads them: the kind of document, the
// screening id, the band tag's word and its classes, the score, and the
// cross-document flags behind both the text and the individual entries. A card
// in a case of one document carries no cross-document section at all, so the
// three cross-document fields read null rather than a fourth child.
function drawnCards(grid) {
  return grid.children.map(function (card) {
    const [typeHeading, idLine, bandRow, crossdoc] = card.children[0].children;
    const tag = bandRow.children[0];
    const score = bandRow.children[1];
    const crossdocHeading =
      crossdoc === undefined ? null : crossdoc.children[0];
    const body = crossdoc === undefined ? null : crossdoc.children[1];
    const list = body !== null && body.tagName === "UL" ? body : null;
    return {
      cardClasses: [...card.classes],
      screeningId: card.getAttribute("data-screening-id"),
      band: card.getAttribute("data-band"),
      documentType: typeHeading.textContent,
      idText: idLine.textContent,
      bandWord: tag.textContent,
      bandTagClasses: [...tag.classes],
      tagBand: tag.getAttribute("data-band"),
      score: score === undefined ? null : score.textContent,
      crossdocHeading:
        crossdocHeading === null ? null : crossdocHeading.textContent,
      crossdocText: body === null ? null : body.textContent,
      crossdocFlags:
        list === null
          ? []
          : list.children.map((item) => ({
              label: item.children[0].textContent,
              reason: item.children[1].textContent,
            })),
    };
  });
}

/* ---------- the page ---------- */

test("the case page is a fragment the build fills, and it marks the history section current", () => {
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
    assert.ok(pageHtml.includes(token), "the case page carries " + token);
  }
  assert.ok(
    pageHtml.includes("{{activeNavKey}}screenings"),
    "a case is a detail view of stored screenings, so the history section owns it",
  );
  assert.ok(
    pageHtml.includes('<script src="./cases.js"></script>'),
    "the page loads the module that draws the documents",
  );
});

test("the page ships a container, not a record: no document is written into the markup", () => {
  const open = pageHtml.indexOf('id="case-documents"');
  const inner = pageHtml.slice(
    pageHtml.indexOf(">", open) + 1,
    pageHtml.indexOf("</div>", pageHtml.indexOf(">", open) + 1),
  );
  assert.equal(inner.trim(), "", "the grid element is empty");
  for (const drawn of ["<article", "data-screening-id", "data-band"]) {
    assert.ok(
      !pageHtml.includes(drawn),
      "the markup draws no document: " + drawn,
    );
  }
});

test("every UX4G class the page names ships in 2.1.0", () => {
  for (const className of PAGE_UX4G_CLASSES) {
    assert.ok(
      sheet.includes("." + className),
      "the installed sheet carries ." + className,
    );
  }
});

test("the page adds no CSS of its own and claims no class the sheet does not ship", () => {
  assert.ok(
    !pageHtml.includes("<style"),
    "a page with no stylesheet block needs no custom CSS",
  );
  assert.ok(
    !pageHtml.includes('class="case-'),
    "every class on the page is one the sheet or another page already ships",
  );
});

test("the documents sit side by side in a grid that is never narrower than one column", () => {
  const { module } = loadView();
  assert.deepEqual(host(module.GRID_CLASSES), [
    "ux4g-grid",
    "ux4g-grid-cols-1",
    "ux4g-md-grid-cols-2",
    "ux4g-xl-grid-cols-3",
    "ux4g-gap-m",
  ]);
  assert.ok(
    pageHtml.includes('class="' + module.GRID_CLASSES.join(" ") + '"'),
    "the page's own grid carries that composition",
  );
  for (const className of module.GRID_CLASSES) {
    assert.ok(
      sheet.includes("." + className),
      "the installed sheet carries ." + className,
    );
  }
});

test("the build renders the case page and copies the module it loads", () => {
  const { pageFileNames, staticFiles } = buildFileNames();
  assert.ok(pageFileNames.includes("cases.html"), "the build renders cases.html");
  assert.ok(staticFiles.includes("cases.js"), "the build copies cases.js");
});

test("the page carries no credential or session input anywhere", () => {
  for (const forbidden of [
    "type=\"password\"",
    "autocomplete=\"current-password\"",
    "autocomplete=\"new-password\"",
    "name=\"password\"",
  ]) {
    assert.ok(
      !pageHtml.includes(forbidden),
      "the case page carries no " + forbidden,
    );
  }
});

/* ---------- the read ---------- */

test("the documents are read one screening at a time, from the screenings route", async () => {
  const harness = loadView({ ids: [PASSPORT_ID, VISA_ID] });
  await harness.view.load();
  assert.deepEqual(harness.requests, [
    "/api/screenings/" + PASSPORT_ID,
    "/api/screenings/" + VISA_ID,
  ]);
});

test("a screening id is encoded into the path rather than pasted", () => {
  const { module } = loadView();
  assert.equal(
    module.screeningPath("../../admin"),
    "/api/screenings/..%2F..%2Fadmin",
  );
});

test("the query string is read whole, and a blank parameter names no document", () => {
  const { module } = loadView();
  assert.deepEqual(host(module.screeningIdsFromSearch("?id=" + VISA_ID)), [
    VISA_ID,
  ]);
  assert.deepEqual(
    host(module.screeningIdsFromSearch("?id=a&id=b&id=c")),
    ["a", "b", "c"],
  );
  assert.deepEqual(host(module.screeningIdsFromSearch("?id=a&id=%20&id=b")), [
    "a",
    "b",
  ]);
  assert.deepEqual(host(module.screeningIdsFromSearch("")), []);
  assert.deepEqual(host(module.screeningIdsFromSearch("?other=1")), []);
});

/* ---------- the documents ---------- */

test("one card per document, in the order the link named them", async () => {
  const harness = loadView({ ids: [PASSPORT_ID, VISA_ID] });
  await harness.view.load();
  const cards = drawnCards(harness.grid);
  assert.equal(cards.length, 2);
  assert.deepEqual(
    cards.map((card) => card.documentType),
    ["passport", "visa"],
  );
  assert.deepEqual(
    cards.map((card) => card.screeningId),
    [PASSPORT_ID, VISA_ID],
  );
  assert.equal(harness.view.state(), "documents");
  assert.deepEqual(
    host(harness.view.documents()).map((entry) => entry.documentType),
    ["passport", "visa"],
  );
});

test("each card carries the screening id, so two documents of one kind are tellable apart", async () => {
  const harness = loadView({
    ids: [PASSPORT_ID, SECOND_PASSPORT_ID],
    answers: [
      passportAnswer(),
      passportAnswer({ screening_id: SECOND_PASSPORT_ID }),
    ],
  });
  await harness.view.load();
  const [first, second] = drawnCards(harness.grid);
  assert.deepEqual(
    [first.documentType, second.documentType],
    ["passport", "passport"],
    "two of the same kind of document",
  );
  assert.equal(first.idText, "Screening id: " + PASSPORT_ID);
  assert.equal(first.screeningId, PASSPORT_ID);
  assert.equal(second.idText, "Screening id: " + SECOND_PASSPORT_ID);
  assert.equal(second.screeningId, SECOND_PASSPORT_ID);
});

test("each card carries its document's band as a tag, and the word beside the colour", async () => {
  const harness = loadView({
    ids: [PASSPORT_ID, VISA_ID],
    answers: [passportAnswer({ band: "low" }), visaAnswer({ band: "high" })],
  });
  await harness.view.load();
  const [passport, visa] = drawnCards(harness.grid);
  assert.deepEqual(passport.bandTagClasses, [
    "ux4g-tag",
    "ux4g-tag-s",
    "ux4g-tag-filled-success",
  ]);
  assert.equal(passport.bandWord, "Low Risk");
  assert.equal(passport.tagBand, "low");
  assert.deepEqual(visa.bandTagClasses, [
    "ux4g-tag",
    "ux4g-tag-s",
    "ux4g-tag-filled-error",
  ]);
  assert.equal(visa.bandWord, "High Risk");
  assert.equal(visa.tagBand, "high");
});

test("the band variants and labels are the ones result-band.js and format.js already use", async () => {
  const { module } = loadView();
  for (const [band, variant] of Object.entries(module.BAND_VARIANTS)) {
    assert.ok(
      resultBandSource.includes(band + ': "' + variant + '"'),
      "result-band.js bands " + band + " as " + variant,
    );
  }
  for (const [band, label] of Object.entries(module.BAND_LABELS)) {
    assert.ok(
      formatSource.includes(band + ': "' + label + '"'),
      "format.js labels " + band + " as " + label,
    );
  }
  assert.deepEqual(host(Object.keys(module.BAND_VARIANTS)), [
    "low",
    "review",
    "high",
  ]);
  assert.equal(module.bandVariant("review"), "ux4g-tag-filled-warning");
  assert.equal(module.bandLabel("review"), "Review");
});

test("the band is never the colour alone: the card carries it as an attribute too", async () => {
  const harness = loadView({
    ids: [PASSPORT_ID, VISA_ID],
    answers: [passportAnswer({ band: "low" }), visaAnswer({ band: "high" })],
  });
  await harness.view.load();
  const [passport, visa] = drawnCards(harness.grid);
  assert.equal(passport.band, "low");
  assert.equal(visa.band, "high");
});

test("the score is drawn as the service sent it, at the one decimal format.js prints", async () => {
  const harness = loadView({
    ids: [PASSPORT_ID],
    answers: [passportAnswer({ score: 12.5 })],
  });
  await harness.view.load();
  assert.equal(drawnCards(harness.grid)[0].score, "Score: 12.5");
});

test("a document nothing scored gets the neutral tag, the unscored word, and no score", async () => {
  const harness = loadView({
    ids: [UNKNOWN_ID],
    answers: [
      passportAnswer({ screening_id: UNKNOWN_ID, band: null, score: null }),
    ],
  });
  await harness.view.load();
  const [card] = drawnCards(harness.grid);
  assert.deepEqual(card.bandTagClasses, [
    "ux4g-tag",
    "ux4g-tag-s",
    "ux4g-tag-filled-neutral",
  ]);
  assert.equal(card.bandWord, "Not scored");
  assert.equal(card.score, null);
  assert.equal(card.band, "");
});

test("a band the engine never bands in is refused by name", () => {
  const { module } = loadView();
  assert.throws(
    () => module.bandVariant("pass"),
    (error) =>
      error.name === "CaseViewError" &&
      error.code === "bad_band" &&
      /low, review, high/.test(error.message),
  );
  assert.throws(() => module.bandLabel("toString"), /low, review, high/);
});

test("a score outside the scale, or one that is not a number, is refused by name", () => {
  const { module } = loadView();
  for (const bad of ["72", null, undefined, -1, 101, Number.NaN]) {
    if (bad === null) {
      assert.equal(module.readScore(null), null);
      continue;
    }
    assert.throws(
      () => module.readScore(bad),
      (error) =>
        error.name === "CaseViewError" &&
        error.code === "bad_score" &&
        /between 0 and 100/.test(error.message),
      "a score of " + String(bad) + " is refused",
    );
  }
});

/* ---------- the cross-document flags ---------- */

test("the cross-document flags are drawn with the label and the reason the engine wrote", async () => {
  const harness = loadView({
    ids: [VISA_ID],
    answers: [visaAnswer()],
  });
  await harness.view.load();
  const [card] = drawnCards(harness.grid);
  assert.equal(card.crossdocHeading, "Cross-document flags");
  assert.deepEqual(card.crossdocFlags, [
    { label: NAME_MISMATCH_LABEL, reason: NAME_MISMATCH_REASON },
  ]);
  assert.ok(card.crossdocText.includes(NAME_MISMATCH_LABEL));
  assert.ok(card.crossdocText.includes(NAME_MISMATCH_REASON));
});

test("every cross-document flag on a document is drawn, not only the first", async () => {
  const harness = loadView({
    ids: [VISA_ID],
    answers: [
      visaAnswer({
        flags: [
          crossdocFlag(),
          crossdocFlag({
            id: "CROSSDOC_UNKNOWN_PASSPORT_REFERENCE",
            label: PASSPORT_REFERENCE_LABEL,
            reason: PASSPORT_REFERENCE_REASON,
          }),
        ],
      }),
    ],
  });
  await harness.view.load();
  assert.deepEqual(drawnCards(harness.grid)[0].crossdocFlags, [
    { label: NAME_MISMATCH_LABEL, reason: NAME_MISMATCH_REASON },
    { label: PASSPORT_REFERENCE_LABEL, reason: PASSPORT_REFERENCE_REASON },
  ]);
});

test("a flag of a tier scoped to one document never reaches a case card", async () => {
  const harness = loadView({
    ids: [PASSPORT_ID],
    answers: [
      passportAnswer({
        flags: [
          {
            id: "MRZ_CHECK_DIGIT_MISMATCH",
            tier: 0,
            label: TIER0_LABEL,
            reason: "The check digit does not match the field it covers.",
          },
          crossdocFlag(),
        ],
      }),
    ],
  });
  await harness.view.load();
  const [card] = drawnCards(harness.grid);
  assert.deepEqual(card.crossdocFlags, [
    { label: NAME_MISMATCH_LABEL, reason: NAME_MISMATCH_REASON },
  ]);
  assert.ok(
    !card.crossdocText.includes(TIER0_LABEL),
    "a single-document finding belongs on the result page",
  );
});

test("the tier this view filters on is the one app/risk/flag_ids.py spells", () => {
  const { module } = loadView();
  assert.equal(module.CROSSDOC_TIER, "crossdoc");
  assert.match(
    flagsSource,
    /["']crossdoc["']/,
    "app/risk/flags.py still spells the cross-document tier crossdoc",
  );
  assert.ok(
    flagIdsSource.includes("CROSSDOC_NAME_MISMATCH"),
    "the cross-document rules are named as CROSSDOC_* in the service",
  );
});

test("a document whose rules raised no cross-document flag says so rather than standing empty", async () => {
  const harness = loadView({
    ids: [PASSPORT_ID, VISA_ID],
    answers: [passportAnswer(), visaAnswer({ flags: [] })],
  });
  await harness.view.load();
  const [passport, visa] = drawnCards(harness.grid);
  assert.deepEqual(passport.crossdocFlags, []);
  assert.equal(passport.crossdocText, "No cross-document flag was raised.");
  assert.equal(passport.crossdocHeading, "Cross-document flags");
  assert.equal(
    visa.crossdocText,
    "No cross-document flag was raised.",
    "the second document is compared and raised nothing either",
  );
});

test("a cross-document flag missing its label or its reason is refused by name", () => {
  const { module } = loadView();
  for (const bad of [
    crossdocFlag({ label: "" }),
    crossdocFlag({ label: "   " }),
    crossdocFlag({ reason: undefined }),
    crossdocFlag({ label: 7 }),
    crossdocFlag({ reason: null }),
    null,
    ["not", "a", "flag"],
  ]) {
    assert.throws(
      () => module.readCrossdocFlags([bad]),
      (error) =>
        error.name === "CaseViewError" &&
        error.code === "bad_flags" &&
        /label and a reason/.test(error.message),
      "a flag with no label or reason is refused",
    );
  }
  assert.throws(
    () => module.readCrossdocFlags("crossdoc"),
    (error) => error.code === "bad_flags",
  );
});

test("a flag of another tier needs no label or reason to be passed over", () => {
  const { module } = loadView();
  assert.deepEqual(
    host(module.readCrossdocFlags([{ tier: "quality", id: "BLUR_UNDERPASSED" }])),
    [],
  );
});

/* ---------- refusals ---------- */

test("an answer that cannot be read is refused whole, leaving the documents as they stood", async () => {
  const harness = loadView({
    ids: [PASSPORT_ID, VISA_ID],
    answers: [passportAnswer(), visaAnswer()],
  });
  await harness.view.load();
  assert.equal(drawnCards(harness.grid).length, 2);

  harness.requests.length = 0;
  assert.throws(
    () =>
      harness.view.render([passportAnswer(), visaAnswer({ band: "critical" })]),
    (error) => error.code === "bad_band",
    "a band the engine never bands in must not be drawn",
  );
  assert.equal(
    drawnCards(harness.grid).length,
    2,
    "the two readable documents are still standing",
  );
  assert.deepEqual(
    drawnCards(harness.grid).map((card) => card.documentType),
    ["passport", "visa"],
  );
});

test("a screening answer missing what the card needs is refused by name", () => {
  const { module } = loadView();
  for (const bad of [
    null,
    "passport",
    [],
    { document_type: "passport", band: "low" },
    { screening_id: "", document_type: "passport", band: "low" },
    { screening_id: PASSPORT_ID, band: "low" },
    { screening_id: PASSPORT_ID, document_type: "  ", band: "low" },
  ]) {
    assert.throws(
      () => module.readDocument(bad),
      (error) =>
        error.name === "CaseViewError" &&
        error.code === "bad_document" &&
        /screening_id, a document_type and a band/.test(error.message),
      "an answer without a screening_id, a document_type and a band is refused",
    );
  }
});

test("the view needs an element to draw into, and a list of ids even when empty", () => {
  const { module } = loadView();
  assert.throws(
    () => module.bindCaseView({ ids: [] }),
    (error) =>
      error.code === "missing_element" &&
      /draw the documents into: grid/.test(error.message),
  );
  assert.throws(
    () => module.bindCaseView({ grid: createElement("div") }),
    (error) =>
      error.code === "missing_ids" &&
      /list of screening ids/.test(error.message),
  );
});

/* ---------- the states ---------- */

test("the five states are one switch, and any other state is refused by name", () => {
  const harness = loadView();
  const { module, view, regions, grid } = harness;
  assert.deepEqual(host(module.STATES), [
    "documents",
    "loading",
    "empty",
    "error",
    "single",
  ]);

  view.showState("loading");
  assert.equal(regions.loading.hidden, false);
  assert.equal(regions.loading.getAttribute("aria-busy"), "true");
  assert.equal(regions.failure.hidden, true);
  assert.equal(regions.empty.hidden, true);
  assert.equal(grid.hidden, true);

  view.showState("documents");
  assert.equal(regions.loading.hidden, true);
  assert.equal(regions.loading.getAttribute("aria-busy"), "false");
  assert.equal(grid.hidden, false);

  view.showState("empty");
  assert.equal(regions.empty.hidden, false);
  assert.equal(regions.single.hidden, true);
  assert.equal(grid.hidden, true);

  view.showState("single");
  assert.equal(regions.single.hidden, false);
  assert.equal(regions.empty.hidden, true);
  assert.equal(grid.hidden, false, "the one document is still drawn");

  view.showState("error");
  assert.equal(regions.failure.hidden, false);
  assert.equal(regions.single.hidden, true);
  assert.equal(regions.failure.hidden, false);

  assert.throws(
    () => view.showState("pending"),
    (error) =>
      error.code === "bad_state" &&
      /documents, loading, empty, error/.test(error.message),
  );
});

test("a page opened with no document named is an answer, not a failure", async () => {
  const harness = loadView({ ids: [] });
  await harness.view.load();
  assert.deepEqual(harness.requests, [], "nothing is asked for");
  assert.equal(harness.view.state(), "empty");
  assert.equal(harness.regions.empty.hidden, false);
  assert.equal(harness.regions.single.hidden, true, "not the one-document answer");
  assert.equal(harness.regions.failure.hidden, true);
  assert.equal(harness.grid.children.length, 0);
});

test("a case of one document degrades to a clear empty state, and keeps the document's own facts", async () => {
  const harness = loadView({
    ids: [PASSPORT_ID],
    answers: [passportAnswer()],
  });
  await harness.view.load();
  assert.equal(harness.view.state(), "single");
  assert.equal(harness.regions.single.hidden, false, "its own panel is shown");
  assert.equal(harness.regions.empty.hidden, true, "not the no-document panel");
  assert.equal(harness.regions.failure.hidden, true, "and not a failure");
  assert.equal(
    harness.grid.hidden,
    false,
    "the document the service answered with is still drawn",
  );
  assert.equal(harness.regions.count.textContent, "1 document");

  const [card] = drawnCards(harness.grid);
  assert.equal(card.documentType, "passport");
  assert.equal(card.screeningId, PASSPORT_ID);
  assert.equal(card.idText, "Screening id: " + PASSPORT_ID);
  assert.equal(card.bandWord, "Low Risk");
  assert.equal(card.score, "Score: 12.5");
  assert.equal(
    card.crossdocHeading,
    null,
    "no cross-document section: nothing here could have been compared",
  );
  assert.equal(card.crossdocText, null);
  assert.deepEqual(card.crossdocFlags, []);
});

test("the one-document state is its own answer, said in the page's own words", () => {
  const { module } = loadView();
  assert.equal(module.STATE_SINGLE, "single");
  assert.equal(module.stateFor(0), "empty");
  assert.equal(module.stateFor(1), "single");
  assert.equal(module.stateFor(2), "documents");
  assert.equal(module.stateFor(7), "documents");

  assert.ok(
    pageHtml.includes('id="case-single" hidden'),
    "the panel ships hidden, so it cannot flash before the module answers",
  );
  const panel = pageHtml.slice(pageHtml.indexOf('id="case-single"'));
  assert.ok(
    panel.includes("One document in this case"),
    "the panel names the answer it gives",
  );
  assert.ok(
    panel.includes("nothing beside it"),
    "and says there is nothing to compare against",
  );
  assert.ok(
    !panel.includes("No document was named"),
    "which is not what #case-empty says, and the two are kept apart",
  );
  assert.ok(
    panel.includes("ux4g-empty-state"),
    "the empty state's own composition, as #case-empty ships it",
  );
});

test("two or more documents are compared, and the one-document panel stays away", async () => {
  const harness = loadView({ ids: [PASSPORT_ID, VISA_ID] });
  await harness.view.load();
  assert.equal(harness.view.state(), "documents");
  assert.equal(harness.regions.single.hidden, true);
  for (const card of drawnCards(harness.grid)) {
    assert.equal(card.crossdocHeading, "Cross-document flags");
  }
});

test("a cross-document flag on a lone document is the service's, and is still drawn", async () => {
  const harness = loadView({
    ids: [VISA_ID],
    answers: [visaAnswer()],
  });
  await harness.view.load();
  const [card] = drawnCards(harness.grid);
  assert.equal(harness.view.state(), "single");
  assert.deepEqual(card.crossdocFlags, [
    { label: NAME_MISMATCH_LABEL, reason: NAME_MISMATCH_REASON },
  ]);
});

test("a failed read is shown in the alert in the failure's own words, and the count is cleared", async () => {
  const failure = new Error("That screening could not be found.");
  const harness = loadView({ ids: [PASSPORT_ID], failWith: failure });
  await harness.view.load();
  assert.equal(harness.view.state(), "error");
  assert.equal(harness.regions.failure.hidden, false);
  assert.equal(
    harness.regions.failureMessage.textContent,
    "That screening could not be found.",
  );
  assert.equal(harness.view.error(), failure);
  assert.equal(harness.regions.count.textContent, "");

  harness.requests.length = 0;
  const answers = [passportAnswer(), visaAnswer()];
  harness.view.clear();
  await harness.view.render(answers);
  assert.equal(harness.view.state(), "documents");
});

test("the retry button re-reads the documents the page was opened with", async () => {
  const harness = loadView({ ids: [PASSPORT_ID, VISA_ID] });
  await harness.view.load();
  harness.requests.length = 0;
  harness.regions.retry.click();
  await new Promise((resolve) => setImmediate(resolve));
  assert.deepEqual(harness.requests, [
    "/api/screenings/" + PASSPORT_ID,
    "/api/screenings/" + VISA_ID,
  ]);
});

test("the count says how many documents the case holds", async () => {
  const one = loadView({ ids: [PASSPORT_ID], answers: [passportAnswer()] });
  await one.view.load();
  assert.equal(one.regions.count.textContent, "1 document");
  assert.equal(one.module.documentCountText(1), "1 document");
  assert.equal(one.module.documentCountText(3), "3 documents");

  const none = loadView({ ids: [] });
  await none.view.load();
  assert.equal(none.regions.count.textContent, "");
});

test("a page that cannot reach the API client says so rather than drawing nothing quietly", async () => {
  const source2 = source;
  const sandbox = {
    URLSearchParams: URLSearchParams,
    window: {},
    document: {
      readyState: "complete",
      getElementById: () => null,
      createElement: createElement,
      createTextNode: createTextNode,
    },
  };
  vm.runInNewContext(source2, sandbox);
  const view = sandbox.window.DRISHTI_CASES.bindCaseView({
    grid: createElement("div"),
    ids: [PASSPORT_ID],
  });
  await assert.rejects(
    () => view.load(),
    (error) =>
      error.name === "CaseViewError" &&
      error.code === "no_api" &&
      /cannot reach the API client/.test(error.message),
  );
});