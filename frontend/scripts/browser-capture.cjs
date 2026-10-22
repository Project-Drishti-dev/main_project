const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawn, spawnSync } = require("node:child_process");

/* Launches a headless Chromium on a throwaway profile and speaks the DevTools
   protocol to it.  Inputs: a browser executable path and a profile directory.
   Output: one session per connected page.  A missing browser throws by name
   rather than silently rendering nothing. */

const VIEWPORT_HEIGHT = 900;
const MAX_CAPTURE_HEIGHT = 20000;
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
    return this.sendIn(method, params, null);
  }

  /* A flattened session carries its own id on the message, which is how a
     browser-level connection drives a target it did not open itself. */
  sendIn(method, params = {}, sessionId = null) {
    const id = this.nextId++;
    const message = { id, method, params };
    if (sessionId) message.sessionId = sessionId;
    this.socket.send(JSON.stringify(message));
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

/* The browser-level endpoint, so a caller can open its own off-the-record
   target instead of adopting whichever page the launch left open. */
async function connectToBrowser(port) {
  const response = await fetch(`http://127.0.0.1:${port}/json/version`);
  const version = await response.json();
  const socket = new WebSocket(version.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    socket.addEventListener("open", resolve, { once: true });
    socket.addEventListener("error", () => {
      reject(new Error("DevTools socket refused"));
    }, { once: true });
  });
  return new DevToolsSession(socket);
}

/* A killed browser can still be holding its profile, so the throwaway profile
   is removed by name and a lock is not allowed to fail the run. */
function removeUserDataDirectory(userDataDirectory) {
  try {
    fs.rmSync(userDataDirectory, {
      recursive: true,
      force: true,
      maxRetries: 5,
      retryDelay: 200,
    });
  } catch {
    /* The directory is under the system temp directory and is named per run. */
  }
}

function launchBrowser(executable, userDataDirectory, extraArguments = []) {
  return spawn(
    executable,
    [
      "--headless=new",
      "--disable-gpu",
      "--hide-scrollbars",
      "--no-first-run",
      "--no-default-browser-check",
      "--disable-extensions",
      ...extraArguments,
      `--user-data-dir=${userDataDirectory}`,
      "--remote-debugging-port=0",
      "about:blank",
    ],
    { stdio: "ignore" },
  );
}

/* A Chromium launcher exits as soon as it has handed the browser to another
   process, so by cleanup time its pid is gone and the renderer, network and
   crashpad processes still holding the throwaway profile have been
   re-parented. They are found by that profile directory instead, which is
   named per run exactly as removeUserDataDirectory assumes. */
function stopBrowser(child, userDataDirectory) {
  if (child.exitCode === null && child.signalCode === null) {
    child.kill();
  }
  if (process.platform !== "win32" || !userDataDirectory) {
    return;
  }
  const profile = String(userDataDirectory).replace(/'/g, "''");
  spawnSync(
    "powershell.exe",
    [
      "-NoProfile",
      "-Command",
      "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like " +
        "'*" + profile + "*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }",
    ],
    { stdio: "ignore" },
  );
}

function makeUserDataDirectory() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "drishti-shots-"));
}

/* Navigates and waits for load plus one settle interval. */
async function navigateAndSettle(session, url, settleMs = PAGE_SETTLE_MS) {
  const loaded = session.once("Page.loadEventFired");
  await session.send("Page.navigate", { url });
  await loaded;
  await new Promise((resolve) => setTimeout(resolve, settleMs));
}

/* Reads the full-page picture at the page's own content height. */
async function capturePage(session, width, maxHeight = MAX_CAPTURE_HEIGHT) {
  const metrics = await session.send("Page.getLayoutMetrics");
  const contentHeight = Math.min(
    Math.ceil(metrics.cssContentSize?.height ?? VIEWPORT_HEIGHT),
    maxHeight,
  );
  const capture = await session.send("Page.captureScreenshot", {
    format: "png",
    captureBeyondViewport: true,
    fromSurface: true,
    clip: { x: 0, y: 0, width, height: contentHeight, scale: 1 },
  });
  return { png: Buffer.from(capture.data, "base64"), contentHeight };
}

/* Collects uncaught exceptions for the life of the returned array. */
function collectConsoleErrors(session) {
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
  return consoleErrors;
}

module.exports = {
  BROWSER_CANDIDATES,
  BROWSER_START_TIMEOUT_MS,
  DevToolsSession,
  MAX_CAPTURE_HEIGHT,
  MAX_CONSOLE_ERRORS,
  PAGE_SETTLE_MS,
  VIEWPORT_HEIGHT,
  capturePage,
  collectConsoleErrors,
  connectToBrowser,
  connectToTarget,
  findBrowserExecutable,
  launchBrowser,
  makeUserDataDirectory,
  navigateAndSettle,
  readDevToolsPort,
  removeUserDataDirectory,
  stopBrowser,
  waitForDevToolsPort,
};
