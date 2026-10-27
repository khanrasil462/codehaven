import { useCallback, useEffect, useRef, useState } from "react";
import { executeCode, type ExecuteResponse } from "../api/client";

export interface RunRequest {
  id: string;
  code: string;
  lang: string;
}

const RUNNER_LANG: Record<string, string> = {
  python: "python", javascript: "javascript", typescript: "typescript", bash: "bash",
  c: "c", cpp: "cpp", java: "java", powershell: "powershell",
};
const FILE_NAME: Record<string, string> = {
  python: "main.py", javascript: "main.js", typescript: "main.ts", bash: "script.sh",
  c: "main.c", cpp: "main.cpp", java: "Main.java", powershell: "script.ps1", html: "index.html",
};

export function isRunnable(lang: string, code = ""): boolean {
  return lang in RUNNER_LANG || isHtml(lang, code);
}

export function isHtml(lang: string, code = ""): boolean {
  return lang === "html" || /^\s*<!doctype html|^\s*<html/i.test(code);
}

interface Props {
  request: RunRequest;
  onClose: () => void;
  onFix: (code: string, error: string) => void;
}

export function RunPanel({ request, onClose, onFix }: Props) {
  const html = isHtml(request.lang, request.code);
  const lang = html ? "html" : request.lang;
  const [code, setCode] = useState(request.code);
  const [tab, setTab] = useState<"output" | "code">("output");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<ExecuteResponse | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [stdin, setStdin] = useState("");
  const [previewKey, setPreviewKey] = useState(0);
  const endRef = useRef<HTMLDivElement | null>(null);

  const run = useCallback(
    async (source: string) => {
      if (html) {
        setPreviewKey((k) => k + 1);
        return;
      }
      setRunning(true);
      setFailure(null);
      setResult(null);
      try {
        setResult(
          await executeCode({ code: source, language: RUNNER_LANG[lang] ?? lang, stdin, timeout_seconds: 15 }),
        );
      } catch (err) {
        setFailure(err instanceof Error ? err.message : "Execution failed");
      } finally {
        setRunning(false);
      }
    },
    [html, lang, stdin],
  );

  useEffect(() => {
    setCode(request.code);
    setTab("output");
    void run(request.code);
    // run once per new request
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [request.id]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [result, failure]);

  const error = failure ?? (result && result.exit_code !== 0 ? result.stderr || "Process failed" : null);

  return (
    <aside className="run-panel">
      <div className="run-head">
        <div className="run-tabs">
          <button type="button" className={tab === "output" ? "active" : ""} onClick={() => setTab("output")}>
            {html ? "Preview" : "Terminal"}
          </button>
          <button type="button" className={tab === "code" ? "active" : ""} onClick={() => setTab("code")}>
            {FILE_NAME[lang] ?? "code"}
          </button>
        </div>
        <div className="run-actions">
          <button type="button" className="ghost" onClick={() => void run(code)} disabled={running}>
            {running ? "Running…" : html ? "Reload" : "Run again"}
          </button>
          <button type="button" className="ghost" onClick={onClose} aria-label="Close">
            Close
          </button>
        </div>
      </div>

      {tab === "code" ? (
        <textarea
          className="run-editor"
          spellCheck={false}
          value={code}
          onChange={(e) => setCode(e.target.value)}
          onKeyDown={(e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
              e.preventDefault();
              setTab("output");
              void run(code);
            }
          }}
        />
      ) : html ? (
        <iframe
          key={previewKey}
          className="run-preview"
          title="Preview"
          sandbox="allow-scripts allow-forms allow-modals allow-popups"
          srcDoc={code}
        />
      ) : (
        <div className="run-term">
          <div className="term-line dim">
            <span className="term-prompt">$</span> {RUNNER_LANG[lang] === "bash" ? "bash" : lang} {FILE_NAME[lang]}
          </div>
          {running && <div className="term-line dim">running…</div>}
          {result?.stdout && <pre className="term-out">{result.stdout}</pre>}
          {(result?.stderr || failure) && <pre className="term-err">{failure ?? result?.stderr}</pre>}
          {result && (
            <div className={`term-line ${result.exit_code === 0 ? "ok" : "bad"}`}>
              {result.exit_code === 0 ? "exited 0" : `exited ${result.exit_code}`} · {Math.round(result.execution_time_ms)} ms
            </div>
          )}
          <div ref={endRef} />
        </div>
      )}

      {tab === "output" && !html && (
        <div className="run-foot">
          <input
            value={stdin}
            onChange={(e) => setStdin(e.target.value)}
            placeholder="stdin (optional), then Run again"
            spellCheck={false}
          />
          {error && (
            <button type="button" className="ghost accent" onClick={() => onFix(code, error)}>
              Fix with AI
            </button>
          )}
        </div>
      )}
    </aside>
  );
}
