import { useCallback, useEffect, useRef, useState } from "react";
import { FileText, Image as ImageIcon, Link2, Trash2, Upload } from "lucide-react";
import { api, ingestUrl, uploadDocument } from "../api/client";

function DocIcon({ type }) {
  if (type === "image") return <ImageIcon size={18} />;
  if (type === "url") return <Link2 size={18} />;
  return <FileText size={18} />;
}

function statusLabel(doc) {
  if (doc.status === "processing") return "Indexing…";
  if (doc.status === "failed") return doc.error || "Failed";
  return `${doc.chunk_count} chunks`;
}

export function Documents() {
  const [documents, setDocuments] = useState([]);
  const [totalChunks, setTotalChunks] = useState(0);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [flash, setFlash] = useState("");
  const [error, setError] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [url, setUrl] = useState("");
  const fileRef = useRef(null);

  const refresh = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    setError("");
    try {
      const data = await api("/v1/documents");
      setDocuments(data.documents || []);
      setTotalChunks(data.total_chunks || 0);
    } catch (err) {
      setError(err.message || "Failed to load documents.");
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const processing = documents.some((d) => d.status === "processing");
  useEffect(() => {
    if (!processing) return undefined;
    const timer = setInterval(() => refresh(true), 1200);
    return () => clearInterval(timer);
  }, [processing, refresh]);

  async function handleFiles(files) {
    const list = Array.from(files || []);
    if (!list.length) return;
    setUploading(true);
    setFlash("");
    setError("");
    try {
      for (const file of list) {
        await uploadDocument(file);
      }
      setFlash(`${list.length} file uploaded.`);
      await refresh(true);
    } catch (err) {
      setError(err.message || "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  async function handleUrl(ev) {
    ev.preventDefault();
    const target = url.trim();
    if (!target || uploading) return;
    setUploading(true);
    setFlash("");
    setError("");
    try {
      await ingestUrl(target);
      setUrl("");
      setFlash("URL queued for indexing.");
      await refresh(true);
    } catch (err) {
      setError(err.message || "Failed to fetch URL.");
    } finally {
      setUploading(false);
    }
  }

  async function onDelete(documentId) {
    if (!window.confirm("Delete this document from the index?")) return;
    setError("");
    try {
      await api(`/v1/documents/${encodeURIComponent(documentId)}`, { method: "DELETE" });
      setFlash("Document deleted.");
      await refresh(true);
    } catch (err) {
      setError(err.message || "Failed to delete.");
    }
  }

  return (
    <div className="docs-page">
      <header className="docs-intro">
        <p>PDF, Word, Excel, TXT, JSON, CSV, images, and public URLs become chat context.</p>
      </header>

      <div
        className={`docs-drop${dragOver ? " over" : ""}${uploading ? " busy" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          handleFiles(e.dataTransfer.files);
        }}
        onClick={() => !uploading && fileRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") fileRef.current?.click();
        }}
      >
        <input
          ref={fileRef}
          type="file"
          className="hidden"
          multiple
          accept=".pdf,.docx,.xlsx,.xls,.csv,.txt,.md,.log,.json,.jpg,.jpeg,.png,.webp,.gif,.bmp,.tiff"
          onChange={(e) => {
            handleFiles(e.target.files);
            e.target.value = "";
          }}
        />
        <Upload size={22} strokeWidth={2} />
        <strong>{uploading ? "Uploading…" : "Drop files here or click to upload"}</strong>
        <span>Indexed locally for Alder AI chat</span>
      </div>

      <form className="docs-url" onSubmit={handleUrl}>
        <input
          type="url"
          placeholder="https://example.com/article"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          disabled={uploading}
        />
        <button type="submit" disabled={uploading || !url.trim()}>
          Add URL
        </button>
      </form>

      <div className="docs-meta">
        {loading ? "Loading…" : `${documents.length} files · ${totalChunks} chunks`}
      </div>

      {flash ? <div className="flash">{flash}</div> : null}
      {error ? <div className="flash err">{error}</div> : null}

      <ul className="docs-list">
        {documents.length === 0 && !loading ? (
          <li className="docs-empty">No documents yet.</li>
        ) : (
          documents.map((doc) => (
            <li key={doc.document_id} className={`docs-item${doc.status === "failed" ? " failed" : ""}`}>
              <span className="docs-item-icon">
                <DocIcon type={doc.artifact_type} />
              </span>
              <div className="docs-item-body">
                <strong>{doc.filename}</strong>
                <span>
                  <em className={`docs-status ${doc.status || "ready"}`}>{statusLabel(doc)}</em>
                  {" · "}
                  {doc.artifact_type}
                  {" · "}
                  {new Date(doc.ingested_at).toLocaleString()}
                </span>
              </div>
              <button
                type="button"
                className="docs-delete"
                onClick={() => onDelete(doc.document_id)}
                title="Delete"
                aria-label={`Delete ${doc.filename}`}
              >
                <Trash2 size={16} />
              </button>
            </li>
          ))
        )}
      </ul>
    </div>
  );
}
