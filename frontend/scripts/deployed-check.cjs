const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const vm = require("node:vm");

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

/* D213: a deployed CORS failure is only diagnosable from outside.  This
   records what the traffic-serving API allows, what each deployed
   'api-config.js' bakes in, and what a real browser actually puts on the
   wire for an image upload from each live origin. */

const PAGE_SETTLE_MS = 1200;
const SUBMIT_SETTLE_MS = 6000;
const PREVIEW_TIMEOUT_MS = 8000;
const HTTP_TIMEOUT_MS = 20000;
const UPLOAD_INPUT_SELECTOR = "#screening-file";
const SUBMIT_BUTTON_SELECTOR = "#run-screening";
const PREFLIGHT_PATH = "/api/screenings";

const DEPLOYED_SITES = [
  { name: "cloudflare-pages", url: "https://project-drishti.pages.dev/home" },
  { name: "tech", url: "https://project-drishti.tech/home" },
  { name: "tech-http", url: "http://project-drishti.tech/home" },
];

const ALLOWLIST_PROBE_ORIGINS = [
  "https://project-drishti.pages.dev",
  "https://project-drishti.tech",
  "http://project-drishti.tech",
  "https://project-drishti-dev.github.io",
  "https://Cosmiczen7.github.io",
  "https://cosmiczen7.github.io",
  "http://localhost:5500",
  "https://not-allowed.example",
];

/* A 1x1 PNG written into the throwaway run directory.  The run needs a file
   the browser really decodes, and no officer's image may reach a log. */
const SYNTHETIC_PNG =
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFAAH/q842iQAAAABJRU5ErkJggg==";

function repositoryRoot() {
  return path.resolve(__dirname, "..", "..");
}

function deployedCheckDirectory() {
  return path.join(repositoryRoot(), "docs", "deployed-check");
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/* Runs a fetched 'api-config.js' as it would run on that host, rather than
   pattern-matching it: the file's whole job is to branch on the hostname, so
   a regex would answer a different question than the browser does. */
function readApiConfigSource(source, hostname) {
  const sandbox = { window: { location: { hostname } } };
  vm.runInNewContext(source, sandbox, { timeout: 1000 });
  const configured = sandbox.window.DRISHTI_CONFIG?.apiBaseUrl;
  return typeof configured === "string" ? configured.trim() : null;
}

async function fetchWithTimeout(url, init = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), HTTP_TIMEOUT_MS);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

/* One deployed 'api-config.js', fetched as a file and read as the page that
   hosts it would read it. */
async function probeApiConfig(site) {
  const url = new URL("/api-config.js", site.url).href;
  const hostname = new URL(url).hostname;
  try {
    const response = await fetchWithTimeout(url);
    const source = await response.text();
    return {
      url,
      status: response.status,
      hostname,
      apiBaseUrl: readApiConfigSource(source, hostname),
    };
  } catch (error) {
    return { url, status: 0, hostname, error: error.name };
  }
}

async function probeHealth(url) {
  try {
    const response = await fetchWithTimeout(url);
    return {
      url,
      status: response.status,
      body: (await response.text()).slice(0, 200),
    };
  } catch (error) {
    return { url, status: 0, error: error.name };
  }
}

/* A preflight from one exact origin.  The allowlist is read from the
   traffic-serving revision's own answers, which is what a browser sees. */
async function probeOrigin(apiBaseUrl, origin) {
  const url = apiBaseUrl + PREFLIGHT_PATH;
  try {
    const response = await fetchWithTimeout(url, {
      method: "OPTIONS",
      headers: {
        Origin: origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
      },
    });
    const allowOrigin = response.headers.get("access-control-allow-origin");
    return {
      origin,
      status: response.status,
      allowed: allowOrigin === origin,
      allowOrigin,
    };
  } catch (error) {
    return { origin, status: 0, allowed: false, error: error.name };
  }
}

function writeSyntheticImage(directory) {
  fs.mkdirSync(directory, { recursive: true });
  const file = path.join(directory, "synthetic-document.png");
  fs.writeFileSync(file, Buffer.from(SYNTHETIC_PNG, "base64"));
  return file;
}

