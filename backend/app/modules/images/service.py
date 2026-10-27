import json
import uuid
from datetime import datetime
from pathlib import Path

from app.config import settings
from app.core.ollama_client import ollama_client
from app.modules.images.diagram import parse_spec, render as render_diagram
from app.modules.images.schemas import ImageGenerateRequest, ImageItem, ImageGenerateResponse

IMAGES_DIR = settings.data_dir / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
CATALOG_PATH = IMAGES_DIR / "images.json"


SYSTEM_PROMPT = """You turn a request into a diagram for draw.io. Reply with JSON only.
Schema: {"title": str, "direction": "TB" or "LR", "nodes": [{"id": str, "label": str, "kind": str}], "edges": [{"from": id, "to": id, "label": str}]}

Rules:
- 5 to 14 nodes. Labels are 1 to 4 plain words that come from the request. Ids are n1, n2, n3 ...
- kind is one of: start, end, process, decision, database, io, external.
  start/end = first and last step of a flow. decision = a yes/no question; its two edges are labelled "Yes" and "No".
  database = database, cache or storage. io = input or output. external = a person, browser or third-party system.
- Every edge uses ids that exist in nodes. Every node has an edge. Edges follow the flow.
- Do not make one long line. Real diagrams branch: one node points to several others, and branches can join again.
- Use only the things named in the request. Do not copy the examples.

Example 1 request: online shop checkout
Example 1 reply:
{"title": "Checkout", "direction": "TB", "nodes": [{"id": "n1", "label": "Start", "kind": "start"}, {"id": "n2", "label": "Add items to cart", "kind": "process"}, {"id": "n3", "label": "Payment accepted?", "kind": "decision"}, {"id": "n4", "label": "Send receipt", "kind": "io"}, {"id": "n5", "label": "Show payment error", "kind": "process"}, {"id": "n6", "label": "End", "kind": "end"}], "edges": [{"from": "n1", "to": "n2"}, {"from": "n2", "to": "n3"}, {"from": "n3", "to": "n4", "label": "Yes"}, {"from": "n3", "to": "n5", "label": "No"}, {"from": "n5", "to": "n2"}, {"from": "n4", "to": "n6"}]}

Example 2 request: blog website architecture
Example 2 reply:
{"title": "Blog architecture", "direction": "LR", "nodes": [{"id": "n1", "label": "Reader", "kind": "external"}, {"id": "n2", "label": "Web server", "kind": "process"}, {"id": "n3", "label": "Posts API", "kind": "process"}, {"id": "n4", "label": "Comments API", "kind": "process"}, {"id": "n5", "label": "Database", "kind": "database"}, {"id": "n6", "label": "Cache", "kind": "database"}], "edges": [{"from": "n1", "to": "n2"}, {"from": "n2", "to": "n3"}, {"from": "n2", "to": "n4"}, {"from": "n3", "to": "n5"}, {"from": "n4", "to": "n5"}, {"from": "n3", "to": "n6"}]}
"""

HINTS = {
    "flowchart": "Make a flowchart with a start, a few steps, decisions where needed, and an end.",
    "architecture": "Make a system architecture diagram: users, services, databases and external systems. Use direction LR.",
    "tree": "Make a tree or hierarchy: each parent points to its children. Use process nodes only.",
    "process": "Make a step-by-step process or sequence of stages in order.",
}


def _is_chain(spec: dict) -> bool:
    out: dict[str, int] = {}
    for e in spec["edges"]:
        out[e.src] = out.get(e.src, 0) + 1
    return all(c <= 1 for c in out.values())


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
        hint = HINTS.get(req.style, HINTS["flowchart"])
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"{hint}\nRequest: {req.prompt.strip()}"},
        ]
        options = {"temperature": 0.15, "num_predict": 1400, "num_ctx": 4096}

        spec = None
        last_error = "The model did not return a diagram."
        for attempt in range(2):
            try:
                raw = await ollama_client.chat(messages, model=model, options=options, json_mode=True)
                spec = parse_spec(raw)
                if _is_chain(spec) and len(spec["nodes"]) > 5 and req.style in ("architecture", "tree") and attempt == 0:
                    messages.append({"role": "assistant", "content": raw})
                    messages.append({"role": "user", "content": "That is one straight line. Redraw it so it branches, with one node pointing to several others."})
                    spec = None
                    continue
                break
            except (ValueError, KeyError) as exc:  # includes JSON decode errors
                last_error = str(exc)
                options = {**options, "temperature": 0.4}
        if spec is None:
            raise ValueError(f"{last_error} Try again, or switch to Deep mode for a better result.")

        if req.direction in ("TB", "LR"):
            spec["direction"] = req.direction
        elif req.style == "architecture":
            spec["direction"] = "LR"

        svg_content, xml = render_diagram(spec)

        image_id = str(uuid.uuid4())
        (IMAGES_DIR / f"{image_id}.svg").write_text(svg_content, encoding="utf-8")
        title = spec["title"] or req.prompt.split("\n")[0][:60].strip() or "Diagram"
        item = ImageItem(
            id=image_id,
            prompt=req.prompt,
            style=req.style,
            format="svg",
            created_at=datetime.now().isoformat(),
            svg_content=svg_content,
            title=title,
            mxfile=xml,
        )
        catalog = self._read_catalog()
        catalog.insert(0, item.model_dump())
        self._write_catalog(catalog)
        return ImageGenerateResponse(
            image=item,
            explanation=f"Drew {len(spec['nodes'])} shapes with {model}. Open the SVG in diagrams.net to edit it.",
        )


image_service = ImageService()
