document.addEventListener("DOMContentLoaded", () => {
  const sidebar = document.querySelector("[data-sidebar]");
  const overlay = document.querySelector("[data-sidebar-overlay]");
  const openButtons = document.querySelectorAll("[data-sidebar-open]");
  const closeButtons = document.querySelectorAll("[data-sidebar-close]");
  const dismissButtons = document.querySelectorAll("[data-dismiss-alert]");
  const passwordToggles = document.querySelectorAll("[data-password-toggle]");
  const portalRoot = document.querySelector("[data-login-portal]");

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

  if (portalRoot) {
    const hiddenInput = portalRoot.querySelector("[data-portal-input]");
    const usernameInput = document.getElementById("username");
    const helpText = portalRoot.querySelector("[data-login-help]");
    const loginIdLabel = portalRoot.querySelector("[data-login-id-label]");
    const submitButton = portalRoot.querySelector("button[type='submit']");
    const tabs = portalRoot.querySelectorAll("[data-portal-tab]");

    const applyPortalState = (portal) => {
      if (!hiddenInput) return;

      hiddenInput.value = portal;

      if (usernameInput) {
        usernameInput.placeholder =
          portal === "student"
            ? "Enter your student ID or username"
            : "Enter your username or email";
      }

      if (helpText) {
        helpText.textContent =
          portal === "student"
            ? "Students should sign in with their student ID or assigned username."
            : "Staff should sign in with their username or email address.";
      }

      if (loginIdLabel) {
        loginIdLabel.textContent =
          portal === "student" ? "Student ID or Username" : "Staff Username or Email";
      }

      if (submitButton) {
        submitButton.textContent =
          portal === "student" ? "Student Sign In" : "Staff Sign In";
      }

      tabs.forEach((tab) => {
        const active = tab.dataset.portalTab === portal;
        tab.classList.toggle("bg-white", active);
        tab.classList.toggle("text-brand-700", active);
        tab.classList.toggle("shadow-sm", active);
        tab.classList.toggle("ring-1", active);
        tab.classList.toggle("ring-brand-100", active);
        tab.classList.toggle("text-slate-500", !active);
      });
    };

    tabs.forEach((tab) => {
      tab.addEventListener("click", () => {
        applyPortalState(tab.dataset.portalTab || "student");
      });
    });

    applyPortalState(hiddenInput?.value || "student");
  }
});
