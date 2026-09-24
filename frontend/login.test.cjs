const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

function loadLoginScript() {
  const elements = new Map();
  for (const id of [
    "user-id",
    "password",
    "password-toggle",
    "login-form",
    "form-message",
  ]) {
    elements.set(id, {
      attributes: {},
      listeners: {},
      textContent: "",
      value: "",
      type: id === "password" ? "password" : "",
      addEventListener(event, callback) {
        this.listeners[event] = callback;
      },
      setAttribute(name, value) {
        this.attributes[name] = value;
      },
    });
  }

  const document = {
    getElementById(id) {
      return elements.get(id);
    },
  };
  const source = fs.readFileSync(path.join(__dirname, "login.js"), "utf8");
  const navigation = { href: "" };
  vm.runInNewContext(source, {
    document,
    window: { location: navigation },
  });
  return { elements, navigation };
}

test("password visibility toggles and exposes its state accessibly", () => {
  const { elements } = loadLoginScript();
  const password = elements.get("password");
  const toggle = elements.get("password-toggle");

  toggle.listeners.click();
  assert.equal(password.type, "text");
  assert.equal(toggle.textContent, "Hide");
  assert.equal(toggle.attributes["aria-pressed"], "true");

  toggle.listeners.click();
  assert.equal(password.type, "password");
  assert.equal(toggle.textContent, "Show");
  assert.equal(toggle.attributes["aria-pressed"], "false");
});

test("login redirects to the homescreen regardless of the entered data", () => {
  const { elements, navigation } = loadLoginScript();
  let prevented = false;
  elements.get("user-id").value = "temporary-id";
  elements.get("password").value = "temporary-password";

  elements.get("login-form").listeners.submit({
    preventDefault() {
      prevented = true;
    },
  });

  assert.equal(prevented, true);
  assert.equal(navigation.href, "./home.html");
  assert.equal(elements.get("user-id").value, "");
  assert.equal(elements.get("password").value, "");
});

test("login page uses labeled fields and the pinned default UX4G theme", () => {
  const html = fs.readFileSync(path.join(__dirname, "index.html"), "utf8");
  const css = fs.readFileSync(path.join(__dirname, "login.css"), "utf8");
  const packageJson = JSON.parse(
    fs.readFileSync(path.join(__dirname, "package.json"), "utf8"),
  );

  assert.match(html, /<html lang="en" data-theme="light">/);
  assert.match(html, /for="user-id"/);
  assert.match(html, /for="password"/);
  assert.match(html, /id="login-form"[^>]*novalidate/);
  assert.match(html, /class="ux4g-input ux4g-input-md"/);
  assert.match(html, /data-modal-target="#password-reset-modal"/);
  assert.match(html, /ux4g-modal-backdrop-50 ux4g-modal-backdrop-blur/);
  assert.match(html, /ux4g-modal-box ux4g-modal-m/);
  assert.match(html, /data-close-modal/);
  assert.match(html, /href="\.\/register\.html"/);
  assert.match(html, /node_modules\/ux4g-web-components\/styles\/ux4g\.css/);
  assert.match(html, /node_modules\/ux4g-web-components\/dist\/runtime\/design-system\.js/);
  assert.doesNotMatch(html, /cdn\.ux4g\.gov\.in/);
  assert.equal(packageJson.dependencies["ux4g-web-components"], "2.1.0");
  assert.match(html, /id="password"[\s\S]*?autocomplete="current-password"/);
  assert.doesNotMatch(html, /name="(?:userId|password|account|verificationCode|newPassword|confirmPassword)"/);
  assert.match(css, /color:\s*var\(--ux4g-text-neutral-primary\)/);
  assert.match(css, /linear-gradient/);
  assert.match(css, /place-items:\s*center/);
  assert.match(css, /min-height:\s*34rem/);
});

