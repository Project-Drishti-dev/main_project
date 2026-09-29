const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const homePath = path.join(__dirname, "home.html");
const MODULE_KEYS = [
  "sharpness",
  "noise",
  "exposure",
  "uniformity",
  "glare",
  "ppi",
  "skew",
  "coverage",
  "completeness",
];

function createElement(tagName = "div") {
  const element = {
    tagName: tagName.toUpperCase(),
    attributes: {},
    listeners: {},
    classNames: new Set(),
    dataset: {},
    children: [],
    files: [],
    hidden: false,
    disabled: false,
    _textContent: "",
    value: "",
    src: "",
    get textContent() {
      return (
        this._textContent +
        this.children.map((child) => child.textContent).join("")
      );
    },
    set textContent(value) {
      this._textContent = String(value ?? "");
      this.children = [];
    },
    addEventListener(event, callback) {
      this.listeners[event] = callback;
    },
    appendChild(child) {
      this._textContent = "";
      this.children.push(child);
      return child;
    },
    replaceChildren(...children) {
      this._textContent = "";
      this.children = children;
    },
    setAttribute(name, value) {
      this.attributes[name] = value;
    },
    getAttribute(name) {
      return this.attributes[name] ?? null;
    },
    closest() {
      return null;
    },
    querySelector(selector) {
      return this.queryElements?.[selector] ?? null;
    },
    querySelectorAll() {
      return this.focusableElements ?? [];
    },
    removeAttribute(name) {
      delete this.attributes[name];
      if (name === "src") this.src = "";
    },
    focus() {
      this.focused = true;
    },
  };

  element.classList = {
    add(name) {
      element.classNames.add(name);
    },
    remove(...names) {
      for (const name of names) element.classNames.delete(name);
    },
    contains(name) {
      return element.classNames.has(name);
    },
    toggle(name) {
      if (element.classNames.has(name)) {
        element.classNames.delete(name);
        return false;
      }
      element.classNames.add(name);
      return true;
    },
  };

  return element;
}

function createMetricCard(module) {
  const card = createElement();
  card.dataset.module = module;
  card.queryElements = Object.fromEntries(
    ["score", "unit", "status", "rule", "reasons", "details"].map((key) => [
      `[data-metric-${key}]`,
      createElement(key === "details" ? "dl" : "span"),
    ]),
  );
  return card;
}

class MockFormData {
  constructor() {
    this.entries = [];
  }

  append(name, value) {
    this.entries.push([name, value]);
  }
}

function loadHomeScript({
  fetchImpl = async () => {
    throw new Error("Unexpected API request");
  },
  apiBaseUrl = "http://localhost:8080",
} = {}) {
  const ids = [
    "workspace-shell",
    "app-sidebar",
    "sidebar-toggle",
    "source-chooser",
    "upload-step",
    "choose-upload",
    "choose-camera",
    "back-to-source",
    "screening-file",
    "file-error",
    "preview-panel",
    "image-preview",
    "file-details",
    "image-dimensions",
    "run-screening",
    "screening-modal",
    "screening-modal-close",
    "results-modal",
    "results-modal-close",
    "results-intro",
    "overall-result",
    "analysis-status",
    "screening-source-message",
    "choose-another-image",
    "start-screening",
  ];
  const elements = new Map(ids.map((id) => [id, createElement()]));
  const metricCards = MODULE_KEYS.map(createMetricCard);
  const document = {
    body: { style: {} },
    activeElement: null,
    listeners: {},
    getElementById(id) {
      return elements.get(id);
    },
    createElement(tagName) {
      return createElement(tagName);
    },
    querySelectorAll(selector) {
      if (selector === ".metric-card") return metricCards;
      return [];
    },
    addEventListener(event, callback) {
      this.listeners[event] = callback;
    },
  };
  for (const element of elements.values()) {
    element.focus = function focus() {
      this.focused = true;
      document.activeElement = this;
    };
  }
  const objectUrls = [];
  const urlApi = {
    createObjectURL(file) {
      const url = `blob:screening-${objectUrls.length + 1}`;
      objectUrls.push({ file, url });
      return url;
    },
    revokeObjectURL(url) {
      objectUrls.push({ revoked: url });
    },
  };
  const source = fs.readFileSync(path.join(__dirname, "home.js"), "utf8");
  vm.runInNewContext(source, {
    document,
    URL: urlApi,
    FormData: MockFormData,
    fetch: fetchImpl,
    window: { DRISHTI_CONFIG: { apiBaseUrl } },
    setTimeout(callback) {
      callback();
    },
  });
  return { elements, document, metricCards, objectUrls };
}

