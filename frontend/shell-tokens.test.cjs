const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const SHELL_TOKENS_PATH = path.join(__dirname, "shell-tokens.js");
const source = fs.readFileSync(SHELL_TOKENS_PATH, "utf8");
const shellHtml = fs.readFileSync(path.join(__dirname, "shell.html"), "utf8");

function loadShellTokens() {
  const windowStub = {};
  vm.runInNewContext(source, { window: windowStub });
  return windowStub.DRISHTI_SHELL_TOKENS;
}

function refuses(call, fragment) {
  assert.throws(call, (error) => {
    assert.equal(error.name, "ShellTokenError");
    if (fragment !== undefined) {
      assert.ok(
        error.message.includes(fragment),
        "message was " + JSON.stringify(error.message),
      );
    }
    return true;
  });
}

// The placeholders shell.html actually carries, split into the value tokens
// and the nav conditionals, so a name in one and not the other is visible.
function placeholdersInTemplate() {
  const values = new Set();
  const conditionals = new Set();
  for (const match of shellHtml.matchAll(/\{\{([^}]+)\}\}/g)) {
    const name = match[1].replace(/^[#/]/, "");
    if (name.startsWith("nav.")) {
      conditionals.add(name.slice("nav.".length));
    } else {
      values.add(name);
    }
  }
  return { values: [...values].sort(), conditionals: [...conditionals].sort() };
}

test("the module names the page title, the active nav key and the heading", () => {
  const shellTokens = loadShellTokens();
  const names = shellTokens.tokenNames();

  for (const name of ["pageTitle", "activeNavKey", "pageHeading"]) {
    assert.ok(names.includes(name), "the module must name " + name);
    assert.equal(shellTokens.isToken(name), true, name + " must be a token");
  }
});

test("the table and the template name the same placeholders", () => {
  const shellTokens = loadShellTokens();
  const placeholders = placeholdersInTemplate();

  assert.equal(
    placeholders.values.join(","),
    shellTokens.tokenNames().sort().join(","),
  );
  assert.equal(
    placeholders.conditionals.join(","),
    shellTokens.navKeys().sort().join(","),
  );
});

test("only a name in the table is a token", () => {
  const shellTokens = loadShellTokens();

  for (const name of [
    "",
    "page",
    "nav.home",
    "toString",
    "constructor",
    "pageTitle ",
  ]) {
    assert.equal(
      shellTokens.isToken(name),
      false,
      JSON.stringify(name) + " is not a token",
    );
  }
});

test("each nav key answers the conditional the template uses", () => {
  const shellTokens = loadShellTokens();
  const keys = shellTokens.navKeys();

  assert.ok(keys.length > 0, "the shell must mark at least one link active");
  for (const key of keys) {
    assert.equal(shellTokens.conditionalName(key), "nav." + key);
    assert.ok(shellHtml.includes("{{#nav." + key + "}}"));
    assert.ok(shellHtml.includes("{{/nav." + key + "}}"));
  }
});

test("a name that is not a nav key is refused", () => {
  const shellTokens = loadShellTokens();

  refuses(() => shellTokens.conditionalName("Home"), "Home");
  refuses(() => shellTokens.conditionalName("toString"), "toString");
  refuses(() => shellTokens.conditionalName(undefined), "undefined");
});

test("a caller cannot edit the table through what it is handed", () => {
  const shellTokens = loadShellTokens();

  const names = shellTokens.tokenNames();
  names.push("aTokenNobodyDeclared");
  const keys = shellTokens.navKeys();
  keys.push("another");

  assert.equal(shellTokens.tokenNames().join(","), names.slice(0, -1).join(","));
  assert.equal(shellTokens.navKeys().join(","), keys.slice(0, -1).join(","));
});

test("no page loads the module: the build is its only reader", () => {
  const pages = fs
    .readdirSync(__dirname)
    .filter((fileName) => fileName.endsWith(".html"));

  assert.ok(pages.length > 0, "the frontend must ship pages");
  for (const fileName of pages) {
    const html = fs.readFileSync(path.join(__dirname, fileName), "utf8");
    assert.doesNotMatch(
      html,
      /shell-tokens\.js/,
      `${fileName} must not load the build-time token table`,
    );
  }
});
