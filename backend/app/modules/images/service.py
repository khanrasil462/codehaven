import json
import random
import re
import urllib.parse
import uuid
from datetime import datetime
from pathlib import Path

import httpx

from app.config import settings
from app.modules.images.schemas import ImageGenerateRequest, ImageItem, ImageGenerateResponse

IMAGES_DIR = settings.data_dir / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
CATALOG_PATH = IMAGES_DIR / "images.json"


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

    def get_image(self, image_id: str) -> ImageItem | None:
        items = self._read_catalog()
        for i in items:
            if i.get("id") == image_id:
                return ImageItem(**i)
        return None

    def delete_image(self, image_id: str) -> bool:
        items = self._read_catalog()
        new_items = [i for i in items if i.get("id") != image_id]
        if len(new_items) != len(items):
            self._write_catalog(new_items)
            for ext in [".svg", ".jpg", ".jpeg", ".png"]:
                f = IMAGES_DIR / f"{image_id}{ext}"
                if f.exists():
                    f.unlink()
            return True
        return False

    async def generate_image(self, req: ImageGenerateRequest) -> ImageGenerateResponse:
        # Determine engine: ai_diffusion vs vector_diagram
        use_diffusion = False
        if req.engine == "ai_diffusion":
            use_diffusion = True
        elif req.engine == "vector_diagram":
            use_diffusion = False
        else:
            # Auto-infer
            diagram_keywords = [
                "diagram", "architecture", "flowchart", "flow", "structure", "tree", "bst",
                "gitflow", "schema", "database", "sequence", "pipeline", "wireframe", "uml",
            ]
            prompt_lower = req.prompt.lower()
            if req.style in ["architecture", "datastructure", "flowchart", "ui_mockup", "vector"]:
                use_diffusion = False
            elif any(k in prompt_lower for k in diagram_keywords):
                use_diffusion = False
            else:
                use_diffusion = True

        if use_diffusion:
            try:
                return await self._generate_ai_diffusion(req)
            except Exception as e:
                # If network fails or timeout, fall back to procedural vector diagram
                res = self._generate_vector_diagram(req)
                res.explanation = f"Network unavailable for cloud diffusion ({e}); rendered offline vector illustration."
                return res
        else:
            return self._generate_vector_diagram(req)

    async def _generate_ai_diffusion(self, req: ImageGenerateRequest) -> ImageGenerateResponse:
        # Determine width & height
        w, h = 1024, 576  # 16:9 default
        if req.aspect_ratio == "1:1":
            w, h = 768, 768
        elif req.aspect_ratio == "4:3":
            w, h = 800, 600

        # Enhance prompt based on style & theme
        style_prompts = {
            "cyberpunk": "cyberpunk style, neon emerald and electric cyan glowing lights, dark obsidian background, detailed matrix circuitry, octane render, 8k",
            "photorealistic": "photorealistic, hyper-detailed, cinematic volumetric lighting, 8k resolution, professional photography, studio depth of field",
            "3d_render": "3D isometric render, smooth materials, ambient occlusion, beautiful volumetric lighting, Blender octane 8k, modern aesthetic",
            "anime": "modern anime illustration style, vibrant colors, detailed scenery, Makoto Shinkai lighting, sharp focus",
            "vector": "clean digital vector art, vibrant gradients, modern tech graphic, crisp lines, award winning illustration",
        }
        enhancement = style_prompts.get(req.style, "high quality, digital art, highly detailed, 4k, vibrant modern tech aesthetics")

        full_prompt = f"{req.prompt}, {enhancement}"
        encoded_prompt = urllib.parse.quote(full_prompt)
        seed = random.randint(10000, 999999)
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={w}&height={h}&nologo=true&seed={seed}&model=flux"

        async with httpx.AsyncClient(timeout=25.0) as client:
            resp = await client.get(url, headers={"User-Agent": "CodeHaven/1.0"})
            if resp.status_code != 200:
                raise RuntimeError(f"Diffusion API returned HTTP {resp.status_code}")
            image_bytes = resp.content

        image_id = str(uuid.uuid4())
        file_path = IMAGES_DIR / f"{image_id}.jpg"
        file_path.write_bytes(image_bytes)

        title = req.prompt.split("\n")[0][:60].strip() or "Generated AI Artwork"
        item = ImageItem(
            id=image_id,
            prompt=req.prompt,
            style=req.style,
            format="jpeg",
            created_at=datetime.now().isoformat(),
            image_url=f"/api/images/{image_id}/file",
            title=title,
            engine="ai_diffusion",
        )

        catalog = self._read_catalog()
        catalog.insert(0, item.model_dump())
        self._write_catalog(catalog)

        return ImageGenerateResponse(
            image=item,
            explanation=f"Generated photorealistic AI artwork using Flux model ({w}x{h}).",
        )

    def _generate_vector_diagram(self, req: ImageGenerateRequest) -> ImageGenerateResponse:
        prompt_lower = req.prompt.lower()
        viewbox = "0 0 1200 675"
        if req.aspect_ratio == "1:1":
            viewbox = "0 0 800 800"
        elif req.aspect_ratio == "4:3":
            viewbox = "0 0 1024 768"

        # Theme color pallete
        is_neon = req.theme == "neon"
        is_blueprint = req.theme == "blueprint"
        primary_color = "#38bdf8" if not is_neon else "#00f0ff"
        accent_color = "#10b981" if not is_neon else "#ff007f"
        bg_start = "#0a0f1d" if not is_blueprint else "#0b2046"
        bg_end = "#050811" if not is_blueprint else "#061329"

        if "microservice" in prompt_lower or "api gateway" in prompt_lower or ("order" in prompt_lower and "service" in prompt_lower):
            svg = self._render_microservices_svg(req.prompt, viewbox, primary_color, accent_color, bg_start, bg_end)
            diag_type = "Microservices Architecture"
        elif "tree" in prompt_lower or "bst" in prompt_lower or "avl" in prompt_lower or "binary search" in prompt_lower:
            svg = self._render_bst_svg(req.prompt, viewbox, primary_color, accent_color, bg_start, bg_end)
            diag_type = "Binary Search Tree"
        elif "oauth" in prompt_lower or "token" in prompt_lower or "auth flow" in prompt_lower:
            svg = self._render_oauth_svg(req.prompt, viewbox, primary_color, accent_color, bg_start, bg_end)
            diag_type = "OAuth 2.0 Sequence Flow"
        elif "git" in prompt_lower or "branch" in prompt_lower or "gitflow" in prompt_lower:
            svg = self._render_gitflow_svg(req.prompt, viewbox, primary_color, accent_color, bg_start, bg_end)
            diag_type = "GitFlow Branching Strategy"
        elif "lifecycle" in prompt_lower or "react" in prompt_lower or "state machine" in prompt_lower:
            svg = self._render_lifecycle_svg(req.prompt, viewbox, primary_color, accent_color, bg_start, bg_end)
            diag_type = "State Machine & Lifecycle"
        else:
            svg = self._render_dynamic_pipeline_svg(req.prompt, viewbox, primary_color, accent_color, bg_start, bg_end)
            diag_type = "System Pipeline Architecture"

        image_id = str(uuid.uuid4())
        svg_file = IMAGES_DIR / f"{image_id}.svg"
        svg_file.write_text(svg, encoding="utf-8")

        title = req.prompt.split("\n")[0][:60].strip() or f"{diag_type} Diagram"
        item = ImageItem(
            id=image_id,
            prompt=req.prompt,
            style=req.style,
            format="svg",
            created_at=datetime.now().isoformat(),
            svg_content=svg,
            image_url=f"/api/images/{image_id}/file",
            title=title,
            engine="vector_diagram",
        )

        catalog = self._read_catalog()
        catalog.insert(0, item.model_dump())
        self._write_catalog(catalog)

        return ImageGenerateResponse(
            image=item,
            explanation=f"Generated high-resolution {diag_type} vector diagram.",
        )

    # -------------------------------------------------------------
    # PROCEDURAL VECTOR DIAGRAM GENERATORS
    # -------------------------------------------------------------

    def _render_microservices_svg(self, prompt: str, viewbox: str, c1: str, c2: str, bg1: str, bg2: str) -> str:
        safe_title = "Distributed Microservices Architecture"
        return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}" width="100%" height="100%">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{bg1}" />
      <stop offset="100%" stop-color="{bg2}" />
    </linearGradient>
    <linearGradient id="gw" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="{c1}" />
      <stop offset="100%" stop-color="{c2}" />
    </linearGradient>
    <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 10 5 L 0 9 z" fill="{c1}" />
    </marker>
    <marker id="arrow-green" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 10 5 L 0 9 z" fill="{c2}" />
    </marker>
    <filter id="card-shadow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="6" stdDeviation="8" flood-color="{c1}" flood-opacity="0.18"/>
    </filter>
  </defs>

  <!-- Background -->
  <rect width="100%" height="100%" fill="url(#bg)"/>

  <!-- Grid Pattern -->
  <g opacity="0.08" stroke="#38bdf8" stroke-width="1">
    <line x1="0" y1="100" x2="1200" y2="100" /><line x1="0" y1="200" x2="1200" y2="200" />
    <line x1="0" y1="300" x2="1200" y2="300" /><line x1="0" y1="400" x2="1200" y2="400" />
    <line x1="0" y1="500" x2="1200" y2="500" /><line x1="0" y1="600" x2="1200" y2="600" />
    <line x1="200" y1="0" x2="200" y2="675" /><line x1="400" y1="0" x2="400" y2="675" />
    <line x1="600" y1="0" x2="600" y2="675" /><line x1="800" y1="0" x2="800" y2="675" />
    <line x1="1000" y1="0" x2="1000" y2="675" />
  </g>

  <!-- Title Header Bar -->
  <rect x="40" y="25" width="1120" height="50" rx="10" fill="#111827" stroke="#1f2937" stroke-width="1"/>
  <circle cx="65" cy="50" r="6" fill="#ef4444"/>
  <circle cx="85" cy="50" r="6" fill="#f59e0b"/>
  <circle cx="105" cy="50" r="6" fill="#10b981"/>
  <text x="135" y="56" fill="#f3f4f6" font-family="'JetBrains Mono', monospace" font-size="16" font-weight="bold">{safe_title}</text>
  <text x="1130" y="55" text-anchor="end" fill="{c1}" font-family="monospace" font-size="12">STATUS: HEALTHY · PORT 443</text>

  <!-- Layer 1: Client Ingress -->
  <rect x="50" y="240" width="160" height="90" rx="12" fill="#1e293b" stroke="{c1}" stroke-width="2" filter="url(#card-shadow)"/>
  <text x="130" y="275" text-anchor="middle" fill="#f9fafb" font-family="system-ui" font-size="15" font-weight="bold">📱 Clients</text>
  <text x="130" y="300" text-anchor="middle" fill="#94a3b8" font-family="monospace" font-size="12">Web / Mobile / CLI</text>

  <!-- Connectors Client -> Gateway -->
  <line x1="210" y1="285" x2="270" y2="285" stroke="{c1}" stroke-width="2.5" marker-end="url(#arrow)"/>
  <text x="240" y="275" text-anchor="middle" fill="#94a3b8" font-family="monospace" font-size="10">HTTPS/WSS</text>

  <!-- Layer 2: API Gateway -->
  <rect x="280" y="160" width="170" height="250" rx="14" fill="#0f172a" stroke="url(#gw)" stroke-width="2.5" filter="url(#card-shadow)"/>
  <text x="365" y="195" text-anchor="middle" fill="{c1}" font-family="system-ui" font-size="16" font-weight="bold">🛡️ API GATEWAY</text>
  <line x1="300" y1="210" x2="430" y2="210" stroke="#334155" stroke-width="1"/>
  <text x="365" y="240" text-anchor="middle" fill="#e2e8f0" font-family="monospace" font-size="12">• Reverse Proxy</text>
  <text x="365" y="270" text-anchor="middle" fill="#e2e8f0" font-family="monospace" font-size="12">• JWT Auth Verification</text>
  <text x="365" y="300" text-anchor="middle" fill="#e2e8f0" font-family="monospace" font-size="12">• Rate Limiter (Token)</text>
  <text x="365" y="330" text-anchor="middle" fill="#e2e8f0" font-family="monospace" font-size="12">• SSL Termination</text>
  <rect x="310" y="360" width="110" height="26" rx="6" fill="#1e3a5f"/>
  <text x="365" y="377" text-anchor="middle" fill="{c1}" font-family="monospace" font-size="11">gRPC / REST</text>

  <!-- Connectors Gateway -> Microservices -->
  <line x1="450" y1="200" x2="540" y2="155" stroke="{c1}" stroke-width="2" marker-end="url(#arrow)"/>
  <line x1="450" y1="285" x2="540" y2="285" stroke="{c1}" stroke-width="2" marker-end="url(#arrow)"/>
  <line x1="450" y1="365" x2="540" y2="415" stroke="{c1}" stroke-width="2" marker-end="url(#arrow)"/>

  <!-- Layer 3: Microservices -->
  <!-- Service 1: Auth Service -->
  <rect x="550" y="115" width="200" height="80" rx="10" fill="#1e293b" stroke="{c1}" stroke-width="1.8" filter="url(#card-shadow)"/>
  <text x="650" y="145" text-anchor="middle" fill="#f8fafc" font-family="system-ui" font-size="14" font-weight="bold">🔑 Auth &amp; IAM Service</text>
  <text x="650" y="170" text-anchor="middle" fill="#94a3b8" font-family="monospace" font-size="11">OAuth2 · JWT · Bcrypt</text>

  <!-- Service 2: Order Service -->
  <rect x="550" y="245" width="200" height="80" rx="10" fill="#1e293b" stroke="{c2}" stroke-width="1.8" filter="url(#card-shadow)"/>
  <text x="650" y="275" text-anchor="middle" fill="#f8fafc" font-family="system-ui" font-size="14" font-weight="bold">📦 Order &amp; Catalog</text>
  <text x="650" y="300" text-anchor="middle" fill="#94a3b8" font-family="monospace" font-size="11">FastAPI · CQRS · Redis</text>

  <!-- Service 3: Notification Service -->
  <rect x="550" y="375" width="200" height="80" rx="10" fill="#1e293b" stroke="#f59e0b" stroke-width="1.8" filter="url(#card-shadow)"/>
  <text x="650" y="405" text-anchor="middle" fill="#f8fafc" font-family="system-ui" font-size="14" font-weight="bold">🔔 Event Notifier</text>
  <text x="650" y="430" text-anchor="middle" fill="#94a3b8" font-family="monospace" font-size="11">WebSockets · Emails</text>

  <!-- Connectors Services -> Message Broker -->
  <line x1="750" y1="285" x2="840" y2="285" stroke="{c2}" stroke-width="2" marker-end="url(#arrow-green)"/>
  <line x1="750" y1="415" x2="840" y2="330" stroke="#f59e0b" stroke-width="2" marker-end="url(#arrow)"/>

  <!-- Layer 4: Event Bus & Storage -->
  <!-- Message Broker -->
  <rect x="850" y="240" width="170" height="100" rx="12" fill="#0f172a" stroke="{c2}" stroke-width="2" filter="url(#card-shadow)"/>
  <text x="935" y="275" text-anchor="middle" fill="{c2}" font-family="system-ui" font-size="15" font-weight="bold">⚡ RabbitMQ / Kafka</text>
  <text x="935" y="300" text-anchor="middle" fill="#e2e8f0" font-family="monospace" font-size="11">Event Streaming Bus</text>
  <text x="935" y="320" text-anchor="middle" fill="#64748b" font-family="monospace" font-size="10">order.created → billing</text>

  <!-- Databases -->
  <rect x="850" y="110" width="170" height="90" rx="12" fill="#1e293b" stroke="{c1}" stroke-width="1.8"/>
  <text x="935" y="145" text-anchor="middle" fill="#f8fafc" font-family="system-ui" font-size="14" font-weight="bold">🗄️ PostgreSQL</text>
  <text x="935" y="170" text-anchor="middle" fill="#94a3b8" font-family="monospace" font-size="11">Primary ACID Store</text>

  <rect x="850" y="380" width="170" height="80" rx="12" fill="#1e293b" stroke="#ef4444" stroke-width="1.8"/>
  <text x="935" y="415" text-anchor="middle" fill="#f8fafc" font-family="system-ui" font-size="14" font-weight="bold">⚡ Redis Cache</text>
  <text x="935" y="440" text-anchor="middle" fill="#94a3b8" font-family="monospace" font-size="11">In-Memory Sub-millisecond</text>

  <!-- Connectors Auth -> Postgres & Redis -->
  <line x1="750" y1="155" x2="850" y2="155" stroke="{c1}" stroke-width="1.8" stroke-dasharray="4,4"/>
  <line x1="935" y1="340" x2="935" y2="380" stroke="#ef4444" stroke-width="1.5" stroke-dasharray="3,3"/>

  <!-- Footer Banner -->
  <rect x="40" y="585" width="1120" height="55" rx="10" fill="#0b1120" stroke="#1e293b" stroke-width="1"/>
  <text x="60" y="618" fill="#94a3b8" font-family="monospace" font-size="13">Architectural Pattern: Microservices with Synchronous REST Ingress + Asynchronous AMQP Events</text>
  <text x="1140" y="618" text-anchor="end" fill="{c2}" font-family="monospace" font-size="13">CodeHaven Vector Studio 100% Offline</text>
