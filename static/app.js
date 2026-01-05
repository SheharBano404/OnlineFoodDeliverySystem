// Small helpers only

// Global submit listener for confirmation prompts
document.addEventListener("submit", (e) => {
  const btn = e.submitter; // modern browsers provide the submitter
  if (btn && btn.dataset.confirm) {
    const message = btn.dataset.confirm;
    if (!window.confirm(message)) {
      e.preventDefault();
      e.stopPropagation();
    }
  }
});

// Optional: helper for flash messages auto-dismiss
document.querySelectorAll(".flash").forEach((flash) => {
  setTimeout(() => {
    flash.classList.add("fade-out");
    setTimeout(() => flash.remove(), 500);
  }, 4000);
});
