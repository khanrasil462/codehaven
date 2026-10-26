import { useEffect, useRef, useState } from "react";
import Editor from "@monaco-editor/react";
import {
  createConversation,
  fetchConversation,
  saveMessage,
  streamChat,
  streamCodegen,
  streamDebug,
  extractCodeBlock,
  type ChatMessage,
  type CodeLanguage,
} from "../api/client";
import { TerminalRunner } from "./TerminalRunner";
import { AgentProcessTimeline, extractThoughtAndAnswer } from "./AgentProcessTimeline";

type AppMode = "chat" | "generate" | "debug";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  startTime?: number;
  endTime?: number;
  mode?: AppMode;
  codeSnippet?: string;
}

const LANGUAGE_OPTIONS: { value: CodeLanguage; label: string; monaco: string }[] = [
  { value: "python", label: "Python 3", monaco: "python" },
  { value: "javascript", label: "JavaScript (Node)", monaco: "javascript" },
  { value: "typescript", label: "TypeScript", monaco: "typescript" },
  { value: "react", label: "React (JSX)", monaco: "javascript" },
];

const WELCOME: Record<AppMode, string> = {
  chat:
    "Hi! I'm CodeHaven — your offline terminal coding assistant. Ask me about algorithms, system design, Python, JS, or debugging. Run your code directly in the terminal below.",
  generate:
    "Generate mode: describe what you want built and I'll generate the implementation. Pick a language, click Generate, then hit [Run Code] to test it live.",
  debug:
    "Debug mode: paste your code in the editor and any error traceback below. I'll diagnose the bug, explain the root cause, and apply the verified fix.",
};

export interface ChatPanelProps {
  mode?: AppMode;
  onModeChange?: (mode: AppMode) => void;
  initialConvId?: string | null;
  initialCode?: string;
  initialLanguage?: CodeLanguage;
}

