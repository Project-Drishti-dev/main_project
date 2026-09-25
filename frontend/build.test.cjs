const assert = require("node:assert/strict");
const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const frontendDirectory = path.resolve(__dirname);

function withBuildOutput(environment, assertBuild) {
  const outputDirectory = fs.mkdtempSync(
    path.join(frontendDirectory, ".build-test-"),
  );

  try {
    const result = spawnSync(
      process.execPath,
      [path.join(frontendDirectory, "build.cjs")],
      {
        cwd: frontendDirectory,
        encoding: "utf8",
        env: {
          ...process.env,
          CF_PAGES: "",
          DRISHTI_API_BASE_URL: "",
          DRISHTI_BUILD_OUTPUT_DIR: outputDirectory,
          ...environment,
        },
      },
    );
    assertBuild({ outputDirectory, result });
  } finally {
    const resolvedOutputDirectory = path.resolve(outputDirectory);
    assert.ok(
      resolvedOutputDirectory.startsWith(`${frontendDirectory}${path.sep}`),
      "test build output must remain inside the frontend workspace",
    );
    fs.rmSync(resolvedOutputDirectory, { recursive: true, force: true });
  }
}

test("static build packages pages, UX4G assets, and the configured API origin", () => {
  withBuildOutput(
    {
      CF_PAGES: "1",
      DRISHTI_API_BASE_URL: "https://quality-api.example.run.app",
    },
    ({ outputDirectory, result }) => {
      assert.equal(result.status, 0, result.stderr);

      for (const fileName of [
        "index.html",
        "home.html",
        "register.html",
        "login.css",
        "login.js",
        "reset-flow.js",
        "register.css",
        "register.js",
        "home.css",
        "home.js",
      ]) {
        assert.ok(
          fs.existsSync(path.join(outputDirectory, fileName)),
          `build should include ${fileName}`,
        );
      }

      for (const fileName of ["index.html", "home.html", "register.html"]) {
        const html = fs.readFileSync(
          path.join(outputDirectory, fileName),
          "utf8",
        );
        assert.match(html, /href="\.\/assets\/ux4g\.css"/);
        assert.match(html, /src="\.\/assets\/design-system\.js"/);
        assert.doesNotMatch(html, /node_modules/);
      }

      assert.ok(
        fs.existsSync(path.join(outputDirectory, "assets", "ux4g.css")),
      );
      assert.ok(
        fs.existsSync(path.join(outputDirectory, "assets", "design-system.js")),
      );
      const apiConfig = fs.readFileSync(
        path.join(outputDirectory, "api-config.js"),
        "utf8",
      );
      assert.match(apiConfig, /https:\/\/quality-api\.example\.run\.app/);
      assert.match(apiConfig, /http:\/\/localhost:8080/);
    },
  );
});

test("static build reports when the hosted API origin is not configured", () => {
  withBuildOutput(
    { CF_PAGES: "1", DRISHTI_API_BASE_URL: "" },
    ({ outputDirectory, result }) => {
      assert.equal(result.status, 0, result.stderr);
      assert.match(
        result.stderr,
        /DRISHTI_API_BASE_URL is not set/,
      );
      assert.match(
        fs.readFileSync(path.join(outputDirectory, "api-config.js"), "utf8"),
        /apiBaseUrl: isLocalDevelopment\s+\? "http:\/\/localhost:8080"\s+: ""/,
      );
    },
  );
});
