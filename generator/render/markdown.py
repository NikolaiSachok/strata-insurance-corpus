"""Markdown rendering for knowledge-base documents.

Plain UTF-8 text (inherently deterministic). Carries the synthetic marker both as
an HTML comment and as a visible blockquote under the title.
"""

from __future__ import annotations

from pathlib import Path

from .. import SYNTHETIC_MARKER


def render_markdown(doc: dict) -> str:
    lines = [f"<!-- {SYNTHETIC_MARKER} -->", "", f"# {doc['title']}", "", f"> {SYNTHETIC_MARKER}", ""]
    if doc.get("intro"):
        lines += [doc["intro"], ""]
    for section in doc["sections"]:
        lines += [f"## {section['heading']}", ""]
        for para in section.get("paragraphs", []):
            lines += [para, ""]
        bullets = section.get("bullets", [])
        if bullets:
            lines += [f"- {b}" for b in bullets]
            lines += [""]
    return "\n".join(lines).rstrip() + "\n"


def write_markdown(doc: dict, out_path: Path) -> Path:
    from . import skip_existing

    out_path = Path(out_path)
    if skip_existing(out_path):  # resume: byte-identical .md already on disk
        return out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(render_markdown(doc).encode("utf-8"))
    return out_path
