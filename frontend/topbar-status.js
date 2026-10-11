(() => {
  "use strict";

  // Renders D165's connection state into the topbar element every page
  // carries. The words come from the module; this owns the element only.
  function renderConnectionStatus() {
    const element = document.getElementById("connection-status");
    const status = window.DRISHTI_STATUS;
    if (!element || !status) return;

    function render(state) {
      element.textContent = status.label(state);
      element.dataset.state = state;
    }

    // The probe settled before this script loaded, so read the state it holds
    // before subscribing to the ones it publishes from here on.
    render(status.current());
    status.subscribe(render);
  }

  renderConnectionStatus();
})();
