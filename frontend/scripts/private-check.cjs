const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const {
  BROWSER_START_TIMEOUT_MS,
  collectConsoleErrors,
  connectToBrowser,
  findBrowserExecutable,
  launchBrowser,
  makeUserDataDirectory,
  removeUserDataDirectory,
  stopBrowser,
  waitForDevToolsPort,
} = require("./browser-capture.cjs");
const { previewUrl, startPreviewServer } = require("./preview.cjs");

/* D212: a previewed file and a submitted file look the same in the source, and
   a browser that refuses storage refuses it by throwing rather than by saying
   so.  Both answers are read out of a real off-the-record browser context. */

const PAGE_NAME = "home.html";
const UPLOAD_ENDPOINT_FRAGMENTS = ["/api/analyze", "/api/screenings"];
const PREFERENCES_KEY = "drishti.preferences.v1";
const PAGE_SETTLE_MS = 800;
const PREVIEW_TIMEOUT_MS = 8000;

/* A 1x1 PNG in the throwaway run directory.  The run needs a file the browser
   really decodes, and an officer's image must never reach a log. */
const SYNTHETIC_PNG =
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFAAH/q842iQAAAABJRU5ErkJggg==";

function repositoryRoot() {
  return path.resolve(__dirname, "..", "..");
}

