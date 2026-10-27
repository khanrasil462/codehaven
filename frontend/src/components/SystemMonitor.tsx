import { useEffect, useState } from "react";
import { fetchModels, fetchSystem, type SystemStats } from "../api/client";

/** tmux/vim-style status line pinned to the bottom of the window. */
export function SystemMonitor() {
  const [s, setS] = useState<SystemStats | null>(null);
  const [ready, setReady] = useState<boolean | null | undefined>(undefined);

  useEffect(() => {
    let active = true;
    const tick = () => {
      fetchSystem()
        .then((d) => active && setS(d))
        .catch(() => active && setS(null));
      fetchModels()
        .then((m) => active && setReady(m.ready))
        .catch(() => active && setReady(null));
    };
    tick();
    const id = setInterval(tick, 3000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  const loaded = s?.loaded_models[0];
  return (
    <footer className="statusline">
      <span className={`seg mode ${ready ? "ok" : ready === null ? "bad" : "warn"}`}>
        {ready ? "READY" : ready === null ? "OFFLINE" : ready === undefined ? "…" : "SETUP"}
      </span>
      <span className="seg">{loaded ? loaded.name : "model idle"}</span>
      <span className="grow" />
      {s && (
        <>
          <span className="seg">cpu {Math.round(s.cpu_percent)}%</span>
          <span className="seg">
            ram {(s.ram_used / 1e9).toFixed(1)}/{(s.ram_total / 1e9).toFixed(0)}G
          </span>
        </>
      )}
      <span className="seg">no network needed</span>
    </footer>
  );
}
