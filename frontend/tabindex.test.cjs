const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const { buildFileNames } = require('./build.cjs');

/* D209: the tab order has to be the DOM order, so nothing in this repo may
   claim a tabindex above zero. A positive tabindex lifts an element ahead of
   everything the document would otherwise have put it after, and the DOM order
   is the order this markup already gets right. This guard reads every page,
   every module and both stylesheets, and fails on any positive value in any of
   them.

   Two shapes are read, because the repo writes both:
     - a value written where the attribute itself is: tabindex="3" in markup,
       setAttribute('tabindex', 3) and el.tabIndex = 3 in script;
     - a value held in a named constant and set through it, as overlay.js does
       with REGION_TABINDEX.
   Zero and -1 are both fine, and mean different things. -1 takes an element
   out of the tab order so script can move focus onto it, which is what the
   focus targets in home.html, profile.html and screenings.html use. 0 puts a
   non-native control into the order at its DOM position, which is what
   overlay.js's role="button" regions need. */

const DIRECT = /\btabindex["']?\s*[=:,]\s*["']?\s*(-?\d+)/gi;
const NAMED = /\b[A-Za-z_][A-Za-z0-9_]*TABINDEX[A-Za-z0-9_]*\s*=\s*["']?\s*(-?\d+)/g;

const { pageFileNames } = buildFileNames();

function readFront(fileName) {
  return fs.readFileSync(path.join(__dirname, fileName), 'utf8');
}

/** Every tabindex value a source commits to, in the order they are written. */
function tabindexValues(source) {
  const found = [];
  for (const pattern of [DIRECT, NAMED]) {
    for (const match of source.matchAll(pattern)) {
      found.push({ value: Number(match[1]), at: match.index });
    }
  }
  return found.sort((a, b) => a.at - b.at);
}

/** The values above zero, which is the whole point of this guard. */
function positiveValues(source) {
  return tabindexValues(source)
    .filter((entry) => entry.value > 0)
    .map((entry) => entry.value);
}

/** The same values as bare numbers, for the fixtures that assert on them. */
function numbersIn(source) {
  return tabindexValues(source).map((entry) => entry.value);
}
/** The pages, the shell they share, and every module and stylesheet they load. */
function frontFileNames(suffix, skip) {
  return fs
    .readdirSync(__dirname)
    .filter((name) => name.endsWith(suffix))
    .filter((name) => !name.endsWith(skip));
}

const scannedFileNames = pageFileNames
  .concat(['shell.html'])
  .concat(frontFileNames('.js', '.test.cjs'))
  .concat(frontFileNames('.css', '.never'));

/* ---------- the assertion, one file at a time ---------- */

for (const fileName of scannedFileNames) {
  test(fileName + ' sets no positive tabindex', (t) => {
    const source = readFront(fileName);
    const values = tabindexValues(source);
    t.diagnostic(values.length ? values.map((entry) => entry.value).join(' ') : '(none)');
    assert.deepEqual(
      positiveValues(source),
      [],
      fileName + ' raises a tab stop above the DOM order',
    );
  });
}

/* ---------- the sweep is not empty ---------- */

test('the sweep reads the tabindex values the repo actually writes', () => {
  const read = scannedFileNames.flatMap((fileName) =>
    tabindexValues(readFront(fileName)).map((entry) => entry.value),
  );

  assert.ok(read.length > 0, 'nothing was read, so every file above passed vacuously');
  assert.ok(
    read.includes(-1),
    'the focus targets write tabindex="-1" and the sweep missed them',
  );
  assert.ok(
    read.includes(0),
    "overlay.js writes REGION_TABINDEX = '0' and the sweep missed it",
  );
  assert.deepEqual(
    read.filter((value) => value > 0),
    [],
    'a positive value is already in the sweep, so a file above should be red',
  );
});

/* ---------- the guard is red when it should be ---------- */

test('a positive tabindex written into markup is red', () => {
  assert.deepEqual(positiveValues('<button tabindex="3">Go</button>'), [3]);
  assert.deepEqual(positiveValues("<a href='x' tabindex='1'>x</a>"), [1]);
});

test('a positive tabindex set from script is red', () => {
  assert.deepEqual(positiveValues("el.setAttribute('tabindex', 2);"), [2]);
  assert.deepEqual(positiveValues('el.tabIndex = 7;'), [7]);
});

test('a positive tabindex behind a named constant is red', () => {
  assert.deepEqual(positiveValues('const REGION_TABINDEX = "4";'), [4]);
});

test('a selector naming tabindex is not a value', () => {
  assert.deepEqual(tabindexValues('[tabindex]'), []);
  assert.deepEqual(numbersIn('[tabindex]:not([tabindex="-1"])'), [-1]);
  assert.deepEqual(tabindexValues('el.setAttribute("tabindex", REGION_TABINDEX);'), []);
});

test('zero and minus one are both allowed', () => {
  assert.deepEqual(positiveValues('<div role="button" tabindex="0"></div>'), []);
  assert.deepEqual(positiveValues('<h2 tabindex="-1">Screenings</h2>'), []);
});

/* ---------- the visible-focus half of the same audit ---------- */

/* UX4G zeroes the outline on every element and then puts one back on
   :focus-visible. The reset is written :where(*), which carries no specificity,
   and the focus rule is a bare pseudo-class, so the ring wins and a keyboard
   user can see where they are. Both halves are asserted, because if a future
   package drops either one then focus goes invisible on every page and the
   conclusion recorded for 25.6 quietly stops being true. This repo adds colour
   on :focus-visible but never an outline of its own, so it cannot be the
   thing that removes the ring. */

const packageCss = fs.readFileSync(
  path.join(__dirname, 'node_modules', 'ux4g-web-components', 'styles', 'ux4g.css'),
  'utf8',
);

test('UX4G still zeroes the outline through a zero-specificity reset', () => {
  assert.match(packageCss, /:where\(\*[^)]*\)\{[^}]*outline:0/);
});

test('UX4G still gives :focus-visible an outline of its own', () => {
  assert.match(packageCss, /:focus-visible\{outline:[^}]+\}/);
});

test('our stylesheets never take the focus ring away', () => {
  for (const fileName of frontFileNames('.css', '.never')) {
    assert.doesNotMatch(
      readFront(fileName),
      /[^{}]*:focus[^{}]*\{[^}]*outline:\s*(0|none)\b/i,
      fileName + ' hides the focus ring the package provides',
    );
  }
});
