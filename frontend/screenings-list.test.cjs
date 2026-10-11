const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const { buildFileNames } = require("./build.cjs");

const source = fs.readFileSync(path.join(__dirname, "screenings-list.js"), "utf8");
const formatSource = fs.readFileSync(path.join(__dirname, "format.js"), "utf8");
const pageHtml = fs.readFileSync(
  path.join(__dirname, "screenings.html"),
  "utf8",
);
const sheet = fs.readFileSync(
  path.join(__dirname, "node_modules", "ux4g-web-components", "styles", "ux4g.css"),
  "utf8",
);
const pagesSource = fs.readFileSync(path.join(__dirname, "pages.js"), "utf8");
const pagesCss = fs.readFileSync(path.join(__dirname, "pages.css"), "utf8");
const homeCss = fs.readFileSync(path.join(__dirname, "home.css"), "utf8");


// The UX4G table composition and the column set that 24.2 freezes. Both are
// written once here and read back out of the page, so a later task that
// rewrites either has to change this file rather than quietly change the look.
const TABLE_UX4G_CLASSES = [
  "ux4g-table",
  "ux4g-table-m",
  "ux4g-table-zebra-rows",
  "ux4g-table-interactive",
];

const COLUMN_NAMES = [
  "Screening",
  "Document",
  "Checked",
  "Mode",
  "Score",
  "Result",
  "Actions",
];

// The class attribute of the page's one table, split the way a browser splits
// it: on whitespace, every class kept in the order the page wrote it.
function tableClasses() {
  const start = pageHtml.indexOf("<table");
  assert.ok(start >= 0, "the history page still has a table");
  const tag = pageHtml.slice(start, pageHtml.indexOf(">", start) + 1);
  const quoted = /class="([^"]*)"/.exec(tag);
  assert.ok(quoted, "the history table still carries a class attribute");
  return quoted[1].split(/\s+/).filter(Boolean);
}

// The header cells as the names a screen reader reads: the tags stripped and
// the whitespace collapsed, so a visually hidden name still counts as one.
function headerColumns() {
  const open = pageHtml.indexOf("<thead>");
  const close = pageHtml.indexOf("</thead>");
  assert.ok(open >= 0 && close > open, "the history table still has a header");
  const head = pageHtml.slice(open + "<thead>".length, close);
  return [...head.matchAll(/<th\b([^>]*)>([\s\S]*?)<\/th>/g)].map(
    ([, attributes, inner]) => ({
      scope: (/scope="([^"]*)"/.exec(attributes) ?? [])[1] ?? null,
      name: inner.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim(),
    }),
  );
}

// The smallest tbody the rows can be built in: children, the classes and the
// attributes they write, and nothing else, so a property nobody implemented
// here would throw rather than pass quietly.
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
    },
    focused: false,
    get firstChild() {
      return this.children.length === 0 ? null : this.children[0];
    },
    get dataset() {
      const data = {};
      for (const [name, value] of attributes) {
        if (name.startsWith("data-")) {
          const key = name
            .slice("data-".length)
            .replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
          data[key] = value;
        }
      }
      return data;
    },
    closest: function (selector) {
      const wanted = selector.replace(/^\[|\]$/g, "");
      for (let node = this; node !== null; node = node.parentElement) {
        if (node.attributes.has(wanted)) {
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
    // A click bubbles, which is what lets one handler on the tbody answer
    // every row beneath it.
    click: function () {
      for (let node = this; node !== null; node = node.parentElement) {
        for (const handler of node.listeners.get("click") ?? []) {
          handler({ type: "click", target: this });
        }
      }
    },
    focus: function () {
      this.focused = true;
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
        throw new Error("the history table removed a row it never drew");
      }
      this.children.splice(at, 1);
      return child;
    },
  };
}

function textOf(node) {
  return node.textContent;
}

// The module, the formatter and the API client in one sandbox: the rows are
// drawn from the formatter's answers and read over the API client's request,
// so a send is visible to fail on rather than silently absent.
const DEFAULT_PAGE = {
  items: [
    {
      screening_id: "9f1c0a6e-0000-4000-8000-000000000001",
      status: "completed",
      document_type: "passport",
      created_at: "2026-09-30T09:12:00",
      score: 92,
      band: "low",
    },
  ],
  total: 1,
  offset: 0,
  limit: 20,
};

