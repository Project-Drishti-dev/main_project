const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const apiSource = fs.readFileSync(path.join(__dirname, "api.js"), "utf8");
const statusSource = fs.readFileSync(path.join(__dirname, "status.js"), "utf8");

function createClock() {
  let nextId = 1;
  const pending = new Map();
  return {
    setTimeout(callback, delay) {
      const id = nextId;
      nextId += 1;
      pending.set(id, { callback, delay });
      return id;
    },
    clearTimeout(id) {
      pending.delete(id);
    },
    delays() {
      return Array.from(pending.values(), (entry) => entry.delay);
    },
  };
}

function neverAnswers() {
  const calls = [];
  return {
    calls,
    fetchImpl(url, options) {
      calls.push({ url, options });
      return new Promise(() => {});
    },
  };
}

// No body reader on purpose: the probe must not need what the answer says.
function okResponse() {
  return { ok: true, status: 200 };
}

function failure() {
  return Object.assign(new Error("fetch failed"), { name: "TypeError" });
}

async function waitUntil(predicate) {
  for (let attempt = 0; attempt < 200; attempt += 1) {
    if (predicate()) {
      return;
    }
    await new Promise((resolve) => setImmediate(resolve));
  }
  throw new Error("the condition never held");
}

function loadStatus({
  apiBaseUrl,
  hasConfig = true,
  withApiModule = true,
  fetchImpl,
} = {}) {
  const clock = createClock();
  const calls = [];
  const windowStub = {};
  if (hasConfig) {
    windowStub.DRISHTI_CONFIG = { apiBaseUrl };
  }
  const context = vm.createContext({
    window: windowStub,
    AbortController,
    fetch: (url, options) => {
      calls.push({ url, options });
      return fetchImpl(url, options);
    },
    setTimeout: clock.setTimeout,
    clearTimeout: clock.clearTimeout,
  });
  if (withApiModule) {
    vm.runInContext(apiSource, context);
  }
  vm.runInContext(statusSource, context);
  return { status: windowStub.DRISHTI_STATUS, calls, clock };
}

test("a probe that has not answered yet reads checking, and it has started", () => {
  const hanging = neverAnswers();
  const { status, calls, clock } = loadStatus({
    apiBaseUrl: "https://api.example.test",
    fetchImpl: hanging.fetchImpl,
  });

  assert.equal(status.current(), "checking");
  assert.equal(calls.length, 1, "the probe must start with the page");
  assert.equal(calls[0].url, "https://api.example.test/health");
  assert.deepEqual(
    clock.delays(),
    [15000],
    "the probe is bounded by the API budget, so a stalled server cannot hang a page",
  );
});

test("a health route that answers is online", async () => {
  const { status, calls } = loadStatus({
    apiBaseUrl: "https://api.example.test",
    fetchImpl: () => Promise.resolve(okResponse()),
  });

  await waitUntil(() => status.current() !== "checking");

  assert.equal(status.current(), "online");
  assert.equal(status.lastError(), null);
  assert.equal(calls.length, 1, "the load-time probe is the only call");
});

test("a health route that cannot be reached is unreachable", async () => {
  const { status } = loadStatus({
    apiBaseUrl: "https://api.example.test",
    fetchImpl: () => Promise.reject(failure()),
  });

  await waitUntil(() => status.current() !== "checking");

  assert.equal(status.current(), "unreachable");
  assert.equal(status.lastError().code, "network_error");
  assert.equal(status.lastError().status, 0);
});

test("a health route that answers 5xx is unreachable and keeps the server code", async () => {
  const { status } = loadStatus({
    apiBaseUrl: "https://api.example.test",
    fetchImpl: () =>
      Promise.resolve({
        ok: false,
        status: 502,
        text: () => Promise.resolve("<html>Bad Gateway</html>"),
      }),
  });

  await waitUntil(() => status.current() !== "checking");

  assert.equal(status.current(), "unreachable");
  assert.equal(status.lastError().code, "server_error");
  assert.equal(status.lastError().status, 502);
});

test("a build with no configured base URL is unconfigured and dials nothing", async () => {
  const hanging = neverAnswers();
  const { status, calls } = loadStatus({ fetchImpl: hanging.fetchImpl });

  assert.equal(status.current(), "unconfigured");
  assert.equal(status.lastError(), null);
  assert.deepEqual(calls, []);

  assert.equal(await status.refresh(), "unconfigured");
  assert.deepEqual(calls, [], "a re-probe of nothing dials nothing");
});

