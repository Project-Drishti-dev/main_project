const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const PAGE_FILES = [
  "home.html",
  "screenings.html",
  "settings.html",
  "guide.html",
  "about.html",
  "profile.html",
];
const NAV_LINKS = [
  ["./home.html", "Overview"],
  ["./screenings.html", "Previous screenings"],
  ["./profile.html", "Profile"],
  ["./settings.html", "Settings"],
  ["./guide.html", "Guide"],
  ["./about.html", "About"],
];
const NAV_ACTIVE_FOR = {
  "home.html": "home",
  "screenings.html": "screenings",
  "settings.html": "settings",
  "guide.html": "guide",
  "about.html": "about",
  "profile.html": "profile",
};

function readFront(fileName) {
  return fs.readFileSync(path.join(__dirname, fileName), "utf8");
}

/* ---------- preferences.js ---------- */

function createStorage(initial = {}) {
  const values = new Map(Object.entries(initial));
  return {
    values,
    setItem(key, value) {
      values.set(key, String(value));
    },
    getItem(key) {
      return values.has(key) ? values.get(key) : null;
    },
    removeItem(key) {
      values.delete(key);
    },
  };
}

function loadPreferences({ storage = createStorage(), matchMedia } = {}) {
  const root = {
    attributes: {},
    setAttribute(name, value) {
      this.attributes[name] = value;
    },
    getAttribute(name) {
      return this.attributes[name] ?? null;
    },
  };
  const window = { localStorage: storage };
  if (matchMedia) window.matchMedia = matchMedia;

  vm.runInNewContext(readFront("preferences.js"), {
    document: { documentElement: root },
    window,
  });

  return { root, window, storage };
}

test("preferences default to the light theme and default text size", () => {
  const { root, window } = loadPreferences();

  assert.deepEqual(
    JSON.parse(JSON.stringify(window.DRISHTI_PREFERENCES.read())),
    { theme: "light", textSize: "default" },
  );
  assert.equal(root.getAttribute("data-theme"), "light");
  assert.equal(root.getAttribute("data-text-size"), "default");
});

test("preferences apply and persist theme and text size choices", () => {
  const { root, window, storage } = loadPreferences();

  window.DRISHTI_PREFERENCES.set({ theme: "dark", textSize: "x-large" });

  assert.equal(root.getAttribute("data-theme"), "dark");
  assert.equal(root.getAttribute("data-text-size"), "x-large");
  assert.equal(root.getAttribute("data-theme-preference"), "dark");
  assert.deepEqual(
    JSON.parse(storage.getItem("drishti.preferences.v1")),
    { theme: "dark", textSize: "x-large" },
  );

  const reloaded = loadPreferences({ storage });
  assert.equal(reloaded.root.getAttribute("data-theme"), "dark");
  assert.equal(reloaded.root.getAttribute("data-text-size"), "x-large");
});

test("preferences ignore unknown values and survive corrupt storage", () => {
  const { window } = loadPreferences({
    storage: createStorage({
      "drishti.preferences.v1": '{"theme":"neon","textSize":"huge"}',
    }),
  });

  assert.deepEqual(
    JSON.parse(JSON.stringify(window.DRISHTI_PREFERENCES.read())),
    { theme: "light", textSize: "default" },
  );

  const corrupt = loadPreferences({
    storage: createStorage({ "drishti.preferences.v1": "not json" }),
  });
  assert.deepEqual(
    JSON.parse(JSON.stringify(corrupt.window.DRISHTI_PREFERENCES.read())),
    { theme: "light", textSize: "default" },
  );
});

test("system theme follows the device colour scheme", () => {
  const listeners = [];
  const media = {
    matches: true,
    addEventListener(event, callback) {
      listeners.push({ event, callback });
    },
  };
  const { root, window } = loadPreferences({ matchMedia: () => media });

  window.DRISHTI_PREFERENCES.set({ theme: "system" });
  assert.equal(root.getAttribute("data-theme"), "dark");
  assert.equal(root.getAttribute("data-theme-preference"), "system");

  media.matches = false;
  for (const { event, callback } of listeners) {
    if (event === "change") callback();
  }
  assert.equal(root.getAttribute("data-theme"), "light");
});

