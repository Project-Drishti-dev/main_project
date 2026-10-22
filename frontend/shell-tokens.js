(() => {
  "use strict";

  // The shell template's placeholders, named once.  No page loads this file:
  // the build reads the table and fails on a name the template cannot fill.
  const TOKEN_NAMES = Object.freeze([
    "pageTitle",
    "pageDescription",
    "pageHeading",
    "activeNavKey",
    "content",
    "overlays",
    "pageScripts",
  ]);

  const NAV_KEYS = Object.freeze([
    "home",
    "screenings",
    "profile",
    "settings",
    "guide",
    "about",
    "results",
  ]);

  const NAV_PREFIX = "nav.";

  class ShellTokenError extends Error {
    constructor(message) {
      super(message);
      this.name = "ShellTokenError";
    }
  }

  function tokenNames() {
    return TOKEN_NAMES.slice();
  }

  function navKeys() {
    return NAV_KEYS.slice();
  }

  function isToken(name) {
    return TOKEN_NAMES.indexOf(name) !== -1;
  }

  function conditionalName(navKey) {
    if (NAV_KEYS.indexOf(navKey) === -1) {
      throw new ShellTokenError(
        "Not a navigation key: " + String(navKey) + ".",
      );
    }
    return NAV_PREFIX + navKey;
  }

  window.DRISHTI_SHELL_TOKENS = Object.freeze({
    ShellTokenError,
    tokenNames,
    navKeys,
    isToken,
    conditionalName,
  });
})();
