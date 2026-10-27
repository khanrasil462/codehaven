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
  category: "ai_art" | "diagram";
  engine: "ai_diffusion" | "vector_diagram";
  prompt: string;
  style: ImageGenerateRequest["style"];
}

const PRESETS: PresetPrompt[] = [
  // Real AI Art Presets (Flux / Diffusion)
  {
    label: "Cyberpunk Terminal Hacker",
    category: "ai_art",
    engine: "ai_diffusion",
    prompt: "A futuristic cyberpunk hacker sitting at a multi-monitor glowing terminal workstation with matrix green and cyan neon reflections, rainy window, high-tech cybernetics, 8k cinematic lighting",
    style: "cyberpunk",
  },
  {
    label: "3D Neural Network Core",
    category: "ai_art",
    engine: "ai_diffusion",
    prompt: "Isometric 3D render of a futuristic artificial intelligence glowing neural core, crystalline fiber optic nodes with pulsing electric cyan energy pathways, octane render",
    style: "3d_render",
  },
  {
    label: "Robot Coding Companion",
    category: "ai_art",
    engine: "ai_diffusion",
    prompt: "An adorable friendly glowing robot developer typing on an ergonomic mechanical keyboard with holographic code screens floating in front of it, soft studio lighting",
    style: "3d_render",
  },
  {
    label: "Synthwave Developer Sunset",
    category: "ai_art",
    engine: "ai_diffusion",
    prompt: "Retro 80s synthwave developer desk overlooking a neon grid city skyline with a massive glowing magenta sunset, vintage CRT monitor displaying code, vibrant colors",
    style: "cyberpunk",
  },
  // Technical Architecture Presets (Vector Diagrams)
  {
    label: "Microservices Architecture",
    category: "diagram",
    engine: "vector_diagram",
    prompt: "Modern Microservices Architecture diagram: API Gateway routing to Auth Service, Order Service, and Notification Service, backed by PostgreSQL, Redis Cache, and RabbitMQ message broker with glowing data pathways.",
    style: "architecture",
  },
  {
    label: "Binary Search Tree (AVL)",
    category: "diagram",
    engine: "vector_diagram",
    prompt: "Binary Search Tree data structure diagram showing root node 50 branching to left child 30 and right child 70, with balance factors, directional edge arrows, and color-coded search pathways.",
    style: "datastructure",
  },
  {
    label: "OAuth2 Authorization Flow",
    category: "diagram",
    engine: "vector_diagram",
    prompt: "OAuth2.0 Authorization Code flow diagram between Client Browser, Authorization Server, and Resource API with step-by-step numbered arrow exchanges (Auth Request, Token Exchange, Protected Resource).",
    style: "flowchart",
  },
  {
    label: "GitFlow Branching Model",
    category: "diagram",
    engine: "vector_diagram",
    prompt: "GitFlow branching diagram showing Main/Production branch in emerald, Develop branch in cyan, Feature branches merging in, and Hotfix branch patching directly with commit nodes.",
    style: "architecture",
  },
  {
    label: "React Component Lifecycle",
    category: "diagram",
    engine: "vector_diagram",
    prompt: "Interactive React Component Lifecycle state machine diagram: Mounting (constructor, render, componentDidMount), Updating (shouldComponentUpdate, render), and Unmounting.",
    style: "flowchart",
  },
];

interface ImageStudioPanelProps {
  onOpenInEditor?: (code: string, language: string) => void;
}