test("preferences fall back to defaults when storage is unavailable", () => {
  const blocked = {
    setItem() {
      throw new Error("blocked");
    },
    getItem() {
      throw new Error("blocked");
    },
    removeItem() {
      throw new Error("blocked");
    },
  };
  const { root, window } = loadPreferences({ storage: blocked });

  assert.deepEqual(
    JSON.parse(JSON.stringify(window.DRISHTI_PREFERENCES.read())),
    { theme: "light", textSize: "default" },
  );
  assert.equal(root.getAttribute("data-theme"), "light");

  window.DRISHTI_PREFERENCES.set({ theme: "dark" });
  assert.equal(root.getAttribute("data-theme"), "dark");
});

test("resetting preferences restores the defaults", () => {
  const { root, window } = loadPreferences();
  window.DRISHTI_PREFERENCES.set({ theme: "dark", textSize: "large" });

  window.DRISHTI_PREFERENCES.reset();

  assert.equal(root.getAttribute("data-theme"), "light");
  assert.equal(root.getAttribute("data-text-size"), "default");
});

/* ---------- shared page shell ---------- */

test("every page ships the shared shell, theme default and local UX4G assets", () => {
  for (const fileName of PAGE_FILES) {
    const html = readFront(fileName);
    assert.match(html, /<html lang="en" data-theme="light">/, fileName);
    assert.match(html, /node_modules\/ux4g-web-components\/styles\/ux4g\.css/, fileName);
    assert.match(
      html,
      /node_modules\/ux4g-web-components\/dist\/runtime\/design-system\.js/,
      fileName,
    );
    assert.doesNotMatch(html, /cdn\.ux4g\.gov\.in/, fileName);
    assert.match(html, /href="\.\/pages\.css"/, fileName);
    assert.match(html, /src="\.\/preferences\.js"/, fileName);
    assert.match(html, /src="\.\/(home|pages)\.js"/, fileName);
    assert.match(html, /id="sidebar-toggle"/, fileName);
    assert.match(html, /aria-label="Workspace sidebar"/, fileName);
    assert.match(html, /class="workspace-footer"/, fileName);
  }
});

test("secondary pages load the shared page script and the demo keeps home.js", () => {
  assert.match(readFront("home.html"), /src="\.\/home\.js"/);
  for (const fileName of PAGE_FILES.filter((name) => name !== "home.html")) {
    assert.match(readFront(fileName), /src="\.\/pages\.js"/, fileName);
  }
});

test("every page exposes the same navigation and marks only itself current", () => {
  for (const fileName of PAGE_FILES) {
    const html = readFront(fileName);
    for (const [href, label] of NAV_LINKS) {
      assert.ok(html.includes(label), `${fileName} should link to ${label}`);
      assert.ok(
        html.includes(`href="${href}"`),
        `${fileName} should link to ${href}`,
      );
    }
    const currentMatches = html.match(/aria-current="page"/g) ?? [];
    const sidebarCurrent = (html.match(
      /class="sidebar-link[^"]*"[\s\S]{0,220}?aria-current="page"/g,
    ) ?? []).length;
    assert.equal(sidebarCurrent, 1, `${fileName} should mark one nav item`);
    assert.ok(
      currentMatches.length >= 1,
      `${fileName} should mark the current page`,
    );
    assert.match(
      html,
      new RegExp(`data-nav="${NAV_ACTIVE_FOR[fileName]}"`),
      `${fileName} should mark its own nav item`,
    );
  }
});

test("no page collects credentials or offers a sign-out", () => {
  for (const fileName of PAGE_FILES) {
    const html = readFront(fileName);
    assert.doesNotMatch(
      html,
      /type="password"|Forgot password\?|Personnel ID|Verification code|<form[^>]*action/i,
      fileName,
    );
    assert.doesNotMatch(html, /Logout|Sign out|sidebar-logout/, fileName);
  }
});

test("alerts use the documented UX4G composition rather than custom markup", () => {
  for (const fileName of PAGE_FILES) {
    const html = readFront(fileName);
    const alerts = html.match(/<div class="ux4g-alert[^"]*"[^>]*>/g) ?? [];
    for (const alert of alerts) {
      assert.match(alert, /class="ux4g-alert ux4g-alert-(info|success|warning|error)"/);
    }
    assert.doesNotMatch(html, /settings-note/, fileName);
  }
});

