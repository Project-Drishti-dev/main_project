const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawn } = require("node:child_process");

const { previewPageNames, previewUrl, startPreviewServer } = require("./preview.cjs");

/* D210: renders every built page at four CSS widths in a real browser,
   measures what the render looks like, and writes the pictures out.  The
   measurement is the evidence; a screenshot alone cannot be read for a
   one-pixel overflow. */

const VIEWPORT_WIDTHS = [320, 768, 1024, 1440];
const VIEWPORT_HEIGHT = 900;
const MAX_CAPTURE_HEIGHT = 20000;
const OVERFLOW_TOLERANCE_PX = 1;
const MIN_READABLE_FONT_PX = 10;
const MAX_CONSOLE_ERRORS = 5;
const PAGE_SETTLE_MS = 600;
const BROWSER_START_TIMEOUT_MS = 30000;

const BROWSER_CANDIDATES = [
  process.env.DRISHTI_BROWSER,
  "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
];

function repositoryRoot() {
  return path.resolve(__dirname, "..", "..");
}

/* A directory .gitignore does not swallow: 'screenshots/' is ignored at every
   depth, so the width sets would never be committable under that name. */
function shotsDirectory() {
  return path.resolve(
    process.env.DRISHTI_SHOTS_DIR ||
      path.join(repositoryRoot(), "docs", "viewport-shots"),
  );
}

/* The first browser that exists on this machine, or a thrown name: a run that
   silently rendered nothing is the failure this task exists to prevent. */
function findBrowserExecutable(candidates = BROWSER_CANDIDATES) {
  for (const candidate of candidates) {
    if (candidate && fs.existsSync(candidate)) {
      return candidate;
    }
  }
  throw new Error(
    "no browser found; set DRISHTI_BROWSER to a Chromium executable",
  );
}

/* Reads the port the browser actually bound: port 0 asks the OS, so the
   number in the file is the only correct one. */
function readDevToolsPort(userDataDirectory) {
  const portFile = path.join(userDataDirectory, "DevToolsActivePort");
  const lines = fs.readFileSync(portFile, "utf8").split(/\r?\n/);
  const port = Number(lines[0]);
  if (!Number.isInteger(port) || port <= 0) {
    throw new Error(`browser wrote no usable port to ${portFile}`);
  }
  return port;
}

async function waitForDevToolsPort(userDataDirectory, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      return readDevToolsPort(userDataDirectory);
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
  }
  throw new Error(`browser reported no DevTools port within ${timeoutMs}ms`);
}

/* One CDP connection, request/response by id and events to listeners.  Kept
   here rather than pulled in as a dependency: the browser is already on the
   machine and node ships a WebSocket. */
class DevToolsSession {
  constructor(socket) {
    this.socket = socket;
    this.nextId = 1;
    this.pending = new Map();
    this.listeners = [];
    socket.addEventListener("message", (event) => {
      const message = JSON.parse(event.data);
      if (message.id && this.pending.has(message.id)) {
        const { resolve, reject } = this.pending.get(message.id);
        this.pending.delete(message.id);
        if (message.error) {
          reject(new Error(message.error.message));
        } else {
          resolve(message.result);
        }
        return;
      }
      for (const listener of this.listeners) {
        listener(message);
      }
    });
  }

  send(method, params = {}) {
    const id = this.nextId++;
    this.socket.send(JSON.stringify({ id, method, params }));
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
    });
  }

  on(listener) {
    this.listeners.push(listener);
  }

  once(method) {
    return new Promise((resolve) => {
      this.on((message) => {
        if (message.method === method) {
          resolve(message.params);
        }
      });
    });
  }

  close() {
    this.socket.close();
  }
}

async function connectToTarget(port) {
  const response = await fetch(`http://127.0.0.1:${port}/json/list`);
  const targets = await response.json();
  const page = targets.find((target) => target.type === "page");
  if (!page) {
    throw new Error("browser exposed no page target");
  }
  const socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    socket.addEventListener("open", resolve, { once: true });
    socket.addEventListener("error", () => {
      reject(new Error("DevTools socket refused"));
    }, { once: true });
  });
  return new DevToolsSession(socket);
}
/* The script the page runs.  It reports what it painted rather than what the
   markup says, so a stylesheet that loses a width is caught here and not in
   a review. */