async function evaluateInPage(browser, sessionId, expression) {
  const { result, exceptionDetails } = await browser.sendIn(
    "Runtime.evaluate",
    { expression, returnByValue: true },
    sessionId,
  );
  if (exceptionDetails) {
    throw new Error(exceptionDetails.text || "page evaluation failed");
  }
  return result.value;
}

async function waitForPageState(browser, sessionId, expression, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await evaluateInPage(browser, sessionId, "Boolean(" + expression + ")")) {
      return true;
    }
    await sleep(PAGE_SETTLE_MS / 2);
  }
  return false;
}

/* Only what a network panel would show: method, url, status and the CORS
   headers.  No response body, so no image bytes or extracted text can reach
   the report. */
function apiTrafficIn(entries, pageOrigin) {
  return entries.filter((entry) => {
    if (typeof entry.url !== "string" || !/^https?:/.test(entry.url)) return false;
    let parsed;
    try {
      parsed = new URL(entry.url);
    } catch {
      return false;
    }
    if (!/^\/(api|health)/.test(parsed.pathname)) return false;
    return !pageOrigin || parsed.origin !== pageOrigin;
  });
}

async function runSiteInBrowser(browser, sessionId, site, runDirectory) {
  const requests = [];
  const responses = [];
  const failures = [];
  const urlsById = new Map();
  const onMessage = (message) => {
    if (message.sessionId !== sessionId) return;
    if (message.method === "Network.requestWillBeSent") {
      urlsById.set(message.params.requestId, message.params.request.url);
      requests.push({
        method: message.params.request.method,
        url: message.params.request.url,
      });
    } else if (message.method === "Network.responseReceived") {
      const headers = message.params.response.headers || {};
      responses.push({
        url: message.params.response.url,
        status: message.params.response.status,
        allowOrigin:
          headers["access-control-allow-origin"] ||
          headers["Access-Control-Allow-Origin"] ||
          null,
      });
    } else if (message.method === "Network.loadingFailed") {
      failures.push({
        url: urlsById.get(message.params.requestId) || null,
        errorText: message.params.errorText,
      });
    }
  };
  browser.on(onMessage);
  try {
    const loaded = browser.once("Page.loadEventFired");
    await browser.sendIn("Page.navigate", { url: site.url }, sessionId);
    await loaded;
    await sleep(PAGE_SETTLE_MS);

    const page = await evaluateInPage(
      browser,
      sessionId,
      "({ origin: location.origin, href: location.href, apiBaseUrl: (window.DRISHTI_CONFIG && window.DRISHTI_CONFIG.apiBaseUrl) || '' })",
    );

    const { root } = await browser.sendIn("DOM.getDocument", { depth: -1 }, sessionId);
    const { nodeId } = await browser.sendIn(
      "DOM.querySelector",
      { nodeId: root.nodeId, selector: UPLOAD_INPUT_SELECTOR },
      sessionId,
    );
    if (!nodeId) {
      throw new Error(site.url + " carries no " + UPLOAD_INPUT_SELECTOR + " input");
    }
    await browser.sendIn(
      "DOM.setFileInputFiles",
      { files: [writeSyntheticImage(runDirectory)], nodeId },
      sessionId,
    );
    const previewRendered = await waitForPageState(
      browser,
      sessionId,
      "!document.querySelector('" + SUBMIT_BUTTON_SELECTOR + "').disabled",
      PREVIEW_TIMEOUT_MS,
    );
    if (previewRendered) {
      await browser.sendIn(
        "Runtime.evaluate",
        { expression: "document.querySelector('" + SUBMIT_BUTTON_SELECTOR + "').click()" },
        sessionId,
      );
      await sleep(SUBMIT_SETTLE_MS);
    }

    return {
      name: site.name,
      url: site.url,
      origin: page.origin,
      href: page.href,
      apiBaseUrl: page.apiBaseUrl,
      previewRendered,
      requests: apiTrafficIn(requests, page.origin),
      responses: apiTrafficIn(responses, page.origin),
      failures: apiTrafficIn(failures, page.origin),
    };
  } finally {
    const index = browser.listeners.indexOf(onMessage);
    if (index >= 0) browser.listeners.splice(index, 1);
  }
}

