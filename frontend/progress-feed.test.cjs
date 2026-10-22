const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const { buildFileNames } = require("./build.cjs");

const source = fs.readFileSync(path.join(__dirname, "progress-feed.js"), "utf8");
const progressServiceSource = fs.readFileSync(
  path.join(__dirname, "..", "backend", "app", "progress.py"),
  "utf8",
);
const progressRoutesSource = fs.readFileSync(
  path.join(__dirname, "..", "backend", "app", "api", "routes_progress.py"),
  "utf8",
);

const SCREENING_ID = "6f1a2b3c-4d5e-6f70-8192-a3b4c5d6e7f8";
const API_BASE_URL = "https://api.example.test";

function tierStep(tier) {
  return {
    screening_id: SCREENING_ID,
    unit: "tier",
    state: "completed",
    tier: tier,
    module: null,
  };
}

function moduleStep(tier, module) {
  return {
    screening_id: SCREENING_ID,
    unit: "module",
    state: "reported",
    tier: tier,
    module: module,
  };
}

// The five steps a two-tier run leaves behind, in the order app/progress.py
// writes them: the tiers that returned, then the modules that reported.
const WHOLE_RUN = [
  tierStep("tier_0"),
  moduleStep("tier_0", "m1_forgery"),
  moduleStep("tier_0", "m2_anomaly"),
  tierStep("tier_1"),
  moduleStep("tier_1", "m6_ppi"),
];

function documentOf(steps) {
  return { screening_id: SCREENING_ID, units: steps.length, events: steps };
}

// The module parses a stream frame's data line inside its own realm, so a
// step that arrived that way is a sandbox object. Round-tripping it makes the
// comparisons below about the sequence rather than about which realm built it.
function plain(value) {
  return JSON.parse(JSON.stringify(value));
}

function okResponse(document) {
  return { ok: true, status: 200, json: () => Promise.resolve(document) };
}

function createClock() {
  let nextId = 1;
  const pending = new Map();
  return {
    setTimeout(callback, delay) {
      const id = nextId;
      nextId += 1;
      pending.set(id, { callback: callback, delay: delay });
      return id;
    },
    clearTimeout(id) {
      pending.delete(id);
    },
    delays() {
      return Array.from(pending.values(), (entry) => entry.delay);
    },
    pending() {
      return pending.size;
    },
    fire() {
      const entries = Array.from(pending.values());
      pending.clear();
      for (const entry of entries) {
        entry.callback();
      }
      return entries.length;
    },
  };
}

// A stand-in for the browser's own EventSource: the constructor records what
// was opened, and a case drives the three events the service writes.
function createEventSource() {
  const opened = [];
  class FakeEventSource {
    constructor(url) {
      this.url = url;
      this.closed = false;
      this.handlers = new Map();
      opened.push(this);
    }
    addEventListener(name, handler) {
      if (!this.handlers.has(name)) {
        this.handlers.set(name, []);
      }
      this.handlers.get(name).push(handler);
    }
    emit(name, event) {
      for (const handler of this.handlers.get(name) || []) {
        handler(event);
      }
    }
    close() {
      this.closed = true;
    }
  }
  return { opened: opened, FakeEventSource: FakeEventSource };
}

function loadFeed({
  withEventSource = true,
  answer = () => Promise.resolve(okResponse(documentOf([]))),
  settings = {},
} = {}) {
  const clock = createClock();
  const streams = createEventSource();
  const requests = [];
  const told = [];
  const completed = [];
  const failures = [];
  const windowStub = {
    DRISHTI_CONFIG: { apiBaseUrl: API_BASE_URL },
    DRISHTI_API: {
      request: (requestPath, options) => {
        requests.push({ path: requestPath, options: options });
        return answer(requestPath, requests.length);
      },
      readApiBaseUrl: () => API_BASE_URL,
    },
  };
  if (withEventSource) {
    windowStub.EventSource = streams.FakeEventSource;
  }
  const context = vm.createContext({
    window: windowStub,
    setTimeout: clock.setTimeout,
    clearTimeout: clock.clearTimeout,
  });
  vm.runInContext(source, context);
  const module = windowStub.DRISHTI_PROGRESS_FEED;
  const feed = module.bindProgressFeed({
    screeningId: SCREENING_ID,
    onStep: (step, index) => told.push({ step: plain(step), index: index }),
    onComplete: (units) => completed.push(units),
    onFailed: (refusal) => failures.push(refusal),
    ...settings,
  });
  return {
    feed: feed,
    module: module,
    told: told,
    completed: completed,
    failures: failures,
    requests: requests,
    opened: streams.opened,
    clock: clock,
  };
}