export function ImageStudioPanel({ onOpenInEditor }: ImageStudioPanelProps) {
  const [engine, setEngine] = useState<"auto" | "ai_diffusion" | "vector_diagram">("auto");
  const [prompt, setPrompt] = useState(PRESETS[0].prompt);
  const [style, setStyle] = useState<ImageGenerateRequest["style"]>("cyberpunk");
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

  async function handleGenerate(customPrompt?: string, customEngine?: "auto" | "ai_diffusion" | "vector_diagram", customStyle?: ImageGenerateRequest["style"]) {
    const p = (customPrompt || prompt).trim();
    if (!p || generating) return;

    const eng = customEngine ?? engine;
    const sty = customStyle ?? style;

    setGenerating(true);
    setErrorMsg(null);

    try {
      const res = await generateImage({
        prompt: p,
        engine: eng,
        style: sty,
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
    setEngine(preset.engine);
    handleGenerate(preset.prompt, preset.engine, preset.style);
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

  function handleDownload() {
    if (!currentImage) return;

    if (currentImage.format !== "svg" && currentImage.image_url) {
      // Download raster image directly
      const a = document.createElement("a");
      a.href = currentImage.image_url;
      a.download = `${currentImage.title.replace(/[^a-zA-Z0-9_-]/g, "_") || "codehaven_art"}.${currentImage.format}`;
      a.target = "_blank";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      return;
    }

    if (currentImage.svg_content) {
      const blob = new Blob([currentImage.svg_content], { type: "image/svg+xml;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${currentImage.title.replace(/[^a-zA-Z0-9_-]/g, "_") || "codehaven_vector"}.svg`;
      a.click();
      URL.revokeObjectURL(url);
    }
  }

  function handleExportPNG() {
    if (!currentImage) return;

    if (currentImage.format !== "svg" && currentImage.image_url) {
      handleDownload();
      return;
    }

    if (!currentImage.svg_content) return;
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

  function handleCopyContent() {
    if (!currentImage) return;

    if (currentImage.svg_content) {
      navigator.clipboard.writeText(currentImage.svg_content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } else if (currentImage.image_url) {
      navigator.clipboard.writeText(window.location.origin + currentImage.image_url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }

  function handleOpenInEditor() {
    if (!currentImage?.svg_content || !onOpenInEditor) return;
    onOpenInEditor(currentImage.svg_content, "xml");
  }

  const isSvg = currentImage?.format === "svg" && Boolean(currentImage.svg_content);

  return (
    <div className="layout studio-layout">
      {/* Studio Configuration Sidebar */}
      <aside className="studio-sidebar">
        <div className="panel-header">
          <div className="panel-header-left">
            <span className="terminal-prompt-symbol">🎨</span>
            <strong>Visual &amp; Diagram Studio</strong>
          </div>
          <span className="badge-tag">FLUX &amp; VECTOR</span>
        </div>

        {/* Preset Prompt Pills */}
        <div className="preset-container">
          <span className="section-label">QUICK AI ART &amp; DIAGRAM PRESETS</span>
          <div className="preset-grid">
            {PRESETS.map((p, idx) => (
              <button
                key={idx}
                type="button"
                className="preset-btn"
                onClick={() => handleSelectPreset(p)}
                disabled={generating}
              >
                <span className="preset-icon">{p.category === "ai_art" ? "✨" : "📐"}</span>
                <span className="preset-text">{p.label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Generation Form */}
        <div className="studio-form">
          {/* Engine Selector */}
          <label className="form-group">
            <span className="form-label">ENGINE MODE</span>
            <div className="engine-toggle-group">
              <button
                type="button"
                className={`engine-toggle-btn ${engine === "ai_diffusion" ? "active" : ""}`}
                onClick={() => {
                  setEngine("ai_diffusion");
                  if (style === "architecture" || style === "datastructure" || style === "flowchart") {
                    setStyle("cyberpunk");
                  }
                }}
              >
                ✨ AI Art (Flux)
              </button>
              <button
                type="button"
                className={`engine-toggle-btn ${engine === "vector_diagram" ? "active" : ""}`}
                onClick={() => {
                  setEngine("vector_diagram");
                  if (style === "cyberpunk" || style === "photorealistic" || style === "3d_render") {
                    setStyle("architecture");
                  }
                }}
              >
                📐 Vector Diagram
              </button>
              <button
                type="button"
                className={`engine-toggle-btn ${engine === "auto" ? "active" : ""}`}
                onClick={() => setEngine("auto")}
              >
                ⚡ Auto Detect
              </button>
            </div>
          </label>

          <label className="form-group">
            <span className="form-label">PROMPT / VISUAL DESCRIPTION</span>
            <textarea
              className="studio-textarea"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Describe the image, art, system architecture, flowchart, or concept to generate..."
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
                <optgroup label="AI Diffusion Art">
                  <option value="cyberpunk">⚡ Cyberpunk / Neon Matrix</option>
                  <option value="photorealistic">📸 Photorealistic / Cinematic</option>
                  <option value="3d_render">👾 3D Isometric Render</option>
                  <option value="anime">🌸 Modern Anime Art</option>
                  <option value="vector">📐 Clean Digital Vector</option>
                </optgroup>
                <optgroup label="Technical Diagrams">
                  <option value="architecture">🏗 Architecture Diagram</option>
                  <option value="datastructure">🌳 Data Structure / Trees</option>
                  <option value="flowchart">🔀 Flowchart / Logic Flow</option>
                  <option value="ui_mockup">📱 UI / Component Wireframe</option>
                </optgroup>
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
            {generating
              ? "⏳ Synthesizing Image / Diagram..."
              : engine === "vector_diagram"
              ? "⚡ Generate Vector Diagram"
              : "✨ Generate AI Image"}
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
                    {item.format === "svg" && item.svg_content ? (
                      <div
                        className="thumb-svg-preview"
                        dangerouslySetInnerHTML={{ __html: item.svg_content }}
                      />
                    ) : item.image_url ? (
                      <img
                        src={item.image_url}
                        alt={item.title}
                        className="thumb-raster-preview"
                      />
                    ) : (
                      <div className="thumb-placeholder">🎨</div>
                    )}
                  </div>
                  <div className="gallery-info">
                    <span className="gallery-title" title={item.prompt}>
                      {item.title}
                    </span>
                    <div className="gallery-meta">
                      <span className="gallery-style">{item.format.toUpperCase()} · {item.style}</span>
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
                <span className="badge-style">{currentImage.format.toUpperCase()} · {currentImage.style}</span>
              </div>

              <div className="stage-actions">
                <button
                  type="button"
                  className="stage-btn"
                  onClick={handleExportPNG}
                  title="Download image file"
                >
                  🖼 Download {currentImage.format === "svg" ? "PNG" : currentImage.format.toUpperCase()}
                </button>
                {isSvg && (
                  <button
                    type="button"
                    className="stage-btn"
                    onClick={handleDownload}
                    title="Download vector SVG file"
                  >
                    📐 Download SVG
                  </button>
                )}
                <button
                  type="button"
                  className="stage-btn"
                  onClick={handleCopyContent}
                  title="Copy SVG markup or image URL"
                >
                  {copied ? "✓ Copied" : isSvg ? "📋 Copy SVG" : "🔗 Copy Link"}
                </button>
                {isSvg && onOpenInEditor && (
                  <button
                    type="button"
                    className="stage-btn stage-btn-primary"
                    onClick={handleOpenInEditor}
                    title="Inspect &amp; edit SVG code in Monaco Editor"
                  >
                    ✏ Edit Code in Editor
                  </button>
                )}
              </div>
            </div>

            {/* Visual Canvas Display */}
            <div className="canvas-wrapper" ref={previewRef}>
              {isSvg ? (
                <div
                  className="svg-stage-container"
                  dangerouslySetInnerHTML={{ __html: currentImage.svg_content! }}
                />
              ) : currentImage.image_url ? (
                <div className="raster-stage-container">
                  <img
                    src={currentImage.image_url}
                    alt={currentImage.title}
                    className="stage-raster-image"
                  />
                </div>
              ) : (
                <div className="empty-render">No preview available</div>
              )}
            </div>
          </div>
        ) : (
          <div className="stage-empty">
            <div className="empty-terminal-icon">🎨</div>
            <h3>CodeHaven AI Visual &amp; Diagram Studio</h3>
            <p>
              Generate high-resolution photorealistic AI artworks, 3D renders, and production-grade
              System Architecture &amp; Data Structure Diagrams.
            </p>
            <div className="empty-actions">
              <button
                type="button"
                className="primary-btn"
                onClick={() => handleSelectPreset(PRESETS[0])}
              >
                ✨ Generate Cyberpunk Terminal Hacker
              </button>
              <button
                type="button"
                className="secondary"
                onClick={() => handleSelectPreset(PRESETS[4])}
              >
                📐 Generate Microservices Architecture
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