/* Every judgement this report makes, kept apart from the browser so a green
   run is decidable without repeating it. */
function analyseDeployedCheck(run) {
  const findings = [];
  if (run.api.health.status !== 200) {
    findings.push({
      level: "finding",
      code: "api_health_not_ok",
      site: null,
      detail: "GET /health answered " + (run.api.health.status || run.api.health.error),
    });
  }
  const allowedOrigins = run.allowlist
    .filter((entry) => entry.allowed)
    .map((entry) => entry.origin);
  for (const config of run.apiConfigs) {
    if (config.status !== 200) {
      findings.push({
        level: "finding",
        code: "api_config_unreachable",
        site: config.url,
        detail: "status " + (config.status || config.error),
      });
    } else if (!config.apiBaseUrl) {
      findings.push({
        level: "finding",
        code: "api_base_url_empty",
        site: config.url,
        detail: "api-config.js bakes in no API origin, so the page cannot call the API at all",
      });
    }
  }
  for (const site of run.sites) {
    if (!site.apiBaseUrl) {
      findings.push({
        level: "finding",
        code: "page_makes_no_api_request",
        site: site.name,
        detail:
          site.origin +
          " loaded and rendered the page but issued " +
          site.requests.length +
          " API request(s): api-config.js gave it no API origin",
      });
      continue;
    }
    if (!site.requests.some((request) => request.method === "POST")) {
      findings.push({
        level: "finding",
        code: "upload_request_absent",
        site: site.name,
        detail: site.origin + " rendered the preview but posted nothing",
      });
    }
    if (site.failures.length > 0) {
      findings.push({
        level: "finding",
        code: "browser_blocked_request",
        site: site.name,
        detail: site.failures.map((failure) => failure.errorText).join("; "),
      });
    } else if (!allowedOrigins.includes(site.origin)) {
      findings.push({
        level: "finding",
        code: "origin_not_allowlisted",
        site: site.name,
        detail:
          site.origin +
          " is absent from the allowlist this revision serves: " +
          (allowedOrigins.join(", ") || "none"),
      });
    }
  }
  return findings;
}

function describeDeployedCheckFinding(finding) {
  return (
    "[" +
    finding.level +
    "] " +
    finding.code +
    (finding.site ? " (" + finding.site + ")" : "") +
    ": " +
    finding.detail
  );
}

function deployedCheckIsClean(findings) {
  return findings.every((finding) => finding.level !== "finding");
}

function allowOriginCell(entry) {
  return entry.allowOrigin == null ? "(absent)" : entry.allowOrigin;
}

function summariseDeployedCheck(run) {
  return {
    apiBaseUrl: run.api.baseUrl,
    healthStatus: run.api.health.status,
    allowedOrigins: run.allowlist.filter((entry) => entry.allowed).length,
    probedOrigins: run.allowlist.length,
    sitesWithAnUpload: run.sites.filter((site) =>
      site.requests.some((request) => request.method === "POST"),
    ).length,
  };
}

/* What the report exists to settle: why a deployed origin fails, and the
   one change that fixes it.  Both causes are read off the run, never assumed. */
function describeDeployedCheckResolution(run) {
  const lines = [];
  const allowed = run.allowlist
    .filter((entry) => entry.allowed)
    .map((entry) => entry.origin);
  for (const site of run.sites) {
    if (site.apiBaseUrl) continue;
    const line =
      site.origin +
      " never reaches the API: its api-config.js bakes in no base url, so the " +
      "page issues no request at all. That is a build-time setting " +
      "(DRISHTI_API_BASE_URL), not CORS, and only a redeploy changes it.";
    if (!lines.includes(line)) lines.push(line);
  }
  for (const site of run.sites) {
    if (allowed.includes(site.origin)) continue;
    const lead = site.apiBaseUrl
      ? site.origin + " is refused outright:"
      : site.origin + " would be refused even after that fix:";
    const line =
      lead +
      " the revision serving traffic allows " +
      (allowed.join(", ") || "no origin at all") + ", and " +
      site.origin + " is not among them. Add " + site.origin + " to CORS_ORIGINS " +
      "and deploy a new revision; the variable alone changes nothing until one " +
      "serves traffic.";
    if (!lines.includes(line)) lines.push(line);
  }
  return lines;
}

