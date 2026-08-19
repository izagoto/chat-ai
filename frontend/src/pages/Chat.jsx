import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowUp, FileText, Image as ImageIcon, ListTree, Paperclip, Pencil, Square, Table2 } from "lucide-react";
import { api, streamChat, uploadDocument, waitUntilDocumentReady } from "../api/client";
import { MarkdownMessage } from "../components/MarkdownMessage";
import { CONV_KEY, useConversations } from "../conversations/ConversationContext";

const SUGGESTIONS = [
  { icon: FileText, label: "Summarize document", prompt: "Summarize the document I already uploaded" },
  { icon: ListTree, label: "File highlights", prompt: "What are the main points from the last file?" },
  { icon: ImageIcon, label: "Explain image", prompt: "Explain the image I attached" },
  { icon: Table2, label: "Make a comparison", prompt: "Make a short comparison as a Markdown table" },
];

export function Chat() {
  const { conversationId } = useParams();
  const navigate = useNavigate();
  const { draftNonce, rememberConversation } = useConversations();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [pendingFiles, setPendingFiles] = useState([]);
  const [error, setError] = useState("");
  const [editingId, setEditingId] = useState(null);
  const [editDraft, setEditDraft] = useState("");
  const [docCount, setDocCount] = useState(0);
  const [processingCount, setProcessingCount] = useState(0);
  const bottomRef = useRef(null);
  const fileRef = useRef(null);
  const abortRef = useRef(false);
  const textareaRef = useRef(null);
  const conversationIdRef = useRef(conversationId || "");
  const turnRef = useRef(0);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  useEffect(() => {
    let cancelled = false;
    async function loadDocs() {
      try {
        const data = await api("/v1/documents");
        if (cancelled) return;
        const docs = data.documents || [];
        setDocCount(docs.filter((d) => !d.status || d.status === "ready").length);
        setProcessingCount(docs.filter((d) => d.status === "processing").length);
      } catch {
        if (!cancelled) {
          setDocCount(0);
          setProcessingCount(0);
        }
      }
    }
    loadDocs();
    const timer = setInterval(loadDocs, 2500);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (conversationId) return;
    const stored = sessionStorage.getItem(CONV_KEY);
    if (stored) navigate(`/chat/${stored}`, { replace: true });
  }, [conversationId, navigate, draftNonce]);

  useEffect(() => {
    abortRef.current = true;
    turnRef.current += 1;
    setBusy(false);
    setError("");
    setPendingFiles([]);
    setInput("");
    setEditingId(null);
    setEditDraft("");
    conversationIdRef.current = conversationId || "";

    if (!conversationId) {
      setMessages([]);
      return undefined;
    }

    let cancelled = false;
    (async () => {
      try {
        const data = await api(`/v1/conversations/${conversationId}`);
        if (cancelled) return;
        conversationIdRef.current = data.conversation.id;
        setMessages((data.conversation.messages || []).map((m) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          sources: m.sources || [],
        })));
      } catch (err) {
        if (cancelled) return;
        sessionStorage.removeItem(CONV_KEY);
        setError(err.message || "Conversation not found.");
        setMessages([]);
        navigate("/chat", { replace: true });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [conversationId, draftNonce, navigate]);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = `${Math.min(el.scrollHeight, 140)}px`;
  }, [input]);

  function onPickFiles(ev) {
    const files = Array.from(ev.target.files || []);
    if (files.length) setPendingFiles((prev) => [...prev, ...files]);
    ev.target.value = "";
  }

  async function streamTurn(question, { editMessageId } = {}) {
    const turn = turnRef.current;
    try {
      await streamChat({
        message: question,
        conversationId: conversationIdRef.current,
        editMessageId,
        onDelta: (delta) => {
          if (turn !== turnRef.current) return;
          setMessages((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (last?.role === "assistant") {
              next[next.length - 1] = { ...last, content: last.content + delta };
            }
            return next;
          });
        },
        onError: (detail) => {
          if (turn !== turnRef.current) return;
          setError(detail);
        },
        onSources: (sources) => {
          if (turn !== turnRef.current) return;
          setMessages((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (last?.role === "assistant") {
              next[next.length - 1] = { ...last, sources };
            }
            return next;
          });
        },
        onDone: async (payload) => {
          if (turn !== turnRef.current) return;
          const convId = payload?.conversation_id;
          if (convId) {
            conversationIdRef.current = convId;
            rememberConversation(convId);
            try {
              const data = await api(`/v1/conversations/${convId}`);
              if (turn !== turnRef.current) return;
              setMessages((data.conversation.messages || []).map((m) => ({
                id: m.id,
                role: m.role,
                content: m.content,
                sources: m.sources || [],
              })));
              return;
            } catch {
              // keep streamed messages if refresh fails
            }
          }
          if (payload?.sources?.length) {
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              if (last?.role === "assistant" && !last.sources?.length) {
                next[next.length - 1] = { ...last, sources: payload.sources };
              }
              return next;
            });
          }
        },
      });
    } catch (err) {
      if (turn !== turnRef.current) return;
      setError(err.message || "Chat failed.");
      setMessages((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last?.role === "assistant" && !last.content) {
          next[next.length - 1] = { ...last, content: "Sorry, something went wrong." };
        }
        return next;
      });
    } finally {
      if (turn === turnRef.current) setBusy(false);
    }
  }

  async function send(preset) {
    const text = (preset ?? input).trim();
    if ((!text && pendingFiles.length === 0) || busy) return;

    setError("");
    setBusy(true);
    abortRef.current = false;
    turnRef.current += 1;
    setEditingId(null);

    const filesToUpload = [...pendingFiles];
    setPendingFiles([]);
    setInput("");

    const uploadedNames = [];
    for (const file of filesToUpload) {
      try {
        const res = await uploadDocument(file);
        uploadedNames.push(res.document?.filename || file.name);
        const docId = res.document?.document_id;
        if (docId && res.document?.status === "processing") {
          await waitUntilDocumentReady(docId);
        }
        setDocCount((c) => c + 1);
        setProcessingCount((n) => Math.max(0, n - 1));
      } catch (err) {
        setError(err.message || `Failed to upload ${file.name}`);
        setBusy(false);
        return;
      }
    }

    let question = text;
    if (uploadedNames.length && !question) {
      question = `I just uploaded: ${uploadedNames.join(", ")}. Summarize the contents.`;
    } else if (uploadedNames.length) {
      question = `${text}\n\n(Uploaded files: ${uploadedNames.join(", ")})`;
    }

    setMessages((prev) => [
      ...prev,
      { role: "user", content: question },
      { role: "assistant", content: "", sources: [] },
    ]);

    await streamTurn(question);
  }

  async function submitEdit(index) {
    const msg = messages[index];
    const question = editDraft.trim();
    if (!question || busy || !msg?.id) return;

    setError("");
    setBusy(true);
    abortRef.current = false;
    turnRef.current += 1;
    setEditingId(null);
    setEditDraft("");

    setMessages((prev) => [
      ...prev.slice(0, index),
      { ...msg, content: question },
      { role: "assistant", content: "", sources: [] },
    ]);

    await streamTurn(question, { editMessageId: msg.id, fromIndex: index });
  }

  function onKeyDown(ev) {
    if (ev.key === "Enter" && !ev.shiftKey) {
      ev.preventDefault();
      send();
    }
  }

  const isEmpty = messages.length === 0;

  const composer = (
    <div className="chat-composer">
      <input
        ref={fileRef}
        type="file"
        className="hidden"
        multiple
        accept=".pdf,.docx,.xlsx,.xls,.csv,.txt,.md,.log,.json,.jpg,.jpeg,.png,.webp,.gif,.bmp,.tiff"
        onChange={onPickFiles}
      />
      <button
        type="button"
        className="chat-icon-btn"
        title="Attach file"
        onClick={() => fileRef.current?.click()}
        disabled={busy}
      >
        <Paperclip size={18} />
      </button>
      <textarea
        ref={textareaRef}
        rows={1}
        placeholder={isEmpty ? "Ask anything" : "Message Alder AI…"}
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={onKeyDown}
        disabled={busy}
      />
      <button
        type="button"
        className="chat-send"
        onClick={busy ? () => { abortRef.current = true; turnRef.current += 1; setBusy(false); } : () => send()}
        disabled={!busy && !input.trim() && pendingFiles.length === 0}
        aria-label={busy ? "Stop" : "Send"}
      >
        {busy ? <Square size={13} /> : <ArrowUp size={18} strokeWidth={2.4} />}
      </button>
    </div>
  );

  const flash = error ? <div className="flash err chat-flash">{error}</div> : null;

  const attachments = pendingFiles.length > 0 ? (
    <div className="chat-attachments">
      {pendingFiles.map((f, i) => {
        const isImage = /\.(png|jpe?g|gif|webp|bmp|tiff)$/i.test(f.name);
        return (
          <span key={`${f.name}-${i}`} className="chat-attach-chip">
            {isImage ? <ImageIcon size={13} /> : <FileText size={13} />}
            {f.name}
            <button
              type="button"
              aria-label="Remove"
              onClick={() => setPendingFiles((prev) => prev.filter((_, idx) => idx !== i))}
            >
              ×
            </button>
          </span>
        );
      })}
    </div>
  ) : null;

  if (isEmpty) {
    return (
      <div className="chat-shell is-empty">
        <div className="chat-landing">
          <h2 className="chat-landing-title">What can I help with?</h2>
          {flash}
          {attachments}
          {composer}
          <div className="chat-suggestions">
            {SUGGESTIONS.map((s) => {
              const Icon = s.icon;
              return (
                <button
                  key={s.prompt}
                  type="button"
                  className="suggestion"
                  onClick={() => send(s.prompt)}
                  disabled={busy}
                >
                  <Icon size={15} strokeWidth={2} />
                  {s.label}
                </button>
              );
            })}
          </div>
          <p className="chat-disclaimer">Alder AI can make mistakes. Check important info.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-shell">
      <div className="chat-messages">
        {messages.map((m, i) => (
            <div key={m.id || `${m.role}-${i}`} className={`chat-row ${m.role}`}>
              <div className={`chat-avatar ${m.role}`}>{m.role === "user" ? "You" : "A"}</div>
              <div className="chat-bubble-wrap">
                {m.role === "user" && editingId === (m.id || i) ? (
                  <div className="chat-bubble chat-bubble-edit">
                    <textarea
                      className="chat-edit-input"
                      value={editDraft}
                      onChange={(e) => setEditDraft(e.target.value)}
                      onKeyDown={(ev) => {
                        if (ev.key === "Enter" && !ev.shiftKey) {
                          ev.preventDefault();
                          submitEdit(i);
                        }
                        if (ev.key === "Escape") {
                          setEditingId(null);
                          setEditDraft("");
                        }
                      }}
                      rows={3}
                      autoFocus
                    />
                    <div className="chat-edit-actions">
                      <button type="button" className="chat-edit-cancel" onClick={() => { setEditingId(null); setEditDraft(""); }}>
                        Cancel
                      </button>
                      <button
                        type="button"
                        className="chat-edit-save"
                        onClick={() => submitEdit(i)}
                        disabled={!editDraft.trim() || editDraft.trim() === m.content}
                      >
                        Save
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="chat-bubble">
                    <div className={`chat-text${m.role === "assistant" ? " chat-md" : ""}`}>
                      {!m.content && busy && i === messages.length - 1 ? (
                        <span className="typing"><i /><i /><i /></span>
                      ) : m.role === "assistant" ? (
                        <MarkdownMessage content={m.content} />
                      ) : (
                        m.content
                      )}
                    </div>
                    {m.role === "assistant" && m.sources?.length ? (
                      <div className="chat-cites">
                        {m.sources.map((s, si) => (
                          <span
                            key={`${s.document_id || s.file}-${si}`}
                            className="chat-cite"
                            title={s.excerpt || s.file}
                          >
                            <FileText size={11} />
                            <span className="chat-cite-file">{s.file}</span>
                            {s.location ? <span className="chat-cite-loc">{s.location}</span> : null}
                          </span>
                        ))}
                      </div>
                    ) : null}
                  </div>
                )}
                {m.role === "user" && m.id && !busy && editingId == null ? (
                  <button
                    type="button"
                    className="chat-edit-btn"
                    title="Edit prompt"
                    aria-label="Edit prompt"
                    onClick={() => {
                      setEditingId(m.id);
                      setEditDraft(m.content);
                    }}
                  >
                    <Pencil size={13} />
                  </button>
                ) : null}
              </div>
            </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {flash}
      {attachments}

      <div className="chat-composer-wrap">
        <div className="chat-status">
          <span className={`status-dot${docCount > 0 || processingCount > 0 ? " on" : ""}`} />
        {processingCount > 0
          ? `Indexing ${processingCount} file${processingCount === 1 ? "" : "s"}…`
          : docCount > 0
          ? `${docCount} document${docCount === 1 ? "" : "s"} indexed`
          : "Ready — attach a file or start chatting"}
        </div>
        {composer}
      </div>
    </div>
  );
}
