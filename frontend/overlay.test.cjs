const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const { buildFileNames } = require("./build.cjs");

const source = fs.readFileSync(path.join(__dirname, "overlay.js"), "utf8");

// The smallest element a region can be built on: the one class, the one
// attribute and the style properties the overlay writes, and nothing else, so
// a property nobody implemented here would throw rather than pass quietly.
function createElement(tagName = "div") {
  const attributes = new Map();
  const classes = new Set();
  const properties = new Map();
  return {
    tagName: tagName.toUpperCase(),
    attributes: attributes,
    classes: classes,
    properties: properties,
    children: [],
    listeners: {},
    classList: {
      add: function (name) {
        classes.add(name);
      },
      remove: function (name) {
        classes.delete(name);
      },
      contains: function (name) {
        return classes.has(name);
      },
    },
    style: {
      setProperty: function (name, value) {
        properties.set(name, value);
      },
    },
    setAttribute: function (name, value) {
      attributes.set(name, String(value));
    },
    getAttribute: function (name) {
      return attributes.has(name) ? attributes.get(name) : null;
    },
    appendChild: function (child) {
      this.children.push(child);
      return child;
    },
    removeChild: function (child) {
      const at = this.children.indexOf(child);
      if (at < 0) {
        throw new Error("the overlay removed an element it never drew");
      }
      this.children.splice(at, 1);
      return child;
    },
    addEventListener: function (event, callback) {
      this.listeners[event] = callback;
    },
    // The two events a region answers to, fired by hand and counted: the
    // sandbox has no browser, so a click is whatever a test says it is.
    fire: function (event) {
      return this.listeners[event.type]
        ? this.listeners[event.type](event)
        : undefined;
    },
    click: function () {
      return this.fire({ type: "click" });
    },
    press: function (key) {
      let prevented = 0;
      this.fire({
        type: "keydown",
        key: key,
        preventDefault: function () {
          prevented += 1;
        },
      });
      return prevented;
    },
  };
}

// One sandbox per overlay, with fetch and FormData as recorders rather than
// absences: the claim is that this module sends nothing, so a send has to be
// visible to fail on.
function loadOverlay() {
  const created = [];
  const sent = { fetches: 0, formData: 0 };
  const sandbox = {
    window: {},
    document: {
      createElement: function (tagName) {
        const element = createElement(tagName);
        created.push(element);
        return element;
      },
    },
    fetch: function () {
      sent.fetches += 1;
      throw new Error("the overlay must not send anything");
    },
    FormData: function () {
      sent.formData += 1;
      throw new Error("the overlay must not build a request");
    },
  };
  vm.runInNewContext(source, sandbox);
  return { overlay: sandbox.window.DRISHTI_OVERLAY, created: created, sent: sent };
}

function bind(overlay, options = {}) {
  const container = createElement();
  const controller = overlay.bindOverlay({
    container: container,
    image: { width: 1600, height: 1200 },
    display: { width: 800, height: 600 },
    onSelect: () => {},
    ...options,
  });
  return { controller: controller, container: container };
}

function refuses(check, code, what) {
  assert.throws(check, (error) => {
    assert.equal(error.name, "OverlayError", `${what} must be the overlay's own refusal`);
    assert.equal(error.code, code, `${what} must be refused as ${code}`);
    assert.ok(error.message.length > 0, `${what} must say what it needs`);
    return true;
  });
}

// The module builds its arrays and objects inside the sandbox realm, so they
// are copied into this one before any comparison: a deep comparison reads the
// prototype as well as the values.
function cornersOf(placed) {
  return Array.from(placed, (corner) => [Number(corner.x), Number(corner.y)]);
}

function boundsOf(overlay, corners) {
  const box = overlay.boundsOf(corners);
  return {
    left: box.left,
    top: box.top,
    width: box.width,
    height: box.height,
  };
}

