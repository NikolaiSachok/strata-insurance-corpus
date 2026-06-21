"""Born-digital PDF rendering: Jinja2 (HTML) -> WeasyPrint (PDF).

Reproducibility: WeasyPrint honours ``SOURCE_DATE_EPOCH`` for the PDF metadata
dates and document id, so we pin it to the model anchor. Same env + same content
-> byte-identical PDF (this is what the determinism test relies on).
"""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

_TEMPLATES = Path(__file__).parent / "templates"


def _ensure_native_libs() -> None:
    """On macOS, WeasyPrint's cairo/pango/gobject live in the Homebrew prefix,
    which the dynamic loader does not search by default. Point the loader at it
    before WeasyPrint imports (the loader reads this env var at each dlopen)."""
    if sys.platform != "darwin":
        return
    for prefix in ("/opt/homebrew/lib", "/usr/local/lib"):
        if os.path.isdir(prefix):
            cur = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")
            if prefix not in cur.split(os.pathsep):
                os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = (prefix + os.pathsep + cur).rstrip(os.pathsep)
            break


@lru_cache(maxsize=1)
def _env():
    # Imported lazily so non-render code paths don't pay the import cost.
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES)),
        autoescape=select_autoescape(["html", "xml", "j2"]),
        keep_trailing_newline=True,
    )


def render_html(template: str, context: dict) -> str:
    return _env().get_template(template).render(**context)


def html_to_pdf_bytes(html: str, source_date_epoch: int) -> bytes:
    """Render HTML to a reproducible PDF byte string."""
    # Pin the build clock for reproducible metadata/ids.
    os.environ["SOURCE_DATE_EPOCH"] = str(int(source_date_epoch))
    _ensure_native_libs()
    from weasyprint import CSS, HTML  # heavy import; keep local

    css = CSS(filename=str(_TEMPLATES / "base.css"))
    return HTML(string=html, base_url=str(_TEMPLATES)).write_pdf(stylesheets=[css])


def write_pdf(template: str, context: dict, out_path: Path, source_date_epoch: int) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    html = render_html(template, context)
    out_path.write_bytes(html_to_pdf_bytes(html, source_date_epoch))
    return out_path