function loadList(options = {}) {
  const { withFormat = true, withApi = true, withDownload = true, respond } =
    options;
  const body = createElement("tbody");
  const count = createElement("p");
  const empty = createElement("div");
  empty.hidden = true;
  // 24.7: the three states the page is not in. The starting `hidden` flags
  // are the markup's own -- the skeleton is what the page first paints.
  const loading = createElement("div");
  loading.hidden = false;
  const failure = createElement("div");
  failure.hidden = true;
  const failureMessage = createElement("p");
  const retry = createElement("button");  const scroll = createElement("div");
  const total = createElement("strong");
  const notice = createElement("p");
  const confirm = createElement("div");
  const confirmId = createElement("strong");
  const confirmOk = createElement("button");
  const confirmCancel = createElement("button");
  const exportButton = createElement("button");
  const downloaded = [];
  const sent = { paths: [], calls: [], fails: null, deleteError: null };
  const dispatched = [];
  const sandbox = {
    window: {},
    document: {
      createElement: function (tagName) {
        return createElement(tagName);
      },
      getElementById: function () {
        return null;
      },
      querySelector: function () {
        return null;
      },
      readyState: "loading",
      addEventListener: function () {},
      dispatchEvent: function (event) {
        dispatched.push(event.type);
      },
    },
    Intl: Intl,
    Event: Event,
    Date: Date,
    JSON: JSON,
    Array: Array,
    Object: Object,
    Error: Error,
    Number: Number,
    String: String,
    Promise: Promise,
  };
  if (withFormat) {
    vm.runInNewContext(formatSource, sandbox);
  }
  if (withApi) {
    sandbox.window.DRISHTI_API = {
      request: function (requestPath, requestOptions) {
        const method = (requestOptions ?? {}).method ?? "GET";
        sent.paths.push(requestPath);
        sent.calls.push({ path: requestPath, method: method });
        if (method === "DELETE" && sent.deleteError) {
          return Promise.reject(sent.deleteError);
        }
        if (sent.fails) {
          return Promise.reject(sent.fails);
        }
        return Promise.resolve({
          json: function () {
            return Promise.resolve(
              typeof respond === "function" ? respond() : DEFAULT_PAGE,
            );
          },
        });
      },
    };
  }
  if (withDownload) {
    sandbox.window.DRISHTI_DOWNLOAD = function (fileName, contents, type) {
      downloaded.push({ fileName: fileName, contents: contents, type: type });
    };
  }
  vm.runInNewContext(source, sandbox);
  return {
    list: sandbox.window.DRISHTI_SCREENINGS_LIST,
    format: sandbox.window.DRISHTI_FORMAT,
    body: body,
    count: count,
    empty: empty,
    loading: loading,
    failure: failure,
    failureMessage: failureMessage,
    retry: retry,    scroll: scroll,
    total: total,
    notice: notice,
    confirm: confirm,
    confirmId: confirmId,
    confirmOk: confirmOk,
    confirmCancel: confirmCancel,
    exportButton: exportButton,
    downloaded: downloaded,
    sent: sent,
    dispatched: dispatched,
  };
}

function bind(context, options = {}) {
  return context.list.bindScreeningsList({
    body: context.body,
    count: context.count,
    empty: context.empty,
    loading: context.loading,
    failure: context.failure,
    failureMessage: context.failureMessage,
    retry: context.retry,
    scroll: context.scroll,    total: context.total,
    notice: context.notice,
    confirm: context.confirm,
    confirmId: context.confirmId,
    confirmOk: context.confirmOk,
    confirmCancel: context.confirmCancel,
    export: context.exportButton,
    ...options,
  });
}

// The two controls the seventh column draws, in the order the cell holds them.
function rowActions(context, index = 0) {
  return rowsOf(context)[index].children[6].children[0].children;
}

function deleteButtonOf(context, index = 0) {
  return rowActions(context, index)[1];
}

function item(overrides = {}) {
  return {
    screening_id: "9f1c0a6e-0000-4000-8000-000000000001",
    status: "completed",
    document_type: "passport",
    created_at: "2026-09-30T09:12:00",
    score: 92,
    band: "low",
    ...overrides,
  };
}

function payload(items = [item()], total = items.length) {
  return { items: items, total: total, offset: 0, limit: 20 };
}

function rowsOf(context) {
  return context.body.children;
}

function refuses(call, code) {
  assert.throws(call, (error) => {
    assert.equal(error.name, "ScreeningsListError");
    assert.equal(error.code, code);
    return true;
  });
}

// The chip vocabulary 24.4 freezes: All plus the three bands
// app/risk/bands.py bands in. Read back out of the page, so the sample
// vocabulary cannot return without a case going red.
const CHIP_FILTERS = ["all", "low", "review", "high"];

// The class attribute of a tag, split the way a browser splits it.
function chipClasses(tag) {
  const quoted = /class="([^"]*)"/.exec(tag);
  assert.ok(quoted, "the chip markup still carries a class attribute");
  return quoted[1].split(/\s+/).filter(Boolean);
}

