import { useEffect, useRef, useState } from "react";
import {
  createConversation,
  deleteDocument,
  fetchConversation,
  fetchDocuments,
  saveMessage,
  streamNotesQuery,
  uploadDocument,
  type DocumentInfo,
  type SourceChunk,
} from "../api/client";
import { extractThoughtAndAnswer } from "./AgentProcessTimeline";
import { Markdown } from "../lib/markdown";

interface NotesMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: SourceChunk[];
  startTime?: number;
  endTime?: number;
}

interface NotesPanelProps {
  initialConvId?: string | null;
}

export function NotesPanel({ initialConvId }: NotesPanelProps = {}) {
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<string | undefined>(undefined);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);

  const [messages, setMessages] = useState<NotesMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "Welcome to Notes Q&A! Upload your syllabus, lecture slides, textbooks, or code notes (.pdf, .docx, .txt, .md). Ask any question, and I'll find the exact concepts in your notes and provide answers with verifiable citations.",
    },
  ]);
  const [input, setInput] = useState("");
  const [querying, setQuerying] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  async function loadDocs() {
    setLoadingDocs(true);
    try {
      const docs = await fetchDocuments();
      setDocuments(docs);
    } catch {
      // Backend might be offline
    } finally {
      setLoadingDocs(false);
    }
  }

  useEffect(() => {
    loadDocs();
  }, []);

  useEffect(() => {
    if (initialConvId) {
      setActiveConvId(initialConvId);
      fetchConversation(initialConvId)
        .then((conv) => {
          if (conv.messages.length > 0) {
            setMessages(
              conv.messages.map((m) => ({
                id: m.id,
                role: m.role as "user" | "assistant",
                content: m.content,
                sources: m.sources as SourceChunk[] | undefined,
              }))
            );
          }
        })
        .catch(console.error);
    }
  }, [initialConvId]);

  const [uploadProgress, setUploadProgress] = useState<string | null>(null);

  async function handleFileUpload(fileList: FileList | File[]) {
    const files = Array.from(fileList);
    if (files.length === 0) return;

    setUploading(true);
    setUploadError(null);

    const indexedDocs: DocumentInfo[] = [];
    const errors: string[] = [];

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      setUploadProgress(`Processing ${i + 1} of ${files.length}: ${file.name}...`);
      try {
        const newDoc = await uploadDocument(file);
        indexedDocs.push(newDoc);
      } catch (err) {
        errors.push(`${file.name}: ${err instanceof Error ? err.message : "Upload failed"}`);
      }
    }

    if (indexedDocs.length > 0) {
      setDocuments((prev) => {
        const newIds = new Set(indexedDocs.map((d) => d.id));
        return [...indexedDocs, ...prev.filter((d) => !newIds.has(d.id))];
      });

      const summary = indexedDocs.map((d) => `"${d.filename}" (${d.chunk_count} chunks)`).join(", ");
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: `Successfully indexed ${indexedDocs.length} note(s) [${summary}]! Scanned pages and images were transcribed via local OCR. You can now ask questions about them.`,
        },
      ]);
    }

    if (errors.length > 0) {
      setUploadError(errors.join(" | "));
    }

    setUploading(false);
    setUploadProgress(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  async function handleDelete(docId: string, filename: string) {
    if (!window.confirm(`Delete "${filename}" and its vector index?`)) return;
    try {
      await deleteDocument(docId);
      setDocuments((prev) => prev.filter((d) => d.id !== docId));
      if (selectedDocId === docId) setSelectedDocId(undefined);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to delete document");
    }
  }

  async function askQuestion(customQuestion?: string) {
    const q = (customQuestion || input).trim();
    if (!q || querying) return;

    if (documents.length === 0) {
      alert("Please upload at least one note (.pdf, .docx, .txt) first!");
      return;
    }

    const userMsg: NotesMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: q,
    };
    const assistantId = crypto.randomUUID();
    const assistantStartTime = Date.now();
    const nextMessages = [...messages, userMsg];

    setMessages([
      ...nextMessages,
      { id: assistantId, role: "assistant", content: "", startTime: assistantStartTime },
    ]);
    if (!customQuestion) setInput("");
    setQuerying(true);
    abortRef.current = new AbortController();

    // Auto-create or resume conversation in SQLite
    let currentConvId = activeConvId;
    if (!currentConvId) {
      currentConvId = crypto.randomUUID();
      setActiveConvId(currentConvId);
      createConversation(q.slice(0, 40), "notes_qa", currentConvId).catch(console.error);
    }
    saveMessage(currentConvId, "user", q, undefined, userMsg.id).catch(console.error);

    let fullAnswer = "";
    let capturedSources: SourceChunk[] | undefined = undefined;

    try {
      await streamNotesQuery(
        q,
        selectedDocId,
        (token) => {
          fullAnswer += token;
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, content: fullAnswer } : m
            )
          );
        },
        (sources) => {
          capturedSources = sources;
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, sources } : m
            )
          );
        },
        abortRef.current.signal
      );

      // Auto-save assistant answer to SQLite
      if (fullAnswer.trim()) {
        saveMessage(currentConvId, "assistant", fullAnswer, capturedSources, assistantId).catch(console.error);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Error querying notes";
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId ? { ...m, content: `Error: ${msg}` } : m
        )
      );
    } finally {
      const finishTime = Date.now();
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId ? { ...m, endTime: finishTime } : m
        )
      );
      setQuerying(false);
      abortRef.current = null;
    }
  }

  function stopQuery() {
    abortRef.current?.abort();
    setQuerying(false);
  }

  const selectedDoc = documents.find((d) => d.id === selectedDocId);

  return (
    <div className="layout notes-layout">
      {/* Left Pane: Documents Manager */}
      <section className="docs-sidebar">
        <div className="panel-header">
          <span>Notes Library ({documents.length})</span>
          <button
            type="button"
            className="secondary"
            onClick={loadDocs}
            disabled={loadingDocs}
            title="Refresh documents list"
          >
            Refresh
          </button>
        </div>

        {/* Dropzone / Upload Action */}
        <div
          className={`dropzone ${uploading ? "uploading" : ""}`}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            const files = e.dataTransfer.files;
            if (files && files.length > 0) handleFileUpload(files);
          }}
          onClick={() => fileInputRef.current?.click()}
        >
          <input
            type="file"
            ref={fileInputRef}
            style={{ display: "none" }}
            multiple
            accept=".pdf,.docx,.txt,.md,.py,.js,.ts,.html,.css,.json,.png,.jpg,.jpeg,.webp,.bmp,.tiff"
            onChange={(e) => {
              const files = e.target.files;
              if (files && files.length > 0) handleFileUpload(files);
            }}
          />
          <div className="dropzone-icon">{uploading ? "" : ""}</div>
          <div className="dropzone-text">
            <strong>{uploading ? (uploadProgress || "Running OCR & Indexing...") : "Upload Notes, Scanned PDFs & Images"}</strong>
            <span>Drag & drop multiple files or click to browse</span>
            <span className="file-types">Supports PDF, Scanned Docs, Images (PNG/JPG OCR), Word & Code</span>
          </div>
        </div>

        {uploadError && <div className="upload-error">{uploadError}</div>}

        {/* Document Filter Banner */}
        <div className="filter-bar">
          <label>Scope Q&A to:</label>
          <select
            value={selectedDocId ?? ""}
            onChange={(e) => setSelectedDocId(e.target.value ? e.target.value : undefined)}
          >
            <option value="">All Uploaded Notes ({documents.length})</option>
            {documents.map((d) => (
              <option key={d.id} value={d.id}>
                {d.filename}
              </option>
            ))}
          </select>
        </div>

        {/* Document Cards List */}
        <div className="docs-list">
          {documents.length === 0 ? (
            <div className="empty-docs">
              <p>No notes uploaded yet.</p>
              <span>Upload lecture notes, scanned textbook pages, or image notes to start answering questions.</span>
            </div>
          ) : (
            documents.map((doc) => {
              const isSelected = selectedDocId === doc.id;
              const sizeKb = Math.round(doc.size_bytes / 1024);
              const isImage = [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"].includes(doc.file_type);
              const docIcon = isImage ? "" : doc.file_type === ".pdf" ? "" : doc.file_type === ".docx" ? "" : "";

              return (
                <div
                  key={doc.id}
                  className={`doc-card ${isSelected ? "selected" : ""}`}
                  onClick={() => setSelectedDocId(isSelected ? undefined : doc.id)}
                >
                  <div className="doc-card-header">
                    <span className="doc-icon">{docIcon}</span>
                    <strong className="doc-name" title={doc.filename}>
                      {doc.filename}
                    </strong>
                    {isImage && <span className="ocr-pill">OCR</span>}
                    <button
                      type="button"
                      className="delete-btn"
                      title="Delete note"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(doc.id, doc.filename);
                      }}
                    >×</button>
                  </div>
                  <div className="doc-meta">
                    <span>{doc.chunk_count} chunks</span>
                    <span>{sizeKb} KB</span>
                    <span>{new Date(doc.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
              );
            }))}
        </div>
      </section>

      {/* Right Pane: Notes Q&A Conversation */}
      <section className="chat-section notes-chat-section">
        <div className="panel-header">
          <div>
            <strong>Grounded Q&A</strong>
            <span className="scope-indicator">
              {selectedDoc ? `Filtered: ${selectedDoc.filename}` : "Searching across all notes"}
            </span>
          </div>
          {selectedDoc && (
            <button
              type="button"
              className="secondary clear-filter-btn"
              onClick={() => setSelectedDocId(undefined)}
            >
              Clear filter
            </button>
          )}
        </div>

        <div className="messages notes-thread">
          {messages.map((m) => {
            const isCurrentlyGenerating = querying && m.id === messages[messages.length - 1]?.id;
            const { answer } = extractThoughtAndAnswer(m.content);

            return (
              <div key={m.id} className={`msg ${m.role}`}>
                {m.role === "user" ? (
                  <div className="bubble">{m.content}</div>
                ) : (
                  <>
                    <div className="avatar">CH</div>
                    <div className="body">
                      {answer ? (
                        <div className="answer-card">
                          <Markdown text={answer} />
                        </div>
                      ) : (
                        isCurrentlyGenerating && (
                          <span className="typing-line">
                            <span className="typing">
                              <i />
                              <i />
                              <i />
                            </span>
                            Searching your notes…
                          </span>
                        )
                      )}
                      {m.sources && m.sources.length > 0 && (
                        <details className="sources-container">
                          <summary className="sources-summary">
                            Sources
                            {m.sources.map((src, idx) => (
                              <span key={idx} className="source-chip">
                                {src.filename}
                              </span>
                            ))}
                          </summary>
                          <div className="sources-list">
                            {m.sources.map((src, idx) => (
                              <div key={idx} className="source-item">
                                <div className="source-header">
                                  <span className="source-badge">
                                    {src.filename} · section {src.chunk_index}
                                  </span>
                                  <span className="similarity-badge">{Math.round(src.similarity * 100)}% match</span>
                                </div>
                                <p className="source-text">{src.text}</p>
                              </div>
                            ))}
                          </div>
                        </details>
                      )}
                    </div>
                  </>
                )}
              </div>
            );
          })}
        </div>

        {/* Quick prompt suggestions */}
        <div className="quick-chips">
          <button
            type="button"
            className="chip"
            onClick={() => askQuestion("Summarize the main concepts and topics in these notes.")}
            disabled={querying || documents.length === 0}
          >
            Summarize Notes
          </button>
          <button
            type="button"
            className="chip"
            onClick={() => askQuestion("What are the key definitions and formulas explained here?")}
            disabled={querying || documents.length === 0}
          >
            Key Definitions
          </button>
          <button
            type="button"
            className="chip"
            onClick={() => askQuestion("What are the most likely exam questions from these notes?")}
            disabled={querying || documents.length === 0}
          >
            High-Yield Topics
          </button>
          <button
            type="button"
            className="chip"
            onClick={() => askQuestion("Provide a practical coding example explaining this concept.")}
            disabled={querying || documents.length === 0}
          >
            Code Example
          </button>
        </div>

        <div className="composer">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={
              documents.length === 0
                ? "Upload notes on the left first to enable Q&A..."
                : "Ask any question about your uploaded notes (e.g. 'Explain time complexity of binary search')..."
            }
            rows={3}
            disabled={querying || documents.length === 0}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                askQuestion();
              }
            }}
          />
          <div className="composer-actions">
            {querying ? (
              <button type="button" className="secondary" onClick={stopQuery}>
                Stop
              </button>
            ) : (
              <button
                type="button"
                onClick={() => askQuestion()}
                disabled={!input.trim() || documents.length === 0}
              >
                Ask Notes AI
              </button>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
