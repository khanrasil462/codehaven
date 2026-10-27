from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from app.modules.images.schemas import ImageGenerateRequest, ImageGenerateResponse, ImageItem
from app.modules.images.service import image_service, IMAGES_DIR

router = APIRouter(prefix="/images", tags=["Image & Diagram Studio"])


@router.get("", response_model=list[ImageItem])
async def list_images() -> list[ImageItem]:
    """Lists all previously generated diagrams, visuals, and illustrations."""
    return image_service.list_images()


@router.post("/generate", response_model=ImageGenerateResponse)
async def generate_image(request: ImageGenerateRequest) -> ImageGenerateResponse:
    """Generates a high-resolution AI illustration or vector SVG diagram."""
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")
    try:
        return await image_service.generate_image(request)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Image generation failed: {exc}") from exc


@router.get("/{image_id}/file")
async def get_image_file(image_id: str):
    """Streams the raw image file (JPEG, PNG, or SVG) directly to the browser."""
    item = image_service.get_image(image_id)
    if not item:
        raise HTTPException(status_code=404, detail="Image not found")

    # Determine file path on disk
    fmt = item.format.lower()
    file_path = IMAGES_DIR / f"{image_id}.{fmt}"
    if not file_path.exists():
        # Fallback check for svg or jpg
        if (IMAGES_DIR / f"{image_id}.svg").exists():
            file_path = IMAGES_DIR / f"{image_id}.svg"
            fmt = "svg"
        elif (IMAGES_DIR / f"{image_id}.jpg").exists():
            file_path = IMAGES_DIR / f"{image_id}.jpg"
            fmt = "jpg"
        elif (IMAGES_DIR / f"{image_id}.jpeg").exists():
            file_path = IMAGES_DIR / f"{image_id}.jpeg"
            fmt = "jpeg"
        elif (IMAGES_DIR / f"{image_id}.png").exists():
            file_path = IMAGES_DIR / f"{image_id}.png"
            fmt = "png"
        else:
            raise HTTPException(status_code=404, detail="Image file not found on disk")

    media_type = "image/svg+xml" if fmt == "svg" else "image/png" if fmt == "png" else "image/jpeg"
    return FileResponse(file_path, media_type=media_type)


@router.delete("/{image_id}")
async def delete_image(image_id: str) -> dict[str, bool]:
    """Deletes a generated image from the catalog and disk."""
    success = image_service.delete_image(image_id)
    if not success:
        raise HTTPException(status_code=404, detail="Image not found")
    return {"deleted": True}
