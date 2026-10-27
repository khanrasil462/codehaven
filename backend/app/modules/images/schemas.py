from pydantic import BaseModel, Field


class ImageGenerateRequest(BaseModel):
    prompt: str = Field(..., description="Prompt describing the diagram, visualization, or image to generate")
    engine: str = Field(
        "auto",
        description="'ai_diffusion' for real AI image art, 'vector_diagram' for SVG architecture/diagrams, 'auto' to infer",
    )
    style: str = Field(
        "cyberpunk",
        description="Visual style: 'cyberpunk', 'photorealistic', '3d_render', 'anime', 'architecture', 'datastructure', 'flowchart', 'vector', 'ui_mockup'",
    )
    aspect_ratio: str = Field("16:9", description="'16:9', '1:1', or '4:3'")
    theme: str = Field("terminal", description="'terminal', 'dark', 'blueprint', or 'neon'")
    model: str | None = Field(None, description="Optional local LLM model override")


class ImageItem(BaseModel):
    id: str
    prompt: str
    style: str
    format: str = "svg"  # "svg", "jpeg", "png"
    created_at: str
    svg_content: str | None = None
    image_url: str | None = None
    title: str = ""
    engine: str = "vector"


class ImageGenerateResponse(BaseModel):
    image: ImageItem
    explanation: str = ""
