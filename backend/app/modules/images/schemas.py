from pydantic import BaseModel, Field


class ImageGenerateRequest(BaseModel):
    prompt: str = Field(..., description="What the diagram should show")
    style: str = Field("flowchart", description="'flowchart', 'architecture', 'tree' or 'process'")
    direction: str = Field("auto", description="'auto', 'TB' (top to bottom) or 'LR' (left to right)")
    model: str | None = Field(None, description="Optional local LLM model override")


class ImageItem(BaseModel):
    id: str
    prompt: str
    style: str
    format: str = "svg"
    created_at: str
    svg_content: str
    title: str = ""
    mxfile: str = ""


class ImageGenerateResponse(BaseModel):
    image: ImageItem
    explanation: str = ""
