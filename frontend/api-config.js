(() => {
  const localHosts = new Set(["localhost", "127.0.0.1"]);
  const isLocalDevelopment = localHosts.has(window.location.hostname);

  window.DRISHTI_CONFIG = {
    apiBaseUrl: isLocalDevelopment ? "http://localhost:8080" : "",
  };
})();
