(() => {
  "use strict";

  // The probe names a path and never an address: the base URL is read from
  // window.DRISHTI_CONFIG by the API module, so no URL is baked into a build.
  const HEALTH_PATH = "/health";

  const CHECKING = "checking";
  const ONLINE = "online";
  const UNREACHABLE = "unreachable";
  const UNCONFIGURED = "unconfigured";

  const STATE_LABELS = {
    checking: "Checking the connection...",
    online: "Connected to the quality service",
    unreachable: "The quality service cannot be reached",
    unconfigured: "This site has no quality service configured",
  };

  const STATES = Object.freeze({
    CHECKING,
    ONLINE,
    UNREACHABLE,
    UNCONFIGURED,
  });

  class StatusError extends Error {
    constructor(message) {
      super(message);
      this.name = "StatusError";
    }
  }

  let currentState = CHECKING;
  let currentError = null;
  const listeners = new Set();

  function current() {
    return currentState;
  }

  function lastError() {
    return currentError;
  }

  function label(state) {
    const wanted = state === undefined ? currentState : state;
    if (!Object.prototype.hasOwnProperty.call(STATE_LABELS, wanted)) {
      throw new StatusError("Not a connection state: " + String(state) + ".");
    }
    return STATE_LABELS[wanted];
  }

  function subscribe(listener) {
    listeners.add(listener);
    return function unsubscribe() {
      listeners.delete(listener);
    };
  }

  function publish(state, error) {
    currentState = state;
    currentError = error;
    for (const listener of [...listeners]) {
      listener(state, error);
    }
  }

  // Never rejects: a probe that cannot run settles into a state, so a page
  // reads one name rather than handling a rejection per probe.
  async function refresh() {
    const api = window.DRISHTI_API;
    const baseUrl = api?.request ? api.readApiBaseUrl() : "";
    publish(CHECKING, null);
    if (baseUrl === "") {
      publish(UNCONFIGURED, null);
      return currentState;
    }
    try {
      await api.request(HEALTH_PATH);
      publish(ONLINE, null);
    } catch (error) {
      publish(UNREACHABLE, error);
    }
    return currentState;
  }

  window.DRISHTI_STATUS = {
    current,
    lastError,
    label,
    refresh,
    subscribe,
    HEALTH_PATH,
    STATE_LABELS,
    STATES,
    StatusError,
  };

  // The probe starts with the page: a status nobody asked for is the status an
  // officer reads before touching anything.
  refresh();
})();
