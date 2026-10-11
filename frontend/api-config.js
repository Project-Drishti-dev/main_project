(() => {
  const localHosts = new Set(["localhost", "127.0.0.1"]);
  const isLocalDevelopment = localHosts.has(window.location.hostname);

  window.DRISHTI_CONFIG = {
    apiBaseUrl: isLocalDevelopment ? "http://localhost:8080" : "",
    // The station this build stands at, or the placeholder when nobody
    // configured one.  The build rewrites this file from the environment;
    // this copy is what a served-from-source checkout reads.
    stationLabel: "station-unset",
  };
})();
