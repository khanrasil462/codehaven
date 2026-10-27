import { useEffect, useRef, useState } from "react";
import {
  createConversation,
  fetchConversation,
  saveMessage,
  streamChat,
  type ChatMessage,
} from "../api/client";
import { Markdown, type CodeBlockInfo } from "../lib/markdown";
import { RunPanel, isRunnable, type RunRequest } from "./RunPanel";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  startTime?: number;
  endTime?: number;
}

const SUGGESTIONS = [
  "Write a hello world in Python",
  "Build a simple landing page website",
  "Explain recursion with an example",
  "Write a C program that reverses a string",
];

export interface ChatPanelProps {
  initialConvId?: string | null;
  onConversationChange?: () => void;
}

function CodeBlock({
  info,
  streaming,
  onRun,
}: {
  info: CodeBlockInfo;
  streaming: boolean;
  onRun: (info: CodeBlockInfo) => void;
}) {
  const [copied, setCopied] = useState(false);
  const writing = streaming && !info.complete;

  async function copy() {
    try {
      await navigator.clipboard.writeText(info.code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable */
    }
  }

  return (
    <div className="code-block">
      <div className="code-block-head">
        <span className="code-lang">{info.lang || "text"}</span>
        <div className="code-block-actions">
          {writing ? (
            <span className="muted">writing…</span>
          ) : (
            <>
              <button type="button" className="ghost" onClick={copy}>
                {copied ? "Copied" : "Copy"}
              </button>
              {isRunnable(info.lang, info.code) && (
                <button type="button" className="ghost accent" onClick={() => onRun(info)}>
                  Run
                </button>
              )}
            </>
          )}
        </div>
      </div>
      <pre>
        <code>{info.code}</code>
      </pre>
    </div>
  );
}

export function ChatPanel({ initialConvId, onConversationChange }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [convId, setConvId] = useState<string | null>(initialConvId ?? null);
  const [run, setRun] = useState<RunRequest | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    if (!initialConvId) return;
    setConvId(initialConvId);
    fetchConversation(initialConvId)
      .then((conv) =>
        setMessages(
          conv.messages.map((m) => ({ id: m.id, role: m.role as "user" | "assistant", content: m.content })),
        ),
      )
      .catch(console.error);
  }, [initialConvId]);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [input]);

  async function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed || loading) return;

    const userMsg: Message = { id: crypto.randomUUID(), role: "user", content: trimmed };
    const assistantId = crypto.randomUUID();
    const history = [...messages, userMsg];
    setMessages([...history, { id: assistantId, role: "assistant", content: "", startTime: Date.now() }]);
    setInput("");
    setLoading(true);
    abortRef.current = new AbortController();

    let id = convId;
    if (!id) {
      id = crypto.randomUUID();
      setConvId(id);
      createConversation(trimmed.slice(0, 48), "chat", id)
        .then(() => onConversationChange?.())
        .catch(console.error);
    }
    saveMessage(id, "user", trimmed, undefined, userMsg.id).catch(console.error);

    let full = "";
    try {
      const apiMessages: ChatMessage[] = history.map((m) => ({ role: m.role, content: m.content }));
      await streamChat(
        apiMessages,
        (token) => {
          full += token;
          setMessages((prev) => prev.map((m) => (m.id === assistantId ? { ...m, content: full } : m)));
        },
        abortRef.current.signal,
      );
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        full = full || `Something went wrong: ${err instanceof Error ? err.message : "unknown error"}`;
        setMessages((prev) => prev.map((m) => (m.id === assistantId ? { ...m, content: full } : m)));
      }
    } finally {
      setMessages((prev) => prev.map((m) => (m.id === assistantId ? { ...m, endTime: Date.now() } : m)));
      if (full.trim()) saveMessage(id, "assistant", full, undefined, assistantId).catch(console.error);
      setLoading(false);
      abortRef.current = null;
      inputRef.current?.focus();
    }
  }

  function openRun(info: CodeBlockInfo) {
    setRun({ id: crypto.randomUUID(), code: info.code, lang: info.lang });
  }

  function fixWithAi(code: string, error: string) {
    void send(`This code failed to run. Please fix it.\n\n\`\`\`\n${code}\n\`\`\`\n\nError:\n\`\`\`\n${error.slice(0, 1500)}\n\`\`\``);
  }

  return (
    <div className={`chat-shell ${run ? "with-run" : ""}`}>
      <section className="chat-main">
        <div className="chat-scroll" ref={scrollRef}>
          {messages.length === 0 ? (
            <div className="empty">
              <h1>What are we building?</h1>
              <p className="muted">Runs entirely on this machine. Ask anything, or have it write code and run it.</p>
              <div className="suggestions">
                {SUGGESTIONS.map((s) => (
                  <button key={s} type="button" className="suggestion" onClick={() => void send(s)}>
                    {s}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="thread">
              {messages.map((m, idx) => {
                const live = loading && idx === messages.length - 1;
                if (m.role === "user") {
                  return (
                    <div key={m.id} className="msg user">
                      <div className="bubble">{m.content}</div>
                    </div>
                  );
                }
                const seconds = m.endTime && m.startTime ? (m.endTime - m.startTime) / 1000 : 0;
                const rate = seconds > 0 ? Math.round(m.content.length / 4 / seconds) : 0;
                return (
                  <div key={m.id} className="msg assistant">
                    <div className="avatar">CH</div>
                    <div className="body">
                      {m.content ? (
                        <Markdown
                          text={m.content}
                          renderCode={(info, i) => <CodeBlock key={i} info={info} streaming={live} onRun={openRun} />}
                        />
                      ) : (
                        <span className="typing">
                          <i />
                          <i />
                          <i />
                        </span>
                      )}
                      {seconds > 0 && (
                        <div className="msg-meta muted">
                          {seconds.toFixed(1)}s{rate > 0 ? ` · ~${rate} tok/s` : ""}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="composer-wrap">
          <div className="composer-box">
            <span className="composer-prompt">$</span>
            <textarea
              ref={inputRef}
              value={input}
              rows={1}
              placeholder="Message CodeHaven…"
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void send(input);
                }
              }}
            />
            {loading ? (
              <button type="button" className="send stop" onClick={() => abortRef.current?.abort()}>
                Stop
              </button>
            ) : (
              <button type="button" className="send" disabled={!input.trim()} onClick={() => void send(input)}>
                Send
              </button>
            )}
          </div>
          <div className="composer-hint muted">Enter to send · Shift+Enter for a new line · Ctrl+K for commands</div>
        </div>
      </section>

      {run && <RunPanel request={run} onClose={() => setRun(null)} onFix={fixWithAi} />}
    </div>
  );
}
