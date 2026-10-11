(() => {
  "use strict";

  // Where a flag's region sits on the document an officer is looking at. The
  // service records a region in the pixels of the image it screened, and the
  // page shows that image in whatever box the layout gave it; this module is
  // the one step between those two sets of pixels.

  const MIN_REGION_CORNERS = 3;

  const REQUIRED_ELEMENTS = ["container"];
  const REQUIRED_CALLBACKS = ["onSelect"];

  // G9: the design system ships no box, polygon or highlight, so a region
  // element carries the one class of its own and one attribute naming the
  // flag it belongs to.
  const REGION_CLASS = "result-region";
  const REGION_MARKER = "data-result-region";

  // G2: the sheet ships no control laid over an image either, so a region
  // naming a flag says what it is, takes a tab stop and carries the state of
  // the flag it points at. A region naming no flag is not a control.
  const REGION_ROLE = "button";
  const REGION_TABINDEX = "0";
  const REGION_STATE = "aria-pressed";
  const REGION_SELECTED_CLASS = "result-region-selected";

  const CLICK_EVENT = "click";
  const KEY_EVENT = "keydown";
  const ACTIVATION_KEYS = ["Enter", " "];

  // One rounding for the whole module, so a corner written into a style
  // string and the same corner read back are the same number.
  const ROUNDING = 100;

  const CONTAINER_MESSAGE =
    "The region overlay needs an element to draw into: ";
  const IMAGE_SIZE_MESSAGE =
    "The image size must be two positive numbers: the size the screening recorded.";
  const DISPLAY_SIZE_MESSAGE =
    "The display size must be two positive numbers: the size the image is shown at.";
  const BAD_REGION_MESSAGE =
    "A region must be null, a box of x, y, width and height, or a polygon of " +
    "at least " +
    MIN_REGION_CORNERS +
    " corners, each a pair of numbers.";
  const BAD_FLAGS_MESSAGE =
    "The findings to draw must be a list, so every region is mapped from one.";
  const MISSING_CALLBACK_MESSAGE = "The region overlay needs a callback named ";

  class OverlayError extends Error {
    constructor(code, message) {
      super(message);
      this.name = "OverlayError";
      this.code = code;
    }
  }

  function isNumber(value) {
    return typeof value === "number" && Number.isFinite(value);
  }

  function round(value) {
    return Math.round(value * ROUNDING) / ROUNDING;
  }

  function pixels(value) {
    return round(value) + "px";
  }

  function readSize(size, code, message) {
    const width = size ? size.width : undefined;
    const height = size ? size.height : undefined;
    if (!isNumber(width) || !isNumber(height) || width <= 0 || height <= 0) {
      throw new OverlayError(code, message);
    }
    return { width: width, height: height };
  }

  function readElement(settings, name) {
    const element = settings ? settings[name] : null;
    if (!element) {
      throw new OverlayError(
        "missing_element",
        CONTAINER_MESSAGE + name + ".",
      );
    }
    return element;
  }

  function readCallback(settings, name) {
    const callback = settings ? settings[name] : null;
    if (typeof callback !== "function") {
      throw new OverlayError(
        "missing_callback",
        MISSING_CALLBACK_MESSAGE + name + ".",
      );
    }
    return callback;
  }

  function isBox(region) {
    return (
      typeof region === "object" &&
      region !== null &&
      !Array.isArray(region) &&
      isNumber(region.x) &&
      isNumber(region.y) &&
      isNumber(region.width) &&
      isNumber(region.height)
    );
  }

  function isCorner(corner) {
    return (
      Array.isArray(corner) &&
      corner.length === 2 &&
      isNumber(corner[0]) &&
      isNumber(corner[1])
    );
  }

  // Corners run clockwise from the top left with the far corner left out,
  // which is the order app/risk/flags.py records as a promise.
  function boxCorners(box) {
    const right = box.x + box.width;
    const bottom = box.y + box.height;
    return [
      [box.x, box.y],
      [right, box.y],
      [right, bottom],
      [box.x, bottom],
    ];
  }

  // Both shapes leave here as the same thing: corners in the pixels of the
  // screened image. A missing field is refused rather than read as no region,
  // because null is the one record the service writes when it found nothing.
  function readCorners(region) {
    if (region === null) {
      return null;
    }
    if (isBox(region)) {
      return boxCorners(region);
    }
    if (
      !Array.isArray(region) ||
      region.length < MIN_REGION_CORNERS ||
      !region.every(isCorner)
    ) {
      throw new OverlayError("bad_region", BAD_REGION_MESSAGE);
    }
    return region.map((corner) => [corner[0], corner[1]]);
  }

  // The corners as a share of the image, so one region's shape can be drawn
  // on any box that image is later shown in.
  function normaliseRegion(region, image) {
    const size = readSize(image, "bad_image_size", IMAGE_SIZE_MESSAGE);
    const corners = readCorners(region);
    if (corners === null) {
      return null;
    }
    return corners.map((corner) => ({
      x: corner[0] / size.width,
      y: corner[1] / size.height,
    }));
  }

  // One factor per axis: the displayed box is whatever the layout gave the
  // image, and a region has to land where its own pixel now sits.
  function placeRegion(region, image, display) {
    const shown = readSize(display, "bad_display_size", DISPLAY_SIZE_MESSAGE);
    const fractions = normaliseRegion(region, image);
    if (fractions === null) {
      return null;
    }
    return fractions.map((corner) => ({
      x: corner.x * shown.width,
      y: corner.y * shown.height,
    }));
  }

  function boundsOf(corners) {
    const xs = corners.map((corner) => corner.x);
    const ys = corners.map((corner) => corner.y);
    const left = Math.min(...xs);
    const top = Math.min(...ys);
    return {
      left: left,
      top: top,
      width: Math.max(...xs) - left,
      height: Math.max(...ys) - top,
    };
  }

  function isRectangle(corners) {
    if (corners.length !== 4) {
      return false;
    }
    const box = boundsOf(corners);
    return corners.every(
      (corner) =>
        (corner.x === box.left || corner.x === box.left + box.width) &&
        (corner.y === box.top || corner.y === box.top + box.height),
    );
  }

  // The shape is clipped inside its own bounding box, so one element carries
  // both the position and the outline. Corners already filling that box need
  // no clip, which is every plain box.
  function clipPathFor(corners, box) {
    if (box.width <= 0 || box.height <= 0 || isRectangle(corners)) {
      return null;
    }
    const points = corners.map(
      (corner) =>
        round(((corner.x - box.left) / box.width) * 100) +
        "% " +
        round(((corner.y - box.top) / box.height) * 100) +
        "%",
    );
    return "polygon(" + points.join(", ") + ")";
  }

  // bindOverlay wires one image's regions to the box it is shown in, and
  // draws nothing until a page calls draw().
  function bindOverlay(options) {
    const settings = options || {};
    const container = readElement(settings, "container");
    const image = readSize(
      settings.image,
      "bad_image_size",
      IMAGE_SIZE_MESSAGE,
    );
    const display = readSize(
      settings.display,
      "bad_display_size",
      DISPLAY_SIZE_MESSAGE,
    );
    const onSelect = readCallback(settings, "onSelect");

    let drawn = [];
    let unplaced = 0;
    let selectedId = null;

    // Every region is measured before anything is written, so a region that
    // cannot be mapped leaves the document as it was rather than half drawn.
    function measure(flags, shown) {
      if (!Array.isArray(flags)) {
        throw new OverlayError("bad_flags", BAD_FLAGS_MESSAGE);
      }
      const measured = [];
      let without = 0;
      for (const flag of flags) {
        const region = flag ? flag.region : null;
        const corners = placeRegion(region, image, shown);
        if (corners === null) {
          without += 1;
          continue;
        }
        const bounds = boundsOf(corners);
        measured.push({
          flagId: flag && typeof flag.id === "string" ? flag.id : null,
          corners: corners,
          box: bounds,
          clip: clipPathFor(corners, bounds),
        });
      }
      return { measured: measured, without: without };
    }

    // A region that names a flag answers for itself: the page is told which
    // flag was hit and nothing else. A click is a selection and not a toggle,
    // so the flag id handed over is always a string.
    function choose(region) {
      onSelect(region.flagId);
    }

    // Enter and Space are what a button answers to, and Space would scroll the
    // document past the region the officer just chose.
    function onKeyDown(region, event) {
      if (ACTIVATION_KEYS.indexOf(event.key) >= 0) {
        event.preventDefault();
        choose(region);
      }
    }

    function mark(region, on) {
      if (on) {
        region.element.classList.add(REGION_SELECTED_CLASS);
      } else {
        region.element.classList.remove(REGION_SELECTED_CLASS);
      }
      region.element.setAttribute(REGION_STATE, on ? "true" : "false");
    }

    // The flag list's half of the round trip. An id nothing drew -- a flag
    // with no region, or one this overlay was never given -- leaves nothing
    // lit rather than leaving the previous highlight standing.
    function select(flagId) {
      const wanted =
        typeof flagId === "string" && flagId.length > 0 ? flagId : null;
      const target =
        wanted === null
          ? null
          : drawn.find((region) => region.flagId === wanted) || null;
      if (selectedId !== null) {
        for (const region of drawn) {
          if (region.flagId === selectedId) {
            mark(region, false);
          }
        }
      }
      selectedId = null;
      if (target !== null) {
        mark(target, true);
        selectedId = target.flagId;
      }
      return target !== null;
    }

    function draw(flags, shown) {
      const target =
        shown === undefined
          ? display
          : readSize(shown, "bad_display_size", DISPLAY_SIZE_MESSAGE);
      const measured = measure(flags, target);
      clear();
      for (const region of measured.measured) {
        const element = document.createElement("div");
        element.classList.add(REGION_CLASS);
        if (region.flagId !== null) {
          element.setAttribute(REGION_MARKER, region.flagId);
          element.setAttribute("role", REGION_ROLE);
          element.setAttribute("tabindex", REGION_TABINDEX);
          element.setAttribute(REGION_STATE, "false");
          element.addEventListener(CLICK_EVENT, function () {
            choose(region);
          });
          element.addEventListener(KEY_EVENT, function (event) {
            onKeyDown(region, event);
          });
        }
        element.style.setProperty("position", "absolute");
        element.style.setProperty("left", pixels(region.box.left));
        element.style.setProperty("top", pixels(region.box.top));
        element.style.setProperty("width", pixels(region.box.width));
        element.style.setProperty("height", pixels(region.box.height));
        if (region.clip !== null) {
          element.style.setProperty("clip-path", region.clip);
        }
        container.appendChild(element);
        region.element = element;
        drawn.push(region);
      }
      unplaced = measured.without;
      return drawn.length;
    }

    // Only what this module drew is taken away, so a page's own children in
    // the same container are none of this module's business. A selection
    // goes with the elements it was written on.
    function clear() {
      const removed = drawn.length > 0;
      for (const region of drawn) {
        container.removeChild(region.element);
      }
      drawn = [];
      selectedId = null;
      return removed;
    }

    return {
      draw,
      clear,
      select,
      selected: () => selectedId,
      regions: () => drawn.slice(),
      placed: () => drawn.length,
      unplaced: () => unplaced,
      image: () => ({ width: image.width, height: image.height }),
      display: () => ({ width: display.width, height: display.height }),
    };
  }

  window.DRISHTI_OVERLAY = {
    MIN_REGION_CORNERS,
    REGION_CLASS,
    REGION_MARKER,
    REGION_ROLE,
    REGION_TABINDEX,
    REGION_STATE,
    REGION_SELECTED_CLASS,
    REQUIRED_ELEMENTS,
    REQUIRED_CALLBACKS,
    OverlayError,
    bindOverlay,
    boundsOf,
    clipPathFor,
    normaliseRegion,
    placeRegion,
  };
})();