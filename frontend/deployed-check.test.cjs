const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const {
  analyseDeployedCheck,
  deployedCheckIsClean,
  describeDeployedCheckFinding,
  describeDeployedCheckResolution,
  readApiConfigSource,
  summariseDeployedCheck,
  writeDeployedCheckReport,
} = require("./scripts/deployed-check.cjs");

const API = "https://main-project-888645637790.asia-south1.run.app";

const API_CONFIG = `(() => {
  const localHosts = new Set(["localhost", "127.0.0.1"]);
  const isLocalDevelopment = localHosts.has(window.location.hostname);
  window.DRISHTI_CONFIG = {
    apiBaseUrl: isLocalDevelopment ? "http://localhost:8080" : "` + API + `",
  };
})();`;

const EMPTY_API_CONFIG = `(() => {
  window.DRISHTI_CONFIG = { apiBaseUrl: "" };
})();`;

function site(overrides = {}) {
  return {
    name: "cloudflare-pages",
    url: "https://project-drishti.pages.dev/home",
    origin: "https://project-drishti.pages.dev",
    href: "https://project-drishti.pages.dev/home",
    apiBaseUrl: API,
    previewRendered: true,
    requests: [{ method: "POST", url: API + "/api/analyze" }],
    responses: [
      {
        url: API + "/api/analyze",
        status: 422,
        allowOrigin: "https://project-drishti.pages.dev",
      },
    ],
    failures: [],
    ...overrides,
  };
}

function run(overrides = {}) {
  return {
    generatedAt: "2026-10-05T00:00:00.000Z",
    api: { baseUrl: API, health: { status: 200, body: '{"status":"ok"}' }, version: { status: 404 } },
    apiConfigs: [{ url: "https://project-drishti.pages.dev/api-config.js", status: 200, apiBaseUrl: API }],
    allowlist: [
      { origin: "https://project-drishti.pages.dev", status: 200, allowed: true },
      { origin: "https://project-drishti.tech", status: 400, allowed: false },
    ],
    sites: [site()],
    consoleErrors: [],
    ...overrides,
  };
}

test("api-config.js is read by running it, so the hostname decides the branch", () => {
  assert.equal(readApiConfigSource(API_CONFIG, "project-drishti.pages.dev"), API);
  assert.equal(readApiConfigSource(API_CONFIG, "localhost"), "http://localhost:8080");
});

test("a deployed api-config.js that bakes in nothing is read as no base url", () => {
  assert.equal(readApiConfigSource(EMPTY_API_CONFIG, "project-drishti.tech"), "");
  assert.equal(readApiConfigSource(EMPTY_API_CONFIG, "project-drishti.tech").length, 0);
});

test("a delivered upload that the API answered is not a CORS failure", () => {
  const findings = analyseDeployedCheck(run());
  assert.deepEqual(findings, []);
  assert.equal(deployedCheckIsClean(findings), true);
});

test("a 4xx from the API is not read as a CORS failure", () => {
  const answered = site({
    responses: [{ url: API + "/api/analyze", status: 400, allowOrigin: "https://project-drishti.pages.dev" }],
  });
  assert.deepEqual(analyseDeployedCheck(run({ sites: [answered] })), []);
});

test("an origin the traffic-serving revision refuses is a finding", () => {
  const refused = site({
    name: "tech",
    origin: "https://project-drishti.tech",
    responses: [],
    requests: [],
  });
  const findings = analyseDeployedCheck(run({ sites: [refused] }));
  const codes = findings.map((finding) => finding.code);
  assert.equal(codes.includes("upload_request_absent"), true);
  assert.equal(codes.includes("origin_not_allowlisted"), true);
  assert.match(
    describeDeployedCheckFinding(findings.find((f) => f.code === "origin_not_allowlisted")),
    /https:\/\/project-drishti\.tech is absent from the allowlist/,
  );
});