</svg>"""

    def _render_bst_svg(self, prompt: str, viewbox: str, c1: str, c2: str, bg1: str, bg2: str) -> str:
        safe_title = "Self-Balancing Binary Search Tree (AVL Structure)"
        return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}" width="100%" height="100%">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{bg1}" />
      <stop offset="100%" stop-color="{bg2}" />
    </linearGradient>
    <filter id="node-glow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="0" stdDeviation="8" flood-color="{c1}" flood-opacity="0.4"/>
    </filter>
  </defs>

  <rect width="100%" height="100%" fill="url(#bg)"/>

  <!-- Header -->
  <rect x="40" y="25" width="1120" height="50" rx="10" fill="#111827" stroke="#1f2937"/>
  <circle cx="65" cy="50" r="6" fill="#ef4444"/><circle cx="85" cy="50" r="6" fill="#f59e0b"/><circle cx="105" cy="50" r="6" fill="#10b981"/>
  <text x="135" y="56" fill="#f3f4f6" font-family="'JetBrains Mono', monospace" font-size="16" font-weight="bold">{safe_title}</text>
  <text x="1130" y="55" text-anchor="end" fill="{c2}" font-family="monospace" font-size="12">COMPLEXITY: O(log N) · BALANCED (BF=0)</text>

  <!-- Branch Connecting Edges -->
  <!-- Root (600, 150) -> L1 Left (380, 270) & L1 Right (820, 270) -->
  <line x1="600" y1="150" x2="380" y2="270" stroke="{c1}" stroke-width="3"/>
  <line x1="600" y1="150" x2="820" y2="270" stroke="{c1}" stroke-width="3"/>

  <!-- L1 Left (380, 270) -> L2 (260, 400) & L2 (500, 400) -->
  <line x1="380" y1="270" x2="260" y2="400" stroke="{c2}" stroke-width="2.5"/>
  <line x1="380" y1="270" x2="500" y2="400" stroke="{c2}" stroke-width="2.5"/>

  <!-- L1 Right (820, 270) -> L2 (700, 400) & L2 (940, 400) -->
  <line x1="820" y1="270" x2="700" y2="400" stroke="{c2}" stroke-width="2.5"/>
  <line x1="820" y1="270" x2="940" y2="400" stroke="{c2}" stroke-width="2.5"/>

  <!-- L2 Leaves -->
  <line x1="260" y1="400" x2="190" y2="520" stroke="#64748b" stroke-width="2" stroke-dasharray="3,3"/>
  <line x1="260" y1="400" x2="310" y2="520" stroke="#64748b" stroke-width="2" stroke-dasharray="3,3"/>
  <line x1="940" y1="400" x2="890" y2="520" stroke="#64748b" stroke-width="2" stroke-dasharray="3,3"/>
  <line x1="940" y1="400" x2="990" y2="520" stroke="#64748b" stroke-width="2" stroke-dasharray="3,3"/>

  <!-- Tree Nodes -->
  <!-- ROOT: 50 -->
  <circle cx="600" cy="150" r="38" fill="#0f172a" stroke="{c1}" stroke-width="3.5" filter="url(#node-glow)"/>
  <text x="600" y="157" text-anchor="middle" fill="#ffffff" font-family="monospace" font-size="22" font-weight="bold">50</text>
  <text x="600" y="100" text-anchor="middle" fill="{c1}" font-family="monospace" font-size="12">ROOT · BF: 0</text>

  <!-- LEVEL 1: Left 30, Right 70 -->
  <circle cx="380" cy="270" r="34" fill="#0f172a" stroke="{c2}" stroke-width="3"/>
  <text x="380" y="277" text-anchor="middle" fill="#ffffff" font-family="monospace" font-size="20" font-weight="bold">30</text>
  <text x="380" y="225" text-anchor="middle" fill="{c2}" font-family="monospace" font-size="11">BF: 0 (Left)</text>

  <circle cx="820" cy="270" r="34" fill="#0f172a" stroke="{c2}" stroke-width="3"/>
  <text x="820" y="277" text-anchor="middle" fill="#ffffff" font-family="monospace" font-size="20" font-weight="bold">70</text>
  <text x="820" y="225" text-anchor="middle" fill="{c2}" font-family="monospace" font-size="11">BF: 0 (Right)</text>

  <!-- LEVEL 2: 20, 40, 60, 80 -->
  <circle cx="260" cy="400" r="30" fill="#1e293b" stroke="{c1}" stroke-width="2.5"/>
  <text x="260" y="407" text-anchor="middle" fill="#e2e8f0" font-family="monospace" font-size="18" font-weight="bold">20</text>

  <circle cx="500" cy="400" r="30" fill="#1e293b" stroke="{c1}" stroke-width="2.5"/>
  <text x="500" y="407" text-anchor="middle" fill="#e2e8f0" font-family="monospace" font-size="18" font-weight="bold">40</text>

  <circle cx="700" cy="400" r="30" fill="#1e293b" stroke="{c1}" stroke-width="2.5"/>
  <text x="700" y="407" text-anchor="middle" fill="#e2e8f0" font-family="monospace" font-size="18" font-weight="bold">60</text>

  <circle cx="940" cy="400" r="30" fill="#1e293b" stroke="{c1}" stroke-width="2.5"/>
  <text x="940" y="407" text-anchor="middle" fill="#e2e8f0" font-family="monospace" font-size="18" font-weight="bold">80</text>

  <!-- LEVEL 3: Leaves 10, 25, 75, 95 -->
  <circle cx="190" cy="520" r="22" fill="#0f172a" stroke="#64748b" stroke-width="2"/>
  <text x="190" y="526" text-anchor="middle" fill="#94a3b8" font-family="monospace" font-size="14">10</text>

  <circle cx="310" cy="520" r="22" fill="#0f172a" stroke="#64748b" stroke-width="2"/>
  <text x="310" y="526" text-anchor="middle" fill="#94a3b8" font-family="monospace" font-size="14">25</text>

  <circle cx="890" cy="520" r="22" fill="#0f172a" stroke="#64748b" stroke-width="2"/>
  <text x="890" y="526" text-anchor="middle" fill="#94a3b8" font-family="monospace" font-size="14">75</text>

  <circle cx="990" cy="520" r="22" fill="#0f172a" stroke="#64748b" stroke-width="2"/>
  <text x="990" y="526" text-anchor="middle" fill="#94a3b8" font-family="monospace" font-size="14">95</text>

  <!-- Legend & Properties -->
  <rect x="40" y="590" width="1120" height="55" rx="10" fill="#0b1120" stroke="#1e293b"/>
  <text x="60" y="623" fill="#94a3b8" font-family="monospace" font-size="13">BST Property: Left &lt; Root &lt; Right | In-Order Traversal: [10, 20, 25, 30, 40, 50, 60, 70, 75, 80, 95]</text>
  <text x="1140" y="623" text-anchor="end" fill="{c2}" font-family="monospace" font-size="13">Verified Sorted Sequence</text>
</svg>"""

    def _render_oauth_svg(self, prompt: str, viewbox: str, c1: str, c2: str, bg1: str, bg2: str) -> str:
        safe_title = "OAuth 2.0 Authorization Code Flow"
        return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}" width="100%" height="100%">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{bg1}" />
      <stop offset="100%" stop-color="{bg2}" />
    </linearGradient>
    <marker id="ar1" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 10 5 L 0 9 z" fill="{c1}" />
    </marker>
    <marker id="ar2" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 10 5 L 0 9 z" fill="{c2}" />
    </marker>
  </defs>

  <rect width="100%" height="100%" fill="url(#bg)"/>

  <!-- Header -->
  <rect x="40" y="25" width="1120" height="50" rx="10" fill="#111827" stroke="#1f2937"/>
  <circle cx="65" cy="50" r="6" fill="#ef4444"/><circle cx="85" cy="50" r="6" fill="#f59e0b"/><circle cx="105" cy="50" r="6" fill="#10b981"/>
  <text x="135" y="56" fill="#f3f4f6" font-family="'JetBrains Mono', monospace" font-size="16" font-weight="bold">{safe_title}</text>
  <text x="1130" y="55" text-anchor="end" fill="{c1}" font-family="monospace" font-size="12">RFC 6749 · PKCE ENFORCED</text>

  <!-- Actors (3 Columns) -->
  <!-- Actor 1: Browser / User -->
  <rect x="120" y="105" width="200" height="60" rx="10" fill="#1e293b" stroke="{c1}" stroke-width="2"/>
  <text x="220" y="140" text-anchor="middle" fill="#ffffff" font-family="system-ui" font-size="15" font-weight="bold">👤 Client / Browser</text>
  <line x1="220" y1="165" x2="220" y2="570" stroke="#334155" stroke-width="2" stroke-dasharray="6,6"/>

  <!-- Actor 2: Authorization Server -->
  <rect x="500" y="105" width="200" height="60" rx="10" fill="#1e293b" stroke="{c2}" stroke-width="2"/>
  <text x="600" y="140" text-anchor="middle" fill="#ffffff" font-family="system-ui" font-size="15" font-weight="bold">🛡️ Auth Server (IdP)</text>
  <line x1="600" y1="165" x2="600" y2="570" stroke="#334155" stroke-width="2" stroke-dasharray="6,6"/>

  <!-- Actor 3: Resource API -->
  <rect x="880" y="105" width="200" height="60" rx="10" fill="#1e293b" stroke="#f59e0b" stroke-width="2"/>
  <text x="980" y="140" text-anchor="middle" fill="#ffffff" font-family="system-ui" font-size="15" font-weight="bold">📦 Resource API</text>
  <line x1="980" y1="165" x2="980" y2="570" stroke="#334155" stroke-width="2" stroke-dasharray="6,6"/>

  <!-- Sequence Step 1: User Request Auth -->
  <line x1="220" y1="210" x2="590" y2="210" stroke="{c1}" stroke-width="2" marker-end="url(#ar1)"/>
  <text x="410" y="200" text-anchor="middle" fill="{c1}" font-family="monospace" font-size="12">1. /authorize?response_type=code&amp;client_id=...&amp;pkce</text>

  <!-- Sequence Step 2: Auth Server Returns Code -->
  <line x1="600" y1="270" x2="230" y2="270" stroke="{c2}" stroke-width="2" stroke-dasharray="4,2" marker-end="url(#ar2)"/>
  <text x="410" y="260" text-anchor="middle" fill="{c2}" font-family="monospace" font-size="12">2. Redirect: /callback?code=AUTH_CODE_XYZ</text>

  <!-- Sequence Step 3: Token Exchange -->
  <line x1="220" y1="330" x2="590" y2="330" stroke="{c1}" stroke-width="2" marker-end="url(#ar1)"/>
  <text x="410" y="320" text-anchor="middle" fill="{c1}" font-family="monospace" font-size="12">3. POST /token (code + code_verifier + client_secret)</text>

  <!-- Sequence Step 4: Token Issued -->
  <line x1="600" y1="390" x2="230" y2="390" stroke="{c2}" stroke-width="2" marker-end="url(#ar2)"/>
  <text x="410" y="380" text-anchor="middle" fill="{c2}" font-family="monospace" font-size="12">4. 200 OK: access_token (JWT) + refresh_token</text>

  <!-- Sequence Step 5: Resource Request -->
  <line x1="220" y1="460" x2="970" y2="460" stroke="#f59e0b" stroke-width="2" marker-end="url(#ar1)"/>
  <text x="600" y="450" text-anchor="middle" fill="#f59e0b" font-family="monospace" font-size="12">5. GET /api/v1/userinfo (Header: Bearer &lt;JWT&gt;)</text>

  <!-- Sequence Step 6: Resource Response -->
  <line x1="980" y1="520" x2="230" y2="520" stroke="{c2}" stroke-width="2" stroke-dasharray="4,2" marker-end="url(#ar2)"/>
  <text x="600" y="510" text-anchor="middle" fill="{c2}" font-family="monospace" font-size="12">6. 200 OK: Profile Payload (Claims verified offline via JWKS)</text>

  <!-- Footer -->
  <rect x="40" y="590" width="1120" height="55" rx="10" fill="#0b1120" stroke="#1e293b"/>
  <text x="60" y="623" fill="#94a3b8" font-family="monospace" font-size="13">Security Protocol: High-Trust Token Boundary with Cryptographic Signature Verification</text>
  <text x="1140" y="623" text-anchor="end" fill="{c1}" font-family="monospace" font-size="13">CodeHaven Vector Engine</text>
