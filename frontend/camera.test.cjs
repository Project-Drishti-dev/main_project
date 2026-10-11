const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const CAMERA_PATH = path.join(__dirname, "camera.js");
const UPLOAD_PATH = path.join(__dirname, "upload.js");
const source = fs.readFileSync(CAMERA_PATH, "utf8");
const uploadSource = fs.readFileSync(UPLOAD_PATH, "utf8");
const { buildFileNames } = require("./build.cjs");

const FRAME_BYTES = "a-frame-of-pixels";

function createElement(tagName = "div") {
  return {
    tagName: tagName.toUpperCase(),
    attributes: {},
    listeners: {},
    hidden: false,
    value: "",
    alt: "",
    _textContent: "",
    get textContent() {
      return this._textContent;
    },
    set textContent(value) {
      this._textContent = String(value ?? "");
    },
    addEventListener(event, callback) {
      this.listeners[event] = callback;
    },
    setAttribute(name, value) {
      this.attributes[name] = value;
    },
    getAttribute(name) {
      return this.attributes[name] ?? null;
    },
    removeAttribute(name) {
      delete this.attributes[name];
    },
  };
}

// The two surfaces the camera needs are more than the generic element: a
// video carries a live stream and a frame size, a canvas encodes one.
function createVideo() {
  return {
    ...createElement("video"),
    srcObject: null,
    videoWidth: 640,
    videoHeight: 480,
    played: 0,
    play() {
      this.played += 1;
      return { catch() {} };
    },
  };
}

function createCanvas(blob) {
  return {
    ...createElement("canvas"),
    width: 0,
    height: 0,
    drawn: [],
    encoding: null,
    getContext(kind) {
      const canvas = this;
      return {
        kind,
        drawImage(...args) {
          canvas.drawn.push(args);
        },
      };
    },
    toBlob(callback, type, quality) {
      this.encoding = { type, quality };
      callback(blob);
    },
  };
}

function fakeStream(trackCount = 2) {
  const tracks = [];
  for (let index = 0; index < trackCount; index += 1) {
    tracks.push({
      kind: "video",
      stopped: false,
      stop() {
        this.stopped = true;
      },
    });
  }
  return {
    tracks,
    getTracks() {
      return this.tracks;
    },
  };
}

function frameBlob() {
  return new Blob([FRAME_BYTES], { type: "image/jpeg" });
}

// One sandbox per binding. getUserMedia is a recorder rather than an absence,
// so "capture is not auto-started" is something a test can see fail.
function loadCamera(options = {}) {
  const stream = options.stream === undefined ? fakeStream() : options.stream;
  const blob = options.blob === undefined ? frameBlob() : options.blob;
  const mediaCalls = [];
  const refusals = [];
  const captures = [];

  const getUserMedia = (constraints) => {
    mediaCalls.push({ constraints });
    return options.open ? options.open(mediaCalls.length) : Promise.resolve(stream);
  };

  const elements = {
    video: createVideo(),
    canvas: options.canvas || createCanvas(blob),
    start: createElement("button"),
    capture: createElement("button"),
    stop: createElement("button"),
    consent: createElement("p"),
  };

  const sandbox = {
    window: {},
    File,
    Blob,
    navigator: Object.prototype.hasOwnProperty.call(options, "navigator")
      ? options.navigator
      : { mediaDevices: { getUserMedia } },
  };
  // isSecureContext is a window global in the browser, so the sandbox carries
  // one only where a case asks for it: a test that never raised the question
  // leaves the browser having answered neither way.
  if (Object.prototype.hasOwnProperty.call(options, "isSecureContext")) {
    sandbox.isSecureContext = options.isSecureContext;
  }
  vm.runInNewContext(source, sandbox);
  const camera = sandbox.window.DRISHTI_CAMERA;

  const controller = camera.bindCamera({
    ...elements,
    onCapture: (file) => captures.push(file),
    onRefuse: (refusal) => refusals.push(refusal),
  });

  return { camera, controller, elements, mediaCalls, refusals, captures, stream };
}

