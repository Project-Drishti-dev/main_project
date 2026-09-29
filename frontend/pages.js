(() => {
  const MAX_AVATAR_BYTES = 5 * 1024 * 1024;
  const SUPPORTED_AVATAR_TYPES = new Set([
    "image/jpeg",
    "image/png",
    "image/webp",
  ]);
  const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  const TEXT_SIZE_LABELS = {
    default: "Default text size.",
    large: "Large text size.",
    "x-large": "Extra large text size.",
  };
  const SAMPLE_NAME = "Demo Sample";
  const SAMPLE_EMAIL = "demo.sample@example.com";

  const preferences = window.DRISHTI_PREFERENCES ?? null;
  const workspaceShell = document.getElementById("workspace-shell");
  const sidebar = document.getElementById("app-sidebar");
  const sidebarToggle = document.getElementById("sidebar-toggle");

  if (sidebar && sidebarToggle && workspaceShell) {
    sidebarToggle.addEventListener("click", () => {
      const expanded = sidebar.classList.toggle("is-expanded");
      workspaceShell.classList.toggle("is-sidebar-expanded", expanded);
      sidebarToggle.setAttribute("aria-expanded", String(expanded));
      sidebarToggle.setAttribute(
        "aria-label",
        expanded ? "Collapse sidebar" : "Expand sidebar",
      );
      sidebarToggle.setAttribute(
        "title",
        expanded ? "Collapse sidebar" : "Expand sidebar",
      );
    });
  }

  function initSettings() {
    const themeOptions = document.getElementById("theme-options");
    const textSizeOptions = document.getElementById("text-size-options");
    const summary = document.getElementById("text-size-summary");
    const resetButton = document.getElementById("reset-preferences");
    if (!themeOptions || !textSizeOptions || !preferences) return;

    function syncControls() {
      const current = preferences.read();
      for (const input of themeOptions.querySelectorAll('input[name="theme"]')) {
        input.checked = input.value === current.theme;
      }
      for (const input of textSizeOptions.querySelectorAll(
        'input[name="text-size"]',
      )) {
        input.checked = input.value === current.textSize;
      }
      if (summary) {
        summary.textContent =
          `${TEXT_SIZE_LABELS[current.textSize] ?? ""} Sample: sharpness, glare, and framing.`;
      }
    }

    themeOptions.addEventListener("change", (event) => {
      const input = event.target;
      if (!input || input.name !== "theme") return;
      preferences.set({ theme: input.value });
      syncControls();
    });

    textSizeOptions.addEventListener("change", (event) => {
      const input = event.target;
      if (!input || input.name !== "text-size") return;
      preferences.set({ textSize: input.value });
      syncControls();
    });

    if (resetButton) {
      resetButton.addEventListener("click", () => {
        preferences.reset();
        syncControls();
      });
    }

    syncControls();
  }

  function initAccordions() {
    const toggles = document.querySelectorAll("[data-ux4g-accordion-toggle]");

    for (const toggle of toggles) {
      const collapseId = toggle.getAttribute("aria-controls");
      const collapse = collapseId ? document.getElementById(collapseId) : null;
      if (!collapse) continue;

      // A collapsed panel must be hidden from assistive tech too, not just
      // visually collapsed, so toggle the hidden attribute alongside the class.
      collapse.hidden = !collapse.classList.contains("show");

      toggle.addEventListener("click", () => {
        const expanded = toggle.getAttribute("aria-expanded") === "true";
        toggle.setAttribute("aria-expanded", String(!expanded));
        collapse.classList.toggle("show", !expanded);
        collapse.hidden = expanded;
      });
    }
  }

  function initScreenings() {
    const body = document.getElementById("screenings-body");
    const search = document.getElementById("screening-search");
    const filters = document.getElementById("result-filters");
    const count = document.getElementById("result-count");
    const emptyState = document.getElementById("screenings-empty");
    const clearButton = document.getElementById("clear-filters");
    const exportButton = document.getElementById("export-screenings");
    const notice = document.getElementById("screenings-notice");
    const sortButton = document.getElementById("sort-checked");
    if (!body) return;

    const scroll = body.closest(".table-scroll") ?? body.parentElement;
    let activeFilter = "all";
    let sortAscending = false;

    function rows() {
      return Array.from(body.querySelectorAll("tr"));
    }

    function visibleRows() {
      const term = (search?.value ?? "").trim().toLowerCase();
      return rows().filter((row) => {
        const matchesFilter =
          activeFilter === "all" || row.dataset.result === activeFilter;
        const haystack = (row.dataset.search ?? row.textContent ?? "")
          .toLowerCase();
        return matchesFilter && (!term || haystack.includes(term));
      });
    }

    function render() {
      const term = (search?.value ?? "").trim().toLowerCase();
      const matching = visibleRows();

      for (const row of rows()) {
        row.hidden = !matching.includes(row);
      }

      if (scroll) scroll.hidden = matching.length === 0;
      if (emptyState) emptyState.hidden = matching.length !== 0;
      if (count) {
        count.textContent = term || activeFilter !== "all"
          ? `Showing ${matching.length} of ${rows().length} screenings`
          : `Showing ${rows().length} of ${rows().length} screenings`;
      }
    }

    function setFilter(next) {
      activeFilter = next;
      if (!filters) return;
      for (const chip of filters.querySelectorAll("[data-filter]")) {
        const selected = chip.dataset.filter === next;
        chip.classList.toggle("active", selected);
        chip.setAttribute("aria-pressed", String(selected));
      }
      render();
    }

    if (filters) {
      filters.addEventListener("click", (event) => {
        const chip = event.target?.closest?.("[data-filter]");
        if (chip) setFilter(chip.dataset.filter);
      });
    }

    if (search) search.addEventListener("input", render);

    if (clearButton) {
      clearButton.addEventListener("click", () => {
        if (search) search.value = "";
        setFilter("all");
        search?.focus();
      });
    }

    if (sortButton) {
      sortButton.addEventListener("click", () => {
        sortAscending = !sortAscending;
        const header = sortButton.closest("th");
        if (header) {
          header.setAttribute(
            "aria-sort",
            sortAscending ? "ascending" : "descending",
          );
        }
        const sorted = rows().sort((a, b) => {
          const left = a.querySelector("time")?.getAttribute("datetime") ?? "";
          const right = b.querySelector("time")?.getAttribute("datetime") ?? "";
          return sortAscending
            ? left.localeCompare(right)
            : right.localeCompare(left);
        });
        for (const row of sorted) body.appendChild(row);
        render();
      });
    }

    body.addEventListener("click", (event) => {
      const button = event.target?.closest?.("[data-row-action]");
      if (!button) return;
      const row = button.closest("tr");
      const id = row?.querySelector(".cell-primary strong")?.textContent ?? "record";

      if (button.dataset.rowAction === "delete") {
        row?.remove();
        render();
        if (notice) {
          notice.textContent = `${id} removed from this view. Nothing was deleted on a server.`;
        }
        return;
      }

      if (notice) {
        notice.textContent =
          `Opening ${id} is not available yet. Screening history needs a backend record store.`;
      }
    });

    if (exportButton) {
      exportButton.addEventListener("click", () => {
        const header = ["Screening", "Checked", "Mode", "Score", "Result"];
        const data = visibleRows().map((row) =>
          Array.from(row.querySelectorAll("td"))
            .slice(0, 5)
            .map((cell) => cell.textContent.trim()),
        );
        const csv = [header, ...data]
          .map((line) =>
            line
              .map((cell) => `"${String(cell).replace(/"/g, '""')}"`)
              .join(","),
          )
          .join("\r\n");
        downloadFile(
          "drishti-screenings.csv",
          `${csv}\r\n`,
          "text/csv;charset=utf-8",
        );
      });
    }

    render();
  }

  function initProfile() {
    const form = document.getElementById("profile-form");
    if (!form) return;

    const nameInput = document.getElementById("profile-name");
    const emailInput = document.getElementById("profile-email");
    const emailField = document.getElementById("email-field");
    const error = document.getElementById("profile-error");
    const status = document.getElementById("avatar-status");
    const resetButton = document.getElementById("reset-profile");
    const fileInput = document.getElementById("avatar-file");
    const avatarImage = document.getElementById("avatar-image");
    const avatarInitials = document.getElementById("avatar-initials");
    const removeButton = document.getElementById("remove-photo");
    const changePassword = document.getElementById("change-password");
    const downloadData = document.getElementById("download-data");

    let photoUrl = null;

    function showPhoto(url, fileName) {
      if (photoUrl) URL.revokeObjectURL(photoUrl);
      photoUrl = url;
      avatarImage.src = url;
      avatarImage.alt = `Selected profile photo: ${fileName}`;
      avatarImage.hidden = false;
      if (avatarInitials) avatarInitials.hidden = true;
      if (removeButton) removeButton.disabled = false;
    }

    function clearPhoto() {
      if (photoUrl) {
        URL.revokeObjectURL(photoUrl);
        photoUrl = null;
      }
      avatarImage.removeAttribute("src");
      avatarImage.alt = "";
      avatarImage.hidden = true;
      if (avatarInitials) avatarInitials.hidden = false;
      if (fileInput) fileInput.value = "";
      if (removeButton) removeButton.disabled = true;
      if (status) status.textContent = "Profile photo removed.";
    }

    if (fileInput) {
      fileInput.addEventListener("change", () => {
        const file = fileInput.files && fileInput.files[0];
        if (!file) return;

        if (!SUPPORTED_AVATAR_TYPES.has(file.type)) {
          if (status) status.textContent = "Choose a JPEG, PNG, or WebP image.";
          fileInput.value = "";
          return;
        }
        if (file.size > MAX_AVATAR_BYTES) {
          if (status) status.textContent = "Choose an image that is 5 MB or smaller.";
          fileInput.value = "";
          return;
        }

        showPhoto(URL.createObjectURL(file), file.name);
        if (status) {
          status.textContent = `${file.name} previewed in this tab only. It is not uploaded.`;
        }
        fileInput.value = "";
      });
    }

    if (removeButton) {
      removeButton.disabled = true;
      removeButton.addEventListener("click", clearPhoto);
    }

    function setError(message) {
      if (error) error.textContent = message;
      if (emailField) {
        emailField.classList.toggle("ux4g-input-error", Boolean(message));
        emailField.classList.toggle("ux4g-input-default", !message);
      }
    }

    function applyToDisplay(name, email) {
      for (const node of document.querySelectorAll('[data-display="name"]')) {
        node.textContent = name;
      }
      for (const node of document.querySelectorAll('[data-display="email"]')) {
        node.textContent = email;
      }
      for (const node of document.querySelectorAll(".profile-name")) {
        node.textContent = name.split(/\s+/)[0] || name;
      }
    }

    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const name = nameInput.value.trim();
      const email = emailInput.value.trim();

      if (!name) {
        setError("Enter a name to save your profile.");
        nameInput.focus();
        return;
      }
      if (!EMAIL_PATTERN.test(email)) {
        setError("Enter a valid email address, for example name@example.com.");
        emailInput.focus();
        return;
      }

      setError("");
      applyToDisplay(name, email);
      if (status) {
        status.textContent =
          "Profile updated for this tab. Reloading the page restores the sample details.";
      }
    });

    if (resetButton) {
      resetButton.addEventListener("click", () => {
        nameInput.value = SAMPLE_NAME;
        emailInput.value = SAMPLE_EMAIL;
        setError("");
        applyToDisplay(SAMPLE_NAME, SAMPLE_EMAIL);
        if (status) status.textContent = "Sample details restored.";
      });
    }

    for (const button of [changePassword, downloadData]) {
      button?.addEventListener("click", () => {
        const target = status;
        if (!target) return;
        target.textContent =
          button === changePassword
            ? "Changing a password needs a real account. This build has no sign-in."
            : "There is no personal data stored, so there is nothing to download.";
      });
    }
  }

  function downloadFile(fileName, contents, type) {
    const blob = new Blob([contents], { type });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  initSettings();
  initAccordions();
  initScreenings();
  initProfile();
})();
