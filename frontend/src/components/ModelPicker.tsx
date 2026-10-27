import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchModels,
  fetchSpeedStatus,
  pullModels,
  selectModel,
  setSpeedMode,
  type ModelsStatus,
  type SpeedStatusResponse,
} from "../api/client";

function gb(bytes: number) {
  return (bytes / 1e9).toFixed(1);
}

/** Top-bar dropdown: Fast/Deep mode plus an explicit model choice. */
export function ModelPicker() {
  const [open, setOpen] = useState(false);
  const [models, setModels] = useState<ModelsStatus | null>(null);
  const [speed, setSpeed] = useState<SpeedStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const ref = useRef<HTMLDivElement | null>(null);

  const refresh = useCallback(async () => {
    const [m, s] = await Promise.all([fetchModels().catch(() => null), fetchSpeedStatus().catch(() => null)]);
    if (m) setModels(m);
    if (s) setSpeed(s);
  }, []);

  const busy = models?.models.some((m) => m.state === "pulling" || m.state === "queued") ?? false;

  useEffect(() => {
    void refresh();
    const id = setInterval(refresh, open || busy ? 1500 : 8000);
    return () => clearInterval(id);
  }, [refresh, open, busy]);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);

  const chat = models?.models.filter((m) => !m.name.includes("embed")) ?? [];
  const deep = chat.find((m) => m.name.endsWith(":7b"));
  const active = speed?.selected_model ?? speed?.effective_model ?? "…";
  const modeLabel = speed?.selected_model
    ? speed.selected_model.endsWith(":1.5b")
      ? "Fast"
      : speed.selected_model.endsWith(":7b")
        ? "Deep"
        : "Custom"
    : speed?.active_mode === "balanced"
      ? "Deep"
      : "Fast";

  async function run(action: () => Promise<unknown>) {
    setError(null);
    try {
      await action();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    }
    await refresh();
  }

  function chooseMode(mode: "turbo" | "balanced") {
    if (mode === "balanced" && deep?.state !== "ready") {
      void run(() => pullModels(deep?.name));
      return;
    }
    void run(() => setSpeedMode(mode));
  }

  return (
    <div className="picker" ref={ref}>
      <button type="button" className="picker-btn" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        <span className={`dot ${models?.ready ? "ok" : "warn"}`} />
        <span className="picker-name">{active}</span>
        <span className="picker-mode">{modeLabel}</span>
        <span className="picker-caret">▾</span>
      </button>

      {open && (
        <div className="picker-menu">
          <div className="picker-section">Mode</div>
          <div className="speed">
            <button
              type="button"
              className={modeLabel === "Fast" ? "active" : ""}
              onClick={() => chooseMode("turbo")}
            >
              Fast
              <small>1.5B · quick answers</small>
            </button>
            <button
              type="button"
              className={modeLabel === "Deep" ? "active" : ""}
              onClick={() => chooseMode("balanced")}
            >
              Deep{deep?.state === "ready" ? "" : " ↓"}
              <small>7B · better quality</small>
            </button>
          </div>

          <div className="picker-section">Models</div>
          <div className="picker-list">
            {chat.map((m) => {
              const pct = m.total ? Math.round((m.completed / m.total) * 100) : 0;
              const selected = active === m.name;
              return (
                <div key={m.name} className={`picker-item ${selected ? "selected" : ""}`}>
                  <button
                    type="button"
                    className="picker-item-main"
                    disabled={m.state !== "ready"}
                    onClick={() => void run(async () => { await selectModel(m.name); setOpen(false); })}
                  >
                    <span className="picker-check">{selected ? "✓" : ""}</span>
                    <span className="picker-item-text">
                      <span className="mono">{m.name}</span>
                      <small className="muted">{m.role}</small>
                    </span>
                  </button>
                  {m.state === "missing" && (
                    <button type="button" className="ghost accent" onClick={() => void run(() => pullModels(m.name))}>
                      Download
                    </button>
                  )}
                  {(m.state === "pulling" || m.state === "queued") && (
                    <span className="muted picker-pct">
                      {m.state === "queued" ? "queued" : `${pct}% · ${gb(m.completed)}/${gb(m.total)}G`}
                    </span>
                  )}
                  {m.state === "error" && (
                    <button type="button" className="ghost" onClick={() => void run(() => pullModels(m.name))}>
                      Retry
                    </button>
                  )}
                </div>
              );
            })}
          </div>
          {error && <p className="error-text picker-error">{error}</p>}
        </div>
      )}
    </div>
  );
}
