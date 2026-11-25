(function () {
  const form = document.getElementById("chat-form");
  const input = document.getElementById("q");
  const reply = document.getElementById("reply");
  const btn = document.getElementById("ask");

  if (!form || !input || !reply || !btn) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const message = input.value.trim();
    if (!message) {
      input.focus();
      return;
    }

    btn.disabled = true;
    btn.textContent = "Thinking…";
    form.setAttribute("aria-busy", "true");
    reply.classList.remove("is-error", "is-empty");
    reply.textContent = "";

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });
      const data = await res.json();
      const text = data.reply ?? data.error ?? "Something went wrong.";
      reply.textContent = text;
      if (!data.reply) {
        reply.classList.add("is-error");
      }
    } catch {
      reply.textContent = "Could not reach the server. Try again in a moment.";
      reply.classList.add("is-error");
    } finally {
      btn.disabled = false;
      btn.textContent = "Send message";
      form.removeAttribute("aria-busy");
    }
  });
})();