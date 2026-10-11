const assert = require("node:assert/strict");
const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const { expectedArtefactNames } = require("./build.cjs");
const {
  ArtefactsMissingError,
  checkArtefacts,
  missingArtefacts,
} = require("./scripts/check-artefacts.cjs");

const frontendDirectory = path.resolve(__dirname);
const checkScript = path.join(
  frontendDirectory,
  "scripts",
  "check-artefacts.cjs",
);

/* A page, a script and an asset, each the kind of name this check exists for:
   the first two are named by the build's lists, the last is copied out of
   node_modules/ and is the one a page fails to load without. */
const omittedNames = ["guide.html", "pages.js", "assets/ux4g.css"];

function withBuildOutput(assertBuild) {
  const outputDirectory = fs.mkdtempSync(
    path.join(frontendDirectory, ".artefact-test-"),
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
        },
      },
    );
    assert.equal(result.status, 0, result.stderr);
    assertBuild(outputDirectory);
  } finally {
    const resolvedOutputDirectory = path.resolve(outputDirectory);
    assert.ok(
      resolvedOutputDirectory.startsWith(`${frontendDirectory}${path.sep}`),
      "test build output must remain inside the frontend workspace",
    );
    fs.rmSync(resolvedOutputDirectory, { recursive: true, force: true });
  }
}

/* The command CI runs, over the directory the build wrote, so the exit code is
   the one the workflow would read rather than one this harness asserts. */
function runCheck(outputDirectory) {
  return spawnSync(process.execPath, [checkScript], {
    cwd: frontendDirectory,
    encoding: "utf8",
    env: { ...process.env, DRISHTI_BUILD_OUTPUT_DIR: outputDirectory },
  });
}

test("a build the check can pass on", () => {
  const expectedNames = expectedArtefactNames();

  assert.ok(
    expectedNames.length >= 20,
    "the build should declare a full set of artefacts, not a token few",
  );

  withBuildOutput((outputDirectory) => {
    assert.deepEqual(missingArtefacts(outputDirectory), []);
    assert.equal(checkArtefacts(outputDirectory), outputDirectory);

    const result = runCheck(outputDirectory);
    assert.equal(result.status, 0, result.stderr);
    assert.match(
      result.stdout,
      new RegExp(`All ${expectedNames.length} build artefacts are in`),
    );
  });
});

/* The Verify: a page or a script left out of the build, three at once, and the
   check names all three rather than the first or the count alone. */
test("a page or a script deliberately omitted from the build fails the check", () => {
  withBuildOutput((outputDirectory) => {
    assert.deepEqual(
      missingArtefacts(outputDirectory),
      [],
      "the case must start green",
    );

    for (const name of omittedNames) {
      assert.ok(
        fs.existsSync(path.join(outputDirectory, name)),
        `the case must start with ${name} in the build`,
      );
      fs.rmSync(path.join(outputDirectory, name));
    }

    assert.throws(
      () => checkArtefacts(outputDirectory),
      (error) => {
        assert.ok(error instanceof ArtefactsMissingError, "the check must fail");
        assert.equal(error.name, "ArtefactsMissingError");
        assert.deepEqual(error.missingNames, omittedNames);
        assert.match(error.message, artefactCount(3));
        for (const name of omittedNames) {
          assert.ok(error.message.includes(name), `the message must name ${name}`);
        }
        return true;
      },
    );

    const result = runCheck(outputDirectory);
    assert.notEqual(result.status, 0, "the command CI runs must exit non-zero");
    for (const name of omittedNames) {
      assert.ok(result.stderr.includes(name), `the command must name ${name}`);
    }
  });
});

/* A copy that wrote nothing is a page that 404s just as hard as an absent one,
   so the check reads the bytes rather than the directory entry. */
test("an artefact the build emptied is treated as missing", () => {
  withBuildOutput((outputDirectory) => {
    fs.writeFileSync(path.join(outputDirectory, "index.html"), "");

    assert.deepEqual(missingArtefacts(outputDirectory), ["index.html"]);
    assert.throws(
      () => checkArtefacts(outputDirectory),
      (error) => {
        assert.deepEqual(error.missingNames, ["index.html"]);
        assert.match(
          error.message,
          artefactCount(1, "index\\.html\\."),
        );
        return true;
      },
    );
  });
});

/* A check over a directory nothing was built into has to say so, rather than
   list every artefact as missing and hide the one action that fixes it. */
test("no build output at all is refused with the command to run", () => {
  const absentDirectory = path.join(frontendDirectory, ".artefact-test-absent");
  fs.rmSync(absentDirectory, { recursive: true, force: true });

  assert.throws(
    () => checkArtefacts(absentDirectory),
    (error) => {
      assert.ok(error instanceof ArtefactsMissingError, "the check must fail");
      assert.match(error.message, /holds no build output/);
      assert.match(error.message, /npm run build/);
      assert.deepEqual(
        error.missingNames,
        expectedArtefactNames(),
        "nothing there means every artefact is absent",
      );
      return true;
    },
  );

  const result = runCheck(absentDirectory);
  assert.notEqual(result.status, 0, "the command CI runs must exit non-zero");
});
/* The counts in the messages below are read out of the build's own list rather
   than written down, so a page added later moves them instead of reddening
   three tests that have nothing to do with it. */
function artefactCount(missing, names = "") {
  return new RegExp(
    `is missing ${missing} of ${expectedArtefactNames().length} build artefacts: ${names}`,
  );
}