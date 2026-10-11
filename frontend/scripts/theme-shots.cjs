const fs = require("node:fs");
const path = require("node:path");

const {
  MAX_CAPTURE_HEIGHT,
  capturePage,
  collectConsoleErrors,
  connectToTarget,
  findBrowserExecutable,
  launchBrowser,
  makeUserDataDirectory,
  navigateAndSettle,
  removeUserDataDirectory,
  waitForDevToolsPort,
  BROWSER_START_TIMEOUT_MS,
} = require("./browser-capture.cjs");
const {
  previewPageNames,
  previewUrl,
  startPreviewServer,
} = require("./preview.cjs");

/* D211: renders every built page in every theme and reads back what the
   browser actually painted.  A dark theme that never applied looks identical
   to the light one in a screenshot, so the harness asserts the attribute the
   theme resolves to and measures the colours that reached the screen. */

const THEMES = ["light", "dark"];
const THEME_WIDTH = 1280;
const VIEWPORT_HEIGHT = 900;
const PREFERENCE_STORAGE_KEY = "drishti.preferences.v1";
const MAX_CONSOLE_ERRORS = 5;
const PAGE_SETTLE_MS = 600;

/* Below this a pair of colours is treated as indistinguishable on screen.
   1.0 means the two are the same colour; anything under 1.05 is a rounding
   difference, not a visible difference. */
const MIN_DISTINGUISHABLE_RATIO = 1.05;

/* WCAG 2.1 minimum for body text.  The task asks for unreadable text to be
   found, so the threshold is the published 4.5:1 rather than a guess. */
const MIN_TEXT_CONTRAST_RATIO = 4.5;

/* A non-text boundary has to clear 3:1 to be perceivable at all. */
const MIN_BORDER_CONTRAST_RATIO = 3;

function repositoryRoot() {
  return path.resolve(__dirname, "..", "..");
}

/* Not "screenshots/": .gitignore ignores that name at every depth, and this
   set is meant to be reviewable. */
function themeShotsDirectory() {
  return path.resolve(
    process.env.DRISHTI_THEME_SHOTS_DIR ||
      path.join(repositoryRoot(), "docs", "theme-shots"),
  );
}

/* The page script.  It reports the computed colours the browser resolved,
   which is the only way to see a token that failed to follow the theme: the
   source says var(--token) either way. */
