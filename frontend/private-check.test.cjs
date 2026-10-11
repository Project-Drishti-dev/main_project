const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const {
  PAGE_NAME,
  UPLOAD_ENDPOINT_FRAGMENTS,
  analysePrivateCheck,
  describePrivateCheckFinding,
  privateCheckDirectory,
  privateCheckIsClean,
  storageProbeSource,
  summarisePrivateCheck,
} = require("./scripts/private-check.cjs");

/* D212: the verdicts the run prints have to be decidable without a browser, or
   a passing private-mode run could only be trusted by re-reading it. */

function answeredRun(overrides = {}) {
  const run = {
    pageName: PAGE_NAME,
    privateContext: true,
    preferences: {
      loaded: true,
      theme: "light",
      textSize: "default",
      themePreference: "light",
      storageReadable: true,
      storageError: null,
    },
    blockedStorage: {
      readable: false,
      error: "SecurityError",
      preferencesLoaded: true,
      themePreference: "dark",
      wroteTheme: "dark",
      writeError: null,
    },
    upload: {
      previewRendered: true,
      requestsAfterSelection: 0,
      requestsAfterSubmit: 1,
      requestsAfterSubmitUrls: ["POST https://api.example.test/api/analyze"],
      requestsBeforeSubmitUrls: [],
      totalRequests: 9,
    },
    consoleErrors: [],
    ...overrides,
  };
  return run;
}

function withUpload(overrides) {
  return answeredRun({
    upload: { ...answeredRun().upload, ...overrides },
  });
}

test("a run that answered the question is clean", () => {
  assert.deepEqual(analysePrivateCheck(answeredRun()), []);
  assert.equal(privateCheckIsClean(analysePrivateCheck(answeredRun())), true);
});

test("a request that left the page before the click is a finding", () => {
  const findings = analysePrivateCheck(
    withUpload({ requestsAfterSelection: 2 }),
  );
  assert.deepEqual(
    findings.map((finding) => finding.kind),
    ["upload-before-submit"],
  );
  assert.equal(findings[0].count, 2);
});

test("a click that sent nothing is a finding, not a quiet success", () => {
  const findings = analysePrivateCheck(
    withUpload({ requestsAfterSubmit: 0 }),
  );
  assert.deepEqual(
    findings.map((finding) => finding.kind),
    ["no-upload-on-submit"],
  );
});

test("a run in an ordinary context is a finding, so private mode cannot be assumed", () => {
  const findings = analysePrivateCheck(answeredRun({ privateContext: false }));
  assert.deepEqual(
    findings.map((finding) => finding.kind),
    ["not-private-context"],
  );
});

test("an opaque-origin frame that could still read storage is a finding", () => {
  const findings = analysePrivateCheck(
    answeredRun({
      blockedStorage: { ...answeredRun().blockedStorage, readable: true, error: null },
    }),
  );
  assert.deepEqual(
    findings.map((finding) => finding.kind),
    ["storage-not-blocked"],
  );
});

test("a probe that timed out is not read as a refusal", () => {
  const findings = analysePrivateCheck(
    answeredRun({
      blockedStorage: {
        ...answeredRun().blockedStorage,
        readable: null,
        error: "probe-timed-out",
      },
    }),
  );
  assert.deepEqual(
    findings.map((finding) => finding.kind),
    ["storage-not-blocked"],
  );
});

test("preferences.js failing to load without storage is a finding", () => {
  const findings = analysePrivateCheck(
    answeredRun({
      blockedStorage: {
        ...answeredRun().blockedStorage,
        preferencesLoaded: false,
        wroteTheme: null,
      },
    }),
  );
  assert.deepEqual(
    findings.map((finding) => finding.kind),
    ["preferences-missing-without-storage", "preferences-write-not-applied"],
  );
});

test("a write that throws without storage is named with the error", () => {
  const findings = analysePrivateCheck(
    answeredRun({
      blockedStorage: {
        ...answeredRun().blockedStorage,
        wroteTheme: null,
        writeError: "QuotaExceededError",
      },
    }),
  );
  assert.deepEqual(
    findings.map((finding) => finding.kind),
    ["preferences-write-threw", "preferences-write-not-applied"],
  );
  assert.match(
    describePrivateCheckFinding(findings[0]),
    /QuotaExceededError/,
  );
});

