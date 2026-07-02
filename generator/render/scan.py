"""Scan-effect renderer: a born-digital PDF -> a degraded "scanned" raster (forces OCR).

Takes a document we already render (FNOL, letters — with known ground-truth text),
rasterizes the first page (pypdfium2), and applies seeded scan effects: grayscale,
slight blur, skew (small rotation on white), sensor/paper noise, and lossy JPEG. The
clean source keeps the ground truth; the scanned variant is the OCR/vision target.

Determinism: the effects are driven by a per-document seed, and rasterization + Pillow
ops are deterministic, so the same (source, seed) -> byte-identical scanned image.
"""

from __future__ import annotations

import random
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter


def doc_seed(doc_id: str, corpus_seed: int) -> int:
    """Stable per-document seed (no salted hash)."""
    return corpus_seed * 100003 + sum(ord(c) for c in doc_id)


def scan_pdf(
    pdf_path: Path,
    out_path: Path,
    seed: int,
    dpi: int = 150,
    max_width: int = 1000,
    jpeg_quality: int = 58,
) -> Path:
    from . import skip_existing

    out_path = Path(out_path)
    if skip_existing(out_path):  # resume: byte-identical scan already on disk
        return out_path
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        # Forms/letters are single-page by construction. Fail loudly rather than silently
        # dropping content if a future (e.g. LLM-authored) source ever spans >1 page.
        if len(pdf) != 1:
            raise ValueError(f"scan_pdf expects a single-page document, got {len(pdf)} pages: {pdf_path}")
        im = pdf[0].render(scale=dpi / 72).to_pil().convert("L")  # rasterize on white -> grayscale
    finally:
        pdf.close()

    rng = random.Random(seed)
    im = ImageEnhance.Contrast(im).enhance(1.15)
    im = im.filter(ImageFilter.GaussianBlur(0.5))
    # skew: a small rotation, filling the corners with white paper
    im = im.rotate(rng.uniform(-1.8, 1.8), expand=True, fillcolor=255, resample=Image.BICUBIC)
    # downscale to scan resolution before noise (keeps it fast + small)
    w, h = im.size
    if w > max_width:
        im = im.resize((max_width, int(h * max_width / w)), Image.LANCZOS)
    # sensor/paper noise
    px = im.load()
    w, h = im.size
    for _ in range((w * h) // 18):
        x, y = rng.randrange(w), rng.randrange(h)
        px[x, y] = max(0, min(255, px[x, y] + rng.randint(-38, 38)))

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    im.convert("RGB").save(out_path, "JPEG", quality=jpeg_quality)
    return out_path
