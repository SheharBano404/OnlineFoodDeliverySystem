// small helpers only
document.addEventListener("submit", (e) => {
  const btn = e.submitter;
  if (btn && btn.dataset.confirm) {
    if (!confirm(btn.dataset.confirm)) e.preventDefault();
  }
});