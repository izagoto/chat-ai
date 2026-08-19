const TOKEN_KEY = "alder.token";
const USER_KEY = "alder.user";

let onUnauthorized = null;

export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler;
}

export function getStoredToken() {
  return localStorage.getItem(TOKEN_KEY) || "";
}

export function getStoredUser() {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function storeSession(token, user) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

function extractError(data, status) {
  const detail = data?.detail?.detail || data?.detail?.error || data?.detail || data?.error || `HTTP ${status}`;
  return typeof detail === "string" ? detail : JSON.stringify(detail);
}

export async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  const token = getStoredToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(path, { ...options, headers });
  const data = await res.json().catch(() => ({}));

  if (res.status === 401 && path !== "/v1/auth/login") {
    clearSession();
    if (onUnauthorized) onUnauthorized();
    throw new Error("Session expired. Please sign in again.");
  }

  if (!res.ok) {
    throw new Error(extractError(data, res.status));
  }

  return data;
}

export async function ingestUrl(url) {
  return api("/v1/urls", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
}

export async function uploadDocument(file) {
  const form = new FormData();
  form.append("file", file);
  return api("/v1/documents", { method: "POST", body: form });
}

export async function waitUntilDocumentReady(documentId, { timeoutMs = 120000, intervalMs = 400 } = {}) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const data = await api("/v1/documents");
    const doc = (data.documents || []).find((d) => d.document_id === documentId);
    if (!doc) throw new Error("Document not found.");
    if (!doc.status || doc.status === "ready") return doc;
    if (doc.status === "failed") throw new Error(doc.error || "Document indexing failed.");
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  throw new Error("Document is still indexing. Try sending again in a moment.");
}

export async function streamChat({ message, conversationId, sessionId, editMessageId, onDelta, onSources, onDone, onError }) {
  const token = getStoredToken();
  const headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch("/v1/chat/stream", {
    method: "POST",
    headers,
    body: JSON.stringify({
      message,
      conversation_id: conversationId || undefined,
      session_id: sessionId,
      use_documents: true,
      temperature: 0.5,
      edit_message_id: editMessageId || undefined,
    }),
  });

  if (res.status === 401) {
    clearSession();
    if (onUnauthorized) onUnauthorized();
    throw new Error("Session expired. Please sign in again.");
  }

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(extractError(data, res.status));
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";
    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith("data:")) continue;
      try {
        const payload = JSON.parse(line.slice(5).trim());
        if (payload.type === "delta" && payload.content) onDelta?.(payload.content);
        if (payload.type === "sources") onSources?.(payload.sources || []);
        if (payload.type === "done") onDone?.(payload);
        if (payload.type === "error") onError?.(payload.detail || "Stream error");
      } catch {
        // ignore malformed chunks
      }
    }
  }
}