function writeDeployedCheckReport(run, findings, directory) {
  const summary = summariseDeployedCheck(run);
  const lines = [
    "# Deployed check",
    "",
    "Run at " + run.generatedAt + " against the live deployment, with a real",
    "Chromium on a throwaway profile. Only what a network panel shows is",
    "recorded: methods, urls, statuses and CORS headers. No response body,",
    "no image bytes and no extracted text.",
    "",
    "## API",
    "",
    "- Base URL: `" + summary.apiBaseUrl + "`",
    "- `GET /health` -> " + summary.healthStatus + " `" + (run.api.health.body || "") + "`",
    "- `GET /api/version` -> " + run.api.version.status +
      (run.api.version.status === 404
        ? " (the revision serving traffic predates this route)"
        : ""),
    "",
    "## Deployed `api-config.js`",
    "",
    "| url | status | baked-in `apiBaseUrl` |",
    "| --- | --- | --- |",
  ];
  for (const config of run.apiConfigs) {
    lines.push(
      "| " + config.url + " | " + (config.status || config.error) + " | " +
        (config.apiBaseUrl ? "`" + config.apiBaseUrl + "`" : "_(empty)_") + " |",
    );
  }
  lines.push(
    "",
    "## Origins the API actually allows",
    "",
    "Read from `OPTIONS " + PREFLIGHT_PATH + "` answered by the revision that is",
    "actually serving traffic, so this is the deployed allowlist rather than",
    "the one written down anywhere.",
    "",
    "| probe `Origin` | status | `access-control-allow-origin` |",
    "| --- | --- | --- |",
  );
  for (const entry of run.allowlist) {
    lines.push(
      "| `" + entry.origin + "` | " + (entry.status || entry.error) + " | " +
        allowOriginCell(entry) + " |",
    );
  }
  lines.push(
    "",
    "Allowed: " + summary.allowedOrigins + " of " + summary.probedOrigins +
      " probed origins.",
    "",
    "## Image upload, per deployed origin",
    "",
    "| site | navigated | `location.origin` | preview | POST | responses (allow-origin) | blocked |",
    "| --- | --- | --- | --- | --- | --- | --- |",
  );
  for (const site of run.sites) {
    const posted = site.requests.filter((request) => request.method === "POST").length;
    const responses =
      site.responses
        .map(
          (response) =>
            response.status + " " + response.url +
            (response.allowOrigin ? " [allow-origin: " + response.allowOrigin + "]" : ""),
        )
        .join("<br>") || "--";
    const blocked =
      site.failures.map((failure) => failure.errorText).join("<br>") || "--";
    lines.push(
      "| " + site.name + " | " + site.url + " | `" + site.origin + "` | " + site.previewRendered +
        " | " + posted + " | " + responses + " | " + blocked + " |",
    );
  }
  lines.push(
    "",
    "Sites that reached the API with an upload: " + summary.sitesWithAnUpload +
      " of " + run.sites.length + ".",
    "",
    "A 4xx from the API is the CORS layer having done its job: the browser",
    "delivered the request and the application answered it. Only a blocked",
    "entry, or a response with no allow-origin header, is a CORS failure.",
    "",
    "## Why a deployed origin fails",
    "",
    "Read off the run above, so neither cause is assumed.",
    "",
  );
  const resolution = describeDeployedCheckResolution(run);
  for (const line of resolution.length ? resolution : ["- nothing is misconfigured"]) {
    lines.push("- " + line);
  }
  lines.push("");
  lines.push("## Findings");
  lines.push("");
  if (findings.length) {
    for (const finding of findings) {
      lines.push("- " + describeDeployedCheckFinding(finding));
    }
  } else {
    lines.push("- none");
  }
  lines.push("");
  fs.mkdirSync(directory, { recursive: true });
  fs.writeFileSync(path.join(directory, "README.md"), lines.join("\n"));
}

