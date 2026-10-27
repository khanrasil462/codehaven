import { useEffect, useState } from "react";
import { fetchModels, type ModelsStatus } from "../api/client";

function gb(bytes: number) {
  return (bytes / 1e9).toFixed(1);
}

/** Sidebar footer: model download progress and the Fast/Deep switch. */
export function StatusBar() {
  const [models, setModels] = useState<ModelsStatus | null>(null);

  const downloading = models?.models.some((m) => m.state === "pulling" || m.state === "queued") ?? false;
  const needsSetup = !!models && (!models.ready || downloading);

  useEffect(() => {
    let active = true;
    async function check() {
      const m = await fetchModels().catch(() => null);
      if (!active) return;
      if (m) setModels(m);
    }
    void check();
    const id = setInterval(check, needsSetup ? 1500 : 8000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, [needsSetup]);

  const visible = models?.models.filter((m) => m.state !== "ready" && (!m.optional || m.state !== "missing")) ?? [];

  return (
    <div className="sidebar-status">
      {models && !models.ollama_installed && !models.ollama_running && (
        <p className="muted">Ollama isn't installed. Get it from ollama.com.</p>
      )}

      {visible.length > 0 && (
        <div className="setup">
          <span className="nav-label">Downloading models</span>
          {visible.map((m) => {
            const pct = m.total ? Math.round((m.completed / m.total) * 100) : 0;
            return (
              <div key={m.name} className="setup-row">
                <div className="setup-head">
                  <span>{m.name}</span>
                  <span className="muted">
                    {m.state === "pulling" ? `${pct}%` : m.state === "error" ? "retrying" : "queued"}
                  </span>
                </div>
                <div className="bar">
                  <div className="bar-fill" style={{ width: `${pct}%` }} />
                </div>
                {m.state === "pulling" && (
                  <span className="muted setup-sub">
                    {gb(m.completed)} / {gb(m.total)} GB
                  </span>
                )}
              </div>
            );
          })}
        </div>
      )}

    </div>
  );
}
