import { useState } from "react";
import { StatusBar } from "./components/StatusBar";
import { ChatPanel } from "./components/ChatPanel";
import { NotesPanel } from "./components/NotesPanel";
import { ExamGeneratorPanel } from "./components/ExamGeneratorPanel";
import { ImageStudioPanel } from "./components/ImageStudioPanel";
import { HistoryDrawer } from "./components/HistoryDrawer";
import type { ExamPaperRecord } from "./api/client";

export type NavTab = "chat" | "notes" | "exam" | "image" | "generate" | "debug";

export default function App() {
  const [activeTab, setActiveTab] = useState<NavTab>("chat");
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [selectedConvId, setSelectedConvId] = useState<string | null>(null);
  const [selectedExam, setSelectedExam] = useState<ExamPaperRecord | null>(null);
  const [editorInitialCode, setEditorInitialCode] = useState<string | undefined>(undefined);

  function handleTabChange(tab: NavTab) {
    if (tab !== activeTab) {
      setSelectedConvId(null);
      setSelectedExam(null);
    }
    setActiveTab(tab);
  }

  function handleSelectConversation(convId: string, mode: string) {
    setSelectedConvId(convId);
    if (mode === "notes_qa") {
      setActiveTab("notes");
    } else if (mode === "generate" || mode === "debug") {
      setActiveTab(mode);
    } else {
      setActiveTab("chat");
    }
    setIsHistoryOpen(false);
  }

  function handleSelectExam(paper: ExamPaperRecord) {
    setSelectedExam(paper);
    setActiveTab("exam");
    setIsHistoryOpen(false);
  }

  function handleNewSession() {
    setSelectedConvId(null);
    setSelectedExam(null);
    setIsHistoryOpen(false);
  }

  function handleOpenCodeInEditor(code: string) {
    setEditorInitialCode(code);
    setActiveTab("chat");
  }

  return (
    <div className="app terminal-theme">
      <StatusBar />

      {/* Main Terminal Feature Navigation Bar */}
      <nav className="main-nav-bar">
        <div className="main-tabs">
          <button
            type="button"
            className={`main-tab ${activeTab === "chat" ? "active" : ""}`}
            onClick={() => handleTabChange("chat")}
          >
            <span className="tab-prompt">$</span> 💬 Code Chat
          </button>
          <button
            type="button"
            className={`main-tab ${activeTab === "notes" ? "active" : ""}`}
            onClick={() => handleTabChange("notes")}
          >
            <span className="tab-prompt">$</span> 📚 Notes Q&A (RAG)
          </button>
          <button
            type="button"
            className={`main-tab ${activeTab === "exam" ? "active" : ""}`}
            onClick={() => handleTabChange("exam")}
          >
            <span className="tab-prompt">$</span> 📝 Exam Generator
          </button>
          <button
            type="button"
            className={`main-tab ${activeTab === "image" ? "active" : ""}`}
            onClick={() => handleTabChange("image")}
          >
            <span className="tab-prompt">$</span> 🎨 Image Studio
          </button>
          <button
            type="button"
            className={`main-tab ${activeTab === "generate" ? "active" : ""}`}
            onClick={() => handleTabChange("generate")}
          >
            <span className="tab-prompt">$</span> ⚡ Code Gen
          </button>
          <button
            type="button"
            className={`main-tab ${activeTab === "debug" ? "active" : ""}`}
            onClick={() => handleTabChange("debug")}
          >
            <span className="tab-prompt">$</span> 🐞 Debugger
          </button>
        </div>

        {/* Local Storage & History Toggle */}
        <div className="nav-actions">
          <button
            type="button"
            className="history-toggle-btn"
            onClick={() => setIsHistoryOpen(true)}
            title="Open locally saved chats & exams"
          >
            <span className="history-icon">💾</span> Local History
          </button>
        </div>
      </nav>

      {/* Slide-out History Drawer */}
      <HistoryDrawer
        isOpen={isHistoryOpen}
        onClose={() => setIsHistoryOpen(false)}
        onSelectConversation={handleSelectConversation}
        onSelectExam={handleSelectExam}
        onNewSession={handleNewSession}
      />

      {/* Active Feature Workspace */}
      <main className="main-content">
        {activeTab === "notes" && <NotesPanel initialConvId={selectedConvId} />}
        {activeTab === "exam" && <ExamGeneratorPanel initialExam={selectedExam} />}
        {activeTab === "image" && (
          <ImageStudioPanel onOpenInEditor={handleOpenCodeInEditor} />
        )}
        {(activeTab === "chat" || activeTab === "generate" || activeTab === "debug") && (
          <ChatPanel
            mode={activeTab}
            onModeChange={(m) => setActiveTab(m)}
            initialConvId={selectedConvId}
            initialCode={editorInitialCode}
          />
        )}
      </main>
    </div>
  );
}
