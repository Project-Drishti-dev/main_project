(() => {
  const STORAGE_KEY = "drishti.preferences.v1";
  const THEMES = ["light", "dark", "system"];
  const TEXT_SIZES = ["default", "large", "x-large"];
  const DEFAULTS = { theme: "light", textSize: "default" };
  const DARK_MEDIA_QUERY = "(prefers-color-scheme: dark)";

  const root = document.documentElement;
  const listeners = new Set();
  let preferences = { ...DEFAULTS };

  function getStorage() {
    try {
      const storage = window.localStorage;
      if (!storage) return null;
      const probe = `${STORAGE_KEY}.probe`;
      storage.setItem(probe, "1");
      storage.removeItem(probe);
      return storage;
    } catch {
      return null;
    }
  }

  const storage = getStorage();

  function sanitize(value) {
    const next = { ...DEFAULTS };
    if (value && typeof value === "object") {
      if (THEMES.includes(value.theme)) next.theme = value.theme;
      if (TEXT_SIZES.includes(value.textSize)) next.textSize = value.textSize;
    }
    return next;
  }

  function load() {
    if (!storage) return { ...DEFAULTS };
    try {
      return sanitize(JSON.parse(storage.getItem(STORAGE_KEY) || "null"));
    } catch {
      return { ...DEFAULTS };
    }
  }

  function persist() {
    if (!storage) return;
    try {
      storage.setItem(STORAGE_KEY, JSON.stringify(preferences));
    } catch {
      /* Preferences stay in memory for this page view only. */
    }
  }

  function prefersDark() {
    return (
      typeof window.matchMedia === "function" &&
      window.matchMedia(DARK_MEDIA_QUERY).matches === true
    );
  }

  function resolvedTheme() {
    if (preferences.theme !== "system") return preferences.theme;
    return prefersDark() ? "dark" : "light";
  }

  function apply() {
    root.setAttribute("data-theme", resolvedTheme());
    root.setAttribute("data-text-size", preferences.textSize);
    root.setAttribute("data-theme-preference", preferences.theme);
    for (const listener of listeners) listener(preferences);
  }

  function set(patch) {
    preferences = sanitize({ ...preferences, ...patch });
    persist();
    apply();
    return preferences;
  }

  function reset() {
    preferences = { ...DEFAULTS };
    persist();
    apply();
    return preferences;
  }

  if (typeof window.matchMedia === "function") {
    const query = window.matchMedia(DARK_MEDIA_QUERY);
    if (typeof query.addEventListener === "function") {
      query.addEventListener("change", () => {
        if (preferences.theme === "system") apply();
      });
    }
  }

  preferences = load();
  apply();

  window.DRISHTI_PREFERENCES = {
    read: () => ({ ...preferences }),
    set,
    reset,
    onChange(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
})();