// The three size combinations the mapping is held to: a document shown at
// half size, one shown three times larger, and one shown in a box of another
// shape -- a square document in a wide frame, which is the only combination
// where one factor cannot serve both axes.
const COMBINATIONS = [
  {
    name: "shown at half size",
    image: { width: 1600, height: 1200 },
    display: { width: 800, height: 600 },
    box: { x: 200, y: 300, width: 400, height: 300 },
    placedBox: [
      [100, 150],
      [300, 150],
      [300, 300],
      [100, 300],
    ],
    polygon: [
      [1600, 0],
      [1600, 1200],
      [800, 600],
    ],
    placedPolygon: [
      [800, 0],
      [800, 600],
      [400, 300],
    ],
  },
  {
    name: "shown three times larger",
    image: { width: 400, height: 300 },
    display: { width: 1200, height: 900 },
    box: { x: 50, y: 75, width: 100, height: 75 },
    placedBox: [
      [150, 225],
      [450, 225],
      [450, 450],
      [150, 450],
    ],
    polygon: [
      [400, 0],
      [400, 300],
      [200, 150],
    ],
    placedPolygon: [
      [1200, 0],
      [1200, 900],
      [600, 450],
    ],
  },
  {
    name: "shown in a box of another shape",
    image: { width: 1000, height: 1000 },
    display: { width: 800, height: 400 },
    box: { x: 125, y: 250, width: 250, height: 250 },
    placedBox: [
      [100, 100],
      [300, 100],
      [300, 200],
      [100, 200],
    ],
    polygon: [
      [1000, 0],
      [1000, 1000],
      [500, 500],
    ],
    placedPolygon: [
      [800, 0],
      [800, 400],
      [400, 200],
    ],
  },
];

test("a box and a polygon land on the image at three size combinations", () => {
  const { overlay } = loadOverlay();

  // Every combination carries the same region as a share of its image, so a
  // mapping that read the display size where the image size belongs, or that
  // scaled one axis by the other, cannot answer all three correctly.
  for (const combination of COMBINATIONS) {
    const fractions = overlay.normaliseRegion(combination.box, combination.image);
    assert.deepEqual(
      cornersOf(fractions),
      [
        [0.125, 0.25],
        [0.375, 0.25],
        [0.375, 0.5],
        [0.125, 0.5],
      ],
      `the box normalises once for a document ${combination.name}`,
    );
    assert.deepEqual(
      cornersOf(
        overlay.placeRegion(
          combination.box,
          combination.image,
          combination.display,
        ),
      ),
      combination.placedBox,
      `the box is placed where it belongs, ${combination.name}`,
    );
    assert.deepEqual(
      cornersOf(
        overlay.placeRegion(
          combination.polygon,
          combination.image,
          combination.display,
        ),
      ),
      combination.placedPolygon,
      `the polygon is placed where it belongs, ${combination.name}`,
    );
  }
});

test("one axis is never scaled by the other", () => {
  const { overlay } = loadOverlay();
  const stretched = COMBINATIONS[2];

  // 800/1000 across and 400/1000 down: a single factor would place the right
  // edge at 400 and the bottom edge at 200.
  const placed = overlay.placeRegion(
    stretched.box,
    stretched.image,
    stretched.display,
  );
  const width = placed[1].x - placed[0].x;
  const height = placed[2].y - placed[0].y;
  assert.equal(width, 200, "the width follows the horizontal factor");
  assert.equal(height, 100, "the height follows the vertical factor");
  assert.notEqual(width, height, "one factor cannot have served both axes");
});

test("a box is read as the corners the service promises", () => {
  const { overlay } = loadOverlay();
  const normalised = overlay.normaliseRegion(
    { x: 200, y: 300, width: 400, height: 300 },
    { width: 1600, height: 1200 },
  );

  assert.equal(normalised.length, 4, "a box is four corners");
  assert.deepEqual(
    cornersOf(normalised),
    [
      [0.125, 0.25],
      [0.375, 0.25],
      [0.375, 0.5],
      [0.125, 0.5],
    ],
    "clockwise from the top left, with the far corner left out",
  );
  assert.deepEqual(
    cornersOf(
      overlay.placeRegion(
        { x: 200, y: 300, width: 400, height: 300 },
        { width: 1600, height: 1200 },
        { width: 800, height: 600 },
      ),
    ),
    COMBINATIONS[0].placedBox,
    "a box places as the rectangle it is",
  );
});

