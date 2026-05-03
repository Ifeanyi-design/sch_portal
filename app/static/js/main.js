document.addEventListener("DOMContentLoaded", () => {
  const sidebar = document.querySelector("[data-sidebar]");
  const overlay = document.querySelector("[data-sidebar-overlay]");
  const openButtons = document.querySelectorAll("[data-sidebar-open]");
  const closeButtons = document.querySelectorAll("[data-sidebar-close]");
  const dismissButtons = document.querySelectorAll("[data-dismiss-alert]");
  const passwordToggles = document.querySelectorAll("[data-password-toggle]");

  const closeSidebar = () => {
    if (!sidebar || !overlay) return;
    sidebar.classList.add("-translate-x-full");
    overlay.classList.add("hidden");
  };

  const openSidebar = () => {
    if (!sidebar || !overlay) return;
    sidebar.classList.remove("-translate-x-full");
    overlay.classList.remove("hidden");
  };

  openButtons.forEach((button) => {
    button.addEventListener("click", openSidebar);
  });

  closeButtons.forEach((button) => {
    button.addEventListener("click", closeSidebar);
  });

  if (overlay) {
    overlay.addEventListener("click", closeSidebar);
  }

  dismissButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const alert = button.closest(".rounded-2xl");
      if (alert) {
        alert.remove();
      }
    });
  });

  passwordToggles.forEach((button) => {
    button.addEventListener("click", () => {
      const target = document.getElementById(button.dataset.passwordToggle || "");
      if (!target) return;
      const showing = target.type === "text";
      target.type = showing ? "password" : "text";
      button.textContent = showing ? "Show" : "Hide";
    });
  });
});
