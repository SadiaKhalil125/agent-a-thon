(function () {
  const storageKey = "agent-a-thon-theme";

  function preferredTheme() {
    return window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  }

  function getTheme() {
    const stored = localStorage.getItem(storageKey);
    if (stored === "light" || stored === "dark") return stored;
    return preferredTheme();
  }

  function updateToggleUi(theme) {
    const btn = document.getElementById("theme-toggle");
    if (!btn) return;

    const goTo = theme === "dark" ? "light" : "dark";
    btn.setAttribute(
      "aria-label",
      goTo === "dark" ? "Switch to dark theme" : "Switch to light theme"
    );
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    updateToggleUi(theme);
  }

  applyTheme(getTheme());

  document.addEventListener("DOMContentLoaded", function () {
    const btn = document.getElementById("theme-toggle");
    if (!btn) return;
    btn.addEventListener("click", function () {
      const current =
        document.documentElement.getAttribute("data-theme") || "light";
      const next = current === "dark" ? "light" : "dark";
      localStorage.setItem(storageKey, next);
      applyTheme(next);
    });
  });

  window
    .matchMedia("(prefers-color-scheme: dark)")
    .addEventListener("change", function (e) {
      if (localStorage.getItem(storageKey)) return;
      applyTheme(e.matches ? "dark" : "light");
    });
})();