// The band filter group as the page wrote it: the container role, label
// and classes, and each chip value, classes, pressed state and label.
function filterChips() {
  const open = pageHtml.indexOf('id="result-filters"');
  assert.ok(open >= 0, "the history page still has a band filter");
  const start = pageHtml.lastIndexOf("<div", open);
  const group = pageHtml.slice(start, pageHtml.indexOf("</div>", open));
  const opening = pageHtml.slice(start, pageHtml.indexOf(">", start));
  return {
    role: (/role="([^"]*)"/.exec(opening) ?? [])[1] ?? null,
    label: (/aria-label="([^"]*)"/.exec(opening) ?? [])[1] ?? null,
    classes: chipClasses(opening),
    chips: [...group.matchAll(/<button\b([^>]*)>([\s\S]*?)<\/button>/g)].map(
      ([, attributes, inner]) => ({
        filter: (/data-filter="([^"]*)"/.exec(attributes) ?? [])[1] ?? null,
        type: (/type="([^"]*)"/.exec(attributes) ?? [])[1] ?? null,
        pressed: (/aria-pressed="([^"]*)"/.exec(attributes) ?? [])[1] ?? null,
        classes: chipClasses(attributes),
        label: inner.replace(/\s+/g, " ").trim(),
      }),
    ),
  };
}

// The confirmation the Delete action goes through, as the page wrote it: the
// dialog role, the two ids that name it, and each button in the action bar.
function deleteDialog() {
  const open = pageHtml.indexOf("id=" + String.fromCharCode(34) + "delete-confirm" + String.fromCharCode(34));
  assert.ok(open >= 0, "the history page still has a delete confirmation");
  const start = pageHtml.lastIndexOf("<div", open);
  const opening = pageHtml.slice(start, pageHtml.indexOf(">", start));
  const inner = pageHtml.slice(start, pageHtml.indexOf("{{/overlays}}"));
  return {
    role: (/role="([^"]*)"/.exec(opening) ?? [])[1] ?? null,
    modal: (/aria-modal="([^"]*)"/.exec(opening) ?? [])[1] ?? null,
    labelledBy: (/aria-labelledby="([^"]*)"/.exec(opening) ?? [])[1] ?? null,
    describedBy: (/aria-describedby="([^"]*)"/.exec(opening) ?? [])[1] ?? null,
    classes: chipClasses(opening),
    ids: [...inner.matchAll(/id="([^"]*)"/g)].map(([, id]) => id),
    buttons: [...inner.matchAll(/<button\b([^>]*)>([\s\S]*?)<\/button>/g)].map(
      ([, attributes, label]) => ({
        id: (/id="([^"]*)"/.exec(attributes) ?? [])[1] ?? null,
        type: (/type="([^"]*)"/.exec(attributes) ?? [])[1] ?? null,
        classes: chipClasses(attributes),
        label: label.replace(/\s+/g, " ").trim(),
      }),
    ),
  };
}

test("one row per stored screening, drawn from what the route answered", () => {
  const context = loadList();
  bind(context).render(payload());

  assert.equal(rowsOf(context).length, 1);
  const [row] = rowsOf(context);
  assert.equal(row.children.length, 7, "the seven columns the table declares");
  assert.equal(
    textOf(row.children[0]),
    "9f1c0a6e-0000-4000-8000-000000000001completed",
  );
  assert.equal(textOf(row.children[1]), "passport");
  assert.equal(
    row.children[2].children[0].getAttribute("datetime"),
    "2026-09-30T09:12:00.000Z",
  );
});

test("the count and the total tile read off the answer, not off the markup", () => {
  const context = loadList();
  const page = bind(context).render(
    payload([item(), item({ screening_id: "b" })], 41),
  );

  assert.equal(textOf(context.count), "Showing 2 of 41 screenings");
  assert.equal(textOf(context.total), "41");
  assert.equal(page.total, 41);
  assert.equal(page.rows.length, 2);
});

test("each band draws its own tag, and an unscored row is not given one", () => {
  const cases = [
    { band: "low", variant: "ux4g-tag-filled-success", label: "Low Risk" },
    { band: "review", variant: "ux4g-tag-filled-warning", label: "Review" },
    { band: "high", variant: "ux4g-tag-filled-error", label: "High Risk" },
    { band: null, variant: "ux4g-tag-filled-neutral", label: "Not scored" },
  ];
  for (const expected of cases) {
    const context = loadList();
    bind(context).render(payload([item({ band: expected.band })]));
    const [row] = rowsOf(context);
    const tag = row.children[5].children[0];

    assert.ok(tag.classes.has("ux4g-tag"), String(expected.band));
    assert.ok(tag.classes.has("ux4g-tag-s"), String(expected.band));
    assert.ok(tag.classes.has(expected.variant), String(expected.band));
    assert.equal(textOf(tag), expected.label);
  }
});

test("a mode the route does not carry is named absent, never invented", () => {
  const context = loadList();
  bind(context).render(payload());

  assert.equal(textOf(rowsOf(context)[0].children[3]), "Not recorded");
});

test("an empty page shows the empty state and hides the table", () => {
  const context = loadList();
  bind(context).render(payload([], 0));

  assert.equal(rowsOf(context).length, 0);
  assert.equal(context.empty.hidden, false);
  assert.equal(context.scroll.hidden, true);
  assert.equal(textOf(context.count), "Showing 0 of 0 screenings");
});

