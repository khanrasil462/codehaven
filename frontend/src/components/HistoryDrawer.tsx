import { useEffect, useState } from "react";
import {
  deleteConversation,
  deleteExamPaper,
  fetchConversations,
  fetchExamPapers,
  type ConversationSummary,
  type ExamPaperRecord,
} from "../api/client";

interface HistoryDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectConversation: (convId: string, mode: string) => void;
  onSelectExam: (paper: ExamPaperRecord) => void;
  onNewSession: () => void;
}

export function HistoryDrawer({
  isOpen,
  onClose,
  onSelectConversation,
  onSelectExam,
  onNewSession,
}: HistoryDrawerProps) {
  const [tab, setTab] = useState<"chat" | "notes_qa" | "exams">("chat");
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [exams, setExams] = useState<ExamPaperRecord[]>([]);
  const [loading, setLoading] = useState(false);

  async function loadHistory() {
    setLoading(true);
    try {
      if (tab === "exams") {
        const papers = await fetchExamPapers();
        setExams(papers);
      } else {
        const convs = await fetchConversations(tab);
        setConversations(convs);
      }
    } catch {
      // Backend may be offline
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (isOpen) {
      loadHistory();
    }
  }, [isOpen, tab]);

  async function handleDeleteConv(id: string, e: React.MouseEvent) {
    e.stopPropagation();
    if (!window.confirm("Delete this conversation from local history?")) return;
    try {
      await deleteConversation(id);
      setConversations((prev) => prev.filter((c) => c.id !== id));
    } catch (err) {
      alert("Failed to delete conversation");
    }
  }

  async function handleDeleteExam(id: string, e: React.MouseEvent) {
    e.stopPropagation();
    if (!window.confirm("Delete this saved exam paper?")) return;
    try {
      await deleteExamPaper(id);
      setExams((prev) => prev.filter((ex) => ex.id !== id));
    } catch (err) {
      alert("Failed to delete exam paper");
    }
  }

  if (!isOpen) return null;

  return (
    <div className="history-overlay" onClick={onClose}>
      <aside className="history-drawer" onClick={(e) => e.stopPropagation()}>
        <div className="history-header">
          <div className="history-header-title">
            <span></span>
            <strong>Local Storage & History</strong>
          </div>
          <button type="button" className="close-btn" onClick={onClose} title="Close drawer">Close</button>
        </div>

        <button type="button" className="new-session-btn" onClick={onNewSession}>
          + New Session
        </button>

        {/* Category Tabs */}
        <div className="history-tabs">
          <button
            type="button"
            className={`history-tab ${tab === "chat" ? "active" : ""}`}
            onClick={() => setTab("chat")}
          >
            Chats
          </button>
          <button
            type="button"
            className={`history-tab ${tab === "notes_qa" ? "active" : ""}`}
            onClick={() => setTab("notes_qa")}
          >
            Notes Q&A
          </button>
          <button
            type="button"
            className={`history-tab ${tab === "exams" ? "active" : ""}`}
            onClick={() => setTab("exams")}
          >
            Exam Papers
          </button>
        </div>

        {/* Content List */}
        <div className="history-list">
          {loading ? (
            <div className="history-loading">Loading local SQLite history...</div>
          ) : tab === "exams" ? (
            exams.length === 0 ? (
              <div className="history-empty">No saved exam papers yet.</div>
            ) : (
              exams.map((exam) => (
                <div
                  key={exam.id}
                  className="history-item"
                  onClick={() => onSelectExam(exam)}
                >
                  <div className="history-item-main">
                    <strong className="history-item-title">{exam.title}</strong>
                    <div className="history-item-meta">
                      <span>{exam.subject}</span>
                      <span>• {exam.total_marks} Marks</span>
                      <span>• {new Date(exam.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                  <button
                    type="button"
                    className="delete-icon-btn"
                    title="Delete exam"
                    onClick={(e) => handleDeleteExam(exam.id, e)}
                  >×</button>
                </div>
              ))
            )
          ) : conversations.length === 0 ? (
            <div className="history-empty">No saved sessions in this mode.</div>
          ) : (
            conversations.map((conv) => (
              <div
                key={conv.id}
                className="history-item"
                onClick={() => onSelectConversation(conv.id, conv.mode)}
              >
                <div className="history-item-main">
                  <strong className="history-item-title">{conv.title}</strong>
                  <div className="history-item-meta">
                    <span>{new Date(conv.updated_at).toLocaleDateString()}</span>
                    <span>{new Date(conv.updated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                  </div>
                </div>
                <button
                  type="button"
                  className="delete-icon-btn"
                  title="Delete conversation"
                  onClick={(e) => handleDeleteConv(conv.id, e)}
                >×</button>
              </div>
            ))
          )}
        </div>

        <div className="history-footer">
          <span className="storage-badge">SQLite: codehaven.db (Local)</span>
          <span className="privacy-badge">100% Offline & Private</span>
        </div>
      </aside>
    </div>
  );
}
