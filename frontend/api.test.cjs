const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const { renderPage } = require("./build.cjs");

const source = fs.readFileSync(path.join(__dirname, "api.js"), "utf8");

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
    fire() {
      const entries = Array.from(pending.values());
      pending.clear();
      for (const entry of entries) {
        entry.callback();
      }
    },
  };
}

function createHangingFetch() {
  const calls = [];
  function fetchImpl(url, options) {
    calls.push({ url, options });
    return new Promise((resolve, reject) => {
      options.signal.addEventListener("abort", () => {
        const error = new Error("This operation was aborted");
        error.name = "AbortError";
        reject(error);
      });
    });
  }
  return { calls, fetchImpl };
}

function createResponse({ status, body, text, ok } = {}) {
  const response = {
    status,
    ok: ok === undefined ? status >= 200 && status < 300 : ok,
    textCalls: 0,
  };
  response.text = () => {
    response.textCalls += 1;
    if (text) {
      return text();
    }
    return Promise.resolve(typeof body === "string" ? body : JSON.stringify(body));
  };
  return response;
}

async function waitUntil(predicate) {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    if (predicate()) {
      return;
    }
    await Promise.resolve();
  }
  throw new Error("the condition never held");
}

function loadApi({ apiBaseUrl, hasConfig = true, fetchImpl } = {}) {
  const clock = createClock();
  const windowStub = {};
  if (hasConfig) {
    windowStub.DRISHTI_CONFIG = { apiBaseUrl };
  }
  vm.runInNewContext(source, {
    window: windowStub,
    AbortController,
    fetch: fetchImpl,
    setTimeout: clock.setTimeout,
    clearTimeout: clock.clearTimeout,
  });
  return { api: windowStub.DRISHTI_API, clock };
}

test("the base URL is read from window.DRISHTI_CONFIG", async () => {
  const hanging = createHangingFetch();
  const { api, clock } = loadApi({
    apiBaseUrl: "https://api.example.test///",
    fetchImpl: hanging.fetchImpl,
  });
  const pending = api.request("/api/analyze", { method: "POST" });
  assert.equal(hanging.calls.length, 1);
  assert.equal(hanging.calls[0].url, "https://api.example.test/api/analyze");
  assert.equal(hanging.calls[0].options.method, "POST");
  clock.fire();
  await assert.rejects(pending, () => true);
});

test("a build with no configured base URL calls its own origin", async () => {
  const hanging = createHangingFetch();
  const { api, clock } = loadApi({ fetchImpl: hanging.fetchImpl });
  const pending = api.request("/api/screenings");
  assert.equal(hanging.calls[0].url, "/api/screenings");
  clock.fire();
  await assert.rejects(pending, () => true);
});

test("a base URL that is not a string is refused, not stringified", async () => {
  const hanging = createHangingFetch();
  const { api, clock } = loadApi({ apiBaseUrl: 42, fetchImpl: hanging.fetchImpl });
  const pending = api.request("/api/analyze");
  assert.equal(hanging.calls[0].url, "/api/analyze");
  clock.fire();
  await assert.rejects(pending, () => true);
});

test("a request with no options is a GET carrying the caller body and headers", async () => {
  const hanging = createHangingFetch();
  const { api, clock } = loadApi({ fetchImpl: hanging.fetchImpl });
  const body = { image: "bytes" };
  const headers = { Accept: "application/json" };
  const pending = api.request("/api/analyze", { body, headers });
  assert.equal(hanging.calls[0].options.method, "GET");
  assert.equal(hanging.calls[0].options.body, body);
  assert.equal(hanging.calls[0].options.headers, headers);
  clock.fire();
  await assert.rejects(pending, () => true);
});

test("the shipped default budget is fifteen seconds", () => {
  const { api } = loadApi({ fetchImpl: createHangingFetch().fetchImpl });
  assert.equal(api.DEFAULT_TIMEOUT_MS, 15000);
});

test("a request that never answers is aborted when its budget runs out", async () => {
  const hanging = createHangingFetch();
  const { api, clock } = loadApi({
    apiBaseUrl: "https://api.example.test",
    fetchImpl: hanging.fetchImpl,
  });
  const pending = api.request("/api/analyze");
  const signal = hanging.calls[0].options.signal;
  assert.ok(signal, "fetch must be handed a signal to abort");
  assert.equal(signal.aborted, false);
  assert.deepEqual(clock.delays(), [api.DEFAULT_TIMEOUT_MS]);

  clock.fire();

  await assert.rejects(pending, (error) => {
    assert.equal(error.name, "ApiTimeoutError");
    assert.equal(error.code, "timeout");
    assert.match(error.message, new RegExp(String(api.DEFAULT_TIMEOUT_MS)));
    return true;
  });
  assert.equal(signal.aborted, true);
});

