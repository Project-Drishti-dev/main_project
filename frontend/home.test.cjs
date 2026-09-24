const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const homePath = path.join(__dirname, "home.html");

function createElement() {
  const element = {
    attributes: {},
    listeners: {},
    classNames: new Set(),
    files: [],
    hidden: false,
    disabled: false,
    textContent: "",
    value: "",
    src: "",
    addEventListener(event, callback) {
      this.listeners[event] = callback;
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
    remove(name) {
      element.classNames.delete(name);
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

function loadHomeScript() {
  const ids = [
    "workspace-shell",
    "app-sidebar",
    "sidebar-toggle",
    "sidebar-status",
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
    "screening-source-message",
    "choose-another-image",
    "start-screening",
  ];
  const elements = new Map(ids.map((id) => [id, createElement()]));
  const sidebarOptions = [
    "Previous screenings",
    "Settings",
    "Guide",
    "About",
  ].map((label) => {
    const option = createElement();
    option.setAttribute("data-sidebar-placeholder", label);
    return option;
  });
  const document = {
    body: { style: {} },
    activeElement: null,
    listeners: {},
    getElementById(id) {
      return elements.get(id);
    },
    querySelectorAll(selector) {
      if (selector === "[data-sidebar-placeholder]") return sidebarOptions;
      return [];
    },
    addEventListener(event, callback) {
      this.listeners[event] = callback;
    },
  };
  for (const element of [...elements.values(), ...sidebarOptions]) {
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
    setTimeout(callback) {
      callback();
    },
  });
  return { elements, document, objectUrls, sidebarOptions };
}

test("homescreen keeps the light UX4G theme and uses local UX4G assets", () => {
  const html = fs.readFileSync(homePath, "utf8");

  assert.match(html, /<html lang="en" data-theme="light">/);
  assert.match(html, /node_modules\/ux4g-web-components\/styles\/ux4g\.css/);
  assert.match(html, /node_modules\/ux4g-web-components\/dist\/runtime\/design-system\.js/);
  assert.doesNotMatch(html, /cdn\.ux4g\.gov\.in/);
  assert.match(html, /class="welcome-banner ux4g-card ux4g-p-l"/);
  assert.match(html, /Welcome,\s*User!/);
  assert.match(html, /id="start-screening"[^>]*data-modal-target="#screening-modal"/);
  assert.match(html, /id="screening-modal"[^>]*role="dialog"/);
  assert.match(html, /id="results-modal"[^>]*role="dialog"/);
});

test("homescreen includes a compact expandable sidebar and placeholder options", () => {
  const html = fs.readFileSync(homePath, "utf8");
  const css = fs.readFileSync(path.join(__dirname, "home.css"), "utf8");

  assert.match(html, /id="sidebar-toggle"[^>]*aria-expanded="false"/);
  assert.match(html, /class="profile-avatar/);
  assert.match(css, /\.profile-name\s*\{[^}]*visibility:\s*visible/s);
  assert.match(css, /\.workspace-shell\.is-sidebar-expanded \.sidebar-label/);
  for (const option of [
    "Previous screenings",
    "Settings",
    "Guide",
    "About",
    "Logout",
  ]) {
    assert.ok(html.includes(option), `sidebar should include ${option}`);
  }
  assert.match(html, /href="\.\/index\.html"[^>]*>[\s\S]*?Logout/);
});

test("screening modal offers image upload and camera placeholder options", () => {
  const html = fs.readFileSync(homePath, "utf8");

  assert.match(html, /Upload an image/);
  assert.match(html, /Use camera/);
  assert.match(html, /type="file"[^>]*accept="image\/jpeg,image\/png,image\/webp"/);
  assert.match(html, /id="file-error"[^>]*role="alert"/);
  assert.match(html, /id="image-preview"/);
});

test("selected images stay in the browser and are not sent or persisted", () => {
  const script = fs.readFileSync(path.join(__dirname, "home.js"), "utf8");

  assert.match(script, /URL\.createObjectURL/);
  assert.match(script, /URL\.revokeObjectURL/);
  assert.doesNotMatch(script, /\bfetch\s*\(|XMLHttpRequest|localStorage|sessionStorage|indexedDB/);
});

test("results modal lists all nine checker metrics without inventing results", () => {
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
  assert.match(html, /Python quality checker is not connected/i);
  assert.match(html, /Not run/);
  assert.doesNotMatch(html, /class="metric-status[^"]*">PASS/);
  assert.doesNotMatch(html, /class="metric-status[^"]*">FAIL/);
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

test("sidebar placeholder options announce that they are not implemented", () => {
  const { elements, sidebarOptions } = loadHomeScript();

  sidebarOptions[0].listeners.click();

  assert.match(elements.get("sidebar-status").textContent, /Previous screenings/);
  assert.match(elements.get("sidebar-status").textContent, /placeholder/);
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

test("valid image selection previews locally and opens honest placeholder results", () => {
  const { elements, document, objectUrls } = loadHomeScript();
  const fileInput = elements.get("screening-file");
  const preview = elements.get("image-preview");
  const runButton = elements.get("run-screening");

  fileInput.files = [{ name: "document.webp", type: "image/webp", size: 2048 }];
  fileInput.listeners.change();

  assert.equal(preview.src, "blob:screening-1");
  assert.equal(elements.get("preview-panel").hidden, false);
  assert.equal(runButton.disabled, true);
  preview.naturalWidth = 1200;
  preview.naturalHeight = 800;
  preview.listeners.load();
  assert.equal(runButton.disabled, false);
  assert.match(elements.get("image-dimensions").textContent, /1200 × 800/);
  assert.match(elements.get("file-details").textContent, /document\.webp/);

  runButton.listeners.click();

  assert.equal(elements.get("screening-modal").classList.contains("is-open"), false);
  assert.equal(elements.get("results-modal").classList.contains("is-open"), true);
  assert.equal(document.body.style.overflow, "hidden");
  assert.match(elements.get("results-intro").textContent, /demo preview/i);
  assert.match(elements.get("results-intro").textContent, /not connected/i);
  assert.equal(objectUrls[0].file.name, "document.webp");

  elements.get("choose-another-image").listeners.click();
  assert.equal(elements.get("screening-modal").classList.contains("is-open"), true);
  assert.equal(elements.get("results-modal").classList.contains("is-open"), false);
  assert.equal(objectUrls[1].revoked, "blob:screening-1");
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