test("a page with no configuration object at all is unconfigured", () => {
  const hanging = neverAnswers();
  const { status, calls } = loadStatus({
    hasConfig: false,
    fetchImpl: hanging.fetchImpl,
  });

  assert.equal(status.current(), "unconfigured");
  assert.deepEqual(calls, []);
});

test("a base URL that is not a string is unconfigured, not stringified", () => {
  const hanging = neverAnswers();
  const { status, calls } = loadStatus({
    apiBaseUrl: 42,
    fetchImpl: hanging.fetchImpl,
  });

  assert.equal(status.current(), "unconfigured");
  assert.deepEqual(calls, []);
});

test("a page with no API module is unconfigured rather than a load-time throw", () => {
  const hanging = neverAnswers();
  const { status, calls } = loadStatus({
    apiBaseUrl: "https://api.example.test",
    withApiModule: false,
    fetchImpl: hanging.fetchImpl,
  });

  assert.equal(status.current(), "unconfigured");
  assert.deepEqual(calls, []);
});

test("the module names four states, and one label each", () => {
  const { status } = loadStatus({ fetchImpl: neverAnswers().fetchImpl });

  assert.deepEqual({ ...status.STATE_LABELS }, {
    checking: "Checking the connection...",
    online: "Connected to the quality service",
    unreachable: "The quality service cannot be reached",
    unconfigured: "This site has no quality service configured",
  });
  assert.deepEqual(Object.values(status.STATES), [
    "checking",
    "online",
    "unreachable",
    "unconfigured",
  ]);
  for (const [state, text] of Object.entries({ ...status.STATE_LABELS })) {
    assert.equal(typeof text, "string");
    assert.notEqual(text, "");
    assert.equal(status.label(state), text);
  }
  assert.equal(status.label(), status.label(status.current()));
});

test("a state that is not one of the four is refused, not given a fallback", () => {
  const { status } = loadStatus({ fetchImpl: neverAnswers().fetchImpl });

  for (const value of ["offline", "toString", "", null, 42]) {
    assert.throws(
      () => status.label(value),
      (error) => error.name === "StatusError",
      String(value),
    );
  }
});

test("a subscriber is told every state a probe settles into", async () => {
  let answering = true;
  const seen = [];
  const { status } = loadStatus({
    apiBaseUrl: "https://api.example.test",
    fetchImpl: () =>
      answering ? Promise.resolve(okResponse()) : Promise.reject(failure()),
  });
  const stop = status.subscribe((state, error) => {
    seen.push({ state, code: error ? error.code : null });
  });

  await waitUntil(() => status.current() === "online");
  answering = false;
  assert.equal(await status.refresh(), "unreachable");

  assert.deepEqual(
    seen.map((entry) => entry.state),
    ["online", "checking", "unreachable"],
  );
  assert.deepEqual(
    seen.map((entry) => entry.code),
    [null, null, "network_error"],
  );

  answering = true;
  stop();
  await status.refresh();

  assert.equal(seen.length, 3, "an unsubscribed listener hears nothing more");
  assert.equal(status.current(), "online");
});

test("a subscriber that unsubscribes mid-notification does not skip the next", async () => {
  const heard = [];
  const { status } = loadStatus({
    apiBaseUrl: "https://api.example.test",
    fetchImpl: () => Promise.resolve(okResponse()),
  });

  let stopSecond;
  status.subscribe(() => {
    heard.push("first");
    stopSecond();
  });
  stopSecond = status.subscribe(() => heard.push("second"));

  await status.refresh();

  assert.deepEqual(
    heard.slice(0, 2),
    ["first", "second"],
    "a listener removed mid-notification must not skip the one after it",
  );
  assert.equal(status.current(), "online");
});

test("no address is baked into the module", () => {
  assert.doesNotMatch(statusSource, /https?:\/\//);
  assert.doesNotMatch(statusSource, /localhost/);
  assert.match(statusSource, /DRISHTI_API/);
  assert.match(statusSource, /DRISHTI_STATUS/);
});

test("the address probed is the one the build configured", () => {
  for (const baseUrl of [
    "https://api.example.test",
    "http://localhost:8080",
    "https://quality-api.example.run.app",
  ]) {
    const { status, calls } = loadStatus({
      apiBaseUrl: baseUrl,
      fetchImpl: neverAnswers().fetchImpl,
    });
    assert.equal(calls.length, 1);
    assert.equal(calls[0].url, baseUrl + status.HEALTH_PATH);
  }
});
