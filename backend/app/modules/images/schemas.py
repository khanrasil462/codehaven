from pydantic import BaseModel, Field


class ImageGenerateRequest(BaseModel):
    prompt: str = Field(..., description="Prompt describing the diagram, visualization, or image to generate")
    style: str = Field(
        "vector",
        description="Visual style: 'vector', 'architecture', 'flowchart', 'datastructure', 'cyberpunk', 'ui_mockup'",
    )
    aspect_ratio: str = Field("16:9", description="'16:9', '1:1', or '4:3'")
    theme: str = Field("terminal", description="'terminal', 'dark', 'blueprint', or 'neon'")
    model: str | None = Field(None, description="Optional local LLM model override")


class ImageItem(BaseModel):
    id: str
    prompt: str
    style: str
    format: str = "svg"
    created_at: str
    svg_content: str
    title: str = ""


class ImageGenerateResponse(BaseModel):
    image: ImageItem
    explanation: str = ""
