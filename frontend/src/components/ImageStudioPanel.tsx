import { useState, useEffect, useRef } from "react";
import {
  generateImage,
  fetchImages,
  deleteImage,
  type ImageItem,
  type ImageGenerateRequest,
} from "../api/client";

interface PresetPrompt {
  label: string;
  prompt: string;
  style: "architecture" | "datastructure" | "flowchart" | "vector" | "cyberpunk" | "ui_mockup";
}

const PRESETS: PresetPrompt[] = [
  {
    label: "Microservices Architecture",
    prompt: "Modern Microservices Architecture diagram: API Gateway routing to Auth Service, Order Service, and Notification Service, backed by PostgreSQL, Redis Cache, and RabbitMQ message broker with glowing data pathways.",
    style: "architecture",
  },
  {
    label: "Binary Search Tree Visualizer",
    prompt: "Binary Search Tree data structure diagram showing root node 50 branching to left child 30 and right child 70, with balance factors, directional edge arrows, and color-coded search pathways.",
    style: "datastructure",
  },
  {
    label: "OAuth2 Authorization Flow",
    prompt: "OAuth2.0 Authorization Code flow diagram between Client Browser, Authorization Server, and Resource API with step-by-step numbered arrow exchanges (Auth Request, Token Exchange, Protected Resource).",
    style: "flowchart",
  },
  {
    label: "Cyberpunk Terminal Logo",
    prompt: "Futuristic Cyberpunk Terminal Emblem with glowing neon skull/chip matrix, digital circuitry lines, Japanese tech typography, and electric cyan phosphor green aura.",
    style: "cyberpunk",
  },
  {
    label: "React Component Lifecycle",
    prompt: "Interactive React Component Lifecycle state machine diagram: Mounting (constructor, render, componentDidMount), Updating (shouldComponentUpdate, render), and Unmounting.",
    style: "flowchart",
  },
  {
    label: "Git Branching Strategy",
    prompt: "GitFlow branching diagram showing Main/Production branch in emerald, Develop branch in cyan, Feature branches merging in, and Hotfix branch patching directly with commit nodes.",
    style: "architecture",
  },
];

interface ImageStudioPanelProps {
  onOpenInEditor?: (code: string, language: string) => void;
}

