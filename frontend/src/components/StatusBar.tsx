import { useEffect, useState } from "react";
import {
  fetchHealth,
  fetchSpeedStatus,
  setSpeedMode,
  type HealthResponse,
  type SpeedStatusResponse,
} from "../api/client";

export function StatusBar() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [speedStatus, setSpeedStatus] = useState<SpeedStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [switchingSpeed, setSwitchingSpeed] = useState(false);

  useEffect(() => {
    let active = true;

    async function check() {
      try {
        const [healthData, speedData] = await Promise.all([
          fetchHealth().catch(() => null),
          fetchSpeedStatus().catch(() => null),
        ]);
        if (active) {
          if (healthData) {
            setHealth(healthData);
            setError(null);
          } else {
            setHealth(null);
            setError("Backend offline");
          }
          if (speedData) {
            setSpeedStatus(speedData);
          }
        }
      } catch {
        if (active) {
          setHealth(null);
          setError("Backend offline");
        }
      }
    }

    check();
    const id = setInterval(check, 8000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  async function handleToggleSpeed() {
    if (switchingSpeed) return;
    const nextMode = speedStatus?.active_mode === "turbo" ? "balanced" : "turbo";
    setSwitchingSpeed(true);
    try {
      await setSpeedMode(nextMode);
      const updated = await fetchSpeedStatus();
      setSpeedStatus(updated);
    } catch {
      // ignore
    } finally {
      setSwitchingSpeed(false);
    }
  }

  const ollamaOk = health?.ollama?.reachable;
  const isTurbo = speedStatus?.active_mode === "turbo";
  const activeModelDisplay = speedStatus?.effective_model || health?.chat_model || "qwen2.5-coder:7b";

  return (
    <header className="status-bar terminal-status-bar">
      <div className="brand">
        <div className="terminal-window-dots">
          <span className="dot dot-red" />
          <span className="dot dot-yellow" />
          <span className="dot dot-green" />
        </div>
        <div className="brand-title-wrap">
          <div className="brand-logo-line">
            <span className="terminal-glyph">λ_</span>
            <strong className="brand-name">CodeHaven</strong>
            <span className="terminal-ver">v0.2.0</span>
          </div>
          <span className="tagline">root@offline-station:~$ zero-cloud local coding studio</span>
        </div>
      </div>

      <div className="status-pills">
        {/* Speed Optimization Toggle Pill */}
        <button
          type="button"
          className={`pill pill-speed ${isTurbo ? "turbo" : "balanced"}`}
          onClick={handleToggleSpeed}
          disabled={switchingSpeed}
          title="Click to toggle between Turbo Mode (blazing fast) and Balanced Mode (deep reasoning)"
        >
          <span className="speed-icon">{isTurbo ? "⚡" : "🧠"}</span>
          <span className="speed-mode-name">{isTurbo ? "TURBO (FAST)" : "BALANCED (DEEP)"}</span>
          <span className="speed-badge">{speedStatus?.speed_estimate || (isTurbo ? "50-80 t/s" : "15 t/s")}</span>
        </button>

        <span className={`pill ${health ? "ok" : "bad"}`}>
          <span className="pulsing-dot" />
          FASTAPI {health ? "ONLINE" : error ?? "OFFLINE"}
        </span>

        <span className={`pill ${ollamaOk ? "ok" : "bad"}`}>
          <span className="pulsing-dot" />
          OLLAMA {ollamaOk ? "READY" : "UNAVAILABLE"}
        </span>

        <span className="pill pill-model" title={`Active model: ${activeModelDisplay}`}>
          🤖 {activeModelDisplay}
        </span>

        <span className="pill pill-offline">
          🛡 100% AIR-GAPPED OFFLINE
        </span>
      </div>
    </header>
  );
}
