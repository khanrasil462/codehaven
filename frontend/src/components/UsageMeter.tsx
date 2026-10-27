import { useCallback, useEffect, useRef, useState } from "react";
import { fetchUsage, type MonthUsage } from "../api/client";

function fmt(n: number) {
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}k`;
  return String(n);
}

function monthKey(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function shift(month: string, delta: number) {
  const [y, m] = month.split("-").map(Number);
  return monthKey(new Date(y, m - 1 + delta, 1));
}

function label(month: string) {
  const [y, m] = month.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleString(undefined, { month: "long", year: "numeric" });
}

/** Top-bar token counter; click for the month's usage breakdown. */
export function UsageMeter() {
  const current = monthKey(new Date());
  const [open, setOpen] = useState(false);
  const [month, setMonth] = useState(current);
  const [data, setData] = useState<MonthUsage | null>(null);
  const [today, setToday] = useState<number | null>(null);
  const ref = useRef<HTMLDivElement | null>(null);

  const refresh = useCallback(async () => {
    const d = await fetchUsage(month).catch(() => null);
    if (!d) return;
    setData(d);
    setToday(d.today_tokens);
  }, [month]);

  useEffect(() => {
    void refresh();
    const id = setInterval(refresh, open ? 3000 : 10000);
    return () => clearInterval(id);
  }, [refresh, open]);

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

  const total = data ? data.prompt_tokens + data.completion_tokens : 0;
  const peak = Math.max(1, ...(data?.daily.map((d) => d.prompt_tokens + d.completion_tokens) ?? [0]));
  const [y, m] = month.split("-").map(Number);
  const daysInMonth = new Date(y, m, 0).getDate();
  const byDay = new Map(data?.daily.map((d) => [d.day, d.prompt_tokens + d.completion_tokens]));

  return (
    <div className="picker usage" ref={ref}>
      <button type="button" className="picker-btn" onClick={() => setOpen((v) => !v)} aria-expanded={open} title="Token usage">
        <span className="picker-mode">{today === null ? "…" : fmt(today)}</span>
        <span className="picker-name">tokens today</span>
      </button>

      {open && (
        <div className="picker-menu usage-menu">
          <div className="usage-nav">
            <button type="button" className="ghost" onClick={() => setMonth(shift(month, -1))} aria-label="Previous month">‹</button>
            <strong>{label(month)}</strong>
            <button type="button" className="ghost" disabled={month >= current} onClick={() => setMonth(shift(month, 1))} aria-label="Next month">›</button>
          </div>

          <div className="usage-total">
            <span className="usage-big">{total.toLocaleString()}</span>
            <span className="muted">tokens this month · {data?.requests ?? 0} requests</span>
          </div>

          <div className="usage-split">
            <div><small className="muted">Input</small><span>{(data?.prompt_tokens ?? 0).toLocaleString()}</span></div>
            <div><small className="muted">Output</small><span>{(data?.completion_tokens ?? 0).toLocaleString()}</span></div>
          </div>

          <div className="picker-section">Daily</div>
          <div className="usage-chart" role="img" aria-label="Daily token usage">
            {Array.from({ length: daysInMonth }, (_, i) => {
              const day = `${month}-${String(i + 1).padStart(2, "0")}`;
              const v = byDay.get(day) ?? 0;
              return (
                <div key={day} className="usage-col" title={`${day}: ${v.toLocaleString()} tokens`}>
                  <div className="usage-bar" style={{ height: `${v ? Math.max(4, (v / peak) * 100) : 0}%` }} />
                </div>
              );
            })}
          </div>
          <div className="usage-axis muted"><span>1</span><span>{daysInMonth}</span></div>

          <div className="picker-section">By model</div>
          {data?.models.length ? (
            data.models.map((mo) => {
              const t = mo.prompt_tokens + mo.completion_tokens;
              return (
                <div key={mo.model} className="usage-model">
                  <div className="setup-head">
                    <span>{mo.model}</span>
                    <span className="muted">{fmt(t)}</span>
                  </div>
                  <div className="bar"><div className="bar-fill" style={{ width: `${total ? (t / total) * 100 : 0}%` }} /></div>
                </div>
              );
            })
          ) : (
            <p className="muted usage-empty">No usage recorded this month.</p>
          )}

          <p className="muted usage-foot">All time: {(data?.all_time_tokens ?? 0).toLocaleString()} tokens</p>
        </div>
      )}
    </div>
  );
}
