import { useState, useRef, useEffect } from "react";
import { executeCode, type ExecuteResponse } from "../api/client";

interface TerminalRunnerProps {
  code: string;
  language: string;
  onLanguageChange?: (lang: string) => void;
}

export function TerminalRunner({ code, language, onLanguageChange }: TerminalRunnerProps) {
  const [running, setRunning] = useState(false);
  const [output, setOutput] = useState<string>("");
  const [errorOutput, setErrorOutput] = useState<string>("");
  const [lastResponse, setLastResponse] = useState<ExecuteResponse | null>(null);
  const [stdinInput, setStdinInput] = useState<string>("");
  const [showStdin, setShowStdin] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [copied, setCopied] = useState(false);
  const terminalEndRef = useRef<HTMLDivElement | null>(null);

  // Normalize language for backend
  const normalizedLang =
    language === "react" ? "javascript" : language.toLowerCase();

  async function handleRun() {
    if (running) return;
    setRunning(true);
    setErrorOutput("");

    try {
      const res = await executeCode({
        code,
        language: normalizedLang,
        stdin: stdinInput,
        timeout_seconds: 10.0,
      });

      setLastResponse(res);
      setOutput(res.stdout);
      setErrorOutput(res.stderr);
    } catch (err) {
      setErrorOutput(err instanceof Error ? err.message : "Execution failed.");
      setLastResponse(null);
    } finally {
      setRunning(false);
    }
  }

  // Auto-scroll terminal output
  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [output, errorOutput]);

  // Global shortcut: Ctrl+Enter or Cmd+Enter to run code
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        e.preventDefault();
        handleRun();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [code, normalizedLang, stdinInput]);

  function handleClear() {
    setOutput("");
    setErrorOutput("");
    setLastResponse(null);
  }

  function handleCopy() {
    const fullText = [
      output ? `STDOUT:\n${output}` : "",
      errorOutput ? `STDERR:\n${errorOutput}` : "",
    ]
      .filter(Boolean)
      .join("\n\n");

    if (fullText) {
      navigator.clipboard.writeText(fullText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }

  return (
    <div className={`terminal-runner ${isCollapsed ? "collapsed" : ""}`}>
      {/* Terminal Title Bar */}
      <div className="terminal-header">
        <div className="terminal-header-left">
          <div className="window-dots">
            <span className="dot dot-red" />
            <span className="dot dot-yellow" />
            <span className="dot dot-green" />
          </div>
          <span className="terminal-title">
            <span className="terminal-prompt-symbol">❯_</span> TERMINAL RUNNER
          </span>
          {onLanguageChange ? (
            <select
              className="terminal-lang-select"
              value={normalizedLang}
              onChange={(e) => onLanguageChange(e.target.value)}
              title="Select compiler / interpreter runtime"
            >
              <option value="python">PYTHON 3</option>
              <option value="javascript">NODE.JS</option>
              <option value="typescript">TYPESCRIPT</option>
              <option value="java">JAVA</option>
              <option value="powershell">POWERSHELL</option>
              <option value="c">C / C++</option>
            </select>
          ) : (
            <span className="terminal-badge-lang">{normalizedLang}</span>
          )}
        </div>

        <div className="terminal-header-center">
          {lastResponse && (
            <span
              className={`exec-status-pill ${
                lastResponse.status === "success"
                  ? "pill-success"
                  : lastResponse.status === "timeout"
                  ? "pill-warning"
                  : "pill-error"
              }`}
            >
              {lastResponse.status === "success"
                ? `● EXIT: ${lastResponse.exit_code} (${lastResponse.execution_time_ms}ms)`
                : lastResponse.status === "timeout"
                ? `● TIMED OUT (${lastResponse.execution_time_ms}ms)`
                : `● FAILED (CODE ${lastResponse.exit_code})`}
            </span>
          )}
          {running && (
            <span className="exec-status-pill pill-running">
              <span className="spinner" /> EXECUTING...
            </span>
          )}
        </div>

        <div className="terminal-header-actions">
          {/* Stdin Toggle */}
          <button
            type="button"
            className={`terminal-action-btn ${showStdin ? "active" : ""}`}
            onClick={() => setShowStdin(!showStdin)}
            title="Toggle Standard Input (stdin)"
          >
            ⌨ Stdin
          </button>

          {/* Copy Button */}
          <button
            type="button"
            className="terminal-action-btn"
            onClick={handleCopy}
            disabled={!output && !errorOutput}
            title="Copy terminal output"
          >
            {copied ? "✓ Copied" : "📋 Copy"}
          </button>

          {/* Clear Button */}
          <button
            type="button"
            className="terminal-action-btn"
            onClick={handleClear}
            disabled={!output && !errorOutput && !lastResponse}
            title="Clear terminal"
          >
            ✕ Clear
          </button>

          {/* Run Button */}
          <button
            type="button"
            className={`terminal-run-btn ${running ? "running" : ""}`}
            onClick={handleRun}
            disabled={running || !code.trim()}
            title="Execute code in editor (Ctrl+Enter)"
          >
            {running ? "⏳ Running..." : "▶ Run Code [Ctrl+↵]"}
          </button>

          {/* Collapse/Expand Toggle */}
          <button
            type="button"
            className="terminal-action-btn collapse-toggle"
            onClick={() => setIsCollapsed(!isCollapsed)}
            title={isCollapsed ? "Expand Terminal" : "Collapse Terminal"}
          >
            {isCollapsed ? "▲ Expand" : "▼"}
          </button>
        </div>
      </div>

      {/* Optional Stdin Drawer */}
      {showStdin && !isCollapsed && (
        <div className="terminal-stdin-bar">
          <span className="stdin-label">$ stdin:</span>
          <input
            type="text"
            value={stdinInput}
            onChange={(e) => setStdinInput(e.target.value)}
            placeholder="Type input text passed to program (for input() / readline())..."
            className="stdin-input"
          />
          {stdinInput && (
            <button
              type="button"
              className="stdin-clear"
              onClick={() => setStdinInput("")}
            >
              ✕
            </button>
          )}
        </div>
      )}

      {/* Terminal Output Screen */}
      {!isCollapsed && (
        <div className="terminal-body">
          {!output && !errorOutput && !running && (
            <div className="terminal-placeholder">
              <span className="prompt-dim">$ codehaven runner --ready</span>
              <p>No execution output yet. Click <strong>Run Code</strong> or press <code>Ctrl + Enter</code> to compile & run.</p>
              <div className="terminal-quick-tips">
                <span>⚡ Supports: Python 3, Node.js (JS/TS), Java 21, PowerShell</span>
                <span>⏱ 10s execution timeout with safe sandbox capture</span>
              </div>
            </div>
          )}

          {/* Execution Command Echo */}
          {(output || errorOutput || running) && (
            <div className="terminal-cmd-echo">
              <span className="terminal-host">codehaven@local:~$</span>
              <span className="terminal-cmd">run {normalizedLang} script</span>
              {running && <span className="terminal-cursor">█</span>}
            </div>
          )}

          {/* Standard Output */}
          {output && (
            <pre className="terminal-stdout">
              <code>{output}</code>
            </pre>
          )}

          {/* Standard Error */}
          {errorOutput && (
            <pre className="terminal-stderr">
              <span className="stderr-header">--- RUNTIME ERROR / DIAGNOSTICS ---</span>
              <code>{errorOutput}</code>
            </pre>
          )}

          <div ref={terminalEndRef} />
        </div>
      )}
    </div>
  );
}