function frameOf(payload) {
  return { data: JSON.stringify(payload) };
}

// Binds with exactly the settings it is handed, so a case can leave one out --
// loadFeed always fills the four, which is what the other cases want.
function bindWith(settings, { withApi = true } = {}) {
  const windowStub = withApi
    ? {
        DRISHTI_CONFIG: { apiBaseUrl: API_BASE_URL },
        DRISHTI_API: {
          request: () => Promise.resolve(okResponse(documentOf([]))),
          readApiBaseUrl: () => API_BASE_URL,
        },
      }
    : {};
  const context = vm.createContext({
    window: windowStub,
    setTimeout,
    clearTimeout,
  });
  vm.runInContext(source, context);
  return () => context.window.DRISHTI_PROGRESS_FEED.bindProgressFeed(settings);
}

function streamTheWholeRun(source_) {
  for (const step of WHOLE_RUN) {
    source_.emit("progress", frameOf(step));
  }
  source_.emit("done", frameOf({ screening_id: SCREENING_ID, units: 5 }));
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

test("the feed dials nothing and opens nothing until start() is called", () => {
  const { feed, requests, opened, clock } = loadFeed();

  assert.equal(feed.transport(), "idle");
  assert.equal(feed.complete(), false);
  assert.equal(feed.steps().length, 0);
  assert.deepEqual(requests, []);
  assert.deepEqual(opened, []);
  assert.equal(clock.pending(), 0, "no timer is armed before the feed runs");
});

test("a stream that carries the whole sequence answers with no request at all", () => {
  const { feed, requests, opened, told, completed, failures } = loadFeed();

  assert.equal(feed.start(), "stream");
  streamTheWholeRun(opened[0]);

  assert.deepEqual(requests, [], "a stream that works never polls");
  assert.deepEqual(
    told.map((entry) => entry.index),
    [0, 1, 2, 3, 4],
  );
  assert.deepEqual(told.map((entry) => entry.step), WHOLE_RUN);
  assert.deepEqual(completed, [5], "the done frame reports the step count");
  assert.deepEqual(failures, []);
  assert.equal(opened[0].closed, true, "the feed hangs up on its own");
  assert.equal(feed.complete(), true);
});

test("a stream that cannot connect falls back to polling", async () => {
  const { feed, requests, opened, told, completed, failures } = loadFeed({
    answer: () => Promise.resolve(okResponse(documentOf(WHOLE_RUN))),
  });

  assert.equal(feed.start(), "stream");
  opened[0].emit("error", { type: "error" });

  await waitUntil(() => completed.length > 0);

  assert.equal(feed.transport(), "poll", "the caller never chooses the fallback");
  assert.equal(opened[0].closed, true, "the dead connection is hung up on");
  assert.deepEqual(
    requests.map((entry) => entry.path),
    ["/api/screenings/" + SCREENING_ID + "/progress"],
  );
  assert.deepEqual(told.map((entry) => entry.step), WHOLE_RUN);
  assert.deepEqual(completed, [5]);
  assert.deepEqual(failures, []);
});

test("a page with no EventSource goes straight to polling", async () => {
  const { feed, requests, told, completed, clock } = loadFeed({
    withEventSource: false,
    answer: () => Promise.resolve(okResponse(documentOf(WHOLE_RUN))),
  });

  assert.equal(feed.start(), "poll");
  await waitUntil(() => completed.length > 0);

  assert.deepEqual(
    requests.map((entry) => entry.path),
    ["/api/screenings/" + SCREENING_ID + "/progress"],
  );
  assert.deepEqual(told.map((entry) => entry.step), WHOLE_RUN);
  assert.deepEqual(completed, [5]);
  assert.equal(clock.pending(), 0, "a settled feed leaves no timer armed");
});

test("a stream that dies midway is finished by the document, and no step is told twice", async () => {
  const { feed, requests, opened, told, completed } = loadFeed({
    answer: () => Promise.resolve(okResponse(documentOf(WHOLE_RUN))),
  });

  feed.start();
  opened[0].emit("progress", frameOf(WHOLE_RUN[0]));
  opened[0].emit("progress", frameOf(WHOLE_RUN[1]));
  opened[0].emit("error", { type: "error" });

  await waitUntil(() => completed.length > 0);

  assert.equal(requests.length, 1, "the document is read once");
  assert.deepEqual(
    told.map((entry) => entry.index),
    [0, 1, 2, 3, 4],
    "the two steps the stream delivered are not told a second time",
  );
  assert.deepEqual(told.map((entry) => entry.step), WHOLE_RUN);
  assert.deepEqual(completed, [5]);
});

test("both transports publish the same sequence, so a panel cannot tell them apart", async () => {
  const streamed = loadFeed();
  streamed.feed.start();
  streamTheWholeRun(streamed.opened[0]);

  const polled = loadFeed({
    withEventSource: false,
    answer: () => Promise.resolve(okResponse(documentOf(WHOLE_RUN))),
  });
  polled.feed.start();
  await waitUntil(() => polled.completed.length > 0);

  assert.deepEqual(plain(streamed.feed.steps()), plain(polled.feed.steps()));
  assert.deepEqual(streamed.told.map((entry) => entry.step), polled.told.map((entry) => entry.step));
  assert.deepEqual(streamed.completed, polled.completed);
});

test("a document carrying fewer steps than it reports waits on the interval", async () => {
  const { feed, requests, told, completed, clock } = loadFeed({
    withEventSource: false,
    answer: (requestPath, callNumber) =>
      Promise.resolve(
        okResponse(
          callNumber === 1
            ? { screening_id: SCREENING_ID, units: 5, events: WHOLE_RUN.slice(0, 2) }
            : documentOf(WHOLE_RUN),
        ),
      ),
  });

  feed.start();
  await waitUntil(() => clock.pending() > 0);

  assert.deepEqual(told.map((entry) => entry.step), WHOLE_RUN.slice(0, 2));
  assert.deepEqual(clock.delays(), [1000]);
  assert.deepEqual(completed, [], "an unfinished sequence is not a finished run");

  clock.fire();
  await waitUntil(() => completed.length > 0);

  assert.equal(requests.length, 2);
  assert.deepEqual(
    told.map((entry) => entry.step),
    WHOLE_RUN,
  );
  assert.deepEqual(completed, [5]);
  assert.equal(clock.pending(), 0);
});

test("a poll that fails is retried, and the last refusal is named", async () => {
  const { feed, requests, completed, failures, clock } = loadFeed({
    withEventSource: false,
    answer: () => Promise.reject(new Error("fetch failed")),
    settings: { maxPollAttempts: 2 },
  });

  feed.start();
  await waitUntil(() => clock.pending() > 0);

  assert.equal(requests.length, 1, "one refusal does not end the feed");
  assert.deepEqual(failures, []);

  clock.fire();
  await waitUntil(() => failures.length > 0);

  assert.equal(requests.length, 2);
  assert.deepEqual(completed, [], "a feed that gave up never finished");
  assert.equal(failures.length, 1);
  assert.equal(failures[0].name, "ProgressFeedError");
  assert.equal(failures[0].code, "no_progress");
  assert.equal(clock.pending(), 0, "a feed that gave up leaves no timer armed");
});

test("a frame this page cannot read is refused by name, not drawn", () => {
  for (const frame of [
    { data: "not json at all" },
    { data: "null" },
    { data: "42" },
    { data: '"tier_0"' },
    { data: 42 },
    {},
  ]) {
    const { feed, opened, told, completed, failures } = loadFeed();

    feed.start();
    opened[0].emit("progress", frame);

    assert.deepEqual(told, [], "a frame nobody can read draws no step");
    assert.deepEqual(completed, []);
    assert.equal(failures.length, 1, JSON.stringify(frame));
    assert.equal(failures[0].name, "ProgressFeedError");
    assert.equal(failures[0].code, "bad_frame");
    assert.equal(feed.complete(), true);
  }
});

test("a step naming no unit or no state is refused by name", () => {
  for (const step of [
    { unit: "tier", state: "", tier: "tier_0", module: null },
    { unit: 7, state: "completed", tier: "tier_0", module: null },
    { unit: "tier", tier: "tier_0", module: null },
    [],
  ]) {
    const { feed, opened, told, failures } = loadFeed();

    feed.start();
    opened[0].emit("progress", frameOf(step));

    assert.deepEqual(told, [], "a step that names no unit is not drawn");
    assert.equal(failures.length, 1, JSON.stringify(step));
    assert.equal(failures[0].code, "bad_step");
  }
});

test("a document that is not a document is refused by name", async () => {
  for (const document of [
    null,
    "five",
    { screening_id: SCREENING_ID, units: 1 },
    { screening_id: SCREENING_ID, units: -1, events: [] },
    { screening_id: SCREENING_ID, units: 1.5, events: [] },
  ]) {
    const { feed, told, failures, clock } = loadFeed({
      withEventSource: false,
      answer: () => Promise.resolve(okResponse(document)),
    });

    feed.start();
    await waitUntil(() => failures.length > 0);

    assert.deepEqual(told, [], JSON.stringify(document));
    assert.equal(failures.length, 1, JSON.stringify(document));
    assert.equal(failures[0].name, "ProgressFeedError");
    assert.equal(failures[0].code, "bad_document");
    assert.equal(clock.pending(), 0, "a refused document leaves no timer armed");
  }
});

test("a step the service wrote is passed through whole, tier and module keys included", () => {
  const { feed, opened, told, failures } = loadFeed();

  feed.start();
  opened[0].emit("progress", frameOf(WHOLE_RUN[2]));

  assert.deepEqual(told.map((entry) => entry.step), [WHOLE_RUN[2]]);
  assert.deepEqual(failures, []);
});

test("a done frame reporting no steps is a finished empty run, not a refusal", () => {
  const { feed, opened, told, completed, failures } = loadFeed();

  feed.start();
  opened[0].emit("done", frameOf({ screening_id: SCREENING_ID, units: 0 }));

  assert.deepEqual(told, []);
  assert.deepEqual(completed, [0]);
  assert.deepEqual(failures, []);
});

test("stop() hangs up on the stream, and a later frame draws nothing", () => {
  const { feed, opened, told, completed, failures } = loadFeed();

  feed.start();
  opened[0].emit("progress", frameOf(WHOLE_RUN[0]));
  feed.stop();

  assert.equal(opened[0].closed, true);
  opened[0].emit("progress", frameOf(WHOLE_RUN[1]));
  opened[0].emit("done", frameOf({ screening_id: SCREENING_ID, units: 5 }));

  assert.deepEqual(told.map((entry) => entry.index), [0], "a stopped feed is silent");
  assert.deepEqual(completed, []);
  assert.deepEqual(failures, []);
  assert.equal(feed.complete(), false, "a feed that was stopped never finished");
});

test("stop() disarms the interval a waiting poll left behind", async () => {
  const { feed, requests, clock } = loadFeed({
    withEventSource: false,
    answer: () => Promise.reject(new Error("fetch failed")),
    settings: { maxPollAttempts: 5 },
  });

  feed.start();
  await waitUntil(() => clock.pending() > 0);
  feed.stop();

  assert.equal(clock.pending(), 0);
  assert.equal(clock.fire(), 0, "nothing is left to fire");
  assert.equal(requests.length, 1);
});

test("one feed opens one connection, however many times it is started", () => {
  const { feed, opened, requests } = loadFeed();

  assert.equal(feed.start(), "stream");
  assert.equal(feed.start(), "stream");
  assert.equal(feed.start(), "stream");

  assert.equal(opened.length, 1, "a second start must not open a second stream");
  assert.deepEqual(requests, []);
});

test("the feed refuses a missing setting by name", () => {
  const base = {
    screeningId: SCREENING_ID,
    onStep: () => {},
    onComplete: () => {},
    onFailed: () => {},
  };

  for (const name of ["screeningId", "onStep", "onComplete", "onFailed"]) {
    const settings = { ...base };
    delete settings[name];
    assert.throws(
      () => bindWith(settings)(),
      (error) => {
        assert.equal(error.name, "ProgressFeedError");
        assert.equal(
          error.code,
          name === "screeningId" ? "no_screening_id" : "missing_callback",
        );
        return true;
      },
      name,
    );
  }

  for (const screeningId of ["", "   ", null, 42]) {
    assert.throws(
      () => bindWith({ ...base, screeningId: screeningId })(),
      (error) => error.code === "no_screening_id",
      String(screeningId),
    );
  }

  for (const maxPollAttempts of [0, -1, 1.5, "2"]) {
    assert.throws(
      () => bindWith({ ...base, maxPollAttempts: maxPollAttempts })(),
      (error) => error.code === "bad_attempts",
      String(maxPollAttempts),
    );
  }
});

test("a page with no API module is refused rather than dialled", () => {
  assert.throws(
    () =>
      bindWith(
        {
          screeningId: SCREENING_ID,
          onStep: () => {},
          onComplete: () => {},
          onFailed: () => {},
        },
        { withApi: false },
      )(),
    (error) => error.name === "ProgressFeedError" && error.code === "no_api",
  );
});

test("the event names are the service's own, read out of app/progress.py", () => {
  const { module } = loadFeed();

  for (const name of ["PROGRESS_EVENT", "DONE_EVENT"]) {
    const match = new RegExp("^" + name + ' = "([^"]*)"', "m").exec(progressServiceSource);
    assert.ok(match, name + " must still be defined in app/progress.py");
    assert.equal(module[name], match[1], name + " must be the name the service writes");
  }
});

test("the two paths are the two routes, with the prefix the router declares", () => {
  const { module } = loadFeed();

  assert.ok(
    progressRoutesSource.includes('prefix="/api"'),
    "the progress router must still declare its prefix",
  );
  for (const [suffix, name] of [
    ["/progress/stream", "stream_screening_progress"],
    ["/progress", "get_screening_progress"],
  ]) {
    const route = "/screenings/{screening_id}" + suffix;
    assert.ok(
      progressRoutesSource.includes('"' + route + '"'),
      "app/api/routes_progress.py must still declare " + route,
    );
    assert.equal(
      module[name === "stream_screening_progress" ? "streamPath" : "pollPath"](SCREENING_ID),
      "/api" + route.replace("{screening_id}", SCREENING_ID),
      name + " must read the route the service publishes",
    );
  }
  assert.equal(
    module.streamPath("a b/c"),
    "/api/screenings/a%20b%2Fc/progress/stream",
    "an id is encoded, not pasted into the path",
  );
});

test("no address is baked into the module", () => {
  assert.doesNotMatch(source, /https?:\/\//);
  assert.doesNotMatch(source, /localhost/);
  assert.match(source, /DRISHTI_API/);
  assert.match(source, /DRISHTI_PROGRESS_FEED/);
});

test("no page loads the module yet, so the build copies nothing", () => {
  const { staticFiles, pageFileNames } = buildFileNames();
  const pages = pageFileNames.map((fileName) =>
    fs.readFileSync(path.join(__dirname, fileName), "utf8"),
  );
  const shell = fs.readFileSync(path.join(__dirname, "shell.html"), "utf8");

  assert.ok(!staticFiles.includes("progress-feed.js"));
  for (const markup of [...pages, shell]) {
    assert.doesNotMatch(markup, /progress-feed\.js/);
  }
});