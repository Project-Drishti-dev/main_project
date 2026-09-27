(() => {
  const userId = document.getElementById("user-id");
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
    formMessage.textContent = "Opening the screening workspace…";
    userId.value = "";
    password.value = "";
    window.location.href = "./home.html";
  });
})();
