"""Format renderers: content view-models -> bytes on disk.

M1 ships ``pdf`` (born-digital, via WeasyPrint). docx/xlsx/scan/image land in
M2–M3 per BRIEF.md.

Resumable rendering (#33): the full corpus renders ~750 PDFs through WeasyPrint's native
libraries, which intermittently segfault at scale. Because every renderer is
byte-deterministic (same input -> same bytes), an artifact already on disk from a prior
(crashed) run is re-usable verbatim. In **resume** mode each ``write_*`` returns an existing
output untouched, so a crash-retry *continues* instead of redoing minutes of work. PDF writes
are atomic (temp + ``os.replace``) so a file only exists once fully written — never a truncated
partial after a crash. ``set_resume(True)`` before a resume pass; off by default (a fresh run
re-renders everything, preserving strict byte-stability guarantees).
"""

from pathlib import Path as _Path

_RESUME = False


def set_resume(value: bool) -> None:
    """Enable/disable resume mode for every renderer in this process."""
    global _RESUME
    _RESUME = bool(value)


def skip_existing(out_path) -> bool:
    """True if resume mode is on AND the (byte-deterministic) artifact is already on disk."""
    return _RESUME and _Path(out_path).exists()
