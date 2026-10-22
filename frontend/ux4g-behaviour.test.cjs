const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const { buildFileNames, renderPage } = require('./build.cjs');

/* D208: the UX4G behaviours a page relies on are read out of that page''s own
   bytes, never written by hand. A data- hook is the design system''s when it is
   in the package namespace or when the shipped runtime reads that exact
   attribute; every other data- hook (data-module, data-filter, data-stat) is
   ours and is not judged. Each claimed hook must be implemented by
   dist/runtime/design-system.js or declared as a fallback this repo wires
   itself -- otherwise the page believes in a behaviour the browser never runs.
   Presence of the name in the runtime is the whole test, so a hook the runtime
   reaches only through its U.data(el, name) shorthand reads as unimplemented
   and stays red until a reader confirms it. */

const runtime = fs.readFileSync(
  path.join(__dirname, 'node_modules', 'ux4g-web-components', 'dist', 'runtime', 'design-system.js'),
  'utf8',
);

/** Every data- attribute name the shipped runtime itself names. */
const runtimeHooks = new Set(
  [...runtime.matchAll(/data-[a-z0-9-]+/g)].map((match) => match[0]),
);

/** The package''s own namespace: a hook here claims the runtime explicitly. */
const PACKAGE_NAMESPACE = 'data-ux4g-';

/* Hooks the shipped runtime does not implement and this repo implements itself,
   each with the file that does it. Our debt, not the package''s: an entry holds
   only while the runtime lacks the hook, the file selects it, and every page
   naming it loads that file. */
const FALLBACKS = new Map([['data-ux4g-accordion-toggle', 'pages.js']]);

/** The src of every script a built page loads. */
const scriptSrc = /src=\x22([\w./-]+)\x22/g;

const { pageFileNames } = buildFileNames();
const markupFileNames = [...pageFileNames, 'shell.html'];

function readFront(fileName) {
  return fs.readFileSync(path.join(__dirname, fileName), 'utf8');
}

/** Whether the hook belongs to the design system rather than to us. */
function isDesignSystemHook(name) {
  return name.startsWith(PACKAGE_NAMESPACE) || runtimeHooks.has(name);
}

/** The design-system behaviours a source claims, sorted and deduplicated. */
function behaviours(source) {
  return [...new Set([...source.matchAll(/data-[a-z0-9-]+/g)].map((match) => match[0]))]
    .filter(isDesignSystemHook)
    .sort();
}

/** The claimed hooks neither the runtime nor a declared fallback answers. */
function unanswered(claimed) {
  return claimed.filter((name) => !runtimeHooks.has(name) && !FALLBACKS.has(name));
}

/** The one assertion every page and module gets, and the fixtures must red. */
function assertOnlyAnsweredBehaviours(source, label) {
  assert.deepEqual(
    unanswered(behaviours(source)),
    [],
    label + ' relies on a UX4G behaviour nothing implements',
  );
}

/** Whether the declared file really selects the hook it is said to implement. */
function fallbackSelects(hook, fileName) {
  return readFront(fileName).includes('[' + hook + ']');
}

/** Whether the built page loads the file that implements the hook. */
function pageLoadsFallback(pageFileName, fileName) {
  const html = renderPage(readFront(pageFileName), pageFileName);
  return [...html.matchAll(scriptSrc)].some((match) => match[1] === './' + fileName);
}

/* The modules that write design-system markup into a page after load. Their
   hooks are claims on the same runtime as the static markup''s. */
const moduleFileNames = fs
  .readdirSync(__dirname)
  .filter((name) => name.endsWith('.js') && !name.endsWith('.test.cjs'))
  .filter((name) => behaviours(readFront(name)).length > 0);

/* ---------- the runtime being the right one to grep ---------- */

test('the runtime this guard greps is the one a built page loads', () => {
  const link = /node_modules\/ux4g-web-components\/dist\/runtime\/design-system\.js/;

  assert.match(readFront('shell.html'), link);
  for (const pageFileName of pageFileNames) {
    assert.match(
      renderPage(readFront(pageFileName), pageFileName),
      link,
      pageFileName + ' is built without the runtime the guard reads',
    );
  }
});

