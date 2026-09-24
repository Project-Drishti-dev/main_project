const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

function loadRegistrationScript() {
  const ids = [
    "full-name",
    "personnel-id",
    "email",
    "register-form",
    "register-password",
    "confirm-password",
    "register-status",
    "register-password-toggle",
    "confirm-password-toggle",
  ];
  const elements = new Map(
    ids.map((id) => [
      id,
      {
        attributes: {},
        focused: false,
        listeners: {},
        textContent: "",
        type: id.includes("password") ? "password" : "",
        value: "",
        addEventListener(event, callback) {
          this.listeners[event] = callback;
        },
        focus() {
          this.focused = true;
        },
        removeAttribute(name) {
          delete this.attributes[name];
        },
        setAttribute(name, value) {
          this.attributes[name] = value;
        },
      },
    ]),
  );
  const document = {
    getElementById(id) {
      return elements.get(id);
    },
  };
  const source = fs.readFileSync(path.join(__dirname, "register.js"), "utf8");
  vm.runInNewContext(source, { document });
  return elements;
}

test("registration toggles password visibility accessibly", () => {
  const elements = loadRegistrationScript();
  const password = elements.get("register-password");
  const toggle = elements.get("register-password-toggle");

  toggle.listeners.click();
  assert.equal(password.type, "text");
  assert.equal(toggle.textContent, "Hide");
  assert.equal(toggle.attributes["aria-pressed"], "true");
});

test("registration rejects mismatched passwords and sends or stores no details", () => {
  const elements = loadRegistrationScript();
  const password = elements.get("register-password");
  const confirmPassword = elements.get("confirm-password");
  let prevented = false;

  password.value = "first-password";
  confirmPassword.value = "second-password";
  elements.get("register-form").listeners.submit({
    preventDefault() {
      prevented = true;
    },
  });

  assert.equal(prevented, true);
  assert.equal(confirmPassword.focused, true);
  assert.equal(confirmPassword.attributes["aria-invalid"], "true");
  assert.match(elements.get("register-status").textContent, /do not match/i);

  confirmPassword.value = password.value;
  elements.get("full-name").value = "A User";
  elements.get("personnel-id").value = "ABC-123";
  elements.get("email").value = "user@example.gov.in";
  elements.get("register-form").listeners.submit({ preventDefault() {} });
  assert.equal(elements.get("full-name").value, "");
  assert.equal(elements.get("personnel-id").value, "");
  assert.equal(elements.get("email").value, "");
  assert.equal(password.value, "");
  assert.equal(confirmPassword.value, "");
  assert.match(elements.get("register-status").textContent, /No details were sent or saved/);

  const source = fs.readFileSync(path.join(__dirname, "register.js"), "utf8");
  assert.doesNotMatch(source, /fetch\(|XMLHttpRequest|localStorage|sessionStorage/);
});