function makeAnalysisResponse(overrides = {}) {
  return {
    mode: "photo",
    image: { width: 1200, height: 800 },
    trim_box: null,
    overall_pass: false,
    modules: MODULE_KEYS.map((module, index) => ({
      module,
      label: module[0].toUpperCase() + module.slice(1),
      score: index === 2 ? null : 80 + index,
      unit: index === 2 ? "" : "score units",
      passed: index === 2 ? null : index !== 1,
      rule: `${module} threshold rule`,
      reasons: index === 1 ? ["below_threshold"] : [],
      details: { measured: index * 10 },
      mode: "photo",
    })),
    ...overrides,
  };
}

function selectPreviewImage(elements, file = {
  name: "document.webp",
  type: "image/webp",
  size: 2048,
}) {
  elements.get("screening-modal").classList.add("is-open");
  elements.get("source-chooser").hidden = true;
  elements.get("upload-step").hidden = false;
  const fileInput = elements.get("screening-file");
  fileInput.files = [file];
  fileInput.listeners.change();

  const preview = elements.get("image-preview");
  preview.naturalWidth = 1200;
  preview.naturalHeight = 800;
  preview.listeners.load();
  return preview;
}

test("homescreen keeps the light UX4G theme and uses local UX4G assets", () => {
  const html = fs.readFileSync(homePath, "utf8");

  assert.match(html, /<html lang="en" data-theme="light">/);
  assert.match(html, /node_modules\/ux4g-web-components\/styles\/ux4g\.css/);
  assert.match(html, /node_modules\/ux4g-web-components\/dist\/runtime\/design-system\.js/);
  assert.doesNotMatch(html, /cdn\.ux4g\.gov\.in/);
  assert.match(html, /class="welcome-banner ux4g-card ux4g-p-l"/);
  assert.match(html, /PUBLIC PROTOTYPE · NO SIGN-IN/);
  assert.match(html, /DRISHTI image-quality demo/);
  assert.match(html, /Experimental image-quality checks only—not identity\s+verification/);
  assert.match(html, /Use synthetic images; do not upload real identity\s+documents/);
  assert.match(html, /id="start-screening"[^>]*data-modal-target="#screening-modal"/);
  assert.match(html, /id="screening-modal"[^>]*role="dialog"/);
  assert.match(html, /id="results-modal"[^>]*role="dialog"/);
  assert.doesNotMatch(html, /type="password"|Forgot password\?|Personnel ID|Register/);
});

