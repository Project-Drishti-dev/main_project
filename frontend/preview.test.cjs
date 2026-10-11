const assert = require("node:assert/strict");
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const test = require("node:test");

const frontendDirectory = path.resolve(__dirname);
const readme = fs.readFileSync(
  path.join(frontendDirectory, "README.md"),
  "utf8",
);
const packageJson = JSON.parse(
  fs.readFileSync(path.join(frontendDirectory, "package.json"), "utf8"),
);

/* The command a case runs is the command npm runs, read out of package.json
   rather than named here, so a renamed script fails these cases instead of
   leaving them testing a file nothing ships. */
function previewCommand() {
  const command = packageJson.scripts?.preview;
  assert.ok(command, "package.json should carry a preview script");
  const [runtime, ...scriptArguments] = command.trim().split(/\s+/);
  assert.equal(runtime, "node", `preview should run under node, not ${runtime}`);
  assert.ok(scriptArguments.length > 0, "preview should name a script to run");
  for (const scriptArgument of scriptArguments) {
    assert.ok(
      fs.existsSync(path.join(frontendDirectory, scriptArgument)),
      `preview runs ${scriptArgument}, which is not in frontend/`,
    );
  }
  return scriptArguments;
}

/* A directory that is not there yet: the preview has to build it, so a server
   that published a stale dist/ instead of building one would have nothing to
   serve.  The build refuses an output outside frontend/, so it sits beside the
   other test builds rather than in the system temp directory. */
function absentOutputDirectory() {
  const outputDirectory = fs.mkdtempSync(
    path.join(frontendDirectory, ".preview-test-"),
  );
  fs.rmdirSync(outputDirectory);
  return outputDirectory;
}

function waitForUrl(child, timeoutMs) {
  return new Promise((resolve, reject) => {
    let reported = "";
    const timer = setTimeout(() => {
      reject(
        new Error(
          `preview reported no URL within ${timeoutMs}ms: ${reported}`,
        ),
      );
    }, timeoutMs);

    child.stdout.on("data", (chunk) => {
      reported += chunk;
      const match = reported.match(/http:\/\/127\.0\.0\.1:(\d+)\//);
      if (match) {
        clearTimeout(timer);
        resolve(Number(match[1]));
      }
    });
    child.stderr.on("data", (chunk) => {
      reported += chunk;
    });
    child.once("exit", (code) => {
      clearTimeout(timer);
      reject(new Error(`preview exited with code ${code}: ${reported}`));
    });
    child.once("error", (error) => {
      clearTimeout(timer);
      reject(error);
    });
  });
}

async function withPreview(assertPreview) {
  const outputDirectory = absentOutputDirectory();
  const child = spawn(process.execPath, previewCommand(), {
    cwd: frontendDirectory,
    env: {
      ...process.env,
      CF_PAGES: "",
      DRISHTI_API_BASE_URL: "",
      DRISHTI_BUILD_OUTPUT_DIR: outputDirectory,
      DRISHTI_PREVIEW_PORT: "0",
    },
  });

  try {
    const port = await waitForUrl(child, 25000);
    await assertPreview({ outputDirectory, port });
  } finally {
    child.kill();
    await new Promise((resolve) => child.once("exit", resolve));
    const resolvedOutputDirectory = path.resolve(outputDirectory);
    assert.ok(
      resolvedOutputDirectory.startsWith(`${frontendDirectory}${path.sep}`),
      "preview output must remain inside the frontend workspace",
    );
    fs.rmSync(resolvedOutputDirectory, { force: true, recursive: true });
  }
}

/* A raw request line, because a client that normalises the path would resolve
   the climb this asks about before the server ever saw it. */
function rawGet(port, requestPath) {
  return new Promise((resolve, reject) => {
    const request = http.request(
      { host: "127.0.0.1", method: "GET", path: requestPath, port },
      (response) => {
        const chunks = [];
        response.on("data", (chunk) => chunks.push(chunk));
        response.on("end", () => {
          resolve({
            body: Buffer.concat(chunks).toString("utf8"),
            status: response.statusCode,
          });
        });
      },
    );
    request.on("error", reject);
    request.end();
  });
}

async function get(port, requestPath) {
  const response = await fetch(`http://127.0.0.1:${port}/${requestPath}`);
  return {
    body: Buffer.from(await response.arrayBuffer()),
    status: response.status,
  };
}

test("the preview builds the site, and every page it wrote is served", async () => {
  await withPreview(async ({ outputDirectory, port }) => {
    const builtPages = fs
      .readdirSync(outputDirectory)
      .filter((name) => name.endsWith(".html"))
      .sort();
    assert.ok(
      builtPages.length >= 7,
      "the preview should build the whole site before it serves",
    );

    for (const builtPage of builtPages) {
      const response = await get(port, `${builtPage}`);
      assert.equal(response.status, 200, `${builtPage} should be served`);
      assert.deepEqual(
        response.body,
        fs.readFileSync(path.join(outputDirectory, builtPage)),
        `${builtPage} should be served as the bytes the build wrote`,
      );
    }

    const root = await get(port, "");
    assert.equal(root.status, 200, "the root should open the public demo");
    assert.deepEqual(
      root.body,
      fs.readFileSync(path.join(outputDirectory, "index.html")),
      "the root should serve the built index.html",
    );

    const stylesheet = await get(port, "assets/ux4g.css");
    assert.equal(stylesheet.status, 200, "a built asset should be served");
    assert.match(stylesheet.body.toString("utf8"), /ux4g/);
  });
});

/* The refusal and the miss are held to the answer they must not give: a page
   the build wrote is served, so the 403 and the 404 are not everything. */
test("the preview refuses a path out of the build and misses a name it never wrote", async () => {
  await withPreview(async ({ outputDirectory, port }) => {
    const served = await get(port, "home.html");
    assert.equal(served.status, 200, "a built page should be served");
    assert.deepEqual(
      served.body,
      fs.readFileSync(path.join(outputDirectory, "home.html")),
    );

    const escaping = await rawGet(port, "/%2e%2e%2fpackage.json");
    assert.equal(escaping.status, 403, "a path out of dist/ must be refused");
    assert.match(escaping.body, /leaves the build output/);

    const absent = await rawGet(port, "/dashboard.html");
    assert.equal(absent.status, 404, "a name the build does not write must miss");
    assert.match(absent.body, /is not a file in the build output/);

    const neighbour = await rawGet(port, "/%2e%2e%2f%2e%2e%2fpackage.json");
    assert.equal(neighbour.status, 403, "a climb past the root must be refused");
  });
});

/* What the README tells a developer to type is what package.json defines, and
   what it defines is a file that exists.  A documented command that has
   drifted from the scripts block is the drift this holds. */
test("every command the README documents is one package.json defines", () => {
  const documented = [
    ...readme.matchAll(/npm run ([\w:-]+)/g),
  ].map((match) => match[1]);
  assert.ok(
    documented.includes("preview"),
    "README should document npm run preview",
  );
  assert.match(
    readme,
    /`npm run preview` \| Builds `frontend\/dist\/`, then serves it\./,
    "README should say that preview builds what it serves",
  );

  for (const scriptName of new Set(documented)) {
    const command = packageJson.scripts?.[scriptName];
    assert.ok(
      command,
      `README documents npm run ${scriptName}, which package.json does not define`,
    );
    const [, scriptFile] = command.trim().split(/\s+/);
    assert.ok(
      fs.existsSync(path.join(frontendDirectory, scriptFile)),
      `npm run ${scriptName} runs ${scriptFile}, which is not in frontend/`,
    );
  }
});