const MEASURE_PAGE = `(() => {
  const root = document.documentElement;
  const viewportWidth = root.clientWidth;

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

  const paints = (element) => {
    const style = getComputedStyle(element);
    if (style.display === "none" || style.visibility === "hidden") return false;
    if (Number(style.opacity) === 0) return false;
    const rect = element.getBoundingClientRect();
    return rect.width > 0 || rect.height > 0;
  };

  /* An element inside a clipping box cannot widen the page, so it is not the
     cause of a page-level overflow and is left to the clipped-text check. */
  const clippedByAncestor = (element) => {
    let parent = element.parentElement;
    while (parent && parent !== root) {
      const style = getComputedStyle(parent);
      if (style.overflowX === "hidden" || style.overflowX === "clip") return true;
      parent = parent.parentElement;
    }
    return false;
  };

  const overflowing = [];
  const smallText = [];
  const clippedText = [];

  for (const element of root.querySelectorAll("*")) {
    if (!paints(element)) continue;
    const rect = element.getBoundingClientRect();
    if ((rect.right > viewportWidth + 1 || rect.left < -1) && !clippedByAncestor(element)) {
      overflowing.push({
        selector: describe(element),
        left: Math.round(rect.left),
        right: Math.round(rect.right),
      });
    }

    const style = getComputedStyle(element);
    const fontSize = parseFloat(style.fontSize) || 0;
    const holdsOwnText = Array.from(element.childNodes).some(
      (node) => node.nodeType === 3 && node.textContent.trim() !== "",
    );
    if (holdsOwnText) {
      if (fontSize > 0 && fontSize < ${MIN_READABLE_FONT_PX}) {
        smallText.push({ selector: describe(element), fontSize });
      }
      if (
        (style.overflowX === "hidden" || style.overflowX === "clip") &&
        element.clientWidth > 1 && element.clientHeight > 1 &&
        element.scrollWidth > element.clientWidth + 1
      ) {
        clippedText.push({
          selector: describe(element),
          clientWidth: element.clientWidth,
          scrollWidth: element.scrollWidth,
        });
      }
    }
  }

  return {
    viewportWidth,
    scrollWidth: root.scrollWidth,
    overflowPx: root.scrollWidth - viewportWidth,
    overflowing,
    smallText,
    clippedText,
  };
})()`;

/* Everything the harness decides, decided from a measurement alone, so the
   verdicts can be tested without a browser. */
function analyseMeasurement(
  measurement,
  { tolerancePx = OVERFLOW_TOLERANCE_PX, minFontPx = MIN_READABLE_FONT_PX } = {},
) {
  const findings = [];
  const overflowPx = measurement.overflowPx ?? 0;

  if (overflowPx > tolerancePx) {
    findings.push({
      kind: "page-overflow",
      overflowPx,
      viewportWidth: measurement.viewportWidth,
    });
  }
  for (const element of measurement.overflowing ?? []) {
    findings.push({ kind: "element-overflow", ...element });
  }
  for (const element of measurement.smallText ?? []) {
    findings.push({ kind: "small-text", ...element, minFontPx });
  }
  for (const element of measurement.clippedText ?? []) {
    findings.push({ kind: "clipped-text", ...element });
  }

  const order = {
    "page-overflow": 0,
    "element-overflow": 1,
    "clipped-text": 2,
    "small-text": 3,
  };
  return findings.sort((a, b) => order[a.kind] - order[b.kind]);
}

function measurementIsClean(findings) {
  return findings.length === 0;
}

/* Launches a headless browser on a throwaway profile: a real user profile
   carries extensions and a saved window size that would change the render. */
/* A killed browser can still be holding its profile, so the throwaway profile
   is removed by name and a lock is not allowed to fail the run. */
