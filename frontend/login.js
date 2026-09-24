(() => {
  const password = document.getElementById("password");
  const passwordToggle = document.getElementById("password-toggle");
  const loginForm = document.getElementById("login-form");
  const formMessage = document.getElementById("form-message");

  passwordToggle.addEventListener("click", () => {
    const isVisible = password.type === "text";
    password.type = isVisible ? "password" : "text";
    passwordToggle.textContent = isVisible ? "Show" : "Hide";
    passwordToggle.setAttribute("aria-pressed", String(!isVisible));
  });

  loginForm.addEventListener("submit", (event) => {
    event.preventDefault();
    formMessage.textContent =
      "Sign-in is not connected yet. No credentials were sent.";
  });
})();