const MEASURE_THEME = `(() => {
  const root = document.documentElement;

  const describe = (element) => {
    if (element.id) return element.tagName.toLowerCase() + "#" + element.id;
    const testId = element.getAttribute("data-testid");
    if (testId) return element.tagName.toLowerCase() + "[data-testid=" + testId + "]";
    const classes = (element.getAttribute("class") || "")
      .trim().split(/\\s+/).filter(Boolean).slice(0, 3);
    return classes.length
      ? element.tagName.toLowerCase() + "." + classes.join(".")
      : element.tagName.toLowerCase();
  };

  /* The colour actually behind an element: its own background if it has one,
     otherwise the nearest painted ancestor.  A semi-transparent layer has to
     be blended, because the theme can set one and the raw pair would then
     be compared against a colour that is not on screen. */
  const parseColor = (value) => {
    const match = String(value || "").match(
      /^rgba?\\(\\s*([\\d.]+)[,\\s]+([\\d.]+)[,\\s]+([\\d.]+)(?:[,/\\s]+([\\d.%]+))?\\s*\\)$/i,
    );
    if (!match) return null;
    const alpha = match[4] === undefined
      ? 1
      : match[4].endsWith("%")
        ? parseFloat(match[4]) / 100
        : parseFloat(match[4]);
    return {
      r: parseFloat(match[1]),
      g: parseFloat(match[2]),
      b: parseFloat(match[3]),
      a: alpha,
    };
  };

  const flattenOver = (top, bottom) => {
    if (!top) return bottom;
    if (!bottom) return top;
    const a = top.a;
    return {
      r: top.r * a + bottom.r * (1 - a),
      g: top.g * a + bottom.g * (1 - a),
      b: top.b * a + bottom.b * (1 - a),
      a: 1,
    };
  };

  const backdropOf = (element) => {
    const layers = [];
    let node = element;
    while (node && node.nodeType === 1) {
      const color = parseColor(getComputedStyle(node).backgroundColor);
      if (color && color.a > 0) {
        layers.push(color);
        if (color.a === 1) break;
      }
      node = node.parentElement;
    }
    let painted = { r: 255, g: 255, b: 255, a: 1 };
    for (const layer of layers.reverse()) painted = flattenOver(layer, painted);
    return painted;
  };

  const channel = (value) => {
    const srgb = value / 255;
    return srgb <= 0.03928 ? srgb / 12.92 : Math.pow((srgb + 0.055) / 1.055, 2.4);
  };

  const luminance = (color) =>
    0.2126 * channel(color.r) + 0.7152 * channel(color.g) + 0.0722 * channel(color.b);

  const contrastRatio = (a, b) => {
    const first = luminance(a);
    const second = luminance(b);
    const lighter = Math.max(first, second);
    const darker = Math.min(first, second);
    return (lighter + 0.05) / (darker + 0.05);
  };

  const paints = (element) => {
    const style = getComputedStyle(element);
    if (style.display === "none" || style.visibility === "hidden") return false;
    if (Number(style.opacity) === 0) return false;
    const rect = element.getBoundingClientRect();
    return rect.width > 0 || rect.height > 0;
  };

  const sides = [
    ["Top", "borderTopColor", "borderTopWidth", "borderTopStyle"],
    ["Right", "borderRightColor", "borderRightWidth", "borderRightStyle"],
    ["Bottom", "borderBottomColor", "borderBottomWidth", "borderBottomStyle"],
    ["Left", "borderLeftColor", "borderLeftWidth", "borderLeftStyle"],
  ];

  const unreadableText = [];
  const invisibleBorders = [];
  const distinctColors = new Set();

  /* A decorative shape is not read, so a colour failure inside one is not
     a readability failure. */
  const decorative = (element) =>
    element.closest('[aria-hidden="true"]') !== null;

  /* WCAG 1.4.3 exempts a control the user cannot operate, so a dimmed
     disabled button is not an unreadable-text failure. */
  const disabledControl = (element) =>
    element.closest("button, a, input, select, textarea, fieldset")?.matches(
      ':disabled, [aria-disabled="true"]',
    ) === true;

  for (const element of root.querySelectorAll("*")) {
    if (!paints(element)) continue;
    const style = getComputedStyle(element);
    const backdrop = backdropOf(element);
    distinctColors.add(
      [backdrop.r, backdrop.g, backdrop.b].map(Math.round).join(","),
    );

    const holdsOwnText = Array.from(element.childNodes).some(
      (node) => node.nodeType === 3 && node.textContent.trim() !== "",
    );
    if (holdsOwnText) {
      const color = flattenOver(parseColor(style.color), backdrop);
      distinctColors.add([color.r, color.g, color.b].map(Math.round).join(","));
      const ratio = contrastRatio(color, backdrop);
      const fontSize = parseFloat(style.fontSize) || 0;
      const bold = Number(style.fontWeight) >= 700;
      const large =
        fontSize >= 24 || (fontSize >= 18.66 && bold) || (bold && fontSize >= 14);
      if (decorative(element) || disabledControl(element)) continue;
      unreadableText.push({
        selector: describe(element),
        color: style.color,
        background: "rgb(" + backdrop.r.toFixed(0) + ", " + backdrop.g.toFixed(0) + ", " + backdrop.b.toFixed(0) + ")",
        ratio: Math.round(ratio * 100) / 100,
        fontSize,
        large,
      });
    }

    for (const [side, colorKey, widthKey, styleKey] of sides) {
      const width = parseFloat(style[widthKey]) || 0;
      if (width <= 0 || style[styleKey] === "none") continue;
      const parsed = parseColor(style[colorKey]);
      if (!parsed || parsed.a <= 0) continue;
      /* A shape filled with the same colour it is outlined in is not
         missing a border: the fill is the boundary.  Only an outline that
         vanishes into what surrounds the element is invisible. */
      const borderColor = flattenOver(parsed, backdrop);
      const ownFill = parseColor(style.backgroundColor);
      if (ownFill && ownFill.a >= 1) {
        const filled = flattenOver(ownFill, backdrop);
        const matches =
          Math.abs(filled.r - borderColor.r) < 2 &&
          Math.abs(filled.g - borderColor.g) < 2 &&
          Math.abs(filled.b - borderColor.b) < 2;
        if (matches) continue;
      }
      distinctColors.add(
        [borderColor.r, borderColor.g, borderColor.b].map(Math.round).join(","),
      );
      if (decorative(element)) continue;
      invisibleBorders.push({
        selector: describe(element),
        side: side.toLowerCase(),
        width,
        color: style[colorKey],
        background: "rgb(" + backdrop.r.toFixed(0) + ", " + backdrop.g.toFixed(0) + ", " + backdrop.b.toFixed(0) + ")",
        ratio: Math.round(contrastRatio(borderColor, backdrop) * 100) / 100,
      });
    }
  }

  const bodyStyle = getComputedStyle(document.body);
  const rootStyle = getComputedStyle(root);
  return {
    themeAttribute: root.getAttribute("data-theme"),
    themePreference: root.getAttribute("data-theme-preference"),
    textSize: root.getAttribute("data-text-size"),
    pageBackground: bodyStyle.backgroundColor,
    pageColor: bodyStyle.color,
    rootBackground: rootStyle.backgroundColor,
    distinctColorCount: distinctColors.size,
    unreadableText,
    invisibleBorders,
  };
})()`;