// upload.js and camera.js in one sandbox, so "the capture passes the same two
// gates" is a call rather than a claim: onCapture is literally choose().
function loadUploadAndCamera() {
  const mediaCalls = [];
  const refusals = [];
  const sent = { fetches: 0, formData: 0 };
  const stream = fakeStream(1);

  const elements = {
    input: createElement("input"),
    panel: createElement("div"),
    preview: createElement("img"),
    details: createElement("p"),
    error: createElement("p"),
    video: createVideo(),
    canvas: createCanvas(frameBlob()),
    start: createElement("button"),
    capture: createElement("button"),
    stop: createElement("button"),
    consent: createElement("p"),
  };

  const sandbox = {
    window: {},
    File,
    Blob,
    URL,
    navigator: {
      mediaDevices: {
        getUserMedia(constraints) {
          mediaCalls.push({ constraints });
          return Promise.resolve(stream);
        },
      },
    },
    fetch() {
      sent.fetches += 1;
      throw new Error("the camera must not send anything");
    },
    FormData() {
      sent.formData += 1;
      throw new Error("the camera must not build a request");
    },
  };
  vm.runInNewContext(uploadSource, sandbox);
  vm.runInNewContext(source, sandbox);

  const uploadController = sandbox.window.DRISHTI_UPLOAD.bindUpload({
    input: elements.input,
    panel: elements.panel,
    preview: elements.preview,
    details: elements.details,
    error: elements.error,
  });
  const cameraController = sandbox.window.DRISHTI_CAMERA.bindCamera({
    video: elements.video,
    canvas: elements.canvas,
    start: elements.start,
    capture: elements.capture,
    stop: elements.stop,
    consent: elements.consent,
    onCapture: uploadController.choose,
    onRefuse: (refusal) => refusals.push(refusal),
  });

  return { elements, mediaCalls, refusals, sent, uploadController, cameraController };
}

function refuses(call, code, fragment) {
  assert.throws(call, (error) => {
    assert.equal(error.name, "CameraError");
    assert.equal(error.code, code);
    assert.ok(
      error.message.includes(fragment),
      "message was " + JSON.stringify(error.message),
    );
    return true;
  });
}

test("the consent copy is present, in one home, before anything is opened", () => {
  const { camera, elements } = loadCamera();
  const consent = camera.CONSENT;

  assert.equal(typeof consent, "string");
  assert.ok(consent.length > 0, "the consent copy must not be empty");
  assert.match(consent, /camera/i);
  assert.match(consent, /nothing is recorded/i);
  assert.match(consent, /until you submit/i);
  // One home: the container carries exactly the module's copy, so a page
  // drifting from it fails here rather than reading as consent.
  assert.equal(elements.consent.textContent, consent);
});

test("capture is not auto-started: binding asks for no permission", async () => {
  const { controller, elements, mediaCalls, captures } = loadCamera();

  assert.deepEqual(mediaCalls, []);
  assert.equal(elements.video.srcObject, null);
  assert.equal(elements.video.played, 0);
  assert.deepEqual(elements.canvas.drawn, []);
  assert.equal(controller.active(), false);

  await elements.start.listeners.click();

  assert.equal(mediaCalls.length, 1);
  assert.equal(elements.video.srcObject !== null, true);
  assert.equal(controller.active(), true);
  assert.deepEqual(captures, []);
});

test("no page reads the module before the officer clicks, and nothing is opened at load", () => {
  const sandbox = { window: {}, File, Blob, navigator: { mediaDevices: { getUserMedia() { throw new Error("getUserMedia must not be called at load"); } } } };
  vm.runInNewContext(source, sandbox);
  assert.equal(typeof sandbox.window.DRISHTI_CAMERA.bindCamera, "function");
  assert.doesNotMatch(source, /^\s*bindCamera\(\)/m);
});