test("homescreen includes a compact expandable sidebar with working navigation", () => {
  const html = fs.readFileSync(homePath, "utf8");
  const css = fs.readFileSync(path.join(__dirname, "home.css"), "utf8");

  assert.match(html, /id="sidebar-toggle"[^>]*aria-expanded="false"/);
  assert.match(html, /class="profile-avatar/);
  assert.match(css, /\.profile-name\s*\{[^}]*visibility:\s*visible/s);
  assert.match(css, /\.workspace-shell\.is-sidebar-expanded \.sidebar-label/);
  for (const [href, label] of [
    ["./home.html", "Overview"],
    ["./screenings.html", "Previous screenings"],
    ["./profile.html", "Profile"],
    ["./settings.html", "Settings"],
    ["./guide.html", "Guide"],
    ["./about.html", "About"],
  ]) {
    assert.ok(html.includes(label), `sidebar should include ${label}`);
    assert.match(
      html,
      new RegExp(`href="${href.replace(".", "\\.")}"`),
      `sidebar should link to ${href}`,
    );
  }
  assert.match(html, /href="\.\/home\.html"[^>]*aria-current="page"|aria-current="page"[^>]*href="\.\/home\.html"/);
  assert.match(html, /data-nav="home"/);
  assert.doesNotMatch(html, /data-sidebar-placeholder/);
  assert.doesNotMatch(html, /sidebar-status/);
  assert.doesNotMatch(html, /Logout|sidebar-logout/);
});

test("screening modal offers image upload and camera placeholder options", () => {
  const html = fs.readFileSync(homePath, "utf8");

  assert.match(html, /Upload an image/);
  assert.match(html, /Use camera/);
  assert.match(html, /type="file"[^>]*accept="image\/jpeg,image\/png,image\/webp"/);
  assert.match(html, /id="file-error"[^>]*role="alert"/);
  assert.match(html, /id="image-preview"/);
});

test("selected images preview locally and are sent only when analysis is requested", () => {
  const script = fs.readFileSync(path.join(__dirname, "home.js"), "utf8");

  assert.match(script, /URL\.createObjectURL/);
  assert.match(script, /URL\.revokeObjectURL/);
  assert.match(script, /\bfetch\s*\(/);
  assert.match(script, /new FormData/);
  assert.doesNotMatch(script, /localStorage|sessionStorage|indexedDB/);
});

test("results modal lists all nine metrics and identifies the prototype thresholds", () => {
  const html = fs.readFileSync(homePath, "utf8");
  const expectedMetrics = [
    "Sharpness",
    "Noise",
    "Exposure",
    "Lighting uniformity",
    "Glare",
    "Resolution (PPI)",
    "Skew / perspective",
    "Card coverage",
    "Completeness (cut/crop)",
  ];

  for (const metric of expectedMetrics) {
    assert.ok(html.includes(metric), `results should include ${metric}`);
  }
  assert.match(html, /experimental/i);
  assert.match(html, /identity-verification decision/i);
  assert.match(html, /Not run/);
  assert.doesNotMatch(html, /class="metric-status[^"]*">PASS/);
  assert.doesNotMatch(html, /class="metric-status[^"]*">FAIL/);
  assert.match(html, /data-metric-rule/);
  assert.match(html, /data-metric-reasons/);
  assert.match(html, /<dl class="metric-details" data-metric-details><\/dl>/);
  assert.match(html, /id="analysis-status"[^>]*aria-live="polite"/);
  assert.match(html, /sent to the configured[\s\S]*analysis API/i);
});

test("homescreen uses only installed UX4G tokens and keeps hidden upload content hidden", () => {
  const css = fs.readFileSync(path.join(__dirname, "home.css"), "utf8");
  const ux4gStylesheet = fs.readFileSync(
    path.join(__dirname, "node_modules", "ux4g-web-components", "styles", "ux4g.css"),
    "utf8",
  );
  const usedTokens = [
    ...new Set([...css.matchAll(/var\((--ux4g-[a-z0-9-]+)/g)].map((match) => match[1])),
  ];

  assert.match(css, /\.upload-step\[hidden\][\s\S]*display:\s*none/);
  assert.match(css, /\.preview-panel\[hidden\][\s\S]*display:\s*none/);
  for (const token of usedTokens) {
    assert.ok(ux4gStylesheet.includes(token), `UX4G token must exist: ${token}`);
  }
});

test("sidebar expands and updates its accessible state", () => {
  const { elements } = loadHomeScript();
  const sidebar = elements.get("app-sidebar");
  const toggle = elements.get("sidebar-toggle");

  toggle.listeners.click();
  assert.equal(sidebar.classList.contains("is-expanded"), true);
  assert.equal(toggle.attributes["aria-expanded"], "true");

  toggle.listeners.click();
  assert.equal(sidebar.classList.contains("is-expanded"), false);
  assert.equal(toggle.attributes["aria-expanded"], "false");
});

test("screening modal traps keyboard focus within the open dialog", () => {
  const { elements, document } = loadHomeScript();
  const modal = elements.get("screening-modal");
  const closeButton = elements.get("screening-modal-close");
  const uploadButton = elements.get("choose-upload");
  const cameraButton = elements.get("choose-camera");
  modal.focusableElements = [closeButton, uploadButton, cameraButton];
  modal.classList.add("is-open");

  elements.get("start-screening").listeners.click();
  closeButton.focus();
  const event = {
    key: "Tab",
    shiftKey: true,
    prevented: false,
    preventDefault() {
      this.prevented = true;
    },
  };
  modal.listeners.keydown(event);

  assert.equal(event.prevented, true);
  assert.equal(document.activeElement, cameraButton);
});

test("closing and reopening screening returns to the source choices", () => {
  const { elements } = loadHomeScript();
  const sourceChooser = elements.get("source-chooser");
  const uploadStep = elements.get("upload-step");
  const modal = elements.get("screening-modal");

  elements.get("choose-upload").listeners.click();
  assert.equal(sourceChooser.hidden, true);
  assert.equal(uploadStep.hidden, false);

  modal.listeners.click({ target: modal });
  elements.get("start-screening").listeners.click();

  assert.equal(sourceChooser.hidden, false);
  assert.equal(uploadStep.hidden, true);
});

test("valid image selection previews locally without requesting analysis", () => {
  let requestCount = 0;
  const { elements, objectUrls } = loadHomeScript({
    fetchImpl: async () => {
      requestCount += 1;
      return { ok: true, json: async () => makeAnalysisResponse() };
    },
  });
  const runButton = elements.get("run-screening");

  const preview = selectPreviewImage(elements);

  assert.equal(preview.src, "blob:screening-1");
  assert.equal(elements.get("preview-panel").hidden, false);
  assert.equal(runButton.disabled, false);
  assert.match(elements.get("image-dimensions").textContent, /1200 × 800/);
  assert.match(elements.get("file-details").textContent, /document\.webp/);
  assert.equal(requestCount, 0);
  assert.equal(objectUrls[0].file.name, "document.webp");
});

test("analysis posts the selected image and renders all API results as text", async () => {
  const calls = [];
  const payload = makeAnalysisResponse({
    modules: makeAnalysisResponse().modules.map((module, index) =>
      index === 0
        ? {
            ...module,
            label: "<img src=x onerror=alert(1)>",
            reasons: ["<script>untrusted</script>"],
            details: {
              measured: "<b>raw text</b>",
              measurement_window: { samples: 3, reliable: true },
              edges: ["top", "right"],
            },
          }
        : index === 1
          ? {
              ...module,
              details: {
                "whole_image_sigma (inflated by text edges)": 6.39,
                perfectly_flat_pixel_fraction: 0.7,
                measured_at: "native resolution 455x593",
              },
            }
          : module,
    ),
  });
  const { elements, document, metricCards, objectUrls } = loadHomeScript({
    fetchImpl: async (url, options) => {
      calls.push({ url, options });
      return { ok: true, json: async () => payload };
    },
  });
  selectPreviewImage(elements);

  await elements.get("run-screening").listeners.click();

  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, "http://localhost:8080/api/analyze");
  assert.equal(calls[0].options.method, "POST");
  assert.equal(calls[0].options.headers, undefined);
  assert.deepEqual(
    calls[0].options.body.entries.map(([name]) => name),
    ["image", "mode"],
  );
  assert.equal(calls[0].options.body.entries[0][1].name, "document.webp");
  assert.equal(calls[0].options.body.entries[1][1], "auto");

  assert.equal(elements.get("screening-modal").classList.contains("is-open"), false);
  assert.equal(elements.get("results-modal").classList.contains("is-open"), true);
  assert.equal(document.body.style.overflow, "hidden");
  assert.match(elements.get("results-intro").textContent, /1200 × 800/);
  assert.match(elements.get("overall-result").textContent, /needs attention/i);
  assert.equal(metricCards.length, 9);
  assert.match(metricCards[0].querySelector("[data-metric-status]").textContent, /pass/i);
  assert.equal(
    metricCards[0].querySelector("[data-metric-rule]").textContent,
    "sharpness threshold rule",
  );
  assert.match(
    metricCards[0].querySelector("[data-metric-reasons]").textContent,
    /<script>untrusted<\/script>/,
  );
  const sharpnessDetails = metricCards[0].querySelector("[data-metric-details]");
  assert.deepEqual(
    sharpnessDetails.children.map((row) => row.children[0].textContent),
    ["Measured", "Measurement window", "Edges"],
  );
  assert.equal(sharpnessDetails.children[0].children[1].textContent, "<b>raw text</b>");
  assert.equal(
    sharpnessDetails.children[1].children[1].textContent,
    "Samples: 3; Reliable: Yes",
  );
  assert.equal(sharpnessDetails.children[2].children[1].textContent, "top, right");
  assert.doesNotMatch(sharpnessDetails.textContent, /[{}"]/);

  const noiseDetails = metricCards[1].querySelector("[data-metric-details]");
  assert.deepEqual(
    noiseDetails.children.map((row) => row.children[0].textContent),
    [
      "Whole image sigma (inflated by text edges)",
      "Perfectly flat pixel fraction",
      "Measured at",
    ],
  );
  assert.deepEqual(
    noiseDetails.children.map((row) => row.children[1].textContent),
    ["6.39", "0.7", "native resolution 455x593"],
  );
  assert.doesNotMatch(noiseDetails.textContent, /[{}"]/);
  assert.equal(metricCards[1].querySelector("[data-metric-status]").textContent, "Fail");
  assert.equal(
    metricCards[2].querySelector("[data-metric-status]").textContent,
    "N/A",
  );
  assert.equal(metricCards[0].innerHTML, undefined);

  elements.get("choose-another-image").listeners.click();
  assert.equal(elements.get("screening-modal").classList.contains("is-open"), true);
  assert.equal(elements.get("results-modal").classList.contains("is-open"), false);
  assert.equal(objectUrls[1].revoked, "blob:screening-1");
});

test("analysis exposes loading state and ignores duplicate submissions", async () => {
  let resolveRequest;
  let requestCount = 0;
  const { elements } = loadHomeScript({
    fetchImpl: () => {
      requestCount += 1;
      return new Promise((resolve) => {
        resolveRequest = resolve;
      });
    },
  });
  selectPreviewImage(elements);
  const runButton = elements.get("run-screening");

  const firstRequest = runButton.listeners.click();
  assert.equal(runButton.disabled, true);
  assert.equal(elements.get("screening-file").disabled, true);
  assert.equal(elements.get("back-to-source").disabled, true);
  assert.equal(elements.get("screening-modal-close").disabled, true);
  assert.match(elements.get("analysis-status").textContent, /analyzing/i);
  assert.equal(elements.get("analysis-status").focused, true);
  const duplicateRequest = runButton.listeners.click();
  assert.equal(requestCount, 1);

  resolveRequest({ ok: true, json: async () => makeAnalysisResponse() });
  await Promise.all([firstRequest, duplicateRequest]);
  assert.equal(runButton.disabled, false);
  assert.equal(elements.get("screening-file").disabled, false);
  assert.equal(elements.get("results-modal").classList.contains("is-open"), true);
  assert.equal(elements.get("results-modal-close").focused, true);
});

test("checker module errors still render when the backend reports its internal module name", async () => {
  const response = makeAnalysisResponse();
  response.modules[0] = {
    ...response.modules[0],
    module: "app.quality_checker.m1_sharpness",
    label: "Sharpness",
    passed: false,
    reasons: ["module_error"],
  };
  const { elements, metricCards } = loadHomeScript({
    fetchImpl: async () => ({
      ok: true,
      json: async () => response,
    }),
  });
  selectPreviewImage(elements);
  await elements.get("run-screening").listeners.click();

  assert.equal(elements.get("results-modal").classList.contains("is-open"), true);
  assert.equal(
    metricCards[0].querySelector("[data-metric-status]").textContent,
    "Fail",
  );
  assert.match(
    metricCards[0].querySelector("[data-metric-reasons]").textContent,
    /module_error/,
  );
});

test("API and network errors stay in the upload flow and allow retry", async () => {
  const cases = [
    {
      fetchImpl: async () => {
        throw new TypeError("Failed to fetch");
      },
      expectedMessage: /could not connect|unable to reach/i,
    },
    {
      fetchImpl: async () => ({
        ok: false,
        json: async () => ({
          error: { code: "IMAGE_TOO_LARGE", message: "The image is too large." },
        }),
      }),
      expectedMessage: /too large/i,
    },
  ];

  for (const { fetchImpl, expectedMessage } of cases) {
    const { elements } = loadHomeScript({ fetchImpl });
    selectPreviewImage(elements);
    const runButton = elements.get("run-screening");

    await runButton.listeners.click();

    assert.equal(elements.get("screening-modal").classList.contains("is-open"), true);
    assert.equal(elements.get("results-modal").classList.contains("is-open"), false);
    assert.equal(runButton.disabled, false);
    assert.match(elements.get("file-error").textContent, expectedMessage);
    assert.equal(elements.get("analysis-status").textContent, "");
    assert.equal(runButton.focused, true);
  }
});

test("malformed API responses are rejected without rendering partial results", async () => {
  const { elements } = loadHomeScript({
    fetchImpl: async () => ({
      ok: true,
      json: async () => ({ modules: [{ label: "<script>invalid</script>" }] }),
    }),
  });
  selectPreviewImage(elements);
  await elements.get("run-screening").listeners.click();

  assert.equal(elements.get("results-modal").classList.contains("is-open"), false);
  assert.match(elements.get("file-error").textContent, /unexpected response/i);
});

test("API config selects localhost only for local development", () => {
  const source = fs.readFileSync(path.join(__dirname, "api-config.js"), "utf8");
  const localWindow = { location: { hostname: "localhost" } };
  vm.runInNewContext(source, { window: localWindow });
  assert.equal(localWindow.DRISHTI_CONFIG.apiBaseUrl, "http://localhost:8080");

  const deployedWindow = { location: { hostname: "drishti.pages.dev" } };
  vm.runInNewContext(source, { window: deployedWindow });
  assert.equal(deployedWindow.DRISHTI_CONFIG.apiBaseUrl, "");
});

test("unsupported and oversized files are rejected without enabling screening", () => {
  for (const file of [
    { name: "notes.txt", type: "text/plain", size: 100 },
    { name: "large.png", type: "image/png", size: 11 * 1024 * 1024 },
  ]) {
    const { elements } = loadHomeScript();
    const fileInput = elements.get("screening-file");
    fileInput.files = [file];
    fileInput.listeners.change();

    assert.equal(elements.get("run-screening").disabled, true);
    assert.equal(elements.get("preview-panel").hidden, true);
    assert.notEqual(elements.get("file-error").textContent, "");
  }
});

test("unreadable image previews are cleared and cannot be screened", () => {
  const { elements, objectUrls } = loadHomeScript();
  const fileInput = elements.get("screening-file");
  fileInput.files = [{ name: "broken.png", type: "image/png", size: 500 }];
  fileInput.listeners.change();

  elements.get("image-preview").listeners.error();

  assert.equal(elements.get("run-screening").disabled, true);
  assert.equal(elements.get("preview-panel").hidden, true);
  assert.match(elements.get("file-error").textContent, /could not be opened/i);
  assert.equal(objectUrls[1].revoked, "blob:screening-1");
});

test("camera option explains that capture is not implemented yet", () => {
  const { elements } = loadHomeScript();

  elements.get("choose-camera").listeners.click();

  assert.match(elements.get("screening-source-message").textContent, /coming soon/i);
});