test("registration page uses matching local UX4G assets and account fields", () => {
  const html = fs.readFileSync(path.join(__dirname, "register.html"), "utf8");

  assert.match(html, /<html lang="en" data-theme="light">/);
  assert.match(html, /id="full-name"/);
  assert.match(html, /id="personnel-id"/);
  assert.match(html, /id="email"[\s\S]*type="email"/);
  assert.match(html, /id="register-password"[\s\S]*autocomplete="new-password"/);
  assert.match(html, /id="confirm-password"/);
  assert.doesNotMatch(html, /name="(?:fullName|personnelId|email|password|confirmPassword)"/);
  assert.match(html, /node_modules\/ux4g-web-components\/styles\/ux4g\.css/);
  assert.match(html, /href="\.\/index\.html"/);
  assert.match(html, /href="\.\/login\.css"/);
  assert.match(html, /ux4g-card ux4g-p-l/);
  assert.match(html, /class="login-visual ux4g-radius-m"/);
  assert.match(html, /no details will be sent or saved/i);
});

test("installed UX4G assets contain the components used by the page", () => {
  const ux4gRoot = path.join(__dirname, "node_modules", "ux4g-web-components");
  const stylesheet = fs.readFileSync(
    path.join(ux4gRoot, "styles", "ux4g.css"),
    "utf8",
  );
  const appStyles = [
    fs.readFileSync(path.join(__dirname, "login.css"), "utf8"),
    fs.readFileSync(path.join(__dirname, "register.css"), "utf8"),
  ].join("\n");
  const runtime = fs.readFileSync(
    path.join(ux4gRoot, "dist", "runtime", "design-system.js"),
    "utf8",
  );

  assert.ok(stylesheet.includes(".ux4g-card"));
  assert.ok(stylesheet.includes(".ux4g-input"));
  assert.ok(stylesheet.includes(".ux4g-btn-primary"));
  assert.ok(stylesheet.includes(".ux4g-modal-backdrop"));
  assert.ok(stylesheet.includes(".ux4g-modal-backdrop-50"));
  assert.ok(stylesheet.includes(".ux4g-modal-backdrop-blur"));
  assert.ok(stylesheet.includes(".ux4g-modal-box"));
  assert.ok(stylesheet.includes(".ux4g-modal-m"));
  assert.ok(stylesheet.includes(".ux4g-radius-m"));
  assert.ok(stylesheet.includes(".ux4g-p-l"));
  assert.ok(stylesheet.includes("--ux4g-bg-neutral-soft"));
  assert.ok(stylesheet.includes("--ux4g-bg-neutral-elevated"));
  assert.ok(stylesheet.includes("--ux4g-bg-primary-strong"));
  assert.ok(stylesheet.includes("--ux4g-text-neutral-primary"));
  assert.ok(stylesheet.includes("--ux4g-text-neutral-secondary"));
  assert.ok(stylesheet.includes("--ux4g-border-color-neutral-strong"));
  assert.ok(
    fs.existsSync(path.join(ux4gRoot, "dist", "runtime", "design-system.js")),
  );
  assert.ok(runtime.includes("data-modal-target"));
  assert.ok(runtime.includes("data-close-modal"));

  const usedTokens = [
    ...new Set(appStyles.match(/var\((--ux4g-[a-z0-9-]+)/g) ?? []),
  ].map((reference) => reference.slice("var(".length));
  for (const token of usedTokens) {
    assert.ok(stylesheet.includes(token), `UX4G token must exist: ${token}`);
  }
});

test("login page omits the workspace brand labels requested for this screen", () => {
  const html = fs.readFileSync(path.join(__dirname, "index.html"), "utf8");
  const css = fs.readFileSync(path.join(__dirname, "login.css"), "utf8");

  assert.doesNotMatch(html, /Document screening workspace/);
  assert.doesNotMatch(html, /Secure document screening/);
  assert.doesNotMatch(html, /class="brand"/);
  assert.match(html, /class="login-panel ux4g-card ux4g-p-l"/);
  assert.match(html, /class="scan-visual" aria-hidden="true"/);
  assert.match(css, /@media \(max-width: 48rem\)/);
  assert.match(css, /--ux4g-bg-primary-strong/);
});
