const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

function loadResetFlow() {
  const ids = [
    "forgot-password",
    "reset-request-step",
    "reset-account",
    "reset-continue",
    "reset-password-step",
    "reset-code",
    "reset-new-password",
    "reset-confirm-password",
    "reset-form",
    "reset-back",
    "reset-close",
    "password-reset-modal",
    "reset-step-counter",
    "reset-status",
  ];
  const elements = new Map(
    ids.map((id) => [
      id,
      {
        attributes: {},
        focused: false,
        hidden: id === "reset-password-step",
        listeners: {},
        textContent: "",
        value: "",
        addEventListener(event, callback) {
          this.listeners[event] = callback;
        },
        focus() {
          this.focused = true;
        },
        reportValidity() {
          return this.valid !== false;
        },
        setAttribute(name, value) {
          this.attributes[name] = value;
        },
        removeAttribute(name) {
          delete this.attributes[name];
        },
      },
    ]),
  );
  const document = {
    addEventListener(event, callback) {
      this.listeners ??= {};
      this.listeners[event] = callback;
    },
    getElementById(id) {
      return elements.get(id);
    },
  };
  const source = fs.readFileSync(path.join(__dirname, "reset-flow.js"), "utf8");
  vm.runInNewContext(source, { document });
  return { document, elements };
}

test("reset flow advances, returns, and focuses the verification step", () => {
  const { elements } = loadResetFlow();
  const accountStep = elements.get("reset-request-step");
  const passwordStep = elements.get("reset-password-step");

  elements.get("forgot-password").listeners.click();
  elements.get("reset-account").value = "officer@example.gov.in";
  elements.get("reset-continue").listeners.click();

  assert.equal(accountStep.hidden, true);
  assert.equal(passwordStep.hidden, false);
  assert.equal(elements.get("reset-code").focused, true);

  elements.get("reset-back").listeners.click();
  assert.equal(accountStep.hidden, false);
  assert.equal(passwordStep.hidden, true);
});

test("reset flow stays on account lookup when the identifier is invalid", () => {
  const { elements } = loadResetFlow();
  const accountStep = elements.get("reset-request-step");
  const passwordStep = elements.get("reset-password-step");

  elements.get("reset-account").valid = false;
  elements.get("reset-continue").listeners.click();

  assert.equal(accountStep.hidden, false);
  assert.equal(passwordStep.hidden, true);
});

test("reset flow rejects mismatched passwords and never changes a password", () => {
  const { elements } = loadResetFlow();
  const submit = elements.get("reset-form").listeners.submit;
  let prevented = false;

  elements.get("reset-new-password").value = "new-password-123";
  elements.get("reset-confirm-password").value = "different-password";
  submit({ preventDefault: () => (prevented = true) });
  assert.equal(prevented, true);
  assert.match(elements.get("reset-status").textContent, /do not match/i);

  elements.get("reset-confirm-password").value = "new-password-123";
  submit({ preventDefault() {} });
  assert.match(elements.get("reset-status").textContent, /no password was changed/i);
});

test("closing reset flow clears values from the page", () => {
  const { elements } = loadResetFlow();

  elements.get("reset-account").value = "officer@example.gov.in";
  elements.get("reset-new-password").value = "sensitive-value";
  elements.get("reset-close").listeners.click();

  assert.equal(elements.get("reset-account").value, "");
  assert.equal(elements.get("reset-new-password").value, "");
  assert.equal(elements.get("reset-confirm-password").value, "");
  assert.equal(elements.get("reset-request-step").hidden, false);
  assert.equal(elements.get("reset-password-step").hidden, true);
});

test("reset prototype does not make network requests or persist reset data", () => {
  const source = fs.readFileSync(path.join(__dirname, "reset-flow.js"), "utf8");

  assert.doesNotMatch(source, /fetch\(|XMLHttpRequest|localStorage|sessionStorage/);
});
