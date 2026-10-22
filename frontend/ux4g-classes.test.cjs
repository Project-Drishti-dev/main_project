const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const { buildFileNames, renderPage } = require("./build.cjs");

/* D207: the list of UX4G classes a page uses is read out of that page's own
   markup, never written by hand, and every name on it is looked up in the one
   stylesheet shell.html loads. A name the sheet does not carry is a class the
   browser would not draw, which no reading of the CSS can catch. */

const sheet = fs.readFileSync(
  path.join(__dirname, "node_modules", "ux4g-web-components", "styles", "ux4g.css"),
  "utf8",
);

const { pageFileNames } = buildFileNames();

function readFront(fileName) {
  return fs.readFileSync(path.join(__dirname, fileName), "utf8");
}

/* ---------- the guard ---------- */

/** Every token of every class="" attribute in the markup, deduplicated. */
function classTokens(html) {
  return [
    ...new Set(
      [...html.matchAll(/class="([^"]*)"/g)]
        .flatMap((match) => match[1].split(/\s+/))
        .filter((name) => name.length > 0),
    ),
  ];
}

/** The UX4G ones, sorted: the names the design system owns, not our own. */
function ux4gClasses(html) {
  return classTokens(html)
    .filter((name) => name.startsWith("ux4g-"))
    .sort();
}

/**
 * Whether the stylesheet defines the class. The boundary is the whole point:
 * a lookup for ux4g-p-l must not be answered by ux4g-p-lg, or a typo reads as
 * a hit and the guard is theatre.
 */
function isShipped(name) {
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp("\\." + escaped + "(?![\\w-])").test(sheet);
}

/** The classes the page names that the installed stylesheet does not define. */
function unknownClasses(html) {
  return ux4gClasses(html).filter((name) => !isShipped(name));
}

/** The one assertion every page gets, and the one the fixtures below must red. */
function assertOnlyShippedClasses(html, label) {
  const used = ux4gClasses(html);
  assert.ok(
    used.length > 0,
    label + " names no UX4G class, so the guard would pass on it vacuously",
  );
  assert.deepEqual(
    unknownClasses(html),
    [],
    label + " names a UX4G class ux4g.css does not define",
  );
}

/* ---------- the stylesheet being the right one to grep ---------- */

test("the stylesheet this guard greps is the one a built page loads", () => {
  const link = /node_modules\/ux4g-web-components\/styles\/ux4g\.css/;

  assert.match(readFront("shell.html"), link);
  for (const pageFileName of pageFileNames) {
    assert.match(
      renderPage(readFront(pageFileName), pageFileName),
      link,
      pageFileName + " is built without the stylesheet the guard reads",
    );
  }
});

/* ---------- every page, one assertion each ---------- */

for (const pageFileName of pageFileNames) {
  test(`${pageFileName} names only UX4G classes the installed stylesheet ships`, (t) => {
    const html = readFront(pageFileName);
    t.diagnostic(ux4gClasses(html).join(" "));
    assertOnlyShippedClasses(html, pageFileName);
  });
}

test("the shell names only UX4G classes the installed stylesheet ships", (t) => {
  const html = readFront("shell.html");
  t.diagnostic(ux4gClasses(html).join(" "));
  assertOnlyShippedClasses(html, "shell.html");
});

/* ---------- the guard is red when it should be ---------- */

test("a page naming a class the stylesheet does not define is red", () => {
  assert.throws(
    () =>
      assertOnlyShippedClasses(
        '<div class="ux4g-card ux4g-card-typo"></div>',
        "the typo fixture",
      ),
    /names a UX4G class ux4g\.css does not define/,
  );
});

test("a longer shipped name does not answer a shorter lookup", () => {
  assert.equal(isShipped("ux4g-card"), true, "ux4g-card is in the sheet");
  assert.equal(
    isShipped("ux4g-card-b"),
    false,
    "ux4g-card-b must not be answered by ux4g-card-body or ux4g-card",
  );
  assert.equal(isShipped("ux4g-p-l"), true);
  assert.equal(isShipped("ux4g-p-larger"), false);
});

test("a page with no UX4G class at all is red rather than vacuously green", () => {
  assert.throws(
    () =>
      assertOnlyShippedClasses('<div class="page-header"></div>', "the plain fixture"),
    /no UX4G class/,
  );
});

test("only the design system's own names are judged, not ours", () => {
  assert.deepEqual(unknownClasses('<div class="page-header table-panel active"></div>'), []);
  assert.deepEqual(unknownClasses('<div class="visually-hidden"></div>'), []);
});