</svg>"""

    def _render_gitflow_svg(self, prompt: str, viewbox: str, c1: str, c2: str, bg1: str, bg2: str) -> str:
        safe_title = "Enterprise GitFlow Branching Model"
        return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}" width="100%" height="100%">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{bg1}" />
      <stop offset="100%" stop-color="{bg2}" />
    </linearGradient>
  </defs>

  <rect width="100%" height="100%" fill="url(#bg)"/>

  <!-- Header -->
  <rect x="40" y="25" width="1120" height="50" rx="10" fill="#111827" stroke="#1f2937"/>
  <circle cx="65" cy="50" r="6" fill="#ef4444"/><circle cx="85" cy="50" r="6" fill="#f59e0b"/><circle cx="105" cy="50" r="6" fill="#10b981"/>
  <text x="135" y="56" fill="#f3f4f6" font-family="'JetBrains Mono', monospace" font-size="16" font-weight="bold">{safe_title}</text>
  <text x="1130" y="55" text-anchor="end" fill="{c2}" font-family="monospace" font-size="12">STABLE TRUNK · FEATURE ISOLATION</text>

  <!-- Branch Tracks (Lanes) -->
  <!-- 1. Main / Production (Green) -->
  <text x="160" y="165" text-anchor="end" fill="#10b981" font-family="monospace" font-size="14" font-weight="bold">main / prod</text>
  <line x1="180" y1="160" x2="1100" y2="160" stroke="#10b981" stroke-width="4"/>

  <!-- 2. Hotfix (Red) -->
  <text x="160" y="255" text-anchor="end" fill="#ef4444" font-family="monospace" font-size="14" font-weight="bold">hotfix/*</text>
  <line x1="180" y1="250" x2="1100" y2="250" stroke="#ef4444" stroke-width="3" stroke-dasharray="6,4"/>

  <!-- 3. Develop (Cyan) -->
  <text x="160" y="345" text-anchor="end" fill="{c1}" font-family="monospace" font-size="14" font-weight="bold">develop</text>
  <line x1="180" y1="340" x2="1100" y2="340" stroke="{c1}" stroke-width="4"/>

  <!-- 4. Feature Branches (Purple/Amber) -->
  <text x="160" y="445" text-anchor="end" fill="#a855f7" font-family="monospace" font-size="14" font-weight="bold">feature/*</text>
  <line x1="180" y1="440" x2="1100" y2="440" stroke="#a855f7" stroke-width="3" stroke-dasharray="6,4"/>

  <!-- Commits on Main -->
  <circle cx="260" cy="160" r="10" fill="#10b981" stroke="#ffffff" stroke-width="2"/>
  <rect x="235" y="115" width="50" height="22" rx="4" fill="#064e3b"/><text x="260" y="130" text-anchor="middle" fill="#a7f3d0" font-family="monospace" font-size="10">v1.0.0</text>

  <circle cx="860" cy="160" r="10" fill="#10b981" stroke="#ffffff" stroke-width="2"/>
  <rect x="835" y="115" width="50" height="22" rx="4" fill="#064e3b"/><text x="860" y="130" text-anchor="middle" fill="#a7f3d0" font-family="monospace" font-size="10">v1.1.0</text>

  <!-- Commits on Develop -->
  <circle cx="260" cy="340" r="8" fill="{c1}"/>
  <circle cx="420" cy="340" r="8" fill="{c1}"/>
  <circle cx="680" cy="340" r="8" fill="{c1}"/>
  <circle cx="800" cy="340" r="8" fill="{c1}"/>
  <circle cx="1000" cy="340" r="8" fill="{c1}"/>

  <!-- Feature Branch Diverge & Merge -->
  <path d="M 260 340 C 300 340, 320 440, 360 440" fill="none" stroke="#a855f7" stroke-width="2.5"/>
  <circle cx="360" cy="440" r="8" fill="#a855f7"/>
  <circle cx="480" cy="440" r="8" fill="#a855f7"/>
  <circle cx="600" cy="440" r="8" fill="#a855f7"/>
  <path d="M 600 440 C 640 440, 660 340, 680 340" fill="none" stroke="#a855f7" stroke-width="2.5"/>
  <text x="480" y="475" text-anchor="middle" fill="#d8b4fe" font-family="monospace" font-size="11">PR #42: Feature Auth Module</text>

  <!-- Hotfix Branch Diverge & Merge directly to Main + Develop -->
  <path d="M 260 160 C 310 160, 330 250, 380 250" fill="none" stroke="#ef4444" stroke-width="2.5"/>
  <circle cx="380" cy="250" r="8" fill="#ef4444"/>
  <circle cx="520" cy="250" r="8" fill="#ef4444"/>
  <path d="M 520 250 C 560 250, 580 160, 620 160" fill="none" stroke="#ef4444" stroke-width="2.5"/>
  <circle cx="620" cy="160" r="10" fill="#10b981" stroke="#ef4444" stroke-width="2"/>
  <rect x="595" y="115" width="50" height="22" rx="4" fill="#7f1d1d"/><text x="620" y="130" text-anchor="middle" fill="#fca5a5" font-family="monospace" font-size="10">v1.0.1</text>
  <!-- Also back-merge hotfix into develop -->
  <path d="M 520 250 C 580 250, 620 340, 680 340" fill="none" stroke="#ef4444" stroke-width="2" stroke-dasharray="3,3"/>

  <!-- Release Branch Diverge to Main -->
  <path d="M 800 340 C 830 340, 840 160, 860 160" fill="none" stroke="#10b981" stroke-width="2.5"/>

  <!-- Footer -->
  <rect x="40" y="590" width="1120" height="55" rx="10" fill="#0b1120" stroke="#1e293b"/>
  <text x="60" y="623" fill="#94a3b8" font-family="monospace" font-size="13">Branch Policy: No Direct Commits to Main | All Changes Merged via Pull Request &amp; Automated CI</text>
  <text x="1140" y="623" text-anchor="end" fill="#10b981" font-family="monospace" font-size="13">Production Grade CI/CD</text>
</svg>"""

    def _render_lifecycle_svg(self, prompt: str, viewbox: str, c1: str, c2: str, bg1: str, bg2: str) -> str:
        safe_title = "Modern State Machine & Component Lifecycle"
        return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}" width="100%" height="100%">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{bg1}" />
      <stop offset="100%" stop-color="{bg2}" />
    </linearGradient>
    <marker id="m1" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 10 5 L 0 9 z" fill="{c1}" />
    </marker>
  </defs>

  <rect width="100%" height="100%" fill="url(#bg)"/>

  <!-- Header -->
  <rect x="40" y="25" width="1120" height="50" rx="10" fill="#111827" stroke="#1f2937"/>
  <circle cx="65" cy="50" r="6" fill="#ef4444"/><circle cx="85" cy="50" r="6" fill="#f59e0b"/><circle cx="105" cy="50" r="6" fill="#10b981"/>
  <text x="135" y="56" fill="#f3f4f6" font-family="'JetBrains Mono', monospace" font-size="16" font-weight="bold">{safe_title}</text>
  <text x="1130" y="55" text-anchor="end" fill="{c1}" font-family="monospace" font-size="12">DETERMINISTIC TRANSITIONS</text>

  <!-- 3 Stages: Mounting, Updating, Unmounting -->
  <!-- Stage 1: MOUNTING -->
  <rect x="70" y="110" width="310" height="430" rx="14" fill="#0f172a" stroke="{c1}" stroke-width="2"/>
  <rect x="70" y="110" width="310" height="45" rx="14" fill="#1e293b"/>
  <text x="225" y="140" text-anchor="middle" fill="{c1}" font-family="system-ui" font-size="16" font-weight="bold">🌱 1. INITIAL MOUNT</text>
  
  <rect x="100" y="180" width="250" height="55" rx="8" fill="#111827" stroke="#334155"/>
  <text x="225" y="213" text-anchor="middle" fill="#e2e8f0" font-family="monospace" font-size="13">constructor() / useState()</text>

  <line x1="225" y1="235" x2="225" y2="270" stroke="{c1}" stroke-width="2" marker-end="url(#m1)"/>

  <rect x="100" y="270" width="250" height="55" rx="8" fill="#111827" stroke="{c1}"/>
  <text x="225" y="303" text-anchor="middle" fill="#e2e8f0" font-family="monospace" font-size="13">render() / JSX Virtual DOM</text>

  <line x1="225" y1="325" x2="225" y2="360" stroke="{c1}" stroke-width="2" marker-end="url(#m1)"/>

  <rect x="100" y="360" width="250" height="55" rx="8" fill="#111827" stroke="#334155"/>
  <text x="225" y="393" text-anchor="middle" fill="#e2e8f0" font-family="monospace" font-size="13">componentDidMount()</text>
  <text x="225" y="445" text-anchor="middle" fill="#94a3b8" font-family="monospace" font-size="11">useEffect(() =&gt; {{}}, [])</text>

  <!-- Stage 2: UPDATING -->
  <rect x="445" y="110" width="310" height="430" rx="14" fill="#0f172a" stroke="{c2}" stroke-width="2"/>
  <rect x="445" y="110" width="310" height="45" rx="14" fill="#1e293b"/>
  <text x="600" y="140" text-anchor="middle" fill="{c2}" font-family="system-ui" font-size="16" font-weight="bold">⚡ 2. STATE / PROP UPDATE</text>

  <rect x="475" y="180" width="250" height="55" rx="8" fill="#111827" stroke="#334155"/>
  <text x="600" y="213" text-anchor="middle" fill="#e2e8f0" font-family="monospace" font-size="13">setState() / New Props</text>

  <line x1="600" y1="235" x2="600" y2="270" stroke="{c2}" stroke-width="2" marker-end="url(#m1)"/>

  <rect x="475" y="270" width="250" height="55" rx="8" fill="#111827" stroke="{c2}"/>
  <text x="600" y="303" text-anchor="middle" fill="#e2e8f0" font-family="monospace" font-size="13">Diffing &amp; Reconciliation</text>

  <line x1="600" y1="325" x2="600" y2="360" stroke="{c2}" stroke-width="2" marker-end="url(#m1)"/>

  <rect x="475" y="360" width="250" height="55" rx="8" fill="#111827" stroke="#334155"/>
  <text x="600" y="393" text-anchor="middle" fill="#e2e8f0" font-family="monospace" font-size="13">DOM Re-painted</text>
  <text x="600" y="445" text-anchor="middle" fill="#94a3b8" font-family="monospace" font-size="11">useEffect(() =&gt; {{}}, [deps])</text>

  <!-- Stage 3: UNMOUNTING -->
  <rect x="820" y="110" width="310" height="430" rx="14" fill="#0f172a" stroke="#ef4444" stroke-width="2"/>
  <rect x="820" y="110" width="310" height="45" rx="14" fill="#1e293b"/>
  <text x="975" y="140" text-anchor="middle" fill="#ef4444" font-family="system-ui" font-size="16" font-weight="bold">🍂 3. CLEANUP &amp; UNMOUNT</text>

  <rect x="850" y="240" width="250" height="70" rx="8" fill="#111827" stroke="#ef4444"/>
  <text x="975" y="273" text-anchor="middle" fill="#fca5a5" font-family="monospace" font-size="13">componentWillUnmount()</text>
  <text x="975" y="295" text-anchor="middle" fill="#94a3b8" font-family="monospace" font-size="11">Clear Timers &amp; Listeners</text>
  <text x="975" y="445" text-anchor="middle" fill="#94a3b8" font-family="monospace" font-size="11">return () =&gt; {{ cleanup() }}</text>

  <!-- Connectors Between Stages -->
  <path d="M 380 325 C 410 325, 415 325, 445 325" fill="none" stroke="{c1}" stroke-width="2.5" marker-end="url(#m1)"/>
  <path d="M 755 325 C 785 325, 790 325, 820 325" fill="none" stroke="#ef4444" stroke-width="2.5" marker-end="url(#m1)"/>

  <!-- Footer -->
  <rect x="40" y="590" width="1120" height="55" rx="10" fill="#0b1120" stroke="#1e293b"/>
  <text x="60" y="623" fill="#94a3b8" font-family="monospace" font-size="13">Lifecycle Contract: Strict unidirectional data flow from parent props through internal state transitions</text>
  <text x="1140" y="623" text-anchor="end" fill="{c2}" font-family="monospace" font-size="13">Zero Memory Leaks</text>