test("the history is read over the API client, at the list route", async () => {
  const context = loadList();
  const page = await bind(context).load();

  assert.deepEqual(context.sent.paths, ["/api/screenings"]);
  assert.equal(page.rows.length, 1);
});

test("a page this module cannot read leaves the table as it stood", () => {
  const context = loadList();
  const controller = bind(context);
  controller.render(payload());

  refuses(() => controller.render(payload([item({ band: "medium" })])), "bad_band");
  refuses(() => controller.render(payload([item({ score: 140 })])), "bad_score");
  refuses(
    () => controller.render(payload([item({ created_at: "not-a-date" })])),
    "bad_timestamp",
  );
  refuses(() => controller.render(payload([item({ status: "archived" })])), "bad_item");
  refuses(() => controller.render({ total: 1 }), "bad_payload");

  assert.equal(rowsOf(context).length, 1, "the drawn row is left standing");
});

test("the binding refuses what it cannot draw into", () => {
  const context = loadList();
  refuses(() => context.list.bindScreeningsList({}), "missing_element");
  refuses(
    () =>
      loadList({ withFormat: false }).list.bindScreeningsList({
        body: createElement("tbody"),
      }),
    "no_format",
  );
  assert.deepEqual([...context.list.REQUIRED_ELEMENTS], ["body"]);
});

test("a history the service will not answer is stored, not thrown at the page", async () => {
  const context = loadList();
  context.sent.fails = new Error("the service is down");
  const controller = bind(context);

  const page = await controller.load();

  assert.equal(page, null);
  assert.equal(controller.error().message, "the service is down");
});

test("every class the module writes is one the project already ships", () => {
  const written = [
    "ux4g-table-cell-text",
    "ux4g-tag",
    "ux4g-tag-s",
    "ux4g-tag-filled-success",
    "ux4g-tag-filled-warning",
    "ux4g-tag-filled-error",
    "ux4g-tag-filled-neutral",
    "ux4g-btn",
    "ux4g-btn-text-primary",
    "ux4g-btn-sm",
  ];
  for (const name of [
    "ux4g-modal-backdrop",
    "ux4g-modal-backdrop-50",
    "ux4g-modal-backdrop-blur",
    "ux4g-modal-box",
    "ux4g-modal-s",
    "ux4g-modal-header",
    "ux4g-modal-header-title",
    "ux4g-modal-body",
    "ux4g-modal-actions",
    "ux4g-btn-outline-neutral",
    "ux4g-btn-danger",
    "ux4g-btn-md",
  ]) {
    assert.match(
      sheet,
      new RegExp("\\." + name + "(?![a-z0-9-])"),
      name + " is not in the installed stylesheet",
    );
  }
  assert.match(
    sheet,
    /\.is-open(?![\w-])/,
    "the installed stylesheet ships no is-open to show a backdrop",
  );
  assert.doesNotMatch(
    sheet,
    /\.ux4g-modal-footer(?![\w-])/,
    "2.1.0 documents a modal footer it does not ship",
  );
  for (const name of written) {
    assert.match(
      sheet,
      new RegExp("\\." + name + "(?![a-z0-9-])"),
      `${name} is not in the installed stylesheet`,
    );
  }
  // The three classes of the project's own, each already carried by the
  // markup this module draws into.
  for (const name of ["cell-primary", "cell-actions", "visually-hidden"]) {
    assert.match(
      pagesCss + homeCss,
      new RegExp("\\." + name + "(?![a-z0-9-])"),
      `${name} is not in the project's own CSS`,
    );
  }
});

