const thread = document.getElementById("thread");
const composer = document.getElementById("composer");
const promptEl = document.getElementById("prompt");
const sendBtn = document.getElementById("sendBtn");
const safetyMode = document.getElementById("safetyMode");
const sessionId = document.getElementById("sessionId");
const clearSession = document.getElementById("clearSession");
const statusDot = document.getElementById("statusDot");
const statusLabel = document.getElementById("statusLabel");
const modelLabel = document.getElementById("modelLabel");
const metaLine = document.getElementById("metaLine");
const modeHint = document.getElementById("modeHint");

let mode = "chat";
let busy = false;

const hints = {
  chat: "Streaming chat ke Ollama lokal. Konteks tersimpan per session.",
  ask: "Jawaban berbasis dokumen di folder docs/, lengkap dengan sources.",
};

function setMode(next) {
  mode = next;
  document.querySelectorAll(".seg").forEach((btn) => {
    const active = btn.dataset.mode === mode;
    btn.classList.toggle("active", active);
    btn.setAttribute("aria-selected", active ? "true" : "false");
  });
  modeHint.textContent = hints[mode];
  promptEl.placeholder =
    mode === "ask"
      ? "Contoh: Apa prinsip privacy di sistem ini?"
      : "Tanya sesuatu… coba prinsip privacy, atau uji prompt injection di mode strict";
}

document.querySelectorAll(".seg").forEach((btn) => {
  btn.addEventListener("click", () => setMode(btn.dataset.mode));
});

function showEmpty() {
  thread.innerHTML = `<p class="empty">Mulai percakapan. Ganti ke <strong>Ask (RAG)</strong> untuk jawaban bersumber dokumen lokal.</p>`;
}

function clearEmpty() {
  const empty = thread.querySelector(".empty");
  if (empty) empty.remove();
}

function appendMessage({ role, content, foot = "", sources = [] }) {
  clearEmpty();
  const wrap = document.createElement("article");
  wrap.className = `msg ${role}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = content;
  wrap.appendChild(bubble);

  if (sources.length) {
    const box = document.createElement("div");
    box.className = "sources";
    for (const src of sources) {
      const item = document.createElement("div");
      item.className = "source";
      item.innerHTML = `<strong>${escapeHtml(src.file)}</strong> · score ${src.score}<br>${escapeHtml(src.excerpt)}`;
      box.appendChild(item);
    }
    wrap.appendChild(box);
  }

  if (foot) {
    const f = document.createElement("div");
    f.className = "foot";
    f.innerHTML = foot;
    wrap.appendChild(f);
  }

  thread.appendChild(wrap);
  thread.scrollTop = thread.scrollHeight;
  return { wrap, bubble };
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function safetyFoot(safety, requestId) {
  const parts = [];
  if (requestId) parts.push(`<span class="badge">id ${escapeHtml(requestId.slice(0, 8))}</span>`);
  if (safety?.input_flagged) parts.push(`<span class="badge warn">input flagged</span>`);
  if (safety?.output_redacted) parts.push(`<span class="badge warn">output redacted</span>`);
  if (!safety?.input_flagged && !safety?.output_redacted) {
    parts.push(`<span class="badge ok">clean</span>`);
  }
  return parts.join("");
}

function setBusy(state) {
  busy = state;
  sendBtn.disabled = state;
  promptEl.disabled = state;
  metaLine.textContent = state ? "thinking…" : "ready";
}

async function refreshHealth() {
  try {
    const res = await fetch("/health");
    const data = await res.json();
    const ok = data.status === "ok" && data.ollama === "up";
    statusDot.dataset.state = ok ? "ok" : "degraded";
    statusLabel.textContent = ok ? "Stack online" : `Stack ${data.status}`;
    modelLabel.textContent = data.model || "—";
  } catch {
    statusDot.dataset.state = "down";
    statusLabel.textContent = "API unreachable";
    modelLabel.textContent = "start uvicorn";
  }
}

async function sendChat(message) {
  appendMessage({ role: "user", content: message });
  const { bubble, wrap } = appendMessage({ role: "assistant", content: "" });

  const res = await fetch("/v1/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      session_id: sessionId.value.trim() || "session-1",
      safety_mode: safetyMode.value,
    }),
  });

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const err = await res.json();
      detail = err.detail?.reason || err.detail?.error || err.reason || detail;
      wrap.className = "msg system";
      bubble.textContent = String(detail);
      wrap.querySelector(".bubble").insertAdjacentHTML(
        "afterend",
        `<div class="foot">${safetyFoot({ input_flagged: true }, err.detail?.request_id || err.request_id)}</div>`,
      );
    } catch {
      wrap.className = "msg system";
      bubble.textContent = detail;
    }
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let requestId = "";
  let outputRedacted = false;

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() || "";

    for (const chunk of chunks) {
      const line = chunk.trim();
      if (!line.startsWith("data:")) continue;
      const payload = JSON.parse(line.slice(5).trim());
      if (payload.request_id) requestId = payload.request_id;
      if (payload.type === "delta") {
        bubble.textContent += payload.content;
        thread.scrollTop = thread.scrollHeight;
      } else if (payload.type === "done") {
        outputRedacted = Boolean(payload.output_redacted);
      } else if (payload.type === "error") {
        wrap.className = "msg system";
        bubble.textContent = payload.detail || "Stream error";
      }
    }
  }

  const foot = document.createElement("div");
  foot.className = "foot";
  foot.innerHTML = safetyFoot({ input_flagged: false, output_redacted: outputRedacted }, requestId);
  wrap.appendChild(foot);
}

async function sendAsk(question) {
  appendMessage({ role: "user", content: question });
  const res = await fetch("/v1/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      top_k: 3,
      safety_mode: safetyMode.value,
    }),
  });

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data.detail?.reason || data.detail?.error || data.detail || `HTTP ${res.status}`;
    appendMessage({
      role: "system",
      content: String(detail),
      foot: safetyFoot({ input_flagged: true }, data.detail?.request_id || data.request_id),
    });
    return;
  }

  appendMessage({
    role: "assistant",
    content: data.answer || "(empty)",
    sources: data.sources || [],
    foot: safetyFoot(data.safety, data.request_id),
  });
}

composer.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (busy) return;
  const message = promptEl.value.trim();
  if (!message) return;

  promptEl.value = "";
  setBusy(true);
  try {
    if (mode === "ask") await sendAsk(message);
    else await sendChat(message);
  } catch (err) {
    appendMessage({ role: "system", content: err?.message || "Request failed" });
  } finally {
    setBusy(false);
    promptEl.focus();
  }
});

promptEl.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    composer.requestSubmit();
  }
});

clearSession.addEventListener("click", async () => {
  const id = sessionId.value.trim() || "session-1";
  try {
    await fetch(`/v1/sessions/${encodeURIComponent(id)}`, { method: "DELETE" });
    appendMessage({
      role: "system",
      content: `Session “${id}” dibersihkan.`,
    });
  } catch (err) {
    appendMessage({ role: "system", content: err?.message || "Gagal clear session" });
  }
});

showEmpty();
refreshHealth();
setInterval(refreshHealth, 15000);