</svg>"""

    def _render_dynamic_pipeline_svg(self, prompt: str, viewbox: str, c1: str, c2: str, bg1: str, bg2: str) -> str:
        # Extract meaningful terms from prompt
        words = [w for w in re.findall(r"\b[A-Za-z0-9_-]{3,}\b", prompt) if w.lower() not in ["the", "and", "with", "for", "diagram", "showing", "from", "that", "this", "system", "using"]]
        nodes = []
        if len(words) >= 4:
            nodes = [words[0].upper(), words[1].upper(), words[2].upper(), words[3].upper()]
        elif len(words) >= 2:
            nodes = ["INGRESS", words[0].upper(), words[1].upper(), "STORAGE", "MONITORING"]
        else:
            nodes = ["INGRESS", "CORE_ENGINE", "CACHE_STORE", "PERSISTENCE", "ANALYTICS"]

        safe_prompt = prompt.replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
        if len(safe_prompt) > 80:
            safe_prompt = safe_prompt[:77] + "..."

        node_count = len(nodes)
        card_w = 170
        spacing = (1120 - (node_count * card_w)) // (node_count + 1)
        start_x = 40 + spacing

        nodes_svg = ""
        for i, node_name in enumerate(nodes):
            x = start_x + i * (card_w + spacing)
            y = 240
            color = c1 if i % 2 == 0 else c2
            badge = f"STAGE 0{i+1}"
            nodes_svg += f"""
  <g transform="translate({x}, {y})">
    <rect width="{card_w}" height="140" rx="12" fill="#0f172a" stroke="{color}" stroke-width="2"/>
    <rect width="{card_w}" height="32" rx="12" fill="#1e293b"/>
    <text x="{card_w//2}" y="22" text-anchor="middle" fill="{color}" font-family="monospace" font-size="11" font-weight="bold">{badge}</text>
    <circle cx="20" cy="65" r="5" fill="{color}"/>
    <text x="35" y="70" fill="#f8fafc" font-family="'JetBrains Mono', monospace" font-size="13" font-weight="bold">{node_name[:12]}</text>
    <line x1="20" y1="85" x2="{card_w-20}" y2="85" stroke="#334155" stroke-width="1"/>
    <text x="20" y="105" fill="#94a3b8" font-family="monospace" font-size="10">• Latency: &lt;5ms</text>
    <text x="20" y="122" fill="#94a3b8" font-family="monospace" font-size="10">• State: ACTIVE</text>
  </g>