test("a preview that never rendered is a finding, because nothing was then proven", () => {
  const findings = analysePrivateCheck(
    withUpload({ previewRendered: false, requestsAfterSubmit: 0 }),
  );
  assert.deepEqual(
    findings.map((finding) => finding.kind),
    ["preview-not-rendered", "no-upload-on-submit"],
  );
});

test("a page that never applied the theme is a finding", () => {
  const findings = analysePrivateCheck(
    answeredRun({
      preferences: { ...answeredRun().preferences, theme: null },
    }),
  );
  assert.deepEqual(
    findings.map((finding) => finding.kind),
    ["theme-not-defaulted"],
  );
});

test("every uncaught console error is reported by name", () => {
  const findings = analysePrivateCheck(
    answeredRun({ consoleErrors: ["TypeError: x is not a function"] }),
  );
  assert.deepEqual(
    findings.map((finding) => finding.kind),
    ["console-error"],
  );
  assert.match(describePrivateCheckFinding(findings[0]), /TypeError/);
});

test("every finding has a sentence, so the report reads without the browser", () => {
  const runs = [
    answeredRun(),
    withUpload({ requestsAfterSelection: 3 }),
    withUpload({ requestsAfterSubmit: 0 }),
    withUpload({ previewRendered: false }),
    answeredRun({ privateContext: false }),
    answeredRun({ consoleErrors: ["boom"] }),
    answeredRun({ blockedStorage: { readable: true, error: null } }),
    answeredRun({
      preferences: { ...answeredRun().preferences, theme: "dark" },
    }),
    answeredRun({
      blockedStorage: {
        ...answeredRun().blockedStorage,
        preferencesLoaded: false,
        wroteTheme: null,
        writeError: "SecurityError",
      },
    }),
  ];
  let count = 0;
  for (const run of runs) {
    for (const finding of analysePrivateCheck(run)) {
      count += 1;
      const sentence = describePrivateCheckFinding(finding);
      assert.equal(typeof sentence, "string");
      assert.ok(sentence.length > 0, `${finding.kind} needs a sentence`);
      assert.ok(
        !sentence.includes("[object Object]"),
        `${finding.kind} must not stringify an object`,
      );
      assert.ok(!sentence.includes("undefined"));
      assert.ok(!sentence.includes(" null"));
    }
  }
  assert.ok(count >= 8, `expected findings to be exercised, saw ${count}`);
});

test("an unrecognised finding is named rather than dropped", () => {
  assert.match(
    describePrivateCheckFinding({ kind: "from-the-future" }),
    /from-the-future/,
  );
});

test("the summary reports the two numbers the task asks about", () => {
  const summary = summarisePrivateCheck(answeredRun());
  assert.equal(summary.privateContext, true);
  assert.equal(summary.pageName, PAGE_NAME);
  assert.equal(summary.requestsAfterSelection, 0);
  assert.equal(summary.requestsAfterSubmit, 1);
  assert.equal(summary.blockedStorageError, "SecurityError");
});

test("the probe sandboxes the frame without allow-same-origin", () => {
  const probe = storageProbeSource("window.DRISHTI_PREFERENCES = {};");
  assert.match(probe, /setAttribute\("sandbox", "allow-scripts"\)/);
  assert.ok(!probe.includes("allow-same-origin"));
  assert.match(probe, /localStorage\.getItem/);
});

test("the probe inlines preferences.js rather than fetching it", () => {
  const probe = storageProbeSource('const MARKER = "inlined";');
  assert.ok(probe.includes("inlined"));
  assert.ok(!/src=/.test(probe), "the probe must not load a script over the network");
});

test("the upload endpoints named are the ones the site posts to", () => {
  assert.deepEqual(UPLOAD_ENDPOINT_FRAGMENTS, ["/api/analyze", "/api/screenings"]);
  for (const fileName of ["home.js", "submit.js"]) {
    const source = fs.readFileSync(path.join(__dirname, fileName), "utf8");
    assert.ok(
      UPLOAD_ENDPOINT_FRAGMENTS.some((fragment) => source.includes(fragment)),
      `${fileName} posts to no endpoint this check watches`,
    );
  }
});

test("the private check directory is one .gitignore does not swallow", () => {
  const ignore = fs.readFileSync(
    path.resolve(__dirname, "..", ".gitignore"),
    "utf8",
  );
  const relative = path
    .relative(path.resolve(__dirname, ".."), privateCheckDirectory())
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
