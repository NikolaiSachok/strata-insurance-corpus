"""Reproducibility helpers shared by the zip-container renderers (docx, xlsx).

A .docx / .xlsx is a zip whose member timestamps and core-property dates are
otherwise wall-clock. Pin the dates (done by each renderer) and re-pack the
archive deterministically here, so the same content -> byte-identical file.
"""

from __future__ import annotations

import datetime as dt
import io
import zipfile

# Fixed packaging clock (the model anchor). Not a wall-clock read.
FIXED_DT = dt.datetime(2024, 7, 1, 0, 0, 0)
_ZIP_MTIME = (1980, 1, 1, 0, 0, 0)  # zip epoch floor — constant, content-independent


def normalize_zip(raw: bytes, rewrite=None) -> bytes:
    """Re-pack a zip (docx/xlsx) deterministically: sorted members, fixed mtime.

    ``rewrite`` is an optional ``(name, data) -> data`` hook applied per member —
    used by the xlsx renderer to pin the ``dcterms:modified`` timestamp that
    openpyxl stamps with the wall clock at save time.
    """
    src = zipfile.ZipFile(io.BytesIO(raw))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(src.namelist()):
            data = src.read(name)
            if rewrite is not None:
                data = rewrite(name, data)
            zi = zipfile.ZipInfo(name, date_time=_ZIP_MTIME)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            z.writestr(zi, data)
    return out.getvalue()
