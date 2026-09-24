(() => {
  const form = document.getElementById("register-form");
  const password = document.getElementById("register-password");
  const confirmPassword = document.getElementById("confirm-password");
  const status = document.getElementById("register-status");
  const accountDetails = [
    document.getElementById("full-name"),
    document.getElementById("personnel-id"),
    document.getElementById("email"),
    password,
    confirmPassword,
  ];

  for (const [inputId, buttonId] of [
    ["register-password", "register-password-toggle"],
    ["confirm-password", "confirm-password-toggle"],
  ]) {
    const input = document.getElementById(inputId);
    const toggle = document.getElementById(buttonId);

    toggle.addEventListener("click", () => {
      const isVisible = input.type === "text";
      input.type = isVisible ? "password" : "text";
      toggle.textContent = isVisible ? "Show" : "Hide";
      toggle.setAttribute("aria-pressed", String(!isVisible));
    });
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();

    if (password.value !== confirmPassword.value) {
      confirmPassword.setAttribute("aria-invalid", "true");
      status.textContent = "The passwords do not match.";
      confirmPassword.focus();
      return;
    }

    confirmPassword.removeAttribute("aria-invalid");
    for (const field of accountDetails) field.value = "";
    status.textContent =
      "Registration is not connected. No details were sent or saved.";
  });
})();
