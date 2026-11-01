"""
OCR engine: image -> extracted text, using pytesseract (Tesseract OCR).

Kept intentionally small: light preprocessing (grayscale + upscaling
small images) tends to noticeably improve Tesseract's accuracy on
screenshots of tweets/articles, which is the primary expected input.
"""
import io
import os
import platform
import shutil
from PIL import Image, ImageOps
import pytesseract


class OCRError(Exception):
    pass


def _configure_tesseract_path():
    """
    pytesseract shells out to a `tesseract` binary on PATH. On Linux/
    macOS this just works once installed via apt/brew. On Windows, the
    official installer frequently does NOT add it to PATH unless that
    option was explicitly checked during setup, so pytesseract raises
    TesseractNotFoundError even though Tesseract is installed and
    working. Resolve the binary from (in priority order): an explicit
    TESSERACT_CMD env var, the current PATH, then the two default
    Windows install locations — before giving up and letting the real
    error surface with a platform-appropriate message.
    """
    explicit = os.environ.get("TESSERACT_CMD")
    if explicit:
        pytesseract.pytesseract.tesseract_cmd = explicit
        return

    if shutil.which("tesseract"):
        return  # already resolvable on PATH — nothing to do (Linux/macOS default)

    if platform.system() == "Windows":
        for candidate in (
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ):
            if os.path.isfile(candidate):
                pytesseract.pytesseract.tesseract_cmd = candidate
                return


_configure_tesseract_path()


def _preprocess_image(image: Image.Image) -> Image.Image:
    image = ImageOps.exif_transpose(image)  # respect camera orientation
    image = image.convert("L")              # grayscale
    # Upscale small screenshots — Tesseract does much better above ~1000px wide.
    if image.width < 1000:
        scale = 1000 / image.width
        image = image.resize((int(image.width * scale), int(image.height * scale)), Image.LANCZOS)
    return image


def extract_text_from_bytes(file_bytes: bytes) -> dict:
    """
    Runs OCR on raw image bytes. Returns a dict with the extracted text
    and a rough confidence estimate. Raises OCRError on failure (corrupt
    image, unreadable format, tesseract binary missing, etc.) so the
    caller can return a clear error instead of crashing.
    """
    try:
        image = Image.open(io.BytesIO(file_bytes))
        image.load()
    except Exception as exc:  # noqa: BLE001
        raise OCRError(f"Could not read image file: {exc}") from exc

    try:
        processed = _preprocess_image(image)
        raw_text = pytesseract.image_to_string(processed)
        data = pytesseract.image_to_data(processed, output_type=pytesseract.Output.DICT)
    except pytesseract.TesseractNotFoundError as exc:
        raise OCRError(
            "Tesseract OCR engine was not found. Install it and make sure it's "
            "reachable: Linux — `apt-get install tesseract-ocr`; macOS — "
            "`brew install tesseract`; Windows — install from "
            "https://github.com/UB-Mannheim/tesseract/wiki, then either check "
            "'Add to PATH' during setup or set the TESSERACT_CMD environment "
            "variable to the full path of tesseract.exe."
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise OCRError(f"OCR processing failed: {exc}") from exc

    confidences = [int(c) for c in data.get("conf", []) if str(c).lstrip("-").isdigit() and int(c) >= 0]
    avg_conf = round(sum(confidences) / len(confidences), 1) if confidences else 0.0

    text = raw_text.strip()
    if not text:
        raise OCRError(
            "No text could be detected in this image. Try a clearer "
            "screenshot with visible, upright text."
        )

    return {"text": text, "confidence": avg_conf}