export function ImageStudioPanel({ onOpenInEditor }: ImageStudioPanelProps) {
  const [prompt, setPrompt] = useState(PRESETS[0].prompt);
  const [style, setStyle] = useState<ImageGenerateRequest["style"]>("architecture");
  const [theme, setTheme] = useState<ImageGenerateRequest["theme"]>("terminal");
  const [aspectRatio, setAspectRatio] = useState<ImageGenerateRequest["aspect_ratio"]>("16:9");
  const [generating, setGenerating] = useState(false);
  const [currentImage, setCurrentImage] = useState<ImageItem | null>(null);
  const [history, setHistory] = useState<ImageItem[]>([]);
  const [copied, setCopied] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const previewRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    loadGallery();
  }, []);

  async function loadGallery() {
    try {
      const items = await fetchImages();
      setHistory(items);
      if (items.length > 0 && !currentImage) {
        setCurrentImage(items[0]);
      }
    } catch {
      // Backend may be starting
    }
  }

  async function handleGenerate(customPrompt?: string) {
    const p = (customPrompt || prompt).trim();
    if (!p || generating) return;

    setGenerating(true);
    setErrorMsg(null);

    try {
      const res = await generateImage({
        prompt: p,
        style,
        theme,
        aspect_ratio: aspectRatio,
      });

      setCurrentImage(res.image);
      setHistory((prev) => [res.image, ...prev.filter((item) => item.id !== res.image.id)]);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to generate image.");
    } finally {
      setGenerating(false);
    }
  }

  function handleSelectPreset(preset: PresetPrompt) {
    setPrompt(preset.prompt);
    setStyle(preset.style);
    handleGenerate(preset.prompt);
  }

  async function handleDelete(id: string) {
    try {
      await deleteImage(id);
      setHistory((prev) => prev.filter((item) => item.id !== id));
      if (currentImage?.id === id) {
        const remaining = history.filter((item) => item.id !== id);
        setCurrentImage(remaining.length > 0 ? remaining[0] : null);
      }
    } catch (err) {
      alert("Failed to delete image");
    }
  }

  function handleDownloadSVG() {
    if (!currentImage?.svg_content) return;
    const blob = new Blob([currentImage.svg_content], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${currentImage.title.replace(/[^a-zA-Z0-9_-]/g, "_") || "codehaven_vector"}.svg`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function handleExportPNG() {
    if (!currentImage?.svg_content) return;
    const svgStr = currentImage.svg_content;
    const blob = new Blob([svgStr], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const img = new Image();

    img.onload = () => {
      const scale = 2; // High-res 2x export
      const canvas = document.createElement("canvas");
      canvas.width = (img.width || 1200) * scale;
      canvas.height = (img.height || 675) * scale;
      const ctx = canvas.getContext("2d");
      if (ctx) {
        ctx.scale(scale, scale);
        ctx.drawImage(img, 0, 0);
        const pngUrl = canvas.toDataURL("image/png");
        const a = document.createElement("a");
        a.href = pngUrl;
        a.download = `${currentImage.title.replace(/[^a-zA-Z0-9_-]/g, "_") || "codehaven_diagram"}.png`;
        a.click();
      }
      URL.revokeObjectURL(url);
    };
    img.src = url;
  }

  function handleCopySVG() {
    if (!currentImage?.svg_content) return;
    navigator.clipboard.writeText(currentImage.svg_content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function handleOpenInEditor() {
    if (!currentImage?.svg_content || !onOpenInEditor) return;
    onOpenInEditor(currentImage.svg_content, "xml");
  }

  return (
    <div className="layout studio-layout">
      {/* Studio Configuration Sidebar */}
      <aside className="studio-sidebar">
        <div className="panel-header">
          <div className="panel-header-left">
            <span className="terminal-prompt-symbol">🎨</span>
            <strong>Visual & Diagram Studio</strong>
          </div>
          <span className="badge-tag">100% OFFLINE</span>
        </div>

        {/* Preset Prompt Pills */}
        <div className="preset-container">
          <span className="section-label">QUICK CS PRESETS</span>
          <div className="preset-grid">
            {PRESETS.map((p, idx) => (
              <button
                key={idx}
                type="button"
                className="preset-btn"
                onClick={() => handleSelectPreset(p)}
                disabled={generating}
              >
                <span className="preset-icon">⚡</span>
                <span className="preset-text">{p.label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Generation Form */}
        <div className="studio-form">
          <label className="form-group">
            <span className="form-label">PROMPT / DIAGRAM DESCRIPTION</span>
            <textarea
              className="studio-textarea"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Describe the system architecture, flowchart, data structure, or visual art to generate..."
              rows={4}
              disabled={generating}
            />
          </label>

          <div className="form-row">
            <label className="form-group">
              <span className="form-label">STYLE</span>
              <select
                value={style}
                onChange={(e) => setStyle(e.target.value as any)}
                disabled={generating}
              >
                <option value="architecture">🏗 Architecture Diagram</option>
                <option value="datastructure">🌳 Data Structure / Trees</option>
                <option value="flowchart">🔀 Flowchart / Logic Flow</option>
                <option value="cyberpunk">⚡ Cyberpunk / Terminal Art</option>
                <option value="vector">📐 Clean Vector Graphic</option>
                <option value="ui_mockup">📱 UI / Component Wireframe</option>
              </select>
            </label>

            <label className="form-group">
              <span className="form-label">THEME</span>
              <select
                value={theme}
                onChange={(e) => setTheme(e.target.value as any)}
                disabled={generating}
              >
                <option value="terminal">🟢 Terminal (Obsidian/Green)</option>
                <option value="dark">🔵 Deep Blue / Cyan</option>
                <option value="neon">🟣 Cyber Neon / Violet</option>
                <option value="blueprint">📐 Technical Blueprint</option>
              </select>
            </label>
          </div>

          <label className="form-group">
            <span className="form-label">ASPECT RATIO</span>
            <div className="aspect-buttons">
              {(["16:9", "1:1", "4:3"] as const).map((ar) => (
                <button
                  key={ar}
                  type="button"
                  className={`aspect-btn ${aspectRatio === ar ? "active" : ""}`}
                  onClick={() => setAspectRatio(ar)}
                  disabled={generating}
                >
                  {ar === "16:9" ? "🖥 16:9" : ar === "1:1" ? "⬛ 1:1" : "📺 4:3"}
                </button>
              ))}
            </div>
          </label>

          {errorMsg && <div className="studio-error">{errorMsg}</div>}

          <button
            type="button"
            className={`generate-visual-btn ${generating ? "generating" : ""}`}
            onClick={() => handleGenerate()}
            disabled={generating || !prompt.trim()}
          >
            {generating ? "⏳ Synthesizing Vector Graphics..." : "⚡ Generate Diagram / Art"}
          </button>
        </div>

        {/* Gallery Drawer */}
        <div className="gallery-section">
          <div className="gallery-header">
            <span className="section-label">SAVED GALLERY ({history.length})</span>
            {history.length > 0 && (
              <span className="gallery-hint">Click to preview</span>
            )}
          </div>
          <div className="gallery-list">
            {history.length === 0 ? (
              <div className="empty-gallery">No visuals generated yet. Try a preset above!</div>
            ) : (
              history.map((item) => (
                <div
                  key={item.id}
                  className={`gallery-card ${currentImage?.id === item.id ? "active" : ""}`}
                  onClick={() => setCurrentImage(item)}
                >
                  <div className="gallery-thumb">
                    <div
                      className="thumb-svg-preview"
                      dangerouslySetInnerHTML={{ __html: item.svg_content }}
                    />
                  </div>
                  <div className="gallery-info">
                    <span className="gallery-title" title={item.prompt}>
                      {item.title}
                    </span>
                    <div className="gallery-meta">
                      <span className="gallery-style">{item.style}</span>
                      <button
                        type="button"
                        className="gallery-del"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(item.id);
                        }}
                        title="Delete image"
                      >
                        ✕
                      </button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </aside>

      {/* Main Interactive Stage */}
      <main className="studio-stage">
        {currentImage ? (
          <div className="stage-content">
            {/* Stage Toolbar */}
            <div className="stage-toolbar">
              <div className="stage-info">
                <span className="stage-prompt-symbol">❯_</span>
                <strong className="stage-title">{currentImage.title}</strong>
                <span className="badge-style">{currentImage.style}</span>
              </div>

              <div className="stage-actions">
                <button
                  type="button"
                  className="stage-btn"
                  onClick={handleExportPNG}
                  title="Export high-resolution PNG image"
                >
                  🖼 Download PNG
                </button>
                <button
                  type="button"
                  className="stage-btn"
                  onClick={handleDownloadSVG}
                  title="Download vector SVG file"
                >
                  📐 Download SVG
                </button>
                <button
                  type="button"
                  className="stage-btn"
                  onClick={handleCopySVG}
                  title="Copy SVG markup"
                >
                  {copied ? "✓ Copied" : "📋 Copy SVG"}
                </button>
                {onOpenInEditor && (
                  <button
                    type="button"
                    className="stage-btn stage-btn-primary"
                    onClick={handleOpenInEditor}
                    title="Inspect & edit SVG code in Monaco Editor"
                  >
                    ✏ Edit Code in Editor
                  </button>
                )}
              </div>
            </div>

            {/* SVG Visual Canvas */}
            <div className="canvas-wrapper" ref={previewRef}>
              <div
                className="svg-stage-container"
                dangerouslySetInnerHTML={{ __html: currentImage.svg_content }}
              />
            </div>
          </div>
        ) : (
          <div className="stage-empty">
            <div className="empty-terminal-icon">🎨</div>
            <h3>CodeHaven AI Visual & Diagram Studio</h3>
            <p>
              Generate production-grade System Architecture Diagrams, Flowcharts, Data Structure
              visualizations, and Cyberpunk Vector Graphics 100% offline.
            </p>
            <div className="empty-actions">
              <button
                type="button"
                className="primary-btn"
                onClick={() => handleGenerate(PRESETS[0].prompt)}
              >
                ⚡ Generate Microservices Architecture
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