function round2(value) {
  return Math.round(value * 100) / 100;
}

/* The verdicts, decided from a measurement alone so they can be tested with
   no browser present. */
/* The verdicts, decided from a measurement alone so they can be tested with
   no browser present.  Contrast *thresholds* belong to 25.9; this task finds
   the two failures it names: a border that paints nothing, and text a reader
   cannot make out. */
function analyseThemeMeasurement(
  measurement,
  {
    expectedTheme = null,
    minTextRatio = MIN_TEXT_CONTRAST_RATIO,
    minDistinctRatio = MIN_DISTINGUISHABLE_RATIO,
  } = {},
) {
  const findings = [];

  if (expectedTheme && measurement.themeAttribute !== expectedTheme) {
    findings.push({
      kind: "theme-not-applied",
      expected: expectedTheme,
      actual: measurement.themeAttribute ?? null,
    });
  }

  /* A border drawn in its own background colour is not a subtle border, it
     is an absent one: nothing reaches the screen to see. */
  for (const entry of measurement.invisibleBorders ?? []) {
    if (entry.ratio < minDistinctRatio) {
      findings.push({
        kind: "invisible-border",
        ...entry,
        minDistinctRatio,
      });
    }
  }

  /* Body text has to clear the published 4.5:1.  Large text is held to the
     same line here rather than relaxed, so a real failure cannot hide behind
     a size exemption. */
  for (const entry of measurement.unreadableText ?? []) {
    if (entry.ratio < minTextRatio) {
      findings.push({
        kind: "low-contrast-text",
        ...entry,
        minTextRatio,
      });
    }
  }

  const order = {
    "theme-not-applied": 0,
    "invisible-border": 1,
    "low-contrast-text": 2,
  };
  return findings.sort((a, b) => order[a.kind] - order[b.kind]);
}

function themeMeasurementIsClean(findings) {
  return findings.length === 0;
}

function describeThemeFinding(finding) {
  switch (finding.kind) {
    case "theme-not-applied":
      return `page reports data-theme="${finding.actual}" instead of "${finding.expected}"`;
    case "invisible-border":
      return (
        `${finding.selector} ${finding.side} border ${finding.width}px is ` +
        `${finding.color} on ${finding.background} (ratio ${finding.ratio})`
      );
    case "low-contrast-text":
      return (
        `${finding.selector} text ${finding.color} on ${finding.background} ` +
        `is ${finding.ratio}:1, under ${finding.minTextRatio}:1`
      );
    default:
      return JSON.stringify(finding);
  }
}