test("a timeout is not the error a network failure produces", async () => {
  const { api, clock } = loadApi({
    apiBaseUrl: "https://api.example.test",
    fetchImpl: () =>
      Promise.reject(
        Object.assign(new Error("fetch failed"), { name: "TypeError" }),
      ),
  });
  await assert.rejects(api.request("/api/analyze"), (error) => {
    assert.equal(error.name, "ApiError");
    assert.equal(error.code, "network_error");
    assert.notEqual(error.code, "timeout");
    assert.equal(error.status, 0);
    // One TypeError covers a CORS refusal and a dead host alike, so the
    // composed sentence must name both rather than the one cause it named.
    assert.match(error.message, /CORS/);
    assert.match(error.message, /running/);
    return true;
  });
  assert.deepEqual(clock.delays(), []);
});

test("the budget is cleared once a response has arrived", async () => {
  const response = { ok: true, status: 200 };
  const calls = [];
  const { api, clock } = loadApi({
    apiBaseUrl: "https://api.example.test",
    fetchImpl: (url, options) => {
      calls.push(options);
      return Promise.resolve(response);
    },
  });
  assert.equal(await api.request("/api/analyze"), response);
  assert.deepEqual(clock.delays(), []);

  clock.fire();

  assert.equal(calls[0].signal.aborted, false);
});

test("the caller-chosen budget is the one the timer is armed with", async () => {
  const hanging = createHangingFetch();
  const { api, clock } = loadApi({ fetchImpl: hanging.fetchImpl });
  const pending = api.request("/api/analyze", { timeoutMs: 250 });
  assert.deepEqual(clock.delays(), [250]);

  clock.fire();

  await assert.rejects(pending, (error) => {
    assert.equal(error.code, "timeout");
    assert.equal(error.timeoutMs, 250);
    return true;
  });
});

test("a zero budget still aborts rather than arming the default", async () => {
  const hanging = createHangingFetch();
  const { api, clock } = loadApi({ fetchImpl: hanging.fetchImpl });
  const pending = api.request("/api/analyze", { timeoutMs: 0 });
  assert.deepEqual(clock.delays(), [0]);

  clock.fire();

  await assert.rejects(pending, (error) => {
    assert.equal(error.code, "timeout");
    return true;
  });
});

test("a timeout carries the same three fields as every other refusal", async () => {
  const hanging = createHangingFetch();
  const { api, clock } = loadApi({ fetchImpl: hanging.fetchImpl });
  const pending = api.request("/api/analyze");
  clock.fire();
  await assert.rejects(pending, (error) => {
    assert.ok(error instanceof api.ApiError);
    assert.ok(error instanceof api.ApiTimeoutError);
    assert.equal(error.code, "timeout");
    assert.equal(error.status, 0);
    assert.equal(typeof error.message, "string");
    return true;
  });
});

test("a structured error envelope travels as the server wrote it", async () => {
  const { api, clock } = loadApi({
    apiBaseUrl: "https://api.example.test",
    fetchImpl: () =>
      Promise.resolve(
        createResponse({
          status: 429,
          body: {
            error: { code: "rate_limited", message: "Too many requests." },
          },
        }),
      ),
  });
  await assert.rejects(api.request("/api/analyze"), (error) => {
    assert.equal(error.code, "rate_limited");
    assert.equal(error.message, "Too many requests.");
    assert.equal(error.status, 429);
    return true;
  });
  assert.deepEqual(clock.delays(), []);
});

test("a body that is not JSON is refused rather than parsed", async () => {
  const { api } = loadApi({
    apiBaseUrl: "https://api.example.test",
    fetchImpl: () =>
      Promise.resolve(
        createResponse({ status: 502, body: "<html>Bad Gateway</html>" }),
      ),
  });
  await assert.rejects(api.request("/api/analyze"), (error) => {
    assert.equal(error.code, "server_error");
    assert.equal(error.status, 502);
    assert.match(error.message, /502/);
    assert.doesNotMatch(error.message, /Bad Gateway/);
    return true;
  });
});

test("a JSON body with no envelope falls back to the status it arrived with", async () => {
  const { api } = loadApi({
    apiBaseUrl: "https://api.example.test",
    fetchImpl: () =>
      Promise.resolve(
        createResponse({ status: 422, body: { detail: ["field required"] } }),
      ),
  });
  await assert.rejects(api.request("/api/analyze"), (error) => {
    assert.equal(error.code, "client_error");
    assert.equal(error.status, 422);
    assert.match(error.message, /422/);
    return true;
  });
});

test("an envelope whose code is not a string is refused, not stringified", async () => {
  const { api } = loadApi({
    apiBaseUrl: "https://api.example.test",
    fetchImpl: () =>
      Promise.resolve(
        createResponse({
          status: 500,
          body: { error: { code: 42, message: "boom" } },
        }),
      ),
  });
  await assert.rejects(api.request("/api/analyze"), (error) => {
    assert.equal(error.code, "server_error");
    assert.equal(error.status, 500);
    assert.doesNotMatch(error.message, /boom/);
    return true;
  });
});

