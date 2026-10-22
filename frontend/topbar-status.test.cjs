const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

function readFront(fileName) {
  return fs.readFileSync(path.join(__dirname, fileName), "utf8");
}

function createStatus(initialState) {
  const listeners = new Set();
  return {
    listeners,
    current: () => initialState,
    label: (state) => `label:${state}`,
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}

function loadModule(status, element) {
  const sandbox = {
    window: status === undefined ? {} : { DRISHTI_STATUS: status },
    document: {
      getElementById: (id) => (id === "connection-status" ? element ?? null : null),
    },
  };
  vm.createContext(sandbox);
  vm.runInContext(readFront("topbar-status.js"), sandbox);
  return sandbox;
}

test("the topbar shows the state the probe settled on before subscribing", () => {
  const element = { textContent: "", dataset: {} };
  loadModule(createStatus("checking"), element);
  assert.equal(element.textContent, "label:checking");
  assert.equal(element.dataset.state, "checking");
});

test("the topbar follows every state the module publishes", () => {
  const element = { textContent: "", dataset: {} };
  const status = createStatus("checking");
  loadModule(status, element);

  for (const state of ["online", "unreachable", "unconfigured", "checking"]) {
    for (const listener of [...status.listeners]) listener(state, null);
    assert.equal(element.textContent, `label:${state}`);
    assert.equal(element.dataset.state, state);
  }
});

test("a page missing the element or the module renders nothing and throws nothing", () => {
  const orphan = { textContent: "", dataset: {} };
  loadModule(undefined, orphan);
  loadModule(createStatus("online"), null);
  assert.equal(orphan.textContent, "");
});

test("the module takes no text of its own", () => {
  const script = readFront("topbar-status.js");
  assert.doesNotMatch(script, /DRISHTI_STATUS_STATE_LABELS|cannot be reached|Connected to/);
});