/* ---------- every page, one assertion each ---------- */

for (const fileName of markupFileNames) {
  test(fileName + ' relies only on UX4G behaviours the runtime implements', (t) => {
    const source = readFront(fileName);
    t.diagnostic(behaviours(source).join(' ') || '(no UX4G behaviour)');
    assertOnlyAnsweredBehaviours(source, fileName);
  });
}

/* ---------- the modules that draw UX4G markup ---------- */

for (const fileName of moduleFileNames) {
  test(fileName + ' relies only on UX4G behaviours the runtime implements', (t) => {
    const source = readFront(fileName);
    t.diagnostic(behaviours(source).join(' '));
    assertOnlyAnsweredBehaviours(source, fileName);
  });
}

/* ---------- the list is not empty ---------- */

test('the behaviours judged here are read off the pages, not off a list', () => {
  const claimed = new Set(
    markupFileNames
      .concat(moduleFileNames)
      .flatMap((name) => behaviours(readFront(name))),
  );

  for (const hook of [
    'data-ux4g-accordion-toggle',
    'data-close-modal',
    'data-theme',
    'data-ux-progress-bar',
  ]) {
    assert.ok(claimed.has(hook), hook + ' is used but the guard no longer reads it');
  }
});

/* ---------- a declared fallback is real, and still needed ---------- */

test('every page naming a fallback hook loads the file that implements it', () => {
  const checked = [];

  for (const fileName of markupFileNames) {
    for (const hook of behaviours(readFront(fileName))) {
      if (!FALLBACKS.has(hook)) continue;
      const fallbackFileName = FALLBACKS.get(hook);
      assert.ok(
        fallbackSelects(hook, fallbackFileName),
        fallbackFileName + ' must select [' + hook + '] for ' + fileName,
      );
      assert.ok(
        pageLoadsFallback(fileName, fallbackFileName),
        fileName + ' must load ' + fallbackFileName + ' or nothing implements ' + hook,
      );
      checked.push(fileName + ' ' + hook);
    }
  }

  assert.ok(checked.length > 0, 'no page claims a fallback hook, so nothing above ran');
});

test('no declared fallback is a hook the runtime already implements', () => {
  for (const [hook, fallbackFileName] of FALLBACKS) {
    assert.equal(
      runtimeHooks.has(hook),
      false,
      hook + ' is implemented by the runtime; drop ' + fallbackFileName + ' and the entry',
    );
  }
});

/* ---------- the guard is red when it should be ---------- */

test('a hook the runtime does not implement and nothing declares is red', () => {
  assert.throws(
    () =>
      assertOnlyAnsweredBehaviours(
        '<button data-ux4g-tab-panel></button>',
        'the invented fixture',
      ),
    /relies on a UX4G behaviour nothing implements/,
  );
});

test('a longer hook the runtime reads does not answer a shorter lookup', () => {
  assert.deepEqual(unanswered(['data-ux4g-toggle-disable']), []);
  assert.deepEqual(unanswered(['data-ux4g-toggle']), []);
  assert.deepEqual(
    unanswered(['data-ux4g-toggle-disabl']),
    ['data-ux4g-toggle-disabl'],
    'a truncated name is unimplemented even though a longer one ships',
  );
});

test('our own hooks are not judged as design-system behaviours', () => {
  const ours = '<div data-module data-filter data-stat data-sort-key data-placeholder-switch data-display data-nav></div>';

  assert.deepEqual(behaviours(ours), []);
  assert.deepEqual(unanswered(behaviours(ours)), []);
});

test('a fallback whose file does not select the hook is red', () => {
  assert.equal(fallbackSelects('data-ux4g-accordion-toggle', 'pages.js'), true);
  assert.equal(
    fallbackSelects('data-ux4g-accordion-toggle', 'api.js'),
    false,
    'api.js selects no accordion toggle, so it implements nothing',
  );
});

test('a page that does not load the fallback file is red', () => {
  assert.equal(pageLoadsFallback('guide.html', 'pages.js'), true);
  assert.equal(
    pageLoadsFallback('guide.html', 'home.js'),
    false,
    'guide.html must not rely on a file it does not load',
  );
});