async function renderThemePage(session, url, width, theme) {
  await session.send("Page.enable");
  await session.send("Runtime.enable");
  await session.send("Emulation.setDeviceMetricsOverride", {
    width,
    height: VIEWPORT_HEIGHT,
    deviceScaleFactor: 1,
    mobile: false,
  });

  /* prefers-color-scheme is what the "system" preference reads, and setting
     it keeps the render honest whichever way a page resolves its theme. */
  await session.send("Emulation.setEmulatedMedia", {
    features: [
      { name: "prefers-color-scheme", value: theme === "dark" ? "dark" : "light" },
    ],
  });

  /* The stored preference is set before the document script runs, so
     preferences.js loads already holding the theme.  Without this the page
     would render its default and the dark set would be a second light set. */
  await session.send("Page.addScriptToEvaluateOnNewDocument", {
    source:
      "try { window.localStorage.setItem(" +
      JSON.stringify(PREFERENCE_STORAGE_KEY) +
      ", JSON.stringify({ theme: " +
      JSON.stringify(theme) +
      ', textSize: "default" })); } catch (error) {}',
  });

  await navigateAndSettle(session, url, PAGE_SETTLE_MS);

  const evaluated = await session.send("Runtime.evaluate", {
    expression: MEASURE_THEME,
    returnByValue: true,
  });
  const { png, contentHeight } = await capturePage(
    session,
    width,
    MAX_CAPTURE_HEIGHT,
  );
  return {
    measurement: evaluated.result.value,
    png,
    contentHeight,
  };
}

function themeReportEntry(theme, pageName, result, screenshotName) {
  const findings = analyseThemeMeasurement(result.measurement, {
    expectedTheme: theme,
  });
  return {
    theme,
    pageName,
    screenshotName,
    clean: themeMeasurementIsClean(findings),
    contentHeight: result.contentHeight,
    findings,
  };
}

/* One row per page.  A page whose page background is the same colour in
   both themes is called out by name: that is the shape a dark theme that
   never applied takes, and a picture alone cannot tell it from a real one. */
function summariseThemes(entries) {
  const themes = [...new Set(entries.map((entry) => entry.theme))];
  const pages = [...new Set(entries.map((entry) => entry.pageName))];

  return pages.map((pageName) => {
    const rows = entries.filter((entry) => entry.pageName === pageName);
    const backgrounds = themes.map(
      (theme) =>
        rows.find((candidate) => candidate.theme === theme)?.measurement
          ?.pageBackground ?? null,
    );
    return {
      pageName,
      clean: rows.every((entry) => entry.clean),
      findings: rows.reduce((total, entry) => total + entry.findings.length, 0),
      distinctBackgrounds: new Set(backgrounds).size,
      sameBackgroundInEveryTheme:
        themes.length > 1 && new Set(backgrounds).size === 1,
    };
  });
}

function writeThemeReport(entries, directory) {
  const themes = [...new Set(entries.map((entry) => entry.theme))];
  const summary = summariseThemes(entries);
  const lines = [];

  lines.push("# Theme render set");
  lines.push("");
  lines.push(
    `Rendered ${summary.length} pages in the ${themes.join(" and ")} theme at`,
    `${THEME_WIDTH} CSS pixels in a real Chromium browser. Produced by`,
    "`npm run theme-shots` in `frontend/`.",
    "",
  );

  lines.push("| theme | pages | clean pages | findings |");
  lines.push("| --- | --- | --- | --- |");
  for (const theme of themes) {
    const rows = entries.filter((entry) => entry.theme === theme);
    const clean = rows.filter((entry) => entry.clean).length;
    const findings = rows.reduce((total, entry) => total + entry.findings.length, 0);
    lines.push(`| ${theme} | ${rows.length} | ${clean} | ${findings} |`);
  }
  lines.push("");

  lines.push("## Per page");
  lines.push("");
  for (const row of summary) {
    lines.push(`### ${row.pageName}`);
    lines.push("");
    lines.push(`| theme | page background | distinct colours | verdict |`);
    lines.push(`| --- | --- | --- | --- |`);
    for (const theme of themes) {
      const entry = entries.find(
        (candidate) =>
          candidate.pageName === row.pageName && candidate.theme === theme,
      );
      if (!entry) continue;
      const verdict = entry.clean
        ? "no unreadable text or invisible border"
        : entry.findings.map(describeThemeFinding).join("; ");
      lines.push(
        `| ${theme} | ${entry.measurement?.pageBackground ?? "?"} | ` +
          `${entry.measurement?.distinctColorCount ?? "?"} | ${verdict} |`,
      );
    }
    lines.push("");
    lines.push(`- screenshot: ${themes
      .map(
        (theme) =>
          entries.find(
            (candidate) =>
              candidate.pageName === row.pageName && candidate.theme === theme,
          )?.screenshotName ?? "",
      )
      .filter(Boolean)
      .join(", ")}`);
    if (row.sameBackgroundInEveryTheme) {
      lines.push(
        "- every theme painted the same page background: the theme did not",
        "  change what reached the screen on this page",
      );
    }
    lines.push("");
  }

  fs.writeFileSync(path.join(directory, "README.md"), lines.join("\n"), "utf8");
}