test("a page with no API base url is reported as making no request at all", () => {
  const unconfigured = site({ name: "tech", origin: "https://project-drishti.tech", apiBaseUrl: "", requests: [], responses: [] });
  const codes = analyseDeployedCheck(run({ sites: [unconfigured] })).map((f) => f.code);
  assert.deepEqual(codes, ["page_makes_no_api_request"]);
});

test("a blocked request outranks the allowlist check, because it is what the browser saw", () => {
  const blocked = site({
    name: "tech",
    origin: "https://project-drishti.tech",
    failures: [{ url: API + "/api/analyze", errorText: "net::ERR_FAILED" }],
  });
  const codes = analyseDeployedCheck(run({ sites: [blocked] })).map((f) => f.code);
  assert.equal(codes.includes("browser_blocked_request"), true);
  assert.equal(codes.includes("origin_not_allowlisted"), false);
});

test("an unhealthy API is a finding about the API, not about any one site", () => {
  const findings = analyseDeployedCheck(
    run({ api: { baseUrl: API, health: { status: 503, body: "" }, version: { status: 404 } } }),
  );
  assert.equal(findings[0].code, "api_health_not_ok");
  assert.equal(findings[0].site, null);
});

test("an unreachable api-config.js is a finding, not a missing base url", () => {
  const findings = analyseDeployedCheck(
    run({
      apiConfigs: [{ url: "https://project-drishti.tech/api-config.js", status: 0, error: "TypeError" }],
    }),
  );
  assert.deepEqual(findings.map((f) => f.code), ["api_config_unreachable"]);
});

test("the resolution names the build setting first and the allowlist second", () => {
  const unconfigured = site({
    name: "tech",
    origin: "https://project-drishti.tech",
    apiBaseUrl: "",
    requests: [],
    responses: [],
  });
  const resolution = describeDeployedCheckResolution(run({ sites: [unconfigured] }));
  assert.equal(resolution.length, 2);
  assert.match(resolution[0], /DRISHTI_API_BASE_URL/);
  assert.match(resolution[1], /Add https:\/\/project-drishti\.tech to CORS_ORIGINS/);
  assert.match(resolution[1], /deploy a new revision/);
});

test("one origin reached through two urls is resolved once", () => {
  const unconfigured = site({ origin: "https://project-drishti.tech", apiBaseUrl: "", requests: [], responses: [] });
  const resolution = describeDeployedCheckResolution(run({ sites: [unconfigured, { ...unconfigured, name: "tech-http" }] }));
  assert.equal(resolution.length, 2);
});

test("a fully configured, allowlisted deployment resolves to nothing", () => {
  assert.deepEqual(describeDeployedCheckResolution(run()), []);
});

test("the summary counts allowed origins and sites that reached the API", () => {
  const summary = summariseDeployedCheck(run());
  assert.deepEqual(summary, {
    apiBaseUrl: API,
    healthStatus: 200,
    allowedOrigins: 1,
    probedOrigins: 2,
    sitesWithAnUpload: 1,
  });
});

test("the report records the allowlist, the per-origin upload and the resolution", () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "drishti-report-"));
  const recorded = run({ sites: [site()] });
  writeDeployedCheckReport(recorded, analyseDeployedCheck(recorded), directory);
  const text = fs.readFileSync(path.join(directory, "README.md"), "utf8");
  assert.match(text, /GET \/health` -> 200/);
  assert.match(text, /## Origins the API actually allows/);
  assert.match(text, /## Why a deployed origin fails/);
  assert.match(text, /- nothing is misconfigured/);
  assert.match(text, /allow-origin: https:\/\/project-drishti\.pages\.dev/);
  fs.rmSync(directory, { recursive: true, force: true });
});

test("no response body other than /health is ever written to the report", () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "drishti-report-"));
  const recorded = run();
  writeDeployedCheckReport(recorded, [], directory);
  const text = fs.readFileSync(path.join(directory, "README.md"), "utf8");
  assert.equal(text.includes("iVBORw0KGgo"), false);
  fs.rmSync(directory, { recursive: true, force: true });
});