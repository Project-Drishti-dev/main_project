const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const {
  MEASURE_PAGE,
  MIN_READABLE_FONT_PX,
  OVERFLOW_TOLERANCE_PX,
  VIEWPORT_WIDTHS,
  analyseMeasurement,
  describeFinding,
  findBrowserExecutable,
  measurementIsClean,
  readDevToolsPort,
  reportEntry,
  shotsDirectory,
} = require("./scripts/viewport-shots.cjs");

/* D210: the verdicts this harness prints have to be decidable without a
   browser, or a run could only be trusted by looking at its own pictures.
   Every rule below is one the four widths are checked against. */

function cleanMeasurement(overrides = {}) {
  return {
    viewportWidth: 320,
    scrollWidth: 320,
    overflowPx: 0,
    overflowing: [],
    smallText: [],
    clippedText: [],
    ...overrides,
  };
}

test("the four widths this task names are the widths the harness renders", () => {
  assert.deepEqual(VIEWPORT_WIDTHS, [320, 768, 1024, 1440]);
});

test("a page that fits is clean", () => {
  const findings = analyseMeasurement(cleanMeasurement());
  assert.deepEqual(findings, []);
  assert.equal(measurementIsClean(findings), true);
});

test("a page wider than its viewport is an overflow finding", () => {
  const findings = analyseMeasurement(
    cleanMeasurement({ scrollWidth: 342, overflowPx: 22 }),
  );
  assert.equal(findings.length, 1);
  assert.equal(findings[0].kind, "page-overflow");
  assert.equal(findings[0].overflowPx, 22);
  assert.equal(measurementIsClean(findings), false);
});

test("an overflow inside the tolerance is not a finding", () => {
  const findings = analyseMeasurement(
    cleanMeasurement({ scrollWidth: 321, overflowPx: OVERFLOW_TOLERANCE_PX }),
  );
  assert.deepEqual(findings, []);
});

test("an element past the right edge is named, not just counted", () => {
  const findings = analyseMeasurement(
    cleanMeasurement({
      overflowing: [{ selector: "div.page-header__actions", left: 216, right: 844 }],
    }),
  );
  assert.equal(findings.length, 1);
  assert.equal(findings[0].kind, "element-overflow");
  assert.equal(findings[0].selector, "div.page-header__actions");
});

test("text below the readable floor is a finding carrying the floor", () => {
  const findings = analyseMeasurement(
    cleanMeasurement({ smallText: [{ selector: "span.micro", fontSize: 8 }] }),
  );
  assert.equal(findings.length, 1);
  assert.equal(findings[0].kind, "small-text");
  assert.equal(findings[0].minFontPx, MIN_READABLE_FONT_PX);
});

test("text cut off by a clipping box is a finding", () => {
  const findings = analyseMeasurement(
    cleanMeasurement({
      clippedText: [{ selector: "h2#records-title", clientWidth: 240, scrollWidth: 443 }],
    }),
  );
  assert.equal(findings.length, 1);
  assert.equal(findings[0].kind, "clipped-text");
});

test("page overflow is reported before the element that caused it", () => {
  const findings = analyseMeasurement(
    cleanMeasurement({
      overflowPx: 22,
      overflowing: [{ selector: "main", left: 0, right: 342 }],
    }),
  );
  assert.deepEqual(
    findings.map((finding) => finding.kind),
    ["page-overflow", "element-overflow"],
  );
});

test("every finding has a sentence, so the report can be read without the picture", () => {
  for (const finding of analyseMeasurement(
    cleanMeasurement({
      overflowPx: 22,
      overflowing: [{ selector: "main", left: 0, right: 342 }],
      smallText: [{ selector: "span.micro", fontSize: 8 }],
      clippedText: [{ selector: "h2#t", clientWidth: 240, scrollWidth: 443 }],
    }),
  )) {
    const sentence = describeFinding(finding);
    assert.equal(typeof sentence, "string");
    assert.ok(sentence.length > 0, `${finding.kind} needs a sentence`);
    assert.ok(
      !sentence.includes("[object Object]"),
      `${finding.kind} must not stringify an object`,
    );
  }
});

test("the report entry marks a page clean only when nothing was found", () => {
  const clean = reportEntry(
    "home.html",
    768,
    { measurement: cleanMeasurement(), contentHeight: 1200, consoleErrors: [] },
    "768/home.png",
  );
  assert.equal(clean.clean, true);
  assert.equal(clean.screenshotName, "768/home.png");

  const dirty = reportEntry(
    "profile.html",
    768,
    {
      measurement: cleanMeasurement({ overflowPx: 76 }),
      contentHeight: 1600,
      consoleErrors: [],
    },
    "768/profile.png",
  );
  assert.equal(dirty.clean, false);
  assert.equal(dirty.findings.length, 1);
});

test("the browser is found by name, and a missing one is named too", () => {
  const missing = path.join(__dirname, ".no-such-browser-here");
  assert.throws(() => findBrowserExecutable([missing]), /no browser found/);
  assert.equal(findBrowserExecutable([missing, __filename]), __filename);
  assert.throws(() => findBrowserExecutable([null, ""]), /no browser found/);
});

test("a DevTools port is read from the file the browser wrote", () => {
  const directory = fs.mkdtempSync(path.join(__dirname, ".shots-port-test-"));
  try {
    const portFile = path.join(directory, "DevToolsActivePort");
    fs.writeFileSync(portFile, "51234\n/devtools/browser/abc\n", "utf8");
    assert.equal(readDevToolsPort(directory), 51234);

    fs.writeFileSync(portFile, "not-a-port\n", "utf8");
    assert.throws(() => readDevToolsPort(directory), /no usable port/);
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
});

test("the page script skips the 1px clipping hack that hides text on purpose", () => {
  assert.match(MEASURE_PAGE, /element\.clientWidth > 1 && element\.clientHeight > 1/);
  assert.match(MEASURE_PAGE, new RegExp(String(MIN_READABLE_FONT_PX)));
});

test("the shot directory is one .gitignore does not swallow", () => {
  const ignore = fs.readFileSync(path.resolve(__dirname, "..", ".gitignore"), "utf8");
  const relative = path
    .relative(path.resolve(__dirname, ".."), shotsDirectory())
    .replace(/\\/g, "/");
  const ignored = ignore
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith("#"))
    .some((line) => {
      const pattern = line.replace(/^\//, "").replace(/\/$/, "");
      return relative === pattern || relative.startsWith(`${pattern}/`);
    });
  assert.equal(ignored, false, `${relative} is ignored by .gitignore`);
});