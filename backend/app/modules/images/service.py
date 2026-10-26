import json
import re
import uuid
from datetime import datetime
from pathlib import Path

from app.config import settings
from app.core.ollama_client import ollama_client
from app.modules.images.schemas import ImageGenerateRequest, ImageItem, ImageGenerateResponse

IMAGES_DIR = settings.data_dir / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
CATALOG_PATH = IMAGES_DIR / "images.json"


SYSTEM_PROMPT = """You are an elite Vector Graphics, System Architecture, and Technical Illustration AI engine.
Your task is to generate clean, modern, ultra-high-quality, professional SVG (Scalable Vector Graphics) markup based on the user's prompt and chosen style.

CRITICAL SVG RULES:
1. Output ONLY valid, standalone SVG code starting with `<svg` and ending with `</svg>`.
2. Do not wrap in markdown or explain unless asked — provide the direct SVG XML.
3. Always include `xmlns="http://www.w3.org/2000/svg"`, `viewBox="0 0 1200 675"`, and `width="100%"` `height="100%"`.
4. Visual Design Philosophy:
   - For Terminal/Cyberpunk/Dark themes: use deep obsidian/navy backgrounds (`#0a0f1d`, `#080c14`), glowing neon accents (emerald `#10b981`, electric cyan `#00f0ff`, amber `#f59e0b`, magenta `#ff007f`), sleek gradient definitions (`<defs><linearGradient...></defs>`), and drop-shadow filters.
   - For Architecture/Diagrams/Flowcharts: render distinct nodes with rounded rects, clear labels, colored badges, directional arrows (`<marker>` for arrowheads), connecting lines with `stroke-dasharray` animations or glows, and clean typography with `font-family="system-ui, sans-serif"`.
   - For Data Structures: clearly draw pointers, node values, balance factors, color coding (e.g. Red-Black trees).
5. All text elements MUST have legible `font-size`, `fill`, and `font-family="monospace"` or `sans-serif`.
6. Make the visuals rich, detailed, visually impressive, and educational for computer science students.
"""


