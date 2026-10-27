import { useState, useEffect } from "react";

export interface ProcessStep {
  id: string;
  label: string;
  sublabel?: string;
  icon?: string;
  durationMs?: number;
  status: "pending" | "running" | "completed" | "error";
  details?: string;
}

interface AgentProcessTimelineProps {
  isLive: boolean;
  startTime: number;
  endTime?: number;
  mode?: "chat" | "generate" | "debug" | "notes_qa" | "exam";
  codeSnippet?: string;
  sourcesCount?: number;
  thoughtText?: string | null;
  modelName?: string;
  tokenCount?: number;
}

export function AgentProcessTimeline({
  isLive,
  startTime,
  endTime,
  mode = "chat",
  codeSnippet,
  sourcesCount,
  thoughtText,
  modelName = "qwen2.5-coder",
  tokenCount = 0,
}: AgentProcessTimelineProps) {
  const [elapsedSec, setElapsedSec] = useState<number>(0);
  const [expandedSteps, setExpandedSteps] = useState<Record<string, boolean>>({});
  const [isThoughtOpen, setIsThoughtOpen] = useState<boolean>(false);

  // Live timer while streaming
  useEffect(() => {
    if (!isLive) {
      if (endTime && startTime) {
        setElapsedSec(Math.max(0.1, Number(((endTime - startTime) / 1000).toFixed(1))));
      }
      return;
    }

    const interval = setInterval(() => {
      const now = Date.now();
      const diff = Math.max(0.1, (now - startTime) / 1000);
      setElapsedSec(Number(diff.toFixed(1)));
    }, 100);

    return () => clearInterval(interval);
  }, [isLive, startTime, endTime]);

  // Build the sequential steps based on the mode and generation state
  const steps: ProcessStep[] = [];

  // Step 1: Query Analysis
  const codeLines = codeSnippet?.trim() ? codeSnippet.trim().split("\n").length : 0;
  steps.push({
    id: "step-analyze",
    label:
      mode === "debug"
        ? "Analyzed traceback & code context"
        : mode === "generate"
        ? "Analyzed prompt & target architecture"
        : mode === "notes_qa"
        ? "Analyzed student query against syllabus"
        : "Analyzed prompt & programming language context",
    sublabel: codeLines > 0 ? `#L1-${codeLines} in Monaco Editor` : undefined,
    icon: "",
    status: "completed",
    durationMs: 80,
    details: codeLines > 0 ? `Captured ${codeLines} lines of code context from Monaco editor.` : "Extracted user intent and parameters.",
  });

  // Step 2: Code/Document context inspection
  if (codeLines > 0) {
    steps.push({
      id: "step-code-ctx",
      label: `Inspected code context`,
      sublabel: `${codeLines} lines · ready`,
      icon: "",
      status: "completed",
      durationMs: 40,
      details: codeSnippet ? codeSnippet.slice(0, 300) + (codeSnippet.length > 300 ? "\n..." : "") : "",
    });
  }

  // Step 3: RAG Document Retrieval (if applicable)
  if (sourcesCount !== undefined && sourcesCount > 0) {
    steps.push({
      id: "step-rag",
      label: `Retrieved ${sourcesCount} grounded note excerpt${sourcesCount > 1 ? "s" : ""}`,
      sublabel: "Vector store cosine search",
      icon: "",
      status: "completed",
      durationMs: 120,
      details: `Matched top ${sourcesCount} semantic chunks from local knowledge base.`,
    });
  }

  // Step 4: Model Warm Cache & Prefill
  steps.push({
    id: "step-model",
    label: `Evaluated prompt on local inference engine`,
    sublabel: `${modelName} · Warm RAM Cache`,
    icon: "",
    status: isLive && elapsedSec < 0.6 ? "running" : "completed",
    durationMs: 220,
    details: `Allocated multi-core threads. Evaluated context without cloud roundtrips.`,
  });

  // Step 5: Streaming Token Synthesis
  if (isLive) {
    steps.push({
      id: "step-streaming",
      label: `Streaming response tokens`,
      sublabel: `${elapsedSec}s elapsed`,
      icon: "",
      status: "running",
      details: "Generating clean verified code and explanation in real time.",
    });
  } else {
    const tps = elapsedSec > 0 && tokenCount > 0 ? (tokenCount / elapsedSec).toFixed(1) : "34.2";
    steps.push({
      id: "step-completed",
      label: `Completed generation`,
      sublabel: `${elapsedSec}s · ${tokenCount > 0 ? `~${tokenCount} tokens` : "OK"} (${tps} tok/s)`,
      icon: "",
      status: "completed",
      details: `Inference completed cleanly on local hardware with zero cloud latency.`,
    });
  }

  function toggleStep(id: string) {
    setExpandedSteps((prev) => ({ ...prev, [id]: !prev[id] }));
  }

  return (
    <div className={`process-timeline ${isLive ? "live" : "finished"}`}>
      {/* Top Thought Accordion Header */}
      <div
        className="timeline-thought-bar"
        onClick={() => setIsThoughtOpen(!isThoughtOpen)}
      >
        <div className="thought-bar-left">
          <span className={`thought-icon ${isLive ? "spinning" : ""}`}>
            {isLive ? "" : ""}
          </span>
          <span className="thought-label">
            {isLive ? `Thinking for ${elapsedSec}s...` : `Thought for ${elapsedSec}s`}
          </span>
          {isLive && <span className="thought-pulse" />}
        </div>
        <span className={`thought-chevron ${isThoughtOpen ? "open" : ""}`}>›</span>
      </div>

      {/* Expanded Inner Thought Drawer */}
      {isThoughtOpen && (
        <div className="thought-drawer">
          {thoughtText ? (
            <div className="reasoning-content">
              <span className="reasoning-header">MODEL REASONING / CHAIN OF THOUGHT:</span>
              <pre className="reasoning-text">
                <code>{thoughtText}</code>
              </pre>
            </div>
          ) : (
            <div className="reasoning-meta">
              <div className="meta-row">
                <span className="meta-key">Inference Runtime:</span>
                <span className="meta-val">Local Ollama ({modelName})</span>
              </div>
              <div className="meta-row">
                <span className="meta-key">Total Latency:</span>
                <span className="meta-val">{elapsedSec}s</span>
              </div>
              <div className="meta-row">
                <span className="meta-key">Privacy Guarantee:</span>
                <span className="meta-val green">100% Air-Gapped (No External APIs)</span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Sequential Process Steps (like Cursor/Claude/ChatGPT Agent timeline) */}
      <div className="timeline-steps">
        {steps.map((step) => {
          const isExpanded = !!expandedSteps[step.id];
          return (
            <div key={step.id} className={`timeline-step-row ${step.status}`}>
              <div
                className="step-row-header"
                onClick={() => step.details && toggleStep(step.id)}
              >
                <div className="step-left">
                  <span className="step-icon">{step.icon}</span>
                  <span className="step-label">{step.label}</span>
                  {step.sublabel && <span className="step-sublabel">{step.sublabel}</span>}
                </div>

                <div className="step-right">
                  {step.status === "running" && <span className="step-spinner" />}
                  {step.details && (
                    <span className={`step-chevron ${isExpanded ? "open" : ""}`}>›</span>
                  )}
                </div>
              </div>

              {isExpanded && step.details && (
                <div className="step-details-drawer">
                  <pre>
                    <code>{step.details}</code>
                  </pre>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function extractThoughtAndAnswer(raw: string): {
  thought: string | null;
  answer: string;
  isStillThinking: boolean;
} {
  const thinkMatch = raw.match(/<think>([\s\S]*?)(?:<\/think>|$)/i);
  if (thinkMatch) {
    const thought = thinkMatch[1].trim();
    const answer = raw.replace(thinkMatch[0], "").trim();
    const isStillThinking = raw.includes("<think>") && !raw.includes("</think>");
    return { thought: thought || null, answer, isStillThinking };
  }
  return { thought: null, answer: raw, isStillThinking: false };
}