test("the page ships no sample row and reads its rows from the route", () => {
  assert.equal(
    (pageHtml.match(/<tr data-result="/g) ?? []).length,
    0,
    "no sample row remains in the markup",
  );
  assert.doesNotMatch(pageHtml, /SCR-20\d\d/, "no sample id remains");
  assert.doesNotMatch(pageHtml, /Sample data/, "no sample-data notice remains");
  assert.match(pageHtml, /<tbody id="screenings-body"><\/tbody>/);
  assert.match(pageHtml, /<script src="\.\/screenings-list\.js"><\/script>/);
});

test("the page loads the module and the build copies it", () => {
  const { staticFiles } = buildFileNames();
  for (const name of ["format.js", "screenings-list.js"]) {
    assert.ok(staticFiles.includes(name), `the build copies ${name}`);
    assert.ok(
      pageHtml.includes(`<script src="./${name}"></script>`),
      `the page loads ${name}`,
    );
  }
});
test("the history table keeps its four UX4G classes, in order, and gains none", () => {
  const classes = tableClasses();

  assert.deepEqual(
    classes.filter((name) => name.startsWith("ux4g-table")),
    TABLE_UX4G_CLASSES,
    "the UX4G table composition is unchanged",
  );
  assert.deepEqual(
    classes.filter((name) => !name.startsWith("ux4g-table")),
    ["screenings-table"],
    "only the project's own class sits alongside them",
  );
  for (const name of TABLE_UX4G_CLASSES) {
    assert.match(
      sheet,
      new RegExp("\\." + name + "(?![a-z0-9-])"),
      name + " is not in the installed stylesheet",
    );
  }
  assert.match(
    pagesCss,
    /\.screenings-table(?![\w-])/,
    "the project's own table class is not in the project's own CSS",
  );
});

test("the header still declares seven columns, and a drawn row is that wide", () => {
  const columns = headerColumns();

  assert.equal(columns.length, 7);
  assert.deepEqual(
    columns.map((column) => column.name),
    COLUMN_NAMES,
    "the column set and its order are unchanged",
  );
  assert.deepEqual(
    [...new Set(columns.map((column) => column.scope))],
    ["col"],
    "every column is a header for its own column",
  );

  const context = loadList();
  bind(context).render(payload());
  assert.equal(
    rowsOf(context)[0].children.length,
    columns.length,
    "the module draws a cell for each declared column, no more and no fewer",
  );
});

test("the band filter chips are All plus the three bands the engine bands in", () => {
  const chips = filterChips();
  const context = loadList();

  assert.deepEqual(chips.chips.map((chip) => chip.filter), CHIP_FILTERS);
  assert.equal(context.list.ALL_FILTER, CHIP_FILTERS[0]);
  assert.deepEqual(context.list.BAND_FILTERS, CHIP_FILTERS.slice(1));
  assert.deepEqual(
    Object.keys(context.format.BAND_LABELS),
    CHIP_FILTERS.slice(1),
    "the chips and the formatter name the bands differently",
  );
  assert.doesNotMatch(
    pageHtml,
    /data-filter="(pass|attention)"/,
    "the sample chip vocabulary is back",
  );
});

test("a band chip is labelled the way the formatter labels that band", () => {
  const context = loadList();

  for (const chip of filterChips().chips) {
    const expected =
      chip.filter === context.list.ALL_FILTER
        ? "All"
        : context.format.bandLabel(chip.filter);
    assert.equal(
      chip.label,
      expected,
      chip.filter + " is labelled by something else",
    );
  }
});

test("the chips carry the composition 2.1.0 ships, and one chip is pressed", () => {
  const group = filterChips();

  assert.equal(group.role, "group");
  assert.equal(group.label, "Filter by band");
  assert.deepEqual(group.classes, ["ux4g-filter-chip-group"]);
  for (const chip of group.chips) {
    assert.equal(chip.type, "button", chip.filter + " is not a button");
    assert.ok(
      chip.classes.includes("ux4g-filter-chip-md"),
      chip.filter + " is not an md filter chip",
    );
  }
  const pressed = group.chips.filter((chip) => chip.pressed === "true");
  assert.deepEqual(
    pressed.map((chip) => chip.filter),
    ["all"],
    "more than one chip claims to be pressed",
  );
  assert.deepEqual(pressed[0].classes, ["ux4g-filter-chip-md", "active"]);
  for (const name of ["ux4g-filter-chip-group", "ux4g-filter-chip-md"]) {
    assert.match(
      sheet,
      new RegExp("\\." + name + "(?![a-z0-9-])"),
      name + " is not in the installed stylesheet",
    );
  }
  assert.doesNotMatch(
    sheet,
    /\.ux4g-filter-chip(?![a-z0-9-])/,
    "2.1.0 ships no base filter-chip class to compose with",
  );
});

test("a drawn row answers the chip for the band the engine gave it", () => {
  const context = loadList();
  bind(context).render(
    payload([
      item({ band: "low" }),
      item({ screening_id: "b", band: "review" }),
      item({ screening_id: "c", band: "high" }),
      item({ screening_id: "d", band: null }),
    ]),
  );
  const chips = filterChips().chips.map((chip) => chip.filter);

  assert.deepEqual(
    rowsOf(context).map((row) => row.getAttribute("data-result")),
    ["low", "review", "high", context.list.UNSCORED_FILTER],
    "a row is not filed under the band the engine banded it in",
  );
  for (const band of context.list.BAND_FILTERS) {
    assert.ok(chips.includes(band), "no chip filters on " + band);
  }
  assert.equal(
    chips.includes(context.list.UNSCORED_FILTER),
    false,
    "a row nothing scored is filed under a band chip",
  );
});

const ROW_ID = "9f1c0a6e-0000-4000-8000-000000000001";

test("View is a link to the result view carrying that row own id", () => {
  const context = loadList();
  bind(context).render(payload([item({ screening_id: "9f1c 0a6e/?&=" })]));

  const [view] = rowActions(context);

  assert.equal(view.tagName, "A", "View navigates, so it is a link");
  assert.equal(view.getAttribute("data-row-action"), "view");
  assert.equal(
    view.getAttribute("href"),
    "result.html?id=" + encodeURIComponent("9f1c 0a6e/?&="),
    "the id is pasted into the query string unencoded",
  );
  assert.equal(view.getAttribute("aria-label"), "View screening 9f1c 0a6e/?&=");
  assert.equal(textOf(view), "View");
  assert.equal(context.list.RESULT_PAGE, "result.html");
  assert.equal(
    context.list.viewHref(ROW_ID),
    "result.html?id=" + encodeURIComponent(ROW_ID),
  );
});

test("Delete asks first, names the row, and a cancelled ask sends nothing", () => {
  const context = loadList();
  const controller = bind(context);
  controller.render(payload());

  const remove = deleteButtonOf(context);
  assert.equal(remove.tagName, "BUTTON", "Delete changes a server, so it is not a link");
  assert.equal(remove.getAttribute("type"), "button");
  assert.equal(remove.getAttribute("data-row-id"), ROW_ID);
  remove.click();

  assert.ok(context.confirm.classes.has("is-open"), "the confirmation did not open");
  assert.equal(textOf(context.confirmId), ROW_ID, "the confirmation does not say which row");
  assert.ok(context.confirmOk.focused, "focus did not move to the confirming control");

  context.confirmCancel.click();

  assert.equal(context.confirm.classes.has("is-open"), false, "cancelling left it open");
  assert.deepEqual(context.sent.calls, [], "a cancelled ask reached the service");
});

test("the confirmed delete goes to the item route as a DELETE, and the list is re-read", async () => {
  const context = loadList({ respond: () => payload([], 0) });
  const controller = bind(context);
  controller.render(payload());

  deleteButtonOf(context).click();
  const page = await controller.confirmDelete();

  assert.deepEqual(context.sent.calls, [
    { path: "/api/screenings/" + encodeURIComponent(ROW_ID), method: "DELETE" },
    { path: "/api/screenings", method: "GET" },
  ]);

  assert.equal(page.total, 0);
  assert.equal(rowsOf(context).length, 0, "the deleted row is still drawn");
  assert.equal(textOf(context.count), "Showing 0 of 0 screenings");
  assert.equal(textOf(context.notice), ROW_ID + " deleted.");
  assert.equal(
    context.confirm.classes.has("is-open"),
    false,
    "the confirmation stayed open over a finished delete",
  );
});

test("a delete the service refuses leaves the row standing and says why", async () => {
  const context = loadList();
  context.sent.deleteError = new Error("no such screening");
  const controller = bind(context);
  controller.render(payload());

  deleteButtonOf(context).click();
  const page = await controller.confirmDelete();

  assert.equal(page, null);
  assert.equal(rowsOf(context).length, 1, "a refused delete removed the row anyway");
  assert.equal(context.sent.calls.length, 1, "a refused delete was re-read");
  assert.equal(textOf(context.notice), "no such screening");
  assert.equal(controller.error().message, "no such screening");
});

test("a page with no confirmation refuses the delete by name", () => {
  const context = loadList();
  const controller = bind(context, {
    confirm: null,
    confirmId: null,
    confirmOk: null,
    confirmCancel: null,
  });
  controller.render(payload());

  deleteButtonOf(context).click();

  assert.deepEqual(context.sent.calls, []);
  assert.equal(controller.error().code, "no_confirm");
  assert.match(textOf(context.notice), /nothing was deleted/);
  assert.equal(context.confirm.classes.has("is-open"), false);
});

test("the confirmation is a dialog in the page, and pages.js no longer answers the rows", () => {
  const dialog = deleteDialog();

  assert.equal(dialog.role, "dialog");
  assert.equal(dialog.modal, "true");
  assert.equal(dialog.labelledBy, "delete-confirm-title");
  assert.equal(dialog.describedBy, "delete-confirm-message");
  assert.ok(dialog.ids.includes("delete-confirm-title"));
  assert.ok(dialog.ids.includes("delete-confirm-message"));
  assert.ok(dialog.ids.includes("delete-confirm-id"));
  assert.deepEqual(
    dialog.buttons.map((button) => button.id),
    ["delete-cancel", "delete-confirm-button"],
  );
  assert.deepEqual(dialog.buttons.map((button) => button.label), [
    "Cancel",
    "Delete",
  ]);
  for (const button of dialog.buttons) {
    assert.equal(button.type, "button", button.id + " submits something");
  }
  assert.doesNotMatch(
    pageHtml,
    /class="[^"]*\bis-open\b/,
    "the confirmation ships open",
  );

  assert.doesNotMatch(
    pagesSource,
    /data-row-action/,
    "pages.js still answers the row actions the module owns",
  );
  assert.doesNotMatch(
    pagesSource,
    /Nothing was deleted on a server/,
    "the stub that claimed no server was touched is still there",
  );
  assert.match(
    pagesSource,
    /document.addEventListener\("drishti:screenings-changed", render\)/,
    "the page does not re-apply its filter over a redraw",
  );
});

test("a redraw announces itself, so the filter the page owns survives a delete", () => {
  const context = loadList();

  bind(context).render(payload());

  assert.deepEqual(context.dispatched, [context.list.REDRAWN_EVENT]);
  assert.equal(context.list.REDRAWN_EVENT, "drishti:screenings-changed");
});
// 24.6: one CSV line, as a spreadsheet reads it: every field quoted and an
// inner quote doubled.
function csvLine(fields) {
  return fields
    .map((field) => '"' + String(field).replace(/"/g, '""') + '"')
    .join(",");
}

// The values of a drawn row, read the way an officer reads the row: the
// Screening cell's id and status travel as one field, then the cells the
// remaining columns name. Actions is the seventh cell and is not data.
function drawnFields(row) {
  const cells = row.children;
  const [id, status] = cells[0].children[0].children;
  return [
    textOf(id).trim() + " " + textOf(status).trim(),
    ...cells.slice(1, 6).map((cell) => textOf(cell).trim()),
  ];
}

test("the export's columns are the table's own columns, less the actions", () => {
  const context = loadList();

  assert.deepEqual(
    Array.from(context.list.CSV_COLUMNS),
    COLUMN_NAMES.slice(0, -1),
  );
  assert.deepEqual(
    headerColumns().map((column) => column.name).slice(0, -1),
    Array.from(context.list.CSV_COLUMNS),
    "the export names a column the page does not have",
  );
});

test("the export carries the rows the page left visible, in the order it holds them", () => {
  const context = loadList();
  const controller = bind(context);
  controller.render(
    payload(
      [
        item({ screening_id: "low-row", band: "low", score: 92 }),
        item({ screening_id: "review-row", band: "review", score: 61 }),
        item({ screening_id: "high-row", band: "high", score: 12 }),
      ],
      41,
    ),
  );
  const [low, review, high] = rowsOf(context);
  // The filter belongs to the page, and it says which rows it excluded by
  // hiding them. That answer is what the export reads.
  review.hidden = true;

  context.exportButton.click();

  assert.equal(context.downloaded.length, 1, "the button saved no file");
  assert.equal(context.downloaded[0].fileName, "drishti-screenings.csv");
  assert.equal(context.downloaded[0].type, "text/csv;charset=utf-8");
  assert.deepEqual(
    context.downloaded[0].contents.split("\r\n"),
    [
      csvLine(context.list.CSV_COLUMNS),
      csvLine(drawnFields(low)),
      csvLine(drawnFields(high)),
      "",
    ],
    "the file is not the rows the officer can see",
  );
  assert.doesNotMatch(
    context.downloaded[0].contents,
    /review-row/,
    "a row the page filtered out was exported",
  );
  assert.equal(controller.csvText(), context.downloaded[0].contents);
});

test("a page with nowhere to save the file refuses the export by name", () => {
  const context = loadList({ withDownload: false });
  const controller = bind(context);
  controller.render(payload());

  context.exportButton.click();

  assert.deepEqual(context.downloaded, []);
  assert.equal(controller.error().code, "no_download");
  assert.match(textOf(context.notice), /nothing was exported/);
});

test("the button and the file plumbing stay in pages.js, the CSV does not", () => {
  assert.match(pageHtml, /id="export-screenings"/);
  assert.match(pagesSource, /window\.DRISHTI_DOWNLOAD = downloadFile;/);
  assert.doesNotMatch(
    pagesSource,
    /export-screenings/,
    "pages.js still answers the export button the module owns",
  );
  assert.doesNotMatch(
    pagesSource,
    /text\/csv/,
    "pages.js writes the CSV again, over rows it cannot see the state of",
  );
});
// 24.7: the three states the table is not in -- the skeleton it waits with,
// the alert a failed read lands in, and the empty panel -- and the one switch
// that keeps two of them off the page at the same time.

// The markup of one state, read by its id up to the id of the next, so the
// states can be told apart in the page rather than in one page-wide search.
function regionMarkup(id, nextId) {
  const start = pageHtml.indexOf('id="' + id + '"');
  assert.ok(start >= 0, "the history page no longer has #" + id);
  const from = pageHtml.lastIndexOf("<", start);
  const to =
    nextId === null
      ? pageHtml.length
      : pageHtml.lastIndexOf(
          "<",
          pageHtml.indexOf('id="' + nextId + '"'),
        );
  return pageHtml.slice(from, to);
}

// What an officer can see at once. Exactly one name may come back, because the
// table, the skeleton, the alert and the empty panel are switched together.
function visibleStates(context) {
  return [
    context.scroll.hidden === false ? "rows" : null,
    context.loading.hidden === false ? "loading" : null,
    context.failure.hidden === false ? "error" : null,
    context.empty.hidden === false ? "empty" : null,
  ].filter((name) => name !== null);
}

// The opening tags of a region, the way a browser splits them.
function openingTags(markup) {
  return [...markup.matchAll(/<([a-z]+)\b[^>]*>/g)].map(([tag]) => tag);
}

// A class the installed stylesheet has to carry: a shape or an alert variant
// nobody has read out of 2.1.0 is a typo, and the page would draw nothing.
function ships(className) {
  return new RegExp("\\." + className + "\\s*\\{").test(sheet);
}

test("the loading state is the page's own skeleton, until the answer lands", async () => {
  const context = loadList();
  const controller = bind(context);
  let read = null;
  const waiting = controller.load().then((page) => {
    read = page;
  });

  assert.equal(controller.state(), "loading");
  assert.deepEqual(visibleStates(context), ["loading"]);
  assert.equal(context.loading.getAttribute("aria-busy"), "true");
  assert.equal(textOf(context.count), context.list.LOADING_MESSAGE);

  await waiting;

  assert.equal(read.rows.length, 1);
  assert.equal(controller.state(), "rows");
  assert.deepEqual(visibleStates(context), ["rows"]);
  assert.equal(context.loading.getAttribute("aria-busy"), "false");
});

test("every skeleton shape on the page is one the sheet ships, and none is read aloud", () => {
  const region = regionMarkup("screenings-loading", "screenings-error");
  const shapes = openingTags(region).filter((tag) =>
    /class="[^"]*ux4g-skeleton-/.test(tag),
  );

  assert.ok(shapes.length > 0, "the loading state draws no skeleton shape");
  for (const shape of shapes) {
    const skeleton = /class="([^"]*)"/.exec(shape)[1]
      .split(/\s+/)
      .filter((name) => name.startsWith("ux4g-skeleton-"));
    assert.equal(skeleton.length, 1, shape + " is not one shape");
    assert.ok(ships(skeleton[0]), skeleton[0] + " is not in the installed sheet");
    assert.match(shape, /aria-hidden="true"/, shape + " would be read aloud");
  }
});