class ImageService:
    def __init__(self) -> None:
        self._ensure_catalog()

    def _ensure_catalog(self) -> None:
        if not CATALOG_PATH.exists():
            CATALOG_PATH.write_text("[]", encoding="utf-8")

    def _read_catalog(self) -> list[dict]:
        try:
            return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _write_catalog(self, items: list[dict]) -> None:
        CATALOG_PATH.write_text(json.dumps(items, indent=2), encoding="utf-8")

    def list_images(self) -> list[ImageItem]:
        items = self._read_catalog()
        return [ImageItem(**item) for item in items]

    def delete_image(self, image_id: str) -> bool:
        items = self._read_catalog()
        new_items = [i for i in items if i.get("id") != image_id]
        if len(new_items) != len(items):
            self._write_catalog(new_items)
            svg_file = IMAGES_DIR / f"{image_id}.svg"
            if svg_file.exists():
                svg_file.unlink()
            return True
        return False

    async def generate_image(self, req: ImageGenerateRequest) -> ImageGenerateResponse:
        model = await ollama_client.get_effective_model(req.model)

        viewbox = "0 0 1200 675"
        if req.aspect_ratio == "1:1":
            viewbox = "0 0 800 800"
        elif req.aspect_ratio == "4:3":
            viewbox = "0 0 1024 768"

        user_content = (
            f"Generate a vector SVG illustration for the prompt: '{req.prompt}'.\n"
            f"Style: {req.style.upper()}\n"
            f"Color Theme: {req.theme.upper()}\n"
            f"Aspect Ratio ViewBox: {viewbox}\n"
            f"Ensure all text is crisp, contrasts well against the background, and all shapes/connectors look modern and sleek."
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        raw_response = await ollama_client.chat(messages, model=model)
        svg_content = self._extract_svg(raw_response, req.prompt, req.style, viewbox)

        image_id = str(uuid.uuid4())
        svg_file = IMAGES_DIR / f"{image_id}.svg"
        svg_file.write_text(svg_content, encoding="utf-8")

        title = req.prompt.split("\n")[0][:60].strip()
        item = ImageItem(
            id=image_id,
            prompt=req.prompt,
            style=req.style,
            format="svg",
            created_at=datetime.now().isoformat(),
            svg_content=svg_content,
            title=title or "Generated Illustration",
        )

        catalog = self._read_catalog()
        catalog.insert(0, item.model_dump())
        self._write_catalog(catalog)

        return ImageGenerateResponse(
            image=item,
            explanation=f"Generated {req.style} vector illustration with {model}.",
        )

    def _extract_svg(self, text: str, prompt: str, style: str, viewbox: str) -> str:
        # Match <svg ... </svg>
        match = re.search(r"<svg[\s\S]*?<\/svg>", text, re.IGNORECASE)
        if match:
            svg = match.group(0).strip()
            # Ensure proper attributes
            if "xmlns=" not in svg:
                svg = svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
            if "viewBox=" not in svg and "viewbox=" not in svg:
                svg = svg.replace("<svg", f'<svg viewBox="{viewbox}"', 1)
            return svg

        # Fallback procedural SVG if model failed to output raw SVG tags
        return self._generate_fallback_svg(prompt, style, viewbox)

    def _generate_fallback_svg(self, prompt: str, style: str, viewbox: str) -> str:
        safe_prompt = prompt.replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
        return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}" width="100%" height="100%">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0a0f1d" />
      <stop offset="100%" stop-color="#050811" />
    </linearGradient>
    <linearGradient id="glow" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#00f0ff" />
      <stop offset="100%" stop-color="#7000ff" />
    </linearGradient>
    <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="8" stdDeviation="12" flood-color="#00f0ff" flood-opacity="0.25"/>
    </filter>
  </defs>

  <rect width="100%" height="100%" fill="url(#bg)"/>
  
  <!-- Terminal Grid Pattern -->
  <g opacity="0.1" stroke="#38bdf8" stroke-width="1">
    <line x1="0" y1="100" x2="1200" y2="100" />
    <line x1="0" y1="200" x2="1200" y2="200" />
    <line x1="0" y1="300" x2="1200" y2="300" />
    <line x1="0" y1="400" x2="1200" y2="400" />
    <line x1="0" y1="500" x2="1200" y2="500" />
    <line x1="200" y1="0" x2="200" y2="675" />
    <line x1="400" y1="0" x2="400" y2="675" />
    <line x1="600" y1="0" x2="600" y2="675" />
    <line x1="800" y1="0" x2="800" y2="675" />
    <line x1="1000" y1="0" x2="1000" y2="675" />
  </g>

  <!-- Central Card -->
  <rect x="250" y="150" width="700" height="375" rx="16" fill="#111827" stroke="url(#glow)" stroke-width="2" filter="url(#shadow)"/>
  
  <!-- Header Bar -->
  <rect x="250" y="150" width="700" height="48" rx="16" fill="#1f2937"/>
  <circle cx="280" cy="174" r="6" fill="#ef4444"/>
  <circle cx="300" cy="174" r="6" fill="#f59e0b"/>
  <circle cx="320" cy="174" r="6" fill="#10b981"/>
  <text x="350" y="179" fill="#9ca3af" font-family="monospace" font-size="14">codehaven://visual-studio/{style}</text>

  <!-- Visual Elements -->
  <circle cx="600" cy="290" r="45" fill="#0369a1" stroke="#38bdf8" stroke-width="3"/>
  <text x="600" y="296" text-anchor="middle" fill="#ffffff" font-family="monospace" font-size="20" font-weight="bold">AI</text>

  <rect x="340" y="380" width="160" height="60" rx="8" fill="#1e293b" stroke="#38bdf8" stroke-width="1.5"/>
  <text x="420" y="415" text-anchor="middle" fill="#38bdf8" font-family="monospace" font-size="14">NODE_01</text>

  <rect x="700" y="380" width="160" height="60" rx="8" fill="#1e293b" stroke="#10b981" stroke-width="1.5"/>
  <text x="780" y="415" text-anchor="middle" fill="#10b981" font-family="monospace" font-size="14">NODE_02</text>

  <line x1="570" y1="325" x2="440" y2="380" stroke="#38bdf8" stroke-width="2" stroke-dasharray="4,4"/>
  <line x1="630" y1="325" x2="760" y2="380" stroke="#10b981" stroke-width="2" stroke-dasharray="4,4"/>

  <!-- Prompt Label -->
  <text x="600" y="480" text-anchor="middle" fill="#f3f4f6" font-family="monospace" font-size="16" font-weight="bold">{safe_prompt}</text>
  <text x="600" y="505" text-anchor="middle" fill="#6b7280" font-family="monospace" font-size="12">Rendered in CodeHaven Offline Studio</text>
</svg>"""


image_service = ImageService()