test("the shutter asks for the rear camera and no microphone", async () => {
  const { camera, controller, mediaCalls } = loadCamera();

  await controller.start();

  assert.equal(mediaCalls.length, 1);
  assert.deepEqual(JSON.parse(JSON.stringify(mediaCalls[0].constraints)), {
    audio: false,
    video: { facingMode: { ideal: "environment" } },
  });
  assert.equal(Object.isFrozen(camera.CONSTRAINTS), true);
});

test("the stream is attached to the video and played with playsinline", async () => {
  const { controller, elements, stream } = loadCamera();

  const opened = await controller.start();

  assert.equal(opened, stream);
  assert.equal(elements.video.srcObject, stream);
  assert.equal(elements.video.getAttribute("playsinline"), "");
  assert.equal(elements.video.played, 1);
});

test("starting twice is one stream, not two permission prompts", async () => {
  const { controller, mediaCalls, stream } = loadCamera();

  const first = await controller.start();
  const second = await controller.start();

  assert.equal(mediaCalls.length, 1);
  assert.equal(first, stream);
  assert.equal(second, stream);
});

test("a captured photo is a JPEG File handed to the caller", async () => {
  const { camera, controller, elements, captures } = loadCamera();
  await controller.start();

  const file = await controller.capture();

  assert.equal(captures.length, 1);
  assert.equal(file, captures[0]);
  assert.equal(file.name, camera.CAPTURE_NAME);
  assert.equal(file.type, "image/jpeg");
  assert.equal(file.size, FRAME_BYTES.length);
  assert.equal(elements.canvas.width, 640);
  assert.equal(elements.canvas.height, 480);
  assert.deepEqual(elements.canvas.drawn, [[elements.video, 0, 0, 640, 480]]);
  assert.deepEqual(elements.canvas.encoding, {
    type: "image/jpeg",
    quality: 0.92,
  });
});

test("the captured photo passes through upload.choose and is sent by nobody", async () => {
  const { elements, uploadController, cameraController, sent, refusals } =
    loadUploadAndCamera();
  await cameraController.start();

  await cameraController.capture();

  const selected = uploadController.selected();
  assert.equal(selected.name, "camera-capture.jpg");
  assert.equal(selected.type, "image/jpeg");
  assert.equal(elements.preview.getAttribute("src").startsWith("blob:"), true);
  assert.equal(elements.panel.hidden, false);
  assert.equal(elements.error.textContent, "");
  assert.deepEqual(refusals, []);
  assert.deepEqual(sent, { fetches: 0, formData: 0 });
});

test("stopping the camera stops every track and detaches the surface", async () => {
  const { controller, elements, stream } = loadCamera();
  await controller.start();

  assert.equal(controller.stop(), null);

  assert.deepEqual(stream.tracks.map((track) => track.stopped), [true, true]);
  assert.equal(elements.video.srcObject, null);
  assert.equal(controller.active(), false);
});

test("stopping a camera that was never opened stops nothing", () => {
  const { controller, mediaCalls, refusals } = loadCamera();

  assert.equal(controller.stop(), null);

  assert.deepEqual(mediaCalls, []);
  assert.deepEqual(refusals, []);
});

test("a refused permission is named, and passed on with the browser's own reason kept", async () => {
  const denial = Object.assign(new Error("Permission denied"), {
    name: "NotAllowedError",
  });
  const { controller, mediaCalls, refusals, captures } = loadCamera({
    open: () => Promise.reject(denial),
  });

  const opened = await controller.start();

  assert.equal(opened, null);
  assert.equal(mediaCalls.length, 1);
  assert.equal(refusals.length, 1);
  assert.equal(refusals[0].name, "CameraError");
  assert.equal(refusals[0].code, "permission_denied");
  assert.equal(refusals[0].cause, denial);
  assert.equal(controller.active(), false);
  assert.deepEqual(captures, []);
});