test("a polygon keeps its own corners, in its own order", () => {
  const { overlay } = loadOverlay();
  const polygon = [
    [1600, 0],
    [1600, 1200],
    [800, 600],
  ];

  assert.deepEqual(
    cornersOf(overlay.placeRegion(polygon, COMBINATIONS[0].image, COMBINATIONS[0].display)),
    COMBINATIONS[0].placedPolygon,
    "a triangle is not squared off into a box",
  );
  assert.deepEqual(
    cornersOf(
      overlay.placeRegion(
        [
          [0, 0],
          [800, 120],
          [1600, 0],
          [1600, 1200],
          [0, 1200],
        ],
        COMBINATIONS[0].image,
        COMBINATIONS[0].display,
      ),
    ),
    [
      [0, 0],
      [400, 60],
      [800, 0],
      [800, 600],
      [0, 600],
    ],
    "a five-corner region keeps all five",
  );
});

test("the drawn shape is the region's own, clipped inside its bounding box", () => {
  const { overlay } = loadOverlay();
  const box = COMBINATIONS[0].box;
  const polygon = COMBINATIONS[0].polygon;

  const boxCorners = overlay.placeRegion(
    box,
    COMBINATIONS[0].image,
    COMBINATIONS[0].display,
  );
  assert.equal(
    overlay.clipPathFor(boxCorners, boundsOf(overlay, boxCorners)),
    null,
    "a region already filling its box needs no clip",
  );

  const polygonCorners = overlay.placeRegion(
    polygon,
    COMBINATIONS[0].image,
    COMBINATIONS[0].display,
  );
  const bounds = boundsOf(overlay, polygonCorners);
  assert.deepEqual(bounds, { left: 400, top: 0, width: 400, height: 600 });
  assert.equal(
    overlay.clipPathFor(polygonCorners, bounds),
    "polygon(100% 0%, 100% 100%, 0% 50%)",
    "the clip is measured inside the box the element already occupies",
  );
});

test("a region that locates nothing is drawn as nothing, and is not refused", () => {
  const { overlay } = loadOverlay();
  const empty = { x: 10, y: 10, width: 0, height: 0 };

  const placed = overlay.placeRegion(empty, COMBINATIONS[0].image, COMBINATIONS[0].display);
  assert.equal(placed.length, 4, "the corners are still read");
  assert.deepEqual(boundsOf(overlay, placed), {
    left: 5,
    top: 5,
    width: 0,
    height: 0,
  });
  assert.equal(
    overlay.clipPathFor(placed, boundsOf(overlay, placed)),
    null,
    "there is nothing to clip",
  );
});

test("draw positions one element per region on the displayed image", () => {
  const { overlay } = loadOverlay();
  const { controller, container } = bind(overlay);

  const drawn = controller.draw([
    { id: "mrz_check_failed", region: COMBINATIONS[0].box },
    { id: "glare_detected", region: COMBINATIONS[0].polygon },
  ]);

  assert.equal(drawn, 2);
  assert.equal(controller.placed(), 2);
  assert.equal(container.children.length, 2);

  const [box, polygon] = container.children;
  assert.ok(box.classes.has(overlay.REGION_CLASS));
  assert.equal(box.getAttribute(overlay.REGION_MARKER), "mrz_check_failed");
  assert.deepEqual(
    [
      box.properties.get("position"),
      box.properties.get("left"),
      box.properties.get("top"),
      box.properties.get("width"),
      box.properties.get("height"),
    ],
    ["absolute", "100px", "150px", "200px", "150px"],
    "the box sits where its four corners say",
  );
  assert.equal(
    box.properties.has("clip-path"),
    false,
    "a plain box is not clipped",
  );

  assert.deepEqual(
    [
      polygon.properties.get("position"),
      polygon.properties.get("left"),
      polygon.properties.get("top"),
      polygon.properties.get("width"),
      polygon.properties.get("height"),
      polygon.properties.get("clip-path"),
    ],
    [
      "absolute",
      "400px",
      "0px",
      "400px",
      "600px",
      "polygon(100% 0%, 100% 100%, 0% 50%)",
    ],
    "the polygon occupies its bounding box and is clipped to its own shape",
  );

  const regions = controller.regions();
  assert.equal(regions.length, 2);
  assert.deepEqual(cornersOf(regions[1].corners), COMBINATIONS[0].placedPolygon);
});