async function runDeployedCheck({
  outputDirectory = deployedCheckDirectory(),
  browserExecutable = null,
} = {}) {
  const executable = browserExecutable || findBrowserExecutable();
  const userDataDirectory = makeUserDataDirectory();
  const runDirectory = fs.mkdtempSync(path.join(os.tmpdir(), "drishti-deployed-"));

  const apiConfigs = [];
  for (const site of DEPLOYED_SITES) {
    apiConfigs.push(await probeApiConfig(site));
  }
  const baseUrl =
    apiConfigs.find((config) => config.apiBaseUrl)?.apiBaseUrl || null;

  const versionProbe = baseUrl ? await probeHealth(baseUrl + "/api/version") : { status: 0 };
  const run = {
    generatedAt: new Date().toISOString(),
    api: {
      baseUrl,
      health: baseUrl
        ? await probeHealth(baseUrl + "/health")
        : { url: null, status: 0, error: "no api base url was deployed" },
      version: { status: versionProbe.status },
    },
    apiConfigs,
    allowlist: baseUrl
      ? await Promise.all(
          ALLOWLIST_PROBE_ORIGINS.map((origin) => probeOrigin(baseUrl, origin)),
        )
      : [],
    sites: [],
    consoleErrors: [],
  };

  const child = launchBrowser(executable, userDataDirectory);
  try {
    const devToolsPort = await waitForDevToolsPort(
      userDataDirectory,
      BROWSER_START_TIMEOUT_MS,
    );
    const browser = await connectToBrowser(devToolsPort);
    try {
      const consoleErrors = collectConsoleErrors(browser);
      const { browserContextId } = await browser.send("Target.createBrowserContext", {
        disposeOnDetach: false,
      });
      for (const site of DEPLOYED_SITES) {
        const { targetId } = await browser.send("Target.createTarget", {
          url: "about:blank",
          browserContextId,
        });
        const { sessionId } = await browser.send("Target.attachToTarget", {
          targetId,
          flatten: true,
        });
        for (const domain of ["Page", "Runtime", "Network", "DOM"]) {
          await browser.sendIn(domain + ".enable", {}, sessionId);
        }
        run.sites.push(
          await runSiteInBrowser(browser, sessionId, site, runDirectory),
        );
        await browser.send("Target.closeTarget", { targetId });
      }
      run.consoleErrors = consoleErrors;
    } finally {
      browser.close();
    }
  } finally {
    stopBrowser(child, userDataDirectory);
    /* A killed Chromium can still hold its profile for a moment, so the
       removal is retried instead of trusted on the first attempt. */
    for (let attempt = 0; attempt < 3; attempt += 1) {
      await sleep(500);
      removeUserDataDirectory(userDataDirectory);
      if (!fs.existsSync(userDataDirectory)) break;
    }
  }

  const findings = analyseDeployedCheck(run);
  writeDeployedCheckReport(run, findings, outputDirectory);
  return { run, findings };
}

module.exports = {
  ALLOWLIST_PROBE_ORIGINS,
  DEPLOYED_SITES,
  analyseDeployedCheck,
  deployedCheckDirectory,
  deployedCheckIsClean,
  describeDeployedCheckFinding,
  describeDeployedCheckResolution,
  probeOrigin,
  readApiConfigSource,
  runDeployedCheck,
  summariseDeployedCheck,
  writeDeployedCheckReport,
};

if (require.main === module) {
  runDeployedCheck().then(
    ({ findings, run }) => {
      const summary = summariseDeployedCheck(run);
      console.log(
        "Deployed check: /health " + summary.healthStatus + ", " +
          summary.allowedOrigins + " of " + summary.probedOrigins +
          " probed origins allowed, " +
          summary.sitesWithAnUpload + " of " + run.sites.length +
          " sites reached the API with an upload.",
      );
      console.log("Wrote " + deployedCheckDirectory() + "/README.md");
      for (const finding of findings) {
        console.log("  " + describeDeployedCheckFinding(finding));
      }
    },
    (error) => {
      console.error(error.message);
      process.exitCode = 1;
    },
  );
}