test("a denied permission is told to grant the camera, not to check the connection", async () => {
  const denied = loadCamera({
    open: () =>
      Promise.reject(
        Object.assign(new Error("denied"), { name: "NotAllowedError" }),
      ),
  });
  const odd = loadCamera({
    open: () =>
      Promise.reject(Object.assign(new Error("odd"), { name: "WeirdError" })),
  });

  await denied.controller.start();
  await odd.controller.start();

  const [refusal] = denied.refusals;
  assert.equal(refusal.code, "permission_denied");
  assert.match(refusal.message, /access|permission/i);
  assert.match(refusal.message, /allow/i);
  // The other cause's remedy is not in this one, and neither is the generic
  // sentence: an officer who refused the prompt is not sent to the URL bar.
  assert.doesNotMatch(refusal.message, /https|localhost|secure|connection/i);
  assert.notEqual(refusal.message, odd.refusals[0].message);
});

test("a page served over plain HTTP is told the connection is the problem", async () => {
  const { controller, mediaCalls, refusals, captures } = loadCamera({
    navigator: {},
    isSecureContext: false,
  });

  const opened = await controller.start();

  assert.equal(opened, null);
  assert.deepEqual(mediaCalls, []);
  assert.equal(refusals.length, 1);
  const [refusal] = refusals;
  assert.equal(refusal.code, "insecure_context");
  assert.match(refusal.message, /secure/i);
  assert.match(refusal.message, /https|localhost/i);
  // The permission remedy would be wrong here: nothing was asked, so nothing
  // could have been refused.
  assert.doesNotMatch(refusal.message, /access|permission|allow/i);
  assert.deepEqual(captures, []);
});

test("a missing media API on a secure page is not blamed on the connection", async () => {
  for (const [label, navigatorStub, isSecureContext] of [
    ["no navigator at all", undefined, true],
    ["no mediaDevices", {}, true],
    ["a mediaDevices with no getUserMedia", { mediaDevices: {} }, true],
    ["a browser that never answered the question", {}, undefined],
  ]) {
    const { controller, refusals } = loadCamera({
      navigator: navigatorStub,
      isSecureContext,
    });

    await controller.start();

    assert.equal(refusals.length, 1, label);
    assert.equal(refusals[0].code, "no_media_api", label);
    assert.equal(refusals[0].cause, null, label);
    assert.doesNotMatch(refusals[0].message, /https|localhost|secure/i, label);
  }
});

test("the two named causes reach the officer as two different sentences", async () => {
  const insecure = loadCamera({ navigator: {}, isSecureContext: false });
  await insecure.controller.start();

  const denied = loadCamera({
    open: () =>
      Promise.reject(
        Object.assign(new Error("denied"), { name: "NotAllowedError" }),
      ),
  });
  await denied.controller.start();

  const [insecureRefusal] = insecure.refusals;
  const [deniedRefusal] = denied.refusals;
  assert.equal(insecureRefusal.code, "insecure_context");
  assert.equal(deniedRefusal.code, "permission_denied");
  assert.notEqual(insecureRefusal.message, deniedRefusal.message);
});

test("every cause the browser reports is named rather than folded into one", async () => {
  for (const [name, code] of [
    ["NotAllowedError", "permission_denied"],
    ["PermissionDeniedError", "permission_denied"],
    ["NotFoundError", "camera_not_found"],
    ["DevicesNotFoundError", "camera_not_found"],
    ["NotReadableError", "camera_busy"],
    ["TrackStartError", "camera_busy"],
    ["OverconstrainedError", "constraints_unsupported"],
  ]) {
    const { controller, refusals } = loadCamera({
      open: () => Promise.reject(Object.assign(new Error(name), { name })),
    });

    await controller.start();

    assert.equal(refusals.length, 1, name);
    assert.equal(refusals[0].code, code, name);
    assert.equal(refusals[0].cause.name, name, name);
  }
});

test("a cause the table does not know keeps the generic sentence", async () => {
  for (const cause of [
    Object.assign(new Error("odd"), { name: "WeirdError" }),
    Object.assign(new Error("nameless"), { name: "" }),
    new Error("plain"),
    null,
  ]) {
    const { controller, refusals } = loadCamera({
      open: () => Promise.reject(cause),
    });

    await controller.start();

    assert.equal(refusals.length, 1);
    assert.equal(refusals[0].code, "start_failed", String(cause));
    assert.equal(refusals[0].cause, cause);
    assert.doesNotMatch(
      refusals[0].message,
      /access|permission|allow|https|localhost|secure|no camera|in use/i,
      String(cause),
    );
  }
});

