(() => {
  "use strict";

  // The loading state of a result page. While a screening is still running the
  // page draws its own skeleton shapes; when the answer arrives they are
  // removed and the result takes their place. One switch, applied to the
  // container and to every shape below it, so half a skeleton is not a state
  // the page can be left in.

  // UX4G ships these seven shapes and no size modifier (G3). The list is read
  // out of the installed stylesheet by a case, so it cannot fall behind.
  const SHAPE_CLASSES = [
    "ux4g-skeleton-block",
    "ux4g-skeleton-btn",
    "ux4g-skeleton-circle",
    "ux4g-skeleton-main",
    "ux4g-skeleton-sidebar-card",
    "ux4g-skeleton-subtitle",
    "ux4g-skeleton-title",
  ];
  const SHAPE_PREFIX = "ux4g-skeleton-";
  const SHAPE_SELECTOR = '[class*="' + SHAPE_PREFIX + '"]';

  const REQUIRED_ELEMENTS = ["loading", "surface"];

  // G2: the skeleton ships no ARIA at all, so the two facts a shape cannot
  // carry on its own are written by hand. The container says the page is
  // busy while it waits, and every shape is hidden from assistive technology
  // because a grey block standing in for content that has not arrived is not
  // content -- reading "loading" seven times would be noise, not news.
  const BUSY_ATTRIBUTE = "aria-busy";
  const BUSY_VALUE = "true";
  const IDLE_VALUE = "false";
  const DECORATIVE_ATTRIBUTE = "aria-hidden";
  const DECORATIVE_VALUE = "true";

  const NO_SHAPES_MESSAGE =
    "This loading state holds no skeleton shape, so it would show nothing.";
  const NOT_SHIPPED_MESSAGE =
    "The loading state carries a skeleton class the design system does not " +
    "ship: ";
  const BOTH_VISIBLE_MESSAGE =
    "The loading state and the result are both on the page, so there is no " +
    "loading state to switch between them.";

  class ResultSkeletonError extends Error {
    constructor(code, message) {
      super(message);
      this.name = "ResultSkeletonError";
      this.code = code;
    }
  }

  function readElement(settings, name) {
    const element = settings ? settings[name] : null;
    if (!element) {
      throw new ResultSkeletonError(
        "missing_element",
        "The result loading state needs an element named " + name + ".",
      );
    }
    return element;
  }

  // The shapes are the page's own markup, found by the one class prefix, so a
  // shape added to the page is switched with the rest of them.
  function readShapes(loading) {
    const shapes = Array.from(loading.querySelectorAll(SHAPE_SELECTOR));
    if (shapes.length === 0) {
      throw new ResultSkeletonError("no_shapes", NO_SHAPES_MESSAGE);
    }
    for (const shape of shapes) {
      for (const name of Array.from(shape.classList)) {
        if (
          name.startsWith(SHAPE_PREFIX) &&
          !SHAPE_CLASSES.includes(name)
        ) {
          throw new ResultSkeletonError(
            "unknown_shape",
            NOT_SHIPPED_MESSAGE + name,
          );
        }
      }
    }
    return shapes;
  }

  function classesOf(shapes) {
    const found = new Set();
    for (const shape of shapes) {
      for (const name of Array.from(shape.classList)) {
        if (name.startsWith(SHAPE_PREFIX)) {
          found.add(name);
        }
      }
    }
    return Array.from(found).sort();
  }

  // bindResultSkeleton wires one page's skeleton to the result it stands in
  // front of, and starts nothing: the page calls show() when it begins waiting
  // and hide() when the answer lands, because a page opened on a screening
  // that has already finished must not claim work is happening.
  function bindResultSkeleton(options) {
    const settings = options || {};
    const loading = readElement(settings, "loading");
    const surface = readElement(settings, "surface");
    const shapes = readShapes(loading);

    // The page's own markup decides the starting state, so a skeleton written
    // visible into the fragment needs no first paint to fight with.
    let drawing = !loading.hidden;
    if (drawing && !surface.hidden) {
      throw new ResultSkeletonError("both_visible", BOTH_VISIBLE_MESSAGE);
    }

    // The container and every shape carry the switch together, so a shape can
    // never be left drawn behind a container that is not there.
    function setSkeleton(drawing_) {
      loading.hidden = !drawing_;
      for (const shape of shapes) {
        shape.hidden = !drawing_;
      }
      surface.hidden = drawing_;
      drawing = drawing_;
      // aria-busy travels with hidden, so the flag a screen reader is given
      // and the thing an officer can see are switched by the same write.
      loading.setAttribute(
        BUSY_ATTRIBUTE,
        drawing_ ? BUSY_VALUE : IDLE_VALUE,
      );
    }

    // Set once, at binding: a shape is decorative whether it is drawn now or
    // not, so this is a property of the markup rather than of the state.
    for (const shape of shapes) {
      shape.setAttribute(DECORATIVE_ATTRIBUTE, DECORATIVE_VALUE);
    }
    setSkeleton(drawing);

    // Both switches report whether they changed anything, so a second show()
    // reading false and a hide() reading false cannot be told apart by the
    // return value alone.
    function show() {
      if (drawing) {
        return false;
      }
      setSkeleton(true);
      return true;
    }

    function hide() {
      if (!drawing) {
        return false;
      }
      setSkeleton(false);
      return true;
    }

    return {
      show,
      hide,
      pending: () => drawing,
      shapes: () => shapes.length,
      classes: () => classesOf(shapes),
    };
  }

  window.DRISHTI_RESULT_SKELETON = {
    BUSY_ATTRIBUTE,
    BUSY_VALUE,
    DECORATIVE_ATTRIBUTE,
    DECORATIVE_VALUE,
    IDLE_VALUE,
    REQUIRED_ELEMENTS,
    SHAPE_CLASSES,
    SHAPE_PREFIX,
    SHAPE_SELECTOR,
    ResultSkeletonError,
    bindResultSkeleton,
  };
})();