test("a finding with no region is counted, and nothing is drawn for it", () => {
  const { overlay } = loadOverlay();
  const { controller, container } = bind(overlay);

  const drawn = controller.draw([
    { id: "glare_detected", region: null },
    { id: "mrz_check_failed", region: COMBINATIONS[0].box },
  ]);

  assert.equal(drawn, 1);
  assert.equal(controller.unplaced(), 1);
  assert.equal(container.children.length, 1);
  assert.equal(
    container.children[0].getAttribute(overlay.REGION_MARKER),
    "mrz_check_failed",
  );
});

test("a second draw re-places the same regions at another display size", () => {
  const { overlay } = loadOverlay();
  const { controller, container } = bind(overlay);
  const flags = [{ id: "mrz_check_failed", region: COMBINATIONS[0].box }];

  controller.draw(flags);
  assert.equal(container.children[0].properties.get("width"), "200px");

  const drawn = controller.draw(flags, { width: 1200, height: 900 });

  assert.equal(drawn, 1);
  assert.equal(container.children.length, 1, "the old element was taken away");
  assert.equal(container.children[0].properties.get("left"), "150px");
  assert.equal(container.children[0].properties.get("top"), "225px");
  assert.equal(container.children[0].properties.get("width"), "300px");
  assert.equal(controller.display().width, 800, "the bound size is still readable");
});

test("a region that cannot be mapped leaves the drawing as it was", () => {
  const { overlay } = loadOverlay();
  const { controller, container } = bind(overlay);

  controller.draw([{ id: "mrz_check_failed", region: COMBINATIONS[0].box }]);
  refuses(
    () =>
      controller.draw([
        { id: "mrz_check_failed", region: COMBINATIONS[0].box },
        { id: "glare_detected", region: "not a region" },
      ]),
    "bad_region",
    "a region that is neither a box nor a polygon",
  );

  assert.equal(container.children.length, 1, "nothing was drawn and nothing removed");
  assert.equal(
    container.children[0].getAttribute(overlay.REGION_MARKER),
    "mrz_check_failed",
  );
});

test("clear takes away what the overlay drew and nothing else", () => {
  const { overlay } = loadOverlay();
  const { controller, container } = bind(overlay);
  const pageChild = createElement("img");

  controller.draw([{ id: "mrz_check_failed", region: COMBINATIONS[0].box }]);
  container.appendChild(pageChild);

  assert.equal(controller.clear(), true);
  assert.deepEqual(container.children, [pageChild], "the page's own child stays");
  assert.equal(controller.placed(), 0);
  assert.equal(controller.clear(), false, "a second clear removed nothing");
});

test("every refusal names its own cause", () => {
  const { overlay } = loadOverlay();
  const image = { width: 1600, height: 1200 };
  const display = { width: 800, height: 600 };
  const region = COMBINATIONS[0].box;

  for (const name of overlay.REQUIRED_ELEMENTS) {
    const without = { container: createElement(), image: image, display: display };
    delete without[name];
    refuses(() => overlay.bindOverlay(without), "missing_element", `a binding with no ${name}`);
  }
  refuses(() => overlay.bindOverlay(), "missing_element", "a binding with no options");

  for (const bad of [
    undefined,
    null,
    {},
    { width: 1600 },
    { width: 0, height: 1200 },
    { width: -1, height: 1200 },
    { width: "1600", height: 1200 },
    { width: 1600, height: Number.NaN },
    { width: 1600, height: Number.POSITIVE_INFINITY },
  ]) {
    refuses(
      () => overlay.bindOverlay({ container: createElement(), image: bad, display: display }),
      "bad_image_size",
      "an image size that is not two positive numbers",
    );
    refuses(
      () => overlay.normaliseRegion(region, bad),
      "bad_image_size",
      "an image size that is not two positive numbers",
    );
  }

  for (const bad of [
    undefined,
    null,
    { width: 800 },
    { width: 0, height: 600 },
    { width: 800, height: -600 },
    { width: "800", height: 600 },
    { width: 800, height: Number.NaN },
  ]) {
    refuses(
      () => overlay.bindOverlay({ container: createElement(), image: image, display: bad }),
      "bad_display_size",
      "a display size that is not two positive numbers",
    );
    refuses(
      () => overlay.placeRegion(region, image, bad),
      "bad_display_size",
      "a display size that is not two positive numbers",
    );
  }

  for (const bad of [
    undefined,
    "a region",
    42,
    true,
    [10, 20],
    [
      [0, 0],
      [10, 10],
    ],
    [
      [0, 0],
      [10, 10],
      [0, 10, 20],
    ],
    [
      [0, 0],
      ["10", 10],
      [0, 10],
    ],
    [
      [0, 0],
      [10, 10],
      null,
    ],
    { x: 0, y: 0, width: "10", height: 10 },
    { x: 0, y: 0, width: 10 },
    [0, 0, 10, 10],
  ]) {
    refuses(
      () => overlay.placeRegion(bad, image, display),
      "bad_region",
      "a region that is neither null, a box nor a polygon",
    );
  }

  for (const name of overlay.REQUIRED_CALLBACKS) {
    const without = {
      container: createElement(),
      image: image,
      display: display,
      onSelect: () => {},
    };
    delete without[name];
    refuses(
      () => overlay.bindOverlay(without),
      "missing_callback",
      "a binding with no " + name,
    );
  }

  const { controller } = bind(overlay);
  for (const bad of [undefined, null, {}, "flags", 7]) {
    refuses(() => controller.draw(bad), "bad_flags", "findings that are not a list");
  }
  refuses(
    () => controller.draw([{ id: "mrz_check_failed" }]),
    "bad_region",
    "a finding with no region field at all",
  );
});