test("the refusals that name no cause still name no cause", async () => {
  const idle = loadCamera();
  await idle.controller.capture();

  assert.equal(idle.refusals.length, 1);
  assert.equal(idle.refusals[0].code, "not_running");
  assert.doesNotMatch(
    idle.refusals[0].message,
    /access|permission|allow|https|localhost|secure|no camera|in use/i,
  );
});
test("taking a photo before the camera is on is refused, not attempted", async () => {
  const { controller, elements, refusals, captures, mediaCalls } = loadCamera();

  const file = await controller.capture();

  assert.equal(file, null);
  assert.equal(refusals.length, 1);
  assert.equal(refusals[0].code, "not_running");
  assert.deepEqual(captures, []);
  assert.deepEqual(mediaCalls, []);
  assert.deepEqual(elements.canvas.drawn, []);
});

for (const [label, video] of [
  ["no frame yet", { videoWidth: 0, videoHeight: 480 }],
  ["an unknown frame size", { videoWidth: undefined, videoHeight: 480 }],
  ["a frame size that is not a number", { videoWidth: "640", videoHeight: 480 }],
]) {
  test(`${label} is refused rather than drawn at zero`, async () => {
    const { controller, elements, refusals } = loadCamera();
    Object.assign(elements.video, video);
    await controller.start();

    const file = await controller.capture();

    assert.equal(file, null);
    assert.equal(refusals.length, 1);
    assert.equal(refusals[0].code, "no_frame");
    assert.deepEqual(elements.canvas.drawn, []);
  });
}

test("a canvas that cannot encode the frame is refused by name", async () => {
  const { controller, refusals, captures } = loadCamera({ blob: null });
  await controller.start();

  const file = await controller.capture();

  assert.equal(file, null);
  assert.equal(refusals.length, 1);
  assert.equal(refusals[0].code, "capture_failed");
  assert.deepEqual(captures, []);
});

test("the binding names the six elements and two callbacks it needs", () => {
  const { camera } = loadCamera();

  assert.deepEqual(Array.from(camera.REQUIRED_ELEMENTS).sort(), [
    "canvas",
    "capture",
    "consent",
    "start",
    "stop",
    "video",
  ]);
  assert.deepEqual(Array.from(camera.REQUIRED_CALLBACKS).sort(), [
    "onCapture",
    "onRefuse",
  ]);
});

test("the binding refuses a missing element or callback by name", () => {
  const { camera, elements } = loadCamera();

  const base = {
    ...elements,
    onCapture: () => {},
    onRefuse: () => {},
  };
  for (const name of camera.REQUIRED_ELEMENTS) {
    const without = { ...base };
    delete without[name];
    refuses(() => camera.bindCamera(without), "missing_element", name);
  }
  for (const name of camera.REQUIRED_CALLBACKS) {
    const without = { ...base };
    delete without[name];
    refuses(() => camera.bindCamera(without), "missing_callback", name);
  }
  refuses(() => camera.bindCamera(), "missing_element", "video");
});

test("the module sends nothing and asks for no file", () => {
  assert.doesNotMatch(source, /fetch|FormData|XMLHttpRequest|sendBeacon|FileReader/);
  assert.doesNotMatch(source, /localStorage|sessionStorage|indexedDB|new Date|Date\.now/);
});

test("no page loads the module yet, so the build copies nothing", () => {
  const { staticFiles, pageFileNames } = buildFileNames();
  const pages = pageFileNames.map((fileName) =>
    fs.readFileSync(path.join(__dirname, fileName), "utf8"),
  );
  const shell = fs.readFileSync(path.join(__dirname, "shell.html"), "utf8");

  assert.ok(!staticFiles.includes("camera.js"));
  for (const markup of [...pages, shell]) {
    assert.doesNotMatch(markup, /camera\.js/);
  }
});