test("a failed read lands in the error alert, in the failure's own words", async () => {
  const context = loadList();
  context.sent.fails = new Error("the service is down");
  const controller = bind(context);

  const page = await controller.load();

  assert.equal(page, null);
  assert.equal(controller.state(), "error");
  assert.deepEqual(visibleStates(context), ["error"]);
  assert.equal(textOf(context.failureMessage), "the service is down");
  assert.equal(textOf(context.count), "", "the count still reads a stale sample");
  assert.equal(controller.error().message, "the service is down");
});

test("the error state is the sheet's error alert, and it offers the read again", () => {
  const region = regionMarkup("screenings-error", "screenings-empty");
  const alert = /<div\b[^>]*class="[^"]*ux4g-alert[^"]*"[^>]*>/.exec(region);

  assert.ok(alert, "the error state draws no ux4g-alert");
  const classes = /class="([^"]*)"/.exec(alert[0])[1].split(/\s+/);
  assert.equal(classes[0], "ux4g-alert", "the base class is missing or not first");
  assert.ok(classes.includes("ux4g-alert-error"), classes.join(" ") + " is not the error variant");
  for (const name of classes) {
    assert.ok(ships(name), name + " is not in the installed sheet");
  }
  assert.match(alert[0], /role="alert"/, "an alert that arrives late must say so");
  assert.match(region, /id="screenings-error-message"/);
  assert.match(
    region,
    /class="ux4g-btn ux4g-btn-outline-primary ux4g-btn-md"\s+id="screenings-retry"/,
  );
});