test("null is the one region that maps to nothing", () => {
  const { overlay } = loadOverlay();
  assert.equal(overlay.normaliseRegion(null, COMBINATIONS[0].image), null);
  assert.equal(
    overlay.placeRegion(null, COMBINATIONS[0].image, COMBINATIONS[0].display),
    null,
  );
});

test("the overlay sends nothing, reads no clock and stores nothing", () => {
  const { overlay, sent } = loadOverlay();
  const { controller, container } = bind(overlay);

  controller.draw([
    { id: "mrz_check_failed", region: COMBINATIONS[0].box },
    { id: "glare_detected", region: COMBINATIONS[0].polygon },
  ]);
  controller.clear();

  assert.deepEqual(sent, { fetches: 0, formData: 0 });
  assert.equal(container.children.length, 0);
  assert.doesNotMatch(
    source,
    /XMLHttpRequest|sendBeacon|localStorage|sessionStorage|indexedDB|new Date|Date\.now|getBoundingClientRect/,
  );
});

test("the overlay asks for no measurement it cannot be given", () => {
  // The displayed size is measured by the page and handed over, because the
  // module runs no layout and reads no box: a region cannot be placed from a
  // container whose size nothing told it.
  assert.doesNotMatch(source, /clientWidth|offsetWidth|getBoundingClientRect/);
});

test("no page loads the overlay yet, so the build copies nothing", () => {
  const { staticFiles, pageFileNames } = buildFileNames();
  const pages = pageFileNames.map((fileName) =>
    fs.readFileSync(path.join(__dirname, fileName), "utf8"),
  );
  const shell = fs.readFileSync(path.join(__dirname, "shell.html"), "utf8");

  assert.ok(!staticFiles.includes("overlay.js"));
  for (const markup of [...pages, shell]) {
    assert.doesNotMatch(markup, /overlay\.js/);
  }
});

