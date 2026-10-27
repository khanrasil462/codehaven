import { useCallback, useEffect, useState } from "react";
import { UsageMeter } from "./components/UsageMeter";
import { StatusBar } from "./components/StatusBar";
import { ChatPanel } from "./components/ChatPanel";
import { NotesPanel } from "./components/NotesPanel";
import { ExamGeneratorPanel } from "./components/ExamGeneratorPanel";
import { ImageStudioPanel } from "./components/ImageStudioPanel";
import { HistoryDrawer } from "./components/HistoryDrawer";
import { ModelPicker } from "./components/ModelPicker";
import { SystemMonitor } from "./components/SystemMonitor";
import { CommandPalette, type Command } from "./components/CommandPalette";
import {
  deleteConversation,
  fetchConversations,
  type ConversationSummary,
  type ExamPaperRecord,
} from "./api/client";

export type NavTab = "chat" | "notes" | "exam" | "image";

const TABS: { id: NavTab; label: string }[] = [
  { id: "chat", label: "Chat" },
  { id: "notes", label: "Notes Q&A" },
  { id: "exam", label: "Exam papers" },
  { id: "image", label: "Diagrams" },
];

export default function App() {
  const [activeTab, setActiveTab] = useState<NavTab>("chat");
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [selectedConvId, setSelectedConvId] = useState<string | null>(null);
  const [chatKey, setChatKey] = useState(0);
  const [selectedExam, setSelectedExam] = useState<ExamPaperRecord | null>(null);
  const [recents, setRecents] = useState<ConversationSummary[]>([]);

  const loadRecents = useCallback(() => {
    fetchConversations("chat")
      .then((list) => setRecents(list.slice(0, 30)))
      .catch(() => setRecents([]));
  }, []);

  useEffect(loadRecents, [loadRecents]);

  function goTab(tab: NavTab) {
    if (tab !== activeTab) setSelectedExam(null);
    setActiveTab(tab);
  }

  function newChat() {
    setSelectedConvId(null);
    setChatKey((k) => k + 1);
    setActiveTab("chat");
    setIsHistoryOpen(false);
  }

  function openConversation(id: string, mode = "chat") {
    setSelectedConvId(id);
    setChatKey((k) => k + 1);
    setActiveTab(mode === "notes_qa" ? "notes" : "chat");
    setIsHistoryOpen(false);
  }

  async function removeConversation(id: string) {
    await deleteConversation(id).catch(() => undefined);
    if (id === selectedConvId) newChat();
    loadRecents();
  }

  const commands: Command[] = [
    { id: "new", label: "New chat", run: newChat },
    ...TABS.map((t) => ({ id: t.id, label: `Go to ${t.label}`, run: () => goTab(t.id) })),
    { id: "history", label: "Open full history", run: () => setIsHistoryOpen(true) },
    { id: "reload", label: "Reload window", run: () => window.location.reload() },
  ];

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">&gt;_</span>
          <strong>codehaven</strong>
        </div>

        <button type="button" className="new-chat" onClick={newChat}>
          <span>New chat</span>
          <kbd>Ctrl K</kbd>
        </button>

        <nav className="nav">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              className={`nav-item ${activeTab === t.id ? "active" : ""}`}
              onClick={() => goTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>

        <div className="recents">
          <span className="nav-label">Recent</span>
          <div className="recents-list">
            {recents.length === 0 && <span className="muted recents-empty">No chats yet</span>}
            {recents.map((c) => (
              <div
                key={c.id}
                className={`recent ${c.id === selectedConvId && activeTab === "chat" ? "active" : ""}`}
              >
                <button type="button" className="recent-title" onClick={() => openConversation(c.id, c.mode)}>
                  {c.title || "Untitled"}
                </button>
                <button
                  type="button"
                  className="recent-del"
                  aria-label="Delete chat"
                  onClick={() => void removeConversation(c.id)}
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        </div>

        <StatusBar />
      </aside>

      <div className="stage">
        <header className="topbar">
          <span className="crumb">~/{TABS.find((t) => t.id === activeTab)?.label.toLowerCase().replace(/[^a-z]+/g, "-")}</span>
          <div className="topbar-right">
            <UsageMeter />
            <ModelPicker />
          </div>
        </header>
        <main className="main-content" key={activeTab === "chat" ? `chat-${chatKey}` : activeTab}>
          {activeTab === "notes" && <NotesPanel initialConvId={selectedConvId} />}
          {activeTab === "exam" && <ExamGeneratorPanel initialExam={selectedExam} />}
          {activeTab === "image" && <ImageStudioPanel onOpenInEditor={() => setActiveTab("chat")} />}
          {activeTab === "chat" && (
            <ChatPanel initialConvId={selectedConvId} onConversationChange={loadRecents} />
          )}
        </main>
        <SystemMonitor />
      </div>

      <CommandPalette commands={commands} />

      <HistoryDrawer
        isOpen={isHistoryOpen}
        onClose={() => setIsHistoryOpen(false)}
        onSelectConversation={(id, mode) => openConversation(id, mode)}
        onSelectExam={(paper) => {
          setSelectedExam(paper);
          setActiveTab("exam");
          setIsHistoryOpen(false);
        }}
        onNewSession={newChat}
      />
    </div>
  );
}
