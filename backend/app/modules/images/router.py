from fastapi import APIRouter, HTTPException
from app.modules.images.schemas import ImageGenerateRequest, ImageGenerateResponse, ImageItem
from app.modules.images.service import image_service

router = APIRouter(prefix="/images", tags=["Image & Diagram Studio"])


@router.get("", response_model=list[ImageItem])
async def list_images() -> list[ImageItem]:
    """Lists all previously generated diagrams, visuals, and illustrations."""
    return image_service.list_images()


@router.post("/generate", response_model=ImageGenerateResponse)
async def generate_image(request: ImageGenerateRequest) -> ImageGenerateResponse:
    """Generates a high-resolution vector SVG diagram or illustration using local AI models."""
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")
    try:
        return await image_service.generate_image(request)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Image generation failed: {exc}") from exc


@router.delete("/{image_id}")
async def delete_image(image_id: str) -> dict[str, bool]:
    """Deletes a generated image from the catalog and disk."""
    success = image_service.delete_image(image_id)
    if not success:
        raise HTTPException(status_code=404, detail="Image not found")
    return {"deleted": True}