"""
            if i < node_count - 1:
                arrow_start = x + card_w
                arrow_end = x + card_w + spacing
                arrow_y = y + 70
                nodes_svg += f"""
  <line x1="{arrow_start}" y1="{arrow_y}" x2="{arrow_end}" y2="{arrow_y}" stroke="{color}" stroke-width="2.5" marker-end="url(#arr)"/>
"""

        return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}" width="100%" height="100%">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{bg1}" />
      <stop offset="100%" stop-color="{bg2}" />
    </linearGradient>
    <marker id="arr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 10 5 L 0 9 z" fill="{c1}" />
    </marker>
  </defs>

  <rect width="100%" height="100%" fill="url(#bg)"/>

  <!-- Grid -->
  <g opacity="0.08" stroke="#38bdf8" stroke-width="1">
    <line x1="0" y1="100" x2="1200" y2="100" /><line x1="0" y1="200" x2="1200" y2="200" />
    <line x1="0" y1="300" x2="1200" y2="300" /><line x1="0" y1="400" x2="1200" y2="400" />
    <line x1="0" y1="500" x2="1200" y2="500" />
    <line x1="300" y1="0" x2="300" y2="675" /><line x1="600" y1="0" x2="600" y2="675" />
    <line x1="900" y1="0" x2="900" y2="675" />
  </g>

  <!-- Header -->
  <rect x="40" y="25" width="1120" height="50" rx="10" fill="#111827" stroke="#1f2937"/>
  <circle cx="65" cy="50" r="6" fill="#ef4444"/><circle cx="85" cy="50" r="6" fill="#f59e0b"/><circle cx="105" cy="50" r="6" fill="#10b981"/>
  <text x="135" y="56" fill="#f3f4f6" font-family="'JetBrains Mono', monospace" font-size="16" font-weight="bold">{safe_prompt}</text>
  <text x="1130" y="55" text-anchor="end" fill="{c1}" font-family="monospace" font-size="12">CUSTOM SYNTHESIS · 100% OFFLINE</text>

  <!-- Dynamic Nodes Flow -->
  {nodes_svg}

  <!-- Footer -->
  <rect x="40" y="590" width="1120" height="55" rx="10" fill="#0b1120" stroke="#1e293b"/>
  <text x="60" y="623" fill="#94a3b8" font-family="monospace" font-size="13">High-Throughput Distributed Flow Architecture with End-to-End Tracing</text>
  <text x="1140" y="623" text-anchor="end" fill="{c2}" font-family="monospace" font-size="13">CodeHaven Vector Engine</text>
</svg>"""


image_service = ImageService()