test("page styles only reference UX4G tokens that exist in the package", () => {
  const css = readFront("pages.css");
  const ux4gStylesheet = fs.readFileSync(
    path.join(__dirname, "node_modules", "ux4g-web-components", "styles", "ux4g.css"),
    "utf8",
  );
  const usedTokens = [
    ...new Set([...css.matchAll(/var\((--ux4g-[a-z0-9-]+)/g)].map((match) => match[1])),
  ];

  assert.ok(usedTokens.length > 20, "pages.css should use UX4G tokens");
  for (const token of usedTokens) {
    assert.ok(ux4gStylesheet.includes(token), `UX4G token must exist: ${token}`);
  }
});

test("text size scaling uses root font size and only known size keys", () => {
  const css = readFront("pages.css");
  assert.match(css, /html\[data-text-size="large"\][^}]*font-size:\s*112\.5%/);
  assert.match(css, /html\[data-text-size="x-large"\][^}]*font-size:\s*125%/);
  assert.doesNotMatch(css, /html\s*\{[^}]*font-size/);
});

test("hidden rows and panels stay hidden under the installed UX4G stylesheet", () => {
  const ux4gStylesheet = fs.readFileSync(
    path.join(__dirname, "node_modules", "ux4g-web-components", "styles", "ux4g.css"),
    "utf8",
  );

  assert.doesNotMatch(
    ux4gStylesheet,
    /\[hidden\]\s*\{/,
    "UX4G should not define its own [hidden] helper",
  );

  // The elements given [hidden] are table rows and .ux4g-card-body. Only rules
  // whose selector list contains exactly those compounds can override the UA
  // [hidden] { display: none } rule, so check those and nothing broader.
  const rules = ux4gStylesheet.match(/[^{}]+\{[^{}]*\}/g) ?? [];
  const offenders = [];
  for (const rule of rules) {
    const braceIndex = rule.indexOf("{");
    const selectorList = rule.slice(0, braceIndex);
    const declarations = rule.slice(braceIndex);
    if (!/display:/.test(declarations)) continue;

    const compounds = selectorList.split(",").map((part) => part.trim());
    if (compounds.some((selector) => selector === "tr" || selector === ".ux4g-card-body")) {
      offenders.push(selectorList.replace(/\s+/g, " ").slice(0, 120));
    }
  }
  assert.deepEqual(
    offenders,
    [],
    "these rules would defeat the hidden attribute on rows or card bodies",
  );

  assert.match(
    readFront("pages.js"),
    /row\.hidden = !matching\.includes\(row\)/,
    "filtering relies on the hidden attribute",
  );
});

/* ---------- page content ---------- */

test("previous screenings renders a table of sample records with filters", () => {
  const html = readFront("screenings.html");

  assert.match(html, /<table class="ux4g-table ux4g-table-m/);
  assert.match(html, /<caption class="visually-hidden">/);
  assert.equal((html.match(/<tbody id="screenings-body">/) ?? []).length, 1);
  assert.equal((html.match(/<tr data-result="/g) ?? []).length, 6);
  assert.equal((html.match(/<th scope="col"/g) ?? []).length, 7);
  assert.match(html, /ux4g-tag-filled-success/);
  assert.match(html, /ux4g-tag-filled-warning/);
  assert.match(html, /id="screening-search"/);
  assert.match(html, /data-filter="all"/);
  assert.match(html, /data-filter="pass"/);
  assert.match(html, /data-filter="attention"/);
  assert.match(html, /id="screenings-empty"[^>]*hidden/);
  assert.match(html, /ux4g-empty-state/);
  assert.match(html, /id="result-count"[^>]*aria-live="polite"/);
  assert.match(html, /class="ux4g-pagination/);
  assert.match(html, /<time datetime="2026-09-30T09:12">/);
  assert.match(html, /Sample data\./);
});

test("settings offers working theme and text size controls plus placeholder switches", () => {
  const html = readFront("settings.html");

  assert.match(html, /role="radiogroup"[^>]*id="theme-options"|id="theme-options"[\s\S]{0,120}role="radiogroup"/);
  for (const value of ["light", "dark", "system"]) {
    assert.ok(
      html.includes(`name="theme"\n                    value="${value}"`) ||
        html.includes(`value="${value}"`),
      `theme option ${value} should exist`,
    );
  }
  assert.match(html, /id="text-size-options"/);
  for (const value of ["default", "large", "x-large"]) {
    assert.ok(html.includes(`value="${value}"`), `text size ${value} should exist`);
  }
  assert.match(html, /name="theme"[\s\S]{0,80}value="light"[\s\S]{0,80}checked/);
  assert.match(html, /id="reset-preferences"/);
  assert.match(html, /class="ux4g-switch ux4g-switch-md"/);
  assert.match(html, /class="ux4g-radio ux4g-radio-md"/);
  assert.match(html, /data-placeholder-switch/);
  assert.match(html, /id="text-size-summary"/);
});

test("guide explains all nine checks and how to prepare an image", () => {
  const html = readFront("guide.html");

  assert.match(html, /class="ux4g-accordion ux4g-accordion-arrow-right guide-accordion"/);
  assert.equal(
    (html.match(/data-ux4g-accordion-toggle/g) ?? []).length,
    9,
    "guide should explain all nine checks",
  );
  assert.equal(
    (html.match(/class="ux4g-accordion__collapse/g) ?? []).length,
    9,
    "every accordion item needs a collapse region",
  );
  assert.equal(
    (html.match(/class="ux4g-accordion__button"/g) ?? []).length,
    9,
    "every accordion item needs the interactive button",
  );
  assert.doesNotMatch(
    html,
    /ux4g-accordion-bordered/,
    "bordered accordion items render as plain boxes",
  );
  assert.equal(
    (html.match(/aria-controls="check-/g) ?? []).length,
    9,
    "every toggle should point at its collapse region",
  );
  for (const label of [
    "Sharpness",
    "Noise",
    "Exposure",
    "Lighting uniformity",
    "Glare",
    "Resolution (PPI)",
    "Skew / perspective",
    "Card coverage",
    "Completeness (cut\/crop)",
  ]) {
    assert.ok(html.includes(label), `guide should cover ${label}`);
  }
  assert.match(html, /ux4g-stepper ux4g-stepper-horizontal ux4g-stepper-center guide-stepper/);
  assert.equal(
    (html.match(/class="ux4g-stepper-head"/g) ?? []).length,
    4,
    "stepper needs a head per step",
  );
  assert.equal(
    (html.match(/class="ux4g-stepper-head-icon"/g) ?? []).length,
    4,
    "stepper needs a head icon per step",
  );
  for (const classAttribute of html.match(/class="ux4g-stepper-step[^"]*"/g) ?? []) {
    const tokens = classAttribute.split(/[\s"]+/);
    assert.ok(
      !tokens.includes("completed") && !tokens.includes("active"),
      `stepper steps must use ux4g-stepper-completed, not a bare token: ${classAttribute}`,
    );
  }
  assert.match(html, /ux4g-stepper-step ux4g-stepper-completed/);
  assert.match(html, /class="checklist"/);
  assert.match(html, /ux4g-alert-warning/);
});

test("the accordion runtime gap is real and pages.js supplies the toggle", () => {
  const runtime = fs.readFileSync(
    path.join(
      __dirname,
      "node_modules",
      "ux4g-web-components",
      "dist",
      "runtime",
      "design-system.js",
    ),
    "utf8",
  );
  assert.equal(
    runtime.includes("ux4g-accordion"),
    false,
    "if UX4G ever ships accordion behaviour, this fallback can be removed",
  );

  const script = readFront("pages.js");
  assert.match(script, /function initAccordions\(\)/);
  assert.match(script, /\[data-ux4g-accordion-toggle\]/);
  assert.match(script, /aria-expanded/);
  assert.match(script, /classList\.toggle\("show", !expanded\)/);
  assert.match(script, /collapse\.hidden = expanded/);
  assert.match(script, /initAccordions\(\);/);
});

test("the stepper connector workaround targets the malformed shipped selector", () => {
  const css = readFront("pages.css");
  const ux4gStylesheet = fs.readFileSync(
    path.join(__dirname, "node_modules", "ux4g-web-components", "styles", "ux4g.css"),
    "utf8",
  );

  assert.ok(
    ux4gStylesheet.includes(".ux4g-stepper-center):not("),
    "the shipped malformed selector should still be present for this comment to hold",
  );
  assert.match(
    css,
    /\.guide-stepper \.ux4g-stepper-step:not\(:last-child\)::after/,
  );
  assert.match(
    css,
    /\.guide-stepper \.ux4g-stepper-step\.ux4g-stepper-done:not\(:last-child\)::after/,
  );
});

test("about page carries placeholder content and honest limitations", () => {
  const html = readFront("about.html");

  assert.match(html, /class="spec-grid"/);
  assert.match(html, /0\.4\.0 \(prototype\)/);
  assert.match(html, /<dt>Accounts<\/dt>\s*<dd>None<\/dd>/);
  assert.match(html, /Known limitations/);
  assert.match(html, /ux4g-list-warning/);
  assert.match(html, /not an identity-verification service/);
  assert.match(html, /href="\.\/guide\.html"/);
});

test("profile page shows identity details without collecting a password", () => {
  const html = readFront("profile.html");

  assert.match(html, /ux4g-avatar ux4g-avatar-profile ux4g-avatar-2xl/);
  assert.match(html, /id="avatar-file"[\s\S]{0,120}accept="image\/jpeg,image\/png,image\/webp"/);
  assert.match(html, /for="avatar-file"\s*>\s*Change photo/);
  assert.match(html, /id="remove-photo"/);
  assert.match(html, /class="ux4g-label-m-default"[^>]*for="profile-name"/);
  assert.match(html, /class="ux4g-input-input"[\s\S]{0,120}name="name"/);
  assert.match(html, /class="ux4g-input-input"[\s\S]{0,160}type="email"/);
  assert.match(html, /<dt>Role<\/dt>/);
  assert.match(html, /id="change-password"/);
  assert.match(html, /id="change-password"[\s\S]{0,400}aria-disabled="true"/);
  assert.doesNotMatch(html, /type="password"/);
  assert.match(html, /There is no account or stored\s+password to change/);
  assert.match(html, /Sample profile\./);
});

test("profile layout keeps security full width below the two column area", () => {
  const html = readFront("profile.html");
  const gridStart = html.indexOf('<div class="profile-grid">');
  const securityStart = html.indexOf('aria-labelledby="security-title"');

  assert.ok(
    gridStart > 0 && securityStart > gridStart,
    "the security card should follow the profile grid",
  );
  assert.ok(
    !html.slice(gridStart, securityStart).includes('aria-labelledby="security-title"'),
    "the security card should sit outside the profile grid, not stacked in a column",
  );
  assert.match(
    html.slice(securityStart - 200, securityStart),
    /<\/div>\s*<section/,
    "the grid should be closed before the security card opens",
  );
  assert.equal(
    (html.match(/class="security-grid"/g) ?? []).length,
    1,
    "security rows should use the three column layout",
  );
  assert.doesNotMatch(
    html,
    /<div class="settings-group">\s*<section[^>]*aria-labelledby="details-title"/,
  );
});

test("profile avatar centres its initials", () => {
  const css = readFront("pages.css");
  const html = readFront("profile.html");

  assert.match(
    css,
    /\.profile-avatar-large \.ux4g-avatar img\[hidden\]\s*\{[^}]*display:\s*none/s,
    "the placeholder photo must be taken out of layout or it claims the circle",
  );
  assert.match(html, /class="avatar-initials"/);

  const ux4gStylesheet = fs.readFileSync(
    path.join(__dirname, "node_modules", "ux4g-web-components", "styles", "ux4g.css"),
    "utf8",
  );
  const avatarImageRule = (
    ux4gStylesheet.match(/\.ux4g-avatar img\{[^}]*\}/) ?? [""]
  )[0];
  assert.match(
    avatarImageRule,
    /height:100%;.*width:100%/,
    "UX4G sizes avatar images to the full circle, which is what displaced the initials",
  );
});

test("pages script does not persist profile details", () => {
  const script = readFront("pages.js");
  assert.doesNotMatch(script, /localStorage|sessionStorage|indexedDB/);
});
