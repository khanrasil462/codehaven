import { useCallback, useEffect, useRef, useState } from "react";
import {
  generateImage,
  fetchImages,
  deleteImage,
  type ImageItem,
  type ImageGenerateRequest,
} from "../api/client";

type DiagramType = NonNullable<ImageGenerateRequest["style"]>;
type Direction = NonNullable<ImageGenerateRequest["direction"]>;

const PRESETS: { label: string; prompt: string; style: DiagramType }[] = [
  { label: "Login flow", prompt: "User login flow with email and password check, error message and dashboard", style: "flowchart" },
  { label: "Microservices", prompt: "Microservices system: browser, API gateway, auth service, order service, notification service, PostgreSQL, Redis cache and RabbitMQ", style: "architecture" },
  { label: "Binary search tree", prompt: "Binary search tree with root 50, children 30 and 70, then 20, 40, 60 and 80", style: "tree" },
  { label: "OAuth2 login", prompt: "OAuth2 authorization code flow between user, client app, authorization server and resource API", style: "process" },
  { label: "CI/CD pipeline", prompt: "CI/CD pipeline: commit, build, unit tests, tests pass decision, deploy to staging, deploy to production", style: "flowchart" },
];

const svgUrl = (svg: string) => `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;

function svgSize(svg: string): { w: number; h: number } {
  const m = svg.match(/viewBox="[\d.\-]+ [\d.\-]+ ([\d.]+) ([\d.]+)"/);
  if (m) return { w: parseFloat(m[1]), h: parseFloat(m[2]) };
  const w = svg.match(/<svg[^>]*\swidth="([\d.]+)/);
  const h = svg.match(/<svg[^>]*\sheight="([\d.]+)/);
  return { w: w ? parseFloat(w[1]) : 1200, h: h ? parseFloat(h[1]) : 675 };
}

function Viewer({ item }: { item: ImageItem }) {
  const box = useRef<HTMLDivElement | null>(null);
  const [view, setView] = useState({ scale: 1, x: 0, y: 0 });
  const drag = useRef<{ x: number; y: number; vx: number; vy: number } | null>(null);
  const size = svgSize(item.svg_content);

  const fit = useCallback(() => {
    const el = box.current;
    if (!el) return;
    const pad = 48;
    const scale = Math.min((el.clientWidth - pad) / size.w, (el.clientHeight - pad) / size.h, 2.5);
    setView({
      scale,
      x: (el.clientWidth - size.w * scale) / 2,
      y: (el.clientHeight - size.h * scale) / 2,
    });
  }, [size.w, size.h]);

  useEffect(() => {
    fit();
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(fit);
    ro.observe(el);
    return () => ro.disconnect();
  }, [item.id, fit]);

  const zoomAt = useCallback((factor: number, cx?: number, cy?: number) => {
    const el = box.current;
    if (!el) return;
    setView((v) => {
      const px = cx ?? el.clientWidth / 2;
      const py = cy ?? el.clientHeight / 2;
      const scale = Math.min(8, Math.max(0.1, v.scale * factor));
      const k = scale / v.scale;
      return { scale, x: px - (px - v.x) * k, y: py - (py - v.y) * k };
    });
  }, []);

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const r = el.getBoundingClientRect();
      zoomAt(e.deltaY < 0 ? 1.12 : 1 / 1.12, e.clientX - r.left, e.clientY - r.top);
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [zoomAt]);

  return (
    <div className="viewer">
      <div
        ref={box}
        className="viewer-canvas"
        onPointerDown={(e) => {
          (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
          drag.current = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y };
        }}
        onPointerMove={(e) => {
          const d = drag.current;
          if (d) setView((v) => ({ ...v, x: d.vx + e.clientX - d.x, y: d.vy + e.clientY - d.y }));
        }}
        onPointerUp={() => (drag.current = null)}
        onDoubleClick={fit}
      >
        <img
          alt={item.title}
          draggable={false}
          src={svgUrl(item.svg_content)}
          style={{ left: view.x, top: view.y, width: size.w * view.scale, height: size.h * view.scale }}
        />
      </div>
      <div className="viewer-zoom">
        <button type="button" onClick={() => zoomAt(1 / 1.25)} aria-label="Zoom out">−</button>
        <span>{Math.round(view.scale * 100)}%</span>
        <button type="button" onClick={() => zoomAt(1.25)} aria-label="Zoom in">+</button>
        <button type="button" onClick={fit}>Fit</button>
        <button type="button" onClick={() => zoomAt(1 / view.scale)}>100%</button>
      </div>
    </div>
  );
}

export function ImageStudioPanel(_props: { onOpenInEditor?: () => void }) {
  const [prompt, setPrompt] = useState("");
  const [style, setStyle] = useState<DiagramType>("flowchart");
  const [direction, setDirection] = useState<Direction>("auto");
  const [generating, setGenerating] = useState(false);
  const [current, setCurrent] = useState<ImageItem | null>(null);
  const [history, setHistory] = useState<ImageItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchImages()
      .then((items) => {
        setHistory(items);
        if (items.length) setCurrent(items[0]);
      })
      .catch(() => undefined);
  }, []);

  async function generate(text = prompt, type = style) {
    const p = text.trim();
    if (!p || generating) return;
    setGenerating(true);
    setError(null);
    try {
      const res = await generateImage({ prompt: p, style: type, direction });
      setCurrent(res.image);
      setHistory((h) => [res.image, ...h.filter((i) => i.id !== res.image.id)]);
    } catch (err) {
      const raw = err instanceof Error ? err.message : "Could not draw the diagram.";
      try {
        setError(JSON.parse(raw).detail ?? raw);
      } catch {
        setError(raw);
      }
    } finally {
      setGenerating(false);
    }
  }

  async function remove(id: string) {
    await deleteImage(id).catch(() => undefined);
    const rest = history.filter((i) => i.id !== id);
    setHistory(rest);
    if (current?.id === id) setCurrent(rest[0] ?? null);
  }

  function download() {
    if (!current) return;
    const blob = new Blob([current.svg_content], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${current.title.replace(/[^a-zA-Z0-9_-]+/g, "_") || "diagram"}.svg`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function openInDiagramsNet() {
    if (!current) return;
    const xml = current.mxfile;
    const url =
      xml && xml.length < 30000
        ? `https://app.diagrams.net/#R${encodeURIComponent(xml)}`
        : "https://app.diagrams.net/";
    window.open(url, "_blank", "noopener");
  }

  const hasEditable = !!current?.svg_content.includes('content="&lt;mxfile');

  return (
    <div className="layout studio-layout">
      <aside className="studio-sidebar">
        <div className="panel-header">
          <strong>Diagrams</strong>
          <span className="badge-tag">offline</span>
        </div>

        <div className="studio-form">
          <label className="form-group">
            <span>Describe the diagram</span>
            <textarea
              className="studio-textarea"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) void generate();
              }}
              placeholder="e.g. Steps of a user signing up, with an email check"
              rows={4}
              disabled={generating}
            />
          </label>

          <div className="form-row">
            <label className="form-group">
              <span>Type</span>
              <select value={style} onChange={(e) => setStyle(e.target.value as DiagramType)} disabled={generating}>
                <option value="flowchart">Flowchart</option>
                <option value="architecture">Architecture</option>
                <option value="tree">Tree / hierarchy</option>
                <option value="process">Process steps</option>
              </select>
            </label>
            <label className="form-group">
              <span>Direction</span>
              <select value={direction} onChange={(e) => setDirection(e.target.value as Direction)} disabled={generating}>
                <option value="auto">Auto</option>
                <option value="TB">Top to bottom</option>
                <option value="LR">Left to right</option>
              </select>
            </label>
          </div>

          {error && <div className="studio-error">{error}</div>}

          <button type="button" className="generate-visual-btn" onClick={() => void generate()} disabled={generating || !prompt.trim()}>
            {generating ? "Drawing…" : "Draw diagram"}
          </button>
          <span className="muted studio-hint">Ctrl+Enter to draw. Tip: Deep mode gives better diagrams.</span>
        </div>

        <div className="preset-container">
          <span className="section-label">Examples</span>
          <div className="preset-grid">
            {PRESETS.map((p) => (
              <button
                key={p.label}
                type="button"
                className="preset-btn"
                disabled={generating}
                onClick={() => {
                  setPrompt(p.prompt);
                  setStyle(p.style);
                  void generate(p.prompt, p.style);
                }}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>

        <div className="gallery-section">
          <div className="gallery-header">
            <span className="section-label">Saved ({history.length})</span>
          </div>
          <div className="gallery-list">
            {history.length === 0 && <div className="empty-gallery">Nothing drawn yet.</div>}
            {history.map((item) => (
              <div
                key={item.id}
                className={`gallery-card ${current?.id === item.id ? "active" : ""}`}
                onClick={() => setCurrent(item)}
              >
                <div className="gallery-thumb">
                  <img alt="" src={svgUrl(item.svg_content)} />
                </div>
                <div className="gallery-info">
                  <span className="gallery-title" title={item.prompt}>{item.title}</span>
                  <div className="gallery-meta">
                    <span className="gallery-style">{item.style}</span>
                    <button
                      type="button"
                      className="gallery-del"
                      title="Delete"
                      onClick={(e) => {
                        e.stopPropagation();
                        void remove(item.id);
                      }}
                    >
                      ×
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </aside>

      <main className="studio-stage">
        {current ? (
          <div className="stage-content">
            <div className="stage-toolbar">
              <div className="stage-info">
                <strong className="stage-title">{current.title}</strong>
                <span className="badge-style">{current.style}</span>
              </div>
              <div className="stage-actions">
                <button type="button" className="stage-btn" onClick={openInDiagramsNet} disabled={!hasEditable && !current.mxfile} title="Opens app.diagrams.net in your browser (needs internet)">
                  Open in diagrams.net
                </button>
                <button type="button" className="stage-btn stage-btn-primary" onClick={download}>
                  Download SVG
                </button>
              </div>
            </div>
            <Viewer item={current} />
            <div className="stage-foot muted">
              Scroll to zoom, drag to move, double-click to fit. The SVG opens as editable shapes in diagrams.net (File → Open from → Device).
            </div>
          </div>
        ) : (
          <div className="stage-empty">
            <h3>Diagrams</h3>
            <p>Describe a flowchart, architecture, tree or process. CodeHaven draws it in draw.io style, offline, and you can download it as SVG and edit it in diagrams.net.</p>
            <button type="button" className="primary-btn" onClick={() => PRESETS[0] && void generate(PRESETS[0].prompt, PRESETS[0].style)}>
              Try the login flow example
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
