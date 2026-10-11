const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const {
  MEASURE_THEME,
  MIN_DISTINGUISHABLE_RATIO,
  MIN_TEXT_CONTRAST_RATIO,
  THEMES,
  analyseThemeMeasurement,
  describeThemeFinding,
  summariseThemes,
  themeMeasurementIsClean,
  themeShotsDirectory,
} = require("./scripts/theme-shots.cjs");

/* D211: the verdicts this harness prints have to be decidable without a
   browser, or a run could only be trusted by looking at its own pictures. */

function cleanMeasurement(overrides = {}) {
  return {
    themeAttribute: "light",
    themePreference: "light",
    textSize: "default",
    pageBackground: "rgb(255, 255, 255)",
    pageColor: "rgb(23, 23, 23)",
    rootBackground: "rgb(255, 255, 255)",
    distinctColorCount: 12,
    unreadableText: [],
    invisibleBorders: [],
    ...overrides,
  };
}

test("both themes are rendered, and the dark one is in the set", () => {
  assert.deepEqual(THEMES, ["light", "dark"]);
});

test("a page whose colours all clear the thresholds is clean", () => {
  const findings = analyseThemeMeasurement(cleanMeasurement(), {
    expectedTheme: "light",
  });
  assert.deepEqual(findings, []);
  assert.equal(themeMeasurementIsClean(findings), true);
});

test("a page that never applied the theme is a finding, not a clean render", () => {
  const findings = analyseThemeMeasurement(
    cleanMeasurement({ themeAttribute: "light" }),
    { expectedTheme: "dark" },
  );
  assert.equal(findings.length, 1);
  assert.equal(findings[0].kind, "theme-not-applied");
  assert.equal(findings[0].expected, "dark");
  assert.equal(findings[0].actual, "light");
});

test("a border in its own background colour is invisible, not merely faint", () => {
  const findings = analyseThemeMeasurement(
    cleanMeasurement({
      invisibleBorders: [
        {
          selector: "span.ux4g-stepper-head-icon",
          side: "top",
          width: 2,
          color: "rgb(38, 38, 38)",
          background: "rgb(38, 38, 38)",
          ratio: 1,
        },
      ],
    }),
  );
  assert.equal(findings.length, 1);
  assert.equal(findings[0].kind, "invisible-border");
  assert.equal(findings[0].minDistinctRatio, MIN_DISTINGUISHABLE_RATIO);
});

test("a border that is merely faint is not called invisible", () => {
  const findings = analyseThemeMeasurement(
    cleanMeasurement({
      invisibleBorders: [
        {
          selector: "aside#app-sidebar",
          side: "right",
          width: 1,
          color: "rgb(64, 64, 64)",
          background: "rgb(10, 10, 10)",
          ratio: 1.91,
        },
      ],
    }),
  );
  assert.deepEqual(findings, []);
});

test("text below 4.5:1 is unreadable and is named with its colours", () => {
  const findings = analyseThemeMeasurement(
    cleanMeasurement({
      unreadableText: [
        {
          selector: "span",
          color: "rgb(250, 140, 22)",
          background: "rgb(255, 231, 191)",
          ratio: 1.98,
          fontSize: 14,
          large: false,
        },
      ],
    }),
  );
  assert.equal(findings.length, 1);
  assert.equal(findings[0].kind, "low-contrast-text");
  assert.equal(findings[0].minTextRatio, MIN_TEXT_CONTRAST_RATIO);
  assert.equal(findings[0].selector, "span");
});

test("large text is held to the same 4.5:1 floor as body text", () => {
  const entry = {
    selector: "h1",
    color: "rgb(115, 115, 115)",
    background: "rgb(245, 245, 245)",
    ratio: 4.35,
    fontSize: 36,
    large: true,
  };
  const findings = analyseThemeMeasurement(
    cleanMeasurement({ unreadableText: [entry] }),
  );
  assert.equal(findings.length, 1);
  assert.equal(findings[0].kind, "low-contrast-text");
});

test("the theme that did not apply is reported before anything it caused", () => {
  const findings = analyseThemeMeasurement(
    cleanMeasurement({
      themeAttribute: "light",
      unreadableText: [
        {
          selector: "span",
          color: "rgb(250, 140, 22)",
          background: "rgb(255, 231, 191)",
          ratio: 1.98,
          fontSize: 14,
          large: false,
        },
      ],
      invisibleBorders: [
        {
          selector: "div.card",
          side: "top",
          width: 1,
          color: "rgb(0, 0, 0)",
          background: "rgb(0, 0, 0)",
          ratio: 1,
        },
      ],
    }),
    { expectedTheme: "dark" },
  );
  assert.deepEqual(
    findings.map((finding) => finding.kind),
    ["theme-not-applied", "invisible-border", "low-contrast-text"],
  );
});

test("every finding has a sentence, so the report reads without the picture", () => {
  for (const finding of analyseThemeMeasurement(
    cleanMeasurement({
      themeAttribute: "light",
      unreadableText: [
        {
          selector: "span",
          color: "rgb(250, 140, 22)",
          background: "rgb(255, 231, 191)",
          ratio: 1.98,
          fontSize: 14,
          large: false,
        },
      ],
      invisibleBorders: [
        {
          selector: "span.icon",
          side: "left",
          width: 2,
          color: "rgb(38, 38, 38)",
          background: "rgb(38, 38, 38)",
          ratio: 1,
        },
      ],
    }),
    { expectedTheme: "dark" },
  )) {
    const sentence = describeThemeFinding(finding);
    assert.equal(typeof sentence, "string");
    assert.ok(sentence.length > 0, `${finding.kind} needs a sentence`);
    assert.ok(
      !sentence.includes("[object Object]"),
      `${finding.kind} must not stringify an object`,
    );
  }
});

test("a page painted one colour in both themes is called out by name", () => {
  const summary = summariseThemes([
    { theme: "light", pageName: "home.html", clean: true, findings: 0,
      measurement: { pageBackground: "rgb(255, 255, 255)" } },
    { theme: "dark", pageName: "home.html", clean: true, findings: 0,
      measurement: { pageBackground: "rgb(255, 255, 255)" } },
  ]);
  assert.equal(summary.length, 1);
  assert.equal(summary[0].sameBackgroundInEveryTheme, true);
});

test("a page that really changed with the theme is not flagged", () => {
  const summary = summariseThemes([
    { theme: "light", pageName: "home.html", clean: true, findings: 0,
      measurement: { pageBackground: "rgb(255, 255, 255)" } },
    { theme: "dark", pageName: "home.html", clean: true, findings: 0,
      measurement: { pageBackground: "rgb(10, 10, 10)" } },
  ]);
  assert.equal(summary[0].sameBackgroundInEveryTheme, false);
  assert.equal(summary[0].clean, true);
});

test("the page script measures the colours, not the class names", () => {
  assert.match(MEASURE_THEME, /getComputedStyle/);
  assert.match(MEASURE_THEME, /data-theme/);
  assert.match(MEASURE_THEME, /contrastRatio/);
});

test("the page script skips a disabled control, which WCAG 1.4.3 exempts", () => {
  assert.match(MEASURE_THEME, /disabledControl/);
  assert.match(MEASURE_THEME, /:disabled/);
});

test("the theme shots directory is one .gitignore does not swallow", () => {
  const ignore = fs.readFileSync(path.resolve(__dirname, "..", ".gitignore"), "utf8");
  const relative = path
    .relative(path.resolve(__dirname, ".."), themeShotsDirectory())
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