test("an empty body answers with the status rather than a parse error", async () => {
  const { api } = loadApi({
    apiBaseUrl: "https://api.example.test",
    fetchImpl: () =>
      Promise.resolve(createResponse({ status: 404, body: "" })),
  });
  await assert.rejects(api.request("/api/screenings/1"), (error) => {
    assert.equal(error.code, "client_error");
    assert.equal(error.status, 404);
    return true;
  });
});

test("a body that cannot be read still answers with the status", async () => {
  const { api } = loadApi({
    apiBaseUrl: "https://api.example.test",
    fetchImpl: () =>
      Promise.resolve(
        createResponse({
          status: 503,
          text: () => Promise.reject(new Error("connection closed")),
        }),
      ),
  });
  await assert.rejects(api.request("/api/analyze"), (error) => {
    assert.equal(error.code, "server_error");
    assert.equal(error.status, 503);
    return true;
  });
});

test("a successful response is returned with its body unread", async () => {
  const response = createResponse({ status: 200, body: { ok: true } });
  const { api } = loadApi({
    apiBaseUrl: "https://api.example.test",
    fetchImpl: () => Promise.resolve(response),
  });
  assert.equal(await api.request("/api/analyze"), response);
  assert.equal(response.textCalls, 0);
});

test("the budget is still armed while an error body is being read", async () => {
  let rejectBody;
  const response = createResponse({
    status: 500,
    text: () =>
      new Promise((_resolve, reject) => {
        rejectBody = reject;
      }),
  });
  const { api, clock } = loadApi({
    apiBaseUrl: "https://api.example.test",
    fetchImpl: (url, options) => {
      options.signal.addEventListener("abort", () =>
        rejectBody(
          Object.assign(new Error("The operation was aborted"), {
            name: "AbortError",
          }),
        ),
      );
      return Promise.resolve(response);
    },
  });
  const pending = api.request("/api/analyze");
  await waitUntil(() => response.textCalls === 1 && rejectBody);

  clock.fire();

  await assert.rejects(pending, (error) => {
    assert.equal(error.code, "timeout");
    assert.equal(error.status, 0);
    return true;
  });
});

test("a response below 400 has neither a client nor a server code", async () => {
  const { api } = loadApi({
    apiBaseUrl: "https://api.example.test",
    fetchImpl: () => Promise.resolve(createResponse({ status: 302, body: "" })),
  });
  await assert.rejects(api.request("/api/analyze"), (error) => {
    assert.equal(error.code, "unknown_error");
    assert.equal(error.status, 302);
    return true;
  });
});

test("a malformed envelope is refused rather than repaired", async () => {
  const bodies = [
    { error: "rate_limited" },
    { error: null },
    { error: [] },
    { error: { code: "", message: "Too many requests." } },
    { error: { code: "rate_limited", message: "" } },
    { error: { code: "rate_limited", message: 7 } },
  ];
  for (const body of bodies) {
    const { api } = loadApi({
      apiBaseUrl: "https://api.example.test",
      fetchImpl: () => Promise.resolve(createResponse({ status: 500, body })),
    });
    await assert.rejects(api.request("/api/analyze"), (error) => {
      assert.equal(error.code, "server_error");
      assert.equal(error.status, 500);
      assert.equal(error.message, "The server answered 500 with no error envelope.");
      return true;
    });
  }
});

test("the base URL reader answers without reaching the network", () => {
  const fetchImpl = createHangingFetch().fetchImpl;
  assert.equal(
    loadApi({ apiBaseUrl: "  https://api.example.test//  ", fetchImpl }).api.readApiBaseUrl(),
    "https://api.example.test",
  );
  assert.equal(loadApi({ apiBaseUrl: 42, fetchImpl }).api.readApiBaseUrl(), "");
});

test("no page script calls fetch directly", () => {
  const pageScripts = fs
    .readdirSync(__dirname)
    .filter((fileName) => fileName.endsWith(".js") && fileName !== "api.js");

  assert.ok(pageScripts.length > 0, "the frontend must ship page scripts");
  for (const fileName of pageScripts) {
    const script = fs.readFileSync(path.join(__dirname, fileName), "utf8");
    assert.doesNotMatch(
      script,
      /\bfetch\s*\(/,
      `${fileName} must reach the API through window.DRISHTI_API`,
    );
  }
  assert.match(source, /\bfetch\s*\(/, "api.js is the module that calls fetch");
});

test("the screening page loads the API module before its own page script", () => {
  const html = renderPage(
    fs.readFileSync(path.join(__dirname, "home.html"), "utf8"),
    "home.html",
  );
  const apiModule = html.indexOf('src="./api.js"');
  const pageScript = html.indexOf('src="./home.js"');

  assert.ok(apiModule > 0, "home.html must load api.js");
  assert.ok(apiModule < pageScript, "api.js must load before home.js");
});
