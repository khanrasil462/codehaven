from __future__ import annotations

import io
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from PIL import Image

OCR_HELPER_PS1 = Path(__file__).resolve().parent / "ocr_helper.ps1"


def run_windows_native_ocr(image_path: str | Path) -> str:
    """Executes native Windows.Media.Ocr via PowerShell helper script."""
    if not OCR_HELPER_PS1.exists():
        return ""

    try:
        cmd = [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(OCR_HELPER_PS1),
            "-ImagePath",
            str(image_path),
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def run_tesseract_ocr(image_path: str | Path) -> str:
    """Optional fallback if tesseract-ocr is installed."""
    try:
        import pytesseract
        text = pytesseract.image_to_string(str(image_path))
        return text.strip()
    except Exception:
        return ""


def ocr_image_bytes(image_bytes: bytes) -> str:
    """Performs OCR on raw image bytes (PNG, JPEG, WEBP, BMP, etc.)."""
    if not image_bytes:
        return ""

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        # Load and convert image to RGB PNG for best OCR results
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode != "RGB":
            img = img.convert("RGB")

        # Upscale small images to improve character recognition
        w, h = img.size
        if w < 1000 and h < 1000:
            scale = max(2, int(1500 / max(w, h)))
            img = img.resize((w * scale, h * scale), Image.Resampling.LANCZOS)

        img.save(tmp_path, format="PNG")

        # 1. Native Windows OCR
        text = run_windows_native_ocr(tmp_path)
        if text.strip():
            return text

        # 2. Tesseract fallback
        text = run_tesseract_ocr(tmp_path)
        if text.strip():
            return text

        return ""
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


def ocr_scanned_pdf(pdf_bytes: bytes) -> str:
    """Renders scanned PDF pages to high-res images and performs OCR on each page."""
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return ""

    try:
        pdf = pdfium.PdfDocument(pdf_bytes)
    except Exception:
        return ""

    extracted_pages: list[str] = []
    for page_idx, page in enumerate(pdf):
        try:
            # Render page at 2x scale (~144-200 DPI) for high OCR accuracy
            pil_image = page.render(scale=2.0).to_pil()
            img_byte_arr = io.BytesIO()
            pil_image.save(img_byte_arr, format="PNG")
            img_bytes = img_byte_arr.getvalue()

            page_text = ocr_image_bytes(img_bytes)
            if page_text.strip():
                extracted_pages.append(
                    f"--- Page {page_idx + 1} (Scanned OCR) ---\n{page_text.strip()}"
                )
        except Exception:
            continue

    return "\n\n".join(extracted_pages)