function removeUserDataDirectory(userDataDirectory) {
  try {
    fs.rmSync(userDataDirectory, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
  } catch {
    /* The directory is under the system temp directory and is named per run. */
  }
}

function launchBrowser(executable, userDataDirectory) {
  return spawn(
    executable,
    [
      "--headless=new",
      "--disable-gpu",
      "--hide-scrollbars",
      "--no-first-run",
      "--no-default-browser-check",
      "--disable-extensions",
      `--user-data-dir=${userDataDirectory}`,
      "--remote-debugging-port=0",
      "about:blank",
    ],
    { stdio: "ignore" },
  );
}
async function renderPage(session, url, width) {
  const consoleErrors = [];
  session.on((message) => {
    if (message.method !== "Runtime.exceptionThrown") {
      return;
    }
    const details = message.params?.exceptionDetails;
    const text = details?.exception?.description || details?.text || "";
    if (text && consoleErrors.length < MAX_CONSOLE_ERRORS) {
      consoleErrors.push(text.split("\n")[0].slice(0, 200));
    }
  });

  await session.send("Page.enable");
  await session.send("Runtime.enable");
  await session.send("Emulation.setDeviceMetricsOverride", {
    width,
    height: VIEWPORT_HEIGHT,
    deviceScaleFactor: 1,
    mobile: false,
  });
  const loaded = session.once("Page.loadEventFired");
  await session.send("Page.navigate", { url });
  await loaded;
  await new Promise((resolve) => setTimeout(resolve, PAGE_SETTLE_MS));

  const evaluated = await session.send("Runtime.evaluate", {
    expression: MEASURE_PAGE,
    returnByValue: true,
  });
  const metrics = await session.send("Page.getLayoutMetrics");
  const contentHeight = Math.min(
    Math.ceil(metrics.cssContentSize?.height ?? VIEWPORT_HEIGHT),
    MAX_CAPTURE_HEIGHT,
  );
  const capture = await session.send("Page.captureScreenshot", {
    format: "png",
    captureBeyondViewport: true,
    fromSurface: true,
    clip: { x: 0, y: 0, width, height: contentHeight, scale: 1 },
  });

  return {
    measurement: evaluated.result.value,
    png: Buffer.from(capture.data, "base64"),
    contentHeight,
    consoleErrors,
  };
}

/* One row per page and width: the picture, what it measured, what that means
   and whether the page logged anything. */
function reportEntry(pageName, width, result, screenshotName) {
  const findings = analyseMeasurement(result.measurement);
  return {
    pageName,
    width,
    screenshotName,
    clean: measurementIsClean(findings),
    contentHeight: result.contentHeight,
    consoleErrors: result.consoleErrors,
    findings,
  };
}

function describeFinding(finding) {
  switch (finding.kind) {
    case "page-overflow":
      return `page scrolls ${finding.overflowPx}px sideways at ${finding.viewportWidth}px`;
    case "element-overflow":
      return `${finding.selector} reaches x=${finding.right}px`;
    case "clipped-text":
      return `${finding.selector} clips ${finding.scrollWidth}px of text into ${finding.clientWidth}px`;
    case "small-text":
      return `${finding.selector} renders text at ${finding.fontSize}px`;
    default:
      return JSON.stringify(finding);
  }
}

function writeReport(entries, directory) {
  const widths = [...new Set(entries.map((entry) => entry.width))].sort((a, b) => a - b);
  const pages = [...new Set(entries.map((entry) => entry.pageName))];
  const lines = [];

  lines.push("# Viewport render set");
  lines.push("");
  lines.push(
    `Rendered ${pages.length} pages at ${widths.join(", ")} CSS pixels in a real`,
    "Chromium browser. Produced by `npm run shots` in `frontend/`.",
    "",
  );

  lines.push("| width | pages | clean pages | findings |");
  lines.push("| --- | --- | --- | --- |");
  for (const width of widths) {
    const rows = entries.filter((entry) => entry.width === width);
    const clean = rows.filter((entry) => entry.clean).length;
    const findings = rows.reduce((total, entry) => total + entry.findings.length, 0);
    lines.push(`| ${width} | ${rows.length} | ${clean} | ${findings} |`);
  }
  lines.push("");

  lines.push("## Per page");
  lines.push("");
  for (const pageName of pages) {
    lines.push(`### ${pageName}`);
    lines.push("");
    for (const width of widths) {
      const entry = entries.find(
        (candidate) => candidate.pageName === pageName && candidate.width === width,
      );
      if (!entry) {
        continue;
      }
      const verdict = entry.clean
        ? "no overflow, clipping or small text"
        : entry.findings.map(describeFinding).join("; ");
      lines.push(`- ${width}px - ${entry.screenshotName} - ${verdict}`);
    }
    lines.push("");
  }

  const errors = entries.filter((entry) => entry.consoleErrors.length > 0);
  lines.push("## Console");
  lines.push("");
  if (errors.length === 0) {
    lines.push("No page threw at any width.");
  } else {
    for (const entry of errors) {
      lines.push(`- ${entry.pageName} at ${entry.width}px: ${entry.consoleErrors.join(" | ")}`);
    }
  }
  lines.push("");

  fs.writeFileSync(path.join(directory, "README.md"), lines.join("\n"), "utf8");
}

async function renderAll({
  pages = null,
  widths = VIEWPORT_WIDTHS,
  outputDirectory = shotsDirectory(),
  browserExecutable = null,
} = {}) {
  const executable = browserExecutable || findBrowserExecutable();
  const userDataDirectory = fs.mkdtempSync(path.join(os.tmpdir(), "drishti-shots-"));
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
      for (const width of widths) {
        const widthDirectory = path.join(outputDirectory, String(width));
        fs.mkdirSync(widthDirectory, { recursive: true });
        for (const pageName of pageNames) {
          const url = `${previewUrl(port)}${pageName}`;
          const result = await renderPage(session, url, width);
          const screenshotName = `${width}/${pageName.replace(/\.html$/, "")}.png`;
          fs.writeFileSync(path.join(outputDirectory, screenshotName), result.png);
          entries.push(reportEntry(pageName, width, result, screenshotName));
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

  writeReport(entries, outputDirectory);
  return entries;
}

module.exports = {
  MEASURE_PAGE,
  MIN_READABLE_FONT_PX,
  OVERFLOW_TOLERANCE_PX,
  VIEWPORT_WIDTHS,
  analyseMeasurement,
  describeFinding,
  findBrowserExecutable,
  measurementIsClean,
  removeUserDataDirectory,
  readDevToolsPort,
  renderAll,
  reportEntry,
  shotsDirectory,
  writeReport,
};

if (require.main === module) {
  renderAll().then(
    (entries) => {
      const dirty = entries.filter((entry) => !entry.clean).length;
      console.log(
        `Wrote ${entries.length} screenshots to ${shotsDirectory()} ` +
          `(${entries.length - dirty} clean, ${dirty} with findings).`,
      );
      for (const entry of entries.filter((candidate) => !candidate.clean)) {
        console.log(
          `  ${entry.pageName} @${entry.width}: ` +
            entry.findings.map(describeFinding).join("; "),
        );
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