export function ChatPanel({
  mode: externalMode,
  onModeChange,
  initialConvId,
  initialCode,
  initialLanguage,
}: ChatPanelProps = {}) {
  const [internalMode, setInternalMode] = useState<AppMode>("chat");
  const mode = externalMode ?? internalMode;
  const [activeConvId, setActiveConvId] = useState<string | null>(null);

  const [language, setLanguage] = useState<CodeLanguage>(initialLanguage ?? "python");
  const [messages, setMessages] = useState<Message[]>([
    { id: "welcome", role: "assistant", content: WELCOME[mode] },
  ]);
  const [input, setInput] = useState("");
  const [errorInput, setErrorInput] = useState("");
  const [code, setCode] = useState(
    initialCode ??
      '# CodeHaven Interactive Runner\n\ndef greet(name: str) -> str:\n    return f"Hello from CodeHaven Terminal, {name}!"\n\nif __name__ == "__main__":\n    print(greet("Student"))\n    print("System: Online | Local Inference: Ready")\n'
  );
  const [loading, setLoading] = useState(false);
  const [lastGenerated, setLastGenerated] = useState("");
  const [lastFixed, setLastFixed] = useState("");
  const abortRef = useRef<AbortController | null>(null);

  const monacoLanguage =
    LANGUAGE_OPTIONS.find((o) => o.value === language)?.monaco ?? "python";

  useEffect(() => {
    if (initialCode !== undefined) {
      setCode(initialCode);
    }
  }, [initialCode]);

  useEffect(() => {
    if (initialLanguage !== undefined) {
      setLanguage(initialLanguage);
    }
  }, [initialLanguage]);

  useEffect(() => {
    if (externalMode) {
      setMessages([{ id: "welcome", role: "assistant", content: WELCOME[externalMode] }]);
      setInput("");
      setErrorInput("");
      setLastGenerated("");
      setLastFixed("");
    }
  }, [externalMode]);

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
              }))
            );
          }
        })
        .catch(console.error);
    }
  }, [initialConvId]);

  function switchMode(next: AppMode) {
    if (next === mode) return;
    if (onModeChange) {
      onModeChange(next);
    } else {
      setInternalMode(next);
    }
    setMessages([{ id: "welcome", role: "assistant", content: WELCOME[next] }]);
    setInput("");
    setErrorInput("");
    setLastGenerated("");
    setLastFixed("");
  }

  async function sendMessage() {
    if (loading) return;

    if (mode === "debug") {
      if (!code.trim()) return;
      await runDebug();
      return;
    }

    const trimmed = input.trim();
    if (!trimmed) return;

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: trimmed,
    };

    const assistantId = crypto.randomUUID();
    const assistantStartTime = Date.now();
    const nextMessages = [...messages, userMsg];
    setMessages([
      ...nextMessages,
      {
        id: assistantId,
        role: "assistant",
        content: "",
        startTime: assistantStartTime,
        mode,
        codeSnippet: code.trim() || undefined,
      },
    ]);
    setInput("");
    setLoading(true);
    abortRef.current = new AbortController();

    // Auto-create or resume conversation in SQLite
    let currentConvId = activeConvId;
    if (!currentConvId) {
      currentConvId = crypto.randomUUID();
      setActiveConvId(currentConvId);
      createConversation(trimmed.slice(0, 40), mode, currentConvId).catch(console.error);
    }
    saveMessage(currentConvId, "user", trimmed, undefined, userMsg.id).catch(console.error);

    let fullAssistantResponse = "";

    try {
      if (mode === "chat") {
        const apiMessages: ChatMessage[] = nextMessages.map((m) => ({
          role: m.role,
          content: m.content,
        }));

        if (code.trim()) {
          apiMessages[apiMessages.length - 1].content +=
            `\n\nCode context:\n\`\`\`\n${code}\n\`\`\``;
        }

        await streamChat(
          apiMessages,
          (token) => {
            fullAssistantResponse += token;
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? { ...m, content: m.content + token }
                  : m
              )
            );
          },
          abortRef.current.signal
        );

        if (fullAssistantResponse.trim()) {
          saveMessage(currentConvId, "assistant", fullAssistantResponse, undefined, assistantId).catch(console.error);
        }
      } else {
        let full = "";
        await streamCodegen(
          { prompt: trimmed, language, include_explanation: true },
          (token) => {
            full += token;
            fullAssistantResponse = full;
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId ? { ...m, content: full } : m
              )
            );
          },
          abortRef.current.signal
        );

        const extracted = extractCodeBlock(full);
        setLastGenerated(extracted);
        if (extracted) setCode(extracted);

        if (full.trim()) {
          saveMessage(currentConvId, "assistant", full, undefined, assistantId).catch(console.error);
        }
      }
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Something went wrong.";
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId ? { ...m, content: `Error: ${message}` } : m
        )
      );
    } finally {
      const finishTime = Date.now();
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId ? { ...m, endTime: finishTime } : m
        )
      );
      setLoading(false);
      abortRef.current = null;
    }
  }

  async function runDebug() {
    const userContent = errorInput.trim()
      ? `Debug this code (error provided):\n\`\`\`\n${errorInput}\n\`\`\``
      : "Debug the code in the editor.";

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: userContent,
    };

    const assistantId = crypto.randomUUID();
    const assistantStartTime = Date.now();
    setMessages((prev) => [
      ...prev,
      userMsg,
      {
        id: assistantId,
        role: "assistant",
        content: "",
        startTime: assistantStartTime,
        mode: "debug",
        codeSnippet: code.trim() || undefined,
      },
    ]);
    setLoading(true);
    abortRef.current = new AbortController();

    // Auto-create or resume conversation in SQLite
    let currentConvId = activeConvId;
    if (!currentConvId) {
      currentConvId = crypto.randomUUID();
      setActiveConvId(currentConvId);
      createConversation("Debug Session", "debug", currentConvId).catch(console.error);
    }
    saveMessage(currentConvId, "user", userContent, undefined, userMsg.id).catch(console.error);

    try {
      let full = "";
      await streamDebug(
        {
          code,
          error_message: errorInput.trim() || undefined,
          language,
        },
        (token) => {
          full += token;
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, content: full } : m
            )
          );
        },
        abortRef.current.signal
      );

      const fixed = extractCodeBlock(full);
      setLastFixed(fixed);

      if (full.trim()) {
        saveMessage(currentConvId, "assistant", full, undefined, assistantId).catch(console.error);
      }
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Something went wrong.";
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId ? { ...m, content: `Error: ${message}` } : m
        )
      );
    } finally {
      const finishTime = Date.now();
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId ? { ...m, endTime: finishTime } : m
        )
      );
      setLoading(false);
      abortRef.current = null;
    }
  }

  function stopGeneration() {
    abortRef.current?.abort();
    setLoading(false);
  }

  function insertIntoEditor() {
    if (lastGenerated) setCode(lastGenerated);
  }

  function applyFix() {
    if (lastFixed) setCode(lastFixed);
  }

  const showLanguageSelect = mode === "generate" || mode === "debug";

  return (
    <div className="layout">
      {/* Left Chat / Assistant Pane */}
      <section className="chat-section">
        <div className="mode-bar">
          <div className="mode-tabs">
            <button
              type="button"
              className={`mode-tab ${mode === "chat" ? "active" : ""}`}
              onClick={() => switchMode("chat")}
            >
              <span className="mode-icon">💬</span> Chat
            </button>
            <button
              type="button"
              className={`mode-tab ${mode === "generate" ? "active" : ""}`}
              onClick={() => switchMode("generate")}
            >
              <span className="mode-icon">⚡</span> Generate
            </button>
            <button
              type="button"
              className={`mode-tab ${mode === "debug" ? "active" : ""}`}
              onClick={() => switchMode("debug")}
            >
              <span className="mode-icon">🐞</span> Debug
            </button>
          </div>
          {showLanguageSelect && (
            <label className="language-select">
              <span className="lang-label">RUNTIME</span>
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value as CodeLanguage)}
                disabled={loading}
              >
                {LANGUAGE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>

        <div className="messages">
          {messages.map((m) => {
            const isCurrentlyGenerating = loading && m.id === messages[messages.length - 1]?.id;
            const { thought, answer } = extractThoughtAndAnswer(m.content);
            const showTimeline =
              m.role === "assistant" &&
              m.id !== "welcome" &&
              (isCurrentlyGenerating || m.startTime !== undefined || !!thought);

            return (
              <article key={m.id} className={`message ${m.role}`}>
                <div className="message-label">
                  <span className="msg-tag">
                    {m.role === "user" ? "user@host:~$" : "codehaven@ai:~$"}
                  </span>
                  <span className="msg-role">{m.role === "user" ? "You" : "CodeHaven Assistant"}</span>
                </div>

                {showTimeline && (
                  <AgentProcessTimeline
                    isLive={isCurrentlyGenerating}
                    startTime={m.startTime || Date.now() - 2000}
                    endTime={m.endTime}
                    mode={m.mode || mode}
                    codeSnippet={m.codeSnippet}
                    thoughtText={thought}
                    tokenCount={answer ? answer.split(/\s+/).filter(Boolean).length : 0}
                  />
                )}

                <div className="message-body">
                  {answer || (isCurrentlyGenerating ? "Generating response..." : (m.content ? m.content : "..."))}
                </div>
              </article>
            );
          })}
        </div>

        <div className="composer">
          {mode === "debug" && (
            <textarea
              className="error-input"
              value={errorInput}
              onChange={(e) => setErrorInput(e.target.value)}
              placeholder="Paste stack trace or error message here (optional)..."
              rows={3}
              disabled={loading}
            />
          )}
          {mode !== "debug" && (
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={
                mode === "chat"
                  ? "Ask anything about your code, algorithms, or computer science concepts..."
                  : "Describe what code to generate (e.g. LRU Cache implementation with tests)..."
              }
              rows={3}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  sendMessage();
                }
              }}
            />
          )}
          <div className="composer-actions">
            {mode === "generate" && lastGenerated && !loading && (
              <button
                type="button"
                className="secondary"
                onClick={insertIntoEditor}
              >
                ⬇ Insert into editor
              </button>
            )}
            {mode === "debug" && lastFixed && !loading && (
              <button type="button" className="secondary" onClick={applyFix}>
                ✓ Apply fix
              </button>
            )}
            {loading ? (
              <button type="button" className="secondary stop-btn" onClick={stopGeneration}>
                ⏹ Stop
              </button>
            ) : (
              <button
                type="button"
                className="primary-btn"
                onClick={sendMessage}
                disabled={mode === "debug" ? !code.trim() : !input.trim()}
              >
                {mode === "chat" ? "Send ↵" : mode === "generate" ? "⚡ Generate Code" : "🐞 Analyze & Fix"}
              </button>
            )}
          </div>
        </div>
      </section>

      {/* Right Monaco Editor + Integrated Terminal Runner */}
      <section className="editor-section">
        <div className="panel-header editor-header">
          <div className="panel-header-left">
            <span className="terminal-prompt-symbol">λ</span>
            <strong>MONACO CODE WORKBENCH</strong>
          </div>
          <div className="panel-header-right">
            <span className="lang-pill">{monacoLanguage.toUpperCase()}</span>
          </div>
        </div>

        {/* Monaco Editor Pane */}
        <div className="editor-container">
          <Editor
            height="100%"
            language={monacoLanguage}
            theme="vs-dark"
            value={code}
            onChange={(v) => setCode(v ?? "")}
            options={{
              minimap: { enabled: false },
              fontSize: 13.5,
              fontFamily: "'JetBrains Mono', 'Fira Code', Consolas, monospace",
              fontLigatures: true,
              wordWrap: "on",
              scrollBeyondLastLine: false,
              automaticLayout: true,
              lineNumbersMinChars: 3,
              padding: { top: 12, bottom: 12 },
              renderLineHighlight: "all",
              scrollbar: {
                verticalScrollbarSize: 8,
                horizontalScrollbarSize: 8,
              },
              overviewRulerBorder: false,
            }}
          />
        </div>

        {/* Integrated Terminal Runner Pane */}
        <TerminalRunner
          code={code}
          language={monacoLanguage}
          onLanguageChange={(lang) => setLanguage(lang as any)}
        />
      </section>
    </div>
  );
}
