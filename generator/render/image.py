"""Finalize an AI-rendered evidence image into the committed corpus JPG.

The pixels themselves are produced out-of-band by the `/generate-image` skill (a
non-deterministic, paid step). This helper is the deterministic *finalization* of an
already-rendered image: downscale to the corpus size and embed a **synthetic marker in
the file's EXIF metadata** (Software + ImageDescription), so a detached pixel file still
carries its synthetic provenance even though it has no visible watermark (a watermark
would defeat the vision-RAG purpose).

DONE criteria for an evidence image (before it enters `sample/`):
  1. visually verified to honour the prompt's negatives — NO recognizable faces, readable
     number plates, or real brand logos/badges (the model does not guarantee this);
  2. finalized through ``finalize_evidence`` so it carries the EXIF synthetic marker.
"""

from __future__ import annotations

from pathlib import Path

from .. import SYNTHETIC_MARKER

_SOFTWARE = f"Meridian Mutual synthetic corpus — AI-generated, fictional ({SYNTHETIC_MARKER})"


def finalize_evidence(src: Path, out_path: Path, caption: str, max_width: int = 1024, quality: int = 80) -> Path:
    """Downscale + JPEG-encode a rendered image, embedding an EXIF synthetic marker."""
    from PIL import Image

    im = Image.open(src).convert("RGB")
    w, h = im.size
    if w > max_width:
        im = im.resize((max_width, round(h * max_width / w)), Image.LANCZOS)

    exif = im.getexif()
    exif[0x0131] = _SOFTWARE  # Software
    exif[0x010E] = caption  # ImageDescription

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    im.save(out_path, "JPEG", quality=quality, exif=exif)
    return out_path