test("clicking a region selects its flag, and clicking a flag highlights its region", () => {
  const { overlay } = loadOverlay();
  const chosen = [];
  const { controller, container } = bind(overlay, {
    onSelect: (flagId) => {
      chosen.push(flagId);
      controller.select(flagId);
    },
  });

  controller.draw([
    { id: "mrz_check_failed", region: COMBINATIONS[0].box },
    { id: "glare_detected", region: COMBINATIONS[0].polygon },
  ]);
  const [box, polygon] = container.children;

  // Region to flag: the click names the flag, and the answer the page gives
  // lights the region the click was on and no other.
  box.click();
  assert.deepEqual(chosen, ["mrz_check_failed"], "the click reached the page as its own flag");
  assert.equal(controller.selected(), "mrz_check_failed");
  assert.equal(box.getAttribute(overlay.REGION_MARKER), "mrz_check_failed");
  assert.ok(box.classes.has(overlay.REGION_SELECTED_CLASS), "the clicked region is lit");
  assert.equal(box.getAttribute(overlay.REGION_STATE), "true");
  assert.equal(polygon.classes.has(overlay.REGION_SELECTED_CLASS), false);
  assert.equal(polygon.getAttribute(overlay.REGION_STATE), "false");

  // Flag to region: a click on the flag row is select(), and the region lit
  // is the one whose own marker carries that id.
  assert.equal(controller.select("glare_detected"), true, "a flag with a region is lit");
  assert.equal(controller.selected(), "glare_detected");
  assert.ok(polygon.classes.has(overlay.REGION_SELECTED_CLASS));
  assert.equal(polygon.getAttribute(overlay.REGION_STATE), "true");
  assert.equal(box.classes.has(overlay.REGION_SELECTED_CLASS), false, "one region is lit at a time");
  assert.equal(box.getAttribute(overlay.REGION_STATE), "false");

  polygon.click();
  assert.deepEqual(chosen, ["mrz_check_failed", "glare_detected"], "the lit region answers with the same flag");
  assert.equal(controller.selected(), "glare_detected", "the round trip ended where it began");
});

test("a region naming a flag is a button, and Enter and Space both choose it", () => {
  const { overlay } = loadOverlay();
  const chosen = [];
  const { controller, container } = bind(overlay, {
    onSelect: (flagId) => chosen.push(flagId),
  });

  controller.draw([{ id: "mrz_check_failed", region: COMBINATIONS[0].box }]);
  const [region] = container.children;

  assert.equal(region.getAttribute("role"), overlay.REGION_ROLE);
  assert.equal(region.getAttribute("tabindex"), overlay.REGION_TABINDEX);
  assert.equal(region.getAttribute(overlay.REGION_STATE), "false", "nothing is chosen to begin with");

  assert.equal(region.press("Enter"), 1, "Enter does not reach the browser");
  assert.equal(region.press(" "), 1, "Space does not scroll the document");
  assert.equal(region.press("Tab"), 0, "any other key is the browser own");
  assert.deepEqual(chosen, ["mrz_check_failed", "mrz_check_failed"], "two activations, two flag ids");
});

test("a region naming no flag is drawn, and is not a control", () => {
  const { overlay } = loadOverlay();
  const chosen = [];
  const { controller, container } = bind(overlay, {
    onSelect: (flagId) => chosen.push(flagId),
  });

  controller.draw([{ region: COMBINATIONS[0].box }]);
  const [region] = container.children;

  assert.equal(region.getAttribute(overlay.REGION_MARKER), null, "it names no flag");
  assert.equal(region.getAttribute("role"), null, "no role and no control");
  assert.equal(region.getAttribute("tabindex"), null);
  assert.equal(region.getAttribute(overlay.REGION_STATE), null);

  region.click();
  assert.deepEqual(chosen, [], "there is nothing for it to choose");
  assert.equal(controller.select(undefined), false);
  assert.equal(region.classes.has(overlay.REGION_SELECTED_CLASS), false);
});

test("a flag with no region leaves nothing lit rather than the last highlight standing", () => {
  const { overlay } = loadOverlay();
  const { controller, container } = bind(overlay);
  const flags = [
    { id: "mrz_check_failed", region: COMBINATIONS[0].box },
    { id: "glare_detected", region: null },
  ];

  controller.draw(flags);
  const [box] = container.children;
  controller.select("mrz_check_failed");
  assert.ok(box.classes.has(overlay.REGION_SELECTED_CLASS));

  assert.equal(controller.select("glare_detected"), false, "a flag the overlay drew nothing for");
  assert.equal(controller.selected(), null);
  assert.equal(box.classes.has(overlay.REGION_SELECTED_CLASS), false, "the old highlight went with it");
  assert.equal(box.getAttribute(overlay.REGION_STATE), "false");

  // A second draw is a new set of elements, so the selection cannot survive it.
  controller.select("mrz_check_failed");
  controller.draw([{ id: "mrz_check_failed", region: COMBINATIONS[0].box }]);
  assert.equal(controller.selected(), null);
  assert.equal(container.children[0].getAttribute(overlay.REGION_STATE), "false");
});