async function renderAllThemes({
  pages = null,
  themes = THEMES,
  width = THEME_WIDTH,
  outputDirectory = themeShotsDirectory(),
  browserExecutable = null,
} = {}) {
  const executable = browserExecutable || findBrowserExecutable();
  const userDataDirectory = makeUserDataDirectory();
  const { port, outputDirectory: built, server } = await startPreviewServer();
  const pageNames = pages ?? previewPageNames(built);
  const child = launchBrowser(executable, userDataDirectory);
  const entries = [];

  fs.mkdirSync(outputDirectory, { recursive: true });
  try {
    const devToolsPort = await waitForDevToolsPort(
      userDataDirectory,
      BROWSER_START_TIMEOUT_MS,
    );
    const session = await connectToTarget(devToolsPort);
    try {
      for (const theme of themes) {
        const themeDirectory = path.join(outputDirectory, theme);
        fs.mkdirSync(themeDirectory, { recursive: true });
        for (const pageName of pageNames) {
          const url = `${previewUrl(port)}${pageName}`;
          const result = await renderThemePage(session, url, width, theme);
          const consoleErrors = collectConsoleErrors(session);
          const screenshotName = `${theme}/${pageName.replace(/\.html$/, "")}.png`;
          fs.writeFileSync(
            path.join(outputDirectory, screenshotName),
            result.png,
          );
          const entry = themeReportEntry(theme, pageName, result, screenshotName);
          entry.measurement = result.measurement;
          entry.consoleErrors = consoleErrors.slice();
          entries.push(entry);
        }
      }
    } finally {
      session.close();
    }
  } finally {
    child.kill();
    await new Promise((resolve) => server.close(resolve));
    server.closeAllConnections();
    removeUserDataDirectory(userDataDirectory);
  }

  writeThemeReport(entries, outputDirectory);
  return entries;
}

module.exports = {
  MEASURE_THEME,
  MIN_DISTINGUISHABLE_RATIO,
  MIN_TEXT_CONTRAST_RATIO,
  THEMES,
  THEME_WIDTH,
  analyseThemeMeasurement,
  describeThemeFinding,
  renderAllThemes,
  summariseThemes,
  themeMeasurementIsClean,
  themeReportEntry,
  themeShotsDirectory,
  writeThemeReport,
};

if (require.main === module) {
  renderAllThemes().then(
    (entries) => {
      const dirty = entries.filter((entry) => !entry.clean).length;
      const summary = summariseThemes(entries);
      const identical = summary.filter((row) => row.sameBackgroundInEveryTheme);
      console.log(
        `Wrote ${entries.length} screenshots to ${themeShotsDirectory()} ` +
          `(${entries.length - dirty} clean, ${dirty} with findings).`,
      );
      for (const entry of entries.filter((candidate) => !candidate.clean)) {
        console.log(
          `  ${entry.pageName} [${entry.theme}]: ` +
            entry.findings.map(describeThemeFinding).join("; "),
        );
      }
      if (identical.length > 0) {
        console.log(
          `  ${identical.length} page(s) painted one background across both themes: ` +
            identical.map((row) => row.pageName).join(", "),
        );
        process.exitCode = 1;
      }
      if (dirty > 0) {
        process.exitCode = 1;
      }
    },
    (error) => {
      console.error(error.message);
      process.exitCode = 1;
    },
  );
}