test("an answer with no rows shows the empty state and nothing else", async () => {
  const context = loadList({ respond: () => payload([], 0) });
  const controller = bind(context);

  await controller.load();

  assert.equal(controller.state(), "empty");
  assert.deepEqual(visibleStates(context), ["empty"]);
  assert.equal(context.loading.getAttribute("aria-busy"), "false");
  assert.equal(context.empty.hidden, false);
});

test("the empty state is the sheet's empty state, and it carries both ways out", () => {
  const region = regionMarkup("screenings-empty", null);
  const state = /<div\b[^>]*class="([^"]*ux4g-empty-state[^"]*)"[^>]*>/.exec(region);

  assert.ok(state, "the empty state is not a ux4g-empty-state");
  assert.ok(ships("ux4g-empty-state"), "the sheet ships no empty state");
  assert.match(region, /id="clear-filters"/);
  assert.match(region, /href="\.\/home\.html"/);
});

test("one state at a time: the retry press reads the route again", async () => {
  const context = loadList();
  context.sent.fails = new Error("the service is down");
  const controller = bind(context);
  await controller.load();
  assert.deepEqual(visibleStates(context), ["error"]);

  context.sent.fails = null;
  context.retry.click();
  // The press is the page's, so the read it starts is the page's to await.
  await new Promise((resolve) => setTimeout(resolve, 0));

  assert.equal(controller.state(), "rows");
  assert.deepEqual(visibleStates(context), ["rows"]);
  assert.deepEqual(context.sent.paths, ["/api/screenings", "/api/screenings"]);
  assert.equal(textOf(context.count), "Showing 1 of 1 screenings");
});

test("a state this page does not have is refused by name", () => {
  const context = loadList();
  const controller = bind(context);

  refuses(() => controller.showState("busy"), "bad_state");
  assert.deepEqual([...context.list.STATES].sort(), [
    "empty",
    "error",
    "loading",
    "rows",
  ]);
});