function privateCheckDirectory() {
  return path.resolve(
    process.env.DRISHTI_PRIVATE_CHECK_DIR ||
      path.join(repositoryRoot(), "docs", "private-check"),
  );
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function writeSyntheticImage(directory) {
  fs.mkdirSync(directory, { recursive: true });
  const file = path.join(directory, "synthetic-document.png");
  fs.writeFileSync(file, Buffer.from(SYNTHETIC_PNG, "base64"));
  return file;
}

/* The page-side probe.  A frame sandboxed without allow-same-origin has an
   opaque origin, so reading localStorage inside it raises SecurityError in the
   browser itself rather than being stubbed to look unavailable.  preferences.js
   is inlined so a script that failed to load cannot be read as a storage
   failure. */
function storageProbeSource(preferencesSource) {
  return `(() => new Promise((resolve) => {
  const body =
    '<!doctype html><meta charset="utf-8">' +
    '<script>' + ${JSON.stringify(preferencesSource)} + '<\/script>' +
    '<script>' +
    'var readable = true; var error = null;' +
    'try { window.localStorage.getItem("probe"); }' +
    'catch (failure) { readable = false; error = failure.name; }' +
    'var api = window.DRISHTI_PREFERENCES;' +
    'var root = document.documentElement;' +
    'var wroteTheme = null; var writeError = null;' +
    'try {' +
    '  api.set({ theme: "dark" }); wroteTheme = root.getAttribute("data-theme");' +
    '} catch (failure) { writeError = failure.name; }' +
    'parent.postMessage({' +
    '  kind: "storage-probe",' +
    '  readable: readable,' +
    '  error: error,' +
    '  preferencesLoaded: !!api && typeof api.read === "function",' +
    '  themePreference: root.getAttribute("data-theme-preference"),' +
    '  wroteTheme: wroteTheme,' +
    '  writeError: writeError' +
    '}, "*");' +
    '<\/script>';
  const frame = document.createElement("iframe");
  frame.setAttribute("sandbox", "allow-scripts");
  frame.style.display = "none";
  frame.srcdoc = body;
  const timer = setTimeout(function () {
    resolve({ kind: "storage-probe", readable: null, error: "probe-timed-out" });
  }, 5000);
  window.addEventListener("message", function (event) {
    if (!event.data || event.data.kind !== "storage-probe") return;
    clearTimeout(timer);
    resolve(event.data);
  });
  document.body.appendChild(frame);
}))()`;
}

const READ_PAGE_PREFERENCES = `(() => {
  const api = window.DRISHTI_PREFERENCES;
  const root = document.documentElement;
  let storageReadable = false;
  let storageError = null;
  try {
    window.localStorage.setItem("drishti.private-check", "1");
    window.localStorage.removeItem("drishti.private-check");
    storageReadable = true;
  } catch (failure) {
    storageError = failure.name;
  }
  return {
    loaded: !!api && typeof api.read === "function",
    theme: root.getAttribute("data-theme"),
    textSize: root.getAttribute("data-text-size"),
    themePreference: root.getAttribute("data-theme-preference"),
    storageReadable: storageReadable,
    storageError: storageError,
  };
})()`;

function countUploadRequests(requests) {
  return requests.filter((request) =>
    UPLOAD_ENDPOINT_FRAGMENTS.some((fragment) => request.url.includes(fragment)),
  );
}

/* The verdicts, over a run that has already happened.  Kept apart from the
   browser so they can be tested without one. */
function analysePrivateCheck(run) {
  const findings = [];
  const page = run.preferences || {};
  const blocked = run.blockedStorage || {};
  const upload = run.upload || {};

  if (run.privateContext !== true) {
    findings.push({ kind: "not-private-context" });
  }
  if (page.loaded !== true) {
    findings.push({ kind: "preferences-missing" });
  }
  if (page.theme !== "light") {
    findings.push({ kind: "theme-not-defaulted", theme: page.theme ?? null });
  }
  if (upload.previewRendered !== true) {
    findings.push({ kind: "preview-not-rendered" });
  }
  if (upload.requestsAfterSelection > 0) {
    findings.push({
      kind: "upload-before-submit",
      count: upload.requestsAfterSelection,
    });
  }
  if (upload.requestsAfterSubmit < 1) {
    findings.push({ kind: "no-upload-on-submit" });
  }
  if (blocked.readable !== false) {
    findings.push({ kind: "storage-not-blocked", error: blocked.error ?? null });
  }
  if (blocked.preferencesLoaded !== true) {
    findings.push({ kind: "preferences-missing-without-storage" });
  }
  if (blocked.writeError !== null && blocked.writeError !== undefined) {
    findings.push({ kind: "preferences-write-threw", error: blocked.writeError });
  }
  if (blocked.wroteTheme !== "dark") {
    findings.push({
      kind: "preferences-write-not-applied",
      theme: blocked.wroteTheme ?? null,
    });
  }
  for (const error of run.consoleErrors || []) {
    findings.push({ kind: "console-error", error });
  }
  return findings;
}

function describePrivateCheckFinding(finding) {
  switch (finding.kind) {
    case "not-private-context":
      return "the page ran in an ordinary browser context, not a private one";
    case "preferences-missing":
      return "preferences.js published no DRISHTI_PREFERENCES on the page";
    case "theme-not-defaulted":
      return "the page did not start on the light theme (was " + (finding.theme ?? "none") + ")";
    case "preview-not-rendered":
      return "the chosen file never rendered a preview, so the submit button stayed disabled";
    case "upload-before-submit":
      return finding.count + " upload request(s) left the page before the button was clicked";
    case "no-upload-on-submit":
      return "no upload request left the page when the button was clicked";
    case "storage-not-blocked":
      return "the opaque-origin frame still allowed localStorage, so the denied path was never exercised";
    case "preferences-missing-without-storage":
      return "preferences.js did not load in a frame whose localStorage throws";
    case "preferences-write-threw":
      return "writing a preference threw without localStorage (" + finding.error + ")";
    case "preferences-write-not-applied":
      return "a preference written without localStorage did not reach the document (theme was " + (finding.theme ?? "none") + ")";
    case "console-error":
      return "uncaught error in the console: " + finding.error;
    default:
      return "unrecognised finding: " + finding.kind;
  }
}

function privateCheckIsClean(findings) {
  return findings.length === 0;
}

function summarisePrivateCheck(run) {
  return {
    privateContext: run.privateContext === true,
    pageName: run.pageName,
    requestsAfterSelection: run.upload.requestsAfterSelection,
    requestsAfterSubmit: run.upload.requestsAfterSubmit,
    storageReadable: run.preferences.storageReadable,
    blockedStorageError: run.blockedStorage.error ?? null,
    consoleErrors: (run.consoleErrors || []).length,
  };
}

function writePrivateCheckReport(run, findings, directory) {
  const upload = run.upload;
  const blocked = run.blockedStorage;
  const page = run.preferences;
  const lines = [];

  lines.push("# Private-browsing check");
  lines.push("");
  lines.push(
    `Opened ${run.pageName} in a private (off-the-record) Chromium context and read`,
    "back what the browser actually did. Produced by `npm run private-check` in",
    "`frontend/`.",
    "",
    "| check | answer |",
    "| --- | --- |",
    `| private browser context | ${run.privateContext === true ? "yes" : "no"} |`,
    `| localStorage on the page | ${page.storageReadable ? "available" : "unavailable (" + page.storageError + ")"} |`,
    `| upload requests after choosing a file | ${upload.requestsAfterSelection} |`,
    `| upload requests after clicking submit | ${upload.requestsAfterSubmit} |`,
    `| localStorage in the opaque-origin frame | ${blocked.readable === false ? "refused with " + blocked.error : "still readable"} |`,
    `| preferences loaded without localStorage | ${blocked.preferencesLoaded === true ? "yes" : "no"} |`,
    `| theme written without localStorage | ${blocked.wroteTheme ?? "none"} |`,
    `| uncaught console errors | ${(run.consoleErrors || []).length} |`,
    "",
  );

  lines.push(
    findings.length === 0
      ? "## Verdict"
      : "## Findings",
  );
  lines.push("");
  if (findings.length === 0) {
    lines.push(
      "Nothing to report: choosing a file sent nothing, clicking submit sent one",
      "request, and preferences.js loaded and wrote with localStorage unavailable.",
    );
  } else {
    for (const finding of findings) {
      lines.push(`- ${describePrivateCheckFinding(finding)}`);
    }
  }
  lines.push("");

  fs.writeFileSync(path.join(directory, "README.md"), lines.join("\n"), "utf8");
}

async function evaluateInPage(browser, sessionId, expression, awaitPromise = false) {
  const result = await browser.sendIn(
    "Runtime.evaluate",
    { expression, awaitPromise, returnByValue: true },
    sessionId,
  );
  if (result.exceptionDetails) {
    const details = result.exceptionDetails;
    throw new Error(details.exception?.description || details.text || "evaluation failed");
  }
  return result.result.value;
}

async function waitForPageState(browser, sessionId, expression, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await evaluateInPage(browser, sessionId, expression)) {
      return true;
    }
    await sleep(100);
  }
  return false;
}

async function runPrivateCheck({
  outputDirectory = privateCheckDirectory(),
  browserExecutable = null,
} = {}) {
  const executable = browserExecutable || findBrowserExecutable();
  const userDataDirectory = makeUserDataDirectory();
  const runDirectory = fs.mkdtempSync(path.join(os.tmpdir(), "drishti-private-"));
  const { port, outputDirectory: built, server } = await startPreviewServer();
  const child = launchBrowser(executable, userDataDirectory, ["--incognito"]);
  const run = {
    pageName: PAGE_NAME,
    privateContext: false,
    preferences: {},
    blockedStorage: {},
    upload: {},
    consoleErrors: [],
  };

  fs.mkdirSync(outputDirectory, { recursive: true });
  try {
    const devToolsPort = await waitForDevToolsPort(
      userDataDirectory,
      BROWSER_START_TIMEOUT_MS,
    );
    const browser = await connectToBrowser(devToolsPort);
    try {
      const requests = [];
      const consoleErrors = collectConsoleErrors(browser);
      browser.on((message) => {
        if (message.method !== "Network.requestWillBeSent") return;
        requests.push({
          method: message.params.request.method,
          url: message.params.request.url,
        });
      });

      const { browserContextId } = await browser.send(
        "Target.createBrowserContext",
        { disposeOnDetach: false },
      );
      const { targetId } = await browser.send("Target.createTarget", {
        url: "about:blank",
        browserContextId,
      });
      const { sessionId } = await browser.send("Target.attachToTarget", {
        targetId,
        flatten: true,
      });
      run.privateContext = typeof browserContextId === "string";

      for (const domain of ["Page", "Runtime", "Network", "DOM"]) {
        await browser.sendIn(`${domain}.enable`, {}, sessionId);
      }

      const loaded = browser.once("Page.loadEventFired");
      await browser.sendIn(
        "Page.navigate",
        { url: `${previewUrl(port)}${PAGE_NAME}` },
        sessionId,
      );
      await loaded;
      await sleep(PAGE_SETTLE_MS);

      run.preferences = await evaluateInPage(
        browser,
        sessionId,
        READ_PAGE_PREFERENCES,
      );

      const { root } = await browser.sendIn(
        "DOM.getDocument",
        { depth: -1 },
        sessionId,
      );
      const { nodeId } = await browser.sendIn(
        "DOM.querySelector",
        { nodeId: root.nodeId, selector: "#screening-file" },
        sessionId,
      );
      if (!nodeId) {
        throw new Error(`${PAGE_NAME} carries no #screening-file input`);
      }
      await browser.sendIn(
        "DOM.setFileInputFiles",
        { files: [writeSyntheticImage(runDirectory)], nodeId },
        sessionId,
      );
      await sleep(PAGE_SETTLE_MS);

      const previewRendered = await waitForPageState(
        browser,
        sessionId,
        "!document.getElementById('run-screening').disabled",
        PREVIEW_TIMEOUT_MS,
      );
      const requestsAfterSelection = countUploadRequests(requests);

      if (previewRendered) {
        await browser.sendIn(
          "Runtime.evaluate",
          { expression: "document.getElementById('run-screening').click()" },
          sessionId,
        );
        await sleep(PAGE_SETTLE_MS * 2);
      }
      const requestsAfterSubmit = countUploadRequests(requests);

      const preferencesSource = fs.readFileSync(
        path.join(built, "preferences.js"),
        "utf8",
      );
      run.blockedStorage = await evaluateInPage(
        browser,
        sessionId,
        storageProbeSource(preferencesSource),
        true,
      );

      run.upload = {
        previewRendered,
        requestsAfterSelection: requestsAfterSelection.length,
        requestsAfterSubmit: requestsAfterSubmit.length,
        requestsAfterSubmitUrls: requestsAfterSubmit.map(
          (request) => request.method + " " + request.url,
        ),
        requestsBeforeSubmitUrls: requestsAfterSelection.map(
          (request) => request.method + " " + request.url,
        ),
        totalRequests: requests.length,
      };
      run.consoleErrors = consoleErrors.slice();
    } finally {
      browser.close();
    }
  } finally {
    stopBrowser(child, userDataDirectory);
    await new Promise((resolve) => server.close(resolve));
    server.closeAllConnections();
    removeUserDataDirectory(userDataDirectory);
    try {
      fs.rmSync(runDirectory, { recursive: true, force: true, maxRetries: 5 });
    } catch {
      /* The run directory is under the system temp directory. */
    }
  }

  const findings = analysePrivateCheck(run);
  writePrivateCheckReport(run, findings, outputDirectory);
  return { findings, run };
}

module.exports = {
  PAGE_NAME,
  UPLOAD_ENDPOINT_FRAGMENTS,
  analysePrivateCheck,
  describePrivateCheckFinding,
  privateCheckDirectory,
  privateCheckIsClean,
  runPrivateCheck,
  storageProbeSource,
  summarisePrivateCheck,
};

if (require.main === module) {
  runPrivateCheck().then(
    ({ findings, run }) => {
      const summary = summarisePrivateCheck(run);
      console.log(
        `Private check of ${summary.pageName}: ` +
          `${summary.requestsAfterSelection} upload request(s) after choosing a ` +
          `file, ${summary.requestsAfterSubmit} after clicking submit, ` +
          `${summary.blockedStorageError ?? "storage readable"} ` +
          `for the opaque-origin frame.`,
      );
      console.log(`Wrote ${privateCheckDirectory()}/README.md`);
      for (const finding of findings) {
        console.log(`  ${describePrivateCheckFinding(finding)}`);
      }
      if (!privateCheckIsClean(findings)) {
        process.exitCode = 1;
      }
    },
    (error) => {
      console.error(error.message);
      process.exitCode = 1;
    },
  );
}
