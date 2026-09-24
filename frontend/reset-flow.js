(() => {
  const trigger = document.getElementById("forgot-password");
  const modal = document.getElementById("password-reset-modal");
  const requestStep = document.getElementById("reset-request-step");
  const account = document.getElementById("reset-account");
  const continueButton = document.getElementById("reset-continue");
  const passwordStep = document.getElementById("reset-password-step");
  const resetForm = document.getElementById("reset-form");
  const code = document.getElementById("reset-code");
  const newPassword = document.getElementById("reset-new-password");
  const confirmPassword = document.getElementById("reset-confirm-password");
  const backButton = document.getElementById("reset-back");
  const closeButton = document.getElementById("reset-close");
  const stepCounter = document.getElementById("reset-step-counter");
  const status = document.getElementById("reset-status");

  function clearResetFlow() {
    account.value = "";
    code.value = "";
    newPassword.value = "";
    confirmPassword.value = "";
    confirmPassword.removeAttribute("aria-invalid");
    requestStep.hidden = false;
    passwordStep.hidden = true;
    stepCounter.textContent = "Step 1 of 2";
    status.textContent = "";
  }

  trigger.addEventListener("click", clearResetFlow);

  continueButton.addEventListener("click", () => {
    if (!account.reportValidity()) return;

    requestStep.hidden = true;
    passwordStep.hidden = false;
    stepCounter.textContent = "Step 2 of 2";
    code.focus();
  });

  backButton.addEventListener("click", () => {
    code.value = "";
    newPassword.value = "";
    confirmPassword.value = "";
    confirmPassword.removeAttribute("aria-invalid");
    passwordStep.hidden = true;
    requestStep.hidden = false;
    stepCounter.textContent = "Step 1 of 2";
    account.focus();
  });

  resetForm.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!resetForm.reportValidity()) return;

    if (newPassword.value !== confirmPassword.value) {
      confirmPassword.setAttribute("aria-invalid", "true");
      status.textContent = "The new passwords do not match.";
      confirmPassword.focus();
      return;
    }

    confirmPassword.removeAttribute("aria-invalid");
    code.value = "";
    newPassword.value = "";
    confirmPassword.value = "";
    status.textContent =
      "Demo complete. No verification was performed and no password was changed.";
  });

  closeButton.addEventListener("click", clearResetFlow);
  modal.addEventListener("click", (event) => {
    if (event.target === modal) clearResetFlow();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") clearResetFlow();
  });
})();
