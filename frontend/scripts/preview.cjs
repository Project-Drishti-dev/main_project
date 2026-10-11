const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");

const { buildOutputDirectory, buildSite } = require("../build.cjs");

/* Builds the site and then serves it.  A source .html under frontend/ is a
   fragment the shell fills at build time, so the site a developer works at is
   the built one: this is the documented replacement for opening a fragment
   from disk (D174). */

const DEFAULT_PORT = 5500;

const PREVIEW_PROBE_PATH = "/index.html";
const PREVIEW_PROBE_ATTEMPTS = 3;
const PREVIEW_PROBE_TIMEOUT_MS = 1000;
const PREVIEW_RETRY_PAUSE_MS = 50;
const CONTENT_TYPES = new Map([
  [".css", "text/css; charset=utf-8"],
  [".html", "text/html; charset=utf-8"],
  [".ico", "image/x-icon"],
  [".js", "text/javascript; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
  [".png", "image/png"],
  [".svg", "image/svg+xml"],
  [".webp", "image/webp"],
]);

class PreviewError extends Error {
  constructor(message) {
    super(message);
    this.name = "PreviewError";
  }
}

/* 0 asks the operating system for a free port, which is how a second preview
   runs beside the first.  Any other value is refused by name. */
function previewPort() {
  const configured = process.env.DRISHTI_PREVIEW_PORT?.trim() || "";
  if (configured === "") {
    return DEFAULT_PORT;
  }
  const port = Number(configured);
  if (!Number.isInteger(port) || port < 0 || port > 65535) {
    throw new PreviewError(
      "DRISHTI_PREVIEW_PORT must be a port number between 0 and 65535.",
    );
  }
  return port;
}

function previewUrl(port) {
  return `http://127.0.0.1:${port}/`;
}

/* One request URL to one file inside the served root: "/" and any name ending
   in "/" open index.html, and a path climbing out of the root is refused by
   name rather than served from beside it. */
function resolveRequestPath(rootDirectory, requestUrl) {
  const root = path.resolve(rootDirectory);
  const requestUrlText = requestUrl || "/";
  const encodedPath = requestUrlText.split("?")[0].split("#")[0];

  let decodedPath;
  try {
    decodedPath = decodeURIComponent(encodedPath);
  } catch {
    throw new PreviewError(`${requestUrlText} is not a readable URL.`);
  }

  const requested = decodedPath.replace(/^\/+/, "");
  const filePath = path.resolve(
    root,
    requested === "" || requested.endsWith("/")
      ? `${requested}index.html`
      : requested,
  );
  if (filePath !== root && !filePath.startsWith(`${root}${path.sep}`)) {
    throw new PreviewError(`${decodedPath} leaves the build output.`);
  }
  return filePath;
}

function respondText(response, statusCode, message) {
  response.writeHead(statusCode, {
    "cache-control": "no-store",
    "content-length": Buffer.byteLength(message),
    "content-type": "text/plain; charset=utf-8",
  });
  response.end(message);
}

function requestHandler(rootDirectory) {
  return (request, response) => {
    let filePath;
    try {
      filePath = resolveRequestPath(rootDirectory, request.url);
    } catch (error) {
      respondText(response, 403, `${error.message}\n`);
      return;
    }

    let body;
    try {
      if (!fs.statSync(filePath).isFile()) {
        throw new Error("not a file");
      }
      body = fs.readFileSync(filePath);
    } catch {
      respondText(
        response,
        404,
        `${request.url} is not a file in the build output.\n`,
      );
      return;
    }

    response.writeHead(200, {
      "cache-control": "no-store",
      "content-length": body.length,
      "content-type":
        CONTENT_TYPES.get(path.extname(filePath).toLowerCase()) ||
        "application/octet-stream",
    });
    response.end(body);
  };
}

function listenOnPort(server, port) {
  return new Promise((resolve, reject) => {
    server.once("error", (error) => {
      reject(
        new PreviewError(
          `preview could not listen on port ${port}: ${error.message}`,
        ),
      );
    });
    server.listen(port, "127.0.0.1", resolve);
  });
}

/* One request the preview makes to itself over the port it just bound.  A
   bound port is not yet an answerable one: a client can be refused for a
   moment after the socket exists, so the preview asks its own URL before it
   announces it, and a port that does not answer is never printed. */
function probePreviewPort(port, timeoutMs = PREVIEW_PROBE_TIMEOUT_MS) {
  return new Promise((resolve) => {
    let answered = false;
    const settle = (isAnswered) => {
      if (answered) {
        return;
      }
      answered = true;
      resolve(isAnswered);
    };
    const request = http.request(
      {
        agent: false,
        host: "127.0.0.1",
        method: "GET",
        path: PREVIEW_PROBE_PATH,
        port,
        timeout: timeoutMs,
      },
      (response) => {
        response.resume();
        response.once("end", () => settle(response.statusCode === 200));
      },
    );
    request.once("timeout", () => {
      request.destroy();
      settle(false);
    });
    request.once("error", () => settle(false));
    request.end();
  });
}

function closeServer(server) {
  return new Promise((resolve) => {
    server.close(() => resolve());
    server.closeAllConnections();
  });
}

/* Builds, then serves the directory the build wrote, so a preview can never
   publish a stale dist/ beside the sources.  Answers the server and the port
   it actually bound rather than the one asked for, and only answers a port
   that has served a request itself: an OS-assigned port can refuse the first
   connection after it is bound, and the retry asks for another one. */
async function startPreviewServer({ port = previewPort() } = {}) {
  buildSite();
  const outputDirectory = buildOutputDirectory();

  for (let attempt = 1; ; attempt += 1) {
    const server = http.createServer(requestHandler(outputDirectory));
    await listenOnPort(server, port);
    const boundPort = server.address().port;

    if (await probePreviewPort(boundPort)) {
      server.on("error", (error) => {
        console.error(
          `preview stopped answering on port ${boundPort}: ${error.message}`,
        );
      });
      return { outputDirectory, port: boundPort, server };
    }

    await closeServer(server);
    if (attempt >= PREVIEW_PROBE_ATTEMPTS) {
      throw new PreviewError(
        `preview did not answer on port ${boundPort} after ` +
          `${PREVIEW_PROBE_ATTEMPTS} attempts.`,
      );
    }
    await new Promise((resolve) =>
      setTimeout(resolve, PREVIEW_RETRY_PAUSE_MS),
    );
  }
}

/* The pages a preview serves, read out of the built directory rather than from
   a list of its own, so the printed set is what a request can open. */
function previewPageNames(outputDirectory) {
  return fs
    .readdirSync(outputDirectory)
    .filter((name) => name.endsWith(".html"))
    .sort();
}

module.exports = {
  PreviewError,
  previewPageNames,
  previewPort,
  previewUrl,
  resolveRequestPath,
  startPreviewServer,
};

if (require.main === module) {
  startPreviewServer().then(
    ({ port, outputDirectory }) => {
      console.log(`Preview at ${previewUrl(port)} -- Ctrl+C to stop.`);
      console.log(`Pages: ${previewPageNames(outputDirectory).join(", ")}`);
    },
    (error) => {
      console.error(error.message);
      process.exitCode = 1;
    },